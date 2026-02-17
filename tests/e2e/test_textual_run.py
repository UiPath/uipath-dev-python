"""E2E tests for the Textual TUI (UiPathDeveloperConsole).

Uses Textual's built-in ``app.run_test()`` / ``Pilot`` API — no browser needed.
"""

import asyncio
import json

from textual.widgets import Footer, Input, Select

from tests.conftest import ENTRYPOINT_NUMBERS
from uipath.dev.ui.panels import NewRunPanel, RunDetailsPanel, RunHistoryPanel
from uipath.dev.ui.widgets.json_input import JsonInput

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _wait_for_entrypoint(app, *, timeout: float = 10.0):
    """Wait until NewRunPanel has a selected entrypoint (schema loaded)."""
    deadline = asyncio.get_event_loop().time() + timeout
    panel = app.query_one("#new-run-panel", NewRunPanel)
    while asyncio.get_event_loop().time() < deadline:
        if panel.selected_entrypoint:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError("Entrypoint not loaded in time")


async def _wait_for_status(app, status: str, *, timeout: float = 10.0):
    """Poll RunService until the *first* run reaches the expected status."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        for run in app.run_service.runs.values():
            if run.status == status:
                return run
        await asyncio.sleep(0.1)
    statuses = {r.id: r.status for r in app.run_service.runs.values()}
    raise TimeoutError(
        f"No run reached '{status}' within {timeout}s. Current: {statuses}"
    )


async def _wait_for_n_completed(app, n: int, *, timeout: float = 10.0):
    """Poll until *n* runs have status 'completed'."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        completed = [
            r for r in app.run_service.runs.values() if r.status == "completed"
        ]
        if len(completed) >= n:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Expected {n} completed runs, timed out")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_app_renders(app):
    """App starts, NewRunPanel and Footer are visible."""
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.query_one("#new-run-panel", NewRunPanel)
        assert app.query_one("#history-panel", RunHistoryPanel)
        assert app.query_one(Footer)


async def test_run_greeting_runtime(app):
    """Select greeting entrypoint, click Run, verify output."""
    async with app.run_test() as pilot:
        # Wait for entrypoint to be loaded (async on_mount)
        await _wait_for_entrypoint(app)
        await pilot.pause()

        # The first entrypoint is auto-selected; set JSON input
        json_input = app.query_one("#json-input", JsonInput)
        json_input.text = json.dumps({"name": "Tester"})
        await pilot.pause()

        # Click the Run button
        await pilot.click("#execute-btn")

        # Wait for the run to complete
        run = await _wait_for_status(app, "completed")

        assert run.output_data is not None
        assert "greeting" in run.output_data
        assert "Tester" in run.output_data["greeting"]


async def test_run_numbers_runtime(app):
    """Select numbers entrypoint, set input, click Run, verify output."""
    async with app.run_test() as pilot:
        await _wait_for_entrypoint(app)
        await pilot.pause()

        # Switch to numbers entrypoint
        select = app.query_one("#entrypoint-select", Select)
        select.value = ENTRYPOINT_NUMBERS
        await pilot.pause()

        # Set input data
        json_input = app.query_one("#json-input", JsonInput)
        json_input.text = json.dumps({"numbers": [1, 2, 3], "operation": "sum"})
        await pilot.pause()

        await pilot.click("#execute-btn")

        run = await _wait_for_status(app, "completed")

        assert run.output_data is not None
        assert run.output_data["result"] == 6.0
        assert run.output_data["operation"] == "sum"


async def test_run_history_shows_runs(app):
    """Run twice and verify RunHistoryPanel has 2 items."""
    async with app.run_test() as pilot:
        await _wait_for_entrypoint(app)
        await pilot.pause()

        # First run
        json_input = app.query_one("#json-input", JsonInput)
        json_input.text = json.dumps({"name": "Run1"})
        await pilot.pause()
        await pilot.click("#execute-btn")
        await _wait_for_status(app, "completed")

        # New run
        await pilot.press("n")
        await pilot.pause()

        # Second run
        json_input = app.query_one("#json-input", JsonInput)
        json_input.text = json.dumps({"name": "Run2"})
        await pilot.pause()
        await pilot.click("#execute-btn")

        await _wait_for_n_completed(app, 2)

        history = app.query_one("#history-panel", RunHistoryPanel)
        assert len(history.runs) == 2


async def test_new_run_button(app):
    """After running, press 'n' to show NewRunPanel again."""
    async with app.run_test() as pilot:
        await _wait_for_entrypoint(app)
        await pilot.pause()

        json_input = app.query_one("#json-input", JsonInput)
        json_input.text = json.dumps({"name": "Test"})
        await pilot.pause()
        await pilot.click("#execute-btn")
        await _wait_for_status(app, "completed")

        # Details panel should be visible, new-run-panel hidden
        details = app.query_one("#details-panel", RunDetailsPanel)
        new_panel = app.query_one("#new-run-panel", NewRunPanel)
        assert "hidden" not in details.classes
        assert "hidden" in new_panel.classes

        # Press 'n' to go back to new run
        await pilot.press("n")
        await pilot.pause()

        assert "hidden" not in new_panel.classes
        assert "hidden" in details.classes


async def test_chat_mode_greeting(app):
    """Start a chat run, send a message, verify it completes without timeout."""
    async with app.run_test() as pilot:
        await _wait_for_entrypoint(app)
        await pilot.pause()

        # Set valid JSON input (required for run creation)
        json_input = app.query_one("#json-input", JsonInput)
        json_input.text = json.dumps({"name": "Tester"})
        await pilot.pause()

        # Click the Chat button to start a chat-mode run
        await pilot.click("#chat-btn")
        await pilot.pause()

        # Details panel should be visible with chat input focused
        details_panel = app.query_one("#details-panel", RunDetailsPanel)
        chat_input = details_panel.query_one("#chat-input", Input)

        # Type a message and submit
        chat_input.value = "Hello there"
        await pilot.press("enter")

        # Wait for the run to complete (would timeout at 60s if auto-resume is broken)
        run = await _wait_for_status(app, "completed")

        assert run.output_data is not None
        assert "greeting" in run.output_data
