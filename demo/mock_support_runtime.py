"""Mock runtime that simulates a support chat agent with token streaming and tool calls."""

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncGenerator
from uuid import uuid4

from opentelemetry import trace
from uipath.core.chat import UiPathConversationMessageEvent
from uipath.core.chat.content import (
    UiPathConversationContentPartChunkEvent,
    UiPathConversationContentPartEndEvent,
    UiPathConversationContentPartEvent,
    UiPathConversationContentPartStartEvent,
)
from uipath.core.chat.interrupt import (
    UiPathConversationToolCallConfirmationValue,
)
from uipath.core.chat.message import (
    UiPathConversationMessageEndEvent,
    UiPathConversationMessageStartEvent,
)
from uipath.core.chat.tool import (
    UiPathConversationToolCallEndEvent,
    UiPathConversationToolCallEvent,
    UiPathConversationToolCallStartEvent,
)
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.events import (
    UiPathRuntimeMessageEvent,
    UiPathRuntimeStateEvent,
    UiPathRuntimeStatePhase,
)
from uipath.runtime.resumable.trigger import (
    UiPathResumeTrigger,
    UiPathResumeTriggerType,
)
from uipath.runtime.schema import (
    UiPathRuntimeEdge,
    UiPathRuntimeGraph,
    UiPathRuntimeNode,
    UiPathRuntimeSchema,
)

ENTRYPOINT_SUPPORT_CHAT = "chat/support.py:main"

logger = logging.getLogger(__name__)

S = UiPathRuntimeStatePhase.STARTED
C = UiPathRuntimeStatePhase.COMPLETED


# --- Turn routing -----------------------------------------------------------
# Each turn: (tool_name, tool_input, tool_output, response_text)
# We always call at least one tool per turn for a realistic demo.

_TURNS: list[dict[str, Any]] = [
    # Turn 1: greeting / first contact — look up account
    {
        "keywords": [],  # default / catch-all for first message
        "tools": [
            {
                "name": "tavily_search",
                "input": {"query": "UiPath support knowledge base"},
                "output": "Found 3 relevant articles: KB-1024 'Getting Started', KB-2048 'Troubleshooting', KB-4096 'Best Practices'",
            },
        ],
        "needs_approval": False,
        "response": (
            "Welcome to UiPath Support! I've searched our knowledge base for "
            "relevant articles. Here's what I found:\n\n"
            "- **KB-1024** — Getting Started with UiPath Studio\n"
            "- **KB-2048** — Troubleshooting Common Issues\n"
            "- **KB-4096** — Automation Best Practices\n\n"
            "How can I help you today? Feel free to describe your issue "
            "and I'll look into it right away."
        ),
    },
    # Turn 2: error / bug report — grep logs + create ticket (needs approval)
    {
        "keywords": ["error", "crash", "bug", "broken", "fail", "issue", "problem"],
        "tools": [
            {
                "name": "grep",
                "input": {"pattern": "ERROR|FATAL", "path": "/var/log/uipath/"},
                "output": "[2026-02-17 09:12:33] ERROR OrchestratorConnection: timeout after 30s\n[2026-02-17 09:12:34] ERROR RetryPolicy: max retries exceeded",
            },
        ],
        "needs_approval": True,
        "approval_tool": {
            "name": "execute",
            "input": {
                "command": "create-ticket --priority high --category connection-timeout"
            },
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    },
                },
                "required": ["command"],
            },
            "output": "Ticket SUP-4821 created successfully. Assigned to engineering team.",
        },
        "response": (
            "I found the issue in the logs — there's a connection timeout "
            "to Orchestrator that's causing the failures:\n\n"
            "```\n"
            "[2026-02-17 09:12:33] ERROR OrchestratorConnection: timeout after 30s\n"
            "[2026-02-17 09:12:34] ERROR RetryPolicy: max retries exceeded\n"
            "```\n\n"
            "I've created ticket **SUP-4821** and assigned it to our engineering team "
            "with high priority. In the meantime, try these steps:\n\n"
            "1. Check your network connectivity to Orchestrator\n"
            "2. Verify the Orchestrator URL in your config\n"
            "3. Restart the UiPath Robot service\n\n"
            "Would you like me to check anything else?"
        ),
    },
    # Turn 3: follow-up / how-to — read docs + write summary
    {
        "keywords": ["how", "help", "guide", "docs", "config", "setup", "restart"],
        "tools": [
            {
                "name": "read_file",
                "input": {"path": "/docs/troubleshooting/connection-timeout.md"},
                "output": "# Connection Timeout Troubleshooting\n\n1. Open UiPath Assistant\n2. Go to Settings > Connections\n3. Set timeout to 60s\n4. Click 'Test Connection'\n5. If still failing, check proxy settings",
            },
        ],
        "needs_approval": False,
        "response": (
            "Here's a step-by-step guide to fix connection timeouts:\n\n"
            "1. Open **UiPath Assistant** on your machine\n"
            "2. Navigate to **Settings → Connections**\n"
            "3. Increase the timeout value to **60 seconds**\n"
            "4. Click **Test Connection** to verify\n"
            "5. If it's still failing, check your proxy settings — "
            "the connection might be going through a corporate proxy\n\n"
            "Let me know if that resolves your issue, or if you need "
            "further assistance!"
        ),
    },
    # Turn 4+: positive / thanks — update ticket
    {
        "keywords": ["thanks", "thank", "great", "awesome", "works", "fixed", "solved"],
        "tools": [
            {
                "name": "execute",
                "input": {
                    "command": "update-ticket SUP-4821 --status resolved --note 'Customer confirmed fix'"
                },
                "output": "Ticket SUP-4821 updated: status → resolved",
            },
        ],
        "needs_approval": False,
        "response": (
            "Glad to hear it's working now! I've updated ticket **SUP-4821** "
            "to resolved status.\n\n"
            "Here's a summary of what we did:\n"
            "- Identified connection timeout errors in the logs\n"
            "- Increased the Orchestrator connection timeout to 60s\n"
            "- Verified the connection is stable\n\n"
            "If you run into any issues in the future, don't hesitate to reach out. "
            "Have a great day!"
        ),
    },
]


