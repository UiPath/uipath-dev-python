"""Authentication endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from uipath.dev.server.auth import build_auth_url, get_status, logout, select_tenant

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    """Request body for starting the OAuth login flow."""

    environment: Literal["cloud", "staging", "alpha"] = "cloud"


class SelectTenantRequest(BaseModel):
    """Request body for selecting a tenant."""

    tenant_name: str


@router.post("/auth/login")
async def login(body: LoginRequest) -> dict[str, Any]:
    """Start the interactive OAuth flow."""
    try:
        return build_auth_url(body.environment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/auth/status")
async def auth_status() -> dict[str, Any]:
    """Return current authentication status."""
    return get_status()


@router.post("/auth/select-tenant")
async def auth_select_tenant(body: SelectTenantRequest) -> dict[str, Any]:
    """Select a tenant after login."""
    try:
        return select_tenant(body.tenant_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/logout")
async def auth_logout() -> dict[str, str]:
    """Clear authentication."""
    logout()
    return {"status": "unauthenticated"}
