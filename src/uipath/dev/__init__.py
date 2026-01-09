"""UiPath Developer Console Application."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pyperclip  # type: ignore[import-untyped]
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import (
    Button,
    Footer,
    Input,
    ListView,
    RichLog,
    TabbedContent,
    TabPane,
)
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import UiPathRuntimeFactoryProtocol

from uipath.dev.infrastructure import (
    patch_textual_stderr,
)
from uipath.dev.models import (
    ChatMessage,
    EvalRun,
    ExecutionMode,
    ExecutionRun,
    LogMessage,
    TraceMessage,
)
from uipath.dev.models.chat import get_user_message, get_user_message_event
from uipath.dev.services import (
    EvalRunService,
    EvalSetService,
    EvaluatorService,
    RunService,
)
from uipath.dev.ui.panels.evals import (
    AssignEvaluatorPanel,
    EvalRunDetailsPanel,
    EvalRunsListPanel,
    EvalSetCreatePanel,
    EvaluationEditPanel,
    EvaluationsListPanel,
)
from uipath.dev.ui.panels.evaluators import EvaluatorFormPanel
from uipath.dev.ui.panels.runs import NewRunPanel, RunDetailsPanel
from uipath.dev.ui.panels.sidebar import SidebarPanel


class UiPathDeveloperConsole(App[Any]):
    """UiPath developer console interface."""

    TITLE = "UiPath Developer Console"
    SUB_TITLE = (
        "Interactive terminal application for building, testing, and debugging "
        "UiPath Python runtimes, agents, and automation scripts."
    )
    CSS_PATH = Path(__file__).parent / "ui" / "styles" / "terminal.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_run", "New"),
        Binding("r", "execute_run", "Run"),
        Binding("c", "copy", "Copy"),
        Binding("h", "clear_history", "Clear History"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        runtime_factory: UiPathRuntimeFactoryProtocol,
        trace_manager: UiPathTraceManager,
        **kwargs,
    ):
        """Initialize the UiPath Dev Terminal App."""
        # Capture subprocess stderr lines and route to our log handler
        self._stderr_write_fd: int = patch_textual_stderr(self._add_subprocess_log)

        super().__init__(**kwargs)

        self.runtime_factory = runtime_factory
        self.trace_manager = trace_manager

        # Core service: owns run state, logs, traces
        self.run_service = RunService(
            runtime_factory=self.runtime_factory,
            trace_manager=self.trace_manager,
            on_run_updated=self._on_run_updated,
            on_log=self._on_log_for_ui,
            on_trace=self._on_trace_for_ui,
            on_chat=self._on_chat_for_ui,
        )

        # Evaluations services
        self.evaluator_service = EvaluatorService()
        self.eval_set_service = EvalSetService()
        self.eval_run_service = EvalRunService(
            trace_manager=self.trace_manager,
            on_run_updated=self._on_eval_run_updated,
            on_log=self._on_eval_log_for_ui,
            on_trace=self._on_eval_trace_for_ui,
        )

        # Just defaults for convenience
        self.initial_entrypoint: str = "main.py"
        self.initial_input: str = '{\n  "message": "Hello World"\n}'

        # Track currently displayed eval run for auto-refresh
        self._current_eval_run_id: str | None = None

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        with Horizontal():
            # Left sidebar - run history, eval sets and evaluators
            with Container(classes="left-panel"):
                yield SidebarPanel(
                    evaluator_service=self.evaluator_service,
                    eval_set_service=self.eval_set_service,
                    eval_run_service=self.eval_run_service,
                    on_run_selected=self._on_sidebar_run_selected,
                    on_new_run_clicked=self._on_new_run_clicked,
                    # Eval sets callbacks
                    on_evaluation_selected=self._on_evaluation_selected,
                    on_add_evaluation_clicked=self._on_add_evaluation_clicked,
                    on_assign_evaluator_clicked=self._on_assign_evaluator_clicked,
                    on_create_eval_set_clicked=self._on_create_eval_set_clicked,
                    on_eval_set_changed=self._on_eval_set_changed,
                    # Evaluators callbacks
                    on_evaluator_selected=self._on_evaluator_selected,
                    on_new_evaluator_clicked=self._on_new_evaluator_clicked,
                    id="left-panel",
                )

            # Main content area
            with Horizontal(id="main-content-split", classes="main-content"):
                # Middle panel - contains different views based on context
                with Container(id="middle-panel", classes="middle-panel"):
                    # New Run tabs - visible when Run History is selected
                    with TabbedContent(id="new-run-tabs"):
                        with TabPane("New Run", id="new-run-tab"):
                            yield NewRunPanel(
                                id="new-run-panel",
                                classes="new-run-panel-content",
                                runtime_factory=self.runtime_factory,
                            )

                    # Eval tabs - visible when Eval Sets is selected
                    with TabbedContent(id="eval-tabs", classes="hidden"):
                        # Evaluations tab
                        with TabPane("Evaluations", id="evaluations-tab"):
                            yield EvaluationsListPanel(
                                on_add_clicked=self._on_add_evaluation_clicked,
                                on_assign_clicked=self._on_assign_evaluator_clicked,
                                on_evaluation_selected=self._on_evaluation_selected,
                                id="evaluations-list-panel",
                            )

                        # Runs tab - shows eval runs for the selected eval set
                        with TabPane("Runs", id="runs-tab"):
                            yield EvalRunsListPanel(
                                eval_run_service=self.eval_run_service,
                                on_run_selected=self._on_eval_run_selected,
                                id="runs-list-panel",
                            )

                    # Create tabs - visible when creating new eval set
                    with TabbedContent(id="create-tabs", classes="hidden"):
                        with TabPane("Create", id="create-tab"):
                            yield EvalSetCreatePanel(
                                on_create=self._on_eval_set_create,
                                on_close=self._on_hide_create_panel,
                                id="eval-set-create-panel",
                            )

                    # Evaluator create tabs - visible when creating new evaluator
                    with TabbedContent(id="evaluator-create-tabs", classes="hidden"):
                        with TabPane("Create Evaluator", id="evaluator-create-tab"):
                            yield EvaluatorFormPanel(
                                on_save=self._on_evaluator_save,
                                on_delete=self._on_evaluator_delete,
                                on_close=self._on_evaluator_form_close,
                                id="evaluator-form-panel",
                            )

                    # Run details panel (initially hidden) - shown when viewing run details
                    yield RunDetailsPanel(id="details-panel", classes="hidden")

                # Right panel - edit panel (initially hidden)
                with Container(
                    id="right-edit-panel", classes="right-edit-panel hidden"
                ):
                    with TabbedContent(id="edit-tabs"):
                        with TabPane("Edit", id="edit-tab"):
                            # Pre-compose all edit panels, toggle visibility
                            yield EvaluationEditPanel(
                                evaluator_service=self.evaluator_service,
                                on_save=self._on_evaluation_save,
                                on_delete=self._on_evaluation_delete,
                                on_close=self._hide_right_edit_panel,
                                id="evaluation-edit-panel",
                                classes="hidden",
                            )
                            yield AssignEvaluatorPanel(
                                evaluator_service=self.evaluator_service,
                                on_assign=self._on_evaluators_assign,
                                on_close=self._hide_right_edit_panel,
                                id="assign-evaluator-panel",
                                classes="hidden",
                            )
                            # Container for evaluator create form (populated dynamically)
                            yield ScrollableContainer(
                                id="evaluator-create-content",
                                classes="hidden",
                            )

                    with TabbedContent(id="eval-run-tabs", classes="hidden"):
                        with TabPane("Details", id="eval-run-tab"):
                            yield EvalRunDetailsPanel(
                                id="eval-run-details-panel",
                            )

        yield Footer()

    def _get_button_handlers(self) -> dict[str, Any]:
        """Get button ID to handler mapping for exact matches."""
        return {
            "new-run-btn": self.action_new_run,
            "execute-btn": lambda: self.action_execute_run(mode=ExecutionMode.RUN),
            "debug-btn": lambda: self.action_execute_run(mode=ExecutionMode.DEBUG),
            "chat-btn": lambda: self.action_execute_run(mode=ExecutionMode.CHAT),
            "cancel-btn": self.action_cancel,
            "debug-step-btn": self.action_debug_step,
            "debug-continue-btn": self.action_debug_continue,
            "debug-stop-btn": self.action_debug_stop,
            "eval-run-btn": self.action_run_eval,
            "close-evaluator-detail-btn": self._hide_right_edit_panel,
            "create-evaluator-btn": self._on_create_evaluator_btn_clicked,
        }

    def _get_prefix_button_handlers(self) -> list[tuple[str, Any]]:
        """Get button prefix to handler mapping for startswith matches."""
        return [
            ("close-detail-btn", self._on_hide_eval_set_detail),
            ("close-right-panel-btn", self._hide_right_edit_panel),
        ]

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        btn_id = event.button.id or ""

        # Try exact match first
        handlers = self._get_button_handlers()
        if btn_id in handlers:
            result = handlers[btn_id]()
            if asyncio.iscoroutine(result):
                await result
            return

        # Try prefix matches
        for prefix, handler in self._get_prefix_button_handlers():
            if btn_id.startswith(prefix):
                result = handler()
                if asyncio.iscoroutine(result):
                    await result
                return

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list selection from history and eval panels."""
        if event.list_view.id == "run-list" and event.item:
            # Run history selection
            run_id = getattr(event.item, "run_id", None)
            if run_id:
                history_panel = self.query_one("#left-panel", SidebarPanel)
                run = history_panel.get_run_by_id(run_id)
                if run:
                    self._show_run_details(run)
        elif event.list_view.id == "evaluator-templates-list" and event.item:
            # Evaluator template selection - show creation form in right panel
            type_id = getattr(event.item, "type_id", None)
            type_def = getattr(event.item, "type_def", None)
            if type_id and type_def:
                self._on_evaluator_type_selected(type_id, type_def)

    # =========================================================================
    # List Panel Callbacks
    # =========================================================================

    def _on_add_evaluation_clicked(self) -> None:
        """Handle add evaluation button click - show add evaluation form."""
        history_panel = self.query_one("#left-panel", SidebarPanel)
        eval_sets_tab = history_panel.get_eval_sets_tab()
        if not eval_sets_tab:
            return

        eval_set_data = eval_sets_tab.get_current_eval_set_data()
        if not eval_set_data:
            self.notify("Please select an eval set first", severity="error")
            return

        # Show evaluation edit panel in add mode (no evaluation data)
        self._show_right_edit_panel(tab_name="Edit")
        edit_panel = self.query_one("#evaluation-edit-panel", EvaluationEditPanel)
        edit_panel.remove_class("hidden")
        edit_panel.set_data(
            evaluation=None,  # Add mode
            eval_set_data=eval_set_data,
            eval_set_path=eval_sets_tab.get_selected_eval_set_path(),
        )

    def _on_evaluation_selected(self, eval_data: dict[str, Any]) -> None:
        """Handle evaluation selection - show edit form."""
        history_panel = self.query_one("#left-panel", SidebarPanel)
        eval_sets_tab = history_panel.get_eval_sets_tab()
        if not eval_sets_tab:
            return

        eval_set_data = eval_sets_tab.get_current_eval_set_data()
        if not eval_set_data:
            return

        # Show evaluation edit panel in edit mode
        self._show_right_edit_panel(tab_name="Edit")
        edit_panel = self.query_one("#evaluation-edit-panel", EvaluationEditPanel)
        edit_panel.remove_class("hidden")
        edit_panel.set_data(
            evaluation=eval_data,
            eval_set_data=eval_set_data,
            eval_set_path=eval_sets_tab.get_selected_eval_set_path(),
        )

    def _on_assign_evaluator_clicked(self) -> None:
        """Handle assign evaluator button click - show assign form."""
        history_panel = self.query_one("#left-panel", SidebarPanel)
        eval_sets_tab = history_panel.get_eval_sets_tab()
        if not eval_sets_tab:
            return

        eval_set_data = eval_sets_tab.get_current_eval_set_data()
        if not eval_set_data:
            self.notify("Please select an eval set first", severity="error")
            return

        # Calculate unassigned evaluators
        assigned_refs = set(eval_set_data.get("evaluatorRefs", []))
        all_evaluators = self.evaluator_service.list_evaluators()
        unassigned = [ev for ev in all_evaluators if ev.get("id") not in assigned_refs]

        if not unassigned:
            self.notify("All evaluators are already assigned", severity="warning")
            return

        # Show assign evaluator panel
        self._show_right_edit_panel(tab_name="Assign")
        assign_panel = self.query_one("#assign-evaluator-panel", AssignEvaluatorPanel)
        assign_panel.remove_class("hidden")
        assign_panel.set_data(
            unassigned=unassigned,
            eval_set_data=eval_set_data,
            eval_set_path=eval_sets_tab.get_selected_eval_set_path(),
        )

    def _on_eval_run_selected(self, eval_run: EvalRun) -> None:
        """Handle eval run selection from EvalRunsListPanel."""
        asyncio.create_task(self._show_eval_run_detail(eval_run))

    # =========================================================================
    # Evaluator Form Panel Callbacks
    # =========================================================================

    def _on_evaluator_form_close(self) -> None:
        """Handle close from EvaluatorFormPanel."""
        self._hide_evaluator_create_panel()

    def _on_create_eval_set_clicked(self) -> None:
        """Handle create eval set button click from sidebar."""
        self._show_create_panel()

    def _on_evaluator_selected(self, ev_data: dict[str, Any]) -> None:
        """Handle evaluator selection from sidebar - show edit form."""
        evaluator_id = ev_data.get("id", "")
        if not evaluator_id:
            return

        self._set_panel_visibility(
            {
                "#new-run-tabs": False,
                "#eval-tabs": False,
                "#create-tabs": False,
                "#evaluator-create-tabs": True,
            }
        )
        self._hide_right_edit_panel()

        try:
            form_panel = self.query_one("#evaluator-form-panel", EvaluatorFormPanel)
            asyncio.create_task(form_panel.show_edit_form(evaluator_id, ev_data))
        except Exception as e:
            self.notify(f"Error showing evaluator edit: {e}", severity="error")

    def _on_new_evaluator_clicked(self) -> None:
        """Handle new evaluator button click from sidebar - show templates."""
        self._on_show_evaluator_templates()

    def _on_hide_create_panel(self) -> None:
        """Handle close button click from EvalSetCreatePanel."""
        self._hide_create_panel()
        self._show_eval_sets_tabs()

    @on(Input.Submitted, "#chat-input")
    async def handle_chat_input(self, event: Input.Submitted) -> None:
        """Handle user submitting text into the chat."""
        user_text = event.value.strip()
        if not user_text:
            return

        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel and details_panel.current_run:
            current_run = details_panel.current_run
            status = current_run.status
            if status == "running":
                self.app.notify(
                    "Wait for agent response...", timeout=1.5, severity="warning"
                )
                return

            if current_run.status == "suspended":
                resume_input: Any = {}
                try:
                    resume_input = json.loads(user_text)
                except json.JSONDecodeError:
                    resume_input = user_text
                current_run.resume_data = resume_input
            else:
                msg = get_user_message(user_text)
                msg_ev = get_user_message_event(user_text)

                self._on_chat_for_ui(
                    ChatMessage(
                        event=msg_ev,
                        message=msg,
                        run_id=current_run.id,
                    )
                )
                current_run.add_event(msg_ev)
                current_run.input_data = {"messages": [msg]}

            if current_run.mode == ExecutionMode.DEBUG:
                asyncio.create_task(
                    self._resume_runtime(current_run, current_run.resume_data)
                )
            else:
                asyncio.create_task(self._execute_runtime(current_run))

            event.input.clear()

    async def action_new_run(self) -> None:
        """Show new run panel."""
        details_panel = self.query_one("#details-panel")

        self._show_new_run_panel()
        details_panel.add_class("hidden")

    def _set_panel_visibility(self, visibility: dict[str, bool]) -> None:
        """Set visibility for multiple panels at once.

        Args:
            visibility: Dict mapping panel IDs to visibility (True=show, False=hide)
        """
        try:
            for panel_id, visible in visibility.items():
                panel = self.query_one(panel_id)
                if visible:
                    panel.remove_class("hidden")
                else:
                    panel.add_class("hidden")
        except Exception:
            pass

    def _show_new_run_panel(self) -> None:
        """Show the New Run panel and hide Eval Sets tabs."""
        self._set_panel_visibility(
            {
                "#new-run-tabs": True,
                "#eval-tabs": False,
                "#create-tabs": False,
                "#evaluator-create-tabs": False,
                "#details-panel": False,
                "#right-edit-panel": False,
            }
        )

    def _show_eval_sets_tabs(self) -> None:
        """Show the Evaluations/Evaluators tabs (for Eval Sets mode)."""
        self._set_panel_visibility(
            {
                "#new-run-tabs": False,
                "#eval-tabs": True,
                "#create-tabs": False,
                "#evaluator-create-tabs": False,
                "#details-panel": False,
                "#right-edit-panel": False,
            }
        )
        try:
            eval_tabs = self.query_one("#eval-tabs", TabbedContent)
            eval_tabs.active = "evaluations-tab"
        except Exception:
            pass
        self._populate_eval_lists()

    def _on_eval_set_changed(self) -> None:
        """Handle eval set selection change - refresh the middle panel lists."""
        self._populate_eval_lists()

    def _show_right_edit_panel(self, tab_name: str = "Edit") -> None:
        """Show the right edit panel container and hide all sub-panels.

        Args:
            tab_name: Name to display on the tab (default "Edit", use "Details" for run details)
        """
        try:
            right_edit_panel = self.query_one("#right-edit-panel")
            edit_tabs = self.query_one("#edit-tabs", TabbedContent)

            right_edit_panel.remove_class("hidden")
            edit_tabs.remove_class("hidden")

            # Hide all pre-composed sub-panels
            self._hide_all_right_sub_panels()

            # Hide eval-run-tabs when showing edit panels
            self.query_one("#eval-run-tabs", TabbedContent).add_class("hidden")

            # Update tab label
            try:
                tab = edit_tabs.get_tab("edit-tab")
                tab.label = tab_name
            except Exception:
                pass
        except Exception:
            pass

    def _hide_all_right_sub_panels(self) -> None:
        """Hide all pre-composed panels in the right edit panel."""
        try:
            self.query_one("#evaluation-edit-panel", EvaluationEditPanel).add_class(
                "hidden"
            )
        except Exception:
            pass
        try:
            self.query_one("#assign-evaluator-panel", AssignEvaluatorPanel).add_class(
                "hidden"
            )
        except Exception:
            pass
        try:
            container = self.query_one(
                "#evaluator-create-content", ScrollableContainer
            )
            container.add_class("hidden")
            # Clear the container contents
            for child in list(container.children):
                child.remove()
        except Exception:
            pass

    def _hide_right_edit_panel(self) -> None:
        """Hide the right edit panel."""
        # Clear eval run tracking
        self._current_eval_run_id = None

        try:
            right_edit_panel = self.query_one("#right-edit-panel")
            right_edit_panel.add_class("hidden")
            self._hide_all_right_sub_panels()

            # Hide eval-run-tabs and restore edit-tabs visibility
            self.query_one("#eval-run-tabs", TabbedContent).add_class("hidden")
            edit_tabs = self.query_one("#edit-tabs", TabbedContent)
            edit_tabs.remove_class("hidden")
        except Exception:
            pass

    def _show_create_panel(self) -> None:
        """Show the create panel in the middle, hide the right panel."""
        try:
            eval_tabs = self.query_one("#eval-tabs", TabbedContent)
            create_tabs = self.query_one("#create-tabs", TabbedContent)

            # Hide eval tabs in middle, show create tabs
            eval_tabs.add_class("hidden")
            create_tabs.remove_class("hidden")

            self._hide_right_edit_panel()

            # Reset the pre-composed create panel
            create_panel = self.query_one("#eval-set-create-panel", EvalSetCreatePanel)
            create_panel.reset()
        except Exception:
            pass

    def _hide_create_panel(self) -> None:
        """Hide the create panel and restore eval tabs in middle."""
        try:
            eval_tabs = self.query_one("#eval-tabs", TabbedContent)
            create_tabs = self.query_one("#create-tabs", TabbedContent)

            # Hide create tabs, show eval tabs in middle
            create_tabs.add_class("hidden")
            eval_tabs.remove_class("hidden")

            # Hide right panel
            self._hide_right_edit_panel()
        except Exception:
            pass

    def _show_evaluator_create_panel(self) -> None:
        """Show the evaluator creation panel (empty placeholder until type is selected)."""
        self._set_panel_visibility(
            {
                "#new-run-tabs": False,
                "#eval-tabs": False,
                "#create-tabs": False,
                "#evaluator-create-tabs": True,
                "#details-panel": False,
                "#right-edit-panel": False,
            }
        )
        try:
            form_panel = self.query_one("#evaluator-form-panel", EvaluatorFormPanel)
            form_panel.show_placeholder()
        except Exception:
            pass

    def _hide_evaluator_create_panel(self) -> None:
        """Hide the evaluator creation panel."""
        try:
            evaluator_create_tabs = self.query_one(
                "#evaluator-create-tabs", TabbedContent
            )
            evaluator_create_tabs.add_class("hidden")
        except Exception:
            pass

    def _on_show_evaluator_templates(self) -> None:
        """Show templates list in middle panel."""
        self._set_panel_visibility(
            {
                "#new-run-tabs": False,
                "#eval-tabs": False,
                "#create-tabs": False,
                "#evaluator-create-tabs": True,
            }
        )
        try:
            form_panel = self.query_one("#evaluator-form-panel", EvaluatorFormPanel)
            asyncio.create_task(form_panel.show_templates())
        except Exception:
            pass
        self._hide_right_edit_panel()

    def _on_evaluator_type_selected(
        self, type_id: str, type_def: dict[str, Any]
    ) -> None:
        """Handle evaluator type/template selection - show creation form in right panel."""
        # Show the right panel and the evaluator create container
        self._show_right_edit_panel(tab_name="Create")
        content = self.query_one("#evaluator-create-content", ScrollableContainer)
        content.remove_class("hidden")

        try:
            form_panel = self.query_one("#evaluator-form-panel", EvaluatorFormPanel)
            asyncio.create_task(
                form_panel.populate_create_form_in_container(content, type_id, type_def)
            )
        except Exception as e:
            self.notify(f"Error showing create form: {e}", severity="error")

    def _populate_eval_lists(self) -> None:
        """Populate the evaluations, runs, and evaluators lists via the panels."""
        try:
            history_panel = self.query_one("#left-panel", SidebarPanel)
            eval_sets_panel = history_panel.get_eval_sets_tab()
            if not eval_sets_panel:
                return

            # Update evaluations list panel with current data
            eval_set_data = eval_sets_panel.current_eval_set_data

            evaluations_panel = self.query_one(
                "#evaluations-list-panel", EvaluationsListPanel
            )
            evaluations_panel.set_eval_set_data(eval_set_data)

            # Update runs list panel with selected eval set
            runs_panel = self.query_one("#runs-list-panel", EvalRunsListPanel)
            runs_panel.set_eval_set(eval_sets_panel.selected_eval_set)
        except Exception:
            pass

    async def _refresh_evaluators_list(self) -> None:
        """Refresh the evaluators list in the sidebar."""
        try:
            history_panel = self.query_one("#left-panel", SidebarPanel)
            evaluators_tab = history_panel.get_evaluators_tab()
            if evaluators_tab:
                await evaluators_tab.refresh_list()
        except Exception:
            pass

    async def action_cancel(self) -> None:
        """Cancel and return to new run view."""
        await self.action_new_run()

    async def action_execute_run(self, mode: ExecutionMode = ExecutionMode.RUN) -> None:
        """Execute a new run based on NewRunPanel inputs."""
        new_run_panel = self.query_one("#new-run-panel", NewRunPanel)
        entrypoint, input_data = new_run_panel.get_input_values()

        if not entrypoint:
            return

        try:
            input_payload: dict[str, Any] = json.loads(input_data)
        except json.JSONDecodeError:
            return

        run = ExecutionRun(entrypoint, input_payload, mode=mode)

        history_panel = self.query_one("#left-panel", SidebarPanel)
        history_panel.add_run(run)

        self.run_service.register_run(run)

        self._show_run_details(run)

        if mode == ExecutionMode.CHAT:
            self._focus_chat_input()
        else:
            asyncio.create_task(self._execute_runtime(run))

    async def action_debug_step(self) -> None:
        """Step to next breakpoint in debug mode."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel and details_panel.current_run:
            run = details_panel.current_run
            self.run_service.step_debug(run)

    async def action_debug_continue(self) -> None:
        """Continue execution without stopping at breakpoints."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel and details_panel.current_run:
            run = details_panel.current_run
            self.run_service.continue_debug(run)

    async def action_debug_stop(self) -> None:
        """Stop debug execution."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel and details_panel.current_run:
            run = details_panel.current_run
            self.run_service.stop_debug(run)

    async def action_clear_history(self) -> None:
        """Clear run history."""
        history_panel = self.query_one("#left-panel", SidebarPanel)
        history_panel.clear_runs()
        await self.action_new_run()

    def action_show_evaluations(self) -> None:
        """Switch to the eval sets tab in the sidebar."""
        history_panel = self.query_one("#left-panel", SidebarPanel)
        history_panel.switch_to_eval_sets()

    async def action_run_eval(self) -> None:
        """Execute an evaluation run based on EvalSetsTab inputs.

        This is the eval equivalent of action_execute_run.
        """
        history_panel = self.query_one("#left-panel", SidebarPanel)
        eval_sets_panel = history_panel.get_eval_sets_tab()
        if not eval_sets_panel:
            return

        # Validate
        if not eval_sets_panel.selected_eval_set:
            self.notify("Please select an eval set", severity="error")
            return

        eval_run = eval_sets_panel.create_eval_run()

        self.eval_run_service.register_run(eval_run)

        try:
            runs_panel = self.query_one("#runs-list-panel", EvalRunsListPanel)
            runs_panel.add_run(eval_run)
        except Exception:
            pass

        # Set the current eval run ID before switching tabs to prevent the tab change
        # handler from hiding the right panel
        self._current_eval_run_id = eval_run.id

        # Switch to Runs tab
        try:
            eval_tabs = self.query_one("#eval-tabs", TabbedContent)
            eval_tabs.active = "runs-tab"
        except Exception:
            pass

        # Show the run details panel automatically
        await self._show_eval_run_detail(eval_run)

        asyncio.create_task(self._execute_eval_run(eval_run))

    def _on_eval_run_started(self, eval_run: EvalRun) -> None:
        """Handle evaluation run started - register with service and update UI."""
        self.eval_run_service.register_run(eval_run)

        # Switch to Runs tab
        try:
            eval_tabs = self.query_one("#eval-tabs", TabbedContent)
            eval_tabs.active = "runs-tab"
        except Exception:
            pass

    def _on_eval_run_updated(self, eval_run: EvalRun) -> None:
        """Handle evaluation run updated - refresh the UI."""
        # Targeted update of the specific run item in the runs list
        try:
            runs_panel = self.query_one("#runs-list-panel", EvalRunsListPanel)
            runs_panel.update_run(eval_run)
        except Exception:
            pass

        # If this run is currently displayed in the right panel, refresh it
        if self._current_eval_run_id and self._current_eval_run_id == eval_run.id:
            asyncio.create_task(self._show_eval_run_detail(eval_run))

    def _on_sidebar_run_selected(self, run: ExecutionRun) -> None:
        """Handle run selection from sidebar."""
        self._show_run_details(run)

    def _on_new_run_clicked(self) -> None:
        """Handle new run button click from sidebar."""
        asyncio.create_task(self.action_new_run())

    def action_copy(self) -> None:
        """Copy content of currently focused RichLog to clipboard and notify."""
        focused = self.app.focused
        if isinstance(focused, RichLog):
            clipboard_text = "\n".join(line.text for line in focused.lines)
            pyperclip.copy(clipboard_text)
            self.app.notify("Copied to clipboard!", timeout=1.5)
        else:
            self.app.notify("Nothing to copy here.", timeout=1.5, severity="warning")

    async def _execute_runtime(self, run: ExecutionRun) -> None:
        """Wrapper that delegates execution to RunService."""
        await self.run_service.execute(run)

    async def _resume_runtime(self, run: ExecutionRun, resume_data: Any) -> None:
        """Wrapper that delegates execution to RunService."""
        await self.run_service.resume_debug(run, resume_data)
    async def _execute_eval_run(self, eval_run: EvalRun) -> None:
        """Wrapper that delegates eval execution to EvalService."""
        try:
            await self.eval_run_service.execute(eval_run)
            self.notify("Evaluations completed!", timeout=3)
        except Exception as e:
            error_str = str(e).replace("[", r"\[").replace("]", r"\]")
            self.notify(f"Evaluation failed: {error_str}", severity="error", timeout=5)

    def _on_run_updated(self, run: ExecutionRun) -> None:
        """Called whenever a run changes (status, times, logs, traces)."""
        # Update the run in history
        history_panel = self.query_one("#left-panel", SidebarPanel)
        history_panel.update_run(run)

        # If this run is currently shown, refresh details
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel.current_run and details_panel.current_run.id == run.id:
            details_panel.update_run_details(run)

    def _on_log_for_ui(self, log_msg: LogMessage) -> None:
        """Append a log message to the logs UI."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.add_log(log_msg)

    def _on_trace_for_ui(self, trace_msg: TraceMessage) -> None:
        """Append/refresh traces in the UI."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.add_trace(trace_msg)

    def _on_eval_log_for_ui(self, log_msg: LogMessage) -> None:
        """Append a log message to the eval run details UI."""
        try:
            details_panel = self.query_one("#eval-run-details-panel", EvalRunDetailsPanel)
            details_panel.add_log(log_msg)
        except Exception:
            pass

    def _on_eval_trace_for_ui(self, trace_msg: TraceMessage) -> None:
        """Append/refresh traces in the eval run details UI."""
        try:
            details_panel = self.query_one("#eval-run-details-panel", EvalRunDetailsPanel)
            details_panel.add_trace(trace_msg)
        except Exception:
            pass

    def _on_chat_for_ui(
        self,
        chat_msg: ChatMessage,
    ) -> None:
        """Append/refresh chat messages in the UI."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.add_chat_message(chat_msg)

    def _show_run_details(self, run: ExecutionRun) -> None:
        """Show details panel for a specific run."""
        self._set_panel_visibility(
            {
                "#new-run-tabs": False,
                "#eval-tabs": False,
                "#right-edit-panel": False,
                "#details-panel": True,
            }
        )
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.update_run(run)

    async def _show_eval_run_detail(self, eval_run: EvalRun) -> None:
        """Show eval run details in the right panel."""
        # Track which eval run is displayed for auto-refresh
        self._current_eval_run_id = eval_run.id

        # Show right panel container
        right_edit_panel = self.query_one("#right-edit-panel")
        right_edit_panel.remove_class("hidden")

        # Hide the edit-tabs TabbedContent and show eval-run-tabs
        edit_tabs = self.query_one("#edit-tabs", TabbedContent)
        edit_tabs.add_class("hidden")

        eval_run_tabs = self.query_one("#eval-run-tabs", TabbedContent)
        eval_run_tabs.remove_class("hidden")

        details_panel = self.query_one("#eval-run-details-panel", EvalRunDetailsPanel)
        details_panel.update_run(eval_run)

    # =========================================================================
    # Action-Specific Handlers
    # =========================================================================

    def _on_eval_set_create(self, form_data: dict[str, Any]) -> None:
        """Handle eval set creation - App calls service.

        Args:
            form_data: Dict with eval_set_id, name, evaluator_refs, evaluations.
        """
        eval_set_id = form_data.get("eval_set_id", "")
        if not eval_set_id:
            self.notify("Eval set ID is required", severity="error")
            return

        # Build the eval set data structure
        eval_set_data = {
            "name": form_data.get("name", eval_set_id),
            "evaluatorRefs": form_data.get("evaluator_refs", []),
            "evaluations": form_data.get("evaluations", []),
        }

        # Call service to persist
        self.eval_set_service.save_eval_set(eval_set_id, eval_set_data)

        # Refresh UI
        self._hide_create_panel()
        self._show_eval_sets_tabs()

        # Refresh eval sets dropdown and select the new one
        history_panel = self.query_one("#left-panel", SidebarPanel)
        eval_sets_tab = history_panel.get_eval_sets_tab()
        if eval_sets_tab:
            eval_sets_tab.refresh_eval_sets()
            eval_sets_tab.select_eval_set(eval_set_id)

        self.notify(f"Eval set '{eval_set_id}' created!", timeout=3)

    def _on_create_evaluator_btn_clicked(self) -> None:
        """Handle create evaluator button click from the external container."""
        form_panel = self.query_one("#evaluator-form-panel", EvaluatorFormPanel)
        form_data = form_panel.get_create_form_data()
        if form_data:
            form_data["is_create"] = True
            self._on_evaluator_save(form_data)

    def _on_evaluator_save(self, form_data: dict[str, Any]) -> None:
        """Handle evaluator save.

        Args:
            form_data: Dict with evaluator_id, type_id, description, config,
                       default_criteria, is_create.
        """
        evaluator_id = form_data.get("evaluator_id", "")
        if not evaluator_id:
            self.notify("Evaluator ID is required", severity="error")
            return

        is_create = form_data.get("is_create", False)

        # Build the evaluator data structure expected by the service
        evaluator_data = {
            "id": evaluator_id,
            "description": form_data.get("description", ""),
            "evaluatorTypeId": form_data.get("type_id", ""),
            "config": form_data.get("config", {}),
            "defaultCriteria": form_data.get("default_criteria", {}),
        }

        # Call service to persist
        self.evaluator_service.save_evaluator(evaluator_id, evaluator_data)

        # Refresh UI
        self._hide_right_edit_panel()
        asyncio.create_task(self._refresh_evaluators_list())

        action = "created" if is_create else "saved"
        self.notify(f"Evaluator '{evaluator_id}' {action}!", timeout=3)

    def _on_evaluator_delete(self, evaluator_id: str) -> None:
        """Handle evaluator delete - App calls service.

        Args:
            evaluator_id: The ID of the evaluator to delete.
        """
        if not evaluator_id:
            return

        # Call service to delete
        self.evaluator_service.delete_evaluator(evaluator_id)

        # Refresh UI
        self._hide_evaluator_create_panel()
        asyncio.create_task(self._refresh_evaluators_list())

        self.notify(f"Evaluator '{evaluator_id}' deleted!", timeout=3)

    def _on_evaluation_save(self, form_data: dict[str, Any]) -> None:
        """Handle evaluation save - App calls service.

        Args:
            form_data: Dict with id, name, inputs, evaluationCriteria, is_add_mode, eval_set_path.
        """
        eval_set_path = form_data.get("eval_set_path", "")
        if not eval_set_path:
            self.notify("No eval set selected", severity="error")
            return

        # Get the eval set name from the path
        eval_set_name = Path(eval_set_path).stem

        # Get current eval set data
        history_panel = self.query_one("#left-panel", SidebarPanel)
        eval_sets_tab = history_panel.get_eval_sets_tab()
        if not eval_sets_tab:
            return

        eval_set_data = eval_sets_tab.get_current_eval_set_data()
        if not eval_set_data:
            return

        # Build the evaluation entry
        evaluation_entry = {
            "id": form_data.get("id"),
            "name": form_data.get("name"),
            "inputs": form_data.get("inputs", {}),
            "evaluationCriterias": form_data.get("evaluationCriterias", {}),
        }

        # Update evaluations list
        evaluations = eval_set_data.get("evaluations", [])
        is_add_mode = form_data.get("is_add_mode", True)

        if is_add_mode:
            evaluations.append(evaluation_entry)
        else:
            # Update existing evaluation
            eval_id = form_data.get("id")
            for i, ev in enumerate(evaluations):
                if ev.get("id") == eval_id:
                    evaluations[i] = evaluation_entry
                    break

        eval_set_data["evaluations"] = evaluations

        # Call service to persist
        self.eval_set_service.save_eval_set(eval_set_name, eval_set_data)

        # Update the tab's cached data
        eval_sets_tab.set_current_eval_set_data(eval_set_data)

        # Refresh UI
        self._hide_right_edit_panel()

        evaluations_panel = self.query_one(
            "#evaluations-list-panel", EvaluationsListPanel
        )
        evaluations_panel.set_eval_set_data(eval_set_data)

        action = "added" if is_add_mode else "saved"
        self.notify(f"Evaluation {action}!", timeout=3)

    def _on_evaluation_delete(self, eval_id: str) -> None:
        """Handle evaluation delete - App calls service.

        Args:
            eval_id: The ID of the evaluation to delete.
        """
        if not eval_id:
            return

        # Get current eval set data
        history_panel = self.query_one("#left-panel", SidebarPanel)
        eval_sets_tab = history_panel.get_eval_sets_tab()
        if not eval_sets_tab:
            return

        eval_set_data = eval_sets_tab.get_current_eval_set_data()
        eval_set_path = eval_sets_tab.get_selected_eval_set_path()
        if not eval_set_data or not eval_set_path:
            return

        eval_set_name = Path(eval_set_path).stem

        # Remove the evaluation from the list
        evaluations = eval_set_data.get("evaluations", [])
        eval_set_data["evaluations"] = [
            ev for ev in evaluations if ev.get("id") != eval_id
        ]

        # Call service to persist
        self.eval_set_service.save_eval_set(eval_set_name, eval_set_data)

        # Update the tab's cached data
        eval_sets_tab.set_current_eval_set_data(eval_set_data)

        # Refresh UI
        self._hide_right_edit_panel()

        evaluations_panel = self.query_one(
            "#evaluations-list-panel", EvaluationsListPanel
        )
        evaluations_panel.set_eval_set_data(eval_set_data)

        self.notify("Evaluation deleted!", timeout=3)

    def _on_evaluators_assign(self, evaluator_ids: list[str]) -> None:
        """Handle evaluators assign - App calls service.

        Args:
            evaluator_ids: List of evaluator IDs to assign.
        """
        if not evaluator_ids:
            self.notify("Please select at least one evaluator", severity="error")
            return

        # Get current eval set data
        history_panel = self.query_one("#left-panel", SidebarPanel)
        eval_sets_tab = history_panel.get_eval_sets_tab()
        if not eval_sets_tab:
            return

        eval_set_data = eval_sets_tab.get_current_eval_set_data()
        eval_set_path = eval_sets_tab.get_selected_eval_set_path()
        if not eval_set_data or not eval_set_path:
            return

        eval_set_name = Path(eval_set_path).stem

        # Add new evaluator refs
        existing_refs = set(eval_set_data.get("evaluatorRefs", []))
        existing_refs.update(evaluator_ids)
        eval_set_data["evaluatorRefs"] = list(existing_refs)

        # Call service to persist
        self.eval_set_service.save_eval_set(eval_set_name, eval_set_data)

        # Update the tab's cached data
        eval_sets_tab.set_current_eval_set_data(eval_set_data)

        # Refresh UI
        self._hide_right_edit_panel()

        evaluations_panel = self.query_one(
            "#evaluations-list-panel", EvaluationsListPanel
        )
        evaluations_panel.set_eval_set_data(eval_set_data)

        count = len(evaluator_ids)
        self.notify(f"{count} evaluator(s) assigned!", timeout=3)

    def _refresh_evaluations_list(self) -> None:
        """Refresh the evaluations list panel with updated data."""
        try:
            updated_data = None
            try:
                edit_panel = self.query_one(
                    "#evaluation-edit-panel", EvaluationEditPanel
                )
                updated_data = edit_panel.get_updated_eval_set_data()
            except Exception:
                pass

            if not updated_data:
                try:
                    assign_panel = self.query_one(
                        "#assign-evaluator-panel", AssignEvaluatorPanel
                    )
                    updated_data = assign_panel.get_updated_eval_set_data()
                except Exception:
                    pass

            if updated_data:
                # Update the eval_sets_tab state
                history_panel = self.query_one("#left-panel", SidebarPanel)
                eval_sets_tab = history_panel.get_eval_sets_tab()
                if eval_sets_tab:
                    eval_sets_tab.set_current_eval_set_data(updated_data)

                # Refresh the evaluations list
                evaluations_panel = self.query_one(
                    "#evaluations-list-panel", EvaluationsListPanel
                )
                evaluations_panel.set_eval_set_data(updated_data)
        except Exception:
            pass

    def _on_hide_eval_set_detail(self) -> None:
        """Hide the detail panel (either create or edit mode)."""
        # Check if create panel is visible
        try:
            create_tabs = self.query_one("#create-tabs", TabbedContent)
            if not create_tabs.has_class("hidden"):
                self._hide_create_panel()
                return
        except Exception:
            pass

        # Otherwise hide the right edit panel
        self._hide_right_edit_panel()

    @on(TabbedContent.TabActivated, "#history-tabs")
    def _on_sidebar_tab_changed(self, event: TabbedContent.TabActivated) -> None:
        """Handle sidebar tab changes to update main content."""
        if event.tab.id == "run-history-tab--tab" or event.pane.id == "run-history-tab":
            # Run History selected - show New Run panel
            self._show_new_run_panel()
        elif event.tab.id == "eval-sets-tab--tab" or event.pane.id == "eval-sets-tab":
            # Eval Sets selected - show Evaluations/Evaluators tabs
            self._show_eval_sets_tabs()
        elif event.tab.id == "evaluators-tab--tab" or event.pane.id == "evaluators-tab":
            # Evaluators selected - show evaluator creation panel (empty until type selected)
            self._show_evaluator_create_panel()

    @on(TabbedContent.TabActivated, "#eval-tabs")
    def _on_eval_tabs_changed(self, event: TabbedContent.TabActivated) -> None:
        """Handle middle panel tab changes (Runs/Evaluations) to hide right panel."""
        if event.pane.id == "runs-tab" and self._current_eval_run_id:
            return
        self._hide_right_edit_panel()

    def _focus_chat_input(self) -> None:
        """Focus the chat input box."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.switch_tab("chat-tab")
        chat_input = details_panel.query_one("#chat-input", Input)
        chat_input.focus()

    def _add_subprocess_log(self, level: str, message: str) -> None:
        """Handle a stderr line coming from subprocesses."""

        def add_log() -> None:
            details_panel = self.query_one("#details-panel", RunDetailsPanel)
            run: ExecutionRun = cast(
                ExecutionRun, getattr(details_panel, "current_run", None)
            )
            if run:
                log_msg = LogMessage(run.id, level, message, datetime.now())
                # Route through RunService so state + UI stay in sync
                self.run_service.handle_log(log_msg)

        self.call_from_thread(add_log)
