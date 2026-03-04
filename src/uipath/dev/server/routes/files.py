"""File explorer API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["files"])

ROOT = Path.cwd().resolve()

IGNORED_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
}

EXTENSION_LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".bat": "bat",
    ".ps1": "powershell",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".r": "r",
    ".lua": "lua",
    ".dockerfile": "dockerfile",
    ".graphql": "graphql",
    ".ini": "ini",
    ".cfg": "ini",
    ".env": "dotenv",
}

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB


def _resolve_safe(path: str) -> Path:
    """Resolve a path and ensure it stays within ROOT."""
    resolved = (ROOT / path).resolve()
    if not str(resolved).startswith(str(ROOT)):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    return resolved


def _detect_language(filepath: Path) -> str | None:
    name = filepath.name.lower()
    if name == "dockerfile":
        return "dockerfile"
    if name == "makefile":
        return "makefile"
    return EXTENSION_LANGUAGES.get(filepath.suffix.lower())


def _is_ignored(name: str) -> bool:
    if name in IGNORED_NAMES:
        return True
    # Check wildcard patterns like *.egg-info
    for pattern in IGNORED_NAMES:
        if pattern.startswith("*") and name.endswith(pattern[1:]):
            return True
    return False


@router.get("/files/tree")
async def list_directory(path: str = "") -> list[dict[str, Any]]:
    """List directory contents. Dirs first, alphabetical."""
    target = _resolve_safe(path)
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    entries: list[dict[str, Any]] = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith(".") and child.name in IGNORED_NAMES:
                continue
            if _is_ignored(child.name):
                continue
            rel = str(child.relative_to(ROOT)).replace("\\", "/")
            entries.append(
                {
                    "name": child.name,
                    "type": "directory" if child.is_dir() else "file",
                    "path": rel,
                }
            )
    except PermissionError as err:
        raise HTTPException(status_code=403, detail="Permission denied") from err

    # Sort: directories first, then files, alphabetical within each group
    entries.sort(
        key=lambda e: (0 if e["type"] == "directory" else 1, e["name"].lower())
    )
    return entries


@router.get("/files/content")
async def read_file(path: str) -> dict[str, Any]:
    """Read file content. Returns content, binary flag, size, and language."""
    target = _resolve_safe(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    size = target.stat().st_size
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size} bytes, max {MAX_FILE_SIZE})",
        )

    # Binary detection: read raw bytes and check for null bytes
    raw = target.read_bytes()
    is_binary = b"\x00" in raw[:8192]

    if is_binary:
        return {
            "content": None,
            "binary": True,
            "size": size,
            "language": None,
        }

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "content": None,
            "binary": True,
            "size": size,
            "language": None,
        }

    return {
        "content": content,
        "binary": False,
        "size": size,
        "language": _detect_language(target),
    }


class SaveFileBody(BaseModel):
    """Request body for saving file content."""

    content: str


@router.put("/files/content")
async def save_file(path: str, body: SaveFileBody) -> dict[str, str]:
    """Save file content. Creates parent dirs if needed."""
    target = _resolve_safe(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Write bytes directly to avoid Python text-mode converting \n → \r\n on
    # Windows, which would add extra carriage returns on every save since
    # Monaco normalizes line endings to \n.
    target.write_bytes(body.content.encode("utf-8"))
    return {"status": "ok"}
