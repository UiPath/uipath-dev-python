"""E2E tests for the web frontend (Playwright against FastAPI server).

Requires:
    pip install pytest-playwright
    playwright install chromium
"""

from playwright.sync_api import Page, expect


def _wait_for_entrypoints(page: Page) -> None:
    """Wait until the entrypoint dropdown has real options loaded."""
    page.wait_for_function(
        "() => {"
        "  const s = document.querySelector('#entrypoint-select');"
        "  return s && s.options.length > 0"
        "    && !s.options[0].text.includes('Loading');"
        "}",
        timeout=10000,
    )


def _go_to_new_run(page: Page, url: str) -> None:
    """Navigate to the new run page and wait for entrypoints."""
    page.goto(f"{url}/#/new")
    expect(page.locator("#entrypoint-select")).to_be_visible()
    _wait_for_entrypoints(page)


def _run_autonomous_and_wait_completed(page: Page) -> None:
    """Click Autonomous, then Execute, switch to I/O tab, wait for output."""
    # Click Autonomous mode card
    page.get_by_role("button", name="Autonomous").click()

    # Wait for setup view with Execute button
    execute_btn = page.get_by_role("button", name="Execute")
    expect(execute_btn).to_be_visible(timeout=10000)
    execute_btn.click()

    # After clicking Execute, the app navigates to run details.
    # Switch to I/O tab and wait for output to appear (proves run completed).
    io_tab = page.get_by_role("button", name="I/O")
    expect(io_tab).to_be_visible(timeout=10000)
    io_tab.click()

    # Wait for the Output section to appear (only rendered after run completes)
    expect(page.get_by_text("Output", exact=True)).to_be_visible(timeout=15000)


def test_new_run_page_loads(page: Page, live_server_url: str):
    """Navigate to / and verify new-run view renders with entrypoint dropdown."""
    _go_to_new_run(page, live_server_url)

    expect(page.get_by_text("New Run", exact=True)).to_be_visible()

    # Dropdown should have at least one real entrypoint
    combo = page.locator("#entrypoint-select")
    option_count = combo.evaluate("el => el.options.length")
    assert option_count >= 1


def test_run_greeting_and_check_output(page: Page, live_server_url: str):
    """Run the default entrypoint and verify output JSON appears."""
    _go_to_new_run(page, live_server_url)

    _run_autonomous_and_wait_completed(page)

    # The I/O tab should render the JSON output from the greeting runtime
    expect(page.locator("pre").first).to_be_visible(timeout=5000)


def test_run_shows_sidebar_tabs(page: Page, live_server_url: str):
    """Run and verify the sidebar tabs (Events, I/O, Logs) are shown."""
    _go_to_new_run(page, live_server_url)

    # Click Autonomous mode card
    page.get_by_role("button", name="Autonomous").click()

    # Wait for setup view, then execute
    execute_btn = page.get_by_role("button", name="Execute")
    expect(execute_btn).to_be_visible(timeout=10000)
    execute_btn.click()

    # Run details view should show sidebar tab buttons
    expect(page.get_by_role("button", name="Events")).to_be_visible(timeout=10000)
    expect(page.get_by_role("button", name="I/O")).to_be_visible()
    expect(page.get_by_role("button", name="Logs")).to_be_visible()


def test_sidebar_shows_run_history(page: Page, live_server_url: str):
    """Run, then verify sidebar gains a new entry."""
    _go_to_new_run(page, live_server_url)

    sidebar = page.locator("aside")
    before_count = sidebar.get_by_role("button").count()

    # Click Autonomous mode card
    page.get_by_role("button", name="Autonomous").click()

    # Wait for setup view, then execute
    execute_btn = page.get_by_role("button", name="Execute")
    expect(execute_btn).to_be_visible(timeout=10000)
    execute_btn.click()

    # Sidebar should now have one more button (the new run entry)
    expect(sidebar.get_by_role("button").nth(before_count)).to_be_visible(
        timeout=10000,
    )
