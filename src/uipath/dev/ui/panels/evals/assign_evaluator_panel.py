"""Assign evaluator panel for assigning evaluators to an eval set."""

import json
from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Checkbox, Collapsible, Static

from uipath.dev.services.evaluator_service import EvaluatorService


class AssignEvaluatorPanel(Vertical):
    """Panel for assigning evaluators to an eval set."""

    def __init__(
        self,
        evaluator_service: EvaluatorService | None = None,
        on_assign: Callable[[list[str]], None] | None = None,
        on_close: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the assign evaluator panel.

        Args:
            evaluator_service: Service for loading evaluator definitions.
            on_assign: Callback with selected evaluator IDs when assign is clicked.
            on_close: Callback when close button is clicked.
        """
        super().__init__(**kwargs)
        self.evaluator_service = evaluator_service or EvaluatorService()
        self.on_assign = on_assign
        self.on_close = on_close

        self._unassigned_evaluators: list[dict[str, Any]] = []
        self._selected_evaluators: set[str] = set()
        self._eval_set_data: dict[str, Any] | None = None
        self._eval_set_path: str = ""

    def compose(self) -> ComposeResult:
        """Compose the panel UI."""
        yield ScrollableContainer(id="assign-evaluator-content")

    def set_data(
        self,
        unassigned: list[dict[str, Any]],
        eval_set_data: dict[str, Any] | None,
        eval_set_path: str = "",
    ) -> None:
        """Set the data and populate the form.

        Args:
            unassigned: List of evaluator dicts that are not yet assigned.
            eval_set_data: The parent eval set data.
            eval_set_path: Path to the eval set file (for saving).
        """
        self._unassigned_evaluators = unassigned
        self._eval_set_data = eval_set_data
        self._eval_set_path = eval_set_path
        self._selected_evaluators = set()
        self.call_later(self._populate_form)

    def get_updated_eval_set_data(self) -> dict[str, Any] | None:
        """Get the updated eval set data after assign."""
        return self._eval_set_data

    async def _populate_form(self) -> None:
        """Populate the form with unassigned evaluators."""
        try:
            content = self.query_one("#assign-evaluator-content", ScrollableContainer)
            await content.remove_children()

            if not self._unassigned_evaluators:
                await content.mount(
                    Static(
                        "[dim]All evaluators are already assigned.[/dim]",
                        classes="helper-text",
                    )
                )
                return

            # Close button
            await content.mount(
                Button("✕", id="close-assign-evaluator-btn", classes="close-btn")
            )

            # Info text
            await content.mount(
                Static("[bold]Assign Evaluators[/bold]", classes="detail-row")
            )
            await content.mount(
                Static(
                    "[dim]Select evaluators to assign to this eval set. Expand to see details.[/dim]",
                    classes="helper-text",
                )
            )

            # Add checkbox + collapsible for each unassigned evaluator
            for ev in self._unassigned_evaluators:
                ev_id = ev.get("id", "")
                if ev_id:
                    await self._add_evaluator_info_section(content, ev_id)

            # Assign button
            await content.mount(
                Button(
                    "Assign Selected",
                    id="do-assign-evaluator-btn",
                    variant="primary",
                    classes="small-btn",
                )
            )

        except Exception:
            pass

    async def _add_evaluator_info_section(
        self, content: ScrollableContainer, ev_ref: str
    ) -> None:
        """Add a collapsible section showing evaluator info."""
        # Load evaluator info
        ev_data = self.evaluator_service.load_evaluator(ev_ref)
        ev_desc = ev_data.get("description", "") if ev_data else ""

        # Get default criteria from evaluator definition
        default_criteria = {}
        if ev_data:
            ev_config = ev_data.get("evaluatorConfig", {})
            default_criteria = ev_config.get("defaultEvaluationCriteria", {})

        # Build info widgets list - description and default criteria (read-only)
        info_children: list = []
        if ev_desc:
            info_children.append(Static(f"[dim]{ev_desc}[/dim]", classes="ev-desc"))

        if default_criteria:
            info_children.append(
                Static("[bold]DEFAULT CRITERIA[/bold]", classes="ev-criteria-header")
            )
            for key, value in default_criteria.items():
                value_str = (
                    json.dumps(value)
                    if isinstance(value, (dict, list))
                    else str(value or "")
                )
                info_children.append(
                    Static(f"[dim]{key}:[/dim] {value_str}", classes="ev-field-lbl")
                )
        else:
            info_children.append(
                Static("[dim]No default criteria[/dim]", classes="helper-text")
            )

        # Row with checkbox + collapsible
        ev_row = Horizontal(classes="ev-row")
        await content.mount(ev_row)

        is_selected = ev_ref in self._selected_evaluators
        await ev_row.mount(
            Checkbox(
                "", value=is_selected, id=f"assign-ev-{ev_ref}", classes="ev-cb"
            )
        )

        # Collapsible with evaluator name as title
        collapsible = Collapsible(
            *info_children,
            title=ev_ref,
            collapsed=True,
            id=f"assign-ev-collapse-{ev_ref}",
            classes="ev-collapse",
        )
        await ev_row.mount(collapsible)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        btn_id = event.button.id or ""

        if btn_id == "close-assign-evaluator-btn":
            event.stop()
            if self.on_close:
                self.on_close()
        elif btn_id == "do-assign-evaluator-btn":
            event.stop()
            await self._handle_assign()

    async def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Track selected evaluators."""
        cb_id = event.checkbox.id or ""
        if cb_id.startswith("assign-ev-"):
            ev_ref = cb_id.replace("assign-ev-", "")
            if event.value:
                self._selected_evaluators.add(ev_ref)
            else:
                self._selected_evaluators.discard(ev_ref)

    async def _handle_assign(self) -> None:
        """Emit selected evaluator IDs to parent."""
        if not self._selected_evaluators:
            self.app.notify("Please select at least one evaluator", severity="error")
            return

        if self.on_assign:
            self.on_assign(list(self._selected_evaluators))
