"""Security tests for the developer server loopback protections.

Covers VULN-45558: the unauthenticated file/run APIs must reject cross-site
(``Origin``) and DNS-rebinding (``Host``) requests, and must never serve the
UiPath Cloud access token stored in ``.env`` / ``.uipath``.
"""

import pytest
from fastapi import FastAPI, WebSocket
from starlette.testclient import TestClient

from uipath.dev.server.security import (
    LoopbackGuardMiddleware,
    _hostname,
    loopback_origin_regex,
)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(LoopbackGuardMiddleware)

    @app.get("/api/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("ok")
        await websocket.close()

    return app


def _client() -> TestClient:
    return TestClient(_app(), base_url="http://localhost")


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "localhost:8080"])
def test_loopback_host_allowed(host: str) -> None:
    resp = _client().get("/api/ping", headers={"Host": host})
    assert resp.status_code == 200


@pytest.mark.parametrize("host", ["evil.com", "attacker.example:8080", "169.254.1.1"])
def test_non_loopback_host_rejected(host: str) -> None:
    resp = _client().get("/api/ping", headers={"Host": host})
    assert resp.status_code == 403


def test_cross_site_origin_rejected() -> None:
    resp = _client().get("/api/ping", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403


def test_same_origin_allowed() -> None:
    resp = _client().get("/api/ping", headers={"Origin": "http://localhost:8080"})
    assert resp.status_code == 200


def test_no_origin_allowed() -> None:
    assert _client().get("/api/ping").status_code == 200


def test_websocket_rejects_cross_site_origin() -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with _client().websocket_connect(
            "/ws", headers={"Host": "localhost", "Origin": "https://evil.example"}
        ) as ws:
            ws.receive_text()


def test_websocket_allows_loopback() -> None:
    with _client().websocket_connect("/ws", headers={"Host": "localhost"}) as ws:
        assert ws.receive_text() == "ok"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("http://evil.example:8080", "evil.example"),
        ("localhost:8080", "localhost"),
        ("[::1]:8080", "::1"),
        ("127.0.0.1", "127.0.0.1"),
    ],
)
def test_hostname_parsing(value: str, expected: str) -> None:
    assert _hostname(value) == expected


def test_cors_regex_matches_loopback_only() -> None:
    import re

    pattern = re.compile(loopback_origin_regex())
    assert pattern.match("http://localhost:8080")
    assert pattern.match("http://127.0.0.1:8080")
    assert not pattern.match("https://evil.example")


def test_secret_files_are_blocked(monkeypatch) -> None:
    from fastapi import HTTPException

    from uipath.dev.server.routes import files

    for name in (".env", ".env.local"):
        with pytest.raises(HTTPException) as exc:
            files._reject_if_secret(files.ROOT / name)
        assert exc.value.status_code == 403

    with pytest.raises(HTTPException):
        files._reject_if_secret(files.ROOT / ".uipath" / ".auth.json")

    files._reject_if_secret(files.ROOT / "main.py")
