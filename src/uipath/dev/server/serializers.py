"""JSON serialization helpers for data models."""

from __future__ import annotations

from typing import Any

from uipath.dev.models.data import ChatData, LogData, StateData, TraceData
from uipath.dev.models.execution import ExecutionRun


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
        "attributes": trace_data.attributes,
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
    return {
        "run_id": state_data.run_id,
        "node_name": state_data.node_name,
    }


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
        "output_data": run.output_data,
        "error": (
            {
                "code": run.error.code,
                "title": run.error.title,
                "detail": run.error.detail,
            }
            if run.error
            else None
        ),
        "trace_count": len(run.traces),
        "log_count": len(run.logs),
        "message_count": len(run.messages),
        "breakpoint_node": run.breakpoint_node,
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
    return base
