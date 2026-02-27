"""Evaluation service — discovers eval sets, executes runs, reports progress."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import StatusCode
from uipath.core.events import EventBus
from uipath.core.tracing import UiPathTraceManager
from uipath.eval.helpers import EvalHelpers
from uipath.eval.runtime import UiPathEvalContext, evaluate
from uipath.eval.runtime.events import (
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunUpdatedEvent,
    EvaluationEvents,
)
from uipath.runtime import UiPathRuntimeFactoryProtocol

from uipath.dev.models.eval_data import EvalItemResult, EvalRunState, EvalSetInfo

logger = logging.getLogger(__name__)


def _convert_span(span: ReadableSpan) -> dict[str, Any]:
    """Convert an OpenTelemetry ReadableSpan to a serializable dict."""
    start_time = span.start_time / 1_000_000_000 if span.start_time is not None else 0
    end_time = span.end_time / 1_000_000_000 if span.end_time is not None else None
    duration_ms = (end_time - start_time) * 1000 if end_time else None

    if span.status.status_code == StatusCode.ERROR:
        status = "failed"
    elif end_time:
        status = "completed"
    else:
        status = "running"

    span_context = span.get_span_context()
    span_id = f"{span_context.span_id:016x}"
    trace_id = f"{span_context.trace_id:032x}"

    parent_span_id = None
    if hasattr(span, "parent") and span.parent:
        parent_span_id = f"{span.parent.span_id:016x}"

    return {
        "span_name": span.name,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "trace_id": trace_id,
        "status": status,
        "duration_ms": duration_ms,
        "timestamp": datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
        "attributes": dict(span.attributes) if span.attributes else {},
    }


class EvalService:
    """Discovers evaluation sets and executes eval runs."""

    def __init__(
        self,
        *,
        runtime_factory: UiPathRuntimeFactoryProtocol,
        trace_manager: UiPathTraceManager,
        on_eval_run_created: Callable[[EvalRunState], None] | None = None,
        on_eval_run_progress: Callable[[str, int, int, EvalItemResult | None], None]
        | None = None,
        on_eval_run_completed: Callable[[EvalRunState], None] | None = None,
    ) -> None:
        """Initialize the eval service."""
        self.runtime_factory = runtime_factory
        self.trace_manager = trace_manager
        self._eval_sets: dict[str, dict[str, Any]] = {}
        self._eval_set_paths: dict[str, str] = {}
        self._eval_runs: dict[str, EvalRunState] = {}
        self._on_eval_run_created = on_eval_run_created
        self._on_eval_run_progress = on_eval_run_progress
        self._on_eval_run_completed = on_eval_run_completed

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_eval_set(self, name: str, evaluator_refs: list[str]) -> EvalSetInfo:
        """Create a new eval set JSON file on disk and update internal cache."""
        slug = name.lower().replace(" ", "-")
        evals_dir = Path.cwd() / "evaluations" / "eval-sets"
        evals_dir.mkdir(parents=True, exist_ok=True)

        filepath = evals_dir / f"{slug}.json"
        if filepath.exists():
            raise FileExistsError(f"Eval set '{slug}' already exists")

        data: dict[str, Any] = {
            "id": slug,
            "name": name,
            "version": "1.0",
            "evaluatorRefs": evaluator_refs,
            "evaluations": [],
        }
        filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")

        self._eval_sets[slug] = data
        self._eval_set_paths[slug] = str(filepath)

        return EvalSetInfo(
            id=slug,
            name=name,
            eval_count=0,
            evaluator_ids=evaluator_refs,
        )

    def update_eval_set_evaluators(
        self, set_id: str, evaluator_refs: list[str]
    ) -> dict[str, Any]:
        """Update the evaluators for an eval set and sync item criterias."""
        if set_id not in self._eval_sets:
            self.discover_eval_sets()

        raw = self._eval_sets.get(set_id)
        if raw is None:
            raise KeyError(f"Eval set '{set_id}' not found")

        old_refs = set(raw.get("evaluatorRefs", raw.get("evaluator_refs", [])))
        new_refs = set(evaluator_refs)
        added = new_refs - old_refs
        removed = old_refs - new_refs

        raw["evaluatorRefs"] = evaluator_refs

        for item in raw.get("evaluations", []):
            criterias = item.setdefault("evaluationCriterias", {})
            for ev_id in added:
                if ev_id not in criterias:
                    criterias[ev_id] = {}
            for ev_id in removed:
                criterias.pop(ev_id, None)

        filepath = Path(self._eval_set_paths[set_id])
        filepath.write_text(json.dumps(raw, indent=2), encoding="utf-8")

        return self.get_eval_set_detail(set_id)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_eval_sets(self) -> list[EvalSetInfo]:
        """Scan the evaluations/ directory for JSON eval set files."""
        evals_dir = Path.cwd() / "evaluations" / "eval-sets"
        self._eval_sets.clear()
        self._eval_set_paths.clear()

        if not evals_dir.is_dir():
            return []

        results: list[EvalSetInfo] = []
        for json_file in sorted(evals_dir.glob("*.json")):
            try:
                raw = json.loads(json_file.read_text(encoding="utf-8"))
                set_id = json_file.stem
                name = raw.get("name", set_id)
                items = raw.get("evaluations", [])

                # Extract evaluator refs
                evaluator_ids = raw.get("evaluatorRefs", raw.get("evaluator_refs", []))

                self._eval_sets[set_id] = raw
                self._eval_set_paths[set_id] = str(json_file)
                results.append(
                    EvalSetInfo(
                        id=set_id,
                        name=name,
                        eval_count=len(items),
                        evaluator_ids=evaluator_ids,
                    )
                )
            except Exception:
                logger.warning("Failed to parse eval set: %s", json_file, exc_info=True)

        return results

    @staticmethod
    def _build_item(
        item: dict[str, Any], index: int, evaluator_ids: list[str]
    ) -> dict[str, Any]:
        """Build a single eval item dict from raw JSON."""
        criterias = item.get("evaluationCriterias", {})

        # Extract expected_output: item-level first, then first evaluator criteria
        expected_output = item.get("expectedOutput", item.get("expected_output", None))
        if expected_output is None:
            for ev_criteria in criterias.values():
                if isinstance(ev_criteria, dict) and "expectedOutput" in ev_criteria:
                    expected_output = ev_criteria["expectedOutput"]
                    break

        return {
            "name": item.get("name", f"item-{index}"),
            "inputs": item.get("inputs", item.get("input", {})),
            "expected_behavior": item.get(
                "expected_behavior",
                item.get("expectedBehavior", ""),
            ),
            "expected_output": expected_output,
            "simulation_instructions": item.get(
                "simulationInstructions",
                item.get("simulation_instructions", ""),
            ),
            "evaluation_criterias": criterias,
            "evaluator_ids": item.get("evaluator_ids", evaluator_ids),
        }

    def add_eval_item(
        self,
        set_id: str,
        name: str,
        inputs: dict[str, Any],
        expected_output: Any,
        *,
        evaluation_criterias: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Append a new item to an eval set and persist to disk."""
        if set_id not in self._eval_sets:
            self.discover_eval_sets()

        raw = self._eval_sets.get(set_id)
        if raw is None:
            raise KeyError(f"Eval set '{set_id}' not found")

        evaluator_ids = raw.get("evaluatorRefs", raw.get("evaluator_refs", []))
        criterias: dict[str, Any] = {}
        if evaluation_criterias is not None:
            # Use per-evaluator criteria as provided by the frontend
            criterias = evaluation_criterias
        elif expected_output is not None:
            # Backward compat: set expectedOutput on all evaluators
            for ev_id in evaluator_ids:
                criterias[ev_id] = {"expectedOutput": expected_output}

        item: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "name": name,
            "inputs": inputs,
            "evaluationCriterias": criterias,
        }
        raw.setdefault("evaluations", []).append(item)

        filepath = Path(self._eval_set_paths[set_id])
        filepath.write_text(json.dumps(raw, indent=2), encoding="utf-8")

        evaluator_ids = raw.get("evaluatorRefs", raw.get("evaluator_refs", []))
        index = len(raw["evaluations"]) - 1
        return self._build_item(item, index, evaluator_ids)

    def delete_eval_item(self, set_id: str, item_name: str) -> None:
        """Remove an item by name from an eval set and persist to disk."""
        if set_id not in self._eval_sets:
            self.discover_eval_sets()

        raw = self._eval_sets.get(set_id)
        if raw is None:
            raise KeyError(f"Eval set '{set_id}' not found")

        evaluations = raw.get("evaluations", [])
        for i, item in enumerate(evaluations):
            if item.get("name") == item_name:
                evaluations.pop(i)
                break
        else:
            raise KeyError(f"Item '{item_name}' not found in eval set '{set_id}'")

        filepath = Path(self._eval_set_paths[set_id])
        filepath.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def get_eval_set_detail(self, set_id: str) -> dict[str, Any] | None:
        """Get full eval set data including items."""
        if set_id not in self._eval_sets:
            self.discover_eval_sets()

        raw = self._eval_sets.get(set_id)
        if raw is None:
            return None

        items = raw.get("evaluations", [])
        evaluator_ids = raw.get("evaluatorRefs", raw.get("evaluator_refs", []))

        return {
            "id": set_id,
            "name": raw.get("name", set_id),
            "eval_count": len(items),
            "evaluator_ids": evaluator_ids,
            "items": [
                self._build_item(item, i, evaluator_ids) for i, item in enumerate(items)
            ],
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def get_eval_run(self, run_id: str) -> EvalRunState | None:
        """Get an eval run by ID."""
        return self._eval_runs.get(run_id)

    def list_eval_runs(self) -> list[EvalRunState]:
        """List all eval runs."""
        return list(self._eval_runs.values())

    async def start_eval_run(self, eval_set_id: str) -> EvalRunState | None:
        """Start an eval run for the given eval set."""
        detail = self.get_eval_set_detail(eval_set_id)
        if detail is None:
            return None

        run = EvalRunState(
            eval_set_id=eval_set_id,
            eval_set_name=detail["name"],
            progress_total=len(detail["items"]),
        )
        # Pre-populate pending results
        for item in detail["items"]:
            run.results.append(
                EvalItemResult(
                    name=item["name"],
                    inputs=item.get("inputs", {}),
                    expected_output=item.get("expected_output"),
                    status="pending",
                )
            )

        self._eval_runs[run.id] = run

        if self._on_eval_run_created:
            self._on_eval_run_created(run)

        # Execute in background
        asyncio.create_task(self._execute_eval_run(run))

        return run

    async def _execute_eval_run(self, run: EvalRunState) -> None:
        """Execute eval run using uipath.eval.runtime.evaluate()."""
        run.start()

        try:
            eval_set_path = self._eval_set_paths.get(run.eval_set_id)
            if eval_set_path is None:
                raise ValueError(f"Eval set path not found for {run.eval_set_id}")

            # Load eval set and evaluators using EvalHelpers
            eval_set, resolved_path = EvalHelpers.load_eval_set(eval_set_path)
            evaluators = await EvalHelpers.load_evaluators(resolved_path, eval_set)

            # Get runtime schema from factory
            entrypoint = self.runtime_factory.discover_entrypoints()[0]
            runtime = await self.runtime_factory.new_runtime(
                entrypoint, str(uuid.uuid4())
            )
            runtime_schema = await runtime.get_schema()

            # Build context
            context = UiPathEvalContext()
            context.runtime_schema = runtime_schema
            context.evaluation_set = eval_set
            context.evaluators = evaluators
            context.execution_id = run.id
            context.entrypoint = entrypoint

            # Create event bus and subscribe for progress
            event_bus = EventBus()
            item_index = 0

            async def on_eval_run_created(event: EvalRunCreatedEvent) -> None:
                logger.debug("Eval item created: %s", event.eval_item.name)

            async def on_eval_run_updated(
                event: EvalRunUpdatedEvent,
            ) -> None:
                nonlocal item_index
                idx = item_index
                item_index += 1

                item_result = run.results[idx] if idx < len(run.results) else None
                if item_result is None:
                    return

                item_result.status = "completed" if event.success else "failed"

                if not event.success and event.exception_details:
                    item_result.error = str(event.exception_details.exception)

                # Map eval results to scores
                for er in event.eval_results:
                    ev_id = er.evaluator_id
                    item_result.scores[ev_id] = (
                        float(er.result.score) if er.result.score is not None else 0.0
                    )
                    if er.result.details:
                        item_result.justifications[ev_id] = str(er.result.details)

                if item_result.scores:
                    item_result.overall_score = sum(item_result.scores.values()) / len(
                        item_result.scores
                    )

                agent_out = event.agent_output
                if isinstance(agent_out, Exception):
                    item_result.output = str(agent_out)
                else:
                    item_result.output = agent_out
                item_result.duration_ms = event.agent_execution_time * 1000
                item_result.traces = [_convert_span(s) for s in event.spans]

                run.progress_completed = idx + 1
                if self._on_eval_run_progress:
                    self._on_eval_run_progress(
                        run.id,
                        run.progress_completed,
                        run.progress_total,
                        item_result,
                    )

            async def on_eval_set_run_updated(
                event: EvalSetRunUpdatedEvent,
            ) -> None:
                run.evaluator_scores = event.evaluator_scores

            event_bus.subscribe(EvaluationEvents.CREATE_EVAL_RUN, on_eval_run_created)
            event_bus.subscribe(EvaluationEvents.UPDATE_EVAL_RUN, on_eval_run_updated)
            event_bus.subscribe(
                EvaluationEvents.UPDATE_EVAL_SET_RUN,
                on_eval_set_run_updated,
            )

            # Run the evaluation
            await evaluate(
                runtime_factory=self.runtime_factory,
                trace_manager=self.trace_manager,
                eval_context=context,
                event_bus=event_bus,
            )

            run.complete()
        except Exception:
            logger.exception("Eval run %s failed", run.id)
            run.fail()

        if self._on_eval_run_completed:
            self._on_eval_run_completed(run)
