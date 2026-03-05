"""Cross-platform PTY subprocess session."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class PtySession:
    """Manages a single PTY subprocess for a CLI coding agent."""

    def __init__(
        self,
        session_id: str,
        command: list[str],
        on_output: Callable[[str, bytes], None],
        on_exit: Callable[[str, int], None],
        cwd: str | None = None,
        cols: int = 120,
        rows: int = 40,
    ) -> None:
        """Initialize a PTY session."""
        self.session_id = session_id
        self.command = command
        self._on_output = on_output
        self._on_exit = on_exit
        self._cwd = cwd or os.getcwd()
        self._cols = cols
        self._rows = rows
        self._reader_task: asyncio.Task[None] | None = None
        self._stopped = False

        # Platform-specific handles (typed as Any to avoid cross-platform mypy issues)
        self._pty_process: Any = None  # winpty PtyProcess on Windows
        self._master_fd: int | None = None  # Unix master fd
        self._process: asyncio.subprocess.Process | None = None  # Unix subprocess

    async def start(self) -> None:
        """Spawn the CLI agent in a PTY."""
        if sys.platform == "win32":
            await self._start_windows()
        else:
            await self._start_unix()

    async def _start_windows(self) -> None:
        from winpty import PtyProcess  # type: ignore

        loop = asyncio.get_running_loop()
        cmd_str = " ".join(self.command)
        self._pty_process = await loop.run_in_executor(
            None,
            lambda: PtyProcess.spawn(
                cmd_str,
                cwd=self._cwd,
                dimensions=(self._rows, self._cols),
            ),
        )
        self._reader_task = asyncio.create_task(self._read_loop_windows())

    async def _start_unix(self) -> None:  # pragma: no cover (Unix only)
        import fcntl  # noqa: PLC0415
        import pty as pty_mod  # noqa: PLC0415
        import struct
        import termios  # noqa: PLC0415

        master_fd, slave_fd = pty_mod.openpty()  # type: ignore
        winsize = struct.pack("HHHH", self._rows, self._cols, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)  # type: ignore

        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=self._cwd,
            start_new_session=True,
        )
        os.close(slave_fd)
        self._master_fd = master_fd
        self._reader_task = asyncio.create_task(self._read_loop_unix())

    async def _read_loop_windows(self) -> None:
        loop = asyncio.get_running_loop()
        pty = self._pty_process
        try:
            while not self._stopped and pty is not None:
                try:
                    data: str = await loop.run_in_executor(None, lambda: pty.read(4096))
                    if data:
                        self._on_output(
                            self.session_id, data.encode("utf-8", errors="replace")
                        )
                except EOFError:
                    break
                except OSError:
                    break
        finally:
            exit_code = -1
            try:
                if pty is not None and hasattr(pty, "exitstatus"):
                    exit_code = pty.exitstatus() or 0
            except Exception:
                pass
            if not self._stopped:
                self._on_exit(self.session_id, exit_code)

    async def _read_loop_unix(self) -> None:
        loop = asyncio.get_running_loop()
        fd = self._master_fd
        try:
            while not self._stopped and fd is not None:
                try:
                    raw: bytes = await loop.run_in_executor(
                        None, lambda: os.read(fd, 4096)
                    )
                    if not raw:
                        break
                    self._on_output(self.session_id, raw)
                except OSError:
                    break
        finally:
            exit_code = -1
            if self._process is not None:
                try:
                    exit_code = await self._process.wait()
                except Exception:
                    pass
            if not self._stopped:
                self._on_exit(self.session_id, exit_code)

    async def write(self, data: str) -> None:
        """Write user input to the PTY stdin."""
        if sys.platform == "win32":
            if self._pty_process is not None:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: self._pty_process.write(data))
        else:
            if self._master_fd is not None:
                os.write(self._master_fd, data.encode("utf-8"))

    async def resize(self, cols: int, rows: int) -> None:
        """Resize the PTY terminal."""
        self._cols = cols
        self._rows = rows
        if sys.platform == "win32":
            if self._pty_process is not None:
                try:
                    self._pty_process.setwinsize(rows, cols)
                except Exception:
                    logger.debug("Failed to resize winpty", exc_info=True)
        else:
            if self._master_fd is not None:
                import fcntl  # noqa: PLC0415
                import struct
                import termios  # noqa: PLC0415

                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)  # type: ignore

    async def stop(self) -> None:
        """Kill the subprocess and clean up."""
        self._stopped = True

        # Terminate the process first — this unblocks any pending read()
        if sys.platform == "win32":
            if self._pty_process is not None:
                try:
                    self._pty_process.terminate()
                except Exception:
                    pass
        else:
            if self._process is not None:
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass

        # Now cancel the reader task (read should have unblocked from terminate)
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await asyncio.wait_for(self._reader_task, timeout=3)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # Clean up handles
        if sys.platform == "win32":
            self._pty_process = None
        else:
            self._process = None
            if self._master_fd is not None:
                try:
                    os.close(self._master_fd)
                except OSError:
                    pass
                self._master_fd = None
