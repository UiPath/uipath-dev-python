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


class ClientCommand(str, Enum):
    """Commands sent from client to server."""

    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    CHAT_MESSAGE = "chat.message"
    DEBUG_STEP = "debug.step"
    DEBUG_CONTINUE = "debug.continue"
    DEBUG_STOP = "debug.stop"


def server_message(event: ServerEvent, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a server-to-client message."""
    return {"type": event.value, "payload": payload}


def parse_client_message(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Parse a client-to-server message into (command, payload)."""
    return data.get("type", ""), data.get("payload", {})
