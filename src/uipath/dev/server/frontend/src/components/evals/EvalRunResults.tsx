import { useCallback, useEffect, useRef, useState } from "react";
import { getEvalRun } from "../../api/eval-client";
import { useEvalStore } from "../../store/useEvalStore";
import { useHashRoute } from "../../hooks/useHashRoute";
import type { EvalRunDetail, EvalItemResult } from "../../types/eval";
import TraceTree from "../traces/TraceTree";
import JsonHighlight from "../shared/JsonHighlight";
import DataSection from "../shared/DataSection";

interface Props {
  evalRunId: string;
  itemName?: string | null;
}

function formatScore(score: number | null): string {
  if (score === null) return "-";
  return `${Math.round(score * 100)}%`;
}

function scoreColor(score: number | null): string {
  if (score === null) return "var(--text-muted)";
  const pct = score * 100;
  if (pct >= 80) return "var(--success)";
  if (pct >= 50) return "var(--warning)";
  return "var(--error)";
}

function formatDuration(startTime: string | null, endTime: string | null): string {
  if (!startTime) return "-";
  const start = new Date(startTime).getTime();
  const end = endTime ? new Date(endTime).getTime() : Date.now();
  const secs = Math.round((end - start) / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

function stripEvaluatorSuffix(name: string): string {
  return name.replace(/\s*Evaluator$/i, "");
}

const statusStyles: Record<string, { color: string; bg: string; label: string }> = {
  pending: { color: "var(--text-muted)", bg: "var(--bg-tertiary)", label: "Pending" },
  running: { color: "var(--info)", bg: "rgba(59,130,246,0.1)", label: "Running" },
  completed: { color: "var(--success)", bg: "rgba(34,197,94,0.1)", label: "Completed" },
  failed: { color: "var(--error)", bg: "rgba(239,68,68,0.1)", label: "Failed" },
};

export default function EvalRunResults({ evalRunId, itemName }: Props) {
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const { navigate } = useHashRoute();

  const selectedItemName = itemName ?? null;

  // Item list height (top panel, resizable like GraphPanel)
  const [itemListHeight, setItemListHeight] = useState(220);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRow = useRef(false);

  // Sidebar width (right panel, resizable like ChatPanel)
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem("evalSidebarWidth");
    return saved ? parseInt(saved, 10) : 320;
  });
  const [isDragging, setIsDragging] = useState(false);
  const outerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem("evalSidebarWidth", String(sidebarWidth));
  }, [sidebarWidth]);

  const storeRun = useEvalStore((s) => s.evalRuns[evalRunId]);
  const evaluators = useEvalStore((s) => s.evaluators);

  useEffect(() => {
    setLoading(true);
    getEvalRun(evalRunId)
      .then((d) => {
        setDetail(d);
        // Auto-navigate to first item if none selected
        if (!itemName) {
          const first = d.results.find((r) => r.status === "completed") ?? d.results[0];
          if (first) navigate(`#/evals/runs/${evalRunId}/${encodeURIComponent(first.name)}`);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [evalRunId]);

  // Re-fetch when store run status reaches terminal
  useEffect(() => {
    if (storeRun?.status === "completed" || storeRun?.status === "failed") {
      getEvalRun(evalRunId).then(setDetail).catch(console.error);
    }
  }, [storeRun?.status, evalRunId]);

  // Auto-select first completed item as results come in (when no item is in route)
  useEffect(() => {
    if (itemName || !detail?.results) return;
    const first = detail.results.find((r) => r.status === "completed") ?? detail.results[0];
    if (first) navigate(`#/evals/runs/${evalRunId}/${encodeURIComponent(first.name)}`);
  }, [detail?.results]);

  // --- Row resize (item list height) ---
  const onRowResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    draggingRow.current = true;

    const startY = "touches" in e ? e.touches[0].clientY : e.clientY;
    const startH = itemListHeight;

    const onMove = (ev: MouseEvent | TouchEvent) => {
      if (!draggingRow.current) return;
      const container = containerRef.current;
      if (!container) return;
      const clientY = "touches" in ev ? ev.touches[0].clientY : ev.clientY;
      const maxH = container.clientHeight - 100;
      const newH = Math.max(80, Math.min(maxH, startH + (clientY - startY)));
      setItemListHeight(newH);
    };

    const onUp = () => {
      draggingRow.current = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend", onUp);
  }, [itemListHeight]);

  // --- Sidebar col resize ---
  const onSidebarResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    setIsDragging(true);

    const startX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const startW = sidebarWidth;

    const onMove = (ev: MouseEvent | TouchEvent) => {
      const container = outerRef.current;
      if (!container) return;
      const clientX = "touches" in ev ? ev.touches[0].clientX : ev.clientX;
      const maxW = container.clientWidth - 300;
      const newW = Math.max(280, Math.min(maxW, startW + (startX - clientX)));
      setSidebarWidth(newW);
    };

    const onUp = () => {
      setIsDragging(false);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend", onUp);
  }, [sidebarWidth]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-sm">
        Loading...
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--text-muted)]">
        Eval run not found
      </div>
    );
  }

  const run = storeRun ?? detail;
  const status = statusStyles[run.status] ?? statusStyles.pending;
  const isRunning = run.status === "running";
  const evaluatorIds = Object.keys(run.evaluator_scores ?? {});
  const selectedItem = detail.results.find((r) => r.name === selectedItemName) ?? null;
  const selectedTraces = (selectedItem?.traces ?? []).map((t) => ({ ...t, run_id: "" }));

  return (
    <div ref={outerRef} className="flex h-full">
      {/* Main content: item list (top) + traces (bottom) */}
      <div ref={containerRef} className="flex flex-col flex-1 min-w-0">
        {/* Header bar */}
        <div className="px-4 h-10 border-b shrink-0 flex items-center gap-4" style={{ borderColor: "var(--border)" }}>
          <h1 className="text-base font-semibold truncate min-w-0" style={{ color: "var(--text-primary)" }}>
            {run.eval_set_name}
          </h1>
          <span
            className="px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: status.color, background: status.bg }}
          >
            {status.label}
          </span>
          <span className="text-sm font-bold font-mono" style={{ color: scoreColor(run.overall_score) }}>
            {formatScore(run.overall_score)}
          </span>
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
            {formatDuration(run.start_time, run.end_time)}
          </span>
          {isRunning && (
            <div className="flex items-center gap-2 max-w-[160px]">
              <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-tertiary)" }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${run.progress_total > 0 ? (run.progress_completed / run.progress_total) * 100 : 0}%`,
                    background: "var(--info)",
                  }}
                />
              </div>
              <span className="text-[11px] shrink-0" style={{ color: "var(--text-muted)" }}>
                {run.progress_completed}/{run.progress_total}
              </span>
            </div>
          )}
          {/* Per-evaluator scores inline */}
          {evaluatorIds.length > 0 && (
            <div className="flex gap-3 ml-auto">
              {evaluatorIds.map((id) => {
                const ev = evaluators.find((e) => e.id === id);
                const score = run.evaluator_scores[id];
                return (
                  <div key={id} className="flex items-center gap-1.5">
                    <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                      {stripEvaluatorSuffix(ev?.name ?? id)}
                    </span>
                    <div className="w-12 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-tertiary)" }}>
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${score * 100}%`, background: scoreColor(score) }}
                      />
                    </div>
                    <span className="text-[11px] font-mono" style={{ color: scoreColor(score) }}>
                      {formatScore(score)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Item list (resizable height, like GraphPanel) */}
        <div className="shrink-0 overflow-hidden flex flex-col" style={{ height: itemListHeight }}>
          {/* Table header */}
          <div
            className="flex items-center px-3 h-7 text-[11px] font-semibold shrink-0 border-b"
            style={{ color: "var(--text-muted)", background: "var(--bg-secondary)", borderColor: "var(--border)" }}
          >
            <span className="w-5 shrink-0" />
            <span className="flex-1 min-w-0">Name</span>
            <span className="w-14 shrink-0 text-right">Score</span>
            {evaluatorIds.map((id) => {
              const ev = evaluators.find((e) => e.id === id);
              return (
                <span key={id} className="w-36 shrink-0 text-right truncate pl-2" title={ev?.name ?? id}>{stripEvaluatorSuffix(ev?.name ?? id)}</span>
              );
            })}
            <span className="w-14 shrink-0 text-right">Time</span>
          </div>
          {/* Scrollable item rows */}
          <div className="flex-1 overflow-y-auto">
            {detail.results.map((item: EvalItemResult) => {
              const isPending = item.status === "pending";
              const isFailed = item.status === "failed";
              const isSelected = item.name === selectedItemName;
              return (
                <button
                  key={item.name}
                  onClick={() => {
                    if (isSelected) {
                      navigate(`#/evals/runs/${evalRunId}`);
                    } else {
                      navigate(`#/evals/runs/${evalRunId}/${encodeURIComponent(item.name)}`);
                    }
                  }}
                  className="w-full text-left px-3 py-1.5 flex items-center text-xs border-b transition-colors cursor-pointer"
                  style={{
                    borderColor: "var(--border)",
                    background: isSelected ? "color-mix(in srgb, var(--accent) 10%, var(--bg-primary))" : undefined,
                    borderLeft: isSelected ? "2px solid var(--accent)" : "2px solid transparent",
                    opacity: isPending ? 0.5 : 1,
                  }}
                  onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "var(--bg-hover)"; }}
                  onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = ""; }}
                >
                  {/* Status dot */}
                  <span className="w-5 shrink-0 flex justify-center">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{
                        background: isPending ? "var(--text-muted)"
                          : isFailed ? "var(--error)"
                          : item.overall_score >= 0.8 ? "var(--success)"
                          : item.overall_score >= 0.5 ? "var(--warning)"
                          : "var(--error)",
                      }}
                    />
                  </span>
                  {/* Name */}
                  <span className="flex-1 min-w-0 truncate" style={{ color: "var(--text-primary)" }}>
                    {item.name}
                  </span>
                  {/* Overall score */}
                  <span className="w-14 shrink-0 text-right font-mono font-semibold" style={{ color: scoreColor(isPending ? null : item.overall_score) }}>
                    {isPending ? "-" : formatScore(item.overall_score)}
                  </span>
                  {/* Per-evaluator scores */}
                  {evaluatorIds.map((id) => (
                    <span key={id} className="w-36 shrink-0 text-right font-mono pl-2" style={{ color: scoreColor(isPending ? null : item.scores[id] ?? null) }}>
                      {isPending ? "-" : formatScore(item.scores[id] ?? null)}
                    </span>
                  ))}
                  {/* Duration */}
                  <span className="w-14 shrink-0 text-right" style={{ color: "var(--text-muted)" }}>
                    {item.duration_ms !== null ? `${(item.duration_ms / 1000).toFixed(1)}s` : "-"}
                  </span>
                </button>
              );
            })}
            {detail.results.length === 0 && (
              <div className="flex items-center justify-center py-8 text-[var(--text-muted)] text-xs">
                {isRunning ? "Waiting for results..." : "No results"}
              </div>
            )}
          </div>
        </div>

        {/* Row drag handle */}
        <div
          onMouseDown={onRowResizeStart}
          onTouchStart={onRowResizeStart}
          className="shrink-0 drag-handle-row"
        />

        {/* Trace tree (bottom, flex-1, like TraceTree in debug) */}
        <div className="flex-1 overflow-hidden">
          {selectedItem && selectedTraces.length > 0 ? (
            <TraceTree traces={selectedTraces} />
          ) : (
            <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-xs">
              {selectedItem?.status === "pending" ? "Pending..." : "No traces available"}
            </div>
          )}
        </div>
      </div>

      {/* Sidebar drag handle */}
      <div
        onMouseDown={onSidebarResizeStart}
        onTouchStart={onSidebarResizeStart}
        className={`shrink-0 drag-handle-col${isDragging ? "" : " transition-all"}`}
        style={{ width: selectedItem ? 3 : 0, opacity: selectedItem ? 1 : 0 }}
      />

      {/* Right sidebar */}
      <DetailsSidebar
        width={sidebarWidth}
        item={selectedItem}
        evaluators={evaluators}
        isRunning={isRunning}
        isDragging={isDragging}
      />
    </div>
  );
}

