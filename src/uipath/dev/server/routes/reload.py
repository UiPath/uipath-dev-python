"""Reload endpoint for hot-reloading the runtime factory."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["reload"])
logger = logging.getLogger(__name__)


@router.post("/reload")
async def reload_factory(request: Request) -> dict[str, str]:
    """Reload the runtime factory by re-importing user modules."""
    server = request.app.state.server

    if server.factory_creator is None:
        raise HTTPException(
            status_code=400,
            detail="Hot reload is not available (no factory_creator configured)",
        )

    # Block reload while any run is active
    active = [
        r
        for r in server.run_service.runs.values()
        if r.status in ("pending", "running")
    ]
    if active:
        raise HTTPException(
            status_code=409,
            detail="Cannot reload while runs are in progress",
        )

    await server.reload_factory()
    return {"status": "ok"}
