"""Typed event system for the agent harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentEvent:
    """Base class for all agent events."""

    session_id: str


@dataclass
class StatusChanged(AgentEvent):
    """Agent status changed."""

    status: str = ""


@dataclass
class TextGenerated(AgentEvent):
    """Final text response (or chunk with done=True)."""

    content: str = ""
    done: bool = False


@dataclass
class TextDelta(AgentEvent):
    """Streaming text token."""

    delta: str = ""


@dataclass
class ThinkingGenerated(AgentEvent):
    """Model thinking/reasoning content."""

    content: str = ""


@dataclass
class PlanUpdated(AgentEvent):
    """Plan items updated."""

    items: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ToolStarted(AgentEvent):
    """Tool execution started."""

    tool_call_id: str = ""
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCompleted(AgentEvent):
    """Tool execution completed."""

    tool_call_id: str = ""
    tool: str = ""
    result: str = ""
    is_error: bool = False


@dataclass
class ToolApprovalRequired(AgentEvent):
    """Tool requires user approval before execution."""

    tool_call_id: str = ""
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorOccurred(AgentEvent):
    """An error occurred in the agent loop."""

    message: str = ""


@dataclass
class TokenUsageUpdated(AgentEvent):
    """Token usage stats for the current turn."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_session_tokens: int = 0


@dataclass
class UserQuestionAsked(AgentEvent):
    """Agent is asking the user a question and waiting for an answer."""

    question_id: str = ""
    question: str = ""
    options: list[str] = field(default_factory=list)
