"""UiPath Developer Server - Web/API mode for the developer console."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from typing import Any

import uvicorn
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import UiPathRuntimeFactoryProtocol

from uipath.dev.models.data import (
    ChatData,
    InterruptData,
    LogData,
    StateData,
    TraceData,
)
from uipath.dev.models.execution import ExecutionRun
from uipath.dev.server.debug_bridge import WebDebugBridge
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
        host: str = os.environ.get("UIPATH_DEV_SERVER_HOST", "localhost"),
        port: int = int(os.environ.get("UIPATH_DEV_SERVER_PORT", "8080")),
        open_browser: bool = True,
        factory_creator: Callable[[], UiPathRuntimeFactoryProtocol] | None = None,
    ) -> None:
        """Initialize the developer server."""
        self.runtime_factory = runtime_factory
        self.trace_manager = trace_manager
        self.host = host
        self.port = port
        self.open_browser = open_browser
        self.factory_creator = factory_creator

        self._watcher_task: asyncio.Task[None] | None = None
        self._watcher_stop: asyncio.Event | None = None
        self.reload_pending = False

        from uipath.dev.server.ws.manager import ConnectionManager

        self.connection_manager = ConnectionManager()

        self.run_service = RunService(
            runtime_factory=self.runtime_factory,
            trace_manager=self.trace_manager,
            on_run_updated=self._on_run_updated,
            on_log=self._on_log,
            on_trace=self._on_trace,
            on_chat=self._on_chat,
            on_state=self._on_state,
            on_interrupt=self._on_interrupt,
            debug_bridge_factory=lambda mode: WebDebugBridge(mode=mode),
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
        await self.run_service.apply_factory_settings()
        self.port = self._find_free_port(self.host, self.port)
        app = self.create_app()

        base_url = f"http://{self.host}:{self.port}"
        self._print_banner(base_url)

        if self.open_browser:
            threading.Thread(
                target=self._deferred_open_browser,
                daemon=True,
            ).start()

        # Start file watcher if factory_creator is available
        if self.factory_creator is not None:
            self._start_watcher()

        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def shutdown(self) -> None:
        """Clean up resources before shutting down."""
        logger.info("Shutting down server resources...")
        self._stop_watcher()
        # Close any active WebSocket connections
        await self.connection_manager.disconnect_all()
        # Give threads time to finish
        await asyncio.sleep(0.1)

    def run(self) -> None:
        """Synchronous wrapper around :meth:`run_async`."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            pass

    # ------------------------------------------------------------------
    # Hot-reload support
    # ------------------------------------------------------------------

    async def reload_factory(self) -> None:
        """Dispose old factory, flush user modules, and recreate."""
        if self.factory_creator is None:
            return

        # Dispose old factory if it supports it
        if hasattr(self.runtime_factory, "dispose"):
            try:
                await self.runtime_factory.dispose()
            except Exception:
                logger.debug("Error disposing old factory", exc_info=True)

        # Flush user modules (files under cwd, excluding venvs/site-packages)
        cwd = os.getcwd()
        to_remove = [
            name
            for name, mod in sys.modules.items()
            if hasattr(mod, "__file__")
            and mod.__file__ is not None
            and os.path.abspath(mod.__file__).startswith(cwd)
            and ".venv" not in mod.__file__
            and "site-packages" not in mod.__file__
        ]
        for name in to_remove:
            del sys.modules[name]
        logger.debug("Flushed %d user modules", len(to_remove))

        # Recreate factory
        self.runtime_factory = self.factory_creator()
        self.run_service.runtime_factory = self.runtime_factory
        await self.run_service.apply_factory_settings()
        self.reload_pending = False
        logger.debug("Factory reloaded successfully")

    def _start_watcher(self) -> None:
        """Start the file watcher background task."""
        from uipath.dev.server.watcher import watch_python_files

        self._watcher_stop = asyncio.Event()
        self._watcher_task = asyncio.create_task(
            watch_python_files(
                on_change=self._on_files_changed,
                stop_event=self._watcher_stop,
            )
        )

    def _stop_watcher(self) -> None:
        """Stop the file watcher background task."""
        if self._watcher_stop is not None:
            self._watcher_stop.set()
        if self._watcher_task is not None:
            self._watcher_task.cancel()
            self._watcher_task = None

    def _on_files_changed(self, changed_files: list[str]) -> None:
        """Handle file change events from the watcher."""
        self.reload_pending = True
        self.connection_manager.broadcast_reload(changed_files)

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

    def _on_interrupt(self, interrupt_data: InterruptData) -> None:
        """Broadcast chat interrupt to subscribed WebSocket clients."""
        self.connection_manager.broadcast_interrupt(interrupt_data)

    def _on_state(self, state_data: StateData) -> None:
        """Broadcast state transition to subscribed WebSocket clients."""
        self.connection_manager.broadcast_state(state_data)

    @staticmethod
    def _find_free_port(host: str, start_port: int, max_attempts: int = 100) -> int:
        """Find a free port starting from *start_port*.

        Tries *start_port*, then *start_port + 1*, etc. up to *max_attempts*.
        """
        for offset in range(max_attempts):
            port = start_port + offset
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, port))
                    return port
            except OSError:
                continue
        raise OSError(
            f"Could not find a free port in range {start_port}-{start_port + max_attempts - 1}"
        )

    @staticmethod
    def _print_banner(base_url: str) -> None:
        """Print a welcome banner to the console."""
        import sys

        from rich.console import Console
        from rich.text import Text

        console = Console()

        # Use emojis only if stdout supports unicode (not Windows cp1252)
        try:
            "\U0001f916".encode(sys.stdout.encoding or "utf-8")
            server_icon, docs_icon = "\U0001f916", "\U0001f4da"
        except (UnicodeEncodeError, LookupError):
            server_icon, docs_icon = ">>", ">>"

        art_lines = [
            " _   _ _ ____       _   _       ____",
            "| | | (_)  _ \\ __ _| |_| |__   |  _ \\  _____   __",
            "| | | | | |_) / _` | __| '_ \\  | | | |/ _ \\ \\ / /",
            "| |_| | |  __/ (_| | |_| | | | | |_| |  __/\\ V /",
            " \\___/|_|_|   \\__,_|\\__|_| |_| |____/ \\___| \\_/",
        ]

        console.print()
        for line in art_lines:
            styled = Text(line)
            styled.stylize("bold orange1")
            console.print(styled)
        console.print()

        console.print(f"  {server_icon} Server: [bold cyan]{base_url}[/bold cyan]")
        console.print(
            f"  {docs_icon} Docs:   [link=https://uipath.github.io/uipath-python/]"
            "https://uipath.github.io/uipath-python/[/link]"
        )
        console.print()
        console.print(
            "  [dim]This server is designed for development and testing.[/dim]"
        )
        console.print()

    def _deferred_open_browser(self) -> None:
        """Open the browser after a short delay to let uvicorn bind."""
        time.sleep(1.5)
        webbrowser.open(f"http://{self.host}:{self.port}")
