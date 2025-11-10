"""UiPath Developer Console run service module."""

from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathExecutionRuntime,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeStatus,
)
from uipath.runtime.errors import UiPathErrorContract, UiPathRuntimeError

from uipath.dev.infrastructure import RunContextExporter, RunContextLogHandler
from uipath.dev.models import ExecutionRun, LogMessage, TraceMessage

RunUpdatedCallback = Callable[[ExecutionRun], None]
LogCallback = Callable[[LogMessage], None]
TraceCallback = Callable[[TraceMessage], None]


class RunService:
    """Orchestrates execution runs and keeps ExecutionRun state in sync.

    - Executes / resumes runtimes
    - Updates run status, timings, output, and error
    - Collects logs and traces
    - Notifies observers via callbacks
    """

    def __init__(
        self,
        runtime_factory: UiPathRuntimeFactoryProtocol,
        trace_manager: UiPathTraceManager,
        on_run_updated: Optional[RunUpdatedCallback] = None,
        on_log: Optional[LogCallback] = None,
        on_trace: Optional[TraceCallback] = None,
    ) -> None:
        """Initialize RunService with runtime factory and trace manager."""
        self.runtime_factory = runtime_factory
        self.trace_manager = trace_manager
        self.runs: Dict[str, ExecutionRun] = {}

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

    def register_run(self, run: ExecutionRun) -> None:
        """Register a new run and emit an initial update."""
        self.runs[run.id] = run
        self._emit_run_updated(run)

    def get_run(self, run_id: str) -> Optional[ExecutionRun]:
        """Get a registered run."""
        return self.runs.get(run_id)

    async def execute(self, run: ExecutionRun) -> None:
        """Execute or resume a run.

        This is the extracted version of the old `_execute_runtime` method.
        """
        try:
            execution_input: Optional[dict[str, Any]] = {}
            execution_options: UiPathExecuteOptions = UiPathExecuteOptions()

            if run.status == "suspended":
                execution_input = run.resume_data
                execution_options.resume = True
                self._add_info_log(run, f"Resuming execution: {run.entrypoint}")
            else:
                execution_input = run.input_data
                self._add_info_log(run, f"Starting execution: {run.entrypoint}")

            run.status = "running"
            run.start_time = datetime.now()
            self._emit_run_updated(run)

            # Attach log handler that goes back into this service
            log_handler = RunContextLogHandler(
                run_id=run.id,
                callback=self.handle_log,
            )

            runtime = await self.runtime_factory.new_runtime(entrypoint=run.entrypoint)

            execution_runtime = UiPathExecutionRuntime(
                delegate=runtime,
                trace_manager=self.trace_manager,
                log_handler=log_handler,
                execution_id=run.id,
            )

            result = await execution_runtime.execute(execution_input, execution_options)

            if result is not None:
                if (
                    result.status == UiPathRuntimeStatus.SUSPENDED.value
                    and result.resume
                ):
                    run.status = "suspended"
                else:
                    if result.output is None:
                        run.output_data = {}
                    elif isinstance(result.output, BaseModel):
                        run.output_data = result.output.model_dump()
                    else:
                        run.output_data = result.output
                    run.status = "completed"

                if run.output_data:
                    self._add_info_log(run, f"Execution result: {run.output_data}")

            self._add_info_log(run, "✅ Execution completed successfully")
            run.end_time = datetime.now()

        except UiPathRuntimeError as e:
            self._add_error_log(run)
            run.status = "failed"
            run.end_time = datetime.now()
            run.error = e.error_info

        except Exception as e:
            self._add_error_log(run)
            run.status = "failed"
            run.end_time = datetime.now()
            run.error = UiPathErrorContract(
                code="Unknown",
                title=str(e),
                detail=traceback.format_exc(),
            )

        self.runs[run.id] = run
        self._emit_run_updated(run)

    def handle_log(self, log_msg: LogMessage) -> None:
        """Entry point for all logs (runtime, traces, stderr)."""
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
            # Update or append trace
            for i, existing_trace in enumerate(run.traces):
                if existing_trace.span_id == trace_msg.span_id:
                    run.traces[i] = trace_msg
                    break
            else:
                run.traces.append(trace_msg)

            self._emit_run_updated(run)

        if self.on_trace is not None:
            self.on_trace(trace_msg)

    def _emit_run_updated(self, run: ExecutionRun) -> None:
        """Notify observers that a run's state changed."""
        self.runs[run.id] = run
        if self.on_run_updated is not None:
            self.on_run_updated(run)

    def _add_info_log(self, run: ExecutionRun, message: str) -> None:
        log_msg = LogMessage(
            run_id=run.id,
            level="INFO",
            message=message,
            timestamp=datetime.now(),
        )
        self.handle_log(log_msg)

    def _add_error_log(self, run: ExecutionRun) -> None:
        from rich.traceback import Traceback

        tb = Traceback(
            show_locals=False,
            max_frames=4,
        )
        log_msg = LogMessage(
            run_id=run.id,
            level="ERROR",
            message=tb,
            timestamp=datetime.now(),
        )
        self.handle_log(log_msg)
