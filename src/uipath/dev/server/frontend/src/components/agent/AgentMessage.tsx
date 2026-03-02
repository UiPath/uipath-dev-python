import { useState } from "react";
import Markdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import type { AgentMessage as AgentMessageType, AgentToolCall } from "../../types/agent";
import { useAgentStore } from "../../store/useAgentStore";
import { getWs } from "../../store/useWebSocket";
import { getAgentSessionDiagnostics } from "../../api/agent-client";
import { DiffView } from "./DiffView";

interface Props {
  message: AgentMessageType;
}

const ROLE_CONFIG: Record<string, { label: string; color: string }> = {
  user: { label: "You", color: "var(--info)" },
  assistant: { label: "AI", color: "var(--success)" },
  tool: { label: "Tool", color: "var(--warning)" },
  plan: { label: "Plan", color: "var(--accent)" },
  thinking: { label: "Reasoning", color: "var(--text-muted)" },
};

function ThinkingCard({ message }: Props) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="py-1.5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 mb-0.5 cursor-pointer"
        style={{ background: "none", border: "none", padding: 0 }}
      >
        <div className="w-2 h-2 rounded-full" style={{ background: "var(--text-muted)", opacity: 0.5 }} />
        <span className="text-[11px] font-semibold" style={{ color: "var(--text-muted)" }}>Reasoning</span>
        <svg
          width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"
          style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.15s", marginLeft: 2 }}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {expanded && (
        <div
          className="text-[12px] leading-relaxed pl-2.5 max-w-prose whitespace-pre-wrap"
          style={{ color: "var(--text-muted)", fontStyle: "italic" }}
        >
          {message.content}
        </div>
      )}
    </div>
  );
}

function PlanCard({ message }: Props) {
  const items = message.planItems ?? [];
  return (
    <div className="py-1.5">
      <div className="flex items-center gap-1.5 mb-0.5">
        <div className="w-2 h-2 rounded-full" style={{ background: "var(--accent)" }} />
        <span className="text-[11px] font-semibold" style={{ color: "var(--accent)" }}>Plan</span>
      </div>
      <div className="pl-2.5 space-y-1 mt-1">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            {item.status === "completed" ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2.5" strokeLinecap="round"><path d="M20 6L9 17l-5-5" /></svg>
            ) : item.status === "in_progress" ? (
              <span className="w-3.5 h-3.5 flex items-center justify-center">
                <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: "var(--accent)" }} />
              </span>
            ) : (
              <span className="w-3.5 h-3.5 flex items-center justify-center">
                <span className="w-2 h-2 rounded-full" style={{ background: "var(--text-muted)", opacity: 0.4 }} />
              </span>
            )}
            <span style={{ color: item.status === "completed" ? "var(--text-muted)" : "var(--text-primary)", textDecoration: item.status === "completed" ? "line-through" : "none" }}>
              {item.title}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function isEditFileDiff(tc: AgentToolCall): { path?: string; old_string: string; new_string: string } | null {
  if (tc.tool !== "edit_file" || !tc.args) return null;
  const a = tc.args as Record<string, unknown>;
  if (typeof a.old_string === "string" && typeof a.new_string === "string") {
    return { path: a.file_path as string | undefined, old_string: a.old_string, new_string: a.new_string };
  }
  return null;
}

