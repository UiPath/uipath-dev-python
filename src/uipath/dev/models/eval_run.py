"""Model for evaluation runs."""

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from rich.text import Text
from uipath.runtime.errors import UiPathErrorContract

if TYPE_CHECKING:
    from uipath.dev.models.messages import LogMessage, TraceMessage


@dataclass
class EvaluatorResult:
    """Result from a single evaluator for a single evaluation."""

    evaluator_id: str
    evaluator_name: str
    score: float
    details: str = ""
    evaluation_time: float = 0.0
    justification: str = ""


@dataclass
class EvaluationResult:
    """Result for a single evaluation."""

    eval_id: str
    eval_name: str
    evaluator_results: list[EvaluatorResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Check if all evaluators passed (score == 1.0)."""
        return all(r.score == 1.0 for r in self.evaluator_results)


class EvalRun:
    """A single evaluation run."""

    def __init__(
        self,
        eval_set_path: str,
        entrypoint: str,
        *,
        id: str | None = None,
        name: str = "",
        no_report: bool = False,
        workers: int = 1,
        eval_set_run_id: str | None = None,
        enable_mocker_cache: bool = False,
        eval_ids: list[str] | None = None,
        report_coverage: bool = False,
        output_file: str | None = None,
        # For deserialization
        status: str = "pending",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        evaluator_refs: list[str] | None = None,
        error: UiPathErrorContract | None = None,
    ):
        """Initialize an EvalRun instance."""
        self.id = id if id is not None else str(uuid4())[:8]
        self.eval_set_path = eval_set_path
        self.entrypoint = entrypoint
        self.name = name if name else f"Run: {self.id}"
        self.status = status  # pending, running, completed, failed
        self.start_time = start_time if start_time is not None else datetime.now()
        self.end_time = end_time
        self.evaluator_refs: list[str] = evaluator_refs if evaluator_refs is not None else []
        self.evaluation_results: list[EvaluationResult] = []
        self.error = error
        self.logs: list["LogMessage"] = []
        self.traces: list["TraceMessage"] = []
        # Execution options
        self.no_report = no_report
        self.workers = workers
        self.eval_set_run_id = eval_set_run_id
        self.enable_mocker_cache = enable_mocker_cache
        self.eval_ids: list[str] = eval_ids if eval_ids is not None else []
        self.report_coverage = report_coverage
        self.output_file = output_file

    @property
    def duration(self) -> str:
        """Get the duration of the run as a formatted string."""
        if self.end_time:
            delta = self.end_time - self.start_time
            return f"{delta.total_seconds():.1f}s"
        elif self.start_time:
            delta = datetime.now() - self.start_time
            return f"{delta.total_seconds():.1f}s"
        return "0.0s"

    @property
    def display_name(self) -> Text:
        """Get formatted display name with status indicator."""
        status_colors = {
            "pending": "grey50",
            "running": "yellow",
            "completed": "green",
            "failed": "red",
        }

        status_icon = {
            "pending": "●",
            "running": "▶",
            "completed": "✔",
            "failed": "✖",
        }.get(self.status, "?")

        eval_set_name = (
            os.path.basename(self.eval_set_path).rsplit(".", 1)[0]
            if self.eval_set_path
            else "eval"
        )
        truncated_name = eval_set_name[:8]
        time_str = self.start_time.strftime("%H:%M:%S")
        duration_str = self.duration[:6]

        text = Text()
        text.append(f"{status_icon:<2} ", style=status_colors.get(self.status, "white"))
        text.append(f"{truncated_name:<8} ")
        text.append(f"({time_str:<8}) ")
        text.append(f"[{duration_str:<6}]")

        return text

    @property
    def total_evaluations(self) -> int:
        """Get total number of evaluations."""
        return len(self.evaluation_results)

    @property
    def evaluator_scores(self) -> dict[str, float]:
        """Get average score per evaluator across all evaluations."""
        scores: dict[str, list[float]] = {}
        for eval_result in self.evaluation_results:
            for ev_result in eval_result.evaluator_results:
                if ev_result.evaluator_id not in scores:
                    scores[ev_result.evaluator_id] = []
                scores[ev_result.evaluator_id].append(ev_result.score)

        return {
            ev_id: sum(s) / len(s) if s else 0.0
            for ev_id, s in scores.items()
        }

    @property
    def overall_score(self) -> float:
        """Get overall average score."""
        all_scores = []
        for eval_result in self.evaluation_results:
            for ev_result in eval_result.evaluator_results:
                all_scores.append(ev_result.score)
        return sum(all_scores) / len(all_scores) if all_scores else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "eval_set_path": self.eval_set_path,
            "entrypoint": self.entrypoint,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "evaluator_refs": self.evaluator_refs,
            "evaluation_results": [
                {
                    "eval_id": er.eval_id,
                    "eval_name": er.eval_name,
                    "evaluator_results": [
                        {
                            "evaluator_id": evr.evaluator_id,
                            "evaluator_name": evr.evaluator_name,
                            "score": evr.score,
                            "details": evr.details,
                            "evaluation_time": evr.evaluation_time,
                            "justification": evr.justification,
                        }
                        for evr in er.evaluator_results
                    ],
                }
                for er in self.evaluation_results
            ],
            "error": self.error.to_dict() if self.error else None,
            # Execution options
            "no_report": self.no_report,
            "workers": self.workers,
            "eval_set_run_id": self.eval_set_run_id,
            "enable_mocker_cache": self.enable_mocker_cache,
            "eval_ids": self.eval_ids,
            "report_coverage": self.report_coverage,
            "output_file": self.output_file,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalRun":
        """Create from dictionary."""
        error_data = data.get("error")
        error = UiPathErrorContract.from_dict(error_data) if error_data else None

        eval_run = cls(
            id=data["id"],
            name=data.get("name", ""),
            eval_set_path=data["eval_set_path"],
            entrypoint=data["entrypoint"],
            status=data.get("status", "pending"),
            start_time=datetime.fromisoformat(data["start_time"]) if data.get("start_time") else None,
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            evaluator_refs=data.get("evaluator_refs", []),
            error=error,
            # Execution options
            no_report=data.get("no_report", False),
            workers=data.get("workers", 1),
            eval_set_run_id=data.get("eval_set_run_id"),
            enable_mocker_cache=data.get("enable_mocker_cache", False),
            eval_ids=data.get("eval_ids", []),
            report_coverage=data.get("report_coverage", False),
            output_file=data.get("output_file"),
        )

        # Parse evaluation results
        for er_data in data.get("evaluation_results", []):
            eval_result = EvaluationResult(
                eval_id=er_data["eval_id"],
                eval_name=er_data.get("eval_name", er_data["eval_id"]),
            )
            for evr_data in er_data.get("evaluator_results", []):
                eval_result.evaluator_results.append(
                    EvaluatorResult(
                        evaluator_id=evr_data["evaluator_id"],
                        evaluator_name=evr_data.get("evaluator_name", evr_data["evaluator_id"]),
                        score=evr_data.get("score", 0.0),
                        details=evr_data.get("details", ""),
                        evaluation_time=evr_data.get("evaluation_time", 0.0),
                        justification=evr_data.get("justification", ""),
                    )
                )
            eval_run.evaluation_results.append(eval_result)

        return eval_run
