"""Evaluators tab component."""

from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, ListItem, ListView, Static

from uipath.dev.services.evaluator_service import EvaluatorService


class EvaluatorsTab(Horizontal):
    """Tab component for listing existing evaluators and creating new ones."""

    def __init__(
        self,
        evaluator_service: EvaluatorService | None = None,
        on_evaluator_selected: Callable[[dict[str, Any]], None] | None = None,
        on_new_evaluator_clicked: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the evaluators tab.

        Args:
            evaluator_service: Service for evaluator CRUD operations.
            on_evaluator_selected: Callback when an evaluator is selected.
            on_new_evaluator_clicked: Callback when add button is clicked.
        """
        super().__init__(**kwargs)
        self.evaluator_service = evaluator_service or EvaluatorService()
        self.on_evaluator_selected = on_evaluator_selected
        self.on_new_evaluator_clicked = on_new_evaluator_clicked

    def compose(self) -> ComposeResult:
        """Compose the evaluators tab UI."""
        with Vertical(classes="eval-sets-main"):
            with Horizontal(classes="list-actions-row"):
                yield Button(
                    "+ Add", id="add-evaluator-btn", variant="default", classes="small-btn"
                )

            # List of existing evaluators
            yield ListView(id="existing-evaluators-list", classes="eval-items-list")

    async def on_mount(self) -> None:
        """Handle mount event - populate the list."""
        await self._populate_evaluators_list()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        btn_id = event.button.id or ""
        if btn_id == "add-evaluator-btn":
            if self.on_new_evaluator_clicked:
                self.on_new_evaluator_clicked()

    async def _populate_evaluators_list(self) -> None:
        """Populate the existing evaluators list."""
        try:
            list_view = self.query_one("#existing-evaluators-list", ListView)
            await list_view.clear()

            # Get existing evaluators from service
            evaluators = self.evaluator_service.list_evaluators()

            if not evaluators:
                item = ListItem(
                    Static("[dim]No evaluators yet. Click + Add to create one.[/dim]"),
                    classes="eval-list-item",
                )
                await list_view.append(item)
                return

            for ev in evaluators:
                ev_id = ev.get("id", "")

                item = ListItem(
                    Static(ev_id),
                    classes="eval-list-item",
                )
                item.evaluator_id = ev_id  # type: ignore
                item.evaluator_data = ev  # type: ignore
                await list_view.append(item)

        except Exception:
            pass

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list item selection."""
        if event.list_view.id == "existing-evaluators-list" and event.item:
            ev_data = getattr(event.item, "evaluator_data", None)
            if ev_data and self.on_evaluator_selected:
                self.on_evaluator_selected(ev_data)

    async def refresh_list(self) -> None:
        """Refresh the existing evaluators list."""
        await self._populate_evaluators_list()
