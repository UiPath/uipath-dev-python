"""WebSocket connection manager with run-level subscriptions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

from uipath.dev.models.data import ChatData, LogData, TraceData
from uipath.dev.models.execution import ExecutionRun
from uipath.dev.server.serializers import (
    serialize_chat,
    serialize_log,
    serialize_run,
    serialize_trace,
)
from uipath.dev.server.ws.protocol import ServerEvent, server_message

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and run-level subscriptions."""

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self._connections: set[WebSocket] = set()
        self._subscriptions: dict[str, set[WebSocket]] = {}
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
        logger.info(f"WebSocket connected: {id(websocket)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection and all its subscriptions."""
        self._connections.discard(websocket)
        for run_id in list(self._subscriptions):
            self._subscriptions[run_id].discard(websocket)
            if not self._subscriptions[run_id]:
                del self._subscriptions[run_id]
        logger.info(f"WebSocket disconnected: {id(websocket)}")

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

    def _schedule_broadcast(self, run_id: str, message: dict[str, Any]) -> None:
        """Schedule an async broadcast from a potentially sync callback."""
        subscribers = self._subscriptions.get(run_id, set())
        if not subscribers:
            return

        try:
            loop = self._get_loop()
            asyncio.ensure_future(
                self._send_to_all(subscribers.copy(), message), loop=loop
            )
        except RuntimeError:
            logger.debug("No event loop available for broadcast")

    async def _send_to_all(
        self, subscribers: set[WebSocket], message: dict[str, Any]
    ) -> None:
        """Send a message to all subscribers, removing disconnected ones."""
        disconnected: list[WebSocket] = []
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)
