"""UiPath Developer Console Application."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pyperclip  # type: ignore[import-untyped]
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Button, Footer, Input, ListView, RichLog
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import UiPathRuntimeFactoryProtocol

from uipath.dev.infrastructure import (
    patch_textual_stderr,
)
from uipath.dev.models import (
    ChatMessage,
    ExecutionMode,
    ExecutionRun,
    LogMessage,
    TraceMessage,
)
from uipath.dev.models.chat import get_user_message, get_user_message_event
from uipath.dev.services import RunService
from uipath.dev.ui.panels import NewRunPanel, RunDetailsPanel, RunHistoryPanel


class UiPathDeveloperConsole(App[Any]):
    """UiPath developer console interface."""

    TITLE = "UiPath Developer Console"
    SUB_TITLE = (
        "Interactive terminal application for building, testing, and debugging "
        "UiPath Python runtimes, agents, and automation scripts."
    )
    CSS_PATH = Path(__file__).parent / "ui" / "styles" / "terminal.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_run", "New"),
        Binding("r", "execute_run", "Run"),
        Binding("c", "copy", "Copy"),
        Binding("h", "clear_history", "Clear History"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        runtime_factory: UiPathRuntimeFactoryProtocol,
        trace_manager: UiPathTraceManager,
        **kwargs,
    ):
        """Initialize the UiPath Dev Terminal App."""
        # Capture subprocess stderr lines and route to our log handler
        self._stderr_write_fd: int = patch_textual_stderr(self._add_subprocess_log)

        super().__init__(**kwargs)

        self.runtime_factory = runtime_factory
        self.trace_manager = trace_manager

        # Core service: owns run state, logs, traces
        self.run_service = RunService(
            runtime_factory=self.runtime_factory,
            trace_manager=self.trace_manager,
            on_run_updated=self._on_run_updated,
            on_log=self._on_log_for_ui,
            on_trace=self._on_trace_for_ui,
            on_chat=self._on_chat_for_ui,
        )

        # Just defaults for convenience
        self.initial_entrypoint: str = "main.py"
        self.initial_input: str = '{\n  "message": "Hello World"\n}'

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        with Horizontal():
            # Left sidebar - run history
            with Container(classes="run-history"):
                yield RunHistoryPanel(id="history-panel")

            # Main content area
            with Container(classes="main-content"):
                # New run panel (initially visible)
                yield NewRunPanel(
                    id="new-run-panel",
                    classes="new-run-panel",
                    runtime_factory=self.runtime_factory,
                )

                # Run details panel (initially hidden)
                yield RunDetailsPanel(id="details-panel", classes="hidden")

        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "new-run-btn":
            await self.action_new_run()
        elif event.button.id == "execute-btn":
            await self.action_execute_run(mode=ExecutionMode.RUN)
        elif event.button.id == "debug-btn":
            await self.action_execute_run(mode=ExecutionMode.DEBUG)
        elif event.button.id == "chat-btn":
            await self.action_execute_run(mode=ExecutionMode.CHAT)
        elif event.button.id == "cancel-btn":
            await self.action_cancel()
        elif event.button.id == "debug-step-btn":
            await self.action_debug_step()
        elif event.button.id == "debug-continue-btn":
            await self.action_debug_continue()
        elif event.button.id == "debug-stop-btn":
            await self.action_debug_stop()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle run selection from history."""
        if event.list_view.id == "run-list" and event.item:
            run_id = getattr(event.item, "run_id", None)
            if run_id:
                history_panel = self.query_one("#history-panel", RunHistoryPanel)
                run = history_panel.get_run_by_id(run_id)
                if run:
                    self._show_run_details(run)

    @on(Input.Submitted, "#chat-input")
    async def handle_chat_input(self, event: Input.Submitted) -> None:
        """Handle user submitting text into the chat."""
        user_text = event.value.strip()
        if not user_text:
            return

        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel and details_panel.current_run:
            status = details_panel.current_run.status
            if status == "running":
                self.app.notify(
                    "Wait for agent response...", timeout=1.5, severity="warning"
                )
                return

            if details_panel.current_run.status == "suspended":
                details_panel.current_run.resume_data = {"value": user_text}
            else:
                msg = get_user_message(user_text)
                msg_ev = get_user_message_event(
                    user_text, conversation_id=details_panel.current_run.id
                )
                self._on_chat_for_ui(
                    ChatMessage(
                        event=msg_ev,
                        message=msg,
                        run_id=details_panel.current_run.id,
                    )
                )
                details_panel.current_run.input_data = {"messages": [msg]}

            asyncio.create_task(self._execute_runtime(details_panel.current_run))

            event.input.clear()

    async def action_new_run(self) -> None:
        """Show new run panel."""
        new_panel = self.query_one("#new-run-panel")
        details_panel = self.query_one("#details-panel")

        new_panel.remove_class("hidden")
        details_panel.add_class("hidden")

    async def action_cancel(self) -> None:
        """Cancel and return to new run view."""
        await self.action_new_run()

    async def action_execute_run(self, mode: ExecutionMode) -> None:
        """Execute a new run based on NewRunPanel inputs."""
        new_run_panel = self.query_one("#new-run-panel", NewRunPanel)
        entrypoint, input_data = new_run_panel.get_input_values()

        if not entrypoint:
            return

        try:
            input_payload: dict[str, Any] = json.loads(input_data)
        except json.JSONDecodeError:
            return

        run = ExecutionRun(entrypoint, input_payload, mode=mode)

        history_panel = self.query_one("#history-panel", RunHistoryPanel)
        history_panel.add_run(run)

        self.run_service.register_run(run)

        self._show_run_details(run)

        if mode == ExecutionMode.CHAT:
            self._focus_chat_input()
        else:
            asyncio.create_task(self._execute_runtime(run))

    async def action_debug_step(self) -> None:
        """Step to next breakpoint in debug mode."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel and details_panel.current_run:
            run = details_panel.current_run
            self.run_service.step_debug(run)

    async def action_debug_continue(self) -> None:
        """Continue execution without stopping at breakpoints."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel and details_panel.current_run:
            run = details_panel.current_run
            self.run_service.continue_debug(run)

    async def action_debug_stop(self) -> None:
        """Stop debug execution."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel and details_panel.current_run:
            run = details_panel.current_run
            self.run_service.stop_debug(run)

    async def action_clear_history(self) -> None:
        """Clear run history."""
        history_panel = self.query_one("#history-panel", RunHistoryPanel)
        history_panel.clear_runs()
        await self.action_new_run()

    def action_copy(self) -> None:
        """Copy content of currently focused RichLog to clipboard and notify."""
        focused = self.app.focused
        if isinstance(focused, RichLog):
            clipboard_text = "\n".join(line.text for line in focused.lines)
            pyperclip.copy(clipboard_text)
            self.app.notify("Copied to clipboard!", timeout=1.5)
        else:
            self.app.notify("Nothing to copy here.", timeout=1.5, severity="warning")

    async def _execute_runtime(self, run: ExecutionRun) -> None:
        """Wrapper that delegates execution to RunService."""
        await self.run_service.execute(run)

    def _on_run_updated(self, run: ExecutionRun) -> None:
        """Called whenever a run changes (status, times, logs, traces)."""
        # Update the run in history
        history_panel = self.query_one("#history-panel", RunHistoryPanel)
        history_panel.update_run(run)

        # If this run is currently shown, refresh details
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel.current_run and details_panel.current_run.id == run.id:
            details_panel.update_run_details(run)

    def _on_log_for_ui(self, log_msg: LogMessage) -> None:
        """Append a log message to the logs UI."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.add_log(log_msg)

    def _on_trace_for_ui(self, trace_msg: TraceMessage) -> None:
        """Append/refresh traces in the UI."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.add_trace(trace_msg)

    def _on_chat_for_ui(
        self,
        chat_msg: ChatMessage,
    ) -> None:
        """Append/refresh chat messages in the UI."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.add_chat_message(chat_msg)

    def _show_run_details(self, run: ExecutionRun) -> None:
        """Show details panel for a specific run."""
        new_panel = self.query_one("#new-run-panel")
        details_panel = self.query_one("#details-panel", RunDetailsPanel)

        new_panel.add_class("hidden")
        details_panel.remove_class("hidden")

        details_panel.update_run(run)

    def _focus_chat_input(self) -> None:
        """Focus the chat input box."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.switch_tab("chat-tab")
        chat_input = details_panel.query_one("#chat-input", Input)
        chat_input.focus()

    def _add_subprocess_log(self, level: str, message: str) -> None:
        """Handle a stderr line coming from subprocesses."""

        def add_log() -> None:
            details_panel = self.query_one("#details-panel", RunDetailsPanel)
            run: ExecutionRun = cast(
                ExecutionRun, getattr(details_panel, "current_run", None)
            )
            if run:
                log_msg = LogMessage(run.id, level, message, datetime.now())
                # Route through RunService so state + UI stay in sync
                self.run_service.handle_log(log_msg)

        self.call_from_thread(add_log)
