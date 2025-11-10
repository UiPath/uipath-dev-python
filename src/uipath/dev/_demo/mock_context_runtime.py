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

ENTRYPOINT_CONTEXT = "agent/context.py:run"

logger = logging.getLogger(__name__)


class MockContextRuntime:
    """A mock runtime that simulates a multi-step workflow with rich telemetry."""

    def __init__(self, entrypoint: str = ENTRYPOINT_CONTEXT) -> None:
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.context")

    async def get_schema(self) -> UiPathRuntimeSchema:
        return UiPathRuntimeSchema(
            filePath=self.entrypoint,
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

        entrypoint = "mock-entrypoint"
        message = str(payload.get("message", ""))
        message_length = len(message)

        with self.tracer.start_as_current_span(
            "mock-runtime.execute",
            attributes={
                "uipath.runtime.name": "MockRuntime",
                "uipath.runtime.type": "agent",
                "uipath.runtime.entrypoint": entrypoint,
                "uipath.input.message.length": message_length,
                "uipath.input.has_message": "message" in payload,
            },
        ) as root_span:
            logger.info(
                "MockRuntime: starting execution",
                extra={
                    "uipath.runtime.entrypoint": entrypoint,
                },
            )
            print(f"[MockRuntime] Starting execution with payload={payload!r}")

            # Stage 1: Initialization
            with self.tracer.start_as_current_span(
                "initialize.environment",
                attributes={
                    "uipath.step.name": "initialize-environment",
                    "uipath.step.kind": "init",
                },
            ):
                logger.info("MockRuntime: initializing environment")
                print("[MockRuntime] Initializing environment...")
                await asyncio.sleep(0.5)

            # Stage 2: Validation
            with self.tracer.start_as_current_span(
                "validate.input",
                attributes={
                    "uipath.step.name": "validate-input",
                    "uipath.step.kind": "validation",
                    "uipath.input.has_message": "message" in payload,
                },
            ) as validate_span:
                logger.info("MockRuntime: validating input")
                print("[MockRuntime] Validating input...")
                await asyncio.sleep(0.5)

                if "message" not in payload:
                    logger.warning("MockRuntime: missing 'message' in payload")
                    validate_span.set_attribute(
                        "uipath.validation.missing_field", "message"
                    )

            # Stage 3: Preprocessing
            with self.tracer.start_as_current_span(
                "preprocess.data",
                attributes={
                    "uipath.step.name": "preprocess-data",
                    "uipath.step.kind": "preprocess",
                    "uipath.input.size.bytes": len(str(payload).encode("utf-8")),
                },
            ):
                logger.info("MockRuntime: preprocessing data")
                print("[MockRuntime] Preprocessing data...")
                await asyncio.sleep(0.5)

            # Stage 4: Compute / reasoning
            with self.tracer.start_as_current_span(
                "compute.result",
                attributes={
                    "uipath.step.name": "compute-result",
                    "uipath.step.kind": "compute",
                },
            ):
                logger.info("MockRuntime: compute phase started")
                print("[MockRuntime] Compute phase...")

                # Subtask: embedding computation
                with self.tracer.start_as_current_span(
                    "compute.embeddings",
                    attributes={
                        "uipath.step.name": "compute-embeddings",
                        "uipath.step.kind": "compute-subtask",
                    },
                ):
                    logger.info("MockRuntime: computing embeddings")
                    print("[MockRuntime] Computing embeddings...")
                    await asyncio.sleep(0.5)

                # Subtask: KB query
                with self.tracer.start_as_current_span(
                    "query.knowledgebase",
                    attributes={
                        "uipath.step.name": "query-knowledgebase",
                        "uipath.step.kind": "io",
                        "uipath.kb.query.length": message_length,
                    },
                ):
                    logger.info("MockRuntime: querying knowledge base")
                    print("[MockRuntime] Querying knowledge base...")
                    await asyncio.sleep(0.5)

            # Stage 5: Post-processing
            with self.tracer.start_as_current_span(
                "postprocess.results",
                attributes={
                    "uipath.step.name": "postprocess-results",
                    "uipath.step.kind": "postprocess",
                },
            ):
                logger.info("MockRuntime: post-processing results")
                print("[MockRuntime] Post-processing results...")
                await asyncio.sleep(0.4)

                with self.tracer.start_as_current_span(
                    "generate.output",
                    attributes={
                        "uipath.step.name": "generate-output",
                        "uipath.step.kind": "postprocess-subtask",
                    },
                ):
                    logger.info("MockRuntime: generating structured output")
                    print("[MockRuntime] Generating output...")
                    await asyncio.sleep(0.4)

            # Stage 6: Persistence
            with self.tracer.start_as_current_span(
                "persist.artifacts",
                attributes={
                    "uipath.step.name": "persist-artifacts",
                    "uipath.step.kind": "io",
                    "uipath.persistence.enabled": False,
                },
            ):
                logger.info("MockRuntime: persisting artifacts (mock)")
                print("[MockRuntime] Persisting artifacts (mock)...")
                await asyncio.sleep(0.4)

            # Stage 7: Cleanup
            with self.tracer.start_as_current_span(
                "cleanup.resources",
                attributes={
                    "uipath.step.name": "cleanup-resources",
                    "uipath.step.kind": "cleanup",
                },
            ):
                logger.info("MockRuntime: cleaning up resources")
                print("[MockRuntime] Cleaning up resources...")
                await asyncio.sleep(0.3)

            result_payload = {
                "result": f"Mock runtime processed: {payload.get('message', '<no message>')}",
                "metadata": {
                    "entrypoint": entrypoint,
                    "message_length": message_length,
                },
            }

            root_span.set_attribute("uipath.runtime.status", "success")
            root_span.set_attribute("uipath.runtime.duration.approx", "5s")
            root_span.set_attribute("uipath.output.has_error", False)
            root_span.set_attribute(
                "uipath.output.message_length", len(str(result_payload))
            )

            logger.info(
                "MockRuntime: execution completed successfully",
                extra={
                    "uipath.runtime.status": "success",
                },
            )
            print(f"[MockRuntime] Finished successfully with result={result_payload!r}")

        return UiPathRuntimeResult(
            output=result_payload,
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: Optional[dict[str, Any]] = None,
        options: Optional[UiPathStreamOptions] = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        logger.info("MockRuntime: stream() invoked")
        print("[MockRuntime] stream() invoked")
        yield await self.execute(input=input, options=options)

    async def dispose(self) -> None:
        logger.info("MockRuntime: dispose() invoked")
        print("[MockRuntime] dispose() invoked")
