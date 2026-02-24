"""JSON serialization helpers for data models."""

from __future__ import annotations

import json
from typing import Any

from uipath.dev.models.data import (
    ChatData,
    InterruptData,
    LogData,
    StateData,
    TraceData,
)
from uipath.dev.models.execution import ExecutionRun


def _sanitize(obj: Any) -> Any:
    """Ensure a value is JSON-serializable, converting non-serializable objects to str."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    # Catch-all: try json.dumps; if it fails, stringify
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def serialize_log(log_data: LogData) -> dict[str, Any]:
    """Serialize a LogData instance to a JSON-compatible dict."""
    return {
        "run_id": log_data.run_id,
        "level": log_data.level,
        "message": log_data.message,
        "timestamp": log_data.timestamp.isoformat(),
    }


def serialize_trace(trace_data: TraceData) -> dict[str, Any]:
    """Serialize a TraceData instance to a JSON-compatible dict."""
    return {
        "run_id": trace_data.run_id,
        "span_name": trace_data.span_name,
        "span_id": trace_data.span_id,
        "parent_span_id": trace_data.parent_span_id,
        "trace_id": trace_data.trace_id,
        "status": trace_data.status,
        "duration_ms": trace_data.duration_ms,
        "timestamp": trace_data.timestamp.isoformat(),
        "attributes": _sanitize(trace_data.attributes),
    }


def serialize_chat(chat_data: ChatData) -> dict[str, Any]:
    """Serialize a ChatData instance to a JSON-compatible dict."""
    result: dict[str, Any] = {
        "run_id": chat_data.run_id,
    }
    if chat_data.event is not None:
        result["event"] = chat_data.event.model_dump(by_alias=True, exclude_none=True)
    if chat_data.message is not None:
        result["message"] = chat_data.message.model_dump(
            by_alias=True, exclude_none=True
        )
    return result


def serialize_state(state_data: StateData) -> dict[str, Any]:
    """Serialize a StateData instance to a JSON-compatible dict."""
    result: dict[str, Any] = {
        "run_id": state_data.run_id,
        "node_name": state_data.node_name,
        "timestamp": state_data.timestamp.isoformat(),
    }
    if state_data.qualified_node_name is not None:
        result["qualified_node_name"] = state_data.qualified_node_name
    if state_data.phase is not None:
        result["phase"] = state_data.phase
    if state_data.payload is not None:
        result["payload"] = _sanitize(state_data.payload)
    return result


def serialize_interrupt(interrupt_data: InterruptData) -> dict[str, Any]:
    """Serialize an InterruptData instance to a JSON-compatible dict."""
    result: dict[str, Any] = {
        "run_id": interrupt_data.run_id,
        "interrupt_id": interrupt_data.interrupt_id,
        "interrupt_type": interrupt_data.interrupt_type,
    }
    if interrupt_data.tool_call_id is not None:
        result["tool_call_id"] = interrupt_data.tool_call_id
    if interrupt_data.tool_name is not None:
        result["tool_name"] = interrupt_data.tool_name
    if interrupt_data.input_schema is not None:
        result["input_schema"] = _sanitize(interrupt_data.input_schema)
    if interrupt_data.input_value is not None:
        result["input_value"] = _sanitize(interrupt_data.input_value)
    if interrupt_data.content is not None:
        result["content"] = _sanitize(interrupt_data.content)
    return result


def serialize_run(run: ExecutionRun) -> dict[str, Any]:
    """Serialize an ExecutionRun to a JSON-compatible dict."""
    return {
        "id": run.id,
        "entrypoint": run.entrypoint,
        "input_data": run.input_data,
        "mode": run.mode.value,
        "status": run.status,
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "duration": run.duration,
        "output_data": _sanitize(run.output_data),
        "error": (
            {
                "code": run.error.code,
                "title": run.error.title,
                "detail": run.error.detail,
                "category": run.error.category.value
                if hasattr(run.error.category, "value")
                else str(run.error.category),
            }
            if run.error
            else None
        ),
        "trace_count": len(run.traces),
        "log_count": len(run.logs),
        "message_count": len(run.messages),
        "breakpoint_node": run.breakpoint_node,
        "breakpoint_next_nodes": run.breakpoint_next_nodes,
        "breakpoints": run.breakpoints,
    }


def serialize_run_detail(run: ExecutionRun) -> dict[str, Any]:
    """Serialize an ExecutionRun with full traces, logs, and messages."""
    base = serialize_run(run)
    base["traces"] = [serialize_trace(t) for t in run.traces]
    base["logs"] = [serialize_log(entry) for entry in run.logs]
    base["messages"] = [
        msg.model_dump(by_alias=True, exclude_none=True) for msg in run.messages
    ]
    base["states"] = [serialize_state(s) for s in run.states]
    base["graph"] = run.graph_data
    return base
