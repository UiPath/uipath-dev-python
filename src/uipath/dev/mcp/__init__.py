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


def _summarize_eval_run(result: dict[str, Any]) -> dict[str, Any]:
    """Return only scores and justifications per item — drop everything else."""
    items = [
        {
            "name": item.get("name"),
            "status": item.get("status"),
            "scores": item.get("scores", {}),
            "justifications": item.get("justifications", {}),
            "overall_score": item.get("overall_score"),
        }
        for item in result.get("results", [])
    ]
    return {
        "id": result.get("id"),
        "status": result.get("status"),
        "overall_score": result.get("overall_score"),
        "evaluator_scores": result.get("evaluator_scores", {}),
        "results": items,
    }


@mcp.tool()
async def list_eval_sets() -> list[dict[str, Any]]:
    """List all evaluation sets.

    Returns the available eval sets with their IDs, names, item counts,
    and attached evaluator IDs. Use the returned IDs with run_eval_set.
    """
    await _report_tool_call("list_eval_sets")
    async with httpx.AsyncClient() as client:
        resp = await client.get(_api_url("/eval-sets"), timeout=10)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_eval_set(eval_set_id: str) -> dict[str, Any]:
    """Get full details of an evaluation set including all items.

    Args:
        eval_set_id: ID of the eval set (from list_eval_sets).

    Returns the eval set with all items, their inputs, expected outputs,
    and evaluation criteria.
    """
    await _report_tool_call("get_eval_set", {"eval_set_id": eval_set_id})
    async with httpx.AsyncClient() as client:
        resp = await client.get(_api_url(f"/eval-sets/{eval_set_id}"), timeout=10)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def run_eval_set(
    eval_set_id: str,
    ctx: Context,  # type: ignore[type-arg]
) -> dict[str, Any]:
    """Run an evaluation set against the agent.

    Args:
        eval_set_id: ID of the eval set (from list_eval_sets).

    Starts the eval run and streams progress as each item completes.
    Returns the full run result with per-item scores and overall score.
    """
    await _report_tool_call("run_eval_set", {"eval_set_id": eval_set_id})
    async with httpx.AsyncClient() as client:
        resp = await client.post(_api_url(f"/eval-sets/{eval_set_id}/runs"), timeout=30)
        resp.raise_for_status()
        run: dict[str, Any] = resp.json()
        run_id = run["id"]

    await ctx.log("info", f"Eval run {run_id} created — streaming progress...")

    async with websockets.connect(_ws_url()) as ws:
        async for raw in ws:
            msg = json.loads(raw)
            msg_type = msg.get("type", "")
            payload = msg.get("payload", {})

            if msg_type == "eval_run.progress" and payload.get("run_id") == run_id:
                completed = payload.get("completed", 0)
                total = payload.get("total", 0)
                item = payload.get("item_result")
                if item:
                    name = item.get("name", "")
                    status = item.get("status", "")
                    score = item.get("overall_score")
                    score_str = f" — score: {score:.0%}" if score is not None else ""
                    await ctx.log(
                        "info", f"  [{completed}/{total}] {name}: {status}{score_str}"
                    )
                await ctx.report_progress(progress=completed, total=total)

            elif msg_type == "eval_run.completed" and payload.get("run_id") == run_id:
                overall = payload.get("overall_score")
                if overall is not None:
                    await ctx.log(
                        "info", f"Eval run completed — overall score: {overall:.0%}"
                    )
                break

    # Fetch final run detail
    async with httpx.AsyncClient() as client:
        resp = await client.get(_api_url(f"/eval-runs/{run_id}"), timeout=10)
        resp.raise_for_status()
        result = resp.json()

    return _summarize_eval_run(result)


@mcp.tool()
async def list_eval_runs() -> list[dict[str, Any]]:
    """List all evaluation runs.

    Returns summaries of all eval runs with their status, scores,
    and progress. Use run IDs with get_eval_run for full details.
    """
    await _report_tool_call("list_eval_runs")
    async with httpx.AsyncClient() as client:
        resp = await client.get(_api_url("/eval-runs"), timeout=10)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_eval_run(eval_run_id: str) -> dict[str, Any]:
    """Get full details of an evaluation run including per-item results.

    Args:
        eval_run_id: ID of the eval run.

    Returns per-item evaluator scores and justifications.
    """
    await _report_tool_call("get_eval_run", {"eval_run_id": eval_run_id})
    async with httpx.AsyncClient() as client:
        resp = await client.get(_api_url(f"/eval-runs/{eval_run_id}"), timeout=10)
        resp.raise_for_status()
        result = resp.json()

    return _summarize_eval_run(result)


def main() -> None:
    """Entry point for the uipath-dev-mcp CLI command."""
    mcp.run(transport="stdio")
