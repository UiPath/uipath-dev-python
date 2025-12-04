"""UiPath Developer Console run service module."""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from typing import Any, Callable, cast

from pydantic import BaseModel
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
from uipath.runtime.debug import UiPathDebugRuntime
from uipath.runtime.errors import UiPathErrorContract, UiPathRuntimeError
from uipath.runtime.events import UiPathRuntimeMessageEvent, UiPathRuntimeStateEvent

from uipath.dev.infrastructure import RunContextExporter, RunContextLogHandler
from uipath.dev.models import (
    ChatMessage,
    ExecutionMode,
    ExecutionRun,
    LogMessage,
    TraceMessage,
)
from uipath.dev.services.debug_bridge import TextualDebugBridge

RunUpdatedCallback = Callable[[ExecutionRun], None]
LogCallback = Callable[[LogMessage], None]
TraceCallback = Callable[[TraceMessage], None]
ChatCallback = Callable[[ChatMessage], None]


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
    ) -> None:
        """Initialize RunService with runtime factory and trace manager."""
        self.runtime_factory = runtime_factory
        self.trace_manager = trace_manager
        self.runs: dict[str, ExecutionRun] = {}

        self.on_run_updated = on_run_updated
        self.on_log = on_log
        self.on_trace = on_trace
        self.on_chat = on_chat

        self.trace_manager.add_span_exporter(
            RunContextExporter(
                on_trace=self.handle_trace,
                on_log=self.handle_log,
            ),
            batch=False,
        )

        self.debug_bridges: dict[str, TextualDebugBridge] = {}

    def register_run(self, run: ExecutionRun) -> None:
        """Register a new run and emit an initial update."""
        self.runs[run.id] = run
        self._emit_run_updated(run)

    def get_run(self, run_id: str) -> ExecutionRun | None:
        """Get a registered run."""
        return self.runs.get(run_id)

    async def execute(self, run: ExecutionRun) -> None:
        """Execute or resume a run."""
        new_runtime: UiPathRuntimeProtocol | None = None
        try:
            execution_input: dict[str, Any] | str | None = {}
            execution_options: UiPathExecuteOptions = UiPathExecuteOptions()

            if run.status == "suspended":
                execution_input = run.resume_data
                execution_options.resume = True
                self._add_info_log(run, f"Resuming execution: {run.entrypoint}")
            else:
                execution_input = run.input_data
                self._add_info_log(run, f"Starting execution: {run.entrypoint}")

            run.status = "running"
            run.start_time = datetime.now()
            self._emit_run_updated(run)

            log_handler = RunContextLogHandler(
                run_id=run.id,
                callback=self.handle_log,
            )

            new_runtime = await self.runtime_factory.new_runtime(
                entrypoint=run.entrypoint,
                runtime_id=run.id,
            )

            runtime: UiPathRuntimeProtocol

            if run.mode == ExecutionMode.DEBUG:
                debug_bridge = TextualDebugBridge()

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

                self.debug_bridges[run.id] = debug_bridge

                runtime = UiPathDebugRuntime(
                    delegate=new_runtime,
                    debug_bridge=debug_bridge,
                )
            else:
                runtime = new_runtime

            execution_runtime = UiPathExecutionRuntime(
                delegate=runtime,
                trace_manager=self.trace_manager,
                log_handler=log_handler,
                execution_id=run.id,
            )

            if run.mode == ExecutionMode.CHAT:
                result: UiPathRuntimeResult | None = None
                async for event in execution_runtime.stream(
                    execution_input,
                    options=cast(UiPathStreamOptions, execution_options),
                ):
                    if isinstance(event, UiPathRuntimeResult):
                        result = event
                    elif isinstance(event, UiPathRuntimeMessageEvent):
                        if self.on_chat is not None:
                            chat_msg = ChatMessage(
                                event=event.payload,
                                message=run.add_event(event.payload),
                                run_id=run.id,
                            )
                            self.on_chat(chat_msg)
            else:
                result = await execution_runtime.execute(
                    execution_input, execution_options
                )

            if result is not None:
                if (
                    result.status == UiPathRuntimeStatus.SUSPENDED.value
                    and result.trigger
                ):
                    run.status = "suspended"
                else:
                    run.status = "completed"

                if result.output is None:
                    run.output_data = {}
                elif isinstance(result.output, BaseModel):
                    run.output_data = result.output.model_dump()
                else:
                    run.output_data = result.output

                if run.output_data:
                    self._add_info_log(run, f"Execution result: {run.output_data}")

            self._add_info_log(run, "✅ Execution completed successfully")
            run.end_time = datetime.now()

        except UiPathRuntimeError as e:
            self._add_error_log(run)
            run.status = "failed"
            run.end_time = datetime.now()
            run.error = e.error_info

        except Exception as e:
            self._add_error_log(run)
            run.status = "failed"
            run.end_time = datetime.now()
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
            run.status = "running"
            self._emit_run_updated(run)
            debug_bridge.resume(resume_data={})

    def continue_debug(self, run: ExecutionRun) -> None:
        """Continue execution without stopping at breakpoints."""
        debug_bridge = self.debug_bridges.get(run.id)
        if debug_bridge:
            # Clear breakpoints = run to completion
            debug_bridge.set_breakpoints([])
            # Resume execution
            run.status = "running"
            self._emit_run_updated(run)
            debug_bridge.resume(resume_data={})

    def stop_debug(self, run: ExecutionRun) -> None:
        """Stop debug execution."""
        debug_bridge = self.debug_bridges.get(run.id)
        if debug_bridge:
            debug_bridge.quit()

    def handle_log(self, log_msg: LogMessage) -> None:
        """Entry point for all logs (runtime, traces, stderr)."""
        run = self.runs.get(log_msg.run_id)
        if run is not None:
            run.logs.append(log_msg)
            self._emit_run_updated(run)

        if self.on_log is not None:
            self.on_log(log_msg)

    def handle_trace(self, trace_msg: TraceMessage) -> None:
        """Entry point for traces (from RunContextExporter)."""
        run = self.runs.get(trace_msg.run_id)
        if run is not None:
            # Update or append trace
            for i, existing_trace in enumerate(run.traces):
                if existing_trace.span_id == trace_msg.span_id:
                    run.traces[i] = trace_msg
                    break
            else:
                run.traces.append(trace_msg)

            self._emit_run_updated(run)

        if self.on_trace is not None:
            self.on_trace(trace_msg)

    def get_debug_bridge(self, run_id: str) -> TextualDebugBridge | None:
        """Get the debug bridge for a run."""
        return self.debug_bridges.get(run_id)

    def _handle_state_update(self, run_id: str, state: UiPathRuntimeStateEvent) -> None:
        """Handle state update from debug runtime."""
        run = self.runs.get(run_id)
        if run:
            self._add_info_log(run, json.dumps(state.payload))

    def _handle_debug_started(self, run_id: str) -> None:
        """Handle debug started event."""
        run = self.runs.get(run_id)
        if run:
            run.status = "suspended"
            self._emit_run_updated(run)

    def _handle_breakpoint_hit(self, run_id: str, bp) -> None:
        """Handle breakpoint hit from debug runtime."""
        run = self.runs.get(run_id)
        if run:
            run.status = "suspended"
            self._emit_run_updated(run)

    def _emit_run_updated(self, run: ExecutionRun) -> None:
        """Notify observers that a run's state changed."""
        self.runs[run.id] = run
        if self.on_run_updated is not None:
            self.on_run_updated(run)

    def _add_info_log(self, run: ExecutionRun, message: str) -> None:
        log_msg = LogMessage(
            run_id=run.id,
            level="INFO",
            message=message,
            timestamp=datetime.now(),
        )
        self.handle_log(log_msg)

    def _add_error_log(self, run: ExecutionRun, error: str | None = None) -> None:
        if error is None:
            from rich.traceback import Traceback

            tb = Traceback(
                show_locals=False,
                max_frames=4,
            )
            log_msg = LogMessage(
                run_id=run.id,
                level="ERROR",
                message=tb,
                timestamp=datetime.now(),
            )
        else:
            log_msg = LogMessage(
                run_id=run.id,
                level="ERROR",
                message=error,
                timestamp=datetime.now(),
            )
        self.handle_log(log_msg)
