"""Messages used for inter-component communication in the UiPath Developer Console."""

from datetime import datetime, timezone
from typing import Any

from rich.console import RenderableType
from textual.message import Message
from uipath.core.chat import UiPathConversationMessage, UiPathConversationMessageEvent

from uipath.dev.models.data import ChatData, LogData, TraceData


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
        self.timestamp = timestamp or datetime.now(timezone.utc)
        super().__init__()

    @classmethod
    def from_data(cls, data: LogData) -> "LogMessage":
        """Create a LogMessage from a LogData instance."""
        return cls(
            run_id=data.run_id,
            level=data.level,
            message=data.message,
            timestamp=data.timestamp,
        )


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
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.attributes = attributes or {}
        super().__init__()

    @classmethod
    def from_data(cls, data: TraceData) -> "TraceMessage":
        """Create a TraceMessage from a TraceData instance."""
        return cls(
            run_id=data.run_id,
            span_name=data.span_name,
            span_id=data.span_id,
            parent_span_id=data.parent_span_id,
            trace_id=data.trace_id,
            status=data.status,
            duration_ms=data.duration_ms,
            timestamp=data.timestamp,
            attributes=data.attributes,
        )


class ChatMessage(Message):
    """Message sent when a new chat message is created or updated."""

    def __init__(
        self,
        event: UiPathConversationMessageEvent | None,
        message: UiPathConversationMessage | None,
        run_id: str,
    ):
        """Initialize a ChatMessage instance."""
        self.run_id = run_id
        self.event = event
        self.message = message
        super().__init__()

    @classmethod
    def from_data(cls, data: ChatData) -> "ChatMessage":
        """Create a ChatMessage from a ChatData instance."""
        return cls(
            event=data.event,
            message=data.message,
            run_id=data.run_id,
        )
