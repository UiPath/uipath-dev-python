import { useState } from "react";
import Markdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import type { ChatToolCall } from "../../store/useRunStore";

interface ChatMsg {
  message_id: string;
  role: string;
  content: string;
  tool_calls?: ChatToolCall[];
}

interface Props {
  message: ChatMsg;
  onToolCallClick?: (name: string, occurrenceIndex: number) => void;
  toolCallIndices?: number[];
  onConfirmToolCall?: (toolCallId: string, approved: boolean, input?: unknown) => void;
}

const ROLE_CONFIG: Record<string, { label: string; color: string }> = {
  user: { label: "You", color: "var(--info)" },
  tool: { label: "Tool", color: "var(--warning)" },
  assistant: { label: "AI", color: "var(--success)" },
};

function ToolCallConfirmPanel({
  toolCall,
  onConfirm,
}: {
  toolCall: ChatToolCall;
  onConfirm: (approved: boolean, input?: unknown) => void;
}) {
  const initial = toolCall.input != null ? JSON.stringify(toolCall.input, null, 2) : "{}";
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = () => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(draft);
    } catch {
      setError("Invalid JSON");
      return;
    }
    setError(null);
    onConfirm(true, parsed);
  };

  return (
    <div
      className="mt-1 ml-2.5 rounded-lg overflow-hidden"
      style={{
        border: "1px solid color-mix(in srgb, var(--warning) 40%, var(--border))",
      }}
    >
      <div
        className="px-3 py-2 flex items-center gap-2"
        style={{
          background: "color-mix(in srgb, var(--warning) 10%, var(--bg-secondary))",
        }}
      >
        <span
          className="text-[11px] font-semibold"
          style={{ color: "var(--warning)" }}
        >
          Action Required
        </span>
        <span
          className="text-[11px] font-mono px-1.5 py-0.5 rounded"
          style={{
            background: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))",
            color: "var(--text-primary)",
          }}
        >
          {toolCall.name}
        </span>
      </div>
      <div
        className="px-3 py-2"
        style={{ background: "var(--bg-secondary)" }}
      >
        <textarea
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setError(null);
          }}
          rows={Math.min(10, Math.max(3, draft.split("\n").length))}
          className="w-full text-[11px] font-mono py-1 px-2 rounded focus:outline-none resize-y"
          style={{
            background: "var(--bg-primary)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
          }}
        />
        {error && (
          <p
            className="text-[11px] mt-1"
            style={{ color: "var(--error)" }}
          >
            {error}
          </p>
        )}
      </div>
      <div
        className="flex items-center gap-2 px-3 py-2"
        style={{
          background: "var(--bg-secondary)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <button
          onClick={handleApprove}
          className="text-xs font-semibold px-3 py-1.5 rounded cursor-pointer transition-colors"
          style={{
            background: "color-mix(in srgb, var(--success) 15%, var(--bg-secondary))",
            color: "var(--success)",
            border: "1px solid color-mix(in srgb, var(--success) 30%, var(--border))",
          }}
        >
          Approve
        </button>
        <button
          onClick={() => onConfirm(false)}
          className="text-xs font-semibold px-3 py-1.5 rounded cursor-pointer transition-colors"
          style={{
            background: "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))",
            color: "var(--error)",
            border: "1px solid color-mix(in srgb, var(--error) 30%, var(--border))",
          }}
        >
          Reject
        </button>
      </div>
    </div>
  );
}

export default function ChatMessage({
  message,
  onToolCallClick,
  toolCallIndices,
  onConfirmToolCall,
}: Props) {
  const isUser = message.role === "user";
  const hasTool = message.tool_calls && message.tool_calls.length > 0;
  const roleKey = isUser ? "user" : hasTool ? "tool" : "assistant";
  const role = ROLE_CONFIG[roleKey];

  return (
    <div className="py-1.5">
      <div className="flex items-center gap-1.5 mb-0.5">
        <div
          className="w-2 h-2 rounded-full"
          style={{ background: role.color }}
        />
        <span
          className="text-[11px] font-semibold"
          style={{ color: role.color }}
        >
          {role.label}
        </span>
      </div>

      {message.content && (
        isUser ? (
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

      {message.tool_calls && message.tool_calls.length > 0 && (
        <>
          <div className="flex flex-wrap gap-1 mt-1 pl-2.5">
            {message.tool_calls.map((tc, i) => {
              const rejected =
                tc.cancelled === true ||
                (tc.confirmation && !tc.confirmation.approved);
              const approved = tc.confirmation && tc.confirmation.approved;
              return (
                <span
                  key={`${tc.tool_call_id || tc.name}-${i}`}
                  className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded cursor-pointer hover:brightness-125"
                  style={{
                    background: "var(--bg-primary)",
                    border: "1px solid var(--border)",
                    color: rejected
                      ? "var(--error)"
                      : tc.has_result
                        ? "var(--success)"
                        : approved
                          ? "var(--success)"
                          : "var(--text-muted)",
                  }}
                  onClick={() => onToolCallClick?.(tc.name, toolCallIndices?.[i] ?? 0)}
                >
                  {rejected
                    ? "✗"
                    : tc.has_result || approved
                      ? "✓"
                      : "•"}{" "}
                  {tc.name}
                </span>
              );
            })}
          </div>
          {message.tool_calls
            .filter(
              (tc) =>
                tc.require_confirmation && !tc.confirmation && !tc.has_result,
            )
            .map((tc) => (
              <ToolCallConfirmPanel
                key={tc.tool_call_id}
                toolCall={tc}
                onConfirm={(approved, input) =>
                  onConfirmToolCall?.(tc.tool_call_id, approved, input)
                }
              />
            ))}
        </>
      )}
    </div>
  );
}
