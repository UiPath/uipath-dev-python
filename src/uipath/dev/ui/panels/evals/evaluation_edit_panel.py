"""Evaluation edit panel for adding/editing evaluations."""

import json
import uuid
from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Checkbox, Collapsible, Input, Static, TextArea

from uipath.dev.services.evaluator_service import EvaluatorService


class EvaluationEditPanel(Vertical):
    """Panel for adding or editing an evaluation."""

    def __init__(
        self,
        evaluator_service: EvaluatorService | None = None,
        on_save: Callable[[dict[str, Any]], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
        on_close: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the evaluation edit panel.

        Args:
            evaluator_service: Service for loading evaluator definitions.
            on_save: Callback with form data when save is clicked.
            on_delete: Callback with eval_id when delete is clicked.
            on_close: Callback when close button is clicked.
        """
        super().__init__(**kwargs)
        self.evaluator_service = evaluator_service or EvaluatorService()
        self.on_save = on_save
        self.on_delete = on_delete
        self.on_close = on_close

        self._evaluation_data: dict[str, Any] | None = None
        self._eval_set_data: dict[str, Any] | None = None
        self._eval_set_path: str = ""
        self._is_add_mode: bool = True
        self._enabled_evaluators: set[str] = set()
        self._evaluator_criterias: dict[str, dict[str, Any]] = {}

    def compose(self) -> ComposeResult:
        """Compose the panel UI."""
        yield ScrollableContainer(id="evaluation-edit-content")

    def set_data(
        self,
        evaluation: dict[str, Any] | None,
        eval_set_data: dict[str, Any] | None,
        eval_set_path: str = "",
    ) -> None:
        """Set the evaluation data and populate the form.

        Args:
            evaluation: The evaluation data to edit, or None for add mode.
            eval_set_data: The parent eval set data containing evaluatorRefs.
            eval_set_path: Path to the eval set file (for saving).
        """
        self._evaluation_data = evaluation
        self._eval_set_data = eval_set_data
        self._eval_set_path = eval_set_path
        self._is_add_mode = evaluation is None

        # Initialize enabled evaluators and criteria from evaluation data
        self._enabled_evaluators = set()
        self._evaluator_criterias = {}

        if evaluation:
            # Load existing criteria from evaluation
            # null/None means disabled, non-null (even empty {}) means enabled
            eval_criteria = evaluation.get("evaluationCriterias", {})
            for ev_ref, criteria in eval_criteria.items():
                if criteria is not None:
                    self._enabled_evaluators.add(ev_ref)
                    self._evaluator_criterias[ev_ref] = criteria

        self.call_later(self._populate_form)

    def get_updated_eval_set_data(self) -> dict[str, Any] | None:
        """Get the updated eval set data after save/delete."""
        return self._eval_set_data

    async def _populate_form(self) -> None:
        """Populate the form with current data."""
        try:
            content = self.query_one("#evaluation-edit-content", ScrollableContainer)
            await content.remove_children()

            # Close button
            await content.mount(
                Button("✕", id="close-evaluation-edit-btn", classes="close-btn")
            )

            # Name field
            await content.mount(Static("[bold]Name *[/bold]", classes="detail-row"))
            name_value = (
                self._evaluation_data.get("name", "")
                if self._evaluation_data
                else ""
            )
            await content.mount(
                Input(
                    value=name_value,
                    placeholder="Test case name" if self._is_add_mode else "",
                    id="evaluation-name-input",
                    classes="detail-input",
                )
            )

            # Inputs (JSON)
            await content.mount(Static("[bold]Input[/bold]", classes="detail-row"))
            await content.mount(
                Static(
                    "[dim]Provide the input data for this evaluation as a JSON object.[/dim]",
                    classes="helper-text",
                )
            )

            if self._evaluation_data:
                inputs_json = json.dumps(
                    self._evaluation_data.get("inputs", {}), indent=2
                )
            else:
                inputs_json = '{\n  "query": "your input here"\n}'

            await content.mount(
                TextArea(inputs_json, id="evaluation-inputs-textarea", classes="detail-json")
            )

            # Evaluator Criteria section
            await content.mount(
                Static("[bold]Evaluator Criteria[/bold]", classes="detail-row")
            )
            await content.mount(
                Static(
                    "[dim]Enable evaluators and configure their criteria. Expand each evaluator to customize values.[/dim]",
                    classes="helper-text",
                )
            )

            # Add collapsible sections for each evaluator
            if self._eval_set_data:
                evaluator_refs = self._eval_set_data.get("evaluatorRefs", [])
                for ev_ref in evaluator_refs:
                    await self._add_evaluator_criteria_section(content, ev_ref)

            # Action buttons
            buttons = [
                Button(
                    "Save",
                    id="save-evaluation-btn",
                    variant="primary",
                    classes="small-btn",
                )
            ]

            if not self._is_add_mode:
                buttons.append(
                    Button(
                        "Remove",
                        id="delete-evaluation-btn",
                        variant="error",
                        classes="small-btn",
                    )
                )

            await content.mount(Horizontal(*buttons, classes="list-actions-row"))

        except Exception:
            pass

    async def _add_evaluator_criteria_section(
        self, content: ScrollableContainer, ev_ref: str
    ) -> None:
        """Add a collapsible section for an evaluator's criteria."""
        # Load evaluator info
        ev_data = self.evaluator_service.load_evaluator(ev_ref)
        ev_desc = ev_data.get("description", "") if ev_data else ""

        # Get current criteria for this evaluator
        current_criteria = self._evaluator_criterias.get(ev_ref, {})
        is_enabled = ev_ref in self._enabled_evaluators

        # Get default criteria from evaluator definition
        default_criteria: dict[str, Any] = {}
        if ev_data:
            ev_config = ev_data.get("evaluatorConfig", {}) or {}
            default_criteria = ev_config.get("defaultEvaluationCriteria", {}) or {}

        # Merge with current criteria
        merged_criteria = {**default_criteria, **current_criteria}

        # Build criteria widgets list
        criteria_children: list = []
        if ev_desc:
            criteria_children.append(Static(f"[dim]{ev_desc}[/dim]", classes="ev-desc"))
        criteria_children.append(
            Static("[bold]EVALUATION CRITERIA[/bold]", classes="ev-criteria-header")
        )

        if merged_criteria:
            for key, value in merged_criteria.items():
                value_str = (
                    json.dumps(value)
                    if isinstance(value, (dict, list))
                    else str(value or "")
                )
                criteria_children.append(Static(f"{key}:", classes="ev-field-lbl"))
                criteria_children.append(
                    Input(
                        value=value_str,
                        id=f"ev-criteria-{ev_ref}-{key}",
                        classes="ev-field-input",
                    )
                )
        else:
            criteria_children.append(
                Static("[dim]No criteria fields[/dim]", classes="helper-text")
            )

        # Row with checkbox + collapsible
        ev_row = Horizontal(classes="ev-row")
        await content.mount(ev_row)

        await ev_row.mount(
            Checkbox("", value=is_enabled, id=f"ev-enable-{ev_ref}", classes="ev-cb")
        )

        # Collapsible with evaluator name as title
        collapsible = Collapsible(
            *criteria_children,
            title=ev_ref,
            collapsed=True,
            id=f"ev-collapse-{ev_ref}",
            classes="ev-collapse",
        )
        await ev_row.mount(collapsible)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        btn_id = event.button.id or ""

        if btn_id == "close-evaluation-edit-btn":
            event.stop()
            if self.on_close:
                self.on_close()
        elif btn_id == "save-evaluation-btn":
            event.stop()
            await self._handle_save()
        elif btn_id == "delete-evaluation-btn":
            event.stop()
            await self._handle_delete()

    async def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Track enabled/disabled evaluators."""
        cb_id = event.checkbox.id or ""
        if cb_id.startswith("ev-enable-"):
            ev_ref = cb_id.replace("ev-enable-", "")
            if event.value:
                self._enabled_evaluators.add(ev_ref)
            else:
                self._enabled_evaluators.discard(ev_ref)

    async def _handle_save(self) -> None:
        """Collect form data and emit to parent for persistence."""
        if not self._eval_set_data:
            return

        try:
            name_input = self.query_one("#evaluation-name-input", Input)
            inputs_area = self.query_one("#evaluation-inputs-textarea", TextArea)

            name = name_input.value.strip()
            if not name:
                self.app.notify("Name is required", severity="error")
                return

            # Parse inputs JSON
            try:
                inputs = json.loads(inputs_area.text)
            except json.JSONDecodeError:
                self.app.notify("Invalid JSON in inputs", severity="error")
                return

            # Collect evaluation criteria for all evaluators
            evaluation_criteria: dict[str, dict[str, Any] | None] = {}

            evaluator_refs = self._eval_set_data.get("evaluatorRefs", [])
            for ev_ref in evaluator_refs:
                # Disabled evaluators get null value
                if ev_ref not in self._enabled_evaluators:
                    evaluation_criteria[ev_ref] = None
                    continue

                # Load evaluator to get criteria keys
                ev_data = self.evaluator_service.load_evaluator(ev_ref)
                default_criteria: dict[str, Any] = {}
                if ev_data:
                    ev_config = ev_data.get("evaluatorConfig", {}) or {}
                    default_criteria = ev_config.get("defaultEvaluationCriteria", {}) or {}

                # Get existing criteria
                current_criteria = self._evaluator_criterias.get(ev_ref, {})
                merged_criteria = {**default_criteria, **current_criteria}

                # Collect from inputs
                criteria: dict[str, Any] = {}
                for key in merged_criteria.keys():
                    try:
                        inp = self.query_one(f"#ev-criteria-{ev_ref}-{key}", Input)
                        val_str = inp.value.strip()
                        try:
                            criteria[key] = json.loads(val_str)
                        except json.JSONDecodeError:
                            criteria[key] = val_str
                    except Exception:
                        criteria[key] = merged_criteria.get(key)

                evaluation_criteria[ev_ref] = criteria

            # Build form data to emit
            form_data: dict[str, Any] = {
                "name": name,
                "inputs": inputs,
                "evaluationCriterias": evaluation_criteria,
                "is_add_mode": self._is_add_mode,
                "eval_set_path": self._eval_set_path,
            }

            # Include existing ID for edit mode
            if not self._is_add_mode and self._evaluation_data:
                form_data["id"] = self._evaluation_data.get("id")
            else:
                # Generate ID for new evaluation
                form_data["id"] = str(uuid.uuid4())[:8]

            # Emit data to parent for persistence
            if self.on_save:
                self.on_save(form_data)

        except Exception as e:
            self.app.notify(f"Error collecting form data: {e}", severity="error")

    async def _handle_delete(self) -> None:
        """Emit eval_id to parent for deletion."""
        if not self._evaluation_data:
            return

        eval_id = self._evaluation_data.get("id")
        if not eval_id:
            return

        if self.on_delete:
            self.on_delete(eval_id)
