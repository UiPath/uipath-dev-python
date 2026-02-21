"""Plain data classes for inter-component communication (no Textual dependency)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from uipath.core.chat import UiPathConversationMessage, UiPathConversationMessageEvent


@dataclass
class LogData:
    """Plain data class for log entries."""

    run_id: str
    level: str
    message: str
    timestamp: datetime


@dataclass
class TraceData:
    """Plain data class for trace spans."""

    run_id: str
    span_name: str
    span_id: str
    parent_span_id: str | None = None
    trace_id: str | None = None
    status: str = "running"
    duration_ms: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class StateData:
    """Plain data class for runtime state transitions."""

    run_id: str
    node_name: str
    qualified_node_name: str | None = None
    phase: str | None = None
    payload: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChatData:
    """Plain data class for chat messages."""

    run_id: str
    event: UiPathConversationMessageEvent | None = None
    message: UiPathConversationMessage | None = None


@dataclass
class InterruptData:
    """Plain data class for HITL interrupt events."""

    run_id: str
    interrupt_id: str
    interrupt_type: str  # "tool_call_confirmation" | "generic"
    tool_call_id: str | None = None
    tool_name: str | None = None
    input_schema: Any | None = None
    input_value: Any | None = None
    content: Any | None = None
