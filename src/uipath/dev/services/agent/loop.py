"""Core agentic loop with streaming, parallel tools, retry, sub-agent dispatch."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import platform
import sys
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from uipath.dev.services.agent.context import maybe_compact, prune_stale_tool_results
from uipath.dev.services.agent.events import (
    AgentEvent,
    ErrorOccurred,
    PlanUpdated,
    StatusChanged,
    TextDelta,
    TextGenerated,
    ThinkingGenerated,
    TokenUsageUpdated,
    ToolApprovalRequired,
    ToolCompleted,
    ToolStarted,
    UserQuestionAsked,
)
from uipath.dev.services.agent.provider import ModelProvider, StreamEvent, ToolCall
from uipath.dev.services.agent.session import AgentSession
from uipath.dev.services.agent.tools import ToolDefinition

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 30
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
SUB_AGENT_MAX_ITERATIONS = 15
_LOOP_WINDOW_SIZE = 6
_LOOP_THRESHOLD = 3
_MID_RUN_CHECKPOINT = 15

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_OS_LABEL = (
    "Windows"
    if sys.platform == "win32"
    else ("macOS" if sys.platform == "darwin" else "Linux")
)
_SHELL_HINT = (
    "The `bash` tool runs commands via `cmd.exe` (shell=True). "
    "Use Windows-compatible commands (e.g., `dir` instead of `ls`, `type` instead of `cat`, "
    "backslashes in paths). PowerShell and cmd builtins are available."
    if sys.platform == "win32"
    else "Standard Unix shell commands are available (ls, cat, etc.)."
)

SYSTEM_PROMPT = f"""\
You are a senior Python developer specializing in UiPath coded agents and automations. \
You help users build, debug, test, and improve Python agents using the UiPath SDK.

## Environment
- **OS**: {_OS_LABEL} ({platform.platform()})
- **Shell**: {_SHELL_HINT}

## Critical Rules

### Use the Shell for Real Commands
- NEVER tell the user to run commands themselves. ALWAYS use `bash` to execute commands directly.
- Use `bash` for: `uv run`, `uv sync`, `uipath init/run/eval/pack/publish`, installing deps, running tests/linters.
- Do NOT use `bash` to run exploratory Python scripts. Use `read_file`, `glob`, `grep` to understand code.
- Do NOT use `bash` to trial-and-error code logic. Write correct code using `edit_file`/`write_file`.
- The user is already authenticated — NEVER ask them to authenticate or run `uipath auth`.

### Stay Focused
- Solve exactly what was asked. Don't research tangential topics.
- If you need info, use read_file/glob/grep — don't run exploratory scripts.
- If you're past turn 5 without making an edit, you're over-exploring. Start implementing.
- Don't read library source code in .venv unless absolutely necessary. Read docs or the user's code instead.
- NEVER run a Python script just to "test" or "explore" how a library works. Read the user's existing code and edit it.

### Read Before Writing
- NEVER suggest code changes without first reading the relevant source files.
- NEVER assume what code looks like — use `read_file`, `glob`, and `grep` to verify.
- When asked about a function or class, read its implementation first. Do not guess signatures, return types, or behavior.
- Before editing a file, always read it to understand context, imports, and conventions.

### Evidence-Based Responses
- Ground every suggestion in actual code you have read in the current session.
- When explaining behavior, quote or reference specific lines from the codebase.
- If you're unsure about something, search the code rather than speculating.
- If you cannot find what you need, say so explicitly instead of making assumptions.

### Surgical, Minimal Changes
- Make the smallest change that solves the problem. Don't refactor adjacent code.
- Match the existing code style — indentation, naming conventions, import patterns.
- Only add imports, variables, or functions that your change requires.
- Don't add error handling, type hints, or docstrings beyond what was asked.

## Workflow

1. **Plan first**: Use `create_task` to add individual steps before doing anything else.
2. **Explore**: Use `list_files` to understand project structure, then `glob` and `grep` to find specific files. Read them with `read_file`.
3. **Implement**: Use `edit_file` for targeted changes, `write_file` only for new files.
4. **Execute**: Use `bash` to run commands — installations, tests, linters, builds, `uv run` commands, etc.
5. **Verify**: Read back edited files to confirm correctness. Run tests or linters via `bash`.
6. **Update progress**: When starting a step, call `update_task` to set it to "in_progress". \
After completing each step, call `update_task` to mark it "completed" BEFORE moving on.
7. **Before your final response**: Mark all remaining tasks as "completed". \
NEVER give your final summary without first ensuring every task is marked completed.
8. **Summarize**: When done, briefly state what you changed and why.

