"""UiPath Dev MCP Server — exposes dev server run tools via stdio."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import websockets
from mcp.server.fastmcp import Context, FastMCP

mcp = FastMCP(
    "uipath-dev",
    instructions=(
        "This MCP server is the ONLY way to run, test, or execute agents, "
        "functions, and projects. Do NOT use shell commands like "
        "`uipath run`, `langgraph dev`, `python -m`, or any subprocess. "
        "Always use the tools provided here instead."
    ),
)


def _base_url() -> str:
    port = os.environ.get("UIPATH_DEV_SERVER_PORT", "8080")
    host = os.environ.get("UIPATH_DEV_SERVER_HOST", "localhost")
    return f"http://{host}:{port}"


def _ws_url() -> str:
    port = os.environ.get("UIPATH_DEV_SERVER_PORT", "8080")
    host = os.environ.get("UIPATH_DEV_SERVER_HOST", "localhost")
    return f"ws://{host}:{port}/ws"


def _api_url(path: str) -> str:
    return f"{_base_url()}/api{path}"


async def _report_tool_call(tool: str, args: dict[str, Any] | None = None) -> None:
    """Notify the dev server that an MCP tool was invoked."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                _api_url("/mcp/events"),
                json={"tool": tool, "args": args or {}},
                timeout=5,
            )
    except Exception:
        pass  # Best-effort — don't fail the tool if reporting fails


@mcp.tool()
async def list_entrypoints() -> list[dict[str, Any]]:
    """List all runnable agents, functions, and projects.

    Call this first to discover what is available to run.
    Use the returned names with get_entrypoint_schema or run_entrypoint.
    """
    await _report_tool_call("list_entrypoints")
    async with httpx.AsyncClient() as client:
        resp = await client.get(_api_url("/entrypoints"), timeout=10)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_entrypoint_schema(entrypoint: str) -> dict[str, Any]:
    """Get the input/output schema for an entrypoint.

    Args:
        entrypoint: Name of the entrypoint (from list_entrypoints).

    Returns the JSON schema describing the entrypoint's expected
    input and output. Use this to construct input_data for run_entrypoint.
    """
    await _report_tool_call("get_entrypoint_schema", {"entrypoint": entrypoint})
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _api_url(f"/entrypoints/{entrypoint}/schema"),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def run_entrypoint(
    entrypoint: str,
    ctx: Context,  # type: ignore[type-arg]
    input_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run an agent, function, or project.

    This is the ONLY correct way to execute code in this project — never
    use shell commands.

    Args:
        entrypoint: Name of the entrypoint (from list_entrypoints).
        input_data: Input data matching the entrypoint's input schema.
            Use get_entrypoint_schema to see what fields are expected.
            Defaults to empty dict if not provided.

    Executes on the dev server with real-time graph visualization in the
    browser. Streams progress as nodes execute, then returns the result.
    """
    await _report_tool_call(
        "run_entrypoint", {"entrypoint": entrypoint, "input_data": input_data}
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _api_url("/runs"),
            json={
                "entrypoint": entrypoint,
                "input_data": input_data or {},
                "mode": "run",
            },
            timeout=10,
        )
        resp.raise_for_status()
        run: dict[str, Any] = resp.json()
        run_id = run["id"]

    await ctx.log("info", f"Run {run_id} created — streaming updates...")

    # Connect to WebSocket and subscribe to run events
    terminal_statuses = {"completed", "failed", "suspended"}
    final_status = None

    async with websockets.connect(_ws_url()) as ws:
        # Subscribe to this run's events
        await ws.send(json.dumps({"type": "subscribe", "payload": {"run_id": run_id}}))

        async for raw in ws:
            msg = json.loads(raw)
            msg_type = msg.get("type", "")
            payload = msg.get("payload", {})

            if msg_type == "run.updated" and payload.get("id") == run_id:
                status = payload.get("status", "")
                await ctx.report_progress(
                    progress=1 if status in terminal_statuses else 0,
                    total=1,
                    message=f"Run status: {status}",
                )
                if status in terminal_statuses:
                    final_status = status
                    break

            elif msg_type == "state" and payload.get("run_id") == run_id:
                node = payload.get("node_name", "")
                phase = payload.get("phase", "")
                if phase == "started":
                    await ctx.log("info", f"Node '{node}' started")
                elif phase == "completed":
                    await ctx.log("info", f"Node '{node}' completed")

            elif msg_type == "log" and payload.get("run_id") == run_id:
                level = payload.get("level", "info").lower()
                message = payload.get("message", "")
                await ctx.log(level, message)

    # Fetch final run result
    async with httpx.AsyncClient() as client:
        resp = await client.get(_api_url(f"/runs/{run_id}"), timeout=10)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()

    if final_status == "failed":
        error = result.get("error", {})
        await ctx.log("error", f"Run failed: {error.get('detail', 'unknown error')}")
    else:
        await ctx.log("info", f"Run {final_status}: {run_id}")

    return result


@mcp.tool()
async def get_run_status(run_id: str) -> dict[str, Any]:
    """Get current status and details of a run.

    Args:
        run_id: The run ID returned by run_entrypoint.

    Returns full run details including status, output, traces, and logs.
    """
    await _report_tool_call("get_run_status", {"run_id": run_id})
    async with httpx.AsyncClient() as client:
        resp = await client.get(_api_url(f"/runs/{run_id}"), timeout=10)
        resp.raise_for_status()
        return resp.json()


def main() -> None:
    """Entry point for the uipath-dev-mcp CLI command."""
    mcp.run(transport="stdio")
