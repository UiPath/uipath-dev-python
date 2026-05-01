"""UiPath Developer Console run service module."""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Protocol, cast

from pydantic import BaseModel
from uipath.core.chat import (
    UiPathConversationMessageEvent,
    UiPathConversationToolCallConfirmationEvent,
)
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathExecutionRuntime,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.chat import UiPathChatRuntime
from uipath.runtime.debug import (
    UiPathBreakpointResult,
    UiPathDebugProtocol,
    UiPathDebugRuntime,
)
from uipath.runtime.errors import (
    UiPathBaseRuntimeError,
    UiPathErrorContract,
)
from uipath.runtime.events import UiPathRuntimeStateEvent

from uipath.dev.infrastructure import RunContextExporter, RunContextLogHandler
from uipath.dev.models.data import (
    ChatData,
    LogData,
    StateData,
    TraceData,
)
from uipath.dev.models.execution import ExecutionMode, ExecutionRun
from uipath.dev.services.chat_bridge import WebChatBridge

MAX_RUNS = 50

RunUpdatedCallback = Callable[[ExecutionRun], None]
LogCallback = Callable[[LogData], None]
TraceCallback = Callable[[TraceData], None]
ChatCallback = Callable[[ChatData], None]
StateCallback = Callable[[StateData], None]


class DebugBridgeProtocol(UiPathDebugProtocol, Protocol):
    """Extended debug bridge protocol with control methods and callbacks."""

    on_execution_started: Callable[[], None] | None
    on_state_update: Callable[[UiPathRuntimeStateEvent], None] | None
    on_breakpoint_hit: Callable[[UiPathBreakpointResult], None] | None
    on_execution_completed: Callable[[UiPathRuntimeResult], None] | None
    on_execution_error: Callable[[str], None] | None

    def resume(self, resume_data: Any) -> None:
        """Signal that execution should resume."""
        ...

    def quit(self) -> None:
        """Signal that execution should quit."""
        ...

    def set_breakpoints(self, breakpoints: list[str] | Literal["*"]) -> None:
        """Set breakpoints."""
        ...


DebugBridgeFactory = Callable[[ExecutionMode], DebugBridgeProtocol]


