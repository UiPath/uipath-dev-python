"""Panel for displaying evaluation run details, traces, and logs."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, TabbedContent, TabPane, Tree
from textual.widgets.tree import TreeNode

from uipath.dev.models.eval_run import EvalRun
from uipath.dev.models.messages import LogMessage, TraceMessage


class SpanDetailsDisplay(Container):
    """Widget to display details of a selected span."""

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield RichLog(
            id="eval-span-details",
            max_lines=1000,
            highlight=True,
            markup=True,
            classes="span-detail-log",
        )

    def show_span_details(self, trace_msg: TraceMessage):
        """Display detailed information about a trace span."""
        details_log = self.query_one("#eval-span-details", RichLog)
        details_log.clear()

        details_log.write(f"[bold cyan]Span: {trace_msg.span_name}[/bold cyan]")

        details_log.write("")

        color_map = {
            "started": "blue",
            "running": "yellow",
            "completed": "green",
            "failed": "red",
            "error": "red",
        }
        color = color_map.get(trace_msg.status.lower(), "white")
        details_log.write(f"Status: [{color}]{trace_msg.status.upper()}[/{color}]")

        details_log.write(
            f"Started: [dim]{trace_msg.timestamp.strftime('%H:%M:%S.%f')[:-3]}[/dim]"
        )

        if trace_msg.duration_ms is not None:
            details_log.write(
                f"Duration: [yellow]{trace_msg.duration_ms:.2f}ms[/yellow]"
            )

        if trace_msg.attributes:
            details_log.write("")
            details_log.write("[bold]Attributes:[/bold]")
            for key, value in trace_msg.attributes.items():
                details_log.write(f"  {key}: {value}")

        details_log.write("")

        details_log.write(f"[dim]Trace ID: {trace_msg.trace_id}[/dim]")
        details_log.write(f"[dim]Span ID: {trace_msg.span_id}[/dim]")
        details_log.write(f"[dim]Run ID: {trace_msg.run_id}[/dim]")

        if trace_msg.parent_span_id:
            details_log.write(f"[dim]Parent Span: {trace_msg.parent_span_id}[/dim]")


class EvalRunDetailsPanel(Vertical):
    """Panel showing details, traces, and logs for selected eval run with tabbed interface."""

    current_run: reactive[EvalRun | None] = reactive(None)

    def __init__(self, **kwargs):
        """Initialize EvalRunDetailsPanel."""
        super().__init__(**kwargs)
        self.span_tree_nodes = {}
        self.current_run = None

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        with TabbedContent(id="eval-run-details-tabs"):
            with TabPane("Details", id="eval-details-tab"):
                yield RichLog(
                    id="eval-details-log",
                    max_lines=1000,
                    highlight=True,
                    markup=True,
                    classes="detail-log",
                )

            with TabPane("Traces", id="eval-traces-tab"):
                with Horizontal(classes="traces-content"):
                    # Left side - Span tree
                    with Vertical(
                        classes="spans-tree-section", id="eval-spans-tree-container"
                    ):
                        yield Tree("Trace", id="eval-spans-tree", classes="spans-tree")

                    # Right side - Span details
                    with Vertical(classes="span-details-section"):
                        yield SpanDetailsDisplay(id="eval-span-details-display")

            with TabPane("Logs", id="eval-logs-tab"):
                yield RichLog(
                    id="eval-logs-log",
                    max_lines=1000,
                    highlight=True,
                    markup=True,
                    classes="detail-log",
                )

    def watch_current_run(
        self, old_value: EvalRun | None, new_value: EvalRun | None
    ):
        """Watch for changes to the current run."""
        if new_value is not None:
            if old_value != new_value:
                self.current_run = new_value
                self.show_run(new_value)

    def update_run(self, eval_run: EvalRun) -> None:
        """Update the displayed run information."""
        self.current_run = eval_run
        self._show_run_details(eval_run)
        self._rebuild_spans_tree()

    def show_run(self, run: EvalRun):
        """Display details, traces, and logs for a specific run."""
        self._show_run_details(run)

        logs_log = self.query_one("#eval-logs-log", RichLog)
        logs_log.clear()
        for log in run.logs:
            self.add_log(log)

        self._rebuild_spans_tree()

    def switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab by id."""
        tabbed = self.query_one(TabbedContent)
        tabbed.active = tab_id

    def clear(self) -> None:
        """Clear the panel."""
        self.current_run = None
        try:
            details_log = self.query_one("#eval-details-log", RichLog)
            details_log.clear()
            logs_log = self.query_one("#eval-logs-log", RichLog)
            logs_log.clear()
            spans_tree = self.query_one("#eval-spans-tree", Tree)
            spans_tree.root.remove_children()
        except Exception:
            pass

    def _show_run_details(self, run: EvalRun):
        """Display detailed information about the run in the Details tab."""
        details_log = self.query_one("#eval-details-log", RichLog)
        details_log.clear()

        details_log.write(f"[bold cyan]Run ID: {run.id}[/bold cyan]")
        details_log.write("")

        status_color_map = {
            "pending": "grey50",
            "running": "yellow",
            "completed": "green",
            "failed": "red",
        }
        color = status_color_map.get(run.status.lower(), "white")
        details_log.write(
            f"[bold]Status:[/bold] [{color}]{run.status.upper()}[/{color}]"
        )

        details_log.write(
            f"[bold]Started:[/bold] [dim]{run.start_time.strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        )

        if run.end_time:
            details_log.write(
                f"[bold]Ended:[/bold] [dim]{run.end_time.strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
            )

        details_log.write(f"[bold]Duration:[/bold] [yellow]{run.duration}[/yellow]")

        details_log.write("")

        # Eval set info
        details_log.write(f"[bold]Eval Set:[/bold] {run.eval_set_path}")
        details_log.write(f"[bold]Entrypoint:[/bold] {run.entrypoint}")
        details_log.write(f"[bold]Workers:[/bold] {run.workers}")

        details_log.write("")

        if run.status == "completed":
            details_log.write(
                f"[bold]Overall Score:[/bold] [cyan]{run.overall_score * 100:.1f}%[/cyan]"
            )
            details_log.write(
                f"[bold]Total Evaluations:[/bold] {run.total_evaluations}"
            )

            details_log.write("")
            details_log.write("[bold]EVALUATOR SCORES:[/bold]")
            details_log.write("[dim]" + "=" * 50 + "[/dim]")

            for ev_id, score in run.evaluator_scores.items():
                score_pct = f"{score * 100:.1f}%"
                score_color = "green" if score == 1.0 else ("yellow" if score >= 0.5 else "red")
                details_log.write(f"  [{score_color}]{ev_id}: {score_pct}[/{score_color}]")

            details_log.write("")
            details_log.write("[bold]EVALUATION RESULTS:[/bold]")
            details_log.write("[dim]" + "=" * 50 + "[/dim]")

            for eval_result in run.evaluation_results:
                passed = eval_result.passed
                icon = "✓" if passed else "✗"
                icon_color = "green" if passed else "red"
                details_log.write(
                    f"[{icon_color}]{icon}[/{icon_color}] [bold]{eval_result.eval_name}[/bold]"
                )

                for ev_result in eval_result.evaluator_results:
                    result_score = f"{ev_result.score * 100:.0f}%"
                    result_color = "green" if ev_result.score == 1.0 else "red"
                    details_log.write(
                        f"    [{result_color}]{ev_result.evaluator_name}: {result_score}[/{result_color}]"
                    )
                    if ev_result.justification:
                        justification = ev_result.justification
                        truncated = (
                            f"{justification[:100]}..."
                            if len(justification) > 100
                            else justification
                        )
                        details_log.write(f"      [dim]{truncated}[/dim]")

        elif run.status == "failed" and run.error:
            details_log.write("[bold red]ERROR:[/bold red]")
            details_log.write("[dim]" + "=" * 50 + "[/dim]")
            if run.error.code:
                details_log.write(f"[red]Code: {run.error.code}[/red]")
            details_log.write(f"[red]Title: {run.error.title}[/red]")
            if run.error.detail:
                details_log.write(f"[red]\n{run.error.detail}[/red]")

        elif run.status == "running":
            details_log.write("[bold yellow]Running...[/bold yellow]")

    def _rebuild_spans_tree(self):
        """Rebuild the spans tree from current run's traces."""
        spans_tree = self.query_one("#eval-spans-tree", Tree)
        if spans_tree is None or spans_tree.root is None:
            return

        spans_tree.root.remove_children()

        self.span_tree_nodes.clear()

        if not self.current_run or not self.current_run.traces:
            return

        self._build_spans_tree(self.current_run.traces)

        # Expand the root "Trace" node
        spans_tree.root.expand()

    def _build_spans_tree(self, trace_messages: list[TraceMessage]):
        """Build the spans tree from trace messages."""
        spans_tree = self.query_one("#eval-spans-tree", Tree)
        root = spans_tree.root

        # Filter out spans without parents (artificial root spans)
        spans_by_id = {
            msg.span_id: msg for msg in trace_messages if msg.parent_span_id is not None
        }

        # Build parent-to-children mapping once upfront
        children_by_parent: dict[str, list[TraceMessage]] = {}
        for msg in spans_by_id.values():
            if msg.parent_span_id:
                if msg.parent_span_id not in children_by_parent:
                    children_by_parent[msg.parent_span_id] = []
                children_by_parent[msg.parent_span_id].append(msg)

        # Find root spans (parent doesn't exist in our filtered data)
        root_spans = [
            msg
            for msg in trace_messages
            if msg.parent_span_id and msg.parent_span_id not in spans_by_id
        ]

        # Build tree recursively for each root span
        for root_span in sorted(root_spans, key=lambda x: x.timestamp):
            self._add_span_with_children(root, root_span, children_by_parent)

    def _add_span_with_children(
        self,
        parent_node: TreeNode[str],
        trace_msg: TraceMessage,
        children_by_parent: dict[str, list[TraceMessage]],
    ):
        """Recursively add a span and all its children."""
        color_map = {
            "started": "🔵",
            "running": "🟡",
            "completed": "🟢",
            "failed": "🔴",
            "error": "🔴",
        }
        status_icon = color_map.get(trace_msg.status.lower(), "⚪")
        duration_str = (
            f" ({trace_msg.duration_ms:.1f}ms)" if trace_msg.duration_ms else ""
        )
        label = f"{status_icon} {trace_msg.span_name}{duration_str}"

        node = parent_node.add(label)
        node.data = trace_msg.span_id
        self.span_tree_nodes[trace_msg.span_id] = node
        node.expand()

        # Get children from prebuilt mapping - O(1) lookup
        children = children_by_parent.get(trace_msg.span_id, [])
        for child in sorted(children, key=lambda x: x.timestamp):
            self._add_span_with_children(node, child, children_by_parent)

    def on_tree_node_selected(self, event: Tree.NodeSelected[str]) -> None:
        """Handle span selection in the tree."""
        # Check if this is our spans tree
        spans_tree = self.query_one("#eval-spans-tree", Tree)
        if event.control != spans_tree:
            return

        # Get the selected span data
        if hasattr(event.node, "data") and event.node.data:
            span_id = event.node.data
            # Find the trace in current_run.traces
            trace_msg = None
            if self.current_run:
                for trace in self.current_run.traces:
                    if trace.span_id == span_id:
                        trace_msg = trace
                        break

            if trace_msg:
                span_details_display = self.query_one(
                    "#eval-span-details-display", SpanDetailsDisplay
                )
                span_details_display.show_span_details(trace_msg)

    def add_trace(self, trace_msg: TraceMessage):
        """Add trace to current run if it matches."""
        if not self.current_run or trace_msg.run_id != self.current_run.id:
            return

        # Rebuild the tree to include new trace
        self._rebuild_spans_tree()

    def add_log(self, log_msg: LogMessage):
        """Add log to current run if it matches."""
        if not self.current_run or log_msg.run_id != self.current_run.id:
            return

        color_map = {
            "DEBUG": "dim cyan",
            "INFO": "blue",
            "WARN": "yellow",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }

        color = color_map.get(log_msg.level.upper(), "white")
        timestamp_str = log_msg.timestamp.strftime("%H:%M:%S")
        level_short = log_msg.level[:4].upper()

        logs_log = self.query_one("#eval-logs-log", RichLog)
        if isinstance(log_msg.message, str):
            log_text = (
                f"[dim]{timestamp_str}[/dim] "
                f"[{color}]{level_short}[/{color}] "
                f"{log_msg.message}"
            )
            logs_log.write(log_text)
        else:
            logs_log.write(log_msg.message)

    def refresh_display(self):
        """Refresh the display with current run data."""
        if self.current_run:
            self.show_run(self.current_run)
