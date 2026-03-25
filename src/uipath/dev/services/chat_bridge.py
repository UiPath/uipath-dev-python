"""Chat bridge implementation for the web server."""

import asyncio
import logging
from typing import Any, Callable

from uipath.core.chat import UiPathConversationMessageEvent
from uipath.runtime.resumable.trigger import UiPathResumeTrigger

logger = logging.getLogger(__name__)


class WebChatBridge:
    """Bridge between the web server and UiPathChatRuntime.

    Implements UiPathChatProtocol. Broadcasts message and interrupt events
    to WebSocket clients via callbacks, and blocks on wait_for_resume until
    the user responds.
    """

    def __init__(self) -> None:
        """Initialize the web chat bridge."""
        self._resume_event = asyncio.Event()
        self._resume_data: dict[str, Any] = {}

        # Callbacks (wired by RunService / server)
        self.on_message: Callable[[UiPathConversationMessageEvent], None] | None = None
        self.on_interrupt: Callable[[UiPathResumeTrigger], None] | None = None
        self.on_exchange_end: Callable[[], None] | None = None

    async def connect(self) -> None:
        """Establish connection to chat service."""
        logger.debug("WebChatBridge connected")

    async def disconnect(self) -> None:
        """Close connection and send exchange end event."""
        self._resume_event.set()
        logger.debug("WebChatBridge disconnected")

    async def emit_message_event(
        self, message_event: UiPathConversationMessageEvent
    ) -> None:
        """Forward a message event via callback."""
        if self.on_message:
            self.on_message(message_event)

    async def emit_interrupt_event(self, resume_trigger: UiPathResumeTrigger) -> None:
        """Forward an interrupt event via callback."""
        if self.on_interrupt:
            self.on_interrupt(resume_trigger)

    async def emit_exchange_end_event(self) -> None:
        """Send an exchange end event."""
        if self.on_exchange_end:
            self.on_exchange_end()

    async def emit_exchange_error_event(self, error: Exception) -> None:
        """Send an exchange error event."""
        logger.error(f"Exchange error: {error}")

    async def wait_for_resume(self) -> dict[str, Any]:
        """Wait for the user to respond to an interrupt."""
        self._resume_event.clear()
        await self._resume_event.wait()
        return self._resume_data

    def resume(self, data: dict[str, Any]) -> None:
        """Store resume data and signal the waiting coroutine."""
        self._resume_data = data
        self._resume_event.set()
