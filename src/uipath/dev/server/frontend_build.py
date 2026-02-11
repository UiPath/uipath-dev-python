"""Auto-build the frontend if needed."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"
STATIC_DIR = Path(__file__).parent / "static"


def _newest_mtime(directory: Path, glob: str = "**/*") -> float:
    """Return the newest mtime of any file matching *glob* under *directory*."""
    newest = 0.0
    for p in directory.glob(glob):
        if p.is_file() and "node_modules" not in p.parts:
            newest = max(newest, p.stat().st_mtime)
    return newest


def _npm() -> str:
    """Return the npm command for the current platform."""
    return "npm.cmd" if sys.platform == "win32" else "npm"


def needs_build() -> bool:
    """Check whether the frontend needs a (re-)build."""
    if not FRONTEND_DIR.exists():
        return False  # no frontend source to build from

    if not STATIC_DIR.exists():
        return True

    index = STATIC_DIR / "index.html"
    if not index.exists():
        return True

    # Rebuild if any source file is newer than the build output
    src_mtime = _newest_mtime(FRONTEND_DIR / "src")
    build_mtime = index.stat().st_mtime
    return src_mtime > build_mtime


def ensure_frontend_built() -> bool:
    """Build the frontend if the static dir is missing or stale.

    Returns True if the static dir exists (either already or after build).
    """
    if not FRONTEND_DIR.exists():
        logger.debug("No frontend source directory found, skipping build")
        return STATIC_DIR.exists()

    if not needs_build():
        logger.debug("Frontend is up to date")
        return True

    npm = _npm()

    # Check npm is available
    if not shutil.which(npm):
        logger.warning(
            "npm not found on PATH — skipping frontend build. "
            "Install Node.js or run 'npm run build' manually in %s",
            FRONTEND_DIR,
        )
        return STATIC_DIR.exists()

    logger.info("Building frontend...")

    # npm install (if node_modules is missing)
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        logger.info("Installing frontend dependencies...")
        result = subprocess.run(
            [npm, "install"],
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(
                "npm install failed:\nSTDOUT:\n%s\nSTDERR:\n%s",
                result.stdout,
                result.stderr,
            )
            return STATIC_DIR.exists()

    # npm run build
    result = subprocess.run(
        [npm, "run", "build"],
        cwd=str(FRONTEND_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(
            "npm run build failed:\nSTDOUT:\n%s\nSTDERR:\n%s",
            result.stdout,
            result.stderr,
        )
        return STATIC_DIR.exists()

    logger.info("Frontend built successfully -> %s", STATIC_DIR)
    return True
