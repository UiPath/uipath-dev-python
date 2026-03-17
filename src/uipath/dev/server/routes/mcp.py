"""MCP event reporting endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["mcp"])


class McpToolCallEvent(BaseModel):
    """Event payload for an MCP tool invocation."""

    tool: str
    args: dict[str, Any] = {}


@router.post("/mcp/events")
async def report_mcp_event(event: McpToolCallEvent, request: Request) -> dict[str, str]:
    """Report an MCP tool call event, broadcast to all WebSocket clients."""
    server = request.app.state.server
    server.connection_manager.broadcast_mcp_tool_call(event.tool, event.args)
    return {"status": "ok"}
