"""Panel for displaying execution run history."""

from typing import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, ListItem, ListView, Static

from uipath.dev.models.execution import ExecutionRun


class RunHistoryTab(Vertical):
    """Left panel showing execution run history."""

    def __init__(
        self,
        on_run_selected: Callable[[ExecutionRun], None] | None = None,
        on_new_run_clicked: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the run history tab.

        Args:
            on_run_selected: Callback when a run is selected.
            on_new_run_clicked: Callback when the "+ New" button is clicked.
        """
        super().__init__(**kwargs)
        self.runs: list[ExecutionRun] = []
        self.selected_run: ExecutionRun | None = None
        self.on_run_selected = on_run_selected
        self.on_new_run_clicked = on_new_run_clicked

    def compose(self) -> ComposeResult:
        """Compose the RunHistoryPanel layout."""
        yield ListView(id="run-list", classes="run-list")
        yield Button(
            "+ New",
            id="new-run-btn",
            variant="primary",
            classes="new-run-btn",
        )

    def on_mount(self) -> None:
        """Set up periodic refresh for running items."""
        self.set_interval(5.0, self._refresh_running_items)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "new-run-btn":
            if self.on_new_run_clicked:
                self.on_new_run_clicked()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list selection."""
        if event.list_view.id == "run-list" and event.item:
            run_id = getattr(event.item, "run_id", None)
            if run_id:
                run = self.get_run_by_id(run_id)
                if run and self.on_run_selected:
                    self.on_run_selected(run)

    def add_run(self, run: ExecutionRun) -> None:
        """Add a new run to history (at the top)."""
        self.runs.insert(0, run)
        self._rebuild_list()

    def update_run(self, run: ExecutionRun) -> None:
        """Update an existing run's row (does not insert new runs)."""
        for index, existing in enumerate(self.runs):
            if existing.id == run.id:
                self.runs[index] = run
                self._update_list_item(run)
                break
        # If run not found, just ignore; creation is done via add_run()

    def get_run_by_id(self, run_id: str) -> ExecutionRun | None:
        """Get a run by ID."""
        for run in self.runs:
            if run.id == run_id:
                return run
        return None

    def clear_runs(self) -> None:
        """Clear all runs from history."""
        self.runs.clear()
        self._rebuild_list()

    def _format_run_label(self, run: ExecutionRun) -> Text:
        """Format the label for a run item."""
        base = run.display_name

        # Ensure we have a Text object
        if not isinstance(base, Text):
            base = Text(str(base))

        # Work on a copy so we don't mutate the model’s display_name
        text = base.copy()

        # We want exactly one leading space visually.
        # Rich Text doesn't have an in-place "lstrip" that keeps spans perfect,
        # so we just check the plain text and conditionally prepend.
        if not text.plain.startswith(" "):
            text = Text(" ") + text

        return text

    def _rebuild_list(self) -> None:
        """Rebuild the entire list."""
        try:
            run_list = self.query_one("#run-list", ListView)
            run_list.clear()

            for run in self.runs:
                item = self._create_list_item(run)
                run_list.append(item)
        except Exception:
            pass

    def _create_list_item(self, run: ExecutionRun) -> ListItem:
        item = ListItem(
            Static(run.display_name),
            classes=f"run-item run-{run.status}",
        )
        item.run_id = run.id  # type: ignore[attr-defined]
        return item

    def _update_list_item(self, run: ExecutionRun) -> None:
        """Update only the ListItem corresponding to a single run."""
        try:
            run_list = self.query_one("#run-list", ListView)
        except Exception:
            return

        for item in list(run_list.children):
            run_id = getattr(item, "run_id", None)
            if run_id != run.id:
                continue

            # Update label
            try:
                static = item.query_one(Static)
                static.update(self._format_run_label(run))
            except Exception:
                continue

            # Update status-related CSS class
            new_classes = [cls for cls in item.classes if not cls.startswith("run-")]
            new_classes.append(f"run-{run.status}")
            item.set_classes(" ".join(new_classes))
            break

    def _refresh_running_items(self) -> None:
        """Refresh display names for running items only."""
        if not any(run.status == "running" for run in self.runs):
            return None

        for run in self.runs:
            if run.status == "running":
                self._update_list_item(run)
