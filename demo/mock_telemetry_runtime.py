"""Mock runtime that simulates a multi-agent supervisor workflow with rich telemetry."""

import asyncio
import logging
from typing import Any, AsyncGenerator, cast

from opentelemetry import context as otel_context
from opentelemetry import trace
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.debug import UiPathBreakpointResult
from uipath.runtime.events import (
    UiPathRuntimeStateEvent,
    UiPathRuntimeStatePhase,
)
from uipath.runtime.schema import (
    UiPathRuntimeEdge,
    UiPathRuntimeGraph,
    UiPathRuntimeNode,
    UiPathRuntimeSchema,
)

ENTRYPOINT_TELEMETRY = "agent/telemetry.py:run"

logger = logging.getLogger(__name__)


def _state(
    node: str,
    phase: UiPathRuntimeStatePhase,
    payload: dict[str, Any] | None = None,
    qualified: str | None = None,
) -> UiPathRuntimeStateEvent:
    return UiPathRuntimeStateEvent(
        node_name=node,
        qualified_node_name=qualified,
        phase=phase,
        payload=payload or {},
    )


S = UiPathRuntimeStatePhase.STARTED
C = UiPathRuntimeStatePhase.COMPLETED


class MockTelemetryRuntime:
    """A mock runtime that simulates a supervisor/researcher/coder multi-agent loop."""

    def __init__(self, entrypoint: str = ENTRYPOINT_TELEMETRY) -> None:
        """Initialize the MockTelemetryRuntime."""
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.context")
        self.current_step_index: int = 0

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Get the schema for the mock telemetry runtime."""
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
            graph=UiPathRuntimeGraph(
                nodes=[
                    UiPathRuntimeNode(id="__start__", name="__start__", type="node"),
                    UiPathRuntimeNode(id="input", name="input", type="node"),
                    UiPathRuntimeNode(
                        id="supervisor",
                        name="supervisor",
                        type="model",
                        metadata={
                            "model_name": "claude-3-7-sonnet-latest",
                            "max_tokens": 64000,
                        },
                    ),
                    UiPathRuntimeNode(
                        id="researcher",
                        name="researcher",
                        type="node",
                        subgraph=UiPathRuntimeGraph(
                            nodes=[
                                UiPathRuntimeNode(
                                    id="__start__", name="__start__", type="node"
                                ),
                                UiPathRuntimeNode(
                                    id="model",
                                    name="model",
                                    type="model",
                                    metadata={
                                        "model_name": "claude-3-7-sonnet-latest",
                                        "max_tokens": 64000,
                                    },
                                ),
                                UiPathRuntimeNode(
                                    id="tools",
                                    name="tools",
                                    type="tool",
                                    metadata={
                                        "tool_names": ["tavily_search"],
                                        "tool_count": 1,
                                    },
                                ),
                                UiPathRuntimeNode(
                                    id="__end__", name="__end__", type="node"
                                ),
                            ],
                            edges=[
                                UiPathRuntimeEdge(source="__start__", target="model"),
                                UiPathRuntimeEdge(source="model", target="__end__"),
                                UiPathRuntimeEdge(source="model", target="tools"),
                                UiPathRuntimeEdge(source="tools", target="model"),
                            ],
                        ),
                    ),
                    UiPathRuntimeNode(
                        id="coder",
                        name="coder",
                        type="node",
                        subgraph=UiPathRuntimeGraph(
                            nodes=[
                                UiPathRuntimeNode(
                                    id="__start__", name="__start__", type="node"
                                ),
                                UiPathRuntimeNode(
                                    id="model",
                                    name="model",
                                    type="model",
                                    metadata={
                                        "model_name": "claude-3-7-sonnet-latest",
                                        "max_tokens": 64000,
                                    },
                                ),
                                UiPathRuntimeNode(
                                    id="tools",
                                    name="tools",
                                    type="tool",
                                    metadata={
                                        "tool_names": ["python_repl_tool"],
                                        "tool_count": 1,
                                    },
                                ),
                                UiPathRuntimeNode(
                                    id="__end__", name="__end__", type="node"
                                ),
                            ],
                            edges=[
                                UiPathRuntimeEdge(source="__start__", target="model"),
                                UiPathRuntimeEdge(source="model", target="__end__"),
                                UiPathRuntimeEdge(source="model", target="tools"),
                                UiPathRuntimeEdge(source="tools", target="model"),
                            ],
                        ),
                    ),
                    UiPathRuntimeNode(id="output", name="output", type="node"),
                    UiPathRuntimeNode(id="__end__", name="__end__", type="__end__"),
                ],
                edges=[
                    UiPathRuntimeEdge(source="__start__", target="input"),
                    UiPathRuntimeEdge(source="coder", target="supervisor"),
                    UiPathRuntimeEdge(source="input", target="supervisor"),
                    UiPathRuntimeEdge(source="researcher", target="supervisor"),
                    UiPathRuntimeEdge(source="supervisor", target="coder"),
                    UiPathRuntimeEdge(
                        source="supervisor", target="output", label="__end__"
                    ),
                    UiPathRuntimeEdge(source="supervisor", target="researcher"),
                    UiPathRuntimeEdge(source="output", target="__end__"),
                ],
            ),
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Execute the mock telemetry runtime by consuming stream()."""
        result: UiPathRuntimeResult | None = None
        async for event in self.stream(
            input=input, options=cast(UiPathStreamOptions, options)
        ):
            if isinstance(event, UiPathRuntimeResult):
                result = event
                if isinstance(event, UiPathBreakpointResult):
                    return event
        return result or UiPathRuntimeResult(
            output={}, status=UiPathRuntimeStatus.SUCCESSFUL
        )

    async def _run_subgraph(
        self, parent: str, span_prefix: str, parent_ctx: otel_context.Context
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Simulate a subgraph execution: model → tools → model."""
        tool_name = "tavily_search" if parent == "researcher" else "python_repl_tool"

        # model call 1
        yield _state("model", S, qualified=f"{parent}/model")
        with self.tracer.start_as_current_span(
            f"{span_prefix}.model",
            context=parent_ctx,
            attributes={
                "uipath.step.kind": "model",
                "uipath.input.model": "claude-3-7-sonnet-latest",
                "uipath.input.max_tokens": 64000,
            },
        ) as span:
            await asyncio.sleep(0.8)
            span.set_attribute("uipath.output.tool_calls", 1)
            span.set_attribute("uipath.output.tool_name", tool_name)
        yield _state("model", C, qualified=f"{parent}/model")

        # tools
        yield _state("tools", S, qualified=f"{parent}/tools")
        with self.tracer.start_as_current_span(
            f"{span_prefix}.tools",
            context=parent_ctx,
            attributes={
                "uipath.step.kind": "tool",
                "uipath.input.tool_name": tool_name,
            },
        ) as span:
            await asyncio.sleep(0.6)
            span.set_attribute("uipath.output.success", True)
            span.set_attribute(
                "uipath.output.result_length",
                256 if parent == "researcher" else 128,
            )
        yield _state("tools", C, qualified=f"{parent}/tools")

        # model call 2
        yield _state("model", S, qualified=f"{parent}/model")
        with self.tracer.start_as_current_span(
            f"{span_prefix}.model_final",
            context=parent_ctx,
            attributes={
                "uipath.step.kind": "model",
                "uipath.input.has_tool_results": True,
            },
        ) as span:
            await asyncio.sleep(0.5)
            span.set_attribute("uipath.output.finish_reason", "end_turn")
            span.set_attribute("uipath.output.response_length", 512)
        yield _state("model", C, qualified=f"{parent}/model")

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Stream events simulating supervisor/researcher/coder multi-agent loop."""
        payload = input or {}
        message = str(payload.get("message", ""))

        breakpoints = options.breakpoints if options else None
        should_break_all = breakpoints == "*"
        should_break_on = set(breakpoints) if isinstance(breakpoints, list) else set()
        is_resuming = options.resume if options else False

        # Steps: (node_name, next_node_for_breakpoint)
        steps = [
            "input",
            "supervisor",
            "researcher",
            "supervisor",
            "coder",
            "supervisor",
            "output",
        ]

        if is_resuming:
            self.current_step_index += 1

        root_span = self.tracer.start_span(
            "mock-runtime.execute",
            attributes={
                "uipath.runtime.name": "MockRuntime",
                "uipath.runtime.type": "agent",
                "uipath.runtime.entrypoint": self.entrypoint,
                "uipath.input.message.length": len(message),
            },
        )
        root_ctx = trace.set_span_in_context(root_span)
        try:
            while self.current_step_index < len(steps):
                step = steps[self.current_step_index]

                if step == "input":
                    yield _state("input", S)
                    with self.tracer.start_as_current_span(
                        "input",
                        context=root_ctx,
                        attributes={
                            "uipath.step.kind": "input",
                            "uipath.input.message": message[:200],
                            "uipath.input.message.length": len(message),
                        },
                    ) as span:
                        await asyncio.sleep(0.3)
                        span.set_attribute(
                            "uipath.output.tokens_estimated", len(message) // 4
                        )
                    yield _state("input", C, {"message": message})

                elif step == "supervisor":
                    yield _state("supervisor", S)
                    # Determine routing decision
                    next_idx = self.current_step_index + 1
                    next_step = steps[next_idx] if next_idx < len(steps) else "output"
                    with self.tracer.start_as_current_span(
                        "supervisor",
                        context=root_ctx,
                        attributes={
                            "uipath.step.kind": "model",
                            "uipath.input.step_index": self.current_step_index,
                            "uipath.input.candidates": "researcher,coder,output",
                        },
                    ) as span:
                        await asyncio.sleep(0.5)
                        span.set_attribute("uipath.output.decision", next_step)
                        span.set_attribute("uipath.output.confidence", 0.92)
                    yield _state("supervisor", C, {"next": next_step})

                elif step == "researcher":
                    yield _state("researcher", S)
                    researcher_span = self.tracer.start_span(
                        "researcher",
                        context=root_ctx,
                        attributes={
                            "uipath.step.kind": "subgraph",
                            "uipath.input.task": "web_research",
                            "uipath.input.query": message[:100],
                        },
                    )
                    researcher_ctx = trace.set_span_in_context(researcher_span)
                    try:
                        async for evt in self._run_subgraph(
                            "researcher", "researcher", researcher_ctx
                        ):
                            yield evt
                        researcher_span.set_attribute("uipath.output.sources_found", 3)
                        researcher_span.set_attribute(
                            "uipath.output.summary.length", 450
                        )
                    finally:
                        researcher_span.end()
                    yield _state("researcher", C)

                elif step == "coder":
                    yield _state("coder", S)
                    coder_span = self.tracer.start_span(
                        "coder",
                        context=root_ctx,
                        attributes={
                            "uipath.step.kind": "subgraph",
                            "uipath.input.task": "code_generation",
                            "uipath.input.language": "python",
                        },
                    )
                    coder_ctx = trace.set_span_in_context(coder_span)
                    try:
                        async for evt in self._run_subgraph(
                            "coder", "coder", coder_ctx
                        ):
                            yield evt
                        coder_span.set_attribute("uipath.output.lines_generated", 47)
                        coder_span.set_attribute("uipath.output.tests_passed", True)
                    finally:
                        coder_span.end()
                    yield _state("coder", C)

                elif step == "output":
                    yield _state("output", S)
                    with self.tracer.start_as_current_span(
                        "output",
                        context=root_ctx,
                        attributes={
                            "uipath.step.kind": "output",
                            "uipath.input.message": message[:100],
                        },
                    ) as span:
                        await asyncio.sleep(0.3)
                        span.set_attribute("uipath.output.format", "markdown")
                        span.set_attribute("uipath.output.length", 820)
                    yield _state("output", C)

                # Check breakpoints after each top-level step
                if should_break_all or step in should_break_on:
                    next_nodes = []
                    if self.current_step_index + 1 < len(steps):
                        next_nodes = [steps[self.current_step_index + 1]]

                    yield UiPathBreakpointResult(
                        status=UiPathRuntimeStatus.SUSPENDED,
                        breakpoint_node=step,
                        breakpoint_type="after",
                        current_state={
                            "paused_at": step,
                            "step_index": self.current_step_index,
                            "payload": payload,
                            "message": message,
                        },
                        next_nodes=next_nodes,
                        output={
                            "paused_at": step,
                            "step_index": self.current_step_index,
                        },
                    )
                    return

                self.current_step_index += 1

            # All steps completed — reset
            self.current_step_index = 0
        finally:
            root_span.end()

        yield UiPathRuntimeResult(
            output={
                "result": f"Mock runtime processed: {message or '<no message>'}",
                "metadata": {
                    "entrypoint": self.entrypoint,
                    "message_length": len(message),
                },
            },
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def dispose(self) -> None:
        """Dispose of any resources used by the mock telemetry runtime."""
        pass
