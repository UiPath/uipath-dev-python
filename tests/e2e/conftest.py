"""E2E-specific fixtures for Textual TUI and web server tests."""

import socket
import threading
import time

import pytest
from uipath.core.tracing import UiPathTraceManager

from tests.conftest import MockRuntimeFactory
from uipath.dev import UiPathDeveloperConsole


@pytest.fixture()
def app(mock_factory, trace_manager):
    """Create a UiPathDeveloperConsole instance for Textual pilot tests."""
    return UiPathDeveloperConsole(
        runtime_factory=mock_factory,
        trace_manager=trace_manager,
    )


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server_url():
    """Start a real FastAPI server in a background thread and yield its URL.

    Session-scoped so the server is started only once for all web tests.
    Uses 'live_server_url' (not 'base_url') to avoid conflicting with the
    autouse session fixture from pytest-base-url, which would force the
    server to start even for non-web tests.
    """
    try:
        import uvicorn

        from uipath.dev.server import UiPathDeveloperServer
    except ImportError:
        pytest.skip("server dependencies not installed (pip install uipath-dev)")

    factory = MockRuntimeFactory()
    trace_mgr = UiPathTraceManager()
    port = _find_free_port()

    server_obj = UiPathDeveloperServer(
        runtime_factory=factory,
        trace_manager=trace_mgr,
        host="127.0.0.1",
        port=port,
        open_browser=False,
    )
    fastapi_app = server_obj.create_app()

    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    uv_server = uvicorn.Server(config)

    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()

    # Wait for server to be ready
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("Server did not start in time")

    yield url

    uv_server.should_exit = True
    thread.join(timeout=5)