function ToolApprovalCard({ tc }: { tc: AgentToolCall }) {
  const handleApproval = (approved: boolean) => {
    if (!tc.tool_call_id) return;
    const sessionId = useAgentStore.getState().sessionId;
    if (!sessionId) return;
    useAgentStore.getState().resolveToolApproval(tc.tool_call_id, approved);
    getWs().sendToolApproval(sessionId, tc.tool_call_id, approved);
  };

  const diff = isEditFileDiff(tc);

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ border: "1px solid color-mix(in srgb, var(--warning) 40%, var(--border))" }}
    >
      <div
        className="px-3 py-2 flex items-center gap-2"
        style={{ background: "color-mix(in srgb, var(--warning) 10%, var(--bg-secondary))" }}
      >
        <span className="text-[11px] font-semibold" style={{ color: "var(--warning)" }}>
          Action Required
        </span>
        <span
          className="text-[11px] font-mono px-1.5 py-0.5 rounded"
          style={{
            background: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))",
            color: "var(--text-primary)",
          }}
        >
          {tc.tool}
        </span>
        {diff?.path && (
          <span className="text-[11px] font-mono truncate" style={{ color: "var(--text-muted)" }}>
            {diff.path}
          </span>
        )}
      </div>

      {diff ? (
        <div className="px-3 py-2" style={{ background: "var(--bg-secondary)" }}>
          <DiffView path={diff.path} oldStr={diff.old_string} newStr={diff.new_string} />
        </div>
      ) : tc.args != null ? (
        <pre
          className="px-3 py-2 text-[11px] font-mono whitespace-pre-wrap break-words overflow-y-auto leading-normal"
          style={{ background: "var(--bg-secondary)", color: "var(--text-secondary)", maxHeight: 200 }}
        >
          {JSON.stringify(tc.args, null, 2)}
        </pre>
      ) : null}

      <div
        className="flex items-center gap-2 px-3 py-2"
        style={{ background: "var(--bg-secondary)", borderTop: "1px solid var(--border)" }}
      >
        <button
          onClick={() => handleApproval(true)}
          className="text-xs font-semibold px-3 py-1.5 rounded cursor-pointer transition-colors"
          style={{
            background: "color-mix(in srgb, var(--success) 15%, var(--bg-secondary))",
            color: "var(--success)",
            border: "1px solid color-mix(in srgb, var(--success) 30%, var(--border))",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "color-mix(in srgb, var(--success) 25%, var(--bg-secondary))"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "color-mix(in srgb, var(--success) 15%, var(--bg-secondary))"; }}
        >
          Approve
        </button>
        <button
          onClick={() => handleApproval(false)}
          className="text-xs font-semibold px-3 py-1.5 rounded cursor-pointer transition-colors"
          style={{
            background: "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))",
            color: "var(--error)",
            border: "1px solid color-mix(in srgb, var(--error) 30%, var(--border))",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "color-mix(in srgb, var(--error) 25%, var(--bg-secondary))"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))"; }}
        >
          Reject
        </button>
      </div>
    </div>
  );
}

function ToolChip({ tc, active, onClick }: { tc: AgentToolCall; active: boolean; onClick: () => void }) {
  const isDenied = tc.status === "denied";
  const hasResult = tc.result !== undefined;

  const statusColor = isDenied
    ? "var(--error)"
    : hasResult
      ? tc.is_error ? "var(--error)" : "var(--success)"
      : "var(--text-muted)";

  const statusIcon = isDenied ? "\u2717" : hasResult ? (tc.is_error ? "\u2717" : "\u2713") : "\u2022";

  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded cursor-pointer transition-all"
      style={{
        background: active ? "var(--bg-secondary)" : "var(--bg-primary)",
        border: active ? "1px solid var(--text-muted)" : "1px solid var(--border)",
        color: statusColor,
      }}
    >
      {statusIcon} {tc.tool}
      {isDenied && <span className="ml-1 text-[10px] uppercase">Denied</span>}
    </button>
  );
}

