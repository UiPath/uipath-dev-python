import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import type { TraceSpan } from "../../types/run";
import { useRunStore } from "../../store/useRunStore";
import SpanDetails from "./SpanDetails";

const STATUS_COLORS: Record<string, string> = {
  started: "var(--info)",
  running: "var(--warning)",
  completed: "var(--success)",
  failed: "var(--error)",
  error: "var(--error)",
};

/* Icons for openinference.span.kind */
function SpanKindIcon({ kind, statusColor }: { kind: string | undefined; statusColor: string }) {
  const color = statusColor;
  const size = 14;
  const props = { width: size, height: size, viewBox: "0 0 16 16", fill: "none", stroke: color, strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

  switch (kind) {
    case "LLM":
      // Brain / sparkle icon
      return (
        <svg {...props}>
          <path d="M8 2L9 5L12 4L10 7L14 8L10 9L12 12L9 11L8 14L7 11L4 12L6 9L2 8L6 7L4 4L7 5Z" fill={color} stroke="none" />
        </svg>
      );
    case "TOOL":
      // Wrench icon
      return (
        <svg {...props}>
          <path d="M10.5 2.5a3.5 3.5 0 0 0-3.17 4.93L3.5 11.27a1 1 0 0 0 0 1.41l.82.82a1 1 0 0 0 1.41 0l3.84-3.83A3.5 3.5 0 1 0 10.5 2.5z" />
        </svg>
      );
    case "AGENT":
      // Bot / agent icon
      return (
        <svg {...props}>
          <rect x="3" y="5" width="10" height="8" rx="2" />
          <circle cx="6" cy="9" r="1" fill={color} stroke="none" />
          <circle cx="10" cy="9" r="1" fill={color} stroke="none" />
          <path d="M8 2v3" />
          <path d="M6 2h4" />
        </svg>
      );
    case "CHAIN":
      // Chain links icon
      return (
        <svg {...props}>
          <path d="M6.5 9.5L9.5 6.5" />
          <path d="M4.5 8.5l-1 1a2 2 0 0 0 2.83 2.83l1-1" />
          <path d="M11.5 7.5l1-1a2 2 0 0 0-2.83-2.83l-1 1" />
        </svg>
      );
    case "RETRIEVER":
      // Search / magnifier icon
      return (
        <svg {...props}>
          <circle cx="7" cy="7" r="4" />
          <path d="M10 10l3.5 3.5" />
        </svg>
      );
    case "EMBEDDING":
      // Grid / matrix icon
      return (
        <svg {...props}>
          <rect x="2" y="2" width="4" height="4" rx="0.5" />
          <rect x="10" y="2" width="4" height="4" rx="0.5" />
          <rect x="2" y="10" width="4" height="4" rx="0.5" />
          <rect x="10" y="10" width="4" height="4" rx="0.5" />
        </svg>
      );
    default:
      // Fallback: status dot
      return (
        <span
          className="shrink-0 w-2 h-2 rounded-full"
          style={{ background: statusColor }}
        />
      );
  }
}

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

  const tree = roots
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    .map(build);

  // Skip "root" spans — promote their children
  return tree.flatMap((node) =>
    node.span.span_name === "root" ? node.children : [node],
  );
}

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "";
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function treeToJson(nodes: TreeNode[]): unknown[] {
  return nodes.map((node) => {
    const { span } = node;
    if (node.children.length > 0) {
      return { name: span.span_name, children: treeToJson(node.children) };
    }
    return { name: span.span_name };
  });
}

