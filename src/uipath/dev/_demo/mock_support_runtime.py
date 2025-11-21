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

ENTRYPOINT_SUPPORT_CHAT = "agent/support.py:chat"

logger = logging.getLogger(__name__)


class MockSupportChatRuntime:
    """Mock runtime that simulates a tiny support agent."""

    def __init__(self, entrypoint: str = ENTRYPOINT_SUPPORT_CHAT) -> None:
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.support-chat")

    async def get_schema(self) -> UiPathRuntimeSchema:
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
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
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
        logger.info("SupportChatRuntime: stream() invoked")
        yield await self.execute(input=input, options=options)

    async def dispose(self) -> None:
        logger.info("SupportChatRuntime: dispose() invoked")
