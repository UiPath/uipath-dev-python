"""REST endpoints for CLI coding agent management."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["cli-agent"])


@router.get("/cli-agent/available")
async def list_available_agents(request: Request) -> list[dict[str, object]]:
    """Return the list of detected CLI coding agents."""
    service = request.app.state.server.cli_agent_service
    agents = service.get_available_agents()
    return [{"id": a.id, "name": a.name, "installed": a.installed} for a in agents]
