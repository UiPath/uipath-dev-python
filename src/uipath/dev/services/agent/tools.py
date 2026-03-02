"""Tool definitions and implementations for the agent harness."""

from __future__ import annotations

import fnmatch
import os
import re
import signal
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_OUTPUT_CHARS = 50_000
MAX_FILE_CHARS = 100_000
MAX_GLOB_RESULTS = 200
MAX_GREP_MATCHES = 100
BASH_TIMEOUT = 120
TOOLS_REQUIRING_APPROVAL = {"write_file", "edit_file", "bash"}

# Directories to exclude from glob/grep results.
# All dot-prefixed directories (e.g. .git, .venv, .claude) are already
# filtered via `startswith(".")` checks. This set covers non-dot dirs
# that should also be excluded.
EXCLUDED_DIRS = {
    "node_modules",
    "__pycache__",
    "__uipath",
}

# Matches standard ANSI CSI sequences, OSC sequences, and carriage returns.
_ANSI_RE = re.compile(r"\x1b\][^\x1b]*(?:\x1b\\|\x07)|\x1b\[[0-9;]*[A-Za-z]|\r")


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------


@dataclass
class ToolDefinition:
    """A tool available to the agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], str]
    requires_approval: bool = False

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def _resolve_safe(project_root: Path, path_str: str) -> Path:
    """Resolve a path and ensure it stays within the project root."""
    p = Path(path_str)
    if not p.is_absolute():
        p = project_root / p
    resolved = p.resolve()
    if not os.path.normcase(str(resolved)).startswith(
        os.path.normcase(str(project_root))
    ):
        raise PermissionError(f"Path escapes project root: {path_str}")
    return resolved


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
    """Kill a process and all its children."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _make_read_file(project_root: Path) -> Callable[[dict[str, Any]], str]:
    def handler(args: dict[str, Any]) -> str:
        path = _resolve_safe(project_root, args["path"])
        if not path.is_file():
            return f"Error: file not found: {args['path']}"
        content = path.read_text(encoding="utf-8", errors="replace")

        offset = args.get("offset")
        limit = args.get("limit")

        if offset is not None or limit is not None:
            lines = content.splitlines(keepends=True)
            total = len(lines)
            start = max(0, (int(offset) - 1)) if offset else 0
            end = start + int(limit) if limit else total
            selected = lines[start:end]
            content = "".join(selected)
            if start > 0 or end < total:
                content += (
                    f"\n[showing lines {start + 1}-{min(end, total)} of {total} total]"
                )
        elif len(content) > MAX_FILE_CHARS:
            content = (
                content[:MAX_FILE_CHARS]
                + f"\n... [truncated at {MAX_FILE_CHARS} chars]"
            )
        return content

    return handler


