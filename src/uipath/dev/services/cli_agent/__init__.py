"""CLI coding agent proxy — delegates to external CLI tools."""

from uipath.dev.services.cli_agent.detection import CliAgentInfo, detect_agents
from uipath.dev.services.cli_agent.service import CliAgentService

__all__ = ["CliAgentInfo", "CliAgentService", "detect_agents"]
