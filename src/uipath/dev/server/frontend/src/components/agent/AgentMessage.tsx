import { useState } from "react";
import Markdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import type { AgentMessage as AgentMessageType, AgentToolCall } from "../../types/agent";
import { useAgentStore } from "../../store/useAgentStore";
import { getWs } from "../../store/useWebSocket";

interface Props {
  message: AgentMessageType;
}

const ROLE_CONFIG: Record<string, { label: string; color: string }> = {
  user: { label: "You", color: "var(--info)" },
  assistant: { label: "AI", color: "var(--success)" },
  tool: { label: "Tool", color: "var(--warning)" },
  plan: { label: "Plan", color: "var(--accent)" },
};

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

function SingleToolCall({ tc }: { tc: AgentToolCall }) {
  const isPending = tc.status === "pending";
  const isDenied = tc.status === "denied";
  const [expanded, setExpanded] = useState(false);
  const hasResult = tc.result !== undefined;

  const handleApproval = (approved: boolean) => {
    if (!tc.tool_call_id) return;
    const sessionId = useAgentStore.getState().sessionId;
    if (!sessionId) return;
    useAgentStore.getState().resolveToolApproval(tc.tool_call_id, approved);
    getWs().sendToolApproval(sessionId, tc.tool_call_id, approved);
  };

  /* ── Pending: card layout matching ChatInterrupt ── */
  if (isPending) {
    return (
      <div
        className="ml-2.5 rounded-lg overflow-hidden"
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
        </div>

        {tc.args != null && (
          <pre
            className="px-3 py-2 text-[11px] font-mono whitespace-pre-wrap break-words overflow-y-auto leading-normal"
            style={{ background: "var(--bg-secondary)", color: "var(--text-secondary)", maxHeight: 200 }}
          >
            {JSON.stringify(tc.args, null, 2)}
          </pre>
        )}

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

  /* ── Resolved / completed: compact inline style ── */
  const statusColor = isDenied
    ? "var(--error)"
    : hasResult
      ? tc.is_error
        ? "var(--error)"
        : "var(--success)"
      : "var(--text-muted)";

  const statusIcon = isDenied ? "\u2717" : hasResult ? (tc.is_error ? "\u2717" : "\u2713") : "\u2022";

  return (
    <div className="pl-2.5">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded cursor-pointer hover:brightness-125"
          style={{
            background: "var(--bg-primary)",
            border: "1px solid var(--border)",
            color: statusColor,
          }}
        >
          {statusIcon} {tc.tool}
          {isDenied && <span className="ml-1 text-[10px] uppercase">Denied</span>}
          <svg
            width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.15s", marginLeft: 2 }}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
      </div>
      {expanded && (
        <div className="mt-1.5 space-y-2">
          <div>
            <div className="text-[10px] uppercase tracking-wider mb-1 font-semibold" style={{ color: "var(--text-muted)" }}>Arguments</div>
            <pre className="text-[11px] font-mono p-2 rounded overflow-x-auto whitespace-pre-wrap" style={{ background: "var(--bg-primary)", color: "var(--text-secondary)" }}>
              {JSON.stringify(tc.args, null, 2)}
            </pre>
          </div>
          {hasResult && (
            <div>
              <div className="text-[10px] uppercase tracking-wider mb-1 font-semibold" style={{ color: tc.is_error ? "var(--error)" : "var(--text-muted)" }}>
                {tc.is_error ? "Error" : "Result"}
              </div>
              <pre className="text-[11px] font-mono p-2 rounded overflow-x-auto whitespace-pre-wrap max-h-48 overflow-y-auto" style={{ background: "var(--bg-primary)", color: tc.is_error ? "var(--error)" : "var(--text-secondary)" }}>
                {tc.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const VISIBLE_TOOL_CALLS = 3;

function ToolCard({ message }: Props) {
  const calls = message.toolCalls ?? (message.toolCall ? [message.toolCall] : []);
  const [showAll, setShowAll] = useState(false);
  if (calls.length === 0) return null;

  const hiddenCount = calls.length - VISIBLE_TOOL_CALLS;
  const shouldCollapse = hiddenCount > 0 && !showAll;
  const visibleCalls = shouldCollapse ? calls.slice(-VISIBLE_TOOL_CALLS) : calls;

  return (
    <div className="py-1.5">
      <div className="flex items-center gap-1.5 mb-0.5">
        <div className="w-2 h-2 rounded-full" style={{ background: "var(--warning)" }} />
        <span className="text-[11px] font-semibold" style={{ color: "var(--warning)" }}>
          {calls.length === 1 ? "Tool" : `Tools (${calls.length})`}
        </span>
      </div>
      <div className="space-y-1">
        {shouldCollapse && (
          <button
            onClick={() => setShowAll(true)}
            className="ml-2.5 inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded cursor-pointer hover:brightness-125"
            style={{
              background: "var(--bg-primary)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
            }}
          >
            {hiddenCount} more tool {hiddenCount === 1 ? "call" : "calls"}
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginLeft: 2 }}>
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>
        )}
        {visibleCalls.map((tc, i) => (
          <SingleToolCall key={shouldCollapse ? i + hiddenCount : i} tc={tc} />
        ))}
      </div>
    </div>
  );
}

export default function AgentMessageComponent({ message }: Props) {
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
          </div>
        )
      )}
    </div>
  );
}