function ToolDetailPanel({ tc }: { tc: AgentToolCall }) {
  const hasResult = tc.result !== undefined;
  const hasArgs = tc.args != null && Object.keys(tc.args).length > 0;
  const diff = isEditFileDiff(tc);

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-1.5"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <span className="text-[11px] font-mono font-semibold" style={{ color: "var(--text-primary)" }}>
          {tc.tool}
        </span>
        {diff?.path && (
          <span className="text-[11px] font-mono truncate" style={{ color: "var(--text-muted)" }}>{diff.path}</span>
        )}
        {tc.is_error && (
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded" style={{ background: "color-mix(in srgb, var(--error) 15%, transparent)", color: "var(--error)" }}>
            Error
          </span>
        )}
      </div>

      {/* Args + Result stacked */}
      <div className="flex flex-col gap-0">
        {diff ? (
          <div className="px-3 py-2" style={{ borderBottom: hasResult ? "1px solid var(--border)" : "none" }}>
            <DiffView path={diff.path} oldStr={diff.old_string} newStr={diff.new_string} />
          </div>
        ) : hasArgs ? (
          <div style={{ borderBottom: hasResult ? "1px solid var(--border)" : "none" }}>
            <div className="px-3 pt-1.5 pb-0.5">
              <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: "var(--text-muted)" }}>Input</span>
            </div>
            <pre className="px-3 pb-2 text-[11px] font-mono whitespace-pre-wrap break-words overflow-y-auto leading-relaxed" style={{ color: "var(--text-secondary)", maxHeight: 160 }}>
              {JSON.stringify(tc.args, null, 2)}
            </pre>
          </div>
        ) : null}
        {hasResult && (
          <div>
            <div className="px-3 pt-1.5 pb-0.5">
              <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: tc.is_error ? "var(--error)" : "var(--text-muted)" }}>
                Output
              </span>
            </div>
            <pre className="px-3 pb-2 text-[11px] font-mono whitespace-pre-wrap break-words overflow-y-auto leading-relaxed" style={{ color: tc.is_error ? "var(--error)" : "var(--text-secondary)", maxHeight: 240 }}>
              {tc.result}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

const VISIBLE_TOOL_CALLS = 3;

function ToolCard({ message }: Props) {
  const calls = message.toolCalls ?? (message.toolCall ? [message.toolCall] : []);
  const [showAll, setShowAll] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  if (calls.length === 0) return null;

  // Check if any call is pending approval — show approval card instead
  const pendingCall = calls.find((tc) => tc.status === "pending");
  if (pendingCall) {
    return (
      <div className="py-1.5 pl-2.5">
        <ToolApprovalCard tc={pendingCall} />
      </div>
    );
  }

  const hiddenCount = calls.length - VISIBLE_TOOL_CALLS;
  const shouldCollapse = hiddenCount > 0 && !showAll;
  const visibleCalls = shouldCollapse ? calls.slice(-VISIBLE_TOOL_CALLS) : calls;
  const indexOffset = shouldCollapse ? hiddenCount : 0;

  return (
    <div className="py-1.5">
      <div className="flex items-center gap-1.5 mb-0.5">
        <div className="w-2 h-2 rounded-full" style={{ background: "var(--warning)" }} />
        <span className="text-[11px] font-semibold" style={{ color: "var(--warning)" }}>
          {calls.length === 1 ? "Tool" : `Tools (${calls.length})`}
        </span>
      </div>
      <div className="pl-2.5 space-y-1.5">
        {/* Chip row */}
        <div className="flex flex-wrap gap-1">
          {shouldCollapse && (
            <button
              onClick={() => setShowAll(true)}
              className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded cursor-pointer hover:brightness-125"
              style={{
                background: "var(--bg-primary)",
                border: "1px solid var(--border)",
                color: "var(--text-muted)",
              }}
            >
              +{hiddenCount} more
            </button>
          )}
          {visibleCalls.map((tc, i) => {
            const realIdx = i + indexOffset;
            return (
              <ToolChip
                key={realIdx}
                tc={tc}
                active={expandedIdx === realIdx}
                onClick={() => setExpandedIdx(expandedIdx === realIdx ? null : realIdx)}
              />
            );
          })}
        </div>
        {/* Detail panel below chips */}
        {expandedIdx !== null && calls[expandedIdx] && (
          <ToolDetailPanel tc={calls[expandedIdx]} />
        )}
      </div>
    </div>
  );
}

