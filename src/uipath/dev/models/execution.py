"""Models for representing execution runs and their data."""

import os
from datetime import datetime
from enum import Enum
from typing import Any, cast
from uuid import uuid4

from rich.text import Text
from uipath.core.chat import UiPathConversationEvent, UiPathConversationMessage
from uipath.runtime.errors import UiPathErrorContract

from uipath.dev.models.chat import ChatEvents
from uipath.dev.models.messages import LogMessage, TraceMessage


class ExecutionMode(Enum):
    """Enumeration of execution modes."""

    RUN = "run"
    DEBUG = "debug"
    CHAT = "chat"


class ExecutionRun:
    """Represents a single execution run."""

    def __init__(
        self,
        entrypoint: str,
        input_data: dict[str, Any],
        mode: ExecutionMode,
    ):
        """Initialize an ExecutionRun instance."""
        self.id = str(uuid4())[:8]
        self.entrypoint = entrypoint
        self.input_data = input_data
        self.mode = mode
        self.resume_data: dict[str, Any] | None = None
        self.output_data: dict[str, Any] | str | None = None
        self.start_time = datetime.now()
        self.end_time: datetime | None = None
        self.status = "pending"  # pending, running, completed, failed, suspended
        self.traces: list[TraceMessage] = []
        self.logs: list[LogMessage] = []
        self.error: UiPathErrorContract | None = None
        self.chat_events = ChatEvents()

    @property
    def duration(self) -> str:
        """Get the duration of the run as a formatted string."""
        if self.end_time:
            delta = self.end_time - self.start_time
            return f"{delta.total_seconds():.1f}s"
        elif self.start_time:
            delta = datetime.now() - self.start_time
            return f"{delta.total_seconds():.1f}s"
        return "0.0s"

    @property
    def display_name(self) -> Text:
        """Get a rich Text representation of the run for display."""
        status_colors = {
            "pending": "grey50",
            "running": "yellow",
            "suspended": "cyan",
            "completed": "green",
            "failed": "red",
        }

        status_icon = {
            "pending": "●",
            "running": "▶",
            "suspended": "⏸",
            "completed": "✔",
            "failed": "✖",
        }.get(self.status, "?")

        script_name = (
            os.path.basename(self.entrypoint) if self.entrypoint else "untitled"
        )
        truncated_script = script_name[:8]
        time_str = self.start_time.strftime("%H:%M:%S")
        duration_str = self.duration[:6]

        text = Text()
        text.append(f"{status_icon:<2} ", style=status_colors.get(self.status, "white"))
        text.append(f"{truncated_script:<8} ")
        text.append(f"({time_str:<8}) ")
        text.append(f"[{duration_str:<6}]")

        return text

    @property
    def messages(self) -> list[UiPathConversationMessage]:
        """Get all conversation messages associated with this run."""
        return list(self.chat_events.messages.values())

    def add_event(self, event: Any) -> UiPathConversationMessage | None:
        """Add a conversation event to the run's chat aggregator."""
        return self.chat_events.add(cast(UiPathConversationEvent, event))
