"""Coding agent service — native agent loop with UiPath OpenAI client + tools."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import os
import re
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from uipath.dev.services.skill_service import SkillService

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 50
MAX_OUTPUT_CHARS = 50_000
MAX_FILE_CHARS = 100_000
MAX_GLOB_RESULTS = 200
MAX_GREP_MATCHES = 100
BASH_TIMEOUT = 30
TOOLS_REQUIRING_APPROVAL = {"write_file", "edit_file", "bash"}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior Python developer specializing in UiPath coded agents and automations. \
You help users build, debug, test, and improve Python agents using the UiPath SDK.

## Core Principles

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

1. **Plan first**: Call `update_plan` with your steps before doing anything else.
2. **Explore**: Use `glob` and `grep` to find relevant files. Read them with `read_file`.
3. **Implement**: Use `edit_file` for targeted changes, `write_file` only for new files.
4. **Verify**: Read back edited files to confirm correctness. Run tests or linters via `bash` when appropriate.
5. **Update progress**: Mark plan steps as "completed" as you go, add new steps if scope expands.
6. **Summarize**: When done, briefly state what you changed and why.

## Tools
- `read_file` — Read file contents (always use before editing)
- `write_file` — Create or overwrite a file
- `edit_file` — Surgical string replacement (old_string must be unique)
- `bash` — Execute a shell command (timeout: 30s)
- `glob` — Find files matching a pattern (e.g. `**/*.py`)
- `grep` — Search file contents with regex
- `update_plan` — Create or update your task plan
- `read_reference` — Read a reference doc from the active skill (when skills are active)
"""

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute file path.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute file path.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full file content to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace an exact string in a file with a new string. The old_string must appear exactly once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute file path.",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to find and replace.",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The replacement string.",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a shell command and return stdout/stderr. Timeout: 30s.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Find files matching a glob pattern. Returns up to 200 results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern, e.g. '**/*.py' or 'src/**/*.ts'.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in. Defaults to project root.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search file contents with a regex pattern. Returns up to 100 matches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for.",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in. Defaults to project root.",
                    },
                    "include": {
                        "type": "string",
                        "description": "Glob filter for files, e.g. '*.py'.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_plan",
            "description": "Update the task plan. Call this first to outline steps, then update as you complete them.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "string",
                        "description": 'JSON array of plan items: [{"title": "...", "status": "pending|in_progress|completed"}]',
                    }
                },
                "required": ["plan"],
            },
        },
    },
]

