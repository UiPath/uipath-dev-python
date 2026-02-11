"""Panel for displaying execution run details, traces, and logs."""

from collections import deque
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    RichLog,
    TabbedContent,
    TabPane,
    Tree,
)
from textual.widgets.tree import TreeNode

from uipath.dev.models.data import ChatData, LogData, TraceData
from uipath.dev.models.execution import ExecutionMode, ExecutionRun
from uipath.dev.ui.panels.chat_panel import ChatPanel


class SpanDetailsDisplay(Container):
    """Widget to display details of a selected span."""

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield RichLog(
            id="span-details",
            max_lines=1000,
            highlight=True,
            markup=True,
            auto_scroll=False,
            classes="span-detail-log",
        )

    def show_span_details(self, trace_data: TraceData):
        """Display detailed information about a trace span."""
        details_log = self.query_one("#span-details", RichLog)
        details_log.clear()

        details_log.write(f"[bold cyan]Span: {trace_data.span_name}[/bold cyan]")

        details_log.write("")

        color_map = {
            "started": "blue",
            "running": "yellow",
            "completed": "green",
            "failed": "red",
            "error": "red",
        }
        color = color_map.get(trace_data.status.lower(), "white")
        details_log.write(f"Status: [{color}]{trace_data.status.upper()}[/{color}]")

        details_log.write(
            f"Started: [dim]{trace_data.timestamp.strftime('%H:%M:%S.%f')[:-3]}[/dim]"
        )

        if trace_data.duration_ms is not None:
            details_log.write(
                f"Duration: [yellow]{trace_data.duration_ms:.2f}ms[/yellow]"
            )

        if trace_data.attributes:
            details_log.write("")
            details_log.write("[bold]Attributes:[/bold]")
            for key, value in trace_data.attributes.items():
                details_log.write(f"  {key}: {value}")

        details_log.write("")

        details_log.write(f"[dim]Trace ID: {trace_data.trace_id}[/dim]")
        details_log.write(f"[dim]Span ID: {trace_data.span_id}[/dim]")
        details_log.write(f"[dim]Run ID: {trace_data.run_id}[/dim]")

        if trace_data.parent_span_id:
            details_log.write(f"[dim]Parent Span: {trace_data.parent_span_id}[/dim]")

        details_log.scroll_home(animate=False)


_STATUS_ICONS: dict[str, str] = {
    "started": "🔵",
    "running": "🟡",
    "completed": "🟢",
    "failed": "🔴",
    "error": "🔴",
}


def _span_label(trace_data: TraceData) -> str:
    """Build the display label for a span tree node."""
    status_icon = _STATUS_ICONS.get(trace_data.status.lower(), "⚪")
    duration_str = (
        f" ({trace_data.duration_ms:.1f}ms)"
        if trace_data.duration_ms is not None
        else ""
    )
    return f"{status_icon} {trace_data.span_name}{duration_str}"


