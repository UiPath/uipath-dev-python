"""Mock runtime that simulates a movie recommendation chat agent."""

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
from uipath.runtime.schema import (
    UiPathRuntimeEdge,
    UiPathRuntimeGraph,
    UiPathRuntimeNode,
    UiPathRuntimeSchema,
)

ENTRYPOINT_MOVIES = "chat/movies.py:graph"

logger = logging.getLogger(__name__)

S = UiPathRuntimeStatePhase.STARTED
C = UiPathRuntimeStatePhase.COMPLETED


# --- Turn definitions -------------------------------------------------------

_TURNS: list[dict[str, Any]] = [
    # Turn: action movies
    {
        "keywords": ["action", "thriller", "fight", "explosion"],
        "tools": [
            {
                "name": "tavily_search",
                "input": {"query": "best action movies 2024 2025 rated"},
                "output": "Top results: 1) Furiosa: A Mad Max Saga (2024) - 90% RT, 2) The Fall Guy (2024) - 81% RT, 3) Rebel Ridge (2024) - 95% RT",
            },
        ],
        "response": (
            "I searched for the latest highly-rated action movies. "
            "Here are my top picks:\n\n"
            "1. **Furiosa: A Mad Max Saga** (2024) — 90% on Rotten Tomatoes. "
            "Anya Taylor-Joy stars in this epic prequel to Fury Road.\n\n"
            "2. **Rebel Ridge** (2024) — 95% on RT. A tense thriller about "
            "a former Marine facing a corrupt small-town police force.\n\n"
            "3. **The Fall Guy** (2024) — 81% on RT. Ryan Gosling in a fun "
            "action-comedy about Hollywood stunt performers.\n\n"
            "Want me to look up more details about any of these, "
            "or search for a different genre?"
        ),
    },
    # Turn: comedy
    {
        "keywords": ["comedy", "funny", "laugh", "humor"],
        "tools": [
            {
                "name": "tavily_search",
                "input": {"query": "best comedy movies 2024 2025 critically acclaimed"},
                "output": "Top results: 1) Hit Man (2024) - 96% RT, 2) A Real Pain (2024) - 92% RT, 3) Hundreds of Beavers (2024) - 96% RT",
            },
        ],
        "response": (
            "Great choice! Here are some critically acclaimed comedies:\n\n"
            "1. **Hit Man** (2024) — 96% on RT. Glen Powell in a hilarious "
            "and surprisingly romantic story about a fake hitman.\n\n"
            "2. **A Real Pain** (2024) — 92% on RT. Jesse Eisenberg and "
            "Kieran Culkin in a bittersweet comedy about cousins touring Poland.\n\n"
            "3. **Hundreds of Beavers** (2024) — 96% on RT. A wildly creative "
            "low-budget slapstick comedy that critics are calling a modern classic.\n\n"
            "Would you like me to find showtimes or streaming availability?"
        ),
    },
    # Turn: sci-fi / horror
    {
        "keywords": ["sci-fi", "horror", "scary", "space", "alien", "robot"],
        "tools": [
            {
                "name": "tavily_search",
                "input": {"query": "best sci-fi horror movies recent highly rated"},
                "output": "Top results: 1) Alien: Romulus (2024) - 80% RT, 2) A Quiet Place: Day One (2024) - 87% RT, 3) The Substance (2024) - 89% RT",
            },
        ],
        "response": (
            "Here are some great sci-fi and horror picks:\n\n"
            "1. **The Substance** (2024) — 89% on RT. Demi Moore in a "
            "body-horror satire that's both terrifying and thought-provoking.\n\n"
            "2. **A Quiet Place: Day One** (2024) — 87% on RT. The prequel "
            "showing how the alien invasion first began in New York City.\n\n"
            "3. **Alien: Romulus** (2024) — 80% on RT. A return to the "
            "claustrophobic horror of the original Alien franchise.\n\n"
            "Want me to search for something more specific?"
        ),
    },
    # Turn: details / specific movie
    {
        "keywords": [
            "tell me more",
            "details",
            "about",
            "where",
            "stream",
            "watch",
            "showtimes",
        ],
        "tools": [
            {
                "name": "tavily_search",
                "input": {"query": "where to stream watch movies 2024"},
                "output": "Streaming availability: Netflix has Hit Man, Amazon Prime has The Fall Guy, Apple TV+ has Killers of the Flower Moon, Disney+ has Furiosa",
            },
        ],
        "response": (
            "Here's where you can find these movies:\n\n"
            "- **Netflix** — Hit Man, Rebel Ridge\n"
            "- **Amazon Prime** — The Fall Guy, A Quiet Place: Day One\n"
            "- **Apple TV+** — Killers of the Flower Moon\n"
            "- **Disney+** — Furiosa: A Mad Max Saga\n"
            "- **Hulu** — Alien: Romulus\n\n"
            "Most of these are included with a subscription. "
            "Would you like me to look up anything else?"
        ),
    },
    # Turn: thanks / positive
    {
        "keywords": ["thanks", "thank", "great", "awesome", "perfect", "bye"],
        "tools": [
            {
                "name": "tavily_search",
                "input": {"query": "upcoming movies 2025 most anticipated"},
                "output": "Most anticipated: Mission Impossible 8 (May 2025), Jurassic World Rebirth (Jul 2025), Superman (Jul 2025)",
            },
        ],
        "response": (
            "You're welcome! Before you go, here are some exciting "
            "upcoming releases to look forward to:\n\n"
            "- **Mission: Impossible 8** — May 2025\n"
            "- **Superman** — July 2025\n"
            "- **Jurassic World Rebirth** — July 2025\n\n"
            "Enjoy your movie night! Feel free to come back anytime "
            "for more recommendations."
        ),
    },
    # Default / catch-all
    {
        "keywords": [],
        "tools": [
            {
                "name": "tavily_search",
                "input": {"query": "best movies 2024 2025 all genres top rated"},
                "output": "Overall top: 1) Anora (2024) - 95% RT Palme d'Or, 2) Conclave (2024) - 93% RT, 3) Dune: Part Two (2024) - 92% RT, 4) The Brutalist (2024) - 89% RT",
            },
        ],
        "response": (
            "I'd be happy to help you find a great movie! "
            "I searched for the top-rated films across all genres:\n\n"
            "1. **Anora** (2024) — 95% on RT, Palme d'Or winner. "
            "A captivating story about a Brooklyn sex worker who marries "
            "the son of a Russian oligarch.\n\n"
            "2. **Conclave** (2024) — 93% on RT. Ralph Fiennes leads a "
            "gripping thriller set inside the Vatican's papal election.\n\n"
            "3. **Dune: Part Two** (2024) — 92% on RT. The epic continuation "
            "of Denis Villeneuve's sci-fi masterpiece.\n\n"
            "4. **The Brutalist** (2024) — 89% on RT. Adrien Brody in a "
            "sweeping drama about a Hungarian architect in post-war America.\n\n"
            "What genre are you in the mood for? I can search for "
            "action, comedy, sci-fi, horror, drama, or anything else!"
        ),
    },
]


