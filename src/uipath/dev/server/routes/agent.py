"""Agent endpoints — model discovery and skills."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from uipath.dev.services.skill_service import SkillService

router = APIRouter(tags=["agent"])
logger = logging.getLogger(__name__)


@router.get("/agent/models")
async def list_agent_models() -> list[dict[str, Any]]:
    """List available LLM models from the UiPath discovery endpoint."""
    base_url = os.environ.get("UIPATH_URL", "")
    access_token = os.environ.get("UIPATH_ACCESS_TOKEN", "")

    if not base_url or not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from uipath.platform.agenthub._agenthub_service import AgentHubService
        from uipath.platform.common._config import UiPathApiConfig
        from uipath.platform.common._execution_context import (
            UiPathExecutionContext,
        )
        from uipath.platform.orchestrator import FolderService

        config = UiPathApiConfig(base_url=base_url, secret=access_token)
        ctx = UiPathExecutionContext()
        folder_service = FolderService(config, ctx)
        svc = AgentHubService(config, ctx, folder_service)
        headers = {
            "X-UiPath-LlmGateway-RequestingProduct": "AgentsPlayground",
            "X-UiPath-LlmGateway-RequestingFeature": "uipath-dev",
            "X-UiPath-AgentHub-Config": "AgentsPlayground",
        }
        models = await svc.get_available_llm_models_async(headers=headers)
    except Exception as e:
        logger.warning("Discovery API error: %s", e)
        raise HTTPException(
            status_code=502, detail="Failed to fetch models from discovery API"
        ) from None

    # Filter to OpenAI-compatible models only (used via passthrough endpoint)
    return [
        {"model_name": m.model_name, "vendor": m.vendor}
        for m in models
        if m.vendor and "openai" in m.vendor.lower()
    ]


@router.get("/agent/skills")
async def list_agent_skills(request: Request) -> list[dict[str, str]]:
    """List available built-in skills."""
    skill_service: SkillService = request.app.state.server.skill_service
    return [
        {"id": s.id, "name": s.name, "description": s.description}
        for s in skill_service.list_skills()
    ]
