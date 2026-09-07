"""Authentication and Host validation for the local dev server.

Scope is the PC-4894 work item: add authentication to the local server and
validate the Host header. CORS is left as-is, so nothing here asserts anything
about Access-Control headers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

CONSOLE_ORIGIN = "http://localhost:8080"
UNAUTHORIZED = 401
MISDIRECTED = 421
STOLEN_TOKEN = "super-secret-token"


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway agent project whose .env holds cloud credentials."""
    (tmp_path / ".env").write_text(f"UIPATH_ACCESS_TOKEN={STOLEN_TOKEN}\n")
    (tmp_path / "main.py").write_text("def main():\n    return {}\n")
    monkeypatch.chdir(tmp_path)

    from uipath.dev.server.routes import files as files_routes

    monkeypatch.setattr(files_routes, "ROOT", tmp_path.resolve())
    return tmp_path


@pytest.fixture()
def server(
    project: Path,
    mock_factory: Any,
    trace_manager: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """A developer server on the mock factory, with no frontend build."""
    from uipath.dev.server import UiPathDeveloperServer, frontend_build

    monkeypatch.setattr(frontend_build, "ensure_frontend_built", lambda: False)
    monkeypatch.setenv("UIPATH_AUTH_ENABLED", "false")

    return UiPathDeveloperServer(
        runtime_factory=mock_factory,
        trace_manager=trace_manager,
        open_browser=False,
    )


@pytest.fixture()
def client(server: Any) -> Iterator[TestClient]:
    with TestClient(server.create_app(), base_url=CONSOLE_ORIGIN) as c:
        yield c


@pytest.fixture()
def token(server: Any) -> str:
    return server.auth_token


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def ws_rejected(
    client: TestClient, url: str, headers: dict[str, str] | None = None
) -> bool:
    """Whether the server refused the upgrade. Handshake only, never reads."""
    try:
        with client.websocket_connect(url, headers=headers or {}):
            return False
    except WebSocketDisconnect:
        return True


@pytest.mark.parametrize(
    "path", ["/api/entrypoints", "/api/files/tree", "/api/statedb/status"]
)
def test_api_routes_require_a_token(client: TestClient, path: str) -> None:
    """Across three routers, to prove the gate is not per-route."""
    assert client.get(path).status_code == UNAUTHORIZED


def test_api_rejects_a_wrong_token(client: TestClient) -> None:
    resp = client.get("/api/entrypoints", headers=auth("not-the-token"))
    assert resp.status_code == UNAUTHORIZED


def test_api_accepts_the_right_token(client: TestClient, token: str) -> None:
    resp = client.get("/api/entrypoints", headers=auth(token))
    assert resp.status_code == 200


def test_reported_credential_theft_is_refused(client: TestClient) -> None:
    """The report's exfiltration request, verbatim."""
    resp = client.get("/api/files/content?path=.env")
    assert resp.status_code == UNAUTHORIZED
    assert STOLEN_TOKEN not in resp.text


def test_reported_rce_chain_is_refused(client: TestClient) -> None:
    """The report's write-an-entrypoint-then-run-it chain, verbatim."""
    write = client.put(
        "/api/files/content?path=main.py",
        json={"content": "import os\nos.system('id')\n"},
    )
    run = client.post(
        "/api/runs", json={"entrypoint": "agent/greeting.py:main", "input_data": {}}
    )
    assert write.status_code == UNAUTHORIZED
    assert run.status_code == UNAUTHORIZED


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8080"])
def test_rebound_host_header_is_rejected(
    client: TestClient, token: str, host: str
) -> None:
    """A DNS name pointed at 127.0.0.1 would otherwise be same-origin."""
    resp = client.get("/api/entrypoints", headers={**auth(token), "Host": host})
    assert resp.status_code == MISDIRECTED, f"accepted Host: {host}"


@pytest.mark.parametrize("host", ["localhost:8080", "127.0.0.1:8080", "[::1]:8080"])
def test_loopback_host_headers_are_accepted(
    client: TestClient, token: str, host: str
) -> None:
    resp = client.get("/api/entrypoints", headers={**auth(token), "Host": host})
    assert resp.status_code == 200, f"rejected legitimate Host: {host}"


def test_websocket_requires_a_token(client: TestClient) -> None:
    """CORS never applies here, so the token is the only gate."""
    assert ws_rejected(client, "/ws")


def test_websocket_accepts_the_console(client: TestClient, token: str) -> None:
    assert not ws_rejected(client, f"/ws?token={token}")


def test_token_file_is_owner_readable_only(project: Path, server: Any) -> None:
    """uipath-dev-mcp reads the token from disk, so the mode is the ACL."""
    import sys

    from uipath.dev.server.security import write_token_file

    path = write_token_file(server.auth_token)
    assert path.read_text().strip() == server.auth_token

    if sys.platform != "win32":
        assert path.stat().st_mode & 0o777 == 0o600
