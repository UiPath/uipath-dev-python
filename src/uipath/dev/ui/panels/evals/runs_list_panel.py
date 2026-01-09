"""Eval runs list panel for displaying eval runs for an eval set."""

from pathlib import Path
from typing import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import ListItem, ListView, Static

from uipath.dev.models.eval_run import EvalRun
from uipath.dev.services.eval_run_service import EvalRunService


class EvalRunsListPanel(Vertical):
    """Panel that owns the eval runs ListView and its population logic."""

    def __init__(
        self,
        eval_run_service: EvalRunService | None = None,
        on_run_selected: Callable[[EvalRun], None] | None = None,
        **kwargs,
    ):
        """Initialize the eval runs list panel.

        Args:
            eval_run_service: The eval run service for loading runs
            on_run_selected: Callback when a run is selected
        """
        super().__init__(**kwargs)
        self.eval_run_service = eval_run_service
        self.on_run_selected = on_run_selected
        self._selected_eval_set: str = ""

    def compose(self) -> ComposeResult:
        """Compose the eval runs list UI."""
        yield ListView(id="eval-runs-list", classes="eval-items-list")

    def on_mount(self) -> None:
        """Set up periodic refresh for running items."""
        self.set_interval(5.0, self._refresh_running_items)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list item selection."""
        if event.list_view.id == "eval-runs-list" and event.item:
            eval_run = getattr(event.item, "eval_run", None)
            if eval_run and self.on_run_selected:
                self.on_run_selected(eval_run)

    def set_eval_set(self, eval_set_path: str) -> None:
        """Set the selected eval set and refresh the list."""
        self._selected_eval_set = eval_set_path
        self.call_later(self._populate_list)

    def set_eval_run_service(self, eval_run_service: EvalRunService) -> None:
        """Set the eval run service."""
        self.eval_run_service = eval_run_service

    async def _populate_list(self) -> None:
        """Populate the eval runs list from the service."""
        if not self._selected_eval_set or not self.eval_run_service:
            return

        try:
            eval_set_name = Path(self._selected_eval_set).stem
            runs = self.eval_run_service.get_runs_for_eval_set(eval_set_name)

            list_view = self.query_one("#eval-runs-list", ListView)
            await list_view.clear()

            for run in runs:
                item = ListItem(
                    Static(self._format_run_label(run)),
                    classes=f"eval-list-item run-{run.status}",
                )
                item.eval_run_id = run.id  # type: ignore
                item.eval_run = run  # type: ignore
                await list_view.append(item)
        except Exception:
            pass

    async def refresh_list(self) -> None:
        """Public method to refresh the list."""
        await self._populate_list()

    def add_run(self, run: EvalRun) -> None:
        """Add a new run to the list (at the top)."""
        self.call_later(self._populate_list)

    def update_run(self, run: EvalRun) -> None:
        """Update an existing run's display (targeted update, no full rebuild)."""
        self.call_later(lambda: self._update_list_item(run))

    async def _update_list_item(self, run: EvalRun) -> None:
        """Update only the ListItem corresponding to a single run."""
        try:
            list_view = self.query_one("#eval-runs-list", ListView)
        except Exception:
            return

        for item in list(list_view.children):
            run_id = getattr(item, "eval_run_id", None)
            if run_id != run.id:
                continue

            # Update label with formatted display_name
            try:
                static = item.query_one(Static)
                static.update(self._format_run_label(run))
            except Exception:
                continue

            # Update the stored run reference
            item.eval_run = run  # type: ignore

            # Update status-related CSS class
            new_classes = [cls for cls in item.classes if not cls.startswith("run-")]
            new_classes.append(f"run-{run.status}")
            item.set_classes(" ".join(new_classes))
            break

    def _format_run_label(self, run: EvalRun) -> Text:
        """Format the label for a run item."""
        base = run.display_name

        if not isinstance(base, Text):
            base = Text(str(base))

        text = base.copy()

        if not text.plain.startswith(" "):
            text = Text(" ") + text

        return text

    def _refresh_running_items(self) -> None:
        """Refresh display names for running items only."""
        if not self.eval_run_service:
            return

        # Get all runs for current eval set
        if not self._selected_eval_set:
            return

        eval_set_name = Path(self._selected_eval_set).stem
        runs = self.eval_run_service.get_runs_for_eval_set(eval_set_name)

        if not any(run.status == "running" for run in runs):
            return

        for run in runs:
            if run.status == "running":
                self.call_later(lambda r=run: self._update_list_item(r))
