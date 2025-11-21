"""Messages used for inter-component communication in the UiPath Developer Console."""

from datetime import datetime
from typing import Any

from rich.console import RenderableType
from textual.message import Message


class LogMessage(Message):
    """Message sent when a new log entry is created."""

    def __init__(
        self,
        run_id: str,
        level: str,
        message: str | RenderableType,
        timestamp: datetime | None = None,
    ):
        """Initialize a LogMessage instance."""
        self.run_id = run_id
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.now()
        super().__init__()


class TraceMessage(Message):
    """Message sent when a new trace entry is created."""

    def __init__(
        self,
        run_id: str,
        span_name: str,
        span_id: str,
        parent_span_id: str | None = None,
        trace_id: str | None = None,
        status: str = "running",
        duration_ms: float | None = None,
        timestamp: datetime | None = None,
        attributes: dict[str, Any] | None = None,
    ):
        """Initialize a TraceMessage instance."""
        self.run_id = run_id
        self.span_name = span_name
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.trace_id = trace_id
        self.status = status
        self.duration_ms = duration_ms
        self.timestamp = timestamp or datetime.now()
        self.attributes = attributes or {}
        super().__init__()
