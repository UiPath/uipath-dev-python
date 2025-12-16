"""Eval sets tab component."""

import json
import os
from pathlib import Path
from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Select,
)
from uipath.eval._helpers import auto_discover_entrypoint

from uipath.dev.models.eval_run import EvalRun
from uipath.dev.services.eval_run_service import EvalRunService
from uipath.dev.services.eval_set_service import EvalSetService
from uipath.dev.services.evaluator_service import EvaluatorService


class EvalSetsTab(Horizontal):
    """Tab component for eval set configuration and run options."""

    selected_eval_set = reactive("")
    selected_entrypoint = reactive("")

    def __init__(
        self,
        evaluator_service: EvaluatorService | None = None,
        eval_set_service: EvalSetService | None = None,
        eval_run_service: EvalRunService | None = None,
        on_evaluation_selected: Callable[[dict[str, Any]], None] | None = None,
        on_add_evaluation_clicked: Callable[[], None] | None = None,
        on_assign_evaluator_clicked: Callable[[], None] | None = None,
        on_create_eval_set_clicked: Callable[[], None] | None = None,
        on_eval_set_changed: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the eval sets tab.

        Args:
            evaluator_service: Service for evaluator CRUD operations.
            eval_set_service: Service for eval set CRUD operations.
            eval_run_service: Service for eval run execution.
            on_evaluation_selected: Callback when an evaluation is selected.
            on_add_evaluation_clicked: Callback when add evaluation is clicked.
            on_assign_evaluator_clicked: Callback when assign evaluator is clicked.
            on_create_eval_set_clicked: Callback when create eval set is clicked.
            on_eval_set_changed: Callback when eval set selection changes.
        """
        super().__init__(**kwargs)
        self.evaluator_service = evaluator_service or EvaluatorService()
        self.eval_set_service = eval_set_service or EvalSetService()
        self.eval_run_service = eval_run_service or EvalRunService()

        # Action-specific callbacks
        self.on_evaluation_selected = on_evaluation_selected
        self.on_add_evaluation_clicked = on_add_evaluation_clicked
        self.on_assign_evaluator_clicked = on_assign_evaluator_clicked
        self.on_create_eval_set_clicked = on_create_eval_set_clicked
        self.on_eval_set_changed = on_eval_set_changed

        # Initialize entrypoints
        self.entrypoints: list[str] = []
        self.entrypoint_paths: list[str] = []
        self._load_entrypoints()

        # Initialize eval sets
        self.eval_sets: list[dict[str, Any]] = []
        self.eval_sets_paths: list[str] = []
        self._refresh_eval_sets()

        # Current eval set data (needed for creating runs)
        self.current_eval_set_data: dict[str, Any] | None = None

        # Run options
        self.workers_count = 1
        self.no_report = False
        self.enable_mocker_cache = False
        self.report_coverage = False
        self.output_file = ""
        self.eval_ids = ""
        self.eval_set_run_id = ""

    def _load_entrypoints(self) -> None:
        """Load available entrypoints."""
        try:
            json_path = os.path.join(os.getcwd(), "entry-points.json")
            with open(json_path, "r") as f:
                data = json.load(f)
            self.entrypoints = data.get("entryPoints", [])
            self.entrypoint_paths = [ep["filePath"] for ep in self.entrypoints]
            self.selected_entrypoint = (
                self.entrypoint_paths[0] if self.entrypoint_paths else ""
            )
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self.selected_entrypoint = ""

    def _refresh_eval_sets(self) -> None:
        """Refresh the list of available eval sets."""
        self.eval_sets = self.eval_set_service.list_eval_sets()
        self.eval_sets_paths = [es["file_path"] for es in self.eval_sets]
        if self.eval_sets_paths and not self.selected_eval_set:
            self.selected_eval_set = self.eval_sets_paths[0]

    def compose(self) -> ComposeResult:
        """Compose the eval sets tab UI for sidebar."""
        with Vertical(classes="eval-sets-main"):
            # Action buttons at top
            with Horizontal(classes="list-actions-row"):
                yield Button(
                    "▶ Run", id="eval-run-btn", variant="primary", classes="small-btn"
                )
                yield Button(
                    "+ Add",
                    id="create-eval-set-btn",
                    variant="default",
                    classes="small-btn",
                )

            # Scrollable form content
            with ScrollableContainer(classes="eval-sets-form"):
                # Eval Set selection
                yield Label("Eval Set:", classes="field-label-inline")
                yield Select(
                    options=[(Path(p).stem, p) for p in self.eval_sets_paths]
                    if self.eval_sets_paths
                    else [],
                    id="eval-set-dropdown",
                    value=self.selected_eval_set
                    if self.eval_sets_paths
                    else Select.BLANK,
                    allow_blank=True,
                    prompt="Select eval set...",
                )

                # Entrypoint selection
                yield Label("Entrypoint:", classes="field-label-inline")
                yield Select(
                    options=[(p, p) for p in self.entrypoint_paths]
                    if self.entrypoint_paths
                    else [],
                    id="entrypoint-dropdown",
                    value=self.selected_entrypoint
                    if self.entrypoint_paths
                    else Select.BLANK,
                    allow_blank=True,
                    prompt="Select entrypoint...",
                )

                # Run options
                yield Label("Workers:", classes="field-label-inline")
                yield Input(value="1", id="workers-input", classes="opt-input-small")
                yield Checkbox(
                    "No Report", id="no-report-checkbox", classes="opt-checkbox"
                )
                yield Checkbox(
                    "Mocker Cache",
                    id="enable-mocker-cache-checkbox",
                    classes="opt-checkbox",
                )
                yield Checkbox(
                    "Coverage", id="report-coverage-checkbox", classes="opt-checkbox"
                )

    async def on_mount(self) -> None:
        """Handle mount event."""
        if self.selected_eval_set:
            await self._load_eval_set_data()

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select changes."""
        if event.select.id == "eval-set-dropdown":
            self.selected_eval_set = str(event.value) if event.value else ""
            await self._load_eval_set_data()
            if self.on_eval_set_changed:
                self.on_eval_set_changed()
        elif event.select.id == "entrypoint-dropdown":
            self.selected_entrypoint = str(event.value) if event.value else ""

    async def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        if event.input.id == "workers-input":
            try:
                self.workers_count = int(event.value) if event.value else 1
            except ValueError:
                self.workers_count = 1
        elif event.input.id == "eval-ids-input":
            self.eval_ids = event.value
        elif event.input.id == "eval-set-run-id-input":
            self.eval_set_run_id = event.value
        elif event.input.id == "output-file-input":
            self.output_file = event.value

    async def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes."""
        checkbox_id = event.checkbox.id or ""
        if checkbox_id == "no-report-checkbox":
            self.no_report = event.value
        elif checkbox_id == "enable-mocker-cache-checkbox":
            self.enable_mocker_cache = event.value
        elif checkbox_id == "report-coverage-checkbox":
            self.report_coverage = event.value

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        btn_id = event.button.id or ""
        if btn_id == "create-eval-set-btn":
            await self._show_create_eval_set_form()

    def get_run_options(self) -> dict[str, Any]:
        """Get all options needed to create an EvalRun."""
        evaluator_refs = []
        if self.current_eval_set_data:
            evaluator_refs = self.current_eval_set_data.get("evaluatorRefs", [])

        eval_ids_list: list[str] = []
        if self.eval_ids:
            eval_ids_list = [
                id.strip() for id in self.eval_ids.split(",") if id.strip()
            ]

        return {
            "eval_set_path": self.selected_eval_set,
            "entrypoint": self.selected_entrypoint or auto_discover_entrypoint(),
            "evaluator_refs": evaluator_refs,
            "workers": self.workers_count,
            "no_report": self.no_report,
            "enable_mocker_cache": self.enable_mocker_cache,
            "report_coverage": self.report_coverage,
            "output_file": self.output_file or None,
            "eval_ids": eval_ids_list,
            "eval_set_run_id": self.eval_set_run_id or None,
        }

    def get_current_eval_set_data(self) -> dict[str, Any] | None:
        """Get the current eval set data."""
        return self.current_eval_set_data

    def set_current_eval_set_data(self, data: dict[str, Any] | None) -> None:
        """Set the current eval set data."""
        self.current_eval_set_data = data

    def get_selected_eval_set_path(self) -> str:
        """Get the selected eval set file path."""
        return self.selected_eval_set

    async def _load_eval_set_data(self) -> None:
        """Load the selected eval set data."""
        if not self.selected_eval_set:
            return

        eval_set_name = Path(self.selected_eval_set).stem
        self.current_eval_set_data = self.eval_set_service.load_eval_set(eval_set_name)

    def refresh_eval_sets(self) -> None:
        """Public method to refresh the eval sets list."""
        self._refresh_eval_sets()
        try:
            select = self.query_one("#eval-set-dropdown", Select)
            options = [(Path(p).stem, p) for p in self.eval_sets_paths]
            select.set_options(options)
            if self.eval_sets_paths:
                select.value = self.eval_sets_paths[0]
        except Exception:
            pass

    def select_eval_set(self, eval_set_id: str) -> None:
        """Select an eval set by ID.

        Args:
            eval_set_id: The eval set ID (file stem without extension).
        """
        # Find the matching path
        for path in self.eval_sets_paths:
            if Path(path).stem == eval_set_id:
                self.selected_eval_set = path
                try:
                    select = self.query_one("#eval-set-dropdown", Select)
                    select.value = path
                except Exception:
                    pass
                # Load the data for the selected eval set
                self.call_later(self._load_eval_set_data)
                if self.on_eval_set_changed:
                    self.on_eval_set_changed()
                break

    async def show_evaluation_detail(self, eval_data: dict[str, Any]) -> None:
        """Notify parent that an evaluation was selected."""
        if self.on_evaluation_selected:
            self.on_evaluation_selected(eval_data)

    async def _show_create_eval_set_form(self) -> None:
        """Notify parent to show create eval set form."""
        if self.on_create_eval_set_clicked:
            self.on_create_eval_set_clicked()

    async def show_add_evaluation_form(self) -> None:
        """Notify parent to show add evaluation form."""
        if not self.current_eval_set_data:
            self.app.notify("Please select an eval set first", severity="error")
            return
        if self.on_add_evaluation_clicked:
            self.on_add_evaluation_clicked()

    async def show_assign_evaluator_form(self) -> None:
        """Notify parent to show assign evaluator form."""
        if not self.current_eval_set_data:
            self.app.notify("Please select an eval set first", severity="error")
            return
        if self.on_assign_evaluator_clicked:
            self.on_assign_evaluator_clicked()

    def create_eval_run(self) -> EvalRun:
        """Create an EvalRun object from current selections."""
        eval_set_path = self.selected_eval_set
        entrypoint = self.selected_entrypoint or auto_discover_entrypoint()

        evaluator_refs = []
        if self.current_eval_set_data:
            evaluator_refs = self.current_eval_set_data.get("evaluatorRefs", [])

        eval_ids_list: list[str] = []
        if self.eval_ids:
            eval_ids_list = [
                id.strip() for id in self.eval_ids.split(",") if id.strip()
            ]

        return EvalRun(
            eval_set_path=eval_set_path,
            entrypoint=entrypoint,
            name=f"Eval: {Path(eval_set_path).stem}",
            status="running",
            evaluator_refs=evaluator_refs,
            workers=self.workers_count,
            no_report=self.no_report,
            enable_mocker_cache=self.enable_mocker_cache,
            report_coverage=self.report_coverage,
            output_file=self.output_file or None,
            eval_ids=eval_ids_list,
            eval_set_run_id=self.eval_set_run_id or None,
        )
