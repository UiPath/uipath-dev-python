"""Data models for evaluation runs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class EvalSetInfo:
    """Summary of a discovered evaluation set."""

    id: str
    name: str
    eval_count: int
    evaluator_ids: list[str]


@dataclass
class EvalItemResult:
    """Result of evaluating a single item."""

    name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    expected_output: Any = None
    scores: dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0
    output: Any = None
    justifications: dict[str, str] = field(default_factory=dict)
    duration_ms: float | None = None
    status: str = "pending"  # pending | running | completed | failed
    error: str | None = None
    traces: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvalRunState:
    """Full state of an eval run."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    eval_set_id: str = ""
    eval_set_name: str = ""
    status: str = "pending"  # pending | running | completed | failed
    progress_completed: int = 0
    progress_total: int = 0
    overall_score: float | None = None
    evaluator_scores: dict[str, float] = field(default_factory=dict)
    results: list[EvalItemResult] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None

    def to_summary(self) -> dict[str, Any]:
        """Serialize to summary dict (no per-item results)."""
        return {
            "id": self.id,
            "eval_set_id": self.eval_set_id,
            "eval_set_name": self.eval_set_name,
            "status": self.status,
            "progress_completed": self.progress_completed,
            "progress_total": self.progress_total,
            "overall_score": self.overall_score,
            "evaluator_scores": self.evaluator_scores,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    def to_detail(self) -> dict[str, Any]:
        """Serialize to detail dict (includes per-item results)."""
        base = self.to_summary()
        base["results"] = [
            {
                "name": r.name,
                "inputs": r.inputs,
                "expected_output": r.expected_output,
                "scores": r.scores,
                "overall_score": r.overall_score,
                "output": str(r.output)
                if isinstance(r.output, Exception)
                else r.output,
                "justifications": r.justifications,
                "duration_ms": r.duration_ms,
                "status": r.status,
                "error": r.error,
                "traces": r.traces,
            }
            for r in self.results
        ]
        return base

    def start(self) -> None:
        """Mark run as started."""
        self.status = "running"
        self.start_time = datetime.now(timezone.utc)

    def complete(self) -> None:
        """Mark run as completed, computing final scores."""
        self.status = "completed"
        self.end_time = datetime.now(timezone.utc)
        self._compute_scores()

    def fail(self) -> None:
        """Mark run as failed."""
        self.status = "failed"
        self.end_time = datetime.now(timezone.utc)

    def _compute_scores(self) -> None:
        """Compute overall and per-evaluator scores from item results."""
        scored = [r for r in self.results if r.status in ("completed", "failed")]
        if not scored:
            self.overall_score = 0.0
            return

        # Per-evaluator averages (failed items count as 0 for each evaluator)
        evaluator_totals: dict[str, list[float]] = {}
        for r in scored:
            for ev_id, score in r.scores.items():
                evaluator_totals.setdefault(ev_id, []).append(score)

        failed = [r for r in scored if r.status == "failed"]
        for ev_id in evaluator_totals:
            for _ in failed:
                evaluator_totals[ev_id].append(0.0)

        self.evaluator_scores = {
            ev_id: sum(scores) / len(scores)
            for ev_id, scores in evaluator_totals.items()
        }

        # Overall = average of item overall_scores
        self.overall_score = sum(r.overall_score for r in scored) / len(scored)
