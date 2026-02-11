"""Entrypoint discovery and schema endpoints."""

from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from uipath.dev.ui.panels._json_schema import mock_json_from_schema

router = APIRouter(tags=["entrypoints"])
logger = logging.getLogger(__name__)


@router.get("/entrypoints")
async def list_entrypoints(request: Request) -> list[dict[str, Any]]:
    """List all available entrypoints from the runtime factory."""
    server = request.app.state.server
    factory = server.runtime_factory

    entrypoints: list[str] = []

    # Try discover_entrypoints() first (mock factory pattern)
    if hasattr(factory, "discover_entrypoints"):
        try:
            entrypoints = factory.discover_entrypoints()
        except Exception:
            logger.exception("Failed to discover entrypoints")
    elif hasattr(factory, "list_entrypoints"):
        try:
            entrypoints = list(factory.list_entrypoints())
        except Exception:
            logger.exception("Failed to list entrypoints")
    elif hasattr(factory, "entrypoints"):
        entrypoints = list(factory.entrypoints)

    return [{"name": ep} for ep in entrypoints]


@router.get("/entrypoints/{entrypoint:path}/schema")
async def get_entrypoint_schema(request: Request, entrypoint: str) -> dict[str, Any]:
    """Get the input/output schema for an entrypoint.

    Creates a temporary runtime to fetch the schema, mirroring TUI behavior.
    """
    server = request.app.state.server
    factory = server.runtime_factory

    result: dict[str, Any] = {"entrypoint": entrypoint, "input": {}, "output": {}}

    runtime = None
    try:
        runtime = await factory.new_runtime(entrypoint, runtime_id="schema-probe")
        schema_obj = await runtime.get_schema()

        if schema_obj.input:
            result["input"] = (
                schema_obj.input
                if isinstance(schema_obj.input, dict)
                else schema_obj.input.model_dump(by_alias=True, exclude_none=True)
            )
        if schema_obj.output:
            result["output"] = (
                schema_obj.output
                if isinstance(schema_obj.output, dict)
                else schema_obj.output.model_dump(by_alias=True, exclude_none=True)
            )
    except Exception as exc:
        logger.exception("Failed to get schema for %s", entrypoint)
        error_detail = {
            "message": f"Failed to load schema for '{entrypoint}'",
            "error": str(exc),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail) from exc
    finally:
        if runtime is not None:
            try:
                await runtime.dispose()
            except Exception:
                pass

    return result


@router.get("/entrypoints/{entrypoint:path}/mock-input")
async def get_entrypoint_mock_input(
    request: Request, entrypoint: str
) -> dict[str, Any]:
    """Generate a mock JSON input based on the entrypoint's input schema.

    Uses the same mock_json_from_schema logic as the TUI.
    """
    server = request.app.state.server
    factory = server.runtime_factory

    runtime = None
    try:
        runtime = await factory.new_runtime(entrypoint, runtime_id="mock-input-probe")
        schema_obj = await runtime.get_schema()

        input_schema = schema_obj.input or {}
        if not isinstance(input_schema, dict):
            input_schema = input_schema.model_dump(by_alias=True, exclude_none=True)

        mock_data = mock_json_from_schema(input_schema)
        return {"entrypoint": entrypoint, "mock_input": mock_data}
    except Exception as exc:
        logger.exception("Failed to generate mock input for %s", entrypoint)
        error_detail = {
            "message": f"Failed to generate mock input for '{entrypoint}'",
            "error": str(exc),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail) from exc
    finally:
        if runtime is not None:
            try:
                await runtime.dispose()
            except Exception:
                pass
