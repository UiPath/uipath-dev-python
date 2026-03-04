import { useEffect, useState, useCallback, useRef } from "react";
import { useAgentStore } from "../../store/useAgentStore";
import { getAgentSessionRawState } from "../../api/agent-client";
import type { AgentRawState, AgentTraceSpan, TraceMessage } from "../../types/agent";
import { DiffView } from "./DiffView";

// ─── Colors ─────────────────────────────────────────────────────────
const ROLE: Record<string, { border: string; fg: string; bg: string; label: string }> = {
  user:      { border: "#22c55e", fg: "#22c55e", bg: "color-mix(in srgb, #22c55e 8%, transparent)",  label: "USER" },
  assistant: { border: "#a855f7", fg: "#a855f7", bg: "color-mix(in srgb, #a855f7 8%, transparent)",  label: "ASSISTANT" },
  tool:      { border: "#f59e0b", fg: "#f59e0b", bg: "color-mix(in srgb, #f59e0b 8%, transparent)",  label: "TOOL" },
  system:    { border: "#3b82f6", fg: "#3b82f6", bg: "color-mix(in srgb, #3b82f6 8%, transparent)",  label: "SYSTEM" },
  thinking:  { border: "#64748b", fg: "#94a3b8", bg: "color-mix(in srgb, #64748b 6%, transparent)",  label: "THINKING" },
};
function roleStyle(r: string) { return ROLE[r] || ROLE.system; }