def _make_write_file(project_root: Path) -> Callable[[dict[str, Any]], str]:
    def handler(args: dict[str, Any]) -> str:
        path = _resolve_safe(project_root, args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        return f"File written: {args['path']} ({len(args['content'])} chars)"

    return handler


def _make_edit_file(project_root: Path) -> Callable[[dict[str, Any]], str]:
    def handler(args: dict[str, Any]) -> str:
        path = _resolve_safe(project_root, args["path"])
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

    return handler


def _make_bash(project_root: Path) -> Callable[[dict[str, Any]], str]:
    def handler(args: dict[str, Any]) -> str:
        command = args["command"]
        stdin_input = args.get("stdin")
        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["NO_COLOR"] = "1"
            env["TERM"] = "dumb"
            popen_kwargs: dict[str, Any] = dict(
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(project_root),
                env=env,
            )
            if stdin_input is not None:
                popen_kwargs["stdin"] = subprocess.PIPE
            else:
                popen_kwargs["stdin"] = subprocess.DEVNULL
            if sys.platform != "win32":
                popen_kwargs["start_new_session"] = True

            proc = subprocess.Popen(command, **popen_kwargs)
            try:
                stdout, stderr = proc.communicate(
                    input=stdin_input, timeout=BASH_TIMEOUT
                )
            except subprocess.TimeoutExpired:
                _kill_process_tree(proc)
                return f"Error: command timed out after {BASH_TIMEOUT}s"

            output = ""
            if stdout:
                output += stdout
            if stderr:
                output += ("\n" if output else "") + stderr
            output = _ANSI_RE.sub("", output)
            if proc.returncode != 0:
                output += f"\n[exit code: {proc.returncode}]"
            if not output:
                output = "[no output]"
            if len(output) > MAX_OUTPUT_CHARS:
                output = (
                    output[:MAX_OUTPUT_CHARS]
                    + f"\n... [truncated at {MAX_OUTPUT_CHARS} chars]"
                )
            return output
        except Exception as e:
            return f"Error: {e}"

    return handler


def _make_glob(project_root: Path) -> Callable[[dict[str, Any]], str]:
    def handler(args: dict[str, Any]) -> str:
        pattern = args["pattern"]
        base = _resolve_safe(project_root, args.get("path", "."))
        if not base.is_dir():
            return f"Error: directory not found: {args.get('path', '.')}"
        matches = sorted(base.glob(pattern))
        root_normed = os.path.normcase(str(project_root))
        filtered: list[Path] = []
        for m in matches:
            if not os.path.normcase(str(m.resolve())).startswith(root_normed):
                continue
            try:
                parts = m.relative_to(project_root).parts
            except ValueError:
                # Fallback for case-mismatch on Windows
                rel_path = os.path.relpath(str(m), str(project_root))
                parts = Path(rel_path).parts
            if any(p.startswith(".") or p in EXCLUDED_DIRS for p in parts):
                continue
            filtered.append(m)
        matches = filtered
        if len(matches) > MAX_GLOB_RESULTS:
            matches = matches[:MAX_GLOB_RESULTS]
            truncated = True
        else:
            truncated = False
        rel = [
            os.path.relpath(str(m), str(project_root)).replace("\\", "/")
            for m in matches
        ]
        result = "\n".join(rel) if rel else "No matches found"
        if truncated:
            result += f"\n... [truncated at {MAX_GLOB_RESULTS} results]"
        return result

    return handler


def _make_grep(project_root: Path) -> Callable[[dict[str, Any]], str]:
    def handler(args: dict[str, Any]) -> str:
        pattern_str = args["pattern"]
        base = _resolve_safe(project_root, args.get("path", "."))
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
            for root, dirs, filenames in os.walk(base):
                # Prune excluded directories in-place to prevent traversal
                dirs[:] = [
                    d for d in dirs if not d.startswith(".") and d not in EXCLUDED_DIRS
                ]
                root_path = Path(root)
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
                    rel = os.path.relpath(str(fpath), str(project_root)).replace(
                        "\\", "/"
                    )
                    matches.append(f"{rel}:{i}: {line.rstrip()}")
                    if len(matches) >= MAX_GREP_MATCHES:
                        break

        result = "\n".join(matches) if matches else "No matches found"
        if len(matches) >= MAX_GREP_MATCHES:
            result += f"\n... [truncated at {MAX_GREP_MATCHES} matches]"
        return result

    return handler


# ---------------------------------------------------------------------------
# Tool schemas (parameter definitions)
# ---------------------------------------------------------------------------

_READ_FILE_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Relative or absolute file path."},
        "offset": {
            "type": "integer",
            "description": "1-based line number to start reading from. Defaults to 1.",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of lines to return. Defaults to all lines.",
        },
    },
    "required": ["path"],
}

_WRITE_FILE_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Relative or absolute file path."},
        "content": {"type": "string", "description": "The full file content to write."},
    },
    "required": ["path", "content"],
}

_EDIT_FILE_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Relative or absolute file path."},
        "old_string": {
            "type": "string",
            "description": "The exact string to find and replace.",
        },
        "new_string": {"type": "string", "description": "The replacement string."},
    },
    "required": ["path", "old_string", "new_string"],
}

