"""Write project-level MCP config so CLI agents auto-discover uipath-dev-mcp."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "uipath-dev"


def ensure_mcp_config(agent_id: str, cwd: str, port: int, host: str) -> None:
    """Ensure the MCP config for the given agent includes our server entry.

    Merges into existing config files without clobbering user entries.
    If our entry already exists, updates it with the current port/host.
    """
    try:
        if agent_id == "claude":
            _ensure_claude_mcp(cwd, port, host)
        elif agent_id == "codex":
            _ensure_codex_mcp(cwd, port, host)
        elif agent_id == "copilot":
            _ensure_copilot_mcp(port, host)
    except Exception:
        logger.warning("Failed to write MCP config for %s", agent_id, exc_info=True)


def _mcp_entry(port: int, host: str) -> dict[str, Any]:
    """Build the MCP server entry for our server."""
    env = {"UIPATH_DEV_SERVER_PORT": str(port)}
    if host != "localhost":
        env["UIPATH_DEV_SERVER_HOST"] = host
    return {
        "command": "uipath-dev-mcp",
        "env": env,
    }


# --- Claude Code: .mcp.json in project root ---


def _ensure_claude_mcp(cwd: str, port: int, host: str) -> None:
    path = Path(cwd) / ".mcp.json"
    config: dict[str, Any] = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config = {}

    servers = config.setdefault("mcpServers", {})
    servers[MCP_SERVER_NAME] = _mcp_entry(port, host)

    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    logger.debug("Wrote Claude MCP config: %s", path)


# --- Codex: .codex/config.toml in project root ---


def _ensure_codex_mcp(cwd: str, port: int, host: str) -> None:
    codex_dir = Path(cwd) / ".codex"
    codex_dir.mkdir(exist_ok=True)
    path = codex_dir / "config.toml"

    # Read existing TOML content (simple parser — just preserve lines)
    lines: list[str] = []
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []

    section_header = f'[mcp_servers."{MCP_SERVER_NAME}"]'
    env_key = "UIPATH_DEV_SERVER_PORT"

    # Check if our section already exists
    section_idx = None
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_idx = i
            break

    entry_lines = [
        section_header,
        'command = "uipath-dev-mcp"',
    ]
    env_dict = {env_key: str(port)}
    if host != "localhost":
        env_dict["UIPATH_DEV_SERVER_HOST"] = host
    env_parts = ", ".join(f'{k} = "{v}"' for k, v in env_dict.items())
    entry_lines.append(f"env = {{ {env_parts} }}")

    if section_idx is not None:
        # Replace existing section (find end = next section or EOF)
        end_idx = section_idx + 1
        while end_idx < len(lines) and not lines[end_idx].strip().startswith("["):
            end_idx += 1
        lines[section_idx:end_idx] = entry_lines
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(entry_lines)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.debug("Wrote Codex MCP config: %s", path)


# --- Copilot CLI: ~/.copilot/mcp-config.json ---


def _ensure_copilot_mcp(port: int, host: str) -> None:
    copilot_dir = Path(os.path.expanduser("~")) / ".copilot"
    copilot_dir.mkdir(exist_ok=True)
    path = copilot_dir / "mcp-config.json"

    config: dict[str, Any] = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config = {}

    servers = config.setdefault("mcpServers", {})
    servers[MCP_SERVER_NAME] = _mcp_entry(port, host)

    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    logger.debug("Wrote Copilot MCP config: %s", path)
