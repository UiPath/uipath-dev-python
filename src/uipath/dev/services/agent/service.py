"""AgentService — thin facade over AgentLoop (session management + orchestration)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from uipath.dev.services.agent.events import AgentEvent, StatusChanged
from uipath.dev.services.agent.loop import SYSTEM_PROMPT, AgentLoop
from uipath.dev.services.agent.provider import create_provider
from uipath.dev.services.agent.session import AgentSession
from uipath.dev.services.agent.tools import (
    EXCLUDED_DIRS,
    create_ask_user_tool,
    create_default_tools,
    create_dispatch_agent_tool,
    create_read_reference_tool,
    create_task_tools,
)
from uipath.dev.services.skill_service import SkillService

_PROJECT_ROOT = Path.cwd().resolve()


def _detect_project_context(project_root: Path) -> str:
    """Detect project files and return a context string for the system prompt."""
    parts: list[str] = []

    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("name"):
                    # Extract name = "value" from TOML
                    _, _, value = stripped.partition("=")
                    name = value.strip().strip('"').strip("'")
                    if name:
                        parts.append(f"Project: {name}")
                    break
        except Exception:
            pass

    # Detect agentic framework config files — only show configs that define
    # agents or functions so the model knows which framework is active.
    framework_configs = [
        "uipath.json",
        "langgraph.json",
        "llama_index.json",
        "agent_framework.json",
        "google_adk.json",
        "pydantic_ai.json",
        "openai_agents.json",
    ]
    for config_name in framework_configs:
        config_path = project_root / config_name
        if not config_path.is_file():
            continue
        try:
            raw = config_path.read_text(encoding="utf-8").strip()
            data = json.loads(raw)
            # Skip configs that have no agents or functions defined
            has_agents = bool(data.get("agents"))
            has_functions = bool(data.get("functions"))
            if not has_agents and not has_functions:
                continue
            parts.append(f"{config_name}: {raw}")
        except Exception:
            pass

    evals_dir = project_root / "evaluations"
    if evals_dir.is_dir():
        eval_set_dir = evals_dir / "eval-sets"
        evaluator_dir = evals_dir / "evaluators"
        eval_sets = list(eval_set_dir.glob("*.json")) if eval_set_dir.is_dir() else []
        evaluators = (
            list(evaluator_dir.glob("*.json")) if evaluator_dir.is_dir() else []
        )
        sub: list[str] = []
        if eval_sets:
            sub.append(
                f"{len(eval_sets)} eval sets: {', '.join(f.stem for f in eval_sets[:5])}"
            )
        if evaluators:
            sub.append(
                f"{len(evaluators)} evaluators: {', '.join(f.stem for f in evaluators[:5])}"
            )
        if sub:
            parts.append(f"Evaluations dir: {'; '.join(sub)}")

    # List Python source files at root and in src/
    py_files = [f.name for f in project_root.glob("*.py")]
    src_dir = project_root / "src"
    if src_dir.is_dir():
        src_py = [
            str(f.relative_to(project_root))
            for f in src_dir.rglob("*.py")
            if not any(
                p.startswith(".") or p in EXCLUDED_DIRS
                for p in f.relative_to(project_root).parts
            )
        ][:10]
        py_files.extend(src_py)
    if py_files:
        parts.append(f"Python files: {', '.join(py_files[:10])}")

    if not parts:
        return ""
    return "\n\n## Current Project\n" + "\n".join(f"- {p}" for p in parts)


def _repair_orphaned_tool_calls(session: AgentSession) -> None:
    """Fix conversation history after a cancelled turn.

    If the last assistant message has tool_calls but some/all tool results
    are missing, the API will reject the next request. Patch by adding
    stub tool results for any missing call IDs.
    """
    if not session.messages:
        return

    # Find the last assistant message with tool_calls
    last_asst_idx = None
    for i in range(len(session.messages) - 1, -1, -1):
        msg = session.messages[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            last_asst_idx = i
            break

    if last_asst_idx is None:
        return

    expected_ids = {tc["id"] for tc in session.messages[last_asst_idx]["tool_calls"]}

    # Collect tool result IDs that follow this assistant message
    present_ids: set[str] = set()
    for msg in session.messages[last_asst_idx + 1 :]:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            present_ids.add(msg["tool_call_id"])

    missing = expected_ids - present_ids
    if not missing:
        return

    # Insert stub results right after the last existing tool result (or after assistant msg)
    insert_at = last_asst_idx + 1
    for j in range(last_asst_idx + 1, len(session.messages)):
        if session.messages[j].get("role") == "tool":
            insert_at = j + 1
        else:
            break

    for call_id in missing:
        session.messages.insert(
            insert_at,
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": "[cancelled by user]",
            },
        )
        insert_at += 1


def _safe_parse_json(s: str) -> dict[str, Any]:
    """Parse JSON string, returning empty dict on failure."""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}


class AgentService:
    """Manages agent sessions and runs the agent loop."""

    def __init__(  # noqa: D107
        self,
        *,
        skill_service: SkillService | None = None,
        on_event: Callable[[AgentEvent], None] | None = None,
    ) -> None:
        self._sessions: dict[str, AgentSession] = {}
        self._skill_service = skill_service
        self._on_event = on_event
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}
        self._pending_questions: dict[str, asyncio.Event] = {}
        self._question_results: dict[str, str] = {}

    def _emit(self, event: AgentEvent) -> None:
        if self._on_event:
            self._on_event(event)

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
        if session.status in (
            "thinking",
            "executing",
            "awaiting_approval",
            "awaiting_input",
        ):
            return

        _repair_orphaned_tool_calls(session)
        session.messages.append({"role": "user", "content": text})
        session.status = "thinking"
        session._cancel_event.clear()

        self._emit(StatusChanged(session.id, status="thinking"))

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

    def resolve_question(self, question_id: str, answer: str) -> None:
        """Resolve a pending agent question with the user's answer."""
        self._question_results[question_id] = answer
        event = self._pending_questions.get(question_id)
        if event:
            event.set()

    def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Return the full session state converted to frontend message format."""
        session = self._sessions.get(session_id)
        if session is None:
            return None

        frontend_messages = self._convert_messages(session)
        tasks = [
            {"title": t["title"], "status": t["status"]} for t in session.tasks.values()
        ]

        return {
            "session_id": session.id,
            "status": "done" if session.status == "idle" else session.status,
            "model": session.model,
            "messages": frontend_messages,
            "plan": tasks,
            "total_prompt_tokens": session.total_prompt_tokens,
            "total_completion_tokens": session.total_completion_tokens,
            "turn_count": session.turn_count,
            "compaction_count": session.compaction_count,
        }

    @staticmethod
    def _convert_messages(session: AgentSession) -> list[dict[str, Any]]:
        """Convert OpenAI-format messages to frontend AgentMessage[] format."""
        result: list[dict[str, Any]] = []
        msg_counter = 0
        hidden_tool_call_ids: set[str] = set()

        def next_id() -> str:
            nonlocal msg_counter
            msg_counter += 1
            return f"restored-msg-{msg_counter}"

        # Task management tools are internal — don't show in restored chat
        _HIDDEN_TOOLS = {
            "create_task",
            "update_task",
            "list_tasks",
            "dispatch_agent",
            "ask_user",
            "read_reference",
        }

        # Walk messages sequentially, collecting tool groups
        pending_tool_calls: list[dict[str, Any]] = []

        for msg in session.messages:
            role = msg.get("role")

            if role == "user":
                # Flush any pending tool group
                if pending_tool_calls:
                    result.append(
                        {
                            "id": next_id(),
                            "role": "tool",
                            "content": "",
                            "timestamp": 0,
                            "toolCalls": pending_tool_calls,
                        }
                    )
                    pending_tool_calls = []

                result.append(
                    {
                        "id": next_id(),
                        "role": "user",
                        "content": msg.get("content", ""),
                        "timestamp": 0,
                    }
                )

            elif role == "assistant":
                content = msg.get("content", "") or ""
                # Only flush pending tool group when the model actually
                # spoke between tool rounds (text content present).
                # Back-to-back tool rounds stay in one group.
                if content and pending_tool_calls:
                    result.append(
                        {
                            "id": next_id(),
                            "role": "tool",
                            "content": "",
                            "timestamp": 0,
                            "toolCalls": pending_tool_calls,
                        }
                    )
                    pending_tool_calls = []

                if content:
                    result.append(
                        {
                            "id": next_id(),
                            "role": "assistant",
                            "content": content,
                            "timestamp": 0,
                            "done": True,
                        }
                    )

                # Start collecting tool calls if present
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "unknown")
                    tc_id = tc.get("id", "")
                    if name in _HIDDEN_TOOLS:
                        hidden_tool_call_ids.add(tc_id)
                        continue
                    pending_tool_calls.append(
                        {
                            "tool": name,
                            "args": _safe_parse_json(func.get("arguments", "{}")),
                            "_tool_call_id": tc_id,
                        }
                    )

            elif role == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                if tool_call_id in hidden_tool_call_ids:
                    continue
                # Match to pending tool call by tool_call_id
                content = msg.get("content", "")
                is_error = content.startswith("Error:")
                for tc in pending_tool_calls:
                    if tc.get("_tool_call_id") == tool_call_id:
                        tc["result"] = content
                        tc["is_error"] = is_error
                        break

        # Flush remaining tool group
        if pending_tool_calls:
            result.append(
                {
                    "id": next_id(),
                    "role": "tool",
                    "content": "",
                    "timestamp": 0,
                    "toolCalls": pending_tool_calls,
                }
            )

        # Clean up internal _tool_call_id from tool calls
        for msg_item in result:
            if msg_item.get("toolCalls"):
                for tc in msg_item["toolCalls"]:
                    tc.pop("_tool_call_id", None)

        return result

    def get_session_diagnostics(self, session_id: str) -> dict[str, Any] | None:
        """Return structured diagnostics for a session."""
        session = self._sessions.get(session_id)
        if session is None:
            return None

        # Tool call summary: count calls and errors per tool name
        tool_counts: dict[str, int] = {}
        tool_errors: dict[str, int] = {}
        for msg in session.messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    name = tc.get("function", {}).get("name", "unknown")
                    tool_counts[name] = tool_counts.get(name, 0) + 1
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                # Find matching tool name from preceding assistant message
                tool_call_id = msg.get("tool_call_id", "")
                tool_name = self._resolve_tool_name(session, tool_call_id)
                if content.startswith("Error:"):
                    tool_errors[tool_name] = tool_errors.get(tool_name, 0) + 1

        tool_summary = []
        for name, count in sorted(tool_counts.items()):
            entry: dict[str, Any] = {"tool": name, "calls": count}
            if name in tool_errors:
                entry["errors"] = tool_errors[name]
            tool_summary.append(entry)

        # Last 10 messages condensed
        last_messages = []
        for msg in session.messages[-10:]:
            role = msg.get("role", "")
            entry_msg: dict[str, Any] = {"role": role}
            if role == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                entry_msg["tool"] = self._resolve_tool_name(session, tool_call_id)
            content = msg.get("content", "")
            if content:
                entry_msg["content"] = content[:200]
            last_messages.append(entry_msg)

        # Tasks
        tasks = [
            {"title": t["title"], "status": t["status"]} for t in session.tasks.values()
        ]

        return {
            "model": session.model,
            "turn_count": session.turn_count,
            "total_prompt_tokens": session.total_prompt_tokens,
            "total_completion_tokens": session.total_completion_tokens,
            "compaction_count": session.compaction_count,
            "tasks": tasks,
            "tool_summary": tool_summary,
            "last_messages": last_messages,
        }

    def get_session_raw_state(self, session_id: str) -> dict[str, Any] | None:
        """Return raw trace data for the agent trace inspector."""
        session = self._sessions.get(session_id)
        if session is None:
            return None

        return {
            "session_id": session.id,
            "model": session.model,
            "status": session.status,
            "turn_count": session.turn_count,
            "total_prompt_tokens": session.total_prompt_tokens,
            "total_completion_tokens": session.total_completion_tokens,
            "system_prompt": session.last_system_prompt,
            "tool_schemas": session.last_tool_schemas,
            "traces": session.traces,
        }

    @staticmethod
    def _resolve_tool_name(session: AgentSession, tool_call_id: str) -> str:
        """Find the tool name for a given tool_call_id from assistant messages."""
        for msg in session.messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if tc.get("id") == tool_call_id:
                        return tc.get("function", {}).get("name", "unknown")
        return "unknown"

    async def _run_agent_loop(self, session: AgentSession) -> None:
        """Create provider, build tools, and run the loop."""
        provider = create_provider(session.model)

        # Build system prompt (inject skill summaries for active skills)
        system_prompt = SYSTEM_PROMPT
        if session.skill_ids and self._skill_service:
            for sid in session.skill_ids:
                try:
                    summary = self._skill_service.get_skill_summary(sid)
                    system_prompt += f"\n\n## Active Skill: {sid}\n\n{summary}"
                except FileNotFoundError:
                    pass
            # Append reference file list once (shared across all skills)
            ref_files = self._skill_service.get_reference_files()
            if ref_files:
                system_prompt += (
                    "\n\n## Reference Files\n"
                    "Use `read_reference` with a filename to view:\n"
                    + "\n".join(f"  - {f}" for f in ref_files)
                )

        # Inject dynamic project context
        system_prompt += _detect_project_context(_PROJECT_ROOT)

        # Build tools list
        tools = create_default_tools(_PROJECT_ROOT)
        tools.extend(create_task_tools())
        tools.append(create_dispatch_agent_tool())
        tools.append(create_ask_user_tool())
        if session.skill_ids and self._skill_service:
            tools.append(create_read_reference_tool())

        # Persist system prompt + tool schemas on session for trace inspection
        session.last_system_prompt = system_prompt
        session.last_tool_schemas = sorted(
            [t.to_openai_schema() for t in tools],
            key=lambda s: s["function"]["name"],
        )

        loop = AgentLoop(
            provider=provider,
            tools=tools,
            emit=self._emit,
            pending_approvals=self._pending_approvals,
            approval_results=self._approval_results,
            pending_questions=self._pending_questions,
            question_results=self._question_results,
            skill_service=self._skill_service,
        )

        await loop.run(session, system_prompt=system_prompt)