export default function TraceTree({ traces }: Props) {
  const [selectedSpan, setSelectedSpan] = useState<TraceSpan | null>(null);
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [leftWidth, setLeftWidth] = useState(() => {
    const saved = localStorage.getItem("traceTreeSplitWidth");
    return saved ? parseFloat(saved) : 50;
  });
  const [isDragging, setIsDragging] = useState(false);
  const [copied, setCopied] = useState(false);
  const tree = buildTree(traces);

  const treeJson = useMemo(() => JSON.stringify(treeToJson(tree), null, 2), [traces]);

  const copyTree = useCallback(() => {
    navigator.clipboard.writeText(treeJson).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [treeJson]);

  const focusedSpan = useRunStore((s) => s.focusedSpan);
  const setFocusedSpan = useRunStore((s) => s.setFocusedSpan);
  const [scrollToSpanId, setScrollToSpanId] = useState<string | null>(null);
  const treeScrollRef = useRef<HTMLDivElement>(null);

  const toggleExpanded = useCallback((spanId: string) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(spanId)) next.delete(spanId);
      else next.add(spanId);
      return next;
    });
  }, []);

  // Auto-select first span only when nothing is selected; keep selected span data fresh
  useEffect(() => {
    if (selectedSpan === null) {
      if (tree.length > 0) setSelectedSpan(tree[0].span);
    } else {
      const updated = traces.find((t) => t.span_id === selectedSpan.span_id);
      if (updated && updated !== selectedSpan) setSelectedSpan(updated);
    }
  }, [traces]);

  // React to focused span from chat tool call click
  useEffect(() => {
    if (!focusedSpan) return;

    // Find the Nth occurrence of spans with this name, sorted by timestamp
    const matches = traces
      .filter((t) => t.span_name === focusedSpan.name)
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    const match = matches[focusedSpan.index];

    if (match) {
      setSelectedSpan(match);
      setScrollToSpanId(match.span_id);

      // Expand all ancestors so the span is visible
      const parentMap = new Map(traces.map((t) => [t.span_id, t.parent_span_id]));
      setCollapsedIds((prev) => {
        const next = new Set(prev);
        let current = match.parent_span_id;
        while (current) {
          next.delete(current);
          current = parentMap.get(current) ?? null;
        }
        return next;
      });
    }

    setFocusedSpan(null);
  }, [focusedSpan, traces, setFocusedSpan]);

  // Scroll tree container to show the focused span
  // Use requestAnimationFrame to wait for React to paint expanded ancestors first
  useEffect(() => {
    if (!scrollToSpanId) return;
    const id = scrollToSpanId;
    setScrollToSpanId(null);

    requestAnimationFrame(() => {
      const container = treeScrollRef.current;
      const el = container?.querySelector<HTMLElement>(`[data-span-id="${id}"]`);
      if (container && el) {
        el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    });
  }, [scrollToSpanId]);

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
      <div className="pr-0.5 pt-0.5 relative" style={{ width: `${leftWidth}%` }}>
        {traces.length > 0 && (
          <button
            onClick={copyTree}
            className="absolute top-2 left-2 z-20 text-[10px] cursor-pointer px-1.5 py-0.5 rounded transition-opacity"
            style={{
              opacity: copied ? 1 : 0.3,
              color: copied ? "var(--success)" : "var(--text-muted)",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.opacity = "1"; }}
            onMouseLeave={(e) => { if (!copied) e.currentTarget.style.opacity = "0.3"; }}
          >
            {copied ? "Copied!" : "Copy JSON"}
          </button>
        )}
        <div ref={treeScrollRef} className="overflow-y-auto h-full p-0.5">
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
                collapsedIds={collapsedIds}
                toggleExpanded={toggleExpanded}
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
  collapsedIds,
  toggleExpanded,
}: {
  node: TreeNode;
  depth: number;
  selectedId: string | null;
  onSelect: (span: TraceSpan) => void;
  isLast: boolean;
  collapsedIds: Set<string>;
  toggleExpanded: (spanId: string) => void;
}) {
  const { span } = node;
  const expanded = !collapsedIds.has(span.span_id);
  const statusColor = STATUS_COLORS[span.status.toLowerCase()] ?? "var(--text-muted)";
  const duration = formatDuration(span.duration_ms);
  const isSelected = span.span_id === selectedId;
  const hasChildren = node.children.length > 0;
  const indent = depth * 20;
  const spanKind = span.attributes?.["openinference.span.kind"] as string | undefined;

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
        data-span-id={span.span_id}
        onClick={() => onSelect(span)}
        className="w-full text-left text-xs leading-normal py-1.5 pr-2 flex items-center gap-1.5 transition-colors relative"
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
              toggleExpanded(span.span_id);
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

        {/* Span kind icon */}
        <span className="shrink-0 flex items-center justify-center w-4 h-4">
          <SpanKindIcon kind={spanKind} statusColor={statusColor} />
        </span>

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
            collapsedIds={collapsedIds}
            toggleExpanded={toggleExpanded}
          />
        ))}
    </div>
  );
}