READ_REFERENCE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_reference",
        "description": "Read a reference document from the skill's references directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path within the references/ directory, e.g. 'authentication.md' or 'evaluations/best-practices.md'.",
                },
            },
            "required": ["path"],
        },
    },
}


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class AgentSession:
    """In-memory state for one agent conversation."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model: str = ""
    skill_ids: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    plan: list[dict[str, str]] = field(default_factory=list)
    status: str = "idle"
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    _task: asyncio.Task[None] | None = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path.cwd().resolve()


def _resolve_safe(path_str: str) -> Path:
    """Resolve a path and ensure it stays within the project root."""
    p = Path(path_str)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    resolved = p.resolve()
    if not str(resolved).startswith(str(_PROJECT_ROOT)):
        raise PermissionError(f"Path escapes project root: {path_str}")
    return resolved


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _tool_read_file(args: dict[str, Any]) -> str:
    path = _resolve_safe(args["path"])
    if not path.is_file():
        return f"Error: file not found: {args['path']}"
    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content) > MAX_FILE_CHARS:
        content = (
            content[:MAX_FILE_CHARS] + f"\n... [truncated at {MAX_FILE_CHARS} chars]"
        )
    return content


def _tool_write_file(args: dict[str, Any]) -> str:
    path = _resolve_safe(args["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args["content"], encoding="utf-8")
    return f"File written: {args['path']} ({len(args['content'])} chars)"


def _tool_edit_file(args: dict[str, Any]) -> str:
    path = _resolve_safe(args["path"])
    if not path.is_file():
        return f"Error: file not found: {args['path']}"
    content = path.read_text(encoding="utf-8")
    old_string = args["old_string"]
    new_string = args["new_string"]
    count = content.count(old_string)
    if count == 0:
        return "Error: old_string not found in file"
    if count > 1:
        return f"Error: old_string found {count} times, must be unique"
    content = content.replace(old_string, new_string, 1)
    path.write_text(content, encoding="utf-8")
    return "Edit applied successfully"


def _tool_bash(args: dict[str, Any]) -> str:
    command = args["command"]
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=BASH_TIMEOUT,
            cwd=str(_PROJECT_ROOT),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n" if output else "") + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        if not output:
            output = "[no output]"
        if len(output) > MAX_OUTPUT_CHARS:
            output = (
                output[:MAX_OUTPUT_CHARS]
                + f"\n... [truncated at {MAX_OUTPUT_CHARS} chars]"
            )
        return output
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {BASH_TIMEOUT}s"
    except Exception as e:
        return f"Error: {e}"


def _tool_glob(args: dict[str, Any]) -> str:
    pattern = args["pattern"]
    base = _resolve_safe(args.get("path", "."))
    if not base.is_dir():
        return f"Error: directory not found: {args.get('path', '.')}"
    matches = sorted(base.glob(pattern))
    # Filter to project root
    matches = [m for m in matches if str(m.resolve()).startswith(str(_PROJECT_ROOT))]
    if len(matches) > MAX_GLOB_RESULTS:
        matches = matches[:MAX_GLOB_RESULTS]
        truncated = True
    else:
        truncated = False
    rel = [str(m.relative_to(_PROJECT_ROOT)) for m in matches]
    result = "\n".join(rel) if rel else "No matches found"
    if truncated:
        result += f"\n... [truncated at {MAX_GLOB_RESULTS} results]"
    return result


def _tool_grep(args: dict[str, Any]) -> str:
    pattern_str = args["pattern"]
    base = _resolve_safe(args.get("path", "."))
    include = args.get("include", None)
    try:
        regex = re.compile(pattern_str)
    except re.error as e:
        return f"Error: invalid regex: {e}"

    matches: list[str] = []
    files_to_search: list[Path] = []

    if base.is_file():
        files_to_search = [base]
    elif base.is_dir():
        for root, _dirs, filenames in os.walk(base):
            # Skip hidden dirs and common non-code dirs
            root_path = Path(root)
            parts = root_path.relative_to(base).parts
            if any(
                p.startswith(".") or p in ("node_modules", "__pycache__", ".venv")
                for p in parts
            ):
                continue
            for fname in filenames:
                if include and not fnmatch.fnmatch(fname, include):
                    continue
                files_to_search.append(root_path / fname)
    else:
        return f"Error: path not found: {args.get('path', '.')}"

    for fpath in files_to_search:
        if len(matches) >= MAX_GREP_MATCHES:
            break
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                rel = str(fpath.relative_to(_PROJECT_ROOT))
                matches.append(f"{rel}:{i}: {line.rstrip()}")
                if len(matches) >= MAX_GREP_MATCHES:
                    break

    result = "\n".join(matches) if matches else "No matches found"
    if len(matches) >= MAX_GREP_MATCHES:
        result += f"\n... [truncated at {MAX_GREP_MATCHES} matches]"
    return result


TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "read_file": _tool_read_file,
    "write_file": _tool_write_file,
    "edit_file": _tool_edit_file,
    "bash": _tool_bash,
    "glob": _tool_glob,
    "grep": _tool_grep,
}


# ---------------------------------------------------------------------------
# Agent service
# ---------------------------------------------------------------------------


class AgentService:
    """Manages agent sessions and runs the agent loop."""

    def __init__(
        self,
        *,
        skill_service: SkillService | None = None,
        on_status: Callable[[str, str], None] | None = None,
        on_text: Callable[[str, str, bool], None] | None = None,
        on_plan: Callable[[str, list[dict[str, str]]], None] | None = None,
        on_tool_use: Callable[[str, str, dict[str, Any]], None] | None = None,
        on_tool_result: Callable[[str, str, str, bool], None] | None = None,
        on_tool_approval: Callable[[str, str, str, dict[str, Any]], None] | None = None,
        on_error: Callable[[str, str], None] | None = None,
    ) -> None:
        """Initialize the agent service with event callbacks."""
        self._sessions: dict[str, AgentSession] = {}
        self._skill_service = skill_service
        self._on_status = on_status
        self._on_text = on_text
        self._on_plan = on_plan
        self._on_tool_use = on_tool_use
        self._on_tool_result = on_tool_result
        self._on_tool_approval = on_tool_approval
        self._on_error = on_error
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}

    def _get_or_create_session(
        self, session_id: str | None, model: str
    ) -> AgentSession:
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if model:
                session.model = model
            return session
        session = AgentSession(model=model)
        self._sessions[session.id] = session
        return session

    async def send_message(
        self,
        session_id: str | None,
        text: str,
        model: str,
        skill_ids: list[str] | None = None,
    ) -> None:
        """Handle an incoming user message — append and start agent loop."""
        session = self._get_or_create_session(session_id, model)
        if skill_ids is not None:
            session.skill_ids = skill_ids

        # If already running, ignore
        if session.status == "thinking":
            return

        session.messages.append({"role": "user", "content": text})
        session.status = "thinking"
        session._cancel_event.clear()

        if self._on_status:
            self._on_status(session.id, "thinking")

        session._task = asyncio.create_task(self._run_agent_loop(session))

    def stop_session(self, session_id: str) -> None:
        """Cancel a running agent session."""
        session = self._sessions.get(session_id)
        if session:
            session._cancel_event.set()
            if session._task and not session._task.done():
                session._task.cancel()

    def resolve_tool_approval(self, tool_call_id: str, approved: bool) -> None:
        """Resolve a pending tool approval request."""
        self._approval_results[tool_call_id] = approved
        event = self._pending_approvals.get(tool_call_id)
        if event:
            event.set()

    async def _run_agent_loop(self, session: AgentSession) -> None:
        """Core agent loop: call LLM, handle tool calls, repeat."""
        try:
            client = self._create_client(session.model)

            # Build system prompt (inject skill content for active skills)
            system_prompt = SYSTEM_PROMPT
            if session.skill_ids and self._skill_service:
                for sid in session.skill_ids:
                    try:
                        skill_body = self._skill_service.get_skill_content(sid)
                        system_prompt += f"\n\n## Active Skill: {sid}\n\n{skill_body}"
                    except FileNotFoundError:
                        pass

            # Build tools list (add read_reference when any skill is active)
            tools = list(TOOLS)
            if session.skill_ids and self._skill_service:
                tools.append(READ_REFERENCE_TOOL)

            for _ in range(MAX_ITERATIONS):
                if session._cancel_event.is_set():
                    session.status = "done"
                    if self._on_status:
                        self._on_status(session.id, "done")
                    return

                # Build messages for LLM
                llm_messages = [
                    {"role": "system", "content": system_prompt},
                    *session.messages,
                ]

                response = await client.chat.completions.create(
                    model=session.model,
                    messages=llm_messages,
                    tools=tools,
                    tool_choice="auto",
                    max_completion_tokens=4096,
                    temperature=0,
                )

                choice = response.choices[0]
                message = choice.message
                finish_reason = choice.finish_reason

                # Build assistant message dict for conversation history
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": message.content or "",
                }
                if message.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ]
                session.messages.append(assistant_msg)

                # If the model returned text with no tool calls, we're done
                if finish_reason == "stop" or not message.tool_calls:
                    content = message.content or ""
                    if self._on_text:
                        self._on_text(session.id, content, True)
                    session.status = "done"
                    if self._on_status:
                        self._on_status(session.id, "done")
                    return

                # Execute tool calls
                for tc in message.tool_calls:
                    if session._cancel_event.is_set():
                        session.status = "done"
                        if self._on_status:
                            self._on_status(session.id, "done")
                        return

                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Handle update_plan specially
                    if tool_name == "update_plan":
                        result = self._handle_update_plan(session, tool_args)
                        is_error = False
                    elif tool_name == "read_reference":
                        result, is_error = self._handle_read_reference(
                            session, tool_args
                        )
                        if self._on_tool_use:
                            self._on_tool_use(session.id, tool_name, tool_args)
                        if self._on_tool_result:
                            self._on_tool_result(
                                session.id, tool_name, result, is_error
                            )
                    else:
                        if self._on_status:
                            self._on_status(session.id, "executing")
                        if self._on_tool_use:
                            self._on_tool_use(session.id, tool_name, tool_args)

                        # Approval gate for destructive tools
                        if tool_name in TOOLS_REQUIRING_APPROVAL:
                            approval_event = asyncio.Event()
                            self._pending_approvals[tc.id] = approval_event
                            if self._on_tool_approval:
                                self._on_tool_approval(
                                    session.id, tc.id, tool_name, tool_args
                                )
                            if self._on_status:
                                self._on_status(session.id, "awaiting_approval")
                            await approval_event.wait()
                            approved = self._approval_results.pop(tc.id, False)
                            self._pending_approvals.pop(tc.id, None)

                            if session._cancel_event.is_set():
                                session.status = "done"
                                if self._on_status:
                                    self._on_status(session.id, "done")
                                return

                            if not approved:
                                result = "Tool execution denied by user"
                                is_error = True
                                if self._on_status:
                                    self._on_status(session.id, "executing")
                                if self._on_tool_result:
                                    self._on_tool_result(
                                        session.id, tool_name, result, is_error
                                    )
                                session.messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc.id,
                                        "content": result,
                                    }
                                )
                                continue

                            if self._on_status:
                                self._on_status(session.id, "executing")

                        handler = TOOL_HANDLERS.get(tool_name)
                        if handler:
                            try:
                                result = await asyncio.get_event_loop().run_in_executor(
                                    None, handler, tool_args
                                )
                                is_error = result.startswith("Error:")
                            except Exception as e:
                                result = f"Error: {e}"
                                is_error = True
                        else:
                            result = f"Error: unknown tool '{tool_name}'"
                            is_error = True

                        if self._on_tool_result:
                            self._on_tool_result(
                                session.id, tool_name, result, is_error
                            )

                    # Append tool result to messages
                    session.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        }
                    )

                # After tools, set status back to thinking
                if self._on_status:
                    self._on_status(session.id, "thinking")

            # Max iterations reached
            if self._on_text:
                self._on_text(
                    session.id,
                    "Reached maximum iterations. Stopping.",
                    True,
                )
            session.status = "done"
            if self._on_status:
                self._on_status(session.id, "done")

        except asyncio.CancelledError:
            session.status = "done"
            if self._on_status:
                self._on_status(session.id, "done")
        except Exception as e:
            logger.exception("Agent loop error for session %s", session.id)
            session.status = "error"
            if self._on_error:
                self._on_error(session.id, str(e))

    def _handle_update_plan(self, session: AgentSession, args: dict[str, Any]) -> str:
        raw = args.get("plan", "[]")
        if isinstance(raw, list):
            items = raw
        else:
            try:
                items = json.loads(raw)
                if not isinstance(items, list):
                    return "Error: plan must be a JSON array"
            except (json.JSONDecodeError, TypeError) as e:
                return f"Error: invalid JSON: {e}"

        session.plan = items
        if self._on_plan:
            self._on_plan(session.id, items)
        return "Plan updated"

    def _handle_read_reference(
        self, session: AgentSession, args: dict[str, Any]
    ) -> tuple[str, bool]:
        """Read a reference file using the base from active skills."""
        ref_path = args.get("path", "")
        if not ref_path or not self._skill_service or not session.skill_ids:
            return "Error: no active skills or missing path", True
        # Derive base from first active skill (e.g. "uipath/authentication" -> "uipath")
        base_skill_id = session.skill_ids[0]
        try:
            content = self._skill_service.get_reference(base_skill_id, ref_path)
            if len(content) > MAX_FILE_CHARS:
                content = (
                    content[:MAX_FILE_CHARS]
                    + f"\n... [truncated at {MAX_FILE_CHARS} chars]"
                )
            return content, False
        except (FileNotFoundError, PermissionError) as e:
            return f"Error: {e}", True

    @staticmethod
    def _create_client(model_name: str) -> Any:
        """Create an AsyncOpenAI client pointed at UiPath's passthrough endpoint."""
        from openai import AsyncOpenAI

        base_url = os.environ.get("UIPATH_URL", "")
        access_token = os.environ.get("UIPATH_ACCESS_TOKEN", "")
        if not base_url or not access_token:
            raise RuntimeError(
                "Not authenticated — UIPATH_URL or UIPATH_ACCESS_TOKEN not set"
            )

        # Passthrough endpoint: {base}/agenthub_/llm/openai/deployments/{model}
        # OpenAI client appends /chat/completions automatically
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
