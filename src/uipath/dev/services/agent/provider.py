"""Model provider protocol + OpenAI-compatible streaming implementation."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """A tool call from the model."""

    id: str
    name: str
    arguments: str  # raw JSON string


@dataclass
class Usage:
    """Token usage for a single completion."""

    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ModelResponse:
    """Non-streaming model response."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking: str | None = None
    finish_reason: str = ""
    usage: Usage | None = None


@dataclass
class StreamEvent:
    """A single event from a streaming response."""

    type: str  # "text_delta" | "thinking_delta" | "tool_call" | "done"
    delta: str = ""
    tool_call: ToolCall | None = None
    usage: Usage | None = None
    finish_reason: str = ""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ModelProvider(Protocol):
    """Protocol for model providers."""

    async def complete(  # noqa: D102
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0,
    ) -> ModelResponse: ...

    def stream(  # noqa: D102
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0,
    ) -> AsyncIterator[StreamEvent]: ...


# ---------------------------------------------------------------------------
# OpenAI-compatible provider via UiPath LLM gateway
# ---------------------------------------------------------------------------


# Reasoning models don't support temperature.
_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def _is_reasoning_model(model: str) -> bool:
    return any(model.startswith(p) for p in _REASONING_PREFIXES)


def _get_gateway_env() -> tuple[str, str]:
    """Return (base_url, access_token) from environment."""
    base_url = os.environ.get("UIPATH_URL", "")
    access_token = os.environ.get("UIPATH_ACCESS_TOKEN", "")
    if not base_url or not access_token:
        raise RuntimeError(
            "Not authenticated — UIPATH_URL or UIPATH_ACCESS_TOKEN not set"
        )
    return base_url, access_token


