"""Evaluations list panel for displaying evaluations in an eval set."""

from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, ListItem, ListView, Static


class EvaluationsListPanel(Vertical):
    """Panel that owns the evaluations ListView and its population logic."""

    def __init__(
        self,
        on_add_clicked: Callable[[], None] | None = None,
        on_assign_clicked: Callable[[], None] | None = None,
        on_evaluation_selected: Callable[[dict[str, Any]], None] | None = None,
        **kwargs,
    ):
        """Initialize the evaluations list panel.

        Args:
            on_add_clicked: Callback when "+ Add" button is clicked
            on_assign_clicked: Callback when "+ Assign" button is clicked
            on_evaluation_selected: Callback when an evaluation is selected
        """
        super().__init__(**kwargs)
        self.on_add_clicked = on_add_clicked
        self.on_assign_clicked = on_assign_clicked
        self.on_evaluation_selected = on_evaluation_selected
        self._eval_set_data: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        """Compose the evaluations list UI."""
        with Horizontal(classes="list-actions-row"):
            yield Button(
                "+ Add",
                id="add-evaluation-btn",
                variant="default",
                classes="tiny-btn",
            )
            yield Button(
                "+ Assign",
                id="assign-evaluator-btn",
                variant="default",
                classes="tiny-btn",
            )
        yield ListView(id="evaluations-list", classes="eval-items-list")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add-evaluation-btn" and self.on_add_clicked:
            self.on_add_clicked()
        elif event.button.id == "assign-evaluator-btn" and self.on_assign_clicked:
            self.on_assign_clicked()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list item selection."""
        if event.list_view.id == "evaluations-list" and event.item:
            eval_data = getattr(event.item, "eval_data", None)
            if eval_data and self.on_evaluation_selected:
                self.on_evaluation_selected(eval_data)

    def set_eval_set_data(self, data: dict[str, Any] | None) -> None:
        """Set the eval set data and refresh the list."""
        self._eval_set_data = data
        self.call_later(self._populate_list)

    async def _populate_list(self) -> None:
        """Populate the evaluations list from current data."""
        try:
            list_view = self.query_one("#evaluations-list", ListView)
            await list_view.clear()

            if not self._eval_set_data:
                return

            evaluations = self._eval_set_data.get("evaluations", [])
            for eval_item in evaluations:
                eval_id = eval_item.get("id", "")
                eval_name = eval_item.get("name", eval_id)

                item = ListItem(Static(f"{eval_name}"), classes="eval-list-item")
                item.eval_data = eval_item  # type: ignore
                await list_view.append(item)
        except Exception:
            pass

    async def refresh_list(self) -> None:
        """Refresh the list."""
        await self._populate_list()
