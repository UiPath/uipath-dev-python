"""Loopback protection for the unauthenticated developer server."""

from __future__ import annotations

from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _hostname(header_value: str) -> str:
    """Extract the hostname from a Host/Origin header, dropping scheme and port."""
    value = header_value.strip()
    if "://" in value:
        value = value.split("://", 1)[1]
    if value.startswith("["):
        return value[1 : value.index("]")] if "]" in value else value[1:]
    return value.rsplit(":", 1)[0] if ":" in value else value


class LoopbackGuardMiddleware:
    """Reject requests whose Host or Origin is not loopback."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI app."""
        self.app = app

    def _allowed_hosts(self, scope: Scope) -> set[str]:
        allowed = set(_LOOPBACK_HOSTS)
        server = getattr(scope.get("app"), "state", None)
        configured = getattr(getattr(server, "server", None), "host", None)
        if configured:
            allowed.add(configured)
        return allowed

    def _is_allowed(self, scope: Scope) -> bool:
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        allowed = self._allowed_hosts(scope)

        host = headers.get(b"host")
        if host is not None and _hostname(host.decode("latin-1")) not in allowed:
            return False

        origin = headers.get(b"origin")
        if origin is not None and _hostname(origin.decode("latin-1")) not in allowed:
            return False

        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Guard HTTP and WebSocket scopes, pass everything else through."""
        if scope["type"] not in ("http", "websocket") or self._is_allowed(scope):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return

        await self._forbidden(send)

    async def _forbidden(self, send: Send) -> None:
        body = b"Forbidden: request rejected by loopback guard"
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def loopback_origin_regex(*args: Any) -> str:
    """Regex matching loopback origins for CORS ``allow_origin_regex``."""
    return r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