function formatDiagnostics(d: Record<string, unknown>): string {
  const total = (d.total_prompt_tokens as number) + (d.total_completion_tokens as number);
  let text = `## Agent Diagnostics
- Model: ${d.model}
- Turns: ${d.turn_count}/50 (max reached)
- Tokens: ${d.total_prompt_tokens} prompt + ${d.total_completion_tokens} completion = ${total} total
- Compactions: ${d.compaction_count}`;

  const tools = d.tool_summary as Array<{ tool: string; calls: number; errors?: number }>;
  if (tools && tools.length > 0) {
    text += "\n\n## Tool Usage";
    for (const t of tools) {
      text += `\n- ${t.tool}: ${t.calls} call${t.calls !== 1 ? "s" : ""}`;
      if (t.errors) text += ` (${t.errors} error${t.errors !== 1 ? "s" : ""})`;
    }
  }

  const tasks = d.tasks as Array<{ title: string; status: string }>;
  if (tasks && tasks.length > 0) {
    text += "\n\n## Tasks";
    for (const t of tasks) {
      text += `\n- [${t.status}] ${t.title}`;
    }
  }

  const msgs = d.last_messages as Array<{ role: string; tool?: string; content?: string }>;
  if (msgs && msgs.length > 0) {
    text += "\n\n## Last Messages";
    msgs.forEach((m, i) => {
      const label = m.tool ? `${m.role}:${m.tool}` : m.role;
      const content = m.content ? m.content.replace(/\n/g, " ") : "";
      text += `\n${i + 1}. [${label}] ${content}`;
    });
  }

  return text;
}

function CopyDiagnosticsButton() {
  const [state, setState] = useState<"idle" | "loading" | "copied">("idle");

  const handleClick = async () => {
    const sessionId = useAgentStore.getState().sessionId;
    if (!sessionId) return;
    setState("loading");
    try {
      const data = await getAgentSessionDiagnostics(sessionId);
      const text = formatDiagnostics(data);
      await navigator.clipboard.writeText(text);
      setState("copied");
      setTimeout(() => setState("idle"), 2000);
    } catch {
      setState("idle");
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={state === "loading"}
      className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded cursor-pointer hover:brightness-125 mt-1"
      style={{
        background: "var(--bg-primary)",
        border: "1px solid var(--border)",
        color: state === "copied" ? "var(--success)" : "var(--text-muted)",
      }}
    >
      {state === "copied" ? "Copied!" : state === "loading" ? "Loading..." : "Copy Diagnostics"}
    </button>
  );
}

export default function AgentMessageComponent({ message }: Props) {
  if (message.role === "thinking") return <ThinkingCard message={message} />;
  if (message.role === "plan") return <PlanCard message={message} />;
  if (message.role === "tool") return <ToolCard message={message} />;

  const roleKey = message.role === "user" ? "user" : "assistant";
  const role = ROLE_CONFIG[roleKey];

  return (
    <div className="py-1.5">
      <div className="flex items-center gap-1.5 mb-0.5">
        <div className="w-2 h-2 rounded-full" style={{ background: role.color }} />
        <span className="text-[11px] font-semibold" style={{ color: role.color }}>
          {role.label}
        </span>
      </div>
      {message.content && (
        message.role === "user" ? (
          <div
            className="text-sm leading-relaxed pl-2.5 max-w-prose"
            style={{ color: "var(--text-primary)" }}
          >
            {message.content}
          </div>
        ) : (
          <div
            className="text-sm leading-relaxed pl-2.5 max-w-prose chat-markdown"
            style={{ color: "var(--text-secondary)" }}
          >
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{message.content}</Markdown>
            {message.content.includes("Reached maximum iterations") && (
              <CopyDiagnosticsButton />
            )}
          </div>
        )
      )}
    </div>
  );
}
