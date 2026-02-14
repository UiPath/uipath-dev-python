"""File watcher for Python source files."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from watchfiles import PythonFilter, awatch

logger = logging.getLogger(__name__)


async def watch_python_files(
    on_change: Callable[[list[str]], None],
    stop_event: asyncio.Event,
) -> None:
    """Watch for Python file changes in the current directory.

    Uses watchfiles which already ignores .venv, __pycache__, node_modules, .git.
    PythonFilter restricts to .py / .pyx files only.
    """
    try:
        async for changes in awatch(
            ".", watch_filter=PythonFilter(), stop_event=stop_event
        ):
            changed_files = [str(path) for _, path in changes]
            logger.debug("Detected file changes: %s", changed_files)
            on_change(changed_files)
    except Exception:
        if not stop_event.is_set():
            logger.exception("File watcher error")