def _make_rewrite_transport(gateway_completions_url: str) -> Any:
    """Create an httpx transport that rewrites all URLs to the gateway endpoint.

    The gateway uses the X-UiPath-LlmGateway-ApiFlavor header (not the URL)
    to distinguish Chat Completions from Responses API payloads.
    """
    import httpx

    class _RewriteTransport(httpx.AsyncHTTPTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            params = request.url.params
            request.url = httpx.URL(gateway_completions_url, params=params)
            return await super().handle_async_request(request)

    return _RewriteTransport()


class OpenAIProvider:
    """OpenAI-compatible provider via UiPath LLM gateway."""

    def __init__(self, model: str) -> None:
        """Initialize with a model name."""
        self._model = model
        self._completions_client = self._create_completions_client(model)
        self._responses_client: Any = None  # Lazy-created for reasoning models

    @staticmethod
    def _create_completions_client(model_name: str) -> Any:
        """Create an AsyncOpenAI client for the Chat Completions API."""
        from openai import AsyncOpenAI

        base_url, access_token = _get_gateway_env()
        gateway_base = (
            f"{base_url.rstrip('/')}/agenthub_/llm/openai/deployments/{model_name}"
        )
        return AsyncOpenAI(
            api_key=access_token,
            base_url=gateway_base,
            default_query={"api-version": "2025-03-01-preview"},
            default_headers={
                "X-UiPath-LlmGateway-RequestingProduct": "AgentsPlayground",
                "X-UiPath-LlmGateway-RequestingFeature": "uipath-dev",
            },
        )

    @staticmethod
    def _create_responses_client(model_name: str) -> Any:
        """Create an AsyncOpenAI client for the Responses API.

        Uses a URL-rewriting transport so the SDK's /responses path
        gets redirected to the gateway's /completions endpoint.
        The ApiFlavor header tells the gateway it's a Responses API payload.
        """
        import httpx
        from openai import AsyncOpenAI

        base_url, access_token = _get_gateway_env()
        # The gateway's unified endpoint — uses the raw vendor/model path
        # (same as uipath-langchain). ApiFlavor header tells the gateway
        # whether the payload is Chat Completions or Responses API format.
        completions_url = (
            f"{base_url.rstrip('/')}/agenthub_/llm"
            f"/raw/vendor/openai/model/{model_name}/completions"
        )
        # The SDK needs a base_url so it can construct /responses,
        # but our transport will rewrite to the completions_url.
        dummy_base = (
            f"{base_url.rstrip('/')}/agenthub_/llm/openai/deployments/{model_name}"
        )
        return AsyncOpenAI(
            api_key=access_token,
            base_url=dummy_base,
            default_query={"api-version": "2025-04-01-preview"},
            default_headers={
                "X-UiPath-LlmGateway-RequestingProduct": "AgentsPlayground",
                "X-UiPath-LlmGateway-RequestingFeature": "uipath-dev",
                "X-UiPath-LlmGateway-ApiFlavor": "auto",
            },
            http_client=httpx.AsyncClient(
                transport=_make_rewrite_transport(completions_url),
            ),
        )

    def _get_responses_client(self) -> Any:
        """Lazy-create and return the Responses API client."""
        if self._responses_client is None:
            self._responses_client = self._create_responses_client(self._model)
        return self._responses_client

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0,
    ) -> ModelResponse:
        """Non-streaming completion (used for compaction)."""
        if _is_reasoning_model(model):
            return await self._complete_responses(
                messages, tools, model=model, max_tokens=max_tokens
            )
        return await self._complete_chat(
            messages, tools, model=model, max_tokens=max_tokens, temperature=temperature
        )

    async def _complete_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0,
    ) -> ModelResponse:
        """Non-streaming completion via Chat Completions API."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self._completions_client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                )

        usage = None
        if response.usage:
            usage = Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )

        return ModelResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            thinking=None,
            finish_reason=choice.finish_reason or "",
            usage=usage,
        )

    async def _complete_responses(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        """Non-streaming completion via Responses API (reasoning models)."""
        client = self._get_responses_client()
        input_items = self._convert_messages_to_input(messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "input": input_items,
            "max_output_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = self._convert_tools_to_responses(tools)

        response = await client.responses.create(**kwargs)

        content = ""
        tool_calls = []
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        content += part.text
            elif item.type == "function_call":
                tool_calls.append(
                    ToolCall(
                        id=item.call_id,
                        name=item.name,
                        arguments=item.arguments,
                    )
                )

        usage = None
        if response.usage:
            usage = Usage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
            )

        finish = "tool_calls" if tool_calls else "stop"
        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            thinking=None,
            finish_reason=finish,
            usage=usage,
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0,
    ) -> AsyncIterator[StreamEvent]:
        """Streaming completion yielding StreamEvent objects."""
        if _is_reasoning_model(model):
            async for event in self._stream_responses(
                messages, tools, model=model, max_tokens=max_tokens
            ):
                yield event
            return

        # --- Chat Completions API (non-reasoning models) ---
        async for event in self._stream_completions(
            messages, tools, model=model, max_tokens=max_tokens, temperature=temperature
        ):
            yield event

    async def _stream_completions(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0,
    ) -> AsyncIterator[StreamEvent]:
        """Stream via Chat Completions API."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = await self._completions_client.chat.completions.create(**kwargs)

        pending_tool_calls: dict[int, dict[str, str]] = {}
        finish_reason = ""
        usage: Usage | None = None

        async for chunk in stream:
            if chunk.usage:
                usage = Usage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                )
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason

            if delta.content:
                yield StreamEvent(type="text_delta", delta=delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in pending_tool_calls:
                        pending_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "name": (
                                tc_delta.function.name
                                if tc_delta.function and tc_delta.function.name
                                else ""
                            ),
                            "arguments": "",
                        }
                    tc_data = pending_tool_calls[idx]
                    if tc_delta.id:
                        tc_data["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_data["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_data["arguments"] += tc_delta.function.arguments

        for _idx in sorted(pending_tool_calls):
            tc_data = pending_tool_calls[_idx]
            yield StreamEvent(
                type="tool_call",
                tool_call=ToolCall(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    arguments=tc_data["arguments"],
                ),
            )

        yield StreamEvent(type="done", finish_reason=finish_reason, usage=usage)

    # ------------------------------------------------------------------
    # Responses API streaming (reasoning models)
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_messages_to_input(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert Chat Completions messages to Responses API input format."""
        result: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            if role == "tool":
                result.append(
                    {
                        "type": "function_call_output",
                        "call_id": msg["tool_call_id"],
                        "output": msg.get("content", ""),
                    }
                )
            elif role == "assistant" and msg.get("tool_calls"):
                if msg.get("content"):
                    result.append({"role": "assistant", "content": msg["content"]})
                for tc in msg["tool_calls"]:
                    func = tc.get("function", {})
                    result.append(
                        {
                            "type": "function_call",
                            "call_id": tc["id"],
                            "name": func["name"],
                            "arguments": func.get("arguments", "{}"),
                        }
                    )
            else:
                result.append(msg)
        return result

    @staticmethod
    def _convert_tools_to_responses(
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert Chat Completions tool schemas to Responses API format."""
        result: list[dict[str, Any]] = []
        for t in tools:
            func = t.get("function", {})
            result.append(
                {
                    "type": "function",
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                }
            )
        return result

    async def _stream_responses(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamEvent]:
        """Stream via Responses API — gives us reasoning summaries."""
        client = self._get_responses_client()

        input_items = self._convert_messages_to_input(messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "input": input_items,
            "max_output_tokens": max_tokens,
            "reasoning": {"summary": "auto"},
            "stream": True,
        }
        if tools:
            kwargs["tools"] = self._convert_tools_to_responses(tools)

        stream = await client.responses.create(**kwargs)

        usage: Usage | None = None
        has_tool_calls = False

        async for event in stream:
            event_type = event.type

            # Text content delta
            if event_type == "response.output_text.delta":
                yield StreamEvent(type="text_delta", delta=event.delta)

            # Reasoning summary delta
            elif event_type == "response.reasoning_summary_text.delta":
                yield StreamEvent(type="thinking_delta", delta=event.delta)

            # Function call completed — emit as tool_call
            elif event_type == "response.output_item.done":
                item = event.item
                if item.type == "function_call":
                    has_tool_calls = True
                    yield StreamEvent(
                        type="tool_call",
                        tool_call=ToolCall(
                            id=item.call_id,
                            name=item.name,
                            arguments=item.arguments,
                        ),
                    )

            # Response completed — extract usage
            elif event_type == "response.completed":
                resp = event.response
                if resp.usage:
                    usage = Usage(
                        prompt_tokens=resp.usage.input_tokens,
                        completion_tokens=resp.usage.output_tokens,
                    )

        # Match Chat Completions convention: "tool_calls" when tools were
        # invoked, "stop" otherwise. The loop uses this to decide whether
        # to execute tools or finish.
        finish = "tool_calls" if has_tool_calls else "stop"
        yield StreamEvent(type="done", finish_reason=finish, usage=usage)


def create_provider(model: str) -> OpenAIProvider:
    """Factory to create the default provider for a model."""
    return OpenAIProvider(model)
