"""Graph visualization endpoint (React Flow format)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["graph"])
logger = logging.getLogger(__name__)

# Map runtime node types to React Flow custom node types
_NODE_TYPE_MAP = {
    "__start__": "startNode",
    "__end__": "endNode",
    "model": "modelNode",
    "tool": "toolNode",
}


def _process_graph(graph: Any) -> dict[str, Any]:
    """Recursively convert a runtime graph to React Flow format."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    graph_nodes = getattr(graph, "nodes", [])
    graph_edges = getattr(graph, "edges", [])

    for gn in graph_nodes:
        node_id = getattr(gn, "id", None) or getattr(gn, "name", str(gn))
        node_name = getattr(gn, "name", None) or node_id
        raw_type = getattr(gn, "type", None) or ""

        # Resolve node type: check type field, then ID, then metadata
        node_type = _NODE_TYPE_MAP.get(str(raw_type)) or _NODE_TYPE_MAP.get(
            str(node_id), "defaultNode"
        )

        metadata = getattr(gn, "metadata", {}) or {}
        if "node_type" in metadata:
            node_type = _NODE_TYPE_MAP.get(metadata["node_type"], metadata["node_type"])

        node_data: dict[str, Any] = {"label": node_name}

        # Pass through relevant metadata for frontend rendering
        if metadata:
            for key in ("tool_names", "tool_count", "model_name"):
                if key in metadata:
                    node_data[key] = metadata[key]

        # Recursively process subgraph if present
        subgraph = getattr(gn, "subgraph", None)
        if subgraph is not None:
            node_data["subgraph"] = _process_graph(subgraph)

        nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "data": node_data,
                "position": {"x": 0, "y": 0},
            }
        )

    for ge in graph_edges:
        source = getattr(ge, "source", None) or (
            ge[0] if isinstance(ge, (list, tuple)) else str(ge)
        )
        target = getattr(ge, "target", None) or (
            ge[1] if isinstance(ge, (list, tuple)) else str(ge)
        )
        label = getattr(ge, "label", None) or getattr(ge, "data", None)

        edge_data: dict[str, Any] = {
            "id": f"{source}-{target}",
            "source": source,
            "target": target,
        }
        if label:
            edge_data["label"] = str(label)
            edge_data["conditional"] = True

        edges.append(edge_data)

    return {"nodes": nodes, "edges": edges}


async def snapshot_graph(factory: Any, entrypoint: str) -> dict[str, Any]:
    """Fetch the graph for an entrypoint and return serialised React Flow data."""
    runtime = None
    try:
        runtime = await factory.new_runtime(
            entrypoint=entrypoint,
            runtime_id="graph-preview",
        )

        graph = None
        if hasattr(runtime, "get_schema"):
            try:
                schema = await runtime.get_schema()
                graph = getattr(schema, "graph", None)
            except Exception:
                pass

        if graph is None and hasattr(runtime, "get_graph"):
            graph = runtime.get_graph()
        elif graph is None and hasattr(runtime, "graph"):
            graph = runtime.graph

        if graph is not None:
            return _process_graph(graph)

    except Exception:
        logger.exception("Failed to get graph for %s", entrypoint)
    finally:
        if runtime is not None:
            try:
                await runtime.dispose()
            except Exception:
                pass

    return {"nodes": [], "edges": []}


@router.get("/entrypoints/{entrypoint:path}/graph")
async def get_graph(request: Request, entrypoint: str) -> dict[str, Any]:
    """Get the execution graph for an entrypoint in React Flow format."""
    server = request.app.state.server
    return await snapshot_graph(server.runtime_factory, entrypoint)
