"""Access control for the local developer server (VULN-45646 / PC-4894)."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import parse_qs

TOKEN_ENV_VAR = "UIPATH_DEV_SERVER_TOKEN"
TOKEN_FILE = Path(".uipath") / "dev-server.token"

TOKEN_BYTES = 32
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})

UNAUTHORIZED = 401
MISDIRECTED = 421
WS_POLICY_VIOLATION = 1008


def generate_token() -> str:
    """Mint this run's token, honouring an externally supplied one."""
    return os.environ.get(TOKEN_ENV_VAR) or secrets.token_urlsafe(TOKEN_BYTES)


def write_token_file(token: str, directory: Path | None = None) -> Path:
    """Persist the token for `uipath-dev-mcp`, readable only by this user."""
    path = (directory / TOKEN_FILE.name) if directory else TOKEN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, token.encode("utf-8"))
    finally:
        os.close(fd)
    return path


def read_token_file(directory: Path | None = None) -> str | None:
    """Read the token a running server left behind, if any."""
    path = (directory / TOKEN_FILE.name) if directory else TOKEN_FILE
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def token_matches(presented: str | None, expected: str) -> bool:
    """Compare in constant time."""
    if not presented:
        return False
    return secrets.compare_digest(presented, expected)


def host_is_loopback(host_header: str | None) -> bool:
    """Whether a `Host` header names this machine. A missing header is refused."""
    if not host_header:
        return False
    host = host_header.strip().lower()
    if host.startswith("["):
        closing = host.find("]")
        if closing == -1:
            return False
        return host[: closing + 1] in LOOPBACK_HOSTS
    return host.rsplit(":", 1)[0] in LOOPBACK_HOSTS


def bearer_token(authorization: str | None) -> str | None:
    """Extract the token from an `Authorization: Bearer` header."""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return value.strip() or None


def query_token(query_string: bytes | str | None) -> str | None:
    """Extract the token from a query string, for the WebSocket handshake."""
    if not query_string:
        return None
    raw = (
        query_string.decode("latin-1")
        if isinstance(query_string, bytes)
        else query_string
    )
    values = parse_qs(raw).get("token") or []
    return values[0] or None if values else None


def api_path_requires_token(path: str) -> bool:
    """Whether a path is a token-protected API route."""
    return path == "/api" or path.startswith("/api/")
