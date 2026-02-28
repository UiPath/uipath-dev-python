"""WebSocket connection manager with run-level subscriptions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

from uipath.dev.models.data import (
    ChatData,
    InterruptData,
    LogData,
    StateData,
    TraceData,
)
from uipath.dev.models.eval_data import EvalItemResult, EvalRunState
from uipath.dev.models.execution import ExecutionRun
from uipath.dev.server.serializers import (
    serialize_chat,
    serialize_interrupt,
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
        """Broadcast a run update to all subscribers (safe from sync context)."""
        msg = server_message(ServerEvent.RUN_UPDATED, serialize_run(run))
        self._schedule_broadcast(run.id, msg)

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

    def broadcast_interrupt(self, interrupt_data: InterruptData) -> None:
        """Broadcast a chat interrupt to run subscribers."""
        msg = server_message(
            ServerEvent.CHAT_INTERRUPT, serialize_interrupt(interrupt_data)
        )
        self._schedule_broadcast(interrupt_data.run_id, msg)

    def broadcast_state(self, state_data: StateData) -> None:
        """Broadcast a state transition to run subscribers."""
        msg = server_message(ServerEvent.STATE, serialize_state(state_data))
        self._schedule_broadcast(state_data.run_id, msg)

    def broadcast_reload(self, changed_files: list[str]) -> None:
        """Broadcast a reload event to all connected clients."""
        msg = server_message(ServerEvent.RELOAD, {"files": changed_files})
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
                "scores": item_result.scores,
                "overall_score": item_result.overall_score,
                "output": item_result.output,
                "justifications": item_result.justifications,
                "duration_ms": item_result.duration_ms,
                "status": item_result.status,
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

    def broadcast_agent_status(self, session_id: str, status: str) -> None:
        """Broadcast agent status to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_STATUS, {"session_id": session_id, "status": status}
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_text(self, session_id: str, content: str, done: bool) -> None:
        """Broadcast agent text to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_TEXT,
            {"session_id": session_id, "content": content, "done": done},
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_plan(
        self, session_id: str, items: list[dict[str, str]]
    ) -> None:
        """Broadcast agent plan to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_PLAN, {"session_id": session_id, "items": items}
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_tool_use(
        self, session_id: str, tool: str, args: dict[str, Any]
    ) -> None:
        """Broadcast agent tool use to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_TOOL_USE,
            {"session_id": session_id, "tool": tool, "args": args},
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_tool_result(
        self, session_id: str, tool: str, result: str, is_error: bool
    ) -> None:
        """Broadcast agent tool result to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_TOOL_RESULT,
            {
                "session_id": session_id,
                "tool": tool,
                "result": result,
                "is_error": is_error,
            },
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_tool_approval(
        self,
        session_id: str,
        tool_call_id: str,
        tool: str,
        args: dict[str, Any],
    ) -> None:
        """Broadcast agent tool approval request to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_TOOL_APPROVAL,
            {
                "session_id": session_id,
                "tool_call_id": tool_call_id,
                "tool": tool,
                "args": args,
            },
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_error(self, session_id: str, message: str) -> None:
        """Broadcast agent error to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_ERROR,
            {"session_id": session_id, "message": message},
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_thinking(self, session_id: str, content: str) -> None:
        """Broadcast agent thinking/reasoning to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_THINKING,
            {"session_id": session_id, "content": content},
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_text_delta(self, session_id: str, delta: str) -> None:
        """Broadcast a streaming text token to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_TEXT_DELTA,
            {"session_id": session_id, "delta": delta},
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_question(
        self,
        session_id: str,
        question_id: str,
        question: str,
        options: list[str],
    ) -> None:
        """Broadcast agent question to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_QUESTION,
            {
                "session_id": session_id,
                "question_id": question_id,
                "question": question,
                "options": options,
            },
        )
        for ws in self._connections:
            self._enqueue(ws, msg)

    def broadcast_agent_token_usage(
        self,
        session_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_session_tokens: int,
    ) -> None:
        """Broadcast token usage stats to all connected clients."""
        msg = server_message(
            ServerEvent.AGENT_TOKEN_USAGE,
            {
                "session_id": session_id,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_session_tokens": total_session_tokens,
            },
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
