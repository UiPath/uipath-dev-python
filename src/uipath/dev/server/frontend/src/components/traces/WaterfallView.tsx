import { useMemo } from "react";
import type { TraceSpan } from "../../types/run";
import type { TreeNode } from "./TraceTree";
import { STATUS_COLORS, SpanKindIcon, formatDuration } from "./TraceTree";

interface Props {
  tree: TreeNode[];
  selectedSpan: TraceSpan | null;
  onSelect: (span: TraceSpan) => void;
}

interface FlatRow {
  span: TraceSpan;
  depth: number;
}

function flattenTree(nodes: TreeNode[]): FlatRow[] {
  const result: FlatRow[] = [];
  function walk(node: TreeNode, depth: number) {
    result.push({ span: node.span, depth });
    for (const child of node.children) walk(child, depth + 1);
  }
  for (const node of nodes) walk(node, 0);
  return result;
}

export default function WaterfallView({ tree, selectedSpan, onSelect }: Props) {
  const rows = useMemo(() => flattenTree(tree), [tree]);

  const { globalStart, totalDuration } = useMemo(() => {
    if (rows.length === 0) return { globalStart: 0, totalDuration: 1 };
    let minStart = Infinity;
    let maxEnd = -Infinity;
    for (const { span } of rows) {
      const start = new Date(span.timestamp).getTime();
      minStart = Math.min(minStart, start);
      maxEnd = Math.max(maxEnd, start + (span.duration_ms ?? 0));
    }
    return { globalStart: minStart, totalDuration: Math.max(maxEnd - minStart, 1) };
  }, [rows]);

  if (rows.length === 0) return null;

  return (
    <>
      {rows.map(({ span, depth }) => {
        const startMs = new Date(span.timestamp).getTime() - globalStart;
        const durationMs = span.duration_ms ?? 0;
        const leftPct = (startMs / totalDuration) * 100;
        const widthPct = Math.max((durationMs / totalDuration) * 100, 0.3);
        const statusColor = STATUS_COLORS[span.status.toLowerCase()] ?? "var(--text-muted)";
        const isSelected = span.span_id === selectedSpan?.span_id;
        const spanKind = span.attributes?.["openinference.span.kind"] as string | undefined;

        return (
          <button
            key={span.span_id}
            data-span-id={span.span_id}
            onClick={() => onSelect(span)}
            className="w-full text-left text-xs leading-normal py-1 flex items-center transition-colors"
            style={{
              background: isSelected
                ? "color-mix(in srgb, var(--accent) 10%, var(--bg-primary))"
                : undefined,
              borderLeft: isSelected ? "2px solid var(--accent)" : "2px solid transparent",
            }}
            onMouseEnter={(e) => {
              if (!isSelected) e.currentTarget.style.background = "var(--bg-hover)";
            }}
            onMouseLeave={(e) => {
              if (!isSelected) e.currentTarget.style.background = "";
            }}
          >
            {/* Name */}
            <div
              className="shrink-0 flex items-center gap-1 overflow-hidden"
              style={{ width: "35%", minWidth: "80px", paddingLeft: `${depth * 12 + 4}px` }}
            >
              <span className="shrink-0 flex items-center justify-center w-3.5 h-3.5">
                <SpanKindIcon kind={spanKind} statusColor={statusColor} />
              </span>
              <span className="text-[var(--text-primary)] truncate">{span.span_name}</span>
            </div>

            {/* Timeline bar */}
            <div
              className="flex-1 relative h-[14px] mx-1 rounded-sm"
              style={{ background: "var(--bg-secondary)" }}
            >
              <div
                className="absolute rounded-sm"
                style={{
                  left: `${leftPct}%`,
                  width: `${widthPct}%`,
                  top: "2px",
                  bottom: "2px",
                  background: statusColor,
                  opacity: 0.8,
                  minWidth: "2px",
                }}
              />
            </div>

            {/* Duration */}
            <span
              className="shrink-0 text-[10px] tabular-nums pr-2"
              style={{ width: "52px", textAlign: "right", color: "var(--text-muted)" }}
            >
              {formatDuration(span.duration_ms)}
            </span>
          </button>
        );
      })}
    </>
  );
}