_movies_turn_index = 0


def _next_turn() -> dict[str, Any]:
    """Return the next turn in sequence, cycling through all turns."""
    global _movies_turn_index  # noqa: PLW0603
    turn = _TURNS[_movies_turn_index % len(_TURNS)]
    _movies_turn_index += 1
    return turn


class MockMoviesRuntime:
    """Mock runtime for movie recommendation chat with streaming + telemetry + tools."""

    def __init__(self, entrypoint: str = ENTRYPOINT_MOVIES) -> None:
        """Initialize the MockMoviesRuntime."""
        self.entrypoint = entrypoint
        self.tracer = trace.get_tracer("uipath.dev.mock.movies")

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Get the schema for the movies runtime."""
        return UiPathRuntimeSchema(
            filePath=self.entrypoint,
            uniqueId="mock-movies-runtime",
            type="agent",
            input={
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {"type": "string"},
                            },
                        },
                        "description": "Conversation history",
                    },
                },
                "required": ["messages"],
            },
            output={
                "type": "object",
                "properties": {
                    "reply": {"type": "string"},
                },
            },
            graph=UiPathRuntimeGraph(
                nodes=[
                    UiPathRuntimeNode(
                        id="__start__", name="__start__", type="__start__"
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
                    UiPathRuntimeNode(id="__end__", name="__end__", type="__end__"),
                ],
                edges=[
                    UiPathRuntimeEdge(source="__start__", target="model"),
                    UiPathRuntimeEdge(source="model", target="__end__"),
                    UiPathRuntimeEdge(source="model", target="tools"),
                    UiPathRuntimeEdge(source="tools", target="model"),
                ],
            ),
        )

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Execute the movies runtime by consuming stream()."""
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
        """Emit chat streaming events: start → chunks → end."""
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
        """Emit tool call start/end events."""
        for tool in tools:
            tool_call_id = f"call_{uuid4().hex[:12]}"

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
            await asyncio.sleep(0.4)

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

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Stream events with tool calls, token streaming, and telemetry."""
        payload = input or {}

        # Extract user message from messages array
        messages = payload.get("messages") or []
        message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                message = str(msg.get("content", ""))
                break

        turn = _next_turn()
        reply = turn["response"]
        tool_defs: list[dict[str, Any]] = turn["tools"]

        message_id = str(uuid4())

        root_span = self.tracer.start_span(
            "movies.execute",
            attributes={
                "uipath.runtime.name": "MoviesRuntime",
                "uipath.runtime.entrypoint": self.entrypoint,
                "uipath.input.message": message[:200],
                "uipath.input.message.length": len(message),
                "uipath.input.turn_keywords": ",".join(turn.get("keywords", [])),
            },
        )
        root_ctx = trace.set_span_in_context(root_span)
        try:
            # --- Model (first call — decides to search) ---
            yield self._node_state("model", S)
            model_span = self.tracer.start_span(
                "model",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.input.model": "claude-3-7-sonnet-latest",
                    "uipath.output.tool_calls_count": len(tool_defs),
                    "uipath.output.tool_names": ",".join(t["name"] for t in tool_defs),
                },
            )
            try:
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
                # Emit tool call events
                async for evt in self._emit_tool_calls(message_id, tool_defs):
                    yield evt
            finally:
                model_span.end()
            yield self._node_state("model", C)

            # --- Tools (execute search) ---
            yield self._node_state("tools", S)
            with self.tracer.start_as_current_span(
                "tools",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "tool",
                    "uipath.input.tool_count": len(tool_defs),
                    "uipath.input.search_query": tool_defs[0]
                    .get("input", {})
                    .get("query", ""),
                    "uipath.output.results": tool_defs[0].get("output", "")[:200],
                },
            ):
                await asyncio.sleep(0.5)
            yield self._node_state("tools", C)

            # --- Model (second call — streaming response with search results) ---
            yield self._node_state("model", S)
            model_final_span = self.tracer.start_span(
                "model.final",
                context=root_ctx,
                attributes={
                    "uipath.step.kind": "model",
                    "uipath.input.has_tool_results": True,
                    "uipath.output.reply.length": len(reply),
                    "uipath.output.finish_reason": "end_turn",
                },
            )
            try:
                async for evt in self._emit_streaming_response(reply):
                    yield evt
            finally:
                model_final_span.end()
            yield self._node_state("model", C)
        finally:
            root_span.end()

        yield UiPathRuntimeResult(
            output={"reply": reply},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def dispose(self) -> None:
        """Dispose of any resources used by the movies runtime."""
        pass
