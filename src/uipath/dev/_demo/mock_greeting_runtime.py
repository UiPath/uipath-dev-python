import asyncio
import logging
from typing import Any, AsyncGenerator, Optional

from opentelemetry import trace
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.schema import UiPathRuntimeSchema

ENTRYPOINT_GREETING = "agent/greeting.py:main"

logger = logging.getLogger(__name__)


class MockGreetingRuntime:
    """Mock runtime that builds a greeting and simulates a small pipeline."""

    def __init__(self, entrypoint: str = ENTRYPOINT_GREETING) -> None:
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.greeting")

    async def get_schema(self) -> UiPathRuntimeSchema:
        return UiPathRuntimeSchema(
            filePath=self.entrypoint,
            uniqueId="mock-greeting-runtime",
            type="agent",
            input={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Who to greet"},
                    "excited": {
                        "type": "boolean",
                        "description": "Whether to use an excited greeting",
                        "default": True,
                    },
                },
                "required": ["name"],
            },
            output={
                "type": "object",
                "properties": {
                    "greeting": {"type": "string"},
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "uppercase": {"type": "boolean"},
                            "length": {"type": "integer"},
                        },
                    },
                },
                "required": ["greeting"],
            },
        )

    async def execute(
        self,
        input: Optional[dict[str, Any]] = None,
        options: Optional[UiPathExecuteOptions] = None,
    ) -> UiPathRuntimeResult:
        payload = input or {}
        name = str(payload.get("name", "world")).strip() or "world"
        excited = bool(payload.get("excited", True))

        with self.tracer.start_as_current_span(
            "greeting.execute",
            attributes={
                "uipath.runtime.name": "GreetingRuntime",
                "uipath.runtime.type": "agent",
                "uipath.runtime.entrypoint": self.entrypoint,
                "uipath.input.name": name,
                "uipath.input.excited": excited,
            },
        ):
            logger.info("GreetingRuntime: starting execution")

            # Stage 1 - normalize name
            with self.tracer.start_as_current_span(
                "greeting.normalize_name",
                attributes={"uipath.step.kind": "preprocess"},
            ):
                await asyncio.sleep(0.1)
                normalized = name.title()

            # Stage 2 - build greeting
            with self.tracer.start_as_current_span(
                "greeting.build_message",
                attributes={"uipath.step.kind": "compute"},
            ):
                await asyncio.sleep(0.1)
                greeting = f"Hello, {normalized}!"
                if excited:
                    greeting += " Excited to meet you!"

            # Stage 3 - compute metadata
            with self.tracer.start_as_current_span(
                "greeting.compute_metadata",
                attributes={"uipath.step.kind": "postprocess"},
            ):
                await asyncio.sleep(0.05)
                metadata = {
                    "uppercase": greeting.isupper(),
                    "length": len(greeting),
                }

            result_payload = {
                "greeting": greeting,
                "metadata": metadata,
            }

            logger.info("GreetingRuntime: execution completed", extra=metadata)

        return UiPathRuntimeResult(
            output=result_payload,
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: Optional[dict[str, Any]] = None,
        options: Optional[UiPathStreamOptions] = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        logger.info("GreetingRuntime: stream() invoked")
        yield await self.execute(input=input, options=options)

    async def dispose(self) -> None:
        logger.info("GreetingRuntime: dispose() invoked")
