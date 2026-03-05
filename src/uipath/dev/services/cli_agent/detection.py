"""Detect installed CLI coding agents."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field


@dataclass
class CliAgentInfo:
    """Metadata for a CLI coding agent."""

    id: str
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    installed: bool = False


_KNOWN_AGENTS = [
    CliAgentInfo(id="claude", name="Claude Code", command="claude"),
    CliAgentInfo(id="codex", name="Codex CLI", command="codex"),
    CliAgentInfo(id="copilot", name="GitHub Copilot", command="gh", args=["copilot"]),
]


def detect_agents() -> list[CliAgentInfo]:
    """Return the list of CLI agents that are installed on this machine."""
    results: list[CliAgentInfo] = []
    for agent in _KNOWN_AGENTS:
        installed = shutil.which(agent.command) is not None
        results.append(
            CliAgentInfo(
                id=agent.id,
                name=agent.name,
                command=agent.command,
                args=list(agent.args),
                installed=installed,
            )
        )
    return results
