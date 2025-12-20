"""Chat panel for displaying and interacting with chat messages."""

import time
from collections import deque

from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Input, Markdown
from uipath.core.chat import (
    UiPathExternalValue,
    UiPathInlineValue,
)

from uipath.dev.models import ChatMessage, ExecutionRun

# Tunables for streaming performance
STREAM_MIN_INTERVAL = 0.08  # seconds between updates while streaming
STREAM_MIN_DELTA_CHARS = 8  # min new chars before we bother updating

# Limit how many message widgets we keep mounted to avoid DOM explosion.
MAX_WIDGETS = 20


class Prompt(Markdown):
    """User prompt message bubble."""

    pass


class Response(Markdown):
    """AI response message bubble."""

    BORDER_TITLE = "🤖 ai"


class Tool(Markdown):
    """Tool message bubble."""

    BORDER_TITLE = "🛠️  tool"


class ChatPanel(Container):
    """Panel for displaying and interacting with chat messages."""

    _chat_widgets: dict[str, Markdown]
    _last_update_time: dict[str, float]
    _last_content: dict[str, str]
    _chat_view: VerticalScroll | None
    _chat_order: deque[str]

    def __init__(self, **kwargs):
        """Initialize the chat panel."""
        super().__init__(**kwargs)
        self._chat_widgets = {}
        self._last_update_time = {}
        self._last_content = {}
        self._chat_view = None
        self._chat_order = deque()

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        with Vertical(id="chat-container"):
            yield VerticalScroll(id="chat-view")
            yield Input(
                placeholder="Type your message and press Enter...",
                id="chat-input",
            )

    def on_mount(self) -> None:
        """Called when the panel is mounted."""
        self._chat_view = self.query_one("#chat-view", VerticalScroll)

    def refresh_messages(self, run: ExecutionRun) -> None:
        """Update the chat panel with messages from the given execution run."""
        assert self._chat_view is not None

        self._chat_view.remove_children()
        self._chat_widgets.clear()
        self._last_update_time.clear()
        self._last_content.clear()
        self._chat_order.clear()

        for chat_msg in run.messages:
            self.add_chat_message(
                ChatMessage(message=chat_msg, event=None, run_id=run.id),
                auto_scroll=False,
            )

        # For a fresh run, always show the latest messages
        self._chat_view.scroll_end(animate=False)

    def add_chat_message(
        self,
        chat_msg: ChatMessage,
        auto_scroll: bool = True,
    ) -> None:
        """Add or update a chat message bubble."""
        assert self._chat_view is not None
        chat_view = self._chat_view

        should_autoscroll = auto_scroll and not chat_view.is_vertical_scrollbar_grabbed

        message = chat_msg.message
        if message is None:
            return

        message_id = message.message_id

        widget_cls: type[Prompt] | type[Response] | type[Tool]
        if message.role == "user":
            widget_cls = Prompt
        elif message.role == "assistant":
            widget_cls = Response
        else:
            widget_cls = Response

        parts: list[str] = []
        if message.content_parts:
            for part in message.content_parts:
                if (
                    part.mime_type.startswith("text/")
                    or part.mime_type == "application/json"
                ):
                    if isinstance(part.data, UiPathInlineValue):
                        parts.append(part.data.inline or "")
                    elif isinstance(part.data, UiPathExternalValue):
                        parts.append(f"[external: {part.data.uri}]")

        text_block = "\n".join(parts).strip()
        content_lines = [f"{text_block}"] if text_block else []

        if message.tool_calls:
            widget_cls = Tool
            for call in message.tool_calls:
                status_icon = "✓" if call.result else "⚙"
                content_lines.append(f" {status_icon} **{call.name}**")

        if not content_lines:
            return

        content = "\n\n".join(content_lines)

        prev_content = self._last_content.get(message_id)
        if prev_content is not None and content == prev_content:
            # We already rendered this exact content, no need to touch the UI.
            return

        existing = self._chat_widgets.get(message_id)
        now = time.monotonic()
        last_update = self._last_update_time.get(message_id, 0.0)

        if existing:
            prev_content_len = len(prev_content) if prev_content is not None else 0
            delta_len = len(content) - prev_content_len

            def should_update() -> bool:
                event = chat_msg.event
                finished = event and event.end is not None

                if finished:
                    # Always paint the final state immediately.
                    return True

                # Throttle streaming: require both some time and a minimum delta size.
                if now - last_update < STREAM_MIN_INTERVAL:
                    return False

                # First streaming chunk for this message: allow update.
                if prev_content is None:
                    return True

                if delta_len < STREAM_MIN_DELTA_CHARS:
                    return False

                return True

            if not should_update():
                return

            # Fast path: message is growing by appending new text.
            if (
                isinstance(existing, Markdown)
                and prev_content is not None
                and content.startswith(prev_content)
            ):
                delta = content[len(prev_content) :]
                if delta:
                    # Streaming update: only append the new portion.
                    existing.append(delta)
            else:
                # Fallback for non-monotonic changes: full update.
                existing.update(content)

            self._last_content[message_id] = content
            self._last_update_time[message_id] = now

        else:
            # First time we see this message: create a new widget.
            widget_instance = widget_cls(content)
            chat_view.mount(widget_instance)
            self._chat_widgets[message_id] = widget_instance
            self._last_update_time[message_id] = now
            self._last_content[message_id] = content
            self._chat_order.append(message_id)

            # Prune oldest widgets to keep DOM size bounded
            if len(self._chat_order) > MAX_WIDGETS:
                oldest_id = self._chat_order.popleft()
                old_widget = self._chat_widgets.pop(oldest_id, None)
                self._last_update_time.pop(oldest_id, None)
                self._last_content.pop(oldest_id, None)
                if old_widget is not None:
                    old_widget.remove()

        if should_autoscroll:
            chat_view.scroll_end(animate=False)
