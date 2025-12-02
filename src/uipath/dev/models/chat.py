"""Aggregates conversation messages from conversation events."""

from datetime import datetime
from uuid import uuid4

from uipath.core.chat import (
    UiPathConversationContentPart,
    UiPathConversationContentPartChunkEvent,
    UiPathConversationContentPartEndEvent,
    UiPathConversationContentPartEvent,
    UiPathConversationContentPartStartEvent,
    UiPathConversationEvent,
    UiPathConversationExchangeEvent,
    UiPathConversationMessage,
    UiPathConversationMessageEndEvent,
    UiPathConversationMessageEvent,
    UiPathConversationMessageStartEvent,
    UiPathConversationToolCall,
    UiPathConversationToolCallResult,
    UiPathInlineValue,
)


class ChatEvents:
    """Incrementally builds messages from UiPathConversationEvents."""

    messages: dict[str, UiPathConversationMessage]

    def __init__(self) -> None:
        """Initialize the chat events aggregator."""
        self.messages = {}

    def add(self, event: UiPathConversationEvent) -> UiPathConversationMessage | None:
        """Process an incoming conversation-level event and return the current message snapshot if applicable."""
        if not event.exchange or not event.exchange.message:
            return None

        ev = event.exchange.message
        msg = self.messages.get(ev.message_id)

        if not msg:
            msg = UiPathConversationMessage(
                message_id=ev.message_id,
                role=self.get_role(ev),
                content_parts=[],
                tool_calls=[],
                created_at=self.get_timestamp(ev),
                updated_at=self.get_timestamp(ev),
            )
            self.messages[ev.message_id] = msg

        # --- Handle content parts (text, JSON, etc.) ---
        if ev.content_part:
            cp_event = ev.content_part

            existing = next(
                (
                    cp
                    for cp in (msg.content_parts or [])
                    if cp.content_part_id == cp_event.content_part_id
                ),
                None,
            )

            # Start of a new content part
            if cp_event.start and not existing:
                new_cp = UiPathConversationContentPart(
                    content_part_id=cp_event.content_part_id,
                    mime_type=cp_event.start.mime_type,
                    data=UiPathInlineValue(inline=""),
                    citations=[],
                    is_transcript=None,
                    is_incomplete=True,
                )
                if msg.content_parts is None:
                    msg.content_parts = []
                msg.content_parts.append(new_cp)
                existing = new_cp

            # Chunk for an existing part (or backfill if start missing)
            if cp_event.chunk:
                if not existing:
                    new_cp = UiPathConversationContentPart(
                        content_part_id=cp_event.content_part_id,
                        mime_type="text/plain",  # fallback if start missing
                        data=UiPathInlineValue(inline=""),
                        citations=[],
                        is_transcript=None,
                        is_incomplete=True,
                    )
                    if msg.content_parts is None:
                        msg.content_parts = []
                    msg.content_parts.append(new_cp)
                    existing = new_cp

                if isinstance(existing.data, UiPathInlineValue):
                    existing.data.inline += cp_event.chunk.data or ""

            if cp_event.end and existing:
                existing.is_incomplete = bool(cp_event.end.interrupted)

        # --- Handle tool calls ---
        if ev.tool_call:
            tc_event = ev.tool_call
            existing_tool_call = next(
                (
                    tc
                    for tc in (msg.tool_calls or [])
                    if tc.tool_call_id == tc_event.tool_call_id
                ),
                None,
            )

            # Start of a tool call
            if tc_event.start:
                if not existing_tool_call:
                    new_tc = UiPathConversationToolCall(
                        tool_call_id=tc_event.tool_call_id,
                        name=tc_event.start.tool_name,
                        arguments=None,  # args will arrive as JSON content part
                        timestamp=tc_event.start.timestamp,
                        result=None,
                    )
                    if msg.tool_calls is None:
                        msg.tool_calls = []
                    msg.tool_calls.append(new_tc)
                    existing_tool_call = new_tc
                else:
                    existing_tool_call.name = (
                        tc_event.start.tool_name or existing_tool_call.name
                    )
                    existing_tool_call.timestamp = (
                        tc_event.start.timestamp or existing_tool_call.timestamp
                    )

            # End of a tool call
            if tc_event.end:
                if not existing_tool_call:
                    existing_tool_call = UiPathConversationToolCall(
                        tool_call_id=tc_event.tool_call_id,
                        name="",  # unknown until start seen
                        arguments=None,
                    )
                    if msg.tool_calls is None:
                        msg.tool_calls = []
                    msg.tool_calls.append(existing_tool_call)

                existing_tool_call.result = UiPathConversationToolCallResult(
                    timestamp=tc_event.end.timestamp,
                    value=tc_event.end.result,
                    is_error=tc_event.end.is_error,
                    cancelled=tc_event.end.cancelled,
                )

        msg.updated_at = self.get_timestamp(ev)

        return msg

    def get_timestamp(self, ev: UiPathConversationMessageEvent) -> str:
        """Choose timestamp from event if available, else fallback."""
        if ev.start and ev.start.timestamp:
            return ev.start.timestamp
        return datetime.now().isoformat()

    def get_role(self, ev: UiPathConversationMessageEvent) -> str:
        """Infer the role of the message from the event."""
        if ev.start and ev.start.role:
            return ev.start.role
        return "assistant"


def get_user_message(user_text: str) -> UiPathConversationMessage:
    """Build a user message from text input."""
    return UiPathConversationMessage(
        message_id=str(uuid4()),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        content_parts=[
            UiPathConversationContentPart(
                content_part_id=str(uuid4()),
                mime_type="text/plain",
                data=UiPathInlineValue(inline=user_text),
            )
        ],
        role="user",
    )


def get_user_message_event(
    user_text: str, conversation_id: str, role: str = "user"
) -> UiPathConversationEvent:
    """Build a conversation event representing a user message from text input."""
    message_id = str(uuid4())
    content_part_id = str(uuid4())
    timestamp = datetime.now().isoformat()

    msg_start = UiPathConversationMessageStartEvent(
        role=role,
        timestamp=timestamp,
    )

    cp_start = UiPathConversationContentPartStartEvent(mime_type="text/plain")
    cp_chunk = UiPathConversationContentPartChunkEvent(data=user_text)
    cp_end = UiPathConversationContentPartEndEvent()

    content_event = UiPathConversationContentPartEvent(
        content_part_id=content_part_id,
        start=cp_start,
        chunk=cp_chunk,
        end=cp_end,
    )

    msg_event = UiPathConversationMessageEvent(
        message_id=message_id,
        start=msg_start,
        content_part=content_event,
        end=UiPathConversationMessageEndEvent(),
    )

    exchange_event = UiPathConversationExchangeEvent(
        exchange_id=str(uuid4()),
        message=msg_event,
    )

    conversation_event = UiPathConversationEvent(
        exchange=exchange_event, conversation_id=conversation_id
    )

    return conversation_event


__all__ = [
    "ChatEvents",
    "get_user_message",
    "get_user_message_event",
]