_BASH_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "The shell command to execute."},
        "stdin": {
            "type": "string",
            "description": "Optional input to feed to the command's stdin.",
        },
    },
    "required": ["command"],
}

_GLOB_PARAMS: dict[str, Any] = {
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
}

_GREP_PARAMS: dict[str, Any] = {
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
}

_CREATE_TASK_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short title describing the task."},
        "description": {
            "type": "string",
            "description": "Optional longer description with details or acceptance criteria.",
        },
    },
    "required": ["title"],
}

_UPDATE_TASK_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string", "description": "The ID of the task to update."},
        "status": {
            "type": "string",
            "enum": ["pending", "in_progress", "completed"],
            "description": "New status for the task.",
        },
        "title": {
            "type": "string",
            "description": "Optional new title for the task.",
        },
    },
    "required": ["task_id", "status"],
}

_LIST_TASKS_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {},
}

_ASK_USER_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "description": "The question to ask the user."},
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional list of choices for the user to pick from.",
        },
    },
    "required": ["question"],
}

_READ_REFERENCE_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Relative path within the references/ directory.",
        }
    },
    "required": ["path"],
}

_DISPATCH_AGENT_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "description": "Description of the subtask for the sub-agent.",
        }
    },
    "required": ["task"],
}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_default_tools(project_root: Path) -> list[ToolDefinition]:
    """Factory that returns all built-in tools."""
    return [
        ToolDefinition(
            name="read_file",
            description=(
                "Read the contents of a file at the given path. Always use this before editing a file "
                "to understand its current content, imports, and conventions. Supports optional offset "
                "(1-based line number) and limit (max lines) for reading specific sections of large files. "
                "Returns up to 100K chars; larger files are truncated. Accepts relative or absolute paths."
            ),
            parameters=_READ_FILE_PARAMS,
            handler=_make_read_file(project_root),
        ),
        ToolDefinition(
            name="write_file",
            description=(
                "Create a new file or completely overwrite an existing file with the given content. "
                "Use this only for new files — prefer edit_file for modifying existing files. "
                "Parent directories are created automatically. Requires user approval."
            ),
            parameters=_WRITE_FILE_PARAMS,
            handler=_make_write_file(project_root),
            requires_approval=True,
        ),
        ToolDefinition(
            name="edit_file",
            description=(
                "Replace an exact string in a file with a new string. The old_string must appear "
                "exactly once in the file (to prevent ambiguous edits). Use this for targeted, "
                "surgical changes to existing files. Always read_file first to get the exact string "
                "to match. Requires user approval."
            ),
            parameters=_EDIT_FILE_PARAMS,
            handler=_make_edit_file(project_root),
            requires_approval=True,
        ),
        ToolDefinition(
            name="bash",
            description=(
                "Execute a shell command and return stdout + stderr. Timeout: 30 seconds. "
                "Use this for running CLI tools (uv run, uipath init, pytest, ruff, etc.), "
                "installing dependencies, and any terminal operations. For commands that need "
                "interactive input, provide it via the stdin parameter. Requires user approval. "
                "Common UiPath commands: `uv run uipath init`, `uv run uipath run <name> '<json>'`, "
                "`uv run uipath eval`, `uv run uipath pack`, `uv run uipath publish -w`. "
                + (
                    "The user is on Windows — use Windows-compatible commands "
                    "(e.g., `dir` instead of `ls`, `type` instead of `cat`)."
                    if sys.platform == "win32"
                    else "The user is on Unix — standard shell commands (ls, cat, etc.) are available."
                )
            ),
            parameters=_BASH_PARAMS,
            handler=_make_bash(project_root),
            requires_approval=True,
        ),
        ToolDefinition(
            name="glob",
            description=(
                "Find files matching a glob pattern (e.g. '**/*.py', 'src/**/*.ts'). "
                "Use this to discover files by name or extension before reading them. "
                "Returns up to 200 file paths relative to the project root, sorted alphabetically. "
                "Automatically excludes .venv, node_modules, __pycache__, .git and other non-source directories. "
                "For searching file *contents*, use grep instead."
            ),
            parameters=_GLOB_PARAMS,
            handler=_make_glob(project_root),
        ),
        ToolDefinition(
            name="grep",
            description=(
                "Search file contents using a regex pattern. Returns matching lines with "
                "file path, line number, and content (up to 100 matches). "
                "Skips .venv, .git, node_modules, __pycache__, and other non-source directories. "
                "Use the 'include' filter for specific file types (e.g. '*.py'). "
                "For finding files by name, use glob instead."
            ),
            parameters=_GREP_PARAMS,
            handler=_make_grep(project_root),
        ),
    ]


