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
        className="text-[11px] cursor-pointer ml-1 px-1"
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
  const [detailMode, setDetailMode] = useState<"table" | "json">("table");
  const [copied, setCopied] = useState(false);
  const status = STATUS_CONFIG[span.status.toLowerCase()] ?? { ...DEFAULT_STATUS, label: span.status };
  const spanJson = useMemo(() => JSON.stringify(span, null, 2), [span]);
  const copySpanJson = useCallback(() => {
    navigator.clipboard.writeText(spanJson).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [spanJson]);

  const attrEntries = Object.entries(span.attributes);
  const ids: { label: string; value: string }[] = [
    { label: "Span", value: span.span_id },
    ...(span.trace_id ? [{ label: "Trace", value: span.trace_id }] : []),
    { label: "Run", value: span.run_id },
    ...(span.parent_span_id ? [{ label: "Parent", value: span.parent_span_id }] : []),
  ];

  return (
    <div className="flex flex-col h-full text-xs leading-normal">
      {/* Header: tabs + status pill — fixed */}
      <div
        className="px-2 border-b flex items-center gap-1 shrink-0"
        style={{ borderColor: "var(--border)", background: "var(--bg-secondary)", height: "32px" }}
      >
        <button
          onClick={() => setDetailMode("table")}
          className="px-2.5 h-6 text-[11px] font-semibold rounded transition-colors cursor-pointer inline-flex items-center"
          style={{
            color: detailMode === "table" ? "var(--accent)" : "var(--text-muted)",
            background: detailMode === "table" ? "color-mix(in srgb, var(--accent) 10%, transparent)" : "transparent",
          }}
          onMouseEnter={(e) => { if (detailMode !== "table") e.currentTarget.style.color = "var(--text-primary)"; }}
          onMouseLeave={(e) => { if (detailMode !== "table") e.currentTarget.style.color = "var(--text-muted)"; }}
        >
          Table
        </button>
        <button
          onClick={() => setDetailMode("json")}
          className="px-2.5 h-6 text-[11px] font-semibold rounded transition-colors cursor-pointer inline-flex items-center"
          style={{
            color: detailMode === "json" ? "var(--accent)" : "var(--text-muted)",
            background: detailMode === "json" ? "color-mix(in srgb, var(--accent) 10%, transparent)" : "transparent",
          }}
          onMouseEnter={(e) => { if (detailMode !== "json") e.currentTarget.style.color = "var(--text-primary)"; }}
          onMouseLeave={(e) => { if (detailMode !== "json") e.currentTarget.style.color = "var(--text-muted)"; }}
        >
          JSON
        </button>
        <span
          className="ml-auto shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider"
          style={{
            background: `color-mix(in srgb, ${status.color} 15%, var(--bg-secondary))`,
            color: status.color,
          }}
        >
          <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: status.color }} />
          {status.label}
        </span>
      </div>

      {/* Scrollable content */}
      <div className="overflow-y-auto flex-1 p-0.5 pr-0 pt-0 mr-0.5 mt-0.5">
      {detailMode === "table" ? (
        <>
        {/* Attributes — collapsible */}
        {attrEntries.length > 0 && (
          <>
            <div
              className="px-2 py-1 text-[11px] uppercase font-bold tracking-wider border-b cursor-pointer flex items-center"
              style={{ color: "var(--success)", borderColor: "var(--border)", background: "var(--bg-secondary)" }}
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
          className="px-2 py-1 text-[11px] uppercase font-bold tracking-wider border-b cursor-pointer flex items-center"
          style={{ color: "var(--success)", borderColor: "var(--border)", background: "var(--bg-secondary)" }}
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
        </>
      ) : (
        <div className="relative">
          <button
            onClick={copySpanJson}
            className="absolute top-1 right-1 z-10 text-[11px] cursor-pointer px-2 py-1 rounded transition-colors"
            style={{
              color: copied ? "var(--success)" : "var(--text-muted)",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
            }}
            onMouseEnter={(e) => { if (!copied) e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = copied ? "var(--success)" : "var(--text-muted)"; }}
          >
            {copied ? "Copied!" : "Copy"}
          </button>
          <JsonHighlight json={spanJson} className="font-mono text-[11px] whitespace-pre-wrap p-2" style={{}} />
        </div>
      )}
      </div>
    </div>
  );
}
