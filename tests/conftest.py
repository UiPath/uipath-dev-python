"""Shared pytest fixtures for all tests."""

import asyncio
from typing import Any, AsyncGenerator

import pytest
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeFactorySettings,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathRuntimeStorageProtocol,
    UiPathStreamOptions,
)
from uipath.runtime.schema import UiPathRuntimeSchema

ENTRYPOINT_GREETING = "agent/greeting.py:main"
ENTRYPOINT_NUMBERS = "agent/numbers.py:analyze"


class _MockGreetingRuntime:
    """Lightweight greeting runtime for tests (no OTel tracing)."""

    def __init__(self, entrypoint: str = ENTRYPOINT_GREETING) -> None:
        self.entrypoint = entrypoint

    async def get_schema(self) -> UiPathRuntimeSchema:
        return UiPathRuntimeSchema(
            filePath=self.entrypoint,
            uniqueId="test-greeting",
            type="agent",
            input={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            output={
                "type": "object",
                "properties": {"greeting": {"type": "string"}},
            },
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        payload = input or {}
        name = str(payload.get("name", "world"))
        await asyncio.sleep(0.05)
        return UiPathRuntimeResult(
            output={"greeting": f"Hello, {name}!"},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        yield await self.execute(input=input, options=options)

    async def dispose(self) -> None:
        pass


class _MockNumbersRuntime:
    """Lightweight numbers runtime for tests (no OTel tracing)."""

    def __init__(self, entrypoint: str = ENTRYPOINT_NUMBERS) -> None:
        self.entrypoint = entrypoint

    async def get_schema(self) -> UiPathRuntimeSchema:
        return UiPathRuntimeSchema(
            filePath=self.entrypoint,
            uniqueId="test-numbers",
            type="script",
            input={
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["sum", "avg", "max"],
                        "default": "sum",
                    },
                },
                "required": ["numbers"],
            },
            output={
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "result": {"type": "number"},
                    "count": {"type": "integer"},
                },
            },
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        payload = input or {}
        numbers = [float(x) for x in (payload.get("numbers") or [])]
        operation = str(payload.get("operation", "sum")).lower()
        await asyncio.sleep(0.05)

        if operation == "avg" and numbers:
            result = sum(numbers) / len(numbers)
        elif operation == "max" and numbers:
            result = max(numbers)
        else:
            operation = "sum"
            result = sum(numbers)

        return UiPathRuntimeResult(
            output={"operation": operation, "result": result, "count": len(numbers)},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        yield await self.execute(input=input, options=options)

    async def dispose(self) -> None:
        pass


class MockRuntimeFactory:
    """Test runtime factory compatible with UiPathRuntimeFactoryProtocol."""

    async def new_runtime(self, entrypoint: str, runtime_id: str, **kwargs):
        if entrypoint == ENTRYPOINT_NUMBERS:
            return _MockNumbersRuntime(entrypoint=entrypoint)
        return _MockGreetingRuntime(entrypoint=entrypoint)

    async def get_settings(self) -> UiPathRuntimeFactorySettings | None:
        return UiPathRuntimeFactorySettings()

    async def get_storage(self) -> UiPathRuntimeStorageProtocol | None:
        return None

    def discover_entrypoints(self) -> list[str]:
        return [ENTRYPOINT_GREETING, ENTRYPOINT_NUMBERS]

    async def dispose(self) -> None:
        pass


@pytest.fixture()
def mock_factory():
    return MockRuntimeFactory()


@pytest.fixture()
def trace_manager():
    return UiPathTraceManager()
