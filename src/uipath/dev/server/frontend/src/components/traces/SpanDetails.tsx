import { useState, useMemo, useCallback } from "react";
import type { TraceSpan } from "../../types/run";
import JsonHighlight from "../shared/JsonHighlight";

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  started: { color: "var(--info)", label: "Started" },
  running: { color: "var(--warning)", label: "Running" },
  completed: { color: "var(--success)", label: "Completed" },
  failed: { color: "var(--error)", label: "Failed" },
  error: { color: "var(--error)", label: "Error" },
};

const DEFAULT_STATUS = { color: "var(--text-muted)", label: "Unknown" };

function tryParseJson(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  ) {
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch {
      return null;
    }
  }
  return null;
}

function formatDuration(ms: number): string {
  if (ms < 1) return `${(ms * 1000).toFixed(0)}us`;
  if (ms < 1000) return `${ms.toFixed(2)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = ((ms % 60000) / 1000).toFixed(1);
  return `${mins}m ${secs}s`;
}

const TRUNCATE_LIMIT = 200;

function stringifyValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

interface Props {
  span: TraceSpan;
}

function AttributeValue({ value }: { value: unknown }) {
  const [expanded, setExpanded] = useState(false);
  const raw = stringifyValue(value);
  const jsonFormatted = useMemo(() => tryParseJson(value), [value]);
  const isJson = jsonFormatted !== null;
  const displayValue = jsonFormatted ?? raw;
  const isLong = displayValue.length > TRUNCATE_LIMIT || displayValue.includes("\n");
  const toggle = useCallback(() => setExpanded((prev) => !prev), []);

  if (!isLong) {
    return isJson ? (
      <JsonHighlight
        json={displayValue}
        className="font-mono text-[11px] break-all whitespace-pre-wrap"
        style={{}}
      />
    ) : (
      <span className="font-mono text-[11px] break-all" style={{ color: "var(--text-primary)" }}>
        {displayValue}
      </span>
    );
  }

  return (
    <div>
      {expanded ? (
        isJson ? (
          <JsonHighlight
            json={displayValue}
            className="font-mono text-[11px] whitespace-pre-wrap break-all"
            style={{}}
          />
        ) : (
          <pre
            className="font-mono text-[11px] whitespace-pre-wrap break-all"
            style={{ color: "var(--text-primary)" }}
          >
            {displayValue}
          </pre>
        )
      ) : (
        <span className="font-mono text-[11px] break-all" style={{ color: "var(--text-primary)" }}>
          {displayValue.slice(0, TRUNCATE_LIMIT)}...
        </span>
      )}
      <button
        onClick={toggle}
        className="text-[10px] cursor-pointer ml-1"
        style={{ color: "var(--info)" }}
      >
        {expanded ? "[less]" : "[more]"}
      </button>
    </div>
  );
}

export default function SpanDetails({ span }: Props) {
  const [attrsOpen, setAttrsOpen] = useState(true);
  const [idsOpen, setIdsOpen] = useState(false);
  const status = STATUS_CONFIG[span.status.toLowerCase()] ?? { ...DEFAULT_STATUS, label: span.status };

  const time = new Date(span.timestamp).toLocaleTimeString(undefined, {
    hour12: false,
    fractionalSecondDigits: 3,
  } as Intl.DateTimeFormatOptions);

  const attrEntries = Object.entries(span.attributes);
  const ids: { label: string; value: string }[] = [
    { label: "Span", value: span.span_id },
    ...(span.trace_id ? [{ label: "Trace", value: span.trace_id }] : []),
    { label: "Run", value: span.run_id },
    ...(span.parent_span_id ? [{ label: "Parent", value: span.parent_span_id }] : []),
  ];

  return (
    <div className="overflow-y-auto h-full text-xs leading-normal">
      {/* Header: name + pills */}
      <div
        className="px-2 py-1.5 border-b flex items-center gap-2 flex-wrap"
        style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
      >
        <span className="text-xs font-semibold mr-auto" style={{ color: "var(--text-primary)" }}>
          {span.span_name}
        </span>
        <span
          className="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider"
          style={{
            background: `color-mix(in srgb, ${status.color} 15%, var(--bg-secondary))`,
            color: status.color,
          }}
        >
          <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: status.color }} />
          {status.label}
        </span>
        {span.duration_ms != null && (
          <span className="shrink-0 font-mono text-[11px] font-semibold" style={{ color: "var(--warning)" }}>
            {formatDuration(span.duration_ms)}
          </span>
        )}
        <span className="shrink-0 font-mono text-[11px]" style={{ color: "var(--text-muted)" }}>
          {time}
        </span>
      </div>

      {/* Attributes — collapsible */}
      {attrEntries.length > 0 && (
        <>
          <div
            className="px-2 py-1 text-[10px] uppercase font-bold tracking-wider border-b cursor-pointer flex items-center"
            style={{ color: "var(--accent)", borderColor: "var(--border)", background: "var(--bg-secondary)" }}
            onClick={() => setAttrsOpen((o) => !o)}
          >
            <span className="flex-1">Attributes ({attrEntries.length})</span>
            <span style={{ color: "var(--text-muted)", transform: attrsOpen ? "rotate(0deg)" : "rotate(-90deg)" }}>
              &#x25BE;
            </span>
          </div>
          {attrsOpen && attrEntries.map(([key, value], idx) => (
            <div
              key={key}
              className="flex gap-2 px-2 py-1 items-start border-b"
              style={{
                borderColor: "var(--border)",
                background: idx % 2 === 0 ? "var(--bg-primary)" : "var(--bg-secondary)",
              }}
            >
              <span
                className="font-mono font-semibold shrink-0 pt-px truncate text-[11px]"
                style={{ color: "var(--info)", width: "35%" }}
                title={key}
              >
                {key}
              </span>
              <span className="flex-1 min-w-0">
                <AttributeValue value={value} />
              </span>
            </div>
          ))}
        </>
      )}

      {/* Identifiers — collapsible */}
      <div
        className="px-2 py-1 text-[10px] uppercase font-bold tracking-wider border-b cursor-pointer flex items-center"
        style={{ color: "var(--accent)", borderColor: "var(--border)", background: "var(--bg-secondary)" }}
        onClick={() => setIdsOpen((o) => !o)}
      >
        <span className="flex-1">Identifiers ({ids.length})</span>
        <span style={{ color: "var(--text-muted)", transform: idsOpen ? "rotate(0deg)" : "rotate(-90deg)" }}>
          &#x25BE;
        </span>
      </div>
      {idsOpen && ids.map((id, idx) => (
        <div
          key={id.label}
          className="flex gap-2 px-2 py-1 items-start border-b"
          style={{
            borderColor: "var(--border)",
            background: idx % 2 === 0 ? "var(--bg-primary)" : "var(--bg-secondary)",
          }}
        >
          <span
            className="font-mono font-semibold shrink-0 pt-px truncate text-[11px]"
            style={{ color: "var(--info)", width: "35%" }}
            title={id.label}
          >
            {id.label}
          </span>
          <span className="flex-1 min-w-0">
            <span className="font-mono text-[11px] break-all" style={{ color: "var(--text-primary)" }}>
              {id.value}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}
