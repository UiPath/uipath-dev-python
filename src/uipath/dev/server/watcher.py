"""File watcher for project source files."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import PurePosixPath

from watchfiles import DefaultFilter, awatch

logger = logging.getLogger(__name__)


async def watch_project_files(
    on_change: Callable[[list[str]], None],
    stop_event: asyncio.Event,
) -> None:
    """Watch for file changes in the current directory.

    Uses DefaultFilter which ignores .git, __pycache__, node_modules, etc.
    Also ignores the __uipath/ runtime directory (state.db, WAL, SHM files).
    """

    def _filter(change: int, path: str) -> bool:
        if not DefaultFilter()(change, path):  # type: ignore[arg-type]
            return False
        # Skip __uipath/ directory (state.db checkpoints cause constant churn)
        parts = PurePosixPath(path.replace("\\", "/")).parts
        return "__uipath" not in parts

    try:
        async for changes in awatch(".", watch_filter=_filter, stop_event=stop_event):
            changed_files = [str(path) for _, path in changes]
            logger.debug("Detected file changes: %s", changed_files)
            on_change(changed_files)
    except Exception:
        if not stop_event.is_set():
            logger.exception("File watcher error")
