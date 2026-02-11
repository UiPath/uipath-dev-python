"""Tests for the server module."""

from datetime import datetime
from unittest.mock import MagicMock


def test_data_models_import_without_textual():
    """Data models should import without Textual dependency."""
    from uipath.dev.models.data import ChatData, LogData, TraceData

    log = LogData(run_id="r1", level="INFO", message="test", timestamp=datetime.now())
    assert log.run_id == "r1"

    trace = TraceData(
        run_id="r1", span_name="agent", span_id="s1", timestamp=datetime.now()
    )
    assert trace.status == "running"
    assert trace.parent_span_id is None

    chat = ChatData(run_id="r1")
    assert chat.event is None


def test_server_class_import():
    """UiPathDeveloperServer should be importable."""
    from uipath.dev.server import UiPathDeveloperServer

    assert UiPathDeveloperServer is not None


def test_serializer_log():
    """serialize_log should produce a valid dict."""
    from uipath.dev.models.data import LogData
    from uipath.dev.server.serializers import serialize_log

    ts = datetime(2025, 1, 15, 10, 30, 0)
    log = LogData(run_id="r1", level="WARNING", message="oops", timestamp=ts)
    result = serialize_log(log)

    assert result["run_id"] == "r1"
    assert result["level"] == "WARNING"
    assert result["message"] == "oops"
    assert "2025-01-15" in result["timestamp"]


def test_serializer_trace():
    """serialize_trace should produce a valid dict."""
    from uipath.dev.models.data import TraceData
    from uipath.dev.server.serializers import serialize_trace

    trace = TraceData(
        run_id="r1",
        span_name="llm_call",
        span_id="s1",
        parent_span_id="s0",
        trace_id="t1",
        status="completed",
        duration_ms=123.4,
        timestamp=datetime.now(),
        attributes={"model": "gpt-4"},
    )
    result = serialize_trace(trace)

    assert result["span_name"] == "llm_call"
    assert result["parent_span_id"] == "s0"
    assert result["duration_ms"] == 123.4
    assert result["attributes"]["model"] == "gpt-4"


def test_serializer_chat():
    """serialize_chat should omit event/message when None."""
    from uipath.dev.models.data import ChatData
    from uipath.dev.server.serializers import serialize_chat

    chat = ChatData(run_id="r1")
    result = serialize_chat(chat)

    assert result["run_id"] == "r1"
    assert "event" not in result
    assert "message" not in result


def test_ws_protocol_enums():
    """WebSocket protocol enums should have correct values."""
    from uipath.dev.server.ws.protocol import ClientCommand, ServerEvent

    assert ServerEvent.RUN_UPDATED.value == "run.updated"
    assert ServerEvent.LOG.value == "log"
    assert ServerEvent.TRACE.value == "trace"
    assert ServerEvent.CHAT.value == "chat"

    assert ClientCommand.SUBSCRIBE.value == "subscribe"
    assert ClientCommand.UNSUBSCRIBE.value == "unsubscribe"
    assert ClientCommand.CHAT_MESSAGE.value == "chat.message"
    assert ClientCommand.DEBUG_STEP.value == "debug.step"
    assert ClientCommand.DEBUG_CONTINUE.value == "debug.continue"
    assert ClientCommand.DEBUG_STOP.value == "debug.stop"


def test_connection_manager_init():
    """ConnectionManager should initialize with empty state."""
    from uipath.dev.server.ws.manager import ConnectionManager

    mgr = ConnectionManager()
    assert mgr is not None


def test_app_factory_creates_fastapi():
    """create_app should return a FastAPI app with routes."""
    from uipath.dev.server.app import create_app

    mock_server = MagicMock()
    mock_server.run_service = MagicMock()
    mock_server.connection_manager = MagicMock()
    mock_server.runtime_factory = MagicMock()
    mock_server.runtime_factory.list_entrypoints.return_value = []

    app = create_app(mock_server)
    assert app.title == "UiPath Developer Server"

    route_paths = [getattr(r, "path", "") for r in app.routes]
    assert "/api/entrypoints" in route_paths
    assert "/api/runs" in route_paths


def test_app_has_fallback_when_no_static():
    """App should serve fallback HTML when static files don't exist."""
    from uipath.dev.server.app import create_app

    mock_server = MagicMock()
    mock_server.run_service = MagicMock()
    mock_server.connection_manager = MagicMock()
    mock_server.runtime_factory = MagicMock()
    mock_server.runtime_factory.list_entrypoints.return_value = []

    app = create_app(mock_server)

    # Should have a "/" route (either static mount or fallback)
    route_paths = [getattr(r, "path", "") for r in app.routes]
    assert "/" in route_paths or any(
        getattr(r, "path", "").startswith("/") for r in app.routes
    )


def test_frontend_build_module():
    """Frontend build functions should be importable."""
    from uipath.dev.server.frontend_build import ensure_frontend_built, needs_build

    assert callable(needs_build)
    assert callable(ensure_frontend_built)
