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
BASH_TIMEOUT = 30
TOOLS_REQUIRING_APPROVAL = {"write_file", "edit_file", "bash"}

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
    if not str(resolved).startswith(str(project_root)):
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
        if len(content) > MAX_FILE_CHARS:
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
        matches = [m for m in matches if str(m.resolve()).startswith(str(project_root))]
        if len(matches) > MAX_GLOB_RESULTS:
            matches = matches[:MAX_GLOB_RESULTS]
            truncated = True
        else:
            truncated = False
        rel = [str(m.relative_to(project_root)) for m in matches]
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
            for root, _dirs, filenames in os.walk(base):
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
                    rel = str(fpath.relative_to(project_root))
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
        "path": {"type": "string", "description": "Relative or absolute file path."}
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

_UPDATE_PLAN_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plan": {
            "type": "array",
            "description": "The full plan with updated statuses. Always send the complete plan, not just changed items.",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Step title"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                        "description": "Step status",
                    },
                },
                "required": ["title", "status"],
            },
        }
    },
    "required": ["plan"],
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
            description="Read the contents of a file at the given path.",
            parameters=_READ_FILE_PARAMS,
            handler=_make_read_file(project_root),
        ),
        ToolDefinition(
            name="write_file",
            description="Create or overwrite a file with the given content.",
            parameters=_WRITE_FILE_PARAMS,
            handler=_make_write_file(project_root),
            requires_approval=True,
        ),
        ToolDefinition(
            name="edit_file",
            description="Replace an exact string in a file with a new string. The old_string must appear exactly once.",
            parameters=_EDIT_FILE_PARAMS,
            handler=_make_edit_file(project_root),
            requires_approval=True,
        ),
        ToolDefinition(
            name="bash",
            description=(
                "Execute a shell command and return stdout/stderr. Timeout: 30s. "
                "For commands that prompt for input, provide the expected input via the stdin parameter."
            ),
            parameters=_BASH_PARAMS,
            handler=_make_bash(project_root),
            requires_approval=True,
        ),
        ToolDefinition(
            name="glob",
            description="Find files matching a glob pattern. Returns up to 200 results.",
            parameters=_GLOB_PARAMS,
            handler=_make_glob(project_root),
        ),
        ToolDefinition(
            name="grep",
            description="Search file contents with a regex pattern. Returns up to 100 matches.",
            parameters=_GREP_PARAMS,
            handler=_make_grep(project_root),
        ),
        ToolDefinition(
            name="update_plan",
            description="Update the task plan. Call this first to outline steps, then update as you complete them.",
            parameters=_UPDATE_PLAN_PARAMS,
            handler=lambda args: "",  # Handled specially in the loop
        ),
    ]


def create_read_reference_tool() -> ToolDefinition:
    """Create the read_reference tool (added when skills are active)."""
    return ToolDefinition(
        name="read_reference",
        description="Read a reference document from the skill's references directory.",
        parameters=_READ_REFERENCE_PARAMS,
        handler=lambda args: "",  # Handled specially in the loop
    )


def create_dispatch_agent_tool() -> ToolDefinition:
    """Create the dispatch_agent tool for sub-agent spawning."""
    return ToolDefinition(
        name="dispatch_agent",
        description=(
            "Spawn a sub-agent to handle a complex subtask in its own context. "
            "The sub-agent has access to read_file, glob, grep, and bash (read-only). "
            "Use this for research tasks, large file analysis, or multi-file searches "
            "that would fill up the main context."
        ),
        parameters=_DISPATCH_AGENT_PARAMS,
        handler=lambda args: "",  # Handled specially in the loop
    )