def create_task_tools() -> list[ToolDefinition]:
    """Create the task management tools (create_task, update_task, list_tasks)."""
    return [
        ToolDefinition(
            name="create_task",
            description=(
                "Create a new task in your plan. Call this at the start to break your work into "
                "trackable steps. Each task gets a unique ID. Returns the task ID. "
                "Use this instead of sending the full plan — add tasks one at a time."
            ),
            parameters=_CREATE_TASK_PARAMS,
            handler=lambda args: "",  # Handled specially in the loop
        ),
        ToolDefinition(
            name="update_task",
            description=(
                "Update a task's status or title. Set status to 'in_progress' when starting a step, "
                "'completed' when done. You can also update the title if the scope changed. "
                "Only sends the fields you want to change — no need to resend the full plan."
            ),
            parameters=_UPDATE_TASK_PARAMS,
            handler=lambda args: "",  # Handled specially in the loop
        ),
        ToolDefinition(
            name="list_tasks",
            description=(
                "List all tasks with their IDs, titles, and statuses. Use this to review your "
                "current plan progress or to find task IDs for updating."
            ),
            parameters=_LIST_TASKS_PARAMS,
            handler=lambda args: "",  # Handled specially in the loop
        ),
    ]


def create_read_reference_tool() -> ToolDefinition:
    """Create the read_reference tool (added when skills are active)."""
    return ToolDefinition(
        name="read_reference",
        description=(
            "Read a reference document from the active skill's references directory. "
            "Use this to get detailed information about a topic listed in the skill's table of "
            "contents. Pass the relative path as shown in the skill summary (e.g. 'authentication.md'). "
            "The skill summary gives you section headings — use read_reference to dive deeper."
        ),
        parameters=_READ_REFERENCE_PARAMS,
        handler=lambda args: "",  # Handled specially in the loop
    )


def create_dispatch_agent_tool() -> ToolDefinition:
    """Create the dispatch_agent tool for sub-agent spawning."""
    return ToolDefinition(
        name="dispatch_agent",
        description=(
            "Spawn a sub-agent to handle a research subtask in its own isolated context. "
            "The sub-agent has read-only access (read_file, glob, grep, bash). Use this for "
            "multi-file analysis, large codebase exploration, or any research that would "
            "fill up the main context window. The sub-agent returns a concise summary of findings. "
            "Don't use this for quick single-file lookups — use read_file or grep directly."
        ),
        parameters=_DISPATCH_AGENT_PARAMS,
        handler=lambda args: "",  # Handled specially in the loop
    )


def create_ask_user_tool() -> ToolDefinition:
    """Create the ask_user tool for structured elicitation."""
    return ToolDefinition(
        name="ask_user",
        description=(
            "Ask the user a question and wait for their answer. Use this when you need "
            "clarification, a decision between options, or confirmation before proceeding. "
            "Optionally provide a list of options for the user to choose from. "
            "The loop will pause until the user responds. Returns the user's answer as text."
        ),
        parameters=_ASK_USER_PARAMS,
        handler=lambda args: "",  # Handled specially in the loop
    )