class RunService:
    """Orchestrates execution runs and keeps ExecutionRun state in sync.

    - Executes / resumes runtimes
    - Updates run status, timings, output, and error
    - Collects logs and traces
    - Notifies observers via callbacks
    """

    def __init__(
        self,
        runtime_factory: UiPathRuntimeFactoryProtocol,
        trace_manager: UiPathTraceManager,
        on_run_updated: RunUpdatedCallback | None = None,
        on_log: LogCallback | None = None,
        on_trace: TraceCallback | None = None,
        on_chat: ChatCallback | None = None,
        on_state: StateCallback | None = None,
        debug_bridge_factory: DebugBridgeFactory | None = None,
        on_run_removed: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize RunService with runtime factory and trace manager."""
        self.runtime_factory = runtime_factory
        self.trace_manager = trace_manager
        self.runs: dict[str, ExecutionRun] = {}

        self.on_run_updated = on_run_updated
        self.on_log = on_log
        self.on_trace = on_trace
        self.on_chat = on_chat
        self.on_state = on_state
        self._debug_bridge_factory = debug_bridge_factory
        self._on_run_removed = on_run_removed

        self._exporter = RunContextExporter(
            on_trace=self.handle_trace,
            on_log=self.handle_log,
        )
        self.trace_manager.add_span_exporter(self._exporter, batch=False)

        self.debug_bridges: dict[str, DebugBridgeProtocol] = {}
        self.chat_bridges: dict[str, WebChatBridge] = {}

    def register_run(self, run: ExecutionRun) -> None:
        """Register a new run and emit an initial update."""
        self.runs[run.id] = run
        self._emit_run_updated(run)
        self._evict_old_runs()

    def _evict_old_runs(self) -> None:
        """Remove oldest terminal runs when total exceeds MAX_RUNS."""
        if len(self.runs) <= MAX_RUNS:
            return

        active = []
        terminal = []
        for run in self.runs.values():
            if run.status in ("pending", "running", "suspended"):
                active.append(run)
            else:
                terminal.append(run)

        keep_terminal = MAX_RUNS - len(active)
        if keep_terminal < 0:
            keep_terminal = 0

        if len(terminal) <= keep_terminal:
            return

        terminal.sort(
            key=lambda r: r.end_time or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        for run in terminal[keep_terminal:]:
            del self.runs[run.id]
            if self._on_run_removed is not None:
                self._on_run_removed(run.id)

    def get_run(self, run_id: str) -> ExecutionRun | None:
        """Get a registered run."""
        return self.runs.get(run_id)

    async def apply_factory_settings(self) -> None:
        """Fetch factory settings and configure span filter on exporter."""
        settings = await self.runtime_factory.get_settings()
        if settings and settings.trace_settings and settings.trace_settings.span_filter:
            self._exporter.span_filter = settings.trace_settings.span_filter

    async def execute(self, run: ExecutionRun) -> None:
        """Execute or resume a run."""
        new_runtime: UiPathRuntimeProtocol | None = None
        try:
            execution_input: dict[str, Any] | str | None = {}
            execution_options: UiPathExecuteOptions = UiPathExecuteOptions(
                breakpoints=run.breakpoints if run.breakpoints else None,
            )

            if run.status == "suspended":
                execution_input = run.resume_data
                execution_options.resume = True
                self._add_info_log(run, f"Resuming execution: {run.entrypoint}")
            else:
                execution_input = run.input_data.copy()
                self._add_info_log(run, f"Starting execution: {run.entrypoint}")

            run.status = "running"
            run.start_time = datetime.now(timezone.utc)
            self._emit_run_updated(run)

            log_handler = RunContextLogHandler(
                run_id=run.id,
                callback=self.handle_log,
            )

            new_runtime = await self.runtime_factory.new_runtime(
                entrypoint=run.entrypoint,
                runtime_id=run.id,
            )

            runtime: UiPathRuntimeProtocol = new_runtime

            if run.mode == ExecutionMode.CHAT:
                chat_bridge = WebChatBridge()
                chat_bridge.on_message = lambda evt: self._handle_chat_message_event(
                    run, evt
                )
                self.chat_bridges[run.id] = chat_bridge

                # ChatRuntime handles suspend/resume internally
                runtime = cast(
                    UiPathRuntimeProtocol,
                    UiPathChatRuntime(
                        delegate=runtime,
                        chat_bridge=chat_bridge,
                    ),
                )

            if self._debug_bridge_factory:
                debug_bridge = self._debug_bridge_factory(run.mode)

                debug_bridge.on_state_update = lambda state: self._handle_state_update(
                    run.id, state
                )
                debug_bridge.on_breakpoint_hit = lambda bp: self._handle_breakpoint_hit(
                    run.id, bp
                )
                debug_bridge.on_execution_started = lambda: self._handle_debug_started(
                    run.id
                )
                debug_bridge.on_execution_error = lambda error: self._add_error_log(
                    run, error
                )

                if run.breakpoints:
                    debug_bridge.set_breakpoints(run.breakpoints)

                self.debug_bridges[run.id] = debug_bridge

                runtime = UiPathDebugRuntime(
                    delegate=runtime,
                    debug_bridge=debug_bridge,
                )

            if run.mode == ExecutionMode.CHAT:
                # Wrap: ExecutionRuntime(Debug(Chat(base)))
                # ExecutionRuntime's OTel span wraps the entire session.
                execution_runtime = UiPathExecutionRuntime(
                    delegate=runtime,
                    trace_manager=self.trace_manager,
                    log_handler=log_handler,
                    execution_id=run.id,
                )

                result: UiPathRuntimeResult | None = None
                async for event in execution_runtime.stream(
                    execution_input,
                    options=cast(UiPathStreamOptions, execution_options),
                ):
                    if isinstance(event, UiPathRuntimeResult):
                        result = event
                    # Message events are handled by the chat bridge's
                    # on_message callback — don't broadcast again here.
            else:
                execution_runtime = UiPathExecutionRuntime(
                    delegate=runtime,
                    trace_manager=self.trace_manager,
                    log_handler=log_handler,
                    execution_id=run.id,
                )
                result = await execution_runtime.execute(
                    execution_input, execution_options
                )

            if result is not None:
                if (
                    result.status == UiPathRuntimeStatus.SUSPENDED.value
                    and result.trigger
                ):
                    run.status = "suspended"
                elif result.status == UiPathRuntimeStatus.FAULTED.value:
                    run.status = "failed"
                    if isinstance(result.error, UiPathErrorContract):
                        run.error = result.error
                    else:
                        run.error = UiPathErrorContract(
                            code="Unknown",
                            title=str(result.error)
                            if result.error
                            else "Unknown error",
                            detail="",
                        )
                    err = run.error
                    error_state = StateData(
                        run_id=run.id,
                        node_name="__error__",
                        payload={
                            "status": "failed",
                            "code": err.code,
                            "title": err.title,
                            "detail": err.detail,
                            "category": err.category.value
                            if hasattr(err.category, "value")
                            else str(err.category),
                        },
                    )
                    run.states.append(error_state)
                    if self.on_state is not None:
                        self.on_state(error_state)
                else:
                    run.status = "completed"

                if result.output is None:
                    run.output_data = {}
                elif isinstance(result.output, BaseModel):
                    run.output_data = result.output.model_dump()
                elif isinstance(result.output, (dict, list, str, int, float, bool)):
                    run.output_data = result.output
                else:
                    run.output_data = {"result": str(result.output)}

                if run.output_data:
                    self._add_info_log(run, f"Execution result: {run.output_data}")

            if run.status == "failed":
                failed_err = run.error
                detail = (
                    f"{failed_err.title}: {failed_err.detail}"
                    if failed_err
                    else "Unknown error"
                )
                self._add_error_log(run, detail)
            else:
                self._add_info_log(run, "✅ Execution completed successfully")
            run.end_time = datetime.now(timezone.utc)

        except UiPathBaseRuntimeError as e:
            self._add_error_log(run)
            run.status = "failed"
            run.end_time = datetime.now(timezone.utc)
            run.error = e.error_info

        except Exception as e:
            self._add_error_log(run)
            run.status = "failed"
            run.end_time = datetime.now(timezone.utc)
            run.error = UiPathErrorContract(
                code="Unknown",
                title=str(e),
                detail=traceback.format_exc(),
            )
        finally:
            if new_runtime is not None:
                await new_runtime.dispose()

        self.runs[run.id] = run
        self._emit_run_updated(run)

        if run.id in self.debug_bridges:
            del self.debug_bridges[run.id]
        if run.id in self.chat_bridges:
            del self.chat_bridges[run.id]

    async def resume_debug(self, run: ExecutionRun, resume_data: Any) -> None:
        """Resume debug execution from a breakpoint."""
        debug_bridge = self.debug_bridges.get(run.id)
        if debug_bridge:
            run.status = "running"
            self._emit_run_updated(run)
            debug_bridge.resume(resume_data)

    def step_debug(self, run: ExecutionRun) -> None:
        """Step to next breakpoint in debug mode."""
        debug_bridge = self.debug_bridges.get(run.id)
        if debug_bridge:
            # Step mode = break on all nodes
            debug_bridge.set_breakpoints("*")
            # Resume execution (will pause at next node)
            run.breakpoint_node = None
            run.breakpoint_next_nodes = []
            run.status = "running"
            self._emit_run_updated(run)
            debug_bridge.resume(resume_data={})

    def continue_debug(self, run: ExecutionRun) -> None:
        """Continue execution, stopping at user-set breakpoints if any."""
        debug_bridge = self.debug_bridges.get(run.id)
        if debug_bridge:
            # Restore user breakpoints (empty list = run to completion)
            debug_bridge.set_breakpoints(run.breakpoints)
            # Resume execution
            run.breakpoint_node = None
            run.breakpoint_next_nodes = []
            run.status = "running"
            self._emit_run_updated(run)
            debug_bridge.resume(resume_data={})

    def set_breakpoints(self, run: ExecutionRun, breakpoints: list[str]) -> None:
        """Update breakpoints for a run and apply to active debug bridge."""
        run.breakpoints = breakpoints
        debug_bridge = self.debug_bridges.get(run.id)
        if debug_bridge:
            debug_bridge.set_breakpoints(breakpoints)

    def stop_debug(self, run: ExecutionRun) -> None:
        """Stop debug execution."""
        debug_bridge = self.debug_bridges.get(run.id)
        if debug_bridge:
            debug_bridge.quit()

    def handle_log(self, log_data: LogData) -> None:
        """Entry point for all logs (runtime, traces, stderr)."""
        run = self.runs.get(log_data.run_id)
        if run is not None:
            run.logs.append(log_data)

        if self.on_log is not None:
            self.on_log(log_data)

    def handle_trace(self, trace_data: TraceData) -> None:
        """Entry point for traces (from RunContextExporter)."""
        run = self.runs.get(trace_data.run_id)
        if run is not None:
            # Update or append trace
            for i, existing_trace in enumerate(run.traces):
                if existing_trace.span_id == trace_data.span_id:
                    run.traces[i] = trace_data
                    break
            else:
                run.traces.append(trace_data)

        if self.on_trace is not None:
            self.on_trace(trace_data)

    def get_chat_bridge(self, run_id: str) -> WebChatBridge | None:
        """Get the chat bridge for a run."""
        return self.chat_bridges.get(run_id)

    def confirm_tool_call(
        self, run_id: str, approved: bool, input: Any | None = None
    ) -> None:
        """Deliver a tool call confirmation to a chat-mode run.

        Forwarded as ``UiPathConversationToolCallConfirmationEvent`` to the
        ``WebChatBridge``, which unblocks the runtime's ``wait_for_resume``.
        """
        chat_bridge = self.chat_bridges.get(run_id)
        if chat_bridge is None:
            return
        chat_bridge.set_tool_confirmation(
            UiPathConversationToolCallConfirmationEvent(approved=approved, input=input)
        )

    def get_debug_bridge(self, run_id: str) -> DebugBridgeProtocol | None:
        """Get the debug bridge for a run."""
        return self.debug_bridges.get(run_id)

    def _handle_chat_message_event(
        self, run: ExecutionRun, event: UiPathConversationMessageEvent
    ) -> None:
        """Handle a chat message event from the chat bridge."""
        if self.on_chat is not None:
            chat_data = ChatData(
                event=event,
                message=run.add_event(event),
                run_id=run.id,
            )
            self.on_chat(chat_data)

    def _handle_state_update(self, run_id: str, state: UiPathRuntimeStateEvent) -> None:
        """Handle state update from debug runtime."""
        run = self.runs.get(run_id)
        if run and state.node_name:
            state_data = StateData(
                run_id=run_id,
                node_name=state.node_name,
                qualified_node_name=state.qualified_node_name,
                phase=state.phase.value if state.phase else None,
                payload=state.payload if state.payload else None,
            )
            run.states.append(state_data)
            if self.on_state is not None:
                self.on_state(state_data)

    def _handle_debug_started(self, run_id: str) -> None:
        """Handle debug started event."""
        run = self.runs.get(run_id)
        if run and run.mode == ExecutionMode.DEBUG:
            run.status = "suspended"
            self._emit_run_updated(run)

    def _handle_breakpoint_hit(self, run_id: str, bp: UiPathBreakpointResult) -> None:
        """Handle breakpoint hit from debug runtime."""
        run = self.runs.get(run_id)
        if run:
            run.breakpoint_node = bp.breakpoint_node
            run.breakpoint_next_nodes = bp.next_nodes if bp.next_nodes else []
            run.status = "suspended"
            self._emit_run_updated(run)

    def _emit_run_updated(self, run: ExecutionRun) -> None:
        """Notify observers that a run's state changed."""
        self.runs[run.id] = run
        if self.on_run_updated is not None:
            self.on_run_updated(run)

    def _add_info_log(self, run: ExecutionRun, message: str) -> None:
        log_data = LogData(
            run_id=run.id,
            level="INFO",
            message=message,
            timestamp=datetime.now(timezone.utc),
        )
        self.handle_log(log_data)

    def _add_error_log(self, run: ExecutionRun, error: str | None = None) -> None:
        if error is None:
            # Serialize traceback to plain text for the data class
            import io

            from rich.console import Console
            from rich.traceback import Traceback

            tb = Traceback(show_locals=False, max_frames=4)
            str_io = io.StringIO()
            console = Console(file=str_io, width=120, no_color=True)
            console.print(tb)
            error_text = str_io.getvalue()

            log_data = LogData(
                run_id=run.id,
                level="ERROR",
                message=error_text,
                timestamp=datetime.now(timezone.utc),
            )
        else:
            log_data = LogData(
                run_id=run.id,
                level="ERROR",
                message=error,
                timestamp=datetime.now(timezone.utc),
            )
        self.handle_log(log_data)
