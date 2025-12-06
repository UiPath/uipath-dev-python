"""An example mock runtime that analyzes numbers."""

import asyncio
import logging
from typing import Any, AsyncGenerator

from opentelemetry import trace
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.schema import UiPathRuntimeSchema

ENTRYPOINT_ANALYZE_NUMBERS = "agent/numbers.py:analyze"

logger = logging.getLogger(__name__)


class MockNumberAnalyticsRuntime:
    """Mock runtime that analyzes a list of numbers."""

    def __init__(self, entrypoint: str = ENTRYPOINT_ANALYZE_NUMBERS) -> None:
        """Initialize the MockNumberAnalyticsRuntime."""
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.number-analytics")

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Get the schema for the number analytics runtime."""
        return UiPathRuntimeSchema(
            filePath=self.entrypoint,
            uniqueId="mock-number-analytics-runtime",
            type="script",
            input={
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "List of numeric values to analyze",
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
                "required": ["operation", "result"],
            },
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Execute the number analytics runtime."""
        payload = input or {}
        numbers = payload.get("numbers") or []
        operation = str(payload.get("operation", "sum")).lower()

        numbers = [float(x) for x in numbers]

        with self.tracer.start_as_current_span(
            "number_analytics.execute",
            attributes={
                "uipath.runtime.name": "NumberAnalyticsRuntime",
                "uipath.runtime.entrypoint": self.entrypoint,
                "uipath.input.count": len(numbers),
                "uipath.input.operation": operation,
            },
        ):
            logger.info("NumberAnalyticsRuntime: starting execution")

            # Validation span
            with self.tracer.start_as_current_span(
                "number_analytics.validate_input",
                attributes={"uipath.step.kind": "validation"},
            ):
                await asyncio.sleep(0.05)
                if not numbers:
                    logger.warning("NumberAnalyticsRuntime: empty 'numbers' list")
                    result_payload = {
                        "operation": operation,
                        "result": 0,
                        "count": 0,
                    }
                    return UiPathRuntimeResult(
                        output=result_payload,
                        status=UiPathRuntimeStatus.SUCCESSFUL,
                    )

            # Compute span
            with self.tracer.start_as_current_span(
                "number_analytics.compute",
                attributes={"uipath.step.kind": "compute"},
            ):
                await asyncio.sleep(0.1)
                if operation == "avg":
                    result = sum(numbers) / len(numbers)
                elif operation == "max":
                    result = max(numbers)
                else:
                    operation = "sum"
                    result = sum(numbers)

            # Postprocess span
            with self.tracer.start_as_current_span(
                "number_analytics.postprocess",
                attributes={"uipath.step.kind": "postprocess"},
            ):
                await asyncio.sleep(0.05)
                result_payload = {
                    "operation": operation,
                    "result": result,
                    "count": len(numbers),
                }

            logger.info(
                "NumberAnalyticsRuntime: execution completed",
                extra={"operation": operation, "result": result},
            )

        return UiPathRuntimeResult(
            output=result_payload,
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Stream events from the number analytics runtime."""
        logger.info("NumberAnalyticsRuntime: stream() invoked")
        yield await self.execute(input=input, options=options)

    async def dispose(self) -> None:
        """Dispose of any resources used by the number analytics runtime."""
        logger.info("NumberAnalyticsRuntime: dispose() invoked")
