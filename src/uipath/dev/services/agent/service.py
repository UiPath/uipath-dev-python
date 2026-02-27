"""AgentService — thin facade over AgentLoop (session management + orchestration)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from uipath.dev.services.agent.events import AgentEvent, StatusChanged
from uipath.dev.services.agent.loop import SYSTEM_PROMPT, AgentLoop
from uipath.dev.services.agent.provider import create_provider
from uipath.dev.services.agent.session import AgentSession
from uipath.dev.services.agent.tools import (
    create_default_tools,
    create_dispatch_agent_tool,
    create_read_reference_tool,
)
from uipath.dev.services.skill_service import SkillService

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path.cwd().resolve()


class AgentService:
    """Manages agent sessions and runs the agent loop."""

    def __init__(  # noqa: D107
        self,
        *,
        skill_service: SkillService | None = None,
        on_event: Callable[[AgentEvent], None] | None = None,
    ) -> None:
        self._sessions: dict[str, AgentSession] = {}
        self._skill_service = skill_service
        self._on_event = on_event
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}

    def _emit(self, event: AgentEvent) -> None:
        if self._on_event:
            self._on_event(event)

    def _get_or_create_session(
        self, session_id: str | None, model: str
    ) -> AgentSession:
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if model:
                session.model = model
            return session
        session = AgentSession(model=model)
        self._sessions[session.id] = session
        return session

    async def send_message(
        self,
        session_id: str | None,
        text: str,
        model: str,
        skill_ids: list[str] | None = None,
    ) -> None:
        """Handle an incoming user message — append and start agent loop."""
        session = self._get_or_create_session(session_id, model)
        if skill_ids is not None:
            session.skill_ids = skill_ids

        # If already running, ignore
        if session.status in ("thinking", "executing", "awaiting_approval"):
            return

        session.messages.append({"role": "user", "content": text})
        session.status = "thinking"
        session._cancel_event.clear()

        self._emit(StatusChanged(session.id, status="thinking"))

        session._task = asyncio.create_task(self._run_agent_loop(session))

    def stop_session(self, session_id: str) -> None:
        """Cancel a running agent session."""
        session = self._sessions.get(session_id)
        if session:
            session._cancel_event.set()
            if session._task and not session._task.done():
                session._task.cancel()

    def resolve_tool_approval(self, tool_call_id: str, approved: bool) -> None:
        """Resolve a pending tool approval request."""
        logger.info(
            "resolve_tool_approval: tool_call_id=%s approved=%s pending_keys=%s",
            tool_call_id,
            approved,
            list(self._pending_approvals.keys()),
        )
        self._approval_results[tool_call_id] = approved
        event = self._pending_approvals.get(tool_call_id)
        if event:
            logger.info("resolve_tool_approval: signaling event for %s", tool_call_id)
            event.set()
        else:
            logger.info(
                "resolve_tool_approval: no pending event for tool_call_id=%s",
                tool_call_id,
            )

    async def _run_agent_loop(self, session: AgentSession) -> None:
        """Create provider, build tools, and run the loop."""
        provider = create_provider(session.model)

        # Build system prompt (inject skill content for active skills)
        system_prompt = SYSTEM_PROMPT
        if session.skill_ids and self._skill_service:
            for sid in session.skill_ids:
                try:
                    skill_body = self._skill_service.get_skill_content(sid)
                    system_prompt += f"\n\n## Active Skill: {sid}\n\n{skill_body}"
                except FileNotFoundError:
                    pass

        # Build tools list
        tools = create_default_tools(_PROJECT_ROOT)
        tools.append(create_dispatch_agent_tool())
        if session.skill_ids and self._skill_service:
            tools.append(create_read_reference_tool())

        loop = AgentLoop(
            provider=provider,
            tools=tools,
            emit=self._emit,
            pending_approvals=self._pending_approvals,
            approval_results=self._approval_results,
            skill_service=self._skill_service,
        )

        await loop.run(session, system_prompt=system_prompt)
