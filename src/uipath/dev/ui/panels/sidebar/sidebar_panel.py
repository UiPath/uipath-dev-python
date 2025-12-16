"""Main sidebar panel - composes individual tab components."""

from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import TabbedContent, TabPane

from uipath.dev.models.execution import ExecutionRun
from uipath.dev.services.eval_run_service import EvalRunService
from uipath.dev.services.eval_set_service import EvalSetService
from uipath.dev.services.evaluator_service import EvaluatorService
from uipath.dev.ui.panels.sidebar.eval_sets_tab import EvalSetsTab
from uipath.dev.ui.panels.sidebar.evaluators_tab import EvaluatorsTab
from uipath.dev.ui.panels.sidebar.run_history_tab import RunHistoryTab


class SidebarPanel(Vertical):
    """Sidebar panel that composes individual tab components."""

    def __init__(
        self,
        evaluator_service: EvaluatorService | None = None,
        eval_set_service: EvalSetService | None = None,
        eval_run_service: EvalRunService | None = None,
        # Run history callbacks
        on_run_selected: Callable[[ExecutionRun], None] | None = None,
        on_new_run_clicked: Callable[[], None] | None = None,
        # Eval sets callbacks (action-specific)
        on_evaluation_selected: Callable[[dict[str, Any]], None] | None = None,
        on_add_evaluation_clicked: Callable[[], None] | None = None,
        on_assign_evaluator_clicked: Callable[[], None] | None = None,
        on_create_eval_set_clicked: Callable[[], None] | None = None,
        on_eval_set_changed: Callable[[], None] | None = None,
        # Evaluators callbacks (action-specific)
        on_evaluator_selected: Callable[[dict[str, Any]], None] | None = None,
        on_new_evaluator_clicked: Callable[[], None] | None = None,
        **kwargs,
    ):
        """Initialize the sidebar panel.

        Args:
            evaluator_service: Service for evaluator CRUD operations.
            eval_set_service: Service for eval set CRUD operations.
            eval_run_service: Service for eval run execution.
            on_run_selected: Callback when a run is selected in history.
            on_new_run_clicked: Callback when "+ New" is clicked.
            on_evaluation_selected: Callback when an evaluation is selected (full data).
            on_add_evaluation_clicked: Callback when add evaluation is clicked.
            on_assign_evaluator_clicked: Callback when assign evaluator is clicked.
            on_create_eval_set_clicked: Callback when create eval set is clicked.
            on_eval_set_changed: Callback when eval set selection changes.
            on_evaluator_selected: Callback when an evaluator is selected (full data).
            on_new_evaluator_clicked: Callback when add evaluator is clicked.
        """
        super().__init__(**kwargs)

        # Services
        self.evaluator_service = evaluator_service or EvaluatorService()
        self.eval_set_service = eval_set_service or EvalSetService()
        self.eval_run_service = eval_run_service or EvalRunService()

        # Run history callbacks
        self.on_run_selected = on_run_selected
        self.on_new_run_clicked = on_new_run_clicked

        # Eval sets callbacks (action-specific)
        self.on_evaluation_selected = on_evaluation_selected
        self.on_add_evaluation_clicked = on_add_evaluation_clicked
        self.on_assign_evaluator_clicked = on_assign_evaluator_clicked
        self.on_create_eval_set_clicked = on_create_eval_set_clicked
        self.on_eval_set_changed = on_eval_set_changed

        # Evaluators callbacks (action-specific)
        self.on_evaluator_selected = on_evaluator_selected
        self.on_new_evaluator_clicked = on_new_evaluator_clicked

    def compose(self) -> ComposeResult:
        """Compose the sidebar panel with three tabs."""
        with TabbedContent(id="history-tabs"):
            with TabPane("Run History", id="run-history-tab"):
                yield RunHistoryTab(
                    on_run_selected=self.on_run_selected,
                    on_new_run_clicked=self.on_new_run_clicked,
                    id="run-history-tab-content",
                )

            with TabPane("Eval Sets", id="eval-sets-tab"):
                yield EvalSetsTab(
                    evaluator_service=self.evaluator_service,
                    eval_set_service=self.eval_set_service,
                    eval_run_service=self.eval_run_service,
                    # Action-specific callbacks
                    on_evaluation_selected=self.on_evaluation_selected,
                    on_add_evaluation_clicked=self.on_add_evaluation_clicked,
                    on_assign_evaluator_clicked=self.on_assign_evaluator_clicked,
                    on_create_eval_set_clicked=self.on_create_eval_set_clicked,
                    on_eval_set_changed=self.on_eval_set_changed,
                    id="eval-sets-panel",
                )

            with TabPane("Evaluators", id="evaluators-tab"):
                yield EvaluatorsTab(
                    evaluator_service=self.evaluator_service,
                    # Action-specific callbacks
                    on_evaluator_selected=self.on_evaluator_selected,
                    on_new_evaluator_clicked=self.on_new_evaluator_clicked,
                    id="evaluators-panel",
                )

    # =========================================================================
    # Run History Tab Delegation
    # =========================================================================

    def get_run_history_tab(self) -> RunHistoryTab | None:
        """Get the run history tab component."""
        try:
            return self.query_one("#run-history-tab-content", RunHistoryTab)
        except Exception:
            return None

    def add_run(self, run: ExecutionRun) -> None:
        """Add a new run to history."""
        tab = self.get_run_history_tab()
        if tab:
            tab.add_run(run)

    def update_run(self, run: ExecutionRun) -> None:
        """Update an existing run."""
        tab = self.get_run_history_tab()
        if tab:
            tab.update_run(run)

    def get_run_by_id(self, run_id: str) -> ExecutionRun | None:
        """Get a run by ID."""
        tab = self.get_run_history_tab()
        if tab:
            return tab.get_run_by_id(run_id)
        return None

    def clear_runs(self) -> None:
        """Clear all runs from history."""
        tab = self.get_run_history_tab()
        if tab:
            tab.clear_runs()

    # =========================================================================
    # Eval Sets Tab Delegation
    # =========================================================================

    def get_eval_sets_tab(self) -> EvalSetsTab | None:
        """Get the eval sets tab component."""
        try:
            return self.query_one("#eval-sets-panel", EvalSetsTab)
        except Exception:
            return None

    # =========================================================================
    # Evaluators Tab Delegation
    # =========================================================================

    def get_evaluators_tab(self) -> EvaluatorsTab | None:
        """Get the evaluators tab component."""
        try:
            return self.query_one("#evaluators-panel", EvaluatorsTab)
        except Exception:
            return None

    # =========================================================================
    # Tab Switching
    # =========================================================================

    def switch_to_run_history(self) -> None:
        """Switch to the run history tab."""
        try:
            tabbed_content = self.query_one("#history-tabs", TabbedContent)
            tabbed_content.active = "run-history-tab"
        except Exception:
            pass

    def switch_to_eval_sets(self) -> None:
        """Switch to the eval sets tab."""
        try:
            tabbed_content = self.query_one("#history-tabs", TabbedContent)
            tabbed_content.active = "eval-sets-tab"
        except Exception:
            pass