// ─── Helpers ────────────────────────────────────────────────────────
function fmtMs(ms: number) { return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`; }
function fmtTok(n: number) { return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n); }
function trunc(s: string, n: number) { return s.length <= n ? s : s.slice(0, n) + "\u2026"; }
function prettyJson(s: string) { try { return JSON.stringify(JSON.parse(s), null, 2); } catch { return s; } }

// ─── Icons ──────────────────────────────────────────────────────────
function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
      style={{ transition: "transform .12s", transform: open ? "rotate(90deg)" : "rotate(0)", flexShrink: 0, opacity: 0.5 }}>
      <path d="M9 18l6-6-6-6" />
    </svg>
  );
}

// ═════════════════════════════════════════════════════════════════════
// Root
// ═════════════════════════════════════════════════════════════════════
export default function AgentStatePanel() {
  const sessionId = useAgentStore((s) => s.sessionId);
  const status = useAgentStore((s) => s.status);
  const [data, setData] = useState<AgentRawState | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    if (!sessionId) return;
    setLoading(true);
    getAgentSessionRawState(sessionId)
      .then((s) => { if (s) setData(s); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sessionId]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { refresh(); }, [status, refresh]);

  if (!sessionId) return <Empty text="No active agent session" />;
  if (!data && loading) return <Empty text="Loading trace data\u2026" />;
  if (!data) return <Empty text="No trace data available" />;

  const total = data.total_prompt_tokens + data.total_completion_tokens;

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--bg-primary)" }}>
      {/* ── Header bar ────────────────────────────────────────── */}
      <div className="shrink-0 flex items-center gap-3 px-4 h-10 border-b"
        style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        <span className="text-[12px] font-bold" style={{ color: "var(--text-primary)" }}>Trace</span>
        <Pill text={data.model || "?"} />
        <Pill text={`${data.turn_count} turn${data.turn_count !== 1 ? "s" : ""}`} />
        <Pill text={`${fmtTok(total)} tok`} />
        <StatusDot status={data.status} />
        <div className="flex-1" />
        <CopyJsonButton data={data} />
        <button onClick={refresh}
          className="text-[11px] px-2 py-0.5 rounded cursor-pointer"
          style={{ background: "var(--bg-hover)", color: "var(--text-secondary)", border: "none" }}>
          {loading ? "\u2026" : "Refresh"}
        </button>
      </div>

      {/* ── Scroll ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <TopSection label="System Prompt">
          <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words font-mono m-0"
            style={{ color: "var(--text-secondary)" }}>
            {data.system_prompt || "(empty)"}
          </pre>
        </TopSection>

        <TopSection label={`Tools (${data.tool_schemas.length})`}>
          <div className="space-y-0.5">
            {data.tool_schemas.map((t) => (
              <div key={t.function.name} className="flex items-baseline gap-2 py-px">
                <code className="text-[11px] font-semibold shrink-0" style={{ color: "var(--accent)" }}>{t.function.name}</code>
                {t.function.description && (
                  <span className="text-[11px] truncate" style={{ color: "var(--text-muted)" }}>{t.function.description}</span>
                )}
              </div>
            ))}
          </div>
        </TopSection>

        {/* ── Spans ───────────────────────────────────────────── */}
        {data.traces.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm" style={{ color: "var(--text-muted)" }}>
            No spans yet — send a message to the agent.
          </div>
        ) : (
          data.traces.map((span, i) => (
            <SpanBlock key={i} span={span} index={i} defaultOpen={i === data.traces.length - 1} />
          ))
        )}
      </div>
    </div>
  );
}

// ─── Tiny components ────────────────────────────────────────────────
function Empty({ text }: { text: string }) {
  return <div className="flex items-center justify-center h-full" style={{ color: "var(--text-muted)" }}><p className="text-sm">{text}</p></div>;
}
function Pill({ text }: { text: string }) {
  return <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: "var(--bg-hover)", color: "var(--text-muted)" }}>{text}</span>;
}
function StatusDot({ status }: { status: string }) {
  const active = ["thinking", "executing", "awaiting_approval"].includes(status);
  const color = status === "error" ? "var(--error)" : active ? "var(--accent)" : "var(--success)";
  return (
    <span className="flex items-center gap-1 text-[11px]" style={{ color }}>
      <span className={`w-1.5 h-1.5 rounded-full${active ? " animate-pulse" : ""}`} style={{ background: color }} />
      {status}
    </span>
  );
}
function CopyJsonButton({ data }: { data: AgentRawState }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(data.traces, null, 2));
    setCopied(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={handleCopy}
      className="text-[11px] px-2 py-0.5 rounded cursor-pointer"
      style={{ background: "var(--bg-hover)", color: copied ? "var(--success)" : "var(--text-secondary)", border: "none" }}>
      {copied ? "Copied!" : "Copy JSON"}
    </button>
  );
}

// ─── Top-level collapsible (system prompt, tools) ───────────────────
function TopSection({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b" style={{ borderColor: "var(--border)" }}>
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2 cursor-pointer"
        style={{ background: open ? "var(--bg-secondary)" : "transparent", border: "none" }}>
        <ChevronIcon open={open} />
        <span className="text-[11px] font-semibold" style={{ color: "var(--text-primary)" }}>{label}</span>
      </button>
      {open && <div className="px-4 pb-3 pt-1" style={{ background: "var(--bg-secondary)" }}>{children}</div>}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════
// Span block — one per LLM call
// ═════════════════════════════════════════════════════════════════════
function SpanBlock({ span, index, defaultOpen }: { span: AgentTraceSpan; index: number; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const tok = span.prompt_tokens + span.completion_tokens;
  const nTools = span.output_tool_calls.length;

  return (
    <div className="border-b" style={{ borderColor: "var(--border)" }}>
      {/* ── Span header ─────────────────────────────────────── */}
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 cursor-pointer"
        style={{ background: "transparent", border: "none" }}>
        <ChevronIcon open={open} />
        <span className="text-[12px] font-bold tabular-nums w-14 shrink-0" style={{ color: "var(--text-primary)" }}>
          Turn {index + 1}
        </span>
        <Pill text={fmtMs(span.duration_ms)} />
        <Pill text={`${fmtTok(tok)} tok`} />
        {nTools > 0 && (
          <span className="text-[11px] px-1.5 py-0.5 rounded font-medium"
            style={{ background: ROLE.tool.bg, color: ROLE.tool.fg }}>
            {nTools} tool{nTools > 1 ? "s" : ""}
          </span>
        )}
        <div className="flex-1" />
        <span className="text-[11px] tabular-nums" style={{ color: "var(--text-muted)" }}>
          {fmtTok(span.prompt_tokens)} in &middot; {fmtTok(span.completion_tokens)} out
        </span>
      </button>

      {/* ── Expanded ────────────────────────────────────────── */}
      {open && (
        <div className="px-4 pb-4">
          {/* Input messages */}
          <ConversationThread
            label={`Input (${span.input_messages.length} messages)`}
            messages={span.input_messages}
            defaultOpen={false}
          />

          {/* Divider */}
          <div className="flex items-center gap-2 my-3">
            <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
            <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>Response</span>
            <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
          </div>

          {/* Output */}
          <div className="space-y-2">
            {span.output_thinking && (
              <MessageCard role="thinking" content={span.output_thinking} />
            )}
            {span.output_content ? (
              <MessageCard role="assistant" content={span.output_content} />
            ) : !span.output_thinking ? (
              <div className="text-[11px] italic pl-3" style={{ color: "var(--text-muted)" }}>(no text output)</div>
            ) : null}
          </div>

          {/* Tool calls */}
          {nTools > 0 && (
            <>
              <div className="flex items-center gap-2 my-3">
                <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
                <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
                  Tool Calls ({nTools})
                </span>
                <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
              </div>
              <div className="space-y-2">
                {span.output_tool_calls.map((tc, i) => {
                  const res = span.tool_results?.find((r) => r.name === tc.name);
                  return <ToolCallCard key={i} name={tc.name} args={tc.arguments} result={res?.result} />;
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════
// Conversation thread — renders a list of messages
// ═════════════════════════════════════════════════════════════════════
function ConversationThread({ label, messages, defaultOpen }: {
  label: string;
  messages: TraceMessage[];
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const MAX_COLLAPSED = 4;
  const [showAll, setShowAll] = useState(false);
  const visible = open ? (showAll ? messages : messages.slice(-MAX_COLLAPSED)) : [];
  const hiddenCount = messages.length - (showAll ? 0 : Math.min(messages.length, MAX_COLLAPSED));

  return (
    <div>
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 cursor-pointer mb-2"
        style={{ background: "none", border: "none", padding: 0 }}>
        <ChevronIcon open={open} />
        <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
          {label}
        </span>
      </button>
      {open && (
        <div className="space-y-1.5">
          {!showAll && hiddenCount > 0 && (
            <button onClick={() => setShowAll(true)}
              className="text-[11px] cursor-pointer"
              style={{ color: "var(--accent)", background: "none", border: "none", padding: "2px 12px" }}>
              Show {hiddenCount} earlier message{hiddenCount !== 1 ? "s" : ""}
            </button>
          )}
          {visible.map((m, i) => (
            <MessageCard key={i} role={m.role} content={m.content} toolCalls={m.tool_calls} toolCallId={m.tool_call_id} />
          ))}
        </div>
      )}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════
// Message card — the core building block
// ═════════════════════════════════════════════════════════════════════
function MessageCard({ role, content, toolCalls, toolCallId }: {
  role: string;
  content: string;
  toolCalls?: { name: string; arguments: string }[];
  toolCallId?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const rs = roleStyle(role);
  const isLong = content.length > 200;
  const preview = isLong && !expanded ? trunc(content, 200) : content;
  const isEmpty = !content && !toolCalls?.length;

  return (
    <div className="rounded" style={{ background: rs.bg, borderLeft: `3px solid ${rs.border}` }}>
      {/* Header row */}
      <div className="flex items-center gap-2 px-3 py-1.5">
        <span className="text-[10px] font-bold uppercase tracking-wider leading-none" style={{ color: rs.fg }}>
          {rs.label}
        </span>
        {toolCallId && (
          <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
            {toolCallId.slice(0, 12)}\u2026
          </span>
        )}
        {toolCalls && toolCalls.length > 0 && (
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
            calls: {toolCalls.map((tc) => tc.name).join(", ")}
          </span>
        )}
        <div className="flex-1" />
        {(isLong || toolCalls?.length) && (
          <button onClick={() => setExpanded(!expanded)}
            className="text-[11px] cursor-pointer font-medium"
            style={{ color: "var(--accent)", background: "none", border: "none", padding: 0 }}>
            {expanded ? "Collapse" : "Expand"}
          </button>
        )}
      </div>

      {/* Content */}
      {!isEmpty && (
        <div className="px-3 pb-2">
          {content && (
            <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words font-[inherit] m-0"
              style={{ color: role === "thinking" ? "var(--text-muted)" : "var(--text-secondary)" }}>
              {preview}
            </pre>
          )}

          {/* Expanded: show tool call details */}
          {expanded && toolCalls && toolCalls.length > 0 && (
            <div className="mt-2 space-y-1.5">
              {toolCalls.map((tc, i) => (
                <div key={i} className="rounded p-2" style={{ background: "var(--bg-secondary)" }}>
                  <code className="text-[11px] font-semibold" style={{ color: "var(--accent)" }}>{tc.name}</code>
                  <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words font-mono mt-1 m-0 max-h-32 overflow-auto"
                    style={{ color: "var(--text-muted)" }}>
                    {prettyJson(tc.arguments)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {isEmpty && (
        <div className="px-3 pb-2 text-[11px] italic" style={{ color: "var(--text-muted)" }}>(empty)</div>
      )}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════
// Tool call card — for output tool calls + results
// ═════════════════════════════════════════════════════════════════════
function ToolCallCard({ name, args, result }: { name: string; args: string; result?: string }) {
  const [open, setOpen] = useState(false);
  const rs = roleStyle("tool");

  // Parse edit_file for diff view
  const isEdit = name === "edit_file";
  let editParsed: { path?: string; old_string?: string; new_string?: string } | null = null;
  if (isEdit) {
    try { editParsed = JSON.parse(args); } catch { /* fall through */ }
  }
  const showDiff = isEdit && editParsed?.old_string != null && editParsed?.new_string != null;

  return (
    <div className="rounded" style={{ background: rs.bg, borderLeft: `3px solid ${rs.border}` }}>
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-1.5 cursor-pointer text-left"
        style={{ background: "none", border: "none" }}>
        <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: rs.fg }}>CALL</span>
        <code className="text-[11px] font-semibold" style={{ color: "var(--accent)" }}>{name}</code>
        {isEdit && editParsed?.path && (
          <span className="text-[11px] font-mono truncate" style={{ color: "var(--text-muted)" }}>{editParsed.path}</span>
        )}
        {result !== undefined && !open && !isEdit && (
          <>
            <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>&rarr;</span>
            <span className="text-[11px] truncate flex-1 min-w-0" style={{ color: "var(--text-secondary)" }}>
              {trunc(result, 80)}
            </span>
          </>
        )}
        <div className="flex-1" />
        {result !== undefined && (
          <span className="text-[11px] px-1.5 py-0.5 rounded"
            style={{
              background: result.startsWith("Error") ? "color-mix(in srgb, var(--error) 12%, transparent)" : "color-mix(in srgb, var(--success) 12%, transparent)",
              color: result.startsWith("Error") ? "var(--error)" : "var(--success)",
            }}>
            {result.startsWith("Error") ? "failed" : "ok"}
          </span>
        )}
        <span className="text-[11px] font-medium" style={{ color: "var(--accent)" }}>{open ? "Collapse" : "Expand"}</span>
      </button>

      {open && (
        <div className="px-3 pb-2.5 space-y-2">
          {showDiff ? (
            <DiffView
              path={editParsed!.path || ""}
              oldStr={editParsed!.old_string!}
              newStr={editParsed!.new_string!}
            />
          ) : (
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Arguments</div>
              <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words p-2 rounded overflow-auto max-h-52 font-mono m-0"
                style={{ background: "var(--bg-primary)", color: "var(--text-secondary)" }}>
                {prettyJson(args)}
              </pre>
            </div>
          )}
          {result !== undefined && (
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Result</div>
              <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words p-2 rounded overflow-auto max-h-52 font-mono m-0"
                style={{ background: "var(--bg-primary)", color: "var(--text-secondary)" }}>
                {result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

