"""Plain data classes for inter-component communication (no Textual dependency)."""

from dataclasses import dataclass, field
from datetime import datetime
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
    timestamp: datetime = field(default_factory=datetime.now)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class StateData:
    """Plain data class for runtime state transitions."""

    run_id: str
    node_name: str
    payload: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ChatData:
    """Plain data class for chat messages."""

    run_id: str
    event: UiPathConversationMessageEvent | None = None
    message: UiPathConversationMessage | None = None
