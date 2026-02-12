import { useState, useEffect } from "react";
import type { TraceSpan } from "../../types/run";
import SpanDetails from "./SpanDetails";

const STATUS_COLORS: Record<string, string> = {
  started: "var(--info)",
  running: "var(--warning)",
  completed: "var(--success)",
  failed: "var(--error)",
  error: "var(--error)",
};

interface Props {
  traces: TraceSpan[];
}

interface TreeNode {
  span: TraceSpan;
  children: TreeNode[];
}

function buildTree(traces: TraceSpan[]): TreeNode[] {
  const byId = new Map(traces.map((t) => [t.span_id, t]));
  const childrenMap = new Map<string, TraceSpan[]>();

  for (const t of traces) {
    if (t.parent_span_id) {
      const list = childrenMap.get(t.parent_span_id) ?? [];
      list.push(t);
      childrenMap.set(t.parent_span_id, list);
    }
  }

  // Root spans: no parent or parent not in our data
  const roots = traces.filter(
    (t) => t.parent_span_id === null || !byId.has(t.parent_span_id),
  );

  function build(span: TraceSpan): TreeNode {
    const kids = (childrenMap.get(span.span_id) ?? [])
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    return { span, children: kids.map(build) };
  }

  return roots
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    .map(build);
}

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "";
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export default function TraceTree({ traces }: Props) {
  const [selectedSpan, setSelectedSpan] = useState<TraceSpan | null>(null);
  const [leftWidth, setLeftWidth] = useState(() => {
    const saved = localStorage.getItem("traceTreeSplitWidth");
    return saved ? parseFloat(saved) : 50;
  });
  const [isDragging, setIsDragging] = useState(false);
  const tree = buildTree(traces);

  // Attach global mouse listeners when dragging
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const container = document.querySelector(".trace-tree-container");
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const newWidth = ((e.clientX - rect.left) / rect.width) * 100;
      const clampedWidth = Math.max(20, Math.min(80, newWidth));
      setLeftWidth(clampedWidth);
      localStorage.setItem("traceTreeSplitWidth", String(clampedWidth));
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  return (
    <div className="flex h-full trace-tree-container" style={{ cursor: isDragging ? "col-resize" : undefined }}>
      {/* Left: tree view */}
      <div className="pr-0.5 pt-0.5" style={{ width: `${leftWidth}%` }}>
        <div className="overflow-y-auto h-full p-0.5">
          {tree.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-[var(--text-muted)] text-sm">No traces yet</p>
            </div>
          ) : (
            tree.map((node, i) => (
              <TreeNodeView
                key={node.span.span_id}
                node={node}
                depth={0}
                selectedId={selectedSpan?.span_id ?? null}
                onSelect={setSelectedSpan}
                isLast={i === tree.length - 1}
              />
            ))
          )}
        </div>
      </div>

      {/* Draggable divider */}
      <div
        onMouseDown={handleMouseDown}
        className="shrink-0 w-1.5 cursor-col-resize bg-[var(--border)] hover:bg-[var(--accent)] transition-colors relative"
        style={isDragging ? { background: "var(--accent)" } : undefined}
      >
        <div className="absolute inset-0 -left-1 -right-1" />
      </div>

      {/* Right: span details */}
      <div className="flex-1 overflow-hidden p-0.5">
        {selectedSpan ? (
          <SpanDetails span={selectedSpan} />
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-[var(--text-muted)] text-sm">
              Select a span to view details
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function TreeNodeView({
  node,
  depth,
  selectedId,
  onSelect,
  isLast,
}: {
  node: TreeNode;
  depth: number;
  selectedId: string | null;
  onSelect: (span: TraceSpan) => void;
  isLast: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  const { span } = node;
  const statusColor = STATUS_COLORS[span.status.toLowerCase()] ?? "var(--text-muted)";
  const duration = formatDuration(span.duration_ms);
  const isSelected = span.span_id === selectedId;
  const hasChildren = node.children.length > 0;
  const indent = depth * 20;

  return (
    <div className="relative">
      {/* Vertical connector line from parent */}
      {depth > 0 && (
        <div
          className="absolute top-0 z-10 pointer-events-none"
          style={{
            left: `${indent - 10}px`,
            width: "1px",
            height: isLast ? "16px" : "100%",
            background: "var(--border)",
          }}
        />
      )}

      {/* Row */}
      <button
        onClick={() => onSelect(span)}
        className="w-full text-left text-xs py-1.5 pr-2 flex items-center gap-1.5 transition-colors relative"
        style={{
          paddingLeft: `${indent + 4}px`,
          background: isSelected
            ? "color-mix(in srgb, var(--accent) 10%, var(--bg-primary))"
            : undefined,
          borderLeft: isSelected ? `2px solid var(--accent)` : "2px solid transparent",
        }}
        onMouseEnter={(e) => {
          if (!isSelected) e.currentTarget.style.background = "var(--bg-hover)";
        }}
        onMouseLeave={(e) => {
          if (!isSelected) e.currentTarget.style.background = "";
        }}
      >
        {/* Horizontal connector line */}
        {depth > 0 && (
          <div
            className="absolute z-10 pointer-events-none"
            style={{
              left: `${indent - 10}px`,
              top: "50%",
              width: "10px",
              height: "1px",
              background: "var(--border)",
            }}
          />
        )}

        {/* Expand/collapse chevron */}
        {hasChildren ? (
          <span
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="shrink-0 w-4 h-4 flex items-center justify-center cursor-pointer rounded hover:bg-[var(--bg-hover)]"
            style={{ color: "var(--text-muted)" }}
          >
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}
            >
              <path d="M3 1.5L7 5L3 8.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        ) : (
          <span className="shrink-0 w-4" />
        )}

        {/* Status dot */}
        <span
          className="shrink-0 w-2 h-2 rounded-full"
          style={{ background: statusColor }}
        />

        {/* Span name */}
        <span className="text-[var(--text-primary)] truncate min-w-0 flex-1">
          {span.span_name}
        </span>

        {/* Duration right-aligned */}
        {duration && (
          <span className="text-[var(--text-muted)] shrink-0 ml-auto pl-2 tabular-nums">
            {duration}
          </span>
        )}
      </button>

      {/* Children */}
      {expanded &&
        node.children.map((child, i) => (
          <TreeNodeView
            key={child.span.span_id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            onSelect={onSelect}
            isLast={i === node.children.length - 1}
          />
        ))}
    </div>
  );
}
