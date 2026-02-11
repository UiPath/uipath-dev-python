import { useState, useMemo, useCallback } from "react";
import type { TraceSpan } from "../../types/run";

/* ------------------------------------------------------------------ */
/*  Status configuration                                               */
/* ------------------------------------------------------------------ */

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  started: { color: "var(--info)", label: "Started" },
  running: { color: "var(--warning)", label: "Running" },
  completed: { color: "var(--success)", label: "Completed" },
  failed: { color: "var(--error)", label: "Failed" },
  error: { color: "var(--error)", label: "Error" },
};

const DEFAULT_STATUS = { color: "var(--text-muted)", label: "Unknown" };

/* ------------------------------------------------------------------ */
/*  Value helpers                                                      */
/* ------------------------------------------------------------------ */

/** Try to parse a string as JSON; return the pretty-printed version or null. */
function tryParseJson(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  ) {
    try {
      const parsed = JSON.parse(trimmed);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return null;
    }
  }
  return null;
}

/** Format a duration in ms to a human-friendly string. */
function formatDuration(ms: number): string {
  if (ms < 1) return `${(ms * 1000).toFixed(0)}us`;
  if (ms < 1000) return `${ms.toFixed(2)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = ((ms % 60000) / 1000).toFixed(1);
  return `${mins}m ${secs}s`;
}

/** Truncate a string value beyond a threshold, returning [display, isTruncated]. */
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

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

interface Props {
  span: TraceSpan;
}

/** Expandable value cell for the attributes table. */
function AttributeValue({ value }: { value: unknown }) {
  const [expanded, setExpanded] = useState(false);

  const raw = stringifyValue(value);
  const jsonFormatted = useMemo(() => tryParseJson(value), [value]);
  const displayValue = jsonFormatted ?? raw;
  const isLong = displayValue.length > TRUNCATE_LIMIT || displayValue.includes("\n");

  const toggle = useCallback(() => setExpanded((prev) => !prev), []);

  if (!isLong) {
    return (
      <span
        className="font-mono text-xs break-all"
        style={{ color: "var(--text-primary)" }}
      >
        {displayValue}
      </span>
    );
  }

  return (
    <div className="space-y-1">
      {expanded ? (
        <pre
          className="font-mono text-xs whitespace-pre-wrap break-all p-2 rounded-md overflow-x-auto"
          style={{
            color: "var(--text-primary)",
            background: "var(--bg-primary)",
            border: "1px solid var(--border)",
          }}
        >
          {displayValue}
        </pre>
      ) : (
        <span
          className="font-mono text-xs break-all"
          style={{ color: "var(--text-primary)" }}
        >
          {displayValue.slice(0, TRUNCATE_LIMIT)}...
        </span>
      )}
      <button
        onClick={toggle}
        className="text-[10px] font-semibold cursor-pointer px-1.5 py-0.5 rounded"
        style={{
          color: "var(--info)",
          background: "color-mix(in srgb, var(--info) 10%, transparent)",
        }}
      >
        {expanded ? "Collapse" : "Expand"}
      </button>
    </div>
  );
}

/** A small labeled metric card used in the metadata grid. */
function MetaCard({
  label,
  value,
  mono,
  color,
}: {
  label: string;
  value: string;
  mono?: boolean;
  color?: string;
}) {
  return (
    <div
      className="rounded-lg p-2.5 min-w-0"
      style={{
        background: "var(--bg-secondary)",
        border: "1px solid var(--border)",
      }}
    >
      <div
        className="text-[10px] uppercase font-semibold mb-1 tracking-wide"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </div>
      <div
        className={`text-xs truncate ${mono ? "font-mono" : "font-medium"}`}
        style={{ color: color ?? "var(--text-primary)" }}
        title={value}
      >
        {value}
      </div>
    </div>
  );
}

/** Copyable ID row shown in the identifiers section. */
function IdRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(() => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [value]);

  return (
    <div
      className="flex items-center gap-2 group px-2.5 py-1.5 rounded-md transition-colors"
      style={{ background: "transparent" }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.background = "var(--bg-tertiary)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.background = "transparent";
      }}
    >
      <span
        className="text-[10px] uppercase font-semibold shrink-0 w-16 tracking-wide"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </span>
      <span
        className="text-xs font-mono truncate flex-1"
        style={{ color: "var(--text-secondary)" }}
        title={value}
      >
        {value}
      </span>
      <button
        onClick={copy}
        className="opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-semibold px-1.5 py-0.5 rounded cursor-pointer shrink-0"
        style={{
          color: copied ? "var(--success)" : "var(--text-muted)",
          background: "var(--bg-primary)",
          border: "1px solid var(--border)",
        }}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

/** Section wrapper with a colored left accent bar. */
function Section({
  title,
  color,
  children,
  defaultOpen = true,
}: {
  title: string;
  color: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{
        background: "var(--card-bg)",
        border: "1px solid var(--border)",
      }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 cursor-pointer text-left"
        style={{
          background: "color-mix(in srgb, var(--bg-tertiary) 40%, var(--card-bg))",
        }}
      >
        <div
          className="w-0.5 h-3.5 rounded-full shrink-0"
          style={{ background: color }}
        />
        <span
          className="text-[10px] uppercase font-bold tracking-wider flex-1"
          style={{ color }}
        >
          {title}
        </span>
        <span
          className="text-xs transition-transform"
          style={{
            color: "var(--text-muted)",
            transform: open ? "rotate(0deg)" : "rotate(-90deg)",
          }}
        >
          &#x25BE;
        </span>
      </button>
      {open && <div className="p-3">{children}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export default function SpanDetails({ span }: Props) {
  const status =
    STATUS_CONFIG[span.status.toLowerCase()] ?? {
      ...DEFAULT_STATUS,
      label: span.status,
    };

  const time = new Date(span.timestamp).toLocaleTimeString(undefined, {
    hour12: false,
    fractionalSecondDigits: 3,
  } as Intl.DateTimeFormatOptions);

  const date = new Date(span.timestamp).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  const attrEntries = Object.entries(span.attributes);
  const hasAttributes = attrEntries.length > 0;

  const ids: { label: string; value: string }[] = [
    { label: "Span", value: span.span_id },
    ...(span.trace_id ? [{ label: "Trace", value: span.trace_id }] : []),
    { label: "Run", value: span.run_id },
    ...(span.parent_span_id
      ? [{ label: "Parent", value: span.parent_span_id }]
      : []),
  ];

  return (
    <div className="space-y-3 p-3 overflow-y-auto h-full">
      {/* ---- Header card ---- */}
      <div
        className="rounded-lg p-4"
        style={{
          background: "var(--card-bg)",
          border: "1px solid var(--border)",
        }}
      >
        {/* Top row: name + status badge */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <h3
            className="text-sm font-semibold leading-snug break-words min-w-0"
            style={{ color: "var(--text-primary)" }}
          >
            {span.span_name}
          </h3>
          <span
            className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide"
            style={{
              background: `color-mix(in srgb, ${status.color} 15%, var(--bg-secondary))`,
              color: status.color,
            }}
          >
            <span
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{ background: status.color }}
            />
            {status.label}
          </span>
        </div>

        {/* Metric row */}
        <div className="grid grid-cols-2 gap-2">
          {span.duration_ms != null && (
            <div
              className="rounded-md px-3 py-2"
              style={{
                background: "var(--bg-secondary)",
                border: "1px solid var(--border)",
              }}
            >
              <div
                className="text-[10px] uppercase font-semibold tracking-wide mb-0.5"
                style={{ color: "var(--text-muted)" }}
              >
                Duration
              </div>
              <div
                className="text-sm font-bold font-mono"
                style={{ color: "var(--warning)" }}
              >
                {formatDuration(span.duration_ms)}
              </div>
            </div>
          )}
          <div
            className="rounded-md px-3 py-2"
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
            }}
          >
            <div
              className="text-[10px] uppercase font-semibold tracking-wide mb-0.5"
              style={{ color: "var(--text-muted)" }}
            >
              Started
            </div>
            <div
              className="text-sm font-bold font-mono"
              style={{ color: "var(--text-primary)" }}
            >
              {time}
            </div>
          </div>
        </div>

        {/* Date subtitle */}
        <div
          className="mt-2 text-[10px] font-medium"
          style={{ color: "var(--text-muted)" }}
        >
          {date}
        </div>
      </div>

      {/* ---- Timing metadata ---- */}
      <div className="grid grid-cols-2 gap-2">
        <MetaCard label="Status" value={status.label} color={status.color} />
        <MetaCard
          label="Duration (raw)"
          value={
            span.duration_ms != null ? `${span.duration_ms.toFixed(2)}ms` : "--"
          }
          mono
          color="var(--warning)"
        />
      </div>

      {/* ---- Attributes ---- */}
      {hasAttributes && (
        <Section
          title={`Attributes (${attrEntries.length})`}
          color="var(--accent)"
        >
          <div className="rounded-md overflow-hidden" style={{ border: "1px solid var(--border)" }}>
            {attrEntries.map(([key, value], idx) => (
              <div
                key={key}
                className="flex gap-3 px-3 py-2 text-xs items-start"
                style={{
                  background:
                    idx % 2 === 0
                      ? "var(--bg-secondary)"
                      : "color-mix(in srgb, var(--bg-tertiary) 30%, var(--bg-secondary))",
                  borderBottom:
                    idx < attrEntries.length - 1
                      ? "1px solid var(--border)"
                      : "none",
                }}
              >
                <span
                  className="font-mono font-semibold shrink-0 pt-px"
                  style={{
                    color: "var(--info)",
                    minWidth: "30%",
                    maxWidth: "40%",
                    wordBreak: "break-all",
                    overflowWrap: "break-word",
                  }}
                >
                  {key}
                </span>
                <span className="flex-1 min-w-0">
                  <AttributeValue value={value} />
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ---- Identifiers ---- */}
      <Section title="Identifiers" color="var(--info)" defaultOpen={false}>
        <div className="space-y-0.5">
          {ids.map((id) => (
            <IdRow key={id.label} label={id.label} value={id.value} />
          ))}
        </div>
      </Section>
    </div>
  );
}
