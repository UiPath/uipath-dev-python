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

ENTRYPOINT_CONTEXT = "agent/context.py:run"

logger = logging.getLogger(__name__)


class MockContextRuntime:
    """A mock runtime that simulates a multi-step workflow with rich telemetry."""

    def __init__(self, entrypoint: str = ENTRYPOINT_CONTEXT) -> None:
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.context")
        # State tracking for breakpoints
        self.current_step_index: int = 0
        self.steps = [
            ("initialize.environment", "initialize-environment", "init"),
            ("validate.input", "validate-input", "validation"),
            ("preprocess.data", "preprocess-data", "preprocess"),
            ("compute.result", "compute-result", "compute"),
            ("compute.embeddings", "compute-embeddings", "compute-subtask"),
            ("query.knowledgebase", "query-knowledgebase", "io"),
            ("postprocess.results", "postprocess-results", "postprocess"),
            ("generate.output", "generate-output", "postprocess-subtask"),
            ("persist.artifacts", "persist-artifacts", "io"),
            ("cleanup.resources", "cleanup-resources", "cleanup"),
        ]

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
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        from uipath.runtime.debug import UiPathBreakpointResult

        payload = input or {}
        entrypoint = "mock-entrypoint"
        message = str(payload.get("message", ""))
        message_length = len(message)

        # Check breakpoints
        breakpoints = options.breakpoints if options else None
        should_break_all = breakpoints == "*"
        should_break_on = set(breakpoints) if isinstance(breakpoints, list) else set()
        is_resuming = options.resume if options else False

        # If resuming, skip to next step
        if is_resuming:
            self.current_step_index += 1

        # Root span for entire execution
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
            # Execute from current step
            while self.current_step_index < len(self.steps):
                span_name, step_name, step_kind = self.steps[self.current_step_index]

                # Create nested spans based on step
                if step_name == "initialize-environment":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Load config
                        with self.tracer.start_as_current_span(
                            "init.load_config",
                            attributes={"uipath.config.source": "default"},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Setup resources
                        with self.tracer.start_as_current_span(
                            "init.setup_resources",
                            attributes={"uipath.resources.count": 3},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Initialize connections
                        with self.tracer.start_as_current_span(
                            "init.connections",
                            attributes={"uipath.connections.type": "http"},
                        ):
                            await asyncio.sleep(2)

                elif step_name == "validate-input":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Schema validation
                        with self.tracer.start_as_current_span(
                            "validate.schema",
                            attributes={"uipath.schema.valid": True},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Type checking
                        with self.tracer.start_as_current_span(
                            "validate.types",
                            attributes={"uipath.types.checked": 2},
                        ):
                            await asyncio.sleep(2)

                elif step_name == "preprocess-data":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Normalize text
                        with self.tracer.start_as_current_span(
                            "preprocess.normalize",
                            attributes={"uipath.text.normalized": True},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Tokenization
                        with self.tracer.start_as_current_span(
                            "preprocess.tokenize",
                            attributes={"uipath.tokens.count": 42},
                        ):
                            await asyncio.sleep(2)

                elif step_name == "compute-result":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Feature extraction
                        with self.tracer.start_as_current_span(
                            "compute.extract_features",
                            attributes={"uipath.features.count": 128},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Model inference
                        with self.tracer.start_as_current_span(
                            "compute.inference",
                            attributes={
                                "uipath.model.name": "mock-model-v1",
                                "uipath.inference.batch_size": 1,
                            },
                        ):
                            # Deeply nested: Load weights
                            with self.tracer.start_as_current_span(
                                "inference.load_weights",
                                attributes={"uipath.weights.size_mb": 150},
                            ):
                                await asyncio.sleep(2)

                            # Deeply nested: Forward pass
                            with self.tracer.start_as_current_span(
                                "inference.forward_pass",
                                attributes={"uipath.layers.executed": 12},
                            ):
                                await asyncio.sleep(2)

                elif step_name == "compute-embeddings":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Encode text
                        with self.tracer.start_as_current_span(
                            "embeddings.encode",
                            attributes={"uipath.embedding.dim": 768},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Normalize vectors
                        with self.tracer.start_as_current_span(
                            "embeddings.normalize",
                            attributes={"uipath.normalization.method": "l2"},
                        ):
                            await asyncio.sleep(2)

                elif step_name == "query-knowledgebase":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Build query
                        with self.tracer.start_as_current_span(
                            "kb.build_query",
                            attributes={"uipath.query.type": "vector_search"},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Execute search
                        with self.tracer.start_as_current_span(
                            "kb.search",
                            attributes={
                                "uipath.kb.index": "documents-v2",
                                "uipath.kb.top_k": 5,
                            },
                        ):
                            # Deeply nested: Vector similarity
                            with self.tracer.start_as_current_span(
                                "search.vector_similarity",
                                attributes={"uipath.similarity.metric": "cosine"},
                            ):
                                await asyncio.sleep(2)

                            # Deeply nested: Rank results
                            with self.tracer.start_as_current_span(
                                "search.rank_results",
                                attributes={"uipath.ranking.algorithm": "bm25"},
                            ):
                                await asyncio.sleep(2)

                        # Nested: Filter results
                        with self.tracer.start_as_current_span(
                            "kb.filter_results",
                            attributes={"uipath.results.filtered": 3},
                        ):
                            await asyncio.sleep(2)

                elif step_name == "postprocess-results":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Format output
                        with self.tracer.start_as_current_span(
                            "postprocess.format",
                            attributes={"uipath.format.type": "json"},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Apply templates
                        with self.tracer.start_as_current_span(
                            "postprocess.templates",
                            attributes={"uipath.template.name": "standard_response"},
                        ):
                            await asyncio.sleep(2)

                elif step_name == "generate-output":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Serialize data
                        with self.tracer.start_as_current_span(
                            "output.serialize",
                            attributes={"uipath.serialization.format": "json"},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Add metadata
                        with self.tracer.start_as_current_span(
                            "output.add_metadata",
                            attributes={"uipath.metadata.fields": 5},
                        ):
                            await asyncio.sleep(2)

                elif step_name == "persist-artifacts":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Compress data
                        with self.tracer.start_as_current_span(
                            "persist.compress",
                            attributes={"uipath.compression.algorithm": "gzip"},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Write to storage
                        with self.tracer.start_as_current_span(
                            "persist.write",
                            attributes={"uipath.storage.backend": "s3"},
                        ):
                            await asyncio.sleep(2)

                elif step_name == "cleanup-resources":
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")

                        # Nested: Close connections
                        with self.tracer.start_as_current_span(
                            "cleanup.close_connections",
                            attributes={"uipath.connections.closed": 3},
                        ):
                            await asyncio.sleep(2)

                        # Nested: Free memory
                        with self.tracer.start_as_current_span(
                            "cleanup.free_memory",
                            attributes={"uipath.memory.freed_mb": 512},
                        ):
                            await asyncio.sleep(2)

                else:
                    # Default simple span for any other steps
                    with self.tracer.start_as_current_span(
                        span_name,
                        attributes={
                            "uipath.step.name": step_name,
                            "uipath.step.kind": step_kind,
                        },
                    ):
                        logger.info(f"MockRuntime: executing {step_name}")
                        print(f"[MockRuntime] ▶️  Executing: {step_name}")
                        await asyncio.sleep(2)

                # Check if we should break AFTER executing this step
                if should_break_all or step_name in should_break_on:
                    logger.info(f"MockRuntime: hitting breakpoint at {step_name}")
                    print(f"[MockRuntime] 🔴 Breakpoint hit: {step_name}")

                    # Determine next nodes
                    next_nodes = []
                    if self.current_step_index + 1 < len(self.steps):
                        next_nodes = [self.steps[self.current_step_index + 1][1]]

                    return UiPathBreakpointResult(
                        status=UiPathRuntimeStatus.SUSPENDED,
                        breakpoint_node=step_name,
                        breakpoint_type="after",
                        current_state={
                            "paused_at": step_name,
                            "step_index": self.current_step_index,
                            "payload": payload,
                            "message": message,
                        },
                        next_nodes=next_nodes,
                        output={
                            "paused_at": step_name,
                            "step_index": self.current_step_index,
                        },
                    )

                # Move to next step
                self.current_step_index += 1

            # All steps completed - reset state
            self.current_step_index = 0

            root_span.set_attribute("uipath.runtime.status", "success")
            root_span.set_attribute("uipath.runtime.steps_executed", len(self.steps))

            result_payload = {
                "result": f"Mock runtime processed: {payload.get('message', '<no message>')}",
                "metadata": {
                    "entrypoint": entrypoint,
                    "message_length": message_length,
                },
            }

            return UiPathRuntimeResult(
                output=result_payload,
                status=UiPathRuntimeStatus.SUCCESSFUL,
            )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        logger.info("MockRuntime: stream() invoked")
        print("[MockRuntime] stream() invoked")
        yield await self.execute(input=input, options=options)

    async def dispose(self) -> None:
        logger.info("MockRuntime: dispose() invoked")
        print("[MockRuntime] dispose() invoked")