**Batch tool calls**: When multiple operations are independent (e.g., reading several files, creating \
multiple tasks, running searches), call them all in a single response to minimize round trips.

## Proportional Response
Assess task scope BEFORE planning:
- **Simple** (restructure code, rename, fix a bug, add a parameter): Read the file → edit it → done. 1-2 tasks max. No research phase.
- **Moderate** (add a new tool, refactor a module, create a sub-agent): Plan → implement → test. 3-5 tasks max.
- **Full build** (new agent from scratch with evals): Full workflow below. Up to 10 tasks.

MOST tasks are simple. Default to simple unless the task clearly requires more. \
If you can do it in 2 steps, don't plan 8. If you can read 2 files, don't read 10.

## Full Build Cycle (New Agents Only)

When building a NEW agent or function from scratch, complete the full cycle:

1. **Write the code** — implement the agent/function with Input/Output models and `@traced()` main function.
2. **Generate entry points** — run `uv run uipath init` via `bash`.
3. **Write evaluations** — create BOTH:
   - **Evaluator files** in `evaluations/evaluators/` (e.g. `exact-match.json`, `json-similarity.json`) — these must exist first.
   - **Eval set files** in `evaluations/eval-sets/` with test cases that reference the evaluator IDs.
4. **Run the evaluations** — execute `uv run uipath eval <name> <eval-file>` via `bash` and report results. \
The `<name>` is the agent key from the active framework config. The `<eval-file>` is the path to the eval set JSON.
5. **Pack & publish** — when the user asks to deploy, run via `bash`:
   - `uv run uipath pack` — create a .nupkg package
   - `uv run uipath publish -w` — publish to personal workspace (default)
   - `uv run uipath publish -t` — publish to a specific tenant folder

When modifying existing code, only create/run evals if the user asks. \
If you create eval sets, you must also create the evaluator files they reference — otherwise the eval run will fail. \
Default to publishing to personal workspace (`-w`) unless the user specifies a tenant folder.

## UiPath Project Structure

A typical UiPath Python project has:
- `main.py` or `src/<name>/main.py` — agent/function entry point (can be at root or in src/)
- **Framework config** — one of these registers agents/functions (check which one has `"agents"` or `"functions"` keys):
  - `uipath.json`, `pydantic_ai.json`, `langgraph.json`, `llama_index.json`, `google_adk.json`, `openai_agents.json`
  - Format: `{{"agents": {{"name": "file.py:func"}}}}` — the key is the agent name used in CLI commands
- `pyproject.toml` — Python dependencies (managed via `uv`)
- `bindings.json` — UiPath resource bindings (queues, buckets)
- `evaluations/` — test suites
  - `eval-sets/` — JSON test case files (inputs + expected outputs)
  - `evaluators/` — JSON evaluator definition files
- `entry-points.json` — auto-generated by `uv run uipath init`
- `src/` — alternative location for agent/function source code

IMPORTANT: A project may have multiple config files (e.g. both `uipath.json` and `pydantic_ai.json`). \
Only the one with non-empty `"agents"` or `"functions"` is the active framework config. \
NEVER add agents to the wrong config file — check the Current Project section to see which config is active.

## Search Strategy

- When searching Python code, ALWAYS use `include: '*.py'` with grep
- Use `glob` to discover file structure first, then `grep` for content
- Start with targeted searches (specific filenames, class names) before broad patterns
- For evaluations: look in `evaluations/eval-sets/` and `evaluations/evaluators/`
- For agent code: check the active framework config (shown in Current Project) to find entry points, then look in both root and `src/` for Python files
- Check `pyproject.toml` for dependencies and project name
- NEVER search without a file type filter — it wastes time on binary/generated files

## Debugging

When `uv run uipath eval` fails or all scores come back 0.0, the function likely crashed — not wrong logic.

