"""WebSocket connection manager with run-level subscriptions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

from uipath.dev.models.data import (
    ChatData,
    LogData,
    StateData,
    TraceData,
)
from uipath.dev.models.eval_data import EvalItemResult, EvalRunState
from uipath.dev.models.execution import ExecutionRun
from uipath.dev.server.serializers import (
    serialize_chat,
    serialize_log,
    serialize_run,
    serialize_state,
    serialize_trace,
)
from uipath.dev.server.ws.protocol import ServerEvent, server_message

logger = logging.getLogger(__name__)

_SENTINEL: dict[str, Any] = {}  # Unique object used to signal queue shutdown


class ConnectionManager:
    """Manages WebSocket connections and run-level subscriptions."""

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self._connections: set[WebSocket] = set()
        self._subscriptions: dict[str, set[WebSocket]] = {}
        self._queues: dict[int, asyncio.Queue[dict[str, Any]]] = {}
        self._send_tasks: dict[int, asyncio.Task[None]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or cache the running event loop."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.get_event_loop()
        return self._loop

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        ws_id = id(websocket)
        self._queues[ws_id] = queue
        self._send_tasks[ws_id] = asyncio.create_task(self._sender(websocket, queue))

    async def _sender(
        self, ws: WebSocket, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        """Consume messages from queue and send them serially."""
        while True:
            message = await queue.get()
            if message is _SENTINEL:
                break
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)
                break

    def _enqueue(self, ws: WebSocket, message: dict[str, Any]) -> None:
        """Put a message on a WebSocket's send queue (non-blocking)."""
        queue = self._queues.get(id(ws))
        if queue is not None:
            queue.put_nowait(message)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection and all its subscriptions."""
        self._connections.discard(websocket)
        for run_id in list(self._subscriptions):
            self._subscriptions[run_id].discard(websocket)
            if not self._subscriptions[run_id]:
                del self._subscriptions[run_id]

        ws_id = id(websocket)
        queue = self._queues.pop(ws_id, None)
        if queue is not None:
            try:
                queue.put_nowait(_SENTINEL)
            except Exception:
                pass
        task = self._send_tasks.pop(ws_id, None)
        if task is not None and not task.done():
            task.cancel()

    async def disconnect_all(self) -> None:
        """Close all WebSocket connections gracefully."""
        for ws in list(self._connections):
            try:
                await ws.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")
            self.disconnect(ws)
        self._connections.clear()
        self._subscriptions.clear()

    def subscribe(self, websocket: WebSocket, run_id: str) -> None:
        """Subscribe a WebSocket to a run's events."""
        if run_id not in self._subscriptions:
            self._subscriptions[run_id] = set()
        self._subscriptions[run_id].add(websocket)

    def unsubscribe(self, websocket: WebSocket, run_id: str) -> None:
        """Unsubscribe a WebSocket from a run's events."""
        if run_id in self._subscriptions:
            self._subscriptions[run_id].discard(websocket)
            if not self._subscriptions[run_id]:
                del self._subscriptions[run_id]

    def remove_run_subscriptions(self, run_id: str) -> None:
        """Remove all subscriptions for a run."""
        self._subscriptions.pop(run_id, None)

    def broadcast_run_updated(self, run: ExecutionRun) -> None:
        """Broadcast a run update to ALL connected clients.

        This goes to all connections (not just subscribers) so the runs list
        in the sidebar updates when new runs are created externally (e.g. MCP).
        Subscribers additionally receive state/log/trace events.
        """
        msg = server_message(ServerEvent.RUN_UPDATED, serialize_run(run))
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_log(self, log_data: LogData) -> None:
        """Broadcast a log entry to run subscribers."""
        msg = server_message(ServerEvent.LOG, serialize_log(log_data))
        self._schedule_broadcast(log_data.run_id, msg)

    def broadcast_trace(self, trace_data: TraceData) -> None:
        """Broadcast a trace span to run subscribers."""
        msg = server_message(ServerEvent.TRACE, serialize_trace(trace_data))
        self._schedule_broadcast(trace_data.run_id, msg)

    def broadcast_chat(self, chat_data: ChatData) -> None:
        """Broadcast a chat message to run subscribers."""
        msg = server_message(ServerEvent.CHAT, serialize_chat(chat_data))
        self._schedule_broadcast(chat_data.run_id, msg)

    def broadcast_state(self, state_data: StateData) -> None:
        """Broadcast a state transition to all connected clients.

        Sent to all connections (not just subscribers) so the explorer
        canvas can highlight nodes for runs started externally (e.g. MCP).
        """
        msg = server_message(ServerEvent.STATE, serialize_state(state_data))
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_reload(
        self, changed_files: list[str], *, reloaded: bool = False
    ) -> None:
        """Broadcast a reload event to all connected clients.

        Args:
            reloaded: If True, the server already reloaded the factory and
                      the client only needs to refresh entrypoints.
        """
        msg = server_message(
            ServerEvent.RELOAD, {"files": changed_files, "reloaded": reloaded}
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_files_changed(self, changed_files: list[str]) -> None:
        """Broadcast file changes for editor auto-refresh."""
        msg = server_message(ServerEvent.FILES_CHANGED, {"files": changed_files})
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_eval_run_created(self, run: EvalRunState) -> None:
        """Broadcast eval run created to all connected clients."""
        msg = server_message(ServerEvent.EVAL_RUN_CREATED, run.to_summary())
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_eval_run_progress(
        self,
        run_id: str,
        completed: int,
        total: int,
        item_result: EvalItemResult | None,
    ) -> None:
        """Broadcast eval run progress to all connected clients."""
        payload: dict[str, Any] = {
            "run_id": run_id,
            "completed": completed,
            "total": total,
        }
        if item_result is not None:
            payload["item_result"] = {
                "name": item_result.name,
                "inputs": item_result.inputs,
                "expected_output": item_result.expected_output,
                "scores": item_result.scores,
                "overall_score": item_result.overall_score,
                "output": str(item_result.output)
                if isinstance(item_result.output, Exception)
                else item_result.output,
                "justifications": item_result.justifications,
                "duration_ms": item_result.duration_ms,
                "status": item_result.status,
                "error": item_result.error,
                "traces": item_result.traces,
            }
        msg = server_message(ServerEvent.EVAL_RUN_PROGRESS, payload)
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_eval_run_completed(self, run: EvalRunState) -> None:
        """Broadcast eval run completed to all connected clients."""
        msg = server_message(
            ServerEvent.EVAL_RUN_COMPLETED,
            {
                "run_id": run.id,
                "overall_score": run.overall_score,
                "evaluator_scores": run.evaluator_scores,
            },
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_cli_agent_output(self, session_id: str, data: str) -> None:
        """Broadcast CLI agent PTY output (base64-encoded) to all clients."""
        msg = server_message(
            ServerEvent.CLI_AGENT_OUTPUT,
            {"session_id": session_id, "data": data},
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_mcp_tool_call(
        self, tool: str, args: dict[str, Any] | None = None
    ) -> None:
        """Broadcast an MCP tool call event to all clients."""
        msg = server_message(
            ServerEvent.MCP_TOOL_CALL,
            {"tool": tool, "args": args or {}},
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_cli_agent_exit(self, session_id: str, exit_code: int) -> None:
        """Broadcast CLI agent process exit to all clients."""
        msg = server_message(
            ServerEvent.CLI_AGENT_EXIT,
            {"session_id": session_id, "exit_code": exit_code},
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def _schedule_broadcast(self, run_id: str, message: dict[str, Any]) -> None:
        """Enqueue a message for all subscribers of a run."""
        subscribers = self._subscriptions.get(run_id)
        if not subscribers:
            return
        for ws in subscribers:
            self._enqueue(ws, message)
