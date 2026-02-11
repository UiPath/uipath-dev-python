"""Validate the server module: imports, app creation, and API structure.

Run with: uv run python scripts/validate_server.py
"""

from __future__ import annotations

import sys


def _check(label: str, fn):
    """Run a check function and report pass/fail."""
    try:
        fn()
        print(f"  PASS  {label}")
        return True
    except Exception as e:
        print(f"  FAIL  {label}: {e}")
        return False


def check_model_imports():
    """Verify plain data classes import without Textual dependency."""
    from uipath.dev.models.data import ChatData, LogData, TraceData

    assert LogData is not None
    assert TraceData is not None
    assert ChatData is not None


def check_server_import():
    """Verify UiPathDeveloperServer imports."""
    from uipath.dev.server import UiPathDeveloperServer

    assert UiPathDeveloperServer is not None


def check_serializers():
    """Verify serializers produce valid dicts."""
    from datetime import datetime

    from uipath.dev.models.data import LogData, TraceData
    from uipath.dev.server.serializers import serialize_log, serialize_trace

    log = LogData(
        run_id="test-1", level="INFO", message="hello", timestamp=datetime.now()
    )
    result = serialize_log(log)
    assert isinstance(result, dict)
    assert result["run_id"] == "test-1"
    assert "timestamp" in result

    trace = TraceData(
        run_id="test-1",
        span_name="agent",
        span_id="span-1",
        timestamp=datetime.now(),
    )
    result = serialize_trace(trace)
    assert isinstance(result, dict)
    assert result["span_name"] == "agent"


def check_ws_protocol():
    """Verify WebSocket protocol enums."""
    from uipath.dev.server.ws.protocol import ClientCommand, ServerEvent

    assert ServerEvent.RUN_UPDATED.value == "run.updated"
    assert ServerEvent.LOG.value == "log"
    assert ServerEvent.TRACE.value == "trace"
    assert ServerEvent.CHAT.value == "chat"

    assert ClientCommand.SUBSCRIBE.value == "subscribe"
    assert ClientCommand.CHAT_MESSAGE.value == "chat.message"


def check_connection_manager():
    """Verify ConnectionManager instantiates."""
    from uipath.dev.server.ws.manager import ConnectionManager

    mgr = ConnectionManager()
    assert mgr is not None


def check_frontend_build_module():
    """Verify frontend_build module loads and functions exist."""
    from uipath.dev.server.frontend_build import (
        ensure_frontend_built,
        needs_build,
    )

    assert callable(needs_build)
    assert callable(ensure_frontend_built)


def check_app_factory():
    """Verify FastAPI app can be created (with a mock server)."""
    from unittest.mock import MagicMock

    from uipath.dev.server.app import create_app

    mock_server = MagicMock()
    mock_server.run_service = MagicMock()
    mock_server.connection_manager = MagicMock()
    mock_server.runtime_factory = MagicMock()
    mock_server.runtime_factory.list_entrypoints.return_value = []

    app = create_app(mock_server)
    assert app is not None
    assert app.title == "UiPath Developer Server"

    # Verify routes are registered
    route_paths = [getattr(route, "path", "") for route in app.routes]
    assert "/api/entrypoints" in route_paths
    assert "/api/runs" in route_paths


def main():
    """Run server module validation checks."""
    print("=" * 60)
    print("Server Module Validation")
    print("=" * 60)

    checks = [
        ("Plain data model imports (no Textual dep)", check_model_imports),
        ("UiPathDeveloperServer import", check_server_import),
        ("Serializers produce valid JSON dicts", check_serializers),
        ("WebSocket protocol enums", check_ws_protocol),
        ("ConnectionManager instantiation", check_connection_manager),
        ("Frontend build module loads", check_frontend_build_module),
        ("FastAPI app factory creates app with routes", check_app_factory),
    ]

    results = [_check(label, fn) for label, fn in checks]

    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        sys.exit(1)
    else:
        print("All checks passed!")


if __name__ == "__main__":
    main()
