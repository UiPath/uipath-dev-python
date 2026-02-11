"""UiPath Developer Server - Web/API mode for the developer console."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import webbrowser
from typing import Any

from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import UiPathRuntimeFactoryProtocol

from uipath.dev.models.data import ChatData, LogData, TraceData
from uipath.dev.models.execution import ExecutionRun
from uipath.dev.services.run_service import RunService

logger = logging.getLogger(__name__)


class UiPathDeveloperServer:
    """Web server mode for the UiPath Developer Console.

    Provides the same functionality as UiPathDeveloperConsole but via
    a FastAPI + WebSocket backend instead of a Textual TUI.

    Usage::

        server = UiPathDeveloperServer(
            runtime_factory=factory,
            trace_manager=trace_manager,
        )
        await server.run_async()          # builds frontend, starts uvicorn, opens browser
        # or
        app = server.create_app()         # just get the FastAPI app
    """

    def __init__(
        self,
        runtime_factory: UiPathRuntimeFactoryProtocol,
        trace_manager: UiPathTraceManager,
        host: str = "localhost",
        port: int = 8000,
        open_browser: bool = True,
    ) -> None:
        """Initialize the developer server."""
        self.runtime_factory = runtime_factory
        self.trace_manager = trace_manager
        self.host = host
        self.port = port
        self.open_browser = open_browser

        from uipath.dev.server.ws.manager import ConnectionManager

        self.connection_manager = ConnectionManager()

        self.run_service = RunService(
            runtime_factory=self.runtime_factory,
            trace_manager=self.trace_manager,
            on_run_updated=self._on_run_updated,
            on_log=self._on_log,
            on_trace=self._on_trace,
            on_chat=self._on_chat,
        )

    def create_app(self) -> Any:
        """Create and return a FastAPI application."""
        from uipath.dev.server.app import create_app

        return create_app(self)

    async def run_async(self) -> None:
        """Build frontend, start the server, and open the browser.

        This is the main entry point — mirrors UiPathDeveloperConsole.run_async().
        Blocks until the server is shut down (Ctrl-C / SIGINT).
        """
        import uvicorn

        app = self.create_app()

        if self.open_browser:
            threading.Thread(
                target=self._deferred_open_browser,
                daemon=True,
            ).start()

        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def shutdown(self) -> None:
        """Clean up resources before shutting down."""
        logger.info("Shutting down server resources...")
        # Close any active WebSocket connections
        await self.connection_manager.disconnect_all()
        # Give threads time to finish
        await asyncio.sleep(0.1)

    def run(self) -> None:
        """Synchronous wrapper around :meth:`run_async`."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("Server stopped.")

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _on_run_updated(self, run: ExecutionRun) -> None:
        """Broadcast run update to subscribed WebSocket clients."""
        self.connection_manager.broadcast_run_updated(run)

    def _on_log(self, log_data: LogData) -> None:
        """Broadcast log to subscribed WebSocket clients."""
        self.connection_manager.broadcast_log(log_data)

    def _on_trace(self, trace_data: TraceData) -> None:
        """Broadcast trace to subscribed WebSocket clients."""
        self.connection_manager.broadcast_trace(trace_data)

    def _on_chat(self, chat_data: ChatData) -> None:
        """Broadcast chat message to subscribed WebSocket clients."""
        self.connection_manager.broadcast_chat(chat_data)

    def _deferred_open_browser(self) -> None:
        """Open the browser after a short delay to let uvicorn bind."""
        time.sleep(1.5)
        url = f"http://{self.host}:{self.port}"
        logger.info("Opening browser at %s", url)
        webbrowser.open(url)
