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
        "  const s = document.querySelector('select');"
        "  return s && s.options.length > 0"
        "    && !s.options[0].text.includes('Loading');"
        "}",
        timeout=10000,
    )


def _go_to_new_run(page: Page, url: str) -> None:
    """Navigate to the new run page and wait for entrypoints."""
    page.goto(f"{url}/#/new")
    expect(page.get_by_role("combobox")).to_be_visible()
    _wait_for_entrypoints(page)


def _run_and_wait_completed(page: Page) -> None:
    """Click Run, switch to Output tab, wait for completed status."""
    page.get_by_role("button", name="Run", exact=True).click()

    # After clicking Run, the app navigates to run details (Trace tab).
    # Switch to Output tab where the status badge lives.
    output_tab = page.get_by_role("button", name="Output")
    expect(output_tab).to_be_visible(timeout=10000)
    output_tab.click()

    # Wait for the completed status badge
    expect(page.get_by_text("Completed", exact=True)).to_be_visible(timeout=15000)


def test_new_run_page_loads(page: Page, live_server_url: str):
    """Navigate to / and verify new-run view renders with entrypoint dropdown."""
    _go_to_new_run(page, live_server_url)

    expect(page.get_by_text("New Run", exact=True)).to_be_visible()

    # Dropdown should have at least one real entrypoint
    combo = page.get_by_role("combobox")
    option_count = combo.evaluate("el => el.options.length")
    assert option_count >= 1


def test_run_greeting_and_check_output(page: Page, live_server_url: str):
    """Run the default entrypoint and verify output JSON appears."""
    _go_to_new_run(page, live_server_url)

    _run_and_wait_completed(page)

    # The output tab should render the JSON output from the greeting runtime
    expect(page.locator("pre").first).to_be_visible(timeout=5000)


def test_run_shows_traces(page: Page, live_server_url: str):
    """Run and verify the Trace/Output tab bar is shown."""
    _go_to_new_run(page, live_server_url)

    page.get_by_role("button", name="Run", exact=True).click()

    # Run details view should show both tab buttons
    expect(page.get_by_role("button", name="Trace")).to_be_visible(timeout=10000)
    expect(page.get_by_role("button", name="Output")).to_be_visible()


def test_sidebar_shows_run_history(page: Page, live_server_url: str):
    """Run, then verify sidebar gains a new entry."""
    _go_to_new_run(page, live_server_url)

    sidebar = page.locator("aside")
    before_count = sidebar.get_by_role("button").count()

    page.get_by_role("button", name="Run", exact=True).click()

    # Sidebar should now have one more button (the new run entry)
    expect(sidebar.get_by_role("button").nth(before_count)).to_be_visible(
        timeout=10000,
    )