### Triage Steps
1. **Run the function standalone first**: `uv run uipath run <name> '<json-input>'` with a sample input from the eval set.
2. **Read the bottom of the traceback** — the last exception is the root cause.
3. **Re-run `uv run uipath init`** after changing Input/Output models to regenerate `entry-points.json`.

### Common Error Patterns
- **Score 0.0 on ALL evals**: function crashed, not wrong logic. The evaluator got `{{}}` because the function errored. Run standalone to see the real error.
- **`ModuleNotFoundError`**: missing dependency — add it to `pyproject.toml` and run `uv sync`.
- **`KeyError` or empty output in evaluator**: function returned `{{}}` instead of expected output — the function errored, not the evaluator.
- **Schema mismatch / wrong input shape**: stale `entry-points.json` — run `uv run uipath init`.
- **`from __future__ import annotations`**: this stringifies all annotations and breaks runtime type detection. Remove it if Input/Output models aren't being recognized.
- **Missing env vars**: check that required variables (`OPENAI_API_KEY`, etc.) are set in the environment.

## Tools
- `read_file` — Read file contents (always use before editing). Supports offset/limit for large files.
- `write_file` — Create or overwrite a file
- `edit_file` — Surgical string replacement (old_string must be unique)
- `bash` — Execute a shell command (timeout: 120s).
- `list_files` — List files/directories in a tree view (up to 3 levels deep). Use to understand project structure.
- `glob` — Find files matching a pattern (e.g. `**/*.py`). Excludes .venv, node_modules, __pycache__, .git.
- `grep` — Search file contents with regex. Excludes .venv, node_modules, __pycache__, .git.
- `create_task` — Add a new step to your task plan
- `update_task` — Update a task's status (pending → in_progress → completed) or title
- `list_tasks` — Show all tasks with their statuses
- `read_reference` — Read a reference doc from the active skill (when skills are active)
- `dispatch_agent` — Spawn a sub-agent to handle a subtask in its own context
- `ask_user` — Ask the user a question and wait for their answer
"""


async def _chain_async(
    first: StreamEvent, rest: AsyncIterator[StreamEvent]
) -> AsyncIterator[StreamEvent]:
    """Yield first, then yield from rest."""
    yield first
    async for item in rest:
        yield item


async def _empty_async_iter() -> AsyncIterator[StreamEvent]:
    """Return an empty async iterator."""
    if False:  # noqa: SIM108 — needed to make this an async generator
        yield StreamEvent(type="done")


SUB_AGENT_PROMPT = """\
You are a research sub-agent with read-only access to the codebase.

## Your Task
Complete the research task described in the user message below.

## Output Format
Return a structured summary with:
- **Findings**: Key facts, code locations, and patterns discovered
- **File paths**: List every relevant file path you found (with line numbers if applicable)
- **Answer**: A direct, concise answer to the question asked

