"""Debug bridge implementation for the web server."""

import asyncio
import logging
from typing import Any, Callable, Literal

from uipath.runtime.debug import UiPathBreakpointResult, UiPathDebugQuitError
from uipath.runtime.events import UiPathRuntimeStateEvent
from uipath.runtime.result import UiPathRuntimeResult
from uipath.runtime.resumable import UiPathResumeTriggerType

from uipath.dev.models.execution import ExecutionMode

logger = logging.getLogger(__name__)


class WebDebugBridge:
    """Bridge between the web server and UiPathDebugRuntime.

    In RUN mode: no breakpoints, auto-resumes the initial debug pause.
    In DEBUG mode: same step-mode behavior as TextualDebugBridge.
    """

    def __init__(self, mode: ExecutionMode = ExecutionMode.RUN):
        """Initialize the web debug bridge."""
        self._mode = mode
        self._should_wait = False
        self._resume_event = asyncio.Event()
        self._resume_data: dict[str, Any] | None = None
        self._terminate_event = asyncio.Event()
        self._breakpoints: list[str] | Literal["*"] = []

        # Callbacks (wired by RunService)
        self.on_execution_started: Callable[[], None] | None = None
        self.on_state_update: Callable[[UiPathRuntimeStateEvent], None] | None = None
        self.on_breakpoint_hit: Callable[[UiPathBreakpointResult], None] | None = None
        self.on_execution_completed: Callable[[UiPathRuntimeResult], None] | None = None
        self.on_execution_error: Callable[[str], None] | None = None

    # ------------------------------------------------------------------
    # UiPathDebugProtocol implementation
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish connection to debugger."""
        logger.debug("WebDebugBridge connected (mode=%s)", self._mode)

    async def disconnect(self) -> None:
        """Close connection to debugger."""
        self._resume_event.set()
        self._terminate_event.set()
        logger.debug("WebDebugBridge disconnected")

    async def emit_execution_started(self, **kwargs: Any) -> None:
        """Notify debugger that execution started."""
        logger.debug("Execution started")
        if self.on_execution_started:
            self.on_execution_started()

    async def emit_state_update(self, state_event: UiPathRuntimeStateEvent) -> None:
        """Notify debugger of runtime state update."""
        logger.debug("State update: %s", state_event.node_name)
        if self.on_state_update:
            self.on_state_update(state_event)

    async def emit_breakpoint_hit(
        self, breakpoint_result: UiPathBreakpointResult
    ) -> None:
        """Notify debugger that a breakpoint was hit."""
        logger.debug("Breakpoint hit: %s", breakpoint_result)
        self._should_wait = True
        if self.on_breakpoint_hit:
            self.on_breakpoint_hit(breakpoint_result)

    async def emit_execution_suspended(
        self, runtime_result: UiPathRuntimeResult
    ) -> None:
        """Notify debugger that execution is suspended."""
        logger.debug("Execution suspended")
        if runtime_result.trigger is None:
            return

        if runtime_result.trigger.trigger_type == UiPathResumeTriggerType.API:
            self._should_wait = True
            if self.on_breakpoint_hit:
                self.on_breakpoint_hit(
                    UiPathBreakpointResult(
                        breakpoint_node="<suspended>",
                        breakpoint_type="before",
                        current_state=runtime_result.output,
                        next_nodes=[],
                    )
                )

    async def emit_execution_resumed(self, resume_data: Any) -> None:
        """Notify debugger that execution resumed."""
        logger.debug("Execution resumed")

    async def emit_execution_completed(
        self, runtime_result: UiPathRuntimeResult
    ) -> None:
        """Notify debugger that execution completed."""
        logger.debug("Execution completed")
        if self.on_execution_completed:
            self.on_execution_completed(runtime_result)

    async def emit_execution_error(self, error: str) -> None:
        """Notify debugger that an error occurred."""
        logger.error("Execution error: %s", error)
        if self.on_execution_error:
            self.on_execution_error(error)

    async def wait_for_resume(self) -> Any:
        """Wait for resume command from debugger."""
        if not self._should_wait:
            return {}

        self._should_wait = False
        self._resume_event.clear()
        await self._resume_event.wait()

        if self._terminate_event.is_set():
            raise UiPathDebugQuitError("Debug session quit requested")

        return self._resume_data

    async def wait_for_terminate(self) -> None:
        """Wait for terminate command from debugger."""
        await self._terminate_event.wait()

    def get_breakpoints(self) -> list[str] | Literal["*"]:
        """Get nodes to suspend execution at."""
        return self._breakpoints

    # ------------------------------------------------------------------
    # Control methods (called from RunService / WS handler)
    # ------------------------------------------------------------------

    def resume(self, resume_data: Any) -> None:
        """Signal that execution should resume."""
        self._resume_data = resume_data or {}
        self._resume_event.set()

    def quit(self) -> None:
        """Signal that execution should quit."""
        self._terminate_event.set()
        self._resume_event.set()

    def set_breakpoints(self, breakpoints: list[str] | Literal["*"]) -> None:
        """Set breakpoints."""
        self._breakpoints = breakpoints