type DetailTab = "score" | "io" | "logs";

const detailTabs: { id: DetailTab; label: string }[] = [
  { id: "score", label: "Score" },
  { id: "io", label: "I/O" },
  { id: "logs", label: "Logs" },
];

function DetailsSidebar({
  width,
  item,
  evaluators,
  isRunning,
  isDragging,
}: {
  width: number;
  item: EvalItemResult | null;
  evaluators: { id: string; name: string }[];
  isRunning: boolean;
  isDragging: boolean;
}) {
  const [tab, setTab] = useState<DetailTab>("score");

  const showSidebar = !!item;

  return (
    <div
      className={`shrink-0 flex flex-col overflow-hidden${isDragging ? "" : " transition-[width] duration-200 ease-in-out"}`}
      style={{ width: showSidebar ? width : 0, background: "var(--bg-primary)" }}
    >
      {/* Tab bar */}
      <div
        className="flex items-center gap-1 px-2 h-10 border-b shrink-0"
        style={{ borderColor: "var(--border)", background: "var(--bg-secondary)", minWidth: width }}
      >
        {detailTabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="px-2.5 py-1 h-7 text-xs font-semibold rounded transition-colors cursor-pointer"
            style={{
              color: tab === t.id ? "var(--accent)" : "var(--text-muted)",
              background: tab === t.id ? "color-mix(in srgb, var(--accent) 10%, transparent)" : "transparent",
              border: "none",
            }}
            onMouseEnter={(e) => { if (tab !== t.id) e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { if (tab !== t.id) e.currentTarget.style.color = "var(--text-muted)"; }}
          >
            {t.label}
          </button>
        ))}
        {isRunning && (
          <span
            className="ml-auto text-[11px] px-2 py-0.5 rounded-full shrink-0"
            style={{
              background: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))",
              color: "var(--warning)",
            }}
          >
            Running...
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto" style={{ minWidth: width }}>
        {!item ? null : item.status === "pending" ? (
          <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-xs">
            Pending...
          </div>
        ) : (
          <>
            {item.status === "failed" && (
              <div
                className="mx-2 mt-2 px-3 py-2 rounded text-xs"
                style={{ background: "rgba(239,68,68,0.1)", color: "var(--error)" }}
              >
                <div className="flex items-center gap-2 font-semibold">
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5"/><path d="M8 4.5v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><circle cx="8" cy="11" r="0.75" fill="currentColor"/></svg>
                  <span>Evaluator error</span>
                </div>
                {item.error && (
                  <div className="mt-1 pl-[22px] text-[11px] opacity-80 break-words" style={{ color: "var(--text-secondary)" }}>
                    {item.error}
                  </div>
                )}
              </div>
            )}
            {tab === "score" ? (
              <ScoreTab item={item} evaluators={evaluators} />
            ) : tab === "io" ? (
              <IOTab item={item} />
            ) : (
              <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-xs">
                Logs coming soon
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ScoreTab({ item, evaluators }: { item: EvalItemResult; evaluators: { id: string; name: string }[] }) {
  const evalIds = Object.keys(item.scores);

  return (
    <div className="p-2 overflow-y-auto h-full space-y-1.5">
      {/* Overall */}
      <div
        className="overflow-hidden"
        style={{ border: "1px solid var(--border)" }}
      >
        <div
          className="px-3 py-2 flex items-center gap-2"
          style={{ background: "var(--bg-secondary)" }}
        >
          <span className="truncate text-[11px] font-semibold" style={{ color: "var(--text-primary)" }}>
            Overall
          </span>
          <div className="ml-auto flex items-center gap-2">
            <div className="w-24 h-2.5 rounded-full overflow-hidden" style={{ background: "var(--bg-tertiary)" }}>
              <div
                className="h-full rounded-full"
                style={{ width: `${item.overall_score * 100}%`, background: scoreColor(item.overall_score) }}
              />
            </div>
            <span className="text-xs font-mono font-bold shrink-0 w-10 text-right" style={{ color: scoreColor(item.overall_score) }}>
              {formatScore(item.overall_score)}
            </span>
          </div>
        </div>
      </div>

      {/* Failed: no evaluator scores */}
      {item.status === "failed" && evalIds.length === 0 && (
        <div
          className="px-3 py-3 text-xs text-center"
          style={{ color: "var(--text-muted)" }}
        >
          All evaluators failed — no scores available
        </div>
      )}

      {/* Per-evaluator scores */}
      {evalIds.map((evId) => {
            const ev = evaluators.find((e) => e.id === evId);
            const score = item.scores[evId];
            const justification = item.justifications[evId];
            return (
              <div
                key={evId}
                className="overflow-hidden"
                style={{ border: "1px solid var(--border)" }}
              >
                <div
                  className="px-3 py-2 flex items-center gap-2"
                  style={{ background: "var(--bg-secondary)" }}
                >
                  <span className="truncate text-[11px] font-semibold" style={{ color: "var(--text-primary)" }} title={ev?.name ?? evId}>
                    {ev?.name ?? evId}
                  </span>
                  <div className="ml-auto flex items-center gap-2">
                    <div className="w-24 h-2.5 rounded-full overflow-hidden" style={{ background: "var(--bg-tertiary)" }}>
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${score * 100}%`, background: scoreColor(score) }}
                      />
                    </div>
                    <span className="text-xs font-mono font-bold shrink-0 w-10 text-right" style={{ color: scoreColor(score) }}>
                      {formatScore(score)}
                    </span>
                  </div>
                </div>
                {justification && (
                  <JustificationBlock text={justification} />
                )}
              </div>
            );
          })}
    </div>
  );
}

function IOTab({ item }: { item: EvalItemResult }) {
  const inputJson = JSON.stringify(item.inputs, null, 2);
  const outputJson = typeof item.output === "string" ? item.output : JSON.stringify(item.output, null, 2);
  const expectedJson = item.expected_output != null
    ? (typeof item.expected_output === "string" ? item.expected_output : JSON.stringify(item.expected_output, null, 2))
    : null;

  return (
    <div className="p-2 overflow-y-auto h-full space-y-1.5">
      <DataSection title="Input" copyText={inputJson}>
        <JsonHighlight
          json={inputJson}
          className="px-3 py-2 text-xs font-mono whitespace-pre-wrap break-words"
        />
      </DataSection>

      {expectedJson && (
        <DataSection title="Expected Output" copyText={expectedJson}>
          <JsonHighlight
            json={expectedJson}
            className="px-3 py-2 text-xs font-mono whitespace-pre-wrap break-words"
          />
        </DataSection>
      )}

      <DataSection
        title="Output"
        copyText={outputJson}
        trailing={item.duration_ms !== null ? (
          <span className="ml-auto text-[10px]" style={{ color: "var(--text-muted)" }}>
            {(item.duration_ms / 1000).toFixed(2)}s
          </span>
        ) : undefined}
      >
        <JsonHighlight
          json={outputJson}
          className="px-3 py-2 text-xs font-mono whitespace-pre-wrap break-words"
        />
      </DataSection>
    </div>
  );
}

/** Try to parse `expected="..." actual="..."` from justification text into structured blocks. */
function parseExpectedActual(text: string): { expected: string; actual: string; meta: Record<string, string> } | null {
  const m = text.match(/expected="(.+?)"\s+actual="(.+?)"(.*)/s);
  if (!m) return null;
  // Parse trailing key=value pairs like matched_leaves=1.0 total_leaves=1.0
  const meta: Record<string, string> = {};
  const rest = m[3]?.trim() ?? "";
  if (rest) {
    for (const pair of rest.match(/(\w+)=([\S]+)/g) ?? []) {
      const eq = pair.indexOf("=");
      meta[pair.slice(0, eq)] = pair.slice(eq + 1);
    }
  }
  return { expected: m[1], actual: m[2], meta };
}

function tryFormatValue(raw: string): string {
  // Python dict repr → JSON: single quotes → double quotes, True/False/None → JSON equivalents
  try {
    const jsonLike = raw
      .replace(/'/g, '"')
      .replace(/\bTrue\b/g, "true")
      .replace(/\bFalse\b/g, "false")
      .replace(/\bNone\b/g, "null");
    const parsed = JSON.parse(jsonLike);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return raw;
  }
}

function JustificationBlock({ text }: { text: string }) {
  const parsed = parseExpectedActual(text);

  if (!parsed) {
    // Fallback: plain text
    return (
      <div className="px-3 py-2 border-t" style={{ borderColor: "var(--border)" }}>
        <div className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {text}
        </div>
      </div>
    );
  }

  const expected = tryFormatValue(parsed.expected);
  const actual = tryFormatValue(parsed.actual);
  const match = expected === actual;

  return (
    <div className="border-t" style={{ borderColor: "var(--border)" }}>
      <div className="grid grid-cols-2 gap-0">
        {/* Expected */}
        <div className="px-3 py-2 border-r" style={{ borderColor: "var(--border)" }}>
          <div className="text-[10px] font-semibold mb-1" style={{ color: "var(--text-muted)" }}>
            Expected
          </div>
          <pre
            className="text-[11px] font-mono whitespace-pre-wrap break-words"
            style={{ color: "var(--text-secondary)" }}
          >
            {expected}
          </pre>
        </div>
        {/* Actual */}
        <div className="px-3 py-2">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[10px] font-semibold" style={{ color: "var(--text-muted)" }}>
              Actual
            </span>
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: match ? "var(--success)" : "var(--error)" }}
            />
          </div>
          <pre
            className="text-[11px] font-mono whitespace-pre-wrap break-words"
            style={{ color: match ? "var(--success)" : "var(--error)" }}
          >
            {actual}
          </pre>
        </div>
      </div>
      {Object.keys(parsed.meta).length > 0 && (
        <div className="px-3 py-1.5 border-t flex items-center gap-3" style={{ borderColor: "var(--border)" }}>
          {Object.entries(parsed.meta).map(([k, v]) => (
            <span key={k} className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              <span className="font-medium">{k.replace(/_/g, " ")}</span>{" "}
              <span className="font-mono">{v}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