class RunDetailsPanel(Container):
    """Panel showing traces and logs for selected run with tabbed interface."""

    current_run: reactive[ExecutionRun | None] = reactive(None)

    def __init__(self, **kwargs):
        """Initialize RunDetailsPanel."""
        super().__init__(**kwargs)
        # Maps span_id -> TreeNode for incremental updates
        self.span_tree_nodes: dict[str, TreeNode[str]] = {}
        # Maps span_id -> last-seen TraceData to detect label changes
        self._span_trace_cache: dict[str, TraceData] = {}
        # Maps span_id -> last-computed label string (avoids recomputing for comparisons)
        self._span_label_cache: dict[str, str] = {}
        # Maps expected parent_span_id -> [child span_ids] for orphans
        # (children that arrived before their parent)
        self._orphaned_spans: dict[str, list[str]] = {}
        self.current_run = None
        self._chat_panel: ChatPanel | None = None
        self._spans_tree: Tree[Any] | None = None
        self._logs: RichLog | None = None
        self._details: RichLog | None = None
        self._debug_controls: Container | None = None

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        with TabbedContent():
            with TabPane("Details", id="run-tab"):
                yield RichLog(
                    id="run-details-log",
                    max_lines=1000,
                    highlight=True,
                    markup=True,
                    classes="detail-log",
                )

            with TabPane("Traces", id="traces-tab"):
                with Horizontal(classes="traces-content"):
                    # Left side - Span tree
                    with Vertical(
                        classes="spans-tree-section", id="spans-tree-container"
                    ):
                        yield Tree("Trace", id="spans-tree", classes="spans-tree")

                    # Right side - Span details
                    with Vertical(classes="span-details-section"):
                        yield SpanDetailsDisplay(id="span-details-display")

            with TabPane("Logs", id="logs-tab"):
                yield RichLog(
                    id="logs-log",
                    max_lines=1000,
                    highlight=True,
                    markup=True,
                    classes="detail-log",
                )

            with TabPane("Chat", id="chat-tab"):
                yield ChatPanel(id="chat-panel")

        # Global debug controls (hidden by default, shown when debug mode active)
        with Container(id="debug-controls", classes="debug-controls hidden"):
            with Horizontal(classes="debug-actions-row"):
                yield Button(
                    "▶ Step",
                    id="debug-step-btn",
                    variant="primary",
                    classes="action-btn",
                )
                yield Button(
                    "⏭ Continue",
                    id="debug-continue-btn",
                    variant="success",
                    classes="action-btn",
                )
                yield Button(
                    "⏹ Stop", id="debug-stop-btn", variant="error", classes="action-btn"
                )

    def on_mount(self) -> None:
        """Cache frequently used child widgets after mount."""
        self._chat_panel = self.query_one("#chat-panel", ChatPanel)
        self._spans_tree = self.query_one("#spans-tree", Tree)
        self._logs = self.query_one("#logs-log", RichLog)
        self._details = self.query_one("#run-details-log", RichLog)
        self._debug_controls = self.query_one("#debug-controls", Container)

    def watch_current_run(
        self, old_value: ExecutionRun | None, new_value: ExecutionRun | None
    ):
        """Watch for changes to the current run."""
        if new_value is not None:
            if old_value != new_value:
                self.current_run = new_value
                self.show_run(new_value)

    def update_run(self, run: ExecutionRun):
        """Update the displayed run information."""
        self.current_run = run

    def show_run(self, run: ExecutionRun):
        """Display traces and logs for a specific run."""
        assert self._logs is not None

        self._show_run_details(run)

        self._show_run_chat(run)

        self._logs.clear()
        for log in run.logs:
            self.add_log(log)

        # Full rebuild only on run switch
        self._full_rebuild_spans_tree()

    def switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab by id (e.g. 'run-tab', 'traces-tab')."""
        tabbed = self.query_one(TabbedContent)
        tabbed.active = tab_id

    def update_debug_controls_visibility(self, run: ExecutionRun):
        """Show or hide debug controls based on whether run is in debug mode."""
        assert self._debug_controls is not None

        if run.mode == ExecutionMode.DEBUG:
            self._debug_controls.remove_class("hidden")
            is_enabled = run.status == "suspended"
            for button in self._debug_controls.query(Button):
                button.disabled = not is_enabled
        else:
            self._debug_controls.add_class("hidden")

    def _flatten_values(self, value: object, prefix: str = "") -> list[str]:
        """Flatten nested dict/list structures into dot-notation paths."""
        lines: list[str] = []

        if value is None:
            lines.append(f"{prefix}: [dim]—[/dim]" if prefix else "[dim]—[/dim]")

        elif isinstance(value, dict):
            if not value:
                lines.append(f"{prefix}: {{}}" if prefix else "{}")
            else:
                for k, v in value.items():
                    new_prefix = f"{prefix}.{k}" if prefix else k
                    lines.extend(self._flatten_values(v, new_prefix))

        elif isinstance(value, list):
            if not value:
                lines.append(f"{prefix}: []" if prefix else "[]")
            else:
                for i, item in enumerate(value):
                    new_prefix = f"{prefix}[{i}]"
                    lines.extend(self._flatten_values(item, new_prefix))

        elif isinstance(value, str):
            if prefix:
                split_lines = value.splitlines()
                if split_lines:
                    lines.append(f"{prefix}: {split_lines[0]}")
                    for line in split_lines[1:]:
                        lines.append(f"{' ' * 2}{line}")
            else:
                lines.extend(value.splitlines())

        else:
            if prefix:
                lines.append(f"{prefix}: {value}")
            else:
                lines.append(str(value))

        return lines

    def _write_block(
        self, log: RichLog, title: str, data: object, style: str = "white"
    ) -> None:
        """Pretty-print a block with flattened dot-notation paths."""
        log.write(f"[bold {style}]{title.upper()}:[/bold {style}]")
        log.write("[dim]" + "=" * 50 + "[/dim]")

        for line in self._flatten_values(data):
            log.write(line)

        log.write("")

    def _show_run_details(self, run: ExecutionRun):
        """Display detailed information about the run in the Details tab."""
        assert self._details is not None

        self.update_debug_controls_visibility(run)

        self._details.clear()

        self._details.write(f"[bold cyan]Run ID: {run.id}[/bold cyan]")
        self._details.write("")

        status_color_map = {
            "started": "blue",
            "running": "yellow",
            "completed": "green",
            "failed": "red",
            "error": "red",
        }
        status = getattr(run, "status", "unknown")
        color = status_color_map.get(status.lower(), "white")
        self._details.write(f"[bold]Status:[/bold] [{color}]{status.upper()}[/{color}]")

        if hasattr(run, "start_time") and run.start_time:
            self._details.write(
                f"[bold]Started:[/bold] [dim]{run.start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}[/dim]"
            )

        if hasattr(run, "end_time") and run.end_time:
            self._details.write(
                f"[bold]Ended:[/bold] [dim]{run.end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}[/dim]"
            )

        if (
            hasattr(run, "start_time")
            and hasattr(run, "end_time")
            and run.start_time
            and run.end_time
        ):
            duration = (run.end_time - run.start_time).total_seconds() * 1000
            self._details.write(
                f"[bold]Duration:[/bold] [yellow]{duration:.2f}ms[/yellow]"
            )

        self._details.write("")

        if hasattr(run, "input_data"):
            self._write_block(self._details, "Input", run.input_data, style="green")

        if hasattr(run, "resume_data") and run.resume_data:
            self._write_block(self._details, "Resume", run.resume_data, style="green")

        if hasattr(run, "output_data"):
            self._write_block(self._details, "Output", run.output_data, style="magenta")

        if hasattr(run, "error") and run.error:
            self._details.write("[bold red]ERROR:[/bold red]")
            self._details.write("[dim]" + "=" * 50 + "[/dim]")
            if run.error.code:
                self._details.write(f"[red]Code: {run.error.code}[/red]")
            self._details.write(f"[red]Title: {run.error.title}[/red]")
            self._details.write(f"[red]\n{run.error.detail}[/red]")
            self._details.write("")

    def _show_run_chat(self, run: ExecutionRun) -> None:
        assert self._chat_panel is not None

        self._chat_panel.refresh_messages(run)

    def _full_rebuild_spans_tree(self):
        """Full rebuild of spans tree — only used on run switch."""
        if self._spans_tree is None or self._spans_tree.root is None:
            return

        # Batch all tree mutations into a single repaint cycle
        with self.app.batch_update():
            self._spans_tree.root.remove_children()
            self.span_tree_nodes.clear()
            self._span_trace_cache.clear()
            self._span_label_cache.clear()
            self._orphaned_spans.clear()

            if not self.current_run or not self.current_run.traces:
                return

            self._build_spans_tree(self.current_run.traces)

            # Expand the root "Trace" node
            self._spans_tree.root.expand()

    def _build_spans_tree(self, trace_data_list: list[TraceData]):
        """Build the spans tree from trace data."""
        assert self._spans_tree is not None

        root = self._spans_tree.root

        # Filter out spans without parents (artificial root spans)
        spans_by_id = {
            td.span_id: td for td in trace_data_list if td.parent_span_id is not None
        }

        # Build parent-to-children mapping once upfront
        children_by_parent: dict[str, list[TraceData]] = {}
        for td in spans_by_id.values():
            if td.parent_span_id:
                if td.parent_span_id not in children_by_parent:
                    children_by_parent[td.parent_span_id] = []
                children_by_parent[td.parent_span_id].append(td)

        # Find root spans (parent doesn't exist in our filtered data)
        root_spans = [
            td
            for td in trace_data_list
            if td.parent_span_id and td.parent_span_id not in spans_by_id
        ]

        # Build tree recursively for each root span
        for root_span in sorted(root_spans, key=lambda x: x.timestamp):
            self._add_span_with_children(root, root_span, children_by_parent)

    def _add_span_with_children(
        self,
        parent_node: TreeNode[str],
        trace_data: TraceData,
        children_by_parent: dict[str, list[TraceData]],
    ):
        """Recursively add a span and all its children."""
        label = _span_label(trace_data)

        node = parent_node.add(label)
        node.data = trace_data.span_id
        self.span_tree_nodes[trace_data.span_id] = node
        self._span_trace_cache[trace_data.span_id] = trace_data
        self._span_label_cache[trace_data.span_id] = label
        node.expand()

        # Get children from prebuilt mapping - O(1) lookup
        children = children_by_parent.get(trace_data.span_id, [])
        for child in sorted(children, key=lambda x: x.timestamp):
            self._add_span_with_children(node, child, children_by_parent)

    def _incremental_add_trace(self, trace_data: TraceData):
        """Incrementally add or update a single trace span in the tree.

        Handles OTel export ordering where children end (and export) before
        parents.  When a child arrives before its parent, it is temporarily
        parked under root.  When the parent finally arrives, orphaned children
        are re-parented under it.

        All tree mutations are wrapped in batch_update() so Textual coalesces
        the N invalidate/refresh cycles into a single repaint.
        """
        if self._spans_tree is None:
            return

        span_id = trace_data.span_id

        # --- UPDATE existing node (cheap: no tree structure change) ---
        if span_id in self.span_tree_nodes:
            new_label = _span_label(trace_data)
            if new_label != self._span_label_cache.get(span_id):
                self.span_tree_nodes[span_id].set_label(new_label)
                self._span_label_cache[span_id] = new_label
            self._span_trace_cache[span_id] = trace_data
            return

        # --- SKIP artificial root spans (no parent) ---
        # But first, re-parent any orphans that were waiting for this span.
        # Their parent_span_id points here; they're currently parked under
        # the tree root which is visually correct, so just clean up the dict.
        if trace_data.parent_span_id is None:
            self._orphaned_spans.pop(span_id, None)
            return

        # --- INSERT new node (+ possible re-parenting of orphans) ---
        # Batch all tree mutations into a single repaint cycle.
        with self.app.batch_update():
            is_orphan = False
            if trace_data.parent_span_id in self.span_tree_nodes:
                parent_node = self.span_tree_nodes[trace_data.parent_span_id]
            else:
                # Parent not in tree yet — park under root temporarily
                parent_node = self._spans_tree.root
                is_orphan = True

            label = _span_label(trace_data)
            node = parent_node.add(label)
            node.data = span_id
            self.span_tree_nodes[span_id] = node
            self._span_trace_cache[span_id] = trace_data
            self._span_label_cache[span_id] = label
            node.expand()
            parent_node.expand()

            # Track as orphan so we can re-parent when the real parent arrives
            if is_orphan:
                self._orphaned_spans.setdefault(trace_data.parent_span_id, []).append(
                    span_id
                )

            # --- RE-PARENT any orphans waiting for this span as their parent ---
            if span_id in self._orphaned_spans:
                orphan_ids = self._orphaned_spans.pop(span_id)
                for orphan_id in orphan_ids:
                    self._reparent_node(orphan_id, node)

    def _collect_subtree_span_ids(self, node: TreeNode[str]) -> list[str]:
        """Collect all span_ids in a subtree in BFS order (parent before children)."""
        result: list[str] = []
        queue: deque[TreeNode[str]] = deque([node])
        while queue:
            current = queue.popleft()
            if current.data:
                result.append(current.data)
            queue.extend(current.children)
        return result

    def _reparent_node(self, span_id: str, new_parent_node: TreeNode[str]) -> None:
        """Move a node (and its entire subtree) under a new parent.

        Textual's Tree has no move/reparent API, so we collect the subtree,
        remove the old node, and re-add everything under the new parent.
        """
        old_node = self.span_tree_nodes.get(span_id)
        if old_node is None:
            return

        # Collect the full subtree in BFS order *before* removing
        subtree_ids = self._collect_subtree_span_ids(old_node)

        # Remove old node (takes all its children with it)
        old_node.remove()

        # Re-add every node in BFS order (parents are processed before children
        # so the parent TreeNode always exists when we add a child)
        for sid in subtree_ids:
            trace = self._span_trace_cache.get(sid)
            if trace is None:
                continue

            # Reuse cached label instead of recomputing
            label = self._span_label_cache.get(sid)
            if label is None:
                label = _span_label(trace)
                self._span_label_cache[sid] = label
            if sid == span_id:
                target_parent = new_parent_node
            else:
                target_parent = self.span_tree_nodes.get(
                    trace.parent_span_id or "", new_parent_node
                )

            new_node = target_parent.add(label)
            new_node.data = sid
            self.span_tree_nodes[sid] = new_node
            new_node.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected[str]) -> None:
        """Handle span selection in the tree."""
        # Check if this is our spans tree
        if event.control != self._spans_tree:
            return

        # Get the selected span data
        if hasattr(event.node, "data") and event.node.data:
            span_id = event.node.data
            trace_data = self._span_trace_cache.get(span_id)

            if trace_data:
                span_details_display = self.query_one(
                    "#span-details-display", SpanDetailsDisplay
                )
                span_details_display.show_span_details(trace_data)

    def update_run_details(self, run: ExecutionRun):
        """Update run details if it matches the current run."""
        if not self.current_run or run.id != self.current_run.id:
            return

        self._show_run_details(run)

    def add_chat_message(
        self,
        chat_data: ChatData,
    ) -> None:
        """Add a chat message to the display."""
        assert self._chat_panel is not None

        if not self.current_run or chat_data.run_id != self.current_run.id:
            return

        self._chat_panel.add_chat_message(chat_data)

    def add_trace(self, trace_data: TraceData):
        """Add trace to current run if it matches."""
        if not self.current_run or trace_data.run_id != self.current_run.id:
            return

        # Incremental update instead of full rebuild
        self._incremental_add_trace(trace_data)

    def add_log(self, log_data: LogData):
        """Add log to current run if it matches."""
        assert self._logs is not None

        if not self.current_run or log_data.run_id != self.current_run.id:
            return

        color_map = {
            "DEBUG": "dim cyan",
            "INFO": "blue",
            "WARN": "yellow",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }

        color = color_map.get(log_data.level.upper(), "white")
        timestamp_str = log_data.timestamp.strftime("%H:%M:%S")
        level_short = log_data.level[:4].upper()

        log_text = (
            f"[dim]{timestamp_str}[/dim] "
            f"[{color}]{level_short}[/{color}] "
            f"{log_data.message}"
        )
        self._logs.write(log_text)

    def clear_display(self):
        """Clear both traces and logs display."""
        assert self._details is not None
        assert self._logs is not None
        assert self._spans_tree is not None

        self._details.clear()
        self._logs.clear()
        self._spans_tree.clear()

        self.current_run = None
        self.span_tree_nodes.clear()
        self._span_trace_cache.clear()
        self._span_label_cache.clear()
        self._orphaned_spans.clear()

        span_details_display = self.query_one(
            "#span-details-display", SpanDetailsDisplay
        )
        span_details_log = span_details_display.query_one("#span-details", RichLog)
        span_details_log.clear()

    def refresh_display(self):
        """Refresh the display with current run data."""
        if self.current_run:
            self.show_run(self.current_run)