_support_turn_index = 0


def _next_turn() -> dict[str, Any]:
    """Return the next turn in sequence, cycling through all turns."""
    global _support_turn_index  # noqa: PLW0603
    turn = _TURNS[_support_turn_index % len(_TURNS)]
    _support_turn_index += 1
    return turn


class MockSupportChatRuntime:
    """Mock runtime that simulates a support agent with chat streaming and tool calls."""

    def __init__(self, entrypoint: str = ENTRYPOINT_SUPPORT_CHAT) -> None:
        """Initialize the MockSupportChatRuntime."""
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.support-chat")
        self._suspended_turn: dict[str, Any] | None = None
        self._suspended_message_id: str | None = None

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
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {"type": "string"},
                            },
                        },
                        "description": "Conversation history for chat mode",
                    },
                },
                "required": ["message"],
            },
            output={
                "type": "object",
                "properties": {
                    "reply": {"type": "string"},
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
                                "tavily_search",
                                "read_file",
                                "grep",
                                "execute",
                            ],
                            "tool_count": 4,
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
        """Execute the support chat runtime by consuming stream()."""
        result: UiPathRuntimeResult | None = None
        async for event in self.stream(input=input):
            if isinstance(event, UiPathRuntimeResult):
                result = event
        return result or UiPathRuntimeResult(
            output={}, status=UiPathRuntimeStatus.SUCCESSFUL
        )

    async def _emit_streaming_response(
        self, text: str
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Emit chat streaming events for a response: start → chunks → end."""
        message_id = str(uuid4())
        content_part_id = str(uuid4())

        # message_start
        yield UiPathRuntimeMessageEvent(
            payload=UiPathConversationMessageEvent(
                message_id=message_id,
                start=UiPathConversationMessageStartEvent(
                    role="assistant",
                    timestamp=datetime.now().isoformat(),
                ),
            ),
        )

        # content_part_start
        yield UiPathRuntimeMessageEvent(
            payload=UiPathConversationMessageEvent(
                message_id=message_id,
                content_part=UiPathConversationContentPartEvent(
                    content_part_id=content_part_id,
                    start=UiPathConversationContentPartStartEvent(
                        mime_type="text/plain",
                    ),
                ),
            ),
        )

        # Stream word by word
        words = text.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else f" {word}"
            yield UiPathRuntimeMessageEvent(
                payload=UiPathConversationMessageEvent(
                    message_id=message_id,
                    content_part=UiPathConversationContentPartEvent(
                        content_part_id=content_part_id,
                        chunk=UiPathConversationContentPartChunkEvent(data=chunk),
                    ),
                ),
            )
            await asyncio.sleep(0.04)

        # content_part_end
        yield UiPathRuntimeMessageEvent(
            payload=UiPathConversationMessageEvent(
                message_id=message_id,
                content_part=UiPathConversationContentPartEvent(
                    content_part_id=content_part_id,
                    end=UiPathConversationContentPartEndEvent(),
                ),
            ),
        )

        # message_end
        yield UiPathRuntimeMessageEvent(
            payload=UiPathConversationMessageEvent(
                message_id=message_id,
                end=UiPathConversationMessageEndEvent(),
            ),
        )

    async def _emit_tool_calls(
        self, message_id: str, tools: list[dict[str, Any]]
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Emit tool call start/end events for each tool in the list."""
        for tool in tools:
            tool_call_id = f"call_{uuid4().hex[:12]}"

            # tool_call start
            yield UiPathRuntimeMessageEvent(
                payload=UiPathConversationMessageEvent(
                    message_id=message_id,
                    tool_call=UiPathConversationToolCallEvent(
                        tool_call_id=tool_call_id,
                        start=UiPathConversationToolCallStartEvent(
                            tool_name=tool["name"],
                            timestamp=datetime.now().isoformat(),
                            input=tool["input"],
                        ),
                    ),
                ),
            )
            await asyncio.sleep(0.3)

            # tool_call end
            yield UiPathRuntimeMessageEvent(
                payload=UiPathConversationMessageEvent(
                    message_id=message_id,
                    tool_call=UiPathConversationToolCallEvent(
                        tool_call_id=tool_call_id,
                        end=UiPathConversationToolCallEndEvent(
                            timestamp=datetime.now().isoformat(),
                            output=tool["output"],
                        ),
                    ),
                ),
            )

    def _node_state(
        self, node: str, phase: UiPathRuntimeStatePhase
    ) -> UiPathRuntimeStateEvent:
        return UiPathRuntimeStateEvent(node_name=node, phase=phase, payload={})

    async def _stream_phase2(
        self, turn: dict[str, Any]
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Phase 2: after tool approval — tools → Summarization → model response → TodoList."""
        reply = turn["response"]
        approval_tool = turn.get("approval_tool", {})

        # --- Tools (execute approved tool call) ---
        yield self._node_state("tools", S)
        with self.tracer.start_as_current_span(
            "tools",
            attributes={
                "uipath.step.kind": "tool",
                "uipath.input.tool_name": approval_tool.get("name", ""),
                "uipath.output.result": approval_tool.get("output", ""),
            },
        ):
            await asyncio.sleep(0.5)
        yield self._node_state("tools", C)

        # --- Middleware: Summarization (with tool results) ---
        yield self._node_state("SummarizationMiddleware.before_model", S)
        with self.tracer.start_as_current_span(
            "SummarizationMiddleware.before_model.2",
            attributes={"uipath.step.kind": "middleware"},
        ):
            await asyncio.sleep(0.15)
        yield self._node_state("SummarizationMiddleware.before_model", C)

        # --- Model (streaming final response) ---
        yield self._node_state("model", S)
        with self.tracer.start_as_current_span(
            "model.2",
            attributes={
                "uipath.step.kind": "model",
                "uipath.output.reply.length": len(reply),
            },
        ):
            async for evt in self._emit_streaming_response(reply):
                yield evt
        yield self._node_state("model", C)

        # --- Middleware: TodoList (routes to __end__) ---
        yield self._node_state("TodoListMiddleware.after_model", S)
        with self.tracer.start_as_current_span(
            "TodoListMiddleware.after_model.2",
            attributes={
                "uipath.step.kind": "middleware",
                "uipath.output.route": "__end__",
            },
        ):
            await asyncio.sleep(0.1)
        yield self._node_state("TodoListMiddleware.after_model", C)

        yield UiPathRuntimeResult(
            output={"reply": reply},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Stream events from the support chat runtime with tool calls and token streaming."""
        is_resuming = options.resume if options else False

        # --- Resume after tool approval ---
        if is_resuming and self._suspended_turn is not None:
            turn = self._suspended_turn
            self._suspended_turn = None
            self._suspended_message_id = None

            with self.tracer.start_as_current_span(
                "support_chat.resume",
                attributes={
                    "uipath.runtime.name": "SupportChatRuntime",
                    "uipath.step.kind": "resume",
                },
            ):
                async for evt in self._stream_phase2(turn):
                    yield evt
            return

        # --- Normal flow ---
        payload = input or {}

        # Extract message from either 'message' or last user message in 'messages'
        messages = payload.get("messages") or []
        message = str(payload.get("message", "")).strip()
        if not message and messages:
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    message = str(msg.get("content", ""))
                    break

        turn = _next_turn()
        reply = turn["response"]
        tool_defs: list[dict[str, Any]] = turn["tools"]
        needs_approval = turn.get("needs_approval", False)

        # Shared message_id for the assistant turn (tool calls + response)
        message_id = str(uuid4())

        with self.tracer.start_as_current_span(
            "support_chat.execute",
            attributes={
                "uipath.runtime.name": "SupportChatRuntime",
                "uipath.runtime.entrypoint": self.entrypoint,
                "uipath.input.message": message[:200],
                "uipath.input.message.length": len(message),
                "uipath.input.turn_keywords": ",".join(turn.get("keywords", [])),
            },
        ):
            # --- Middleware: PatchToolCalls ---
            yield self._node_state("PatchToolCallsMiddleware.before_agent", S)
            with self.tracer.start_as_current_span(
                "PatchToolCallsMiddleware.before_agent",
                attributes={
                    "uipath.step.kind": "middleware",
                    "uipath.output.tools_patched": len(tool_defs),
                },
            ):
                await asyncio.sleep(0.15)
            yield self._node_state("PatchToolCallsMiddleware.before_agent", C)

            # --- Middleware: Summarization (first) ---
            yield self._node_state("SummarizationMiddleware.before_model", S)
            with self.tracer.start_as_current_span(
                "SummarizationMiddleware.before_model",
                attributes={
                    "uipath.step.kind": "middleware",
                    "uipath.input.message_count": len(messages) + 1,
                },
            ):
                await asyncio.sleep(0.2)
            yield self._node_state("SummarizationMiddleware.before_model", C)

            # --- Model (first call — decides to use tools) ---
            yield self._node_state("model", S)
            with self.tracer.start_as_current_span(
                "model",
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.output.tool_calls_count": len(tool_defs),
                    "uipath.output.tool_names": ",".join(t["name"] for t in tool_defs),
                },
            ):
                # message_start for tool-call message
                yield UiPathRuntimeMessageEvent(
                    payload=UiPathConversationMessageEvent(
                        message_id=message_id,
                        start=UiPathConversationMessageStartEvent(
                            role="assistant",
                            timestamp=datetime.now().isoformat(),
                        ),
                    ),
                )
                # Emit tool call events from the model
                async for evt in self._emit_tool_calls(message_id, tool_defs):
                    yield evt
            yield self._node_state("model", C)

            # --- Middleware: TodoList (routes to tools) ---
            yield self._node_state("TodoListMiddleware.after_model", S)
            with self.tracer.start_as_current_span(
                "TodoListMiddleware.after_model",
                attributes={
                    "uipath.step.kind": "middleware",
                    "uipath.output.route": "tools",
                },
            ):
                await asyncio.sleep(0.1)
            yield self._node_state("TodoListMiddleware.after_model", C)

            # --- Tools (execute the tool calls) ---
            yield self._node_state("tools", S)
            with self.tracer.start_as_current_span(
                "tools",
                attributes={
                    "uipath.step.kind": "tool",
                    "uipath.input.tool_count": len(tool_defs),
                    "uipath.output.results": "; ".join(
                        t.get("output", "")[:100] for t in tool_defs
                    ),
                },
            ):
                await asyncio.sleep(0.5)
            yield self._node_state("tools", C)

            # --- Check if this turn needs tool approval ---
            if needs_approval:
                approval_tool = turn["approval_tool"]
                interrupt_id = str(uuid4())
                tool_call_id = f"call_{uuid4().hex[:12]}"

                # Store state for resume
                self._suspended_turn = turn
                self._suspended_message_id = message_id

                yield UiPathRuntimeResult(
                    status=UiPathRuntimeStatus.SUSPENDED,
                    output={"paused_for_approval": approval_tool["name"]},
                    triggers=[
                        UiPathResumeTrigger(
                            interrupt_id=interrupt_id,
                            trigger_type=UiPathResumeTriggerType.API,
                            payload=UiPathConversationToolCallConfirmationValue(
                                tool_call_id=tool_call_id,
                                tool_name=approval_tool["name"],
                                input_schema=approval_tool["input_schema"],
                                input_value=approval_tool["input"],
                            ),
                        ),
                    ],
                )
                return

            # --- No approval needed — continue with phase 2 inline ---

            # --- Middleware: Summarization (second pass with tool results) ---
            yield self._node_state("SummarizationMiddleware.before_model", S)
            with self.tracer.start_as_current_span(
                "SummarizationMiddleware.before_model.2",
                attributes={"uipath.step.kind": "middleware"},
            ):
                await asyncio.sleep(0.15)
            yield self._node_state("SummarizationMiddleware.before_model", C)

            # --- Model (second call — streaming final response with tool results) ---
            yield self._node_state("model", S)
            with self.tracer.start_as_current_span(
                "model.2",
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.output.reply.length": len(reply),
                },
            ):
                async for evt in self._emit_streaming_response(reply):
                    yield evt
            yield self._node_state("model", C)

            # --- Middleware: TodoList (routes to __end__) ---
            yield self._node_state("TodoListMiddleware.after_model", S)
            with self.tracer.start_as_current_span(
                "TodoListMiddleware.after_model.2",
                attributes={
                    "uipath.step.kind": "middleware",
                    "uipath.output.route": "__end__",
                },
            ):
                await asyncio.sleep(0.1)
            yield self._node_state("TodoListMiddleware.after_model", C)

        yield UiPathRuntimeResult(
            output={"reply": reply},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def dispose(self) -> None:
        """Dispose of any resources used by the support chat runtime."""
        pass
