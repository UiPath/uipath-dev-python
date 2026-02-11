"""Mock runtime that simulates a support chat agent."""

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
from uipath.runtime.schema import (
    UiPathRuntimeEdge,
    UiPathRuntimeGraph,
    UiPathRuntimeNode,
    UiPathRuntimeSchema,
)

ENTRYPOINT_SUPPORT_CHAT = "agent/support.py:main"

logger = logging.getLogger(__name__)


class MockSupportChatRuntime:
    """Mock runtime that simulates a tiny support agent."""

    def __init__(self, entrypoint: str = ENTRYPOINT_SUPPORT_CHAT) -> None:
        """Initialize the MockSupportChatRuntime."""
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.support-chat")

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Get the schema for the support chat runtime."""
        return UiPathRuntimeSchema(
            filePath=self.entrypoint,
            uniqueId="mock-support-chat-runtime",
            type="agent",
            input={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "User message to the support bot",
                    },
                    "previousIssues": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional prior issues for context",
                    },
                },
                "required": ["message"],
            },
            output={
                "type": "object",
                "properties": {
                    "reply": {"type": "string"},
                    "sentiment": {"type": "string"},
                    "escalated": {"type": "boolean"},
                },
                "required": ["reply"],
            },
            graph=UiPathRuntimeGraph(
                nodes=[
                    UiPathRuntimeNode(id="__start__", name="__start__", type="node"),
                    UiPathRuntimeNode(
                        id="model",
                        name="model",
                        type="model",
                        metadata={
                            "model_name": "claude-haiku-4-5",
                            "max_tokens": 64000,
                        },
                    ),
                    UiPathRuntimeNode(
                        id="tools",
                        name="tools",
                        type="tool",
                        metadata={
                            "tool_names": [
                                "write_todos",
                                "ls",
                                "read_file",
                                "write_file",
                                "edit_file",
                                "glob",
                                "grep",
                                "execute",
                                "task",
                                "tavily_search",
                            ],
                            "tool_count": 10,
                        },
                    ),
                    UiPathRuntimeNode(
                        id="TodoListMiddleware.after_model",
                        name="TodoListMiddleware.after_model",
                        type="node",
                    ),
                    UiPathRuntimeNode(
                        id="SummarizationMiddleware.before_model",
                        name="SummarizationMiddleware.before_model",
                        type="node",
                    ),
                    UiPathRuntimeNode(
                        id="PatchToolCallsMiddleware.before_agent",
                        name="PatchToolCallsMiddleware.before_agent",
                        type="node",
                    ),
                    UiPathRuntimeNode(id="__end__", name="__end__", type="node"),
                ],
                edges=[
                    UiPathRuntimeEdge(
                        source="PatchToolCallsMiddleware.before_agent",
                        target="SummarizationMiddleware.before_model",
                    ),
                    UiPathRuntimeEdge(
                        source="SummarizationMiddleware.before_model", target="model"
                    ),
                    UiPathRuntimeEdge(
                        source="TodoListMiddleware.after_model",
                        target="SummarizationMiddleware.before_model",
                    ),
                    UiPathRuntimeEdge(
                        source="TodoListMiddleware.after_model", target="__end__"
                    ),
                    UiPathRuntimeEdge(
                        source="TodoListMiddleware.after_model", target="tools"
                    ),
                    UiPathRuntimeEdge(
                        source="__start__",
                        target="PatchToolCallsMiddleware.before_agent",
                    ),
                    UiPathRuntimeEdge(
                        source="model", target="TodoListMiddleware.after_model"
                    ),
                    UiPathRuntimeEdge(
                        source="tools", target="SummarizationMiddleware.before_model"
                    ),
                ],
            ),
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Execute the support chat runtime."""
        payload = input or {}
        message = str(payload.get("message", "")).strip()
        previous = payload.get("previousIssues") or []

        with self.tracer.start_as_current_span(
            "support_chat.execute",
            attributes={
                "uipath.runtime.name": "SupportChatRuntime",
                "uipath.runtime.entrypoint": self.entrypoint,
                "uipath.input.message.length": len(message),
                "uipath.input.previous_issues": len(previous),
            },
        ):
            logger.info("SupportChatRuntime: starting execution")

            # Classify sentiment
            with self.tracer.start_as_current_span(
                "support_chat.classify_sentiment",
                attributes={"uipath.step.kind": "analysis"},
            ):
                await asyncio.sleep(0.1)
                lower = message.lower()
                if any(word in lower for word in ["error", "crash", "bug", "broken"]):
                    sentiment = "frustrated"
                elif any(word in lower for word in ["thanks", "thank you", "great"]):
                    sentiment = "positive"
                else:
                    sentiment = "neutral"

            # Generate reply
            with self.tracer.start_as_current_span(
                "support_chat.generate_reply",
                attributes={
                    "uipath.step.kind": "generate",
                    "uipath.sentiment": sentiment,
                },
            ):
                await asyncio.sleep(0.15)
                if sentiment == "frustrated":
                    reply = (
                        "I'm sorry you're having trouble. "
                        "I've logged this and will escalate it to our engineers. 🔧"
                    )
                elif sentiment == "positive":
                    reply = "Happy to hear that everything is working well! 🎉"
                else:
                    reply = (
                        "Thanks for reaching out. Could you share a few more details?"
                    )

            # Decide escalation
            with self.tracer.start_as_current_span(
                "support_chat.decide_escalation",
                attributes={"uipath.step.kind": "decision"},
            ):
                await asyncio.sleep(0.05)
                escalated = sentiment == "frustrated" or len(previous) > 3

            result_payload = {
                "reply": reply,
                "sentiment": sentiment,
                "escalated": escalated,
            }

            logger.info(
                "SupportChatRuntime: execution completed",
                extra={"sentiment": sentiment, "escalated": escalated},
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
        """Stream events from the support chat runtime."""
        logger.info("SupportChatRuntime: stream() invoked")
        yield await self.execute(input=input, options=options)

    async def dispose(self) -> None:
        """Dispose of any resources used by the support chat runtime."""
        logger.info("SupportChatRuntime: dispose() invoked")
