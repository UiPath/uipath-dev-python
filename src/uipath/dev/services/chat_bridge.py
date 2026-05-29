"""Chat bridge implementation for the web server."""

import asyncio
import logging
from typing import Any, Callable

from uipath.core.chat import (
    UiPathConversationMessageEvent,
    UiPathConversationToolCallConfirmationEvent,
)
from uipath.runtime.resumable.trigger import UiPathResumeTrigger

logger = logging.getLogger(__name__)


class WebChatBridge:
    """Bridge between the web server and UiPathChatRuntime.

    Implements UiPathChatProtocol. Forwards message events to WebSocket clients
    and resumes runtime execution when the user confirms a tool call.

    Tool confirmation flows through ``startToolCall`` events with
    ``requireConfirmation: true`` and ``inputSchema``; the user's decision is
    delivered back as a ``UiPathConversationToolCallConfirmationEvent`` via
    ``set_tool_confirmation`` and consumed by ``wait_for_resume``.
    """

    def __init__(self) -> None:
        """Initialize the web chat bridge."""
        self._tool_confirmation_event = asyncio.Event()
        self._tool_confirmation_value: (
            UiPathConversationToolCallConfirmationEvent | None
        ) = None

        self.on_message: Callable[[UiPathConversationMessageEvent], None] | None = None
        self.on_exchange_end: Callable[[], None] | None = None

    async def connect(self) -> None:
        """Establish connection to chat service."""
        logger.debug("WebChatBridge connected")

    async def disconnect(self) -> None:
        """Unblock any waiting coroutine and close."""
        self._tool_confirmation_event.set()
        logger.debug("WebChatBridge disconnected")

    async def emit_message_event(
        self, message_event: UiPathConversationMessageEvent
    ) -> None:
        """Forward a message event via callback."""
        if self.on_message:
            self.on_message(message_event)

    async def emit_interrupt_event(self, resume_trigger: UiPathResumeTrigger) -> None:
        """No-op.

        Tool confirmations now flow on the tool call event itself
        (``requireConfirmation`` + ``confirmToolCall``); generic agent
        interrupts have no near-term consumer in the dev console.
        """
        return None

    async def emit_executing_tool_call_event(
        self,
        tool_call_id: str,
        tool_input: dict[str, Any] | None = None,
    ) -> None:
        """Emit an executingToolCall event. Forwarded via message callback."""
        pass

    async def emit_exchange_end_event(self) -> None:
        """Send an exchange end event."""
        if self.on_exchange_end:
            self.on_exchange_end()

    async def emit_exchange_error_event(self, error: Exception) -> None:
        """Send an exchange error event."""
        logger.error(f"Exchange error: {error}")

    async def wait_for_resume(self) -> dict[str, Any]:
        """Wait for a confirmToolCall event to be received."""
        self._tool_confirmation_event.clear()
        self._tool_confirmation_value = None

        await self._tool_confirmation_event.wait()

        if self._tool_confirmation_value is not None:
            return self._tool_confirmation_value.model_dump(
                mode="python", by_alias=False
            )
        return {}

    def set_tool_confirmation(
        self, confirmation: UiPathConversationToolCallConfirmationEvent
    ) -> None:
        """Deliver the user's tool call confirmation and unblock the runtime."""
        self._tool_confirmation_value = confirmation
        self._tool_confirmation_event.set()
