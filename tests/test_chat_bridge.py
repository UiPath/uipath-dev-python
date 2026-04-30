"""Tests for WebChatBridge tool-call confirmation flow."""

from __future__ import annotations

import asyncio

from uipath.core.chat import (
    UiPathConversationMessageEvent,
    UiPathConversationToolCallConfirmationEvent,
)

from uipath.dev.services.chat_bridge import WebChatBridge


async def test_wait_for_resume_returns_confirmation_dict() -> None:
    """wait_for_resume should return the confirmation as a plain dict."""
    bridge = WebChatBridge()

    waiter = asyncio.create_task(bridge.wait_for_resume())
    await asyncio.sleep(0)  # let the waiter start

    bridge.set_tool_confirmation(
        UiPathConversationToolCallConfirmationEvent(approved=True, input={"x": 1})
    )

    result = await asyncio.wait_for(waiter, timeout=1.0)
    assert result == {"approved": True, "input": {"x": 1}}


async def test_wait_for_resume_returns_empty_when_disconnected() -> None:
    """If the bridge is disconnected without a confirmation, return {}."""
    bridge = WebChatBridge()

    waiter = asyncio.create_task(bridge.wait_for_resume())
    await asyncio.sleep(0)

    await bridge.disconnect()

    result = await asyncio.wait_for(waiter, timeout=1.0)
    assert result == {}


async def test_emit_interrupt_event_is_noop() -> None:
    """emit_interrupt_event should not block or invoke any callback."""
    bridge = WebChatBridge()

    # No on_interrupt callback exists in the new API; calling should just return.
    await bridge.emit_interrupt_event(None)  # type: ignore[arg-type]


async def test_emit_message_event_forwards_to_callback() -> None:
    """Message events flow through the on_message callback unchanged."""
    bridge = WebChatBridge()

    received: list[UiPathConversationMessageEvent] = []
    bridge.on_message = received.append

    event = UiPathConversationMessageEvent(message_id="m1")  # type: ignore[call-arg]
    await bridge.emit_message_event(event)

    assert received == [event]


async def test_set_tool_confirmation_unblocks_subsequent_waiter() -> None:
    """A second wait_for_resume call after set_tool_confirmation re-arms cleanly."""
    bridge = WebChatBridge()

    # First round
    waiter = asyncio.create_task(bridge.wait_for_resume())
    await asyncio.sleep(0)
    bridge.set_tool_confirmation(
        UiPathConversationToolCallConfirmationEvent(approved=True)
    )
    first = await asyncio.wait_for(waiter, timeout=1.0)
    assert first == {"approved": True, "input": None}

    # Second round
    waiter2 = asyncio.create_task(bridge.wait_for_resume())
    await asyncio.sleep(0)
    bridge.set_tool_confirmation(
        UiPathConversationToolCallConfirmationEvent(approved=False)
    )
    second = await asyncio.wait_for(waiter2, timeout=1.0)
    assert second == {"approved": False, "input": None}
