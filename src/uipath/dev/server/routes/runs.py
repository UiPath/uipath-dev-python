"""Run management endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from uipath.dev.models.execution import ExecutionMode, ExecutionRun
from uipath.dev.server.routes.graph import snapshot_graph
from uipath.dev.server.serializers import serialize_run, serialize_run_detail

router = APIRouter(tags=["runs"])
logger = logging.getLogger(__name__)


class CreateRunRequest(BaseModel):
    """Request body for creating a new run."""

    entrypoint: str
    input_data: dict[str, Any] = {}
    mode: str = "run"
    breakpoints: list[str] = []


@router.post("/runs")
async def create_run(request: Request, body: CreateRunRequest) -> dict[str, Any]:
    """Create and execute a new run."""
    server = request.app.state.server

    mode_map = {
        "run": ExecutionMode.RUN,
        "debug": ExecutionMode.DEBUG,
        "chat": ExecutionMode.CHAT,
    }
    mode = mode_map.get(body.mode, ExecutionMode.RUN)

    run = ExecutionRun(
        entrypoint=body.entrypoint,
        input_data=body.input_data,
        mode=mode,
    )

    run.breakpoints = body.breakpoints

    # Snapshot graph at creation time so it persists across reloads
    run.graph_data = await snapshot_graph(server.runtime_factory, body.entrypoint)

    server.run_service.register_run(run)

    # Chat mode waits for user's first message before executing
    if mode != ExecutionMode.CHAT:
        asyncio.create_task(server.run_service.execute(run))

    return serialize_run(run)


@router.get("/runs")
async def list_runs(request: Request) -> list[dict[str, Any]]:
    """List all runs."""
    server = request.app.state.server
    return [serialize_run(run) for run in server.run_service.runs.values()]


@router.get("/runs/{run_id}")
async def get_run(request: Request, run_id: str) -> dict[str, Any]:
    """Get detailed run information including traces, logs, and messages."""
    server = request.app.state.server
    run = server.run_service.get_run(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return serialize_run_detail(run)
