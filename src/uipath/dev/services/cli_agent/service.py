"""CLI coding agent service — manages PTY sessions for external CLI tools."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from uipath.dev.services.cli_agent.detection import CliAgentInfo, detect_agents
from uipath.dev.services.cli_agent.mcp_config import ensure_mcp_config
from uipath.dev.services.cli_agent.pty_session import PtySession

logger = logging.getLogger(__name__)


class CliAgentService:
    """Facade for managing CLI coding agent PTY sessions."""

    def __init__(
        self,
        on_output: Callable[[str, bytes], None],
        on_exit: Callable[[str, int], None],
        server_port: int = 8080,
        server_host: str = "localhost",
    ) -> None:
        """Initialize the CLI agent service."""
        self._sessions: dict[str, PtySession] = {}
        self._on_output = on_output
        self._on_exit = on_exit
        self._available_agents: list[CliAgentInfo] | None = None
        self._server_port = server_port
        self._server_host = server_host

    def get_available_agents(self) -> list[CliAgentInfo]:
        """Return detected CLI agents (cached after first call)."""
        if self._available_agents is None:
            self._available_agents = detect_agents()
        return self._available_agents

    async def start_session(
        self,
        agent_id: str,
        session_id: str,
        cwd: str | None = None,
        cols: int = 120,
        rows: int = 40,
    ) -> None:
        """Start a new PTY session for the given CLI agent."""
        agent = next(
            (
                a
                for a in self.get_available_agents()
                if a.id == agent_id and a.installed
            ),
            None,
        )
        if agent is None:
            raise ValueError(f"Agent '{agent_id}' is not available or not installed")

        # Stop existing session if any
        if session_id in self._sessions:
            await self.stop_session(session_id)

        # Ensure MCP config is present so the agent discovers our server
        work_dir = cwd or os.getcwd()
        ensure_mcp_config(
            agent_id=agent.id,
            cwd=work_dir,
            port=self._server_port,
            host=self._server_host,
        )

        cmd = [agent.command, *agent.args]
        session = PtySession(
            session_id=session_id,
            command=cmd,
            on_output=self._on_output,
            on_exit=self._handle_exit,
            cwd=cwd,
            cols=cols,
            rows=rows,
        )
        self._sessions[session_id] = session
        await session.start()
        logger.info("Started CLI agent session %s (%s)", session_id, agent.name)

    async def write_input(self, session_id: str, data: str) -> None:
        """Write user input to the PTY."""
        session = self._sessions.get(session_id)
        if session is not None:
            await session.write(data)

    async def resize(self, session_id: str, cols: int, rows: int) -> None:
        """Resize the PTY terminal."""
        session = self._sessions.get(session_id)
        if session is not None:
            await session.resize(cols, rows)

    async def stop_session(self, session_id: str) -> None:
        """Stop and remove a PTY session."""
        session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.stop()
            logger.info("Stopped CLI agent session %s", session_id)

    async def stop_all_sessions(self) -> None:
        """Stop all active PTY sessions (used during server shutdown)."""
        for session_id in list(self._sessions):
            await self.stop_session(session_id)

    def _handle_exit(self, session_id: str, exit_code: int) -> None:
        """Handle subprocess exit — clean up and forward."""
        self._sessions.pop(session_id, None)
        self._on_exit(session_id, exit_code)
