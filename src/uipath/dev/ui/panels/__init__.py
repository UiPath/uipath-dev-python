"""UiPath Dev Console panels module initialization."""

from uipath.dev.ui.panels.evals import EvalRunDetailsPanel
from uipath.dev.ui.panels.evaluators import EvaluatorFormPanel
from uipath.dev.ui.panels.runs import NewRunPanel, RunDetailsPanel
from uipath.dev.ui.panels.sidebar import (
    EvalSetsTab,
    EvaluatorsTab,
    RunHistoryTab,
    SidebarPanel,
)

__all__ = [
    "EvalRunDetailsPanel",
    "EvalSetsTab",
    "EvaluatorFormPanel",
    "EvaluatorsTab",
    "NewRunPanel",
    "RunDetailsPanel",
    "RunHistoryTab",
    "SidebarPanel",
]
