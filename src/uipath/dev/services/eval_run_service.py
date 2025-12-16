"""Service for executing eval runs."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from uipath._cli._evals._console_progress_reporter import ConsoleProgressReporter
from uipath._cli._evals._evaluate import evaluate
from uipath._cli._evals._progress_reporter import StudioWebProgressReporter
from uipath._cli._evals._runtime import UiPathEvalContext
from uipath._cli._utils._eval_set import EvalHelpers
from uipath._cli._utils._folders import get_personal_workspace_key_async
from uipath._cli._utils._studio_project import StudioClient
from uipath._config import UiPathConfig
from uipath._events._event_bus import EventBus
from uipath._utils._bindings import ResourceOverwritesContext
from uipath.core.tracing import UiPathTraceManager
from uipath.eval._helpers import auto_discover_entrypoint
from uipath.runtime import (
    UiPathRuntimeContext,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeFactoryRegistry,
)
from uipath.runtime.errors import UiPathErrorContract
from uipath.tracing import LlmOpsHttpExporter

from uipath.dev.infrastructure import RunContextExporter
from uipath.dev.models import LogMessage, TraceMessage
from uipath.dev.models.eval_run import EvalRun, EvaluationResult, EvaluatorResult

EvalRunUpdatedCallback = Callable[[EvalRun], None]
EvalLogCallback = Callable[[LogMessage], None]
EvalTraceCallback = Callable[[TraceMessage], None]


class EvalRunService:
    """Orchestrates eval runs."""

    def __init__(
        self,
        trace_manager: UiPathTraceManager | None = None,
        on_run_updated: EvalRunUpdatedCallback | None = None,
        on_log: EvalLogCallback | None = None,
        on_trace: EvalTraceCallback | None = None,
    ):
        """Initialize the eval run service.

        Args:
            trace_manager: Trace manager for tracing (created if not provided).
            on_run_updated: Callback when an eval run is updated.
            on_log: Callback for log messages during evaluation.
            on_trace: Callback for trace messages during evaluation.
        """
        self.trace_manager = trace_manager or UiPathTraceManager()
        self.runs: dict[str, EvalRun] = {}

        self.on_run_updated = on_run_updated
        self.on_log = on_log
        self.on_trace = on_trace

        self.trace_manager.add_span_exporter(
            RunContextExporter(
                on_trace=self.handle_trace,
                on_log=self.handle_log,
            ),
            batch=False,
        )

    def register_run(self, run: EvalRun) -> None:
        """Register a new run and emit an initial update."""
        self.runs[run.id] = run
        self._emit_run_updated(run)

    def get_run(self, run_id: str) -> EvalRun | None:
        """Get a registered run."""
        return self.runs.get(run_id)

    def get_runs_for_eval_set(self, eval_set_name: str) -> list[EvalRun]:
        """Get all runs for an eval set.

        Args:
            eval_set_name: Name of the eval set.

        Returns:
            List of EvalRun objects for the given eval set (newest first).
        """
        matching_runs = [
            run
            for run in self.runs.values()
            if Path(run.eval_set_path).stem == eval_set_name
        ]
        # Sort by start_time descending (newest first)
        matching_runs.sort(key=lambda r: r.start_time, reverse=True)
        return matching_runs

    async def execute(self, run: EvalRun) -> None:
        """Execute an eval run."""
        try:
            self._add_info_log(run, "Starting evaluation run...")
            self._add_info_log(run, f"  Eval set path: {run.eval_set_path}")
            self._add_info_log(run, f"  Entrypoint: {run.entrypoint}")
            self._add_info_log(run, f"  Workers: {run.workers}")

            run.status = "running"
            self._emit_run_updated(run)

            # Setup reporting prerequisites
            should_register_progress_reporter = await self._setup_reporting_prereq(run)

            event_bus = EventBus()

            # Register progress reporters
            if should_register_progress_reporter:
                progress_reporter = StudioWebProgressReporter(LlmOpsHttpExporter())
                await progress_reporter.subscribe_to_eval_runtime_events(event_bus)

            # Create eval context
            eval_context = UiPathEvalContext()
            eval_context.entrypoint = run.entrypoint or auto_discover_entrypoint()
            eval_context.no_report = run.no_report
            eval_context.workers = run.workers
            eval_context.eval_set_run_id = run.eval_set_run_id
            eval_context.enable_mocker_cache = run.enable_mocker_cache

            # Resolve eval set path
            eval_set_path = run.eval_set_path
            _, resolved_eval_set_path = EvalHelpers.load_eval_set(
                eval_set_path, run.eval_ids
            )
            eval_context.eval_set = resolved_eval_set_path
            eval_context.eval_ids = run.eval_ids
            eval_context.report_coverage = run.report_coverage

            # Register console reporter
            console_reporter = ConsoleProgressReporter()
            await console_reporter.subscribe_to_eval_runtime_events(event_bus)

            self._add_info_log(run, f"Entrypoint: {eval_context.entrypoint}")
            self._add_info_log(run, f"Eval set: {eval_set_path}")

            # Execute evaluation
            results = await self._execute_eval(
                eval_context, event_bus, run.output_file
            )

            # Parse results and update EvalRun
            self._parse_eval_results(run, results, run.output_file)

            run.status = "completed"
            self._add_info_log(
                run,
                f"Evaluation completed. Overall score: {run.overall_score * 100:.1f}%",
            )

        except SystemExit as e:
            run.status = "failed"
            run.end_time = datetime.now()
            error_msg = f"Evaluation process exited with code: {e.code}"
            run.error = UiPathErrorContract(
                code="SystemExit",
                title=error_msg,
                detail="",
            )
            self._add_error_log(run, f"SystemExit caught - {error_msg}")
            self._emit_run_updated(run)
            raise RuntimeError(error_msg) from e

        except BaseException as e:
            run.status = "failed"
            run.end_time = datetime.now()
            import traceback

            exc_type = type(e).__name__
            exc_str = str(e) if str(e) else "(no message)"
            error_msg = f"{exc_type}: {exc_str}"
            run.error = UiPathErrorContract(
                code=exc_type,
                title=exc_str,
                detail=traceback.format_exc(),
            )
            self._add_error_log(run, f"Exception caught - type: {exc_type}, message: {exc_str}")
            self._add_error_log(run, traceback.format_exc())
            self._emit_run_updated(run)
            if isinstance(e, Exception):
                raise
            else:
                raise RuntimeError(error_msg) from e

        self._emit_run_updated(run)

    def _emit_run_updated(self, run: EvalRun) -> None:
        """Notify observers that a run's state changed."""
        self.runs[run.id] = run
        if self.on_run_updated is not None:
            self.on_run_updated(run)

    def handle_log(self, log_msg: LogMessage) -> None:
        """Entry point for all logs."""
        run = self.runs.get(log_msg.run_id)
        if run is not None:
            run.logs.append(log_msg)
            self._emit_run_updated(run)

        if self.on_log is not None:
            self.on_log(log_msg)

    def handle_trace(self, trace_msg: TraceMessage) -> None:
        """Entry point for traces (from RunContextExporter)."""
        run = self.runs.get(trace_msg.run_id)
        if run is not None:
            # Update or append trace (upsert by span_id)
            for i, existing_trace in enumerate(run.traces):
                if existing_trace.span_id == trace_msg.span_id:
                    run.traces[i] = trace_msg
                    break
            else:
                run.traces.append(trace_msg)

            self._emit_run_updated(run)

        if self.on_trace is not None:
            self.on_trace(trace_msg)

    def _add_info_log(self, run: EvalRun, message: str) -> None:
        log_msg = LogMessage(
            run_id=run.id,
            level="INFO",
            message=message,
            timestamp=datetime.now(),
        )
        self.handle_log(log_msg)

    def _add_error_log(self, run: EvalRun, message: str) -> None:
        log_msg = LogMessage(
            run_id=run.id,
            level="ERROR",
            message=message,
            timestamp=datetime.now(),
        )
        self.handle_log(log_msg)

    async def _setup_reporting_prereq(self, run: EvalRun) -> bool:
        """Setup reporting prerequisites."""
        if run.no_report:
            return False

        if not UiPathConfig.is_studio_project:
            self._add_info_log(
                run,
                "UIPATH_PROJECT_ID not set. Results will not be reported to Studio Web.",
            )
            return False

        if not UiPathConfig.folder_key:
            folder_key = await get_personal_workspace_key_async()
            if folder_key:
                os.environ["UIPATH_FOLDER_KEY"] = folder_key
        return True

    async def _execute_eval(
        self,
        eval_context: UiPathEvalContext,
        event_bus: EventBus,
        output_file: str | None = None,
    ) -> Any:
        """Execute the evaluation.

        Creates a new runtime factory inside the context and disposes it at the end.
        """
        with UiPathRuntimeContext.with_defaults(
            output_file=output_file,
            trace_manager=self.trace_manager,
            command="eval",
        ) as ctx:
            if ctx.job_id:
                self.trace_manager.add_span_exporter(LlmOpsHttpExporter())

            project_id = UiPathConfig.project_id

            # Create runtime factory inside context
            runtime_factory = UiPathRuntimeFactoryRegistry.get(context=ctx)

            try:
                if project_id:
                    studio_client = StudioClient(project_id)

                    async with ResourceOverwritesContext(
                        lambda: studio_client.get_resource_overwrites()
                    ):
                        ctx.result = await evaluate(
                            runtime_factory,
                            self.trace_manager,
                            eval_context,
                            event_bus,
                        )
                else:
                    ctx.result = await evaluate(
                        runtime_factory, self.trace_manager, eval_context, event_bus
                    )
            finally:
                # Dispose runtime factory
                if runtime_factory:
                    await runtime_factory.dispose()

            return ctx.result

    def _parse_eval_results(
        self,
        run: EvalRun,
        results: Any,
        output_file: str | None = None,
    ) -> None:
        """Parse evaluation results and populate the EvalRun."""
        data = None

        # Try to get data from results
        if results and hasattr(results, "output") and results.output:
            try:
                if isinstance(results.output, str):
                    data = json.loads(results.output)
                elif isinstance(results.output, dict):
                    data = results.output
            except Exception:
                pass

        # Try to read from output file if no data yet
        if not data and output_file:
            try:
                output_path = Path(output_file)
                if output_path.exists():
                    with open(output_path, "r") as f:
                        data = json.load(f)
            except Exception:
                pass

        if not data:
            return

        # Parse the evaluation set results
        eval_set_results = data.get("evaluationSetResults", [])

        for eval_result_data in eval_set_results:
            eval_name = eval_result_data.get("evaluationName", "Unknown")
            eval_id = eval_result_data.get("evaluationId", eval_name)

            eval_result = EvaluationResult(eval_id=eval_id, eval_name=eval_name)

            eval_run_results = eval_result_data.get("evaluationRunResults", [])
            for run_result in eval_run_results:
                evaluator_name = run_result.get("evaluatorName", "Unknown")
                result_data = run_result.get("result", {})

                eval_result.evaluator_results.append(
                    EvaluatorResult(
                        evaluator_id=evaluator_name,
                        evaluator_name=evaluator_name,
                        score=result_data.get("score", 0.0),
                        details=str(result_data.get("details", "")),
                        evaluation_time=result_data.get("evaluationTime", 0.0),
                        justification=result_data.get("justification", ""),
                    )
                )

            run.evaluation_results.append(eval_result)
