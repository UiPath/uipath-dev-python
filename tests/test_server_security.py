"""Authentication and Host validation for the local dev server.

Scope is the PC-4894 work item: add authentication to the local server and
validate the Host header. CORS is left as-is, so nothing here asserts anything
about Access-Control headers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterator

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
def make_server(
    project: Path,
    mock_factory: Any,
    trace_manager: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[str], Any]:
    """Builds a developer server bound to a given host, with no frontend."""
    from uipath.dev.server import UiPathDeveloperServer, frontend_build

    monkeypatch.setattr(frontend_build, "ensure_frontend_built", lambda: False)
    monkeypatch.setenv("UIPATH_AUTH_ENABLED", "false")

    def build(host: str) -> Any:
        return UiPathDeveloperServer(
            runtime_factory=mock_factory,
            trace_manager=trace_manager,
            open_browser=False,
            host=host,
        )

    return build


@pytest.fixture()
def server(make_server: Callable[[str], Any]) -> Any:
    return make_server("localhost")


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


def test_a_configured_host_is_accepted(make_server: Callable[[str], Any]) -> None:
    """A server bound to one address must answer requests addressed to it."""
    srv = make_server("192.0.2.10")
    with TestClient(srv.create_app(), base_url="http://192.0.2.10:8080") as c:
        resp = c.get("/api/entrypoints", headers=auth(srv.auth_token))
    assert resp.status_code == 200


def test_a_wildcard_bind_does_not_widen_the_allowlist(
    make_server: Callable[[str], Any],
) -> None:
    """0.0.0.0 names every interface, so allowing it would allow any Host."""
    srv = make_server("0.0.0.0")
    with TestClient(srv.create_app(), base_url="http://0.0.0.0:8080") as c:
        resp = c.get("/api/entrypoints", headers=auth(srv.auth_token))
    assert resp.status_code == MISDIRECTED


def test_the_console_url_host_is_always_one_the_guard_accepts(
    make_server: Callable[[str], Any],
) -> None:
    """The banner URL and the Host allowlist must never disagree."""
    for bind in ("localhost", "127.0.0.1", "0.0.0.0", "192.0.2.10"):
        srv = make_server(bind)
        origin = srv.console_url.split("/?")[0]
        with TestClient(srv.create_app(), base_url=origin) as c:
            resp = c.get("/api/entrypoints", headers=auth(srv.auth_token))
        assert resp.status_code == 200, f"bind {bind} is unreachable at {origin}"


def test_the_console_page_loads_on_a_configured_host(
    make_server: Callable[[str], Any],
) -> None:
    """The guard runs before the path check, so a refused Host 421s the page too."""
    srv = make_server("192.0.2.10")
    with TestClient(srv.create_app(), base_url="http://192.0.2.10:8080") as c:
        assert c.get("/").status_code == 200


def test_a_wildcard_bind_is_not_handed_to_the_mcp_client(
    make_server: Callable[[str], Any],
) -> None:
    """uipath-dev-mcp dials this host, and the guard refuses a wildcard."""
    assert make_server("0.0.0.0").cli_agent_service._server_host == "localhost"


def test_the_token_is_never_taken_from_the_environment(
    make_server: Callable[[str], Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-run rotation is the point, so a pinned token must not be honoured."""
    monkeypatch.setenv("UIPATH_DEV_SERVER_TOKEN", "pinned-by-an-env-var")
    assert make_server("localhost").auth_token != "pinned-by-an-env-var"
