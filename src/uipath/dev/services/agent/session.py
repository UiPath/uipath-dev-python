"""Agent session with token tracking."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentSession:
    """In-memory state for one agent conversation."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model: str = ""
    skill_ids: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    plan: list[dict[str, str]] = field(default_factory=list)
    tasks: dict[str, dict[str, str]] = field(default_factory=dict)
    _next_task_id: int = field(default=1, repr=False)
    status: str = "idle"
    # Trace spans (one per LLM call)
    traces: list[dict[str, Any]] = field(default_factory=list)
    last_system_prompt: str = ""
    last_tool_schemas: list[dict[str, Any]] = field(default_factory=list)
    # Token tracking
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    turn_count: int = 0
    compaction_count: int = 0
    # Control
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    _task: asyncio.Task[None] | None = field(default=None, repr=False)
