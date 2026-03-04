"""Context window management — compaction + stale tool result pruning."""

from __future__ import annotations

from uipath.dev.services.agent.provider import ModelProvider
from uipath.dev.services.agent.session import AgentSession

COMPACTION_TRIGGER_RATIO = 0.75
KEEP_RECENT = 4  # Keep last 4 messages (2 turns) for continuity

_DEFAULT_CONTEXT_WINDOW = 128_000

# Prefix → context window size. Matched longest-prefix-first against model names
# like "gpt-5.1-2025-11-13".
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4o-mini": 128_000,
    "gpt-4o": 128_000,
    "gpt-4.1-mini": 1_048_576,
    "gpt-4.1-nano": 1_048_576,
    "gpt-4.1": 1_048_576,
    "gpt-5.1": 1_048_576,
    "gpt-5.2": 1_048_576,
    "gpt-5": 1_048_576,
}


def get_context_window(model: str) -> int:
    """Return the context window size for a model, matching by prefix."""
    for prefix, size in MODEL_CONTEXT_WINDOWS.items():
        if model.startswith(prefix):
            return size
    return _DEFAULT_CONTEXT_WINDOW


MAX_TOOL_RESULTS_KEPT = 6
MIN_RESULT_SIZE_TO_CLEAR = 200


async def maybe_compact(
    session: AgentSession,
    provider: ModelProvider,
    system_prompt: str,
) -> bool:
    """Check if compaction is needed and perform it if so.

    Returns True if compaction was performed.
    """
    window_size = get_context_window(session.model)
    if session.total_prompt_tokens < window_size * COMPACTION_TRIGGER_RATIO:
        return False

    # Build task state string for preservation
    task_state = ""
    if session.tasks:
        task_lines = []
        for tid, task in session.tasks.items():
            task_lines.append(f"  [{tid}] ({task['status']}) {task['title']}")
        task_state = "\n## Current Task State\n" + "\n".join(task_lines)

    summary_prompt = (
        "Summarize the conversation so far. Preserve:\n"
        "- The user's original request and any clarifications\n"
        "- Key decisions made and their rationale\n"
        "- Current state of the task (what's done, what remains)\n"
        "- File paths and code patterns that were discovered\n"
        "- Any errors encountered and how they were resolved\n"
        "Be concise but don't lose critical context."
        + (f"\n\n{task_state}" if task_state else "")
    )

    summary_response = await provider.complete(
        messages=[
            {"role": "system", "content": summary_prompt},
            *session.messages,
        ],
        tools=[],
        model=session.model,
        max_tokens=2048,
    )

    recent = (
        session.messages[-KEEP_RECENT:] if len(session.messages) > KEEP_RECENT else []
    )

    # If recent starts with orphaned tool results, extend backwards to
    # include the assistant message that carries the matching tool_calls.
    if recent and recent[0].get("role") == "tool":
        start_idx = len(session.messages) - len(recent)
        for j in range(start_idx - 1, -1, -1):
            if session.messages[j].get("role") == "assistant" and session.messages[
                j
            ].get("tool_calls"):
                recent = session.messages[j:]
                break

    summary_content = f"[Conversation Summary]\n{summary_response.content}"
    if task_state:
        summary_content += f"\n\n{task_state}"

    session.messages = [
        {"role": "assistant", "content": summary_content},
        *recent,
    ]
    session.compaction_count += 1
    return True


def prune_stale_tool_results(session: AgentSession) -> int:
    """Replace old tool results with placeholders. Returns chars freed."""
    tool_result_indices = [
        i
        for i, m in enumerate(session.messages)
        if m.get("role") == "tool"
        and len(m.get("content", "")) > MIN_RESULT_SIZE_TO_CLEAR
    ]

    to_clear = (
        tool_result_indices[:-MAX_TOOL_RESULTS_KEPT]
        if len(tool_result_indices) > MAX_TOOL_RESULTS_KEPT
        else []
    )

    freed = 0
    for idx in to_clear:
        msg = session.messages[idx]
        original_len = len(msg["content"])
        msg["content"] = f"[tool result cleared — {original_len} chars]"
        freed += original_len

    return freed
