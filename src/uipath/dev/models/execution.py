"""Models for representing execution runs and their data."""

import os
from datetime import datetime
from typing import Any, Optional, Union
from uuid import uuid4

from rich.text import Text
from uipath.runtime.errors import UiPathErrorContract

from uipath.dev.models.messages import LogMessage, TraceMessage


class ExecutionRun:
    """Represents a single execution run."""

    def __init__(
        self,
        entrypoint: str,
        input_data: Union[dict[str, Any]],
        conversational: bool = False,
        debug: bool = False,
    ):
        """Initialize an ExecutionRun instance."""
        self.id = str(uuid4())[:8]
        self.entrypoint = entrypoint
        self.input_data = input_data
        self.conversational = conversational
        self.debug = debug
        self.resume_data: Optional[dict[str, Any]] = None
        self.output_data: Optional[dict[str, Any]] = None
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.status = "pending"  # pending, running, completed, failed, suspended
        self.traces: list[TraceMessage] = []
        self.logs: list[LogMessage] = []
        self.error: Optional[UiPathErrorContract] = None

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
