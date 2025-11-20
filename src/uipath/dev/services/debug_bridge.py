"""Debug bridge implementation for Textual UI."""

import asyncio
import logging
from typing import Any, Callable, Literal, Optional

from uipath.runtime.debug import UiPathBreakpointResult, UiPathDebugQuitError
from uipath.runtime.events import UiPathRuntimeStateEvent
from uipath.runtime.result import UiPathRuntimeResult

logger = logging.getLogger(__name__)


class TextualDebugBridge:
    """Bridge between Textual UI and UiPathDebugRuntime."""

    def __init__(self):
        """Initialize the debug bridge."""
        self._connected = False
        self._resume_event = asyncio.Event()
        self._quit_requested = False
        self._breakpoints: list[str] | Literal["*"] = "*"  # Default: step mode

        # Callbacks to UI
        self.on_execution_started: Optional[Callable[[], None]] = None
        self.on_state_update: Optional[Callable[[UiPathRuntimeStateEvent], None]] = None
        self.on_breakpoint_hit: Optional[Callable[[UiPathBreakpointResult], None]] = (
            None
        )
        self.on_execution_completed: Optional[Callable[[UiPathRuntimeResult], None]] = (
            None
        )
        self.on_execution_error: Optional[Callable[[str], None]] = None

    async def connect(self) -> None:
        """Establish connection to debugger."""
        self._connected = True
        self._quit_requested = False
        logger.debug("Debug bridge connected")

    async def disconnect(self) -> None:
        """Close connection to debugger."""
        self._connected = False
        self._resume_event.set()  # Unblock any waiting tasks
        logger.debug("Debug bridge disconnected")

    async def emit_execution_started(self, **kwargs: Any) -> None:
        """Notify debugger that execution started."""
        logger.debug("Execution started")
        if self.on_execution_started:
            self.on_execution_started()

    async def emit_state_update(self, state_event: UiPathRuntimeStateEvent) -> None:
        """Notify debugger of runtime state update."""
        logger.debug(f"State update: {state_event.node_name}")
        if self.on_state_update:
            self.on_state_update(state_event)

    async def emit_breakpoint_hit(
        self, breakpoint_result: UiPathBreakpointResult
    ) -> None:
        """Notify debugger that a breakpoint was hit."""
        logger.debug(f"Breakpoint hit: {breakpoint_result}")
        if self.on_breakpoint_hit:
            self.on_breakpoint_hit(breakpoint_result)

    async def emit_execution_completed(
        self, runtime_result: UiPathRuntimeResult
    ) -> None:
        """Notify debugger that execution completed."""
        logger.debug("Execution completed")
        if self.on_execution_completed:
            self.on_execution_completed(runtime_result)

    async def emit_execution_error(self, error: str) -> None:
        """Notify debugger that an error occurred."""
        logger.error(f"Execution error: {error}")
        if self.on_execution_error:
            self.on_execution_error(error)

    async def wait_for_resume(self) -> Any:
        """Wait for resume command from debugger.

        Raises:
            UiPathDebugQuitError: If quit was requested
        """
        self._resume_event.clear()
        await self._resume_event.wait()

        if self._quit_requested:
            raise UiPathDebugQuitError("Debug session quit requested")

    def resume(self) -> None:
        """Signal that execution should resume (called from UI buttons)."""
        self._resume_event.set()

    def quit(self) -> None:
        """Signal that execution should quit (called from UI stop button)."""
        self._quit_requested = True
        self._resume_event.set()

    def get_breakpoints(self) -> list[str] | Literal["*"]:
        """Get nodes to suspend execution at."""
        return self._breakpoints

    def set_breakpoints(self, breakpoints: list[str] | Literal["*"]) -> None:
        """Set breakpoints (called from UI)."""
        self._breakpoints = breakpoints
