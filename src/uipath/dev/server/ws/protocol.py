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
    STATE = "state"
    RELOAD = "reload"
    FILES_CHANGED = "files.changed"
    EVAL_RUN_CREATED = "eval_run.created"
    EVAL_RUN_PROGRESS = "eval_run.progress"
    EVAL_RUN_COMPLETED = "eval_run.completed"
    CLI_AGENT_OUTPUT = "cli_agent.output"
    CLI_AGENT_EXIT = "cli_agent.exit"
    MCP_TOOL_CALL = "mcp.tool_call"


class ClientCommand(str, Enum):
    """Commands sent from client to server."""

    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    CHAT_MESSAGE = "chat.message"
    CHAT_CONFIRM_TOOL_CALL = "chat.confirm_tool_call"
    DEBUG_STEP = "debug.step"
    DEBUG_CONTINUE = "debug.continue"
    DEBUG_STOP = "debug.stop"
    DEBUG_SET_BREAKPOINTS = "debug.set_breakpoints"
    CLI_AGENT_START = "cli_agent.start"
    CLI_AGENT_INPUT = "cli_agent.input"
    CLI_AGENT_RESIZE = "cli_agent.resize"
    CLI_AGENT_STOP = "cli_agent.stop"


def server_message(event: ServerEvent, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a server-to-client message."""
    return {"type": event.value, "payload": payload}


def parse_client_message(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Parse a client-to-server message into (command, payload)."""
    return data.get("type", ""), data.get("payload", {})
