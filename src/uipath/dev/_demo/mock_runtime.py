"""Minimal demo script to run UiPathDevTerminal with mock runtimes."""

import asyncio
from typing import Any, Optional

from uipath.runtime import (
    UiPathBaseRuntime,
    UiPathExecuteOptions,
    UiPathRuntimeFactory,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from uipath.runtime.schema import UiPathRuntimeSchema


class MockRuntime(UiPathBaseRuntime):
    """A simple mock runtime that echoes its input."""

    async def get_schema(self) -> UiPathRuntimeSchema:
        return UiPathRuntimeSchema(
            filePath="default",
            uniqueId="mock-runtime",
            type="agent",
            input={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            output={
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
        )

    async def execute(
        self,
        input: Optional[dict[str, Any]] = None,
        options: Optional[UiPathExecuteOptions] = None,
    ) -> UiPathRuntimeResult:
        payload = input or {}
        # Simulate some async work
        await asyncio.sleep(0.2)
        return UiPathRuntimeResult(
            output={"result": f"Mock runtime got: {payload!r}"},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def cleanup(self) -> None:
        # Nothing to clean up in this mock
        pass


# 2) Mock runtime factory
class MockRuntimeFactory(UiPathRuntimeFactory[MockRuntime]):
    """Runtime factory compatible with UiPathDevTerminal expectations."""

    # This is the method the Textual app calls here:
    #   runtime = self.runtime_factory.new_runtime(entrypoint=run.entrypoint)
    def new_runtime(self, entrypoint: str) -> MockRuntime:
        return MockRuntime()

    def discover_runtimes(self) -> list[MockRuntime]:
        return []
