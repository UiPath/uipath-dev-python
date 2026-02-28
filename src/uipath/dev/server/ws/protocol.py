"""WebSocket message protocol definitions."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ServerEvent(str, Enum):
    """Events sent from server to client."""

    RUN_UPDATED = "run.updated"
    LOG = "log"
    TRACE = "trace"
    CHAT = "chat"
    CHAT_INTERRUPT = "chat.interrupt"
    STATE = "state"
    RELOAD = "reload"
    FILES_CHANGED = "files.changed"
    EVAL_RUN_CREATED = "eval_run.created"
    EVAL_RUN_PROGRESS = "eval_run.progress"
    EVAL_RUN_COMPLETED = "eval_run.completed"
    AGENT_STATUS = "agent.status"
    AGENT_TEXT = "agent.text"
    AGENT_PLAN = "agent.plan"
    AGENT_TOOL_USE = "agent.tool_use"
    AGENT_TOOL_RESULT = "agent.tool_result"
    AGENT_TOOL_APPROVAL = "agent.tool_approval"
    AGENT_ERROR = "agent.error"
    AGENT_THINKING = "agent.thinking"
    AGENT_TEXT_DELTA = "agent.text_delta"
    AGENT_TOKEN_USAGE = "agent.token_usage"
    AGENT_QUESTION = "agent.question"


class ClientCommand(str, Enum):
    """Commands sent from client to server."""

    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    CHAT_MESSAGE = "chat.message"
    CHAT_INTERRUPT_RESPONSE = "chat.interrupt_response"
    DEBUG_STEP = "debug.step"
    DEBUG_CONTINUE = "debug.continue"
    DEBUG_STOP = "debug.stop"
    DEBUG_SET_BREAKPOINTS = "debug.set_breakpoints"
    AGENT_MESSAGE = "agent.message"
    AGENT_STOP = "agent.stop"
    AGENT_TOOL_RESPONSE = "agent.tool_response"
    AGENT_QUESTION_RESPONSE = "agent.question_response"


def server_message(event: ServerEvent, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a server-to-client message."""
    return {"type": event.value, "payload": payload}


def parse_client_message(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Parse a client-to-server message into (command, payload)."""
    return data.get("type", ""), data.get("payload", {})