## Guidelines
- Be thorough: check multiple files, search for patterns, verify assumptions
- Be concise: your full response goes back to the parent agent's context window
- Keep your response under 2000 chars — focus on what matters
- If you can't find something, say so explicitly rather than guessing
- When searching code, always use `include: '*.py'` with grep
- Focus on evaluations/ directory for test-related files
- Check uipath.json and main.py for agent entry points
"""


class AgentLoop:
    """The core agentic loop with all innovations."""

    def __init__(  # noqa: D107
        self,
        *,
        provider: ModelProvider,
        tools: list[ToolDefinition],
        emit: Callable[[AgentEvent], None],
        max_iterations: int = MAX_ITERATIONS,
        allow_dispatch: bool = True,
        # Approval support
        pending_approvals: dict[str, asyncio.Event] | None = None,
        approval_results: dict[str, bool] | None = None,
        # Question support
        pending_questions: dict[str, asyncio.Event] | None = None,
        question_results: dict[str, str] | None = None,
        # Skill support
        skill_service: Any | None = None,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.emit = emit
        self.max_iterations = max_iterations
        self.allow_dispatch = allow_dispatch
        self._pending_approvals = (
            pending_approvals if pending_approvals is not None else {}
        )
        self._approval_results = (
            approval_results if approval_results is not None else {}
        )
        self._pending_questions = (
            pending_questions if pending_questions is not None else {}
        )
        self._question_results = (
            question_results if question_results is not None else {}
        )
        self._skill_service = skill_service

    async def run(self, session: AgentSession, system_prompt: str) -> None:
        """Run the agent loop until completion or max iterations."""
        try:
            # Build tool schemas — sorted for stable prefix ordering (prompt caching)
            tool_schemas = sorted(
                [t.to_openai_schema() for t in self.tools],
                key=lambda t: t["function"]["name"],
            )

            tool_map = {t.name: t for t in self.tools}
            recent_tool_calls: list[str] = []
            total_edit_calls = 0
            total_exploration_calls = 0
            _EXPLORATION_TOOLS = frozenset(
                {"read_file", "grep", "glob", "list_files", "bash"}
            )
            _EDIT_TOOLS = frozenset({"edit_file", "write_file"})

            for _iteration in range(self.max_iterations):
                if session._cancel_event.is_set():
                    session.status = "done"
                    self.emit(StatusChanged(session.id, status="done"))
                    return

                # Prune stale tool results before each LLM call
                prune_stale_tool_results(session)

                # Check if compaction is needed
                compacted = await maybe_compact(session, self.provider, system_prompt)
                if compacted and session.tasks:
                    task_lines = []
                    for tid, task in session.tasks.items():
                        task_lines.append(
                            f"  [{tid}] ({task['status']}) {task['title']}"
                        )
                    pending = [
                        t for t in session.tasks.values() if t["status"] != "completed"
                    ]
                    if pending:
                        session.messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Context was compacted. Continue with the remaining tasks.\n\n"
                                    "Current task state:\n" + "\n".join(task_lines)
                                ),
                            }
                        )

                # Build messages with stable prefix
                llm_messages = [
                    {"role": "system", "content": system_prompt},
                    *session.messages,
                ]

                # --- Trace: snapshot start ---
                span_start = time.monotonic()
                span_input_messages: list[dict[str, Any]] = []
                for m in llm_messages:
                    if m.get("role") == "system":
                        continue
                    entry: dict[str, Any] = {
                        "role": m.get("role", ""),
                        "content": (m.get("content") or "")[:500],
                    }
                    # Preserve tool_calls on assistant messages
                    if m.get("tool_calls"):
                        entry["tool_calls"] = [
                            {
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": tc.get("function", {}).get(
                                    "arguments", ""
                                )[:200],
                            }
                            for tc in m["tool_calls"]
                        ]
                    # Preserve tool_call_id on tool result messages
                    if m.get("role") == "tool" and m.get("tool_call_id"):
                        entry["tool_call_id"] = m["tool_call_id"]
                    span_input_messages.append(entry)

                # Stream the response
                accumulated_content = ""
                accumulated_thinking = ""
                tool_calls: list[ToolCall] = []
                finish_reason = ""
                span_prompt_tokens = 0
                span_completion_tokens = 0

                stream = await self._call_model_with_retry(
                    llm_messages, tool_schemas, session
                )
                async for event in stream:
                    match event.type:
                        case "text_delta":
                            self.emit(TextDelta(session.id, delta=event.delta))
                            accumulated_content += event.delta
                        case "thinking_delta":
                            self.emit(
                                ThinkingGenerated(session.id, content=event.delta)
                            )
                            accumulated_thinking += event.delta
                        case "tool_call":
                            if event.tool_call:
                                tool_calls.append(event.tool_call)
                        case "done":
                            finish_reason = event.finish_reason
                            # Track token usage
                            if event.usage:
                                span_prompt_tokens = event.usage.prompt_tokens
                                span_completion_tokens = event.usage.completion_tokens
                                session.total_prompt_tokens += span_prompt_tokens
                                session.total_completion_tokens += (
                                    span_completion_tokens
                                )
                                session.turn_count += 1
                                self.emit(
                                    TokenUsageUpdated(
                                        session.id,
                                        prompt_tokens=span_prompt_tokens,
                                        completion_tokens=span_completion_tokens,
                                        total_session_tokens=session.total_prompt_tokens
                                        + session.total_completion_tokens,
                                    )
                                )

                span_duration_ms = int((time.monotonic() - span_start) * 1000)

                # Build assistant message for conversation history
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": accumulated_content,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": tc.arguments,
                            },
                        }
                        for tc in tool_calls
                    ]
                session.messages.append(assistant_msg)

                # --- Trace: build span ---
                span: dict[str, Any] = {
                    "turn_index": _iteration,
                    "input_messages": span_input_messages,
                    "output_content": accumulated_content,
                    "output_tool_calls": [
                        {"name": tc.name, "arguments": tc.arguments}
                        for tc in tool_calls
                    ],
                    "prompt_tokens": span_prompt_tokens,
                    "completion_tokens": span_completion_tokens,
                    "duration_ms": span_duration_ms,
                    "model": session.model,
                    "status": "completed",
                }
                if accumulated_thinking:
                    span["output_thinking"] = accumulated_thinking

                # If no tool calls, we're done
                if finish_reason == "stop" or not tool_calls:
                    session.traces.append(span)
                    # Content already streamed via TextDelta — just mark done
                    self._complete_remaining_tasks(session)
                    self.emit(TextGenerated(session.id, content="", done=True))
                    session.status = "done"
                    self.emit(StatusChanged(session.id, status="done"))
                    return

                # Execute tool calls (parallel where possible)
                await self._execute_tools_parallel(tool_calls, session, tool_map)

                # --- Trace: attach tool results ---
                tool_results_for_span: list[dict[str, Any]] = []
                for tc in tool_calls:
                    # Find the matching tool result in session.messages
                    for msg in reversed(session.messages):
                        if (
                            msg.get("role") == "tool"
                            and msg.get("tool_call_id") == tc.id
                        ):
                            tool_results_for_span.append(
                                {
                                    "tool_call_id": tc.id,
                                    "name": tc.name,
                                    "result": msg.get("content", ""),
                                }
                            )
                            break
                span["tool_results"] = tool_results_for_span
                session.traces.append(span)

                # --- Track tool usage stats ---
                for tc in tool_calls:
                    if tc.name in _EDIT_TOOLS:
                        total_edit_calls += 1
                    if tc.name in _EXPLORATION_TOOLS:
                        total_exploration_calls += 1
                    sig = (
                        tc.name
                        + ":"
                        + hashlib.md5(tc.arguments.encode()).hexdigest()[:8]
                    )
                    recent_tool_calls.append(sig)
                recent_tool_calls = recent_tool_calls[-_LOOP_WINDOW_SIZE:]

                # --- Loop detection: repeated similar calls ---
                unique_recent = set(recent_tool_calls)
                if (
                    len(recent_tool_calls) >= _LOOP_WINDOW_SIZE
                    and len(unique_recent) <= len(recent_tool_calls) // 2
                ):
                    session.messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You're repeating similar tool calls in a loop. "
                                "STOP exploring and START making changes. "
                                "What's the simplest edit to complete the task?"
                            ),
                        }
                    )

                # --- Productivity check: too much exploration, too few edits ---
                if (
                    _iteration >= 8
                    and total_edit_calls == 0
                    and total_exploration_calls >= 6
                ):
                    session.messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"You've used {total_exploration_calls} "
                                "exploration calls and made 0 edits after "
                                f"{_iteration + 1} turns. You have enough "
                                "context — make the edit NOW."
                            ),
                        }
                    )

                # --- Mid-run self-reflection checkpoint ---
                if _iteration == _MID_RUN_CHECKPOINT:
                    session.messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Turn {_iteration + 1}/{self.max_iterations}. "
                                f"Edits made: {total_edit_calls}. "
                                f"Exploration calls: {total_exploration_calls}. "
                                "You're halfway through your turn budget. "
                                "If you haven't made the core change yet, do it NOW. "
                                "Simplify your approach."
                            ),
                        }
                    )

                # After tools, set status back to thinking
                self.emit(StatusChanged(session.id, status="thinking"))

            # Max iterations reached
            self._complete_remaining_tasks(session)
            self.emit(
                TextGenerated(
                    session.id,
                    content="Reached maximum iterations. Stopping.",
                    done=True,
                )
            )
            session.status = "done"
            self.emit(StatusChanged(session.id, status="done"))

        except asyncio.CancelledError:
            self._complete_remaining_tasks(session)
            session.status = "done"
            self.emit(StatusChanged(session.id, status="done"))
        except Exception as e:
            logger.exception("Agent loop error for session %s", session.id)
            session.status = "error"
            self.emit(ErrorOccurred(session.id, message=str(e)))

    async def _call_model_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        session: AgentSession,
    ) -> AsyncIterator[StreamEvent]:
        """Call the model with retry on transient errors.

        Retries only apply to connection/API errors before streaming starts.
        Once streaming begins, errors are propagated directly.
        """
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                stream = self.provider.stream(
                    messages,
                    tools,
                    model=session.model,
                    max_tokens=4096,
                    temperature=0,
                )
                # Try to get the first event to detect connection errors early
                first = await stream.__anext__()
                # Success — chain first event with the rest
                return _chain_async(first, stream)
            except StopAsyncIteration:
                return _empty_async_iter()
            except Exception as e:
                last_error = e
                if attempt == MAX_RETRIES or not self._is_retryable(e):
                    raise
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "Retrying model call (attempt %d/%d) after %.1fs: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)
        raise last_error  # type: ignore[misc]

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        """Check if error is transient (rate limit, timeout, 5xx)."""
        err_str = str(error).lower()
        return any(
            k in err_str for k in ("rate limit", "timeout", "429", "500", "502", "503")
        )

    async def _execute_tools_parallel(
        self,
        tool_calls: list[ToolCall],
        session: AgentSession,
        tool_map: dict[str, ToolDefinition],
    ) -> None:
        """Execute tool calls — approval sequentially, execution in parallel."""
        self.emit(StatusChanged(session.id, status="executing"))

        # Phase 1: Handle approval + special tools; collect tasks for parallel exec
        tasks: list[tuple[ToolCall, asyncio.Task[str] | str | None]] = []

        for tc in tool_calls:
            if session._cancel_event.is_set():
                session.status = "done"
                self.emit(StatusChanged(session.id, status="done"))
                return

            tool_name = tc.name
            try:
                tool_args = json.loads(tc.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            tool_def = tool_map.get(tool_name)

            # Handle task tools specially (no approval, immediate)
            if tool_name in ("create_task", "update_task", "list_tasks"):
                result = self._handle_task_tool(session, tool_name, tool_args)
                tasks.append((tc, result))
                continue

            # Handle read_reference specially
            if tool_name == "read_reference":
                result = self._handle_read_reference(session, tool_args)
                self.emit(
                    ToolStarted(
                        session.id, tool_call_id=tc.id, tool=tool_name, args=tool_args
                    )
                )
                is_error = result.startswith("Error:")
                self.emit(
                    ToolCompleted(
                        session.id,
                        tool_call_id=tc.id,
                        tool=tool_name,
                        result=result,
                        is_error=is_error,
                    )
                )
                tasks.append((tc, result))
                continue

            # Handle dispatch_agent specially
            if tool_name == "dispatch_agent" and self.allow_dispatch:
                self.emit(
                    ToolStarted(
                        session.id, tool_call_id=tc.id, tool=tool_name, args=tool_args
                    )
                )
                result = await self._handle_dispatch_agent(
                    tool_args.get("task", ""), session
                )
                self.emit(
                    ToolCompleted(
                        session.id,
                        tool_call_id=tc.id,
                        tool=tool_name,
                        result=result,
                        is_error=False,
                    )
                )
                tasks.append((tc, result))
                continue

            # Handle ask_user specially — blocks until user responds
            if tool_name == "ask_user":
                result = await self._handle_ask_user(session, tool_args)
                tasks.append((tc, result))
                continue

            self.emit(
                ToolStarted(
                    session.id, tool_call_id=tc.id, tool=tool_name, args=tool_args
                )
            )

            # Approval gate for destructive tools (sequential for UX clarity)
            if tool_def and tool_def.requires_approval:
                approval_event = asyncio.Event()
                self._pending_approvals[tc.id] = approval_event
                self.emit(
                    ToolApprovalRequired(
                        session.id,
                        tool_call_id=tc.id,
                        tool=tool_name,
                        args=tool_args,
                    )
                )
                self.emit(StatusChanged(session.id, status="awaiting_approval"))
                await approval_event.wait()
                approved = self._approval_results.pop(tc.id, False)
                self._pending_approvals.pop(tc.id, None)

                if session._cancel_event.is_set():
                    session.status = "done"
                    self.emit(StatusChanged(session.id, status="done"))
                    return

                if not approved:
                    result = "Tool execution denied by user"
                    self.emit(StatusChanged(session.id, status="executing"))
                    self.emit(
                        ToolCompleted(
                            session.id,
                            tool_call_id=tc.id,
                            tool=tool_name,
                            result=result,
                            is_error=True,
                        )
                    )
                    tasks.append((tc, result))
                    continue

                self.emit(StatusChanged(session.id, status="executing"))

            # Queue for parallel execution
            tasks.append((tc, None))  # None = needs execution

        # Phase 2: Execute all pending tools in parallel
        exec_tasks: list[tuple[int, asyncio.Task[str]]] = []
        for i, (tc_item, res_item) in enumerate(tasks):
            if res_item is not None:
                continue  # Already handled
            tool_def = tool_map.get(tc_item.name)
            if tool_def:
                try:
                    tool_args = json.loads(tc_item.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                exec_task = asyncio.create_task(
                    self._execute_single_tool(tool_def, tool_args)
                )
                exec_tasks.append((i, exec_task))
            else:
                tasks[i] = (tc_item, f"Error: unknown tool '{tc_item.name}'")

        if exec_tasks:
            gather_results = await asyncio.gather(
                *[t for _, t in exec_tasks], return_exceptions=True
            )
            for (idx, _), gather_result in zip(exec_tasks, gather_results, strict=True):
                tc_done = tasks[idx][0]
                if isinstance(gather_result, BaseException):
                    result_str = f"Error: {gather_result}"
                    is_error = True
                else:
                    result_str = gather_result
                    is_error = result_str.startswith("Error:")
                tasks[idx] = (tc_done, result_str)
                self.emit(
                    ToolCompleted(
                        session.id,
                        tool_call_id=tc_done.id,
                        tool=tc_done.name,
                        result=result_str,
                        is_error=is_error,
                    )
                )

        # Phase 3: Append all tool results to session messages in order
        for tc_final, result_final in tasks:
            session.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_final.id,
                    "content": result_final or "",
                }
            )

    @staticmethod
    async def _execute_single_tool(
        tool_def: ToolDefinition, args: dict[str, Any]
    ) -> str:
        """Execute a single tool in a thread executor."""
        return await asyncio.get_event_loop().run_in_executor(
            None, tool_def.handler, args
        )

    def _handle_task_tool(
        self, session: AgentSession, tool_name: str, args: dict[str, Any]
    ) -> str:
        """Handle create_task, update_task, and list_tasks."""
        if tool_name == "create_task":
            return self._handle_create_task(session, args)
        if tool_name == "update_task":
            return self._handle_update_task(session, args)
        return self._handle_list_tasks(session)

    def _handle_create_task(self, session: AgentSession, args: dict[str, Any]) -> str:
        title = args.get("title", "").strip()
        if not title:
            return "Error: title is required"
        # Clear completed plan when starting a new one
        if session.tasks and all(
            t["status"] == "completed" for t in session.tasks.values()
        ):
            session.tasks.clear()
            session._next_task_id = 1
        task_id = str(session._next_task_id)
        session._next_task_id += 1
        session.tasks[task_id] = {
            "title": title,
            "status": "pending",
            "description": args.get("description", ""),
        }
        self._emit_plan_from_tasks(session)
        return f"Task {task_id} created"

    def _handle_update_task(self, session: AgentSession, args: dict[str, Any]) -> str:
        task_id = args.get("task_id", "")
        if task_id not in session.tasks:
            return f"Error: task {task_id} not found"
        status = args.get("status", "")
        if status:
            if status not in ("pending", "in_progress", "completed"):
                return f"Error: invalid status '{status}'"
            session.tasks[task_id]["status"] = status
        new_title = args.get("title")
        if new_title:
            session.tasks[task_id]["title"] = new_title
        self._emit_plan_from_tasks(session)
        return f"Task {task_id} updated"

    def _handle_list_tasks(self, session: AgentSession) -> str:
        if not session.tasks:
            return "No tasks yet."
        lines: list[str] = []
        for tid, task in session.tasks.items():
            lines.append(f"[{tid}] ({task['status']}) {task['title']}")
        return "\n".join(lines)

    def _complete_remaining_tasks(self, session: AgentSession) -> None:
        """Mark any non-completed tasks as completed when the turn ends."""
        changed = False
        for task in session.tasks.values():
            if task["status"] != "completed":
                task["status"] = "completed"
                changed = True
        if changed:
            self._emit_plan_from_tasks(session)

    def _emit_plan_from_tasks(self, session: AgentSession) -> None:
        """Convert tasks dict to plan items list and emit PlanUpdated."""
        items = [
            {"title": t["title"], "status": t["status"]} for t in session.tasks.values()
        ]
        session.plan = items
        self.emit(PlanUpdated(session.id, items=items))

    def _handle_read_reference(
        self, session: AgentSession, args: dict[str, Any]
    ) -> str:
        """Read a reference file using the base from active skills."""
        from uipath.dev.services.agent.tools import MAX_FILE_CHARS

        ref_path = args.get("path", "")
        if not ref_path or not self._skill_service or not session.skill_ids:
            return "Error: no active skills or missing path"
        base_skill_id = session.skill_ids[0]
        try:
            content = self._skill_service.get_reference(base_skill_id, ref_path)
            if len(content) > MAX_FILE_CHARS:
                content = (
                    content[:MAX_FILE_CHARS]
                    + f"\n... [truncated at {MAX_FILE_CHARS} chars]"
                )
            return content
        except (FileNotFoundError, PermissionError) as e:
            return f"Error: {e}"

    async def _handle_dispatch_agent(
        self, task: str, parent_session: AgentSession
    ) -> str:
        """Run a sub-agent with isolated context and return its result."""
        from uipath.dev.services.agent.tools import create_read_reference_tool

        child_session = AgentSession(model=parent_session.model)
        child_session.messages.append({"role": "user", "content": task})

        # Read-only tools only, no dispatch_agent or ask_user
        child_tools = [
            t
            for t in self.tools
            if not t.requires_approval
            and t.name
            not in (
                "dispatch_agent",
                "ask_user",
                "create_task",
                "update_task",
                "list_tasks",
            )
        ]

        # Give sub-agent read_reference when skills are active
        has_read_ref = any(t.name == "read_reference" for t in child_tools)
        if not has_read_ref and parent_session.skill_ids and self._skill_service:
            child_tools.append(create_read_reference_tool())

        # Build sub-agent system prompt with skill context
        sub_prompt = SUB_AGENT_PROMPT
        if parent_session.skill_ids and self._skill_service:
            for sid in parent_session.skill_ids:
                try:
                    summary = self._skill_service.get_skill_summary(sid)
                    sub_prompt += f"\n\n## Skill Context: {sid}\n{summary}"
                except FileNotFoundError:
                    pass

        child_loop = AgentLoop(
            provider=self.provider,
            tools=child_tools,
            emit=lambda _e: None,  # Sub-agent events are silent
            max_iterations=SUB_AGENT_MAX_ITERATIONS,
            allow_dispatch=False,
            skill_service=self._skill_service,
        )
        await child_loop.run(child_session, system_prompt=sub_prompt)

        # Extract final assistant message
        for msg in reversed(child_session.messages):
            if msg["role"] == "assistant" and msg.get("content"):
                return msg["content"]
        return "Sub-agent completed without producing a response."

    async def _handle_ask_user(
        self, session: AgentSession, args: dict[str, Any]
    ) -> str:
        """Emit a question event and block until the user responds."""
        import uuid as _uuid

        question = args.get("question", "")
        options = args.get("options", [])
        if not question:
            return "Error: question is required"

        question_id = str(_uuid.uuid4())
        wait_event = asyncio.Event()
        self._pending_questions[question_id] = wait_event

        self.emit(
            UserQuestionAsked(
                session.id,
                question_id=question_id,
                question=question,
                options=options if isinstance(options, list) else [],
            )
        )
        self.emit(StatusChanged(session.id, status="awaiting_input"))

        await wait_event.wait()

        answer = self._question_results.pop(question_id, "")
        self._pending_questions.pop(question_id, None)

        self.emit(StatusChanged(session.id, status="thinking"))
        return answer
