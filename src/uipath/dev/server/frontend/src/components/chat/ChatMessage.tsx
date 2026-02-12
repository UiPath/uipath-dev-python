import Markdown from "react-markdown";

interface ChatMsg {
  message_id: string;
  role: string;
  content: string;
  tool_calls?: { name: string; has_result: boolean }[];
}

interface Props {
  message: ChatMsg;
  onToolCallClick?: (name: string, occurrenceIndex: number) => void;
  toolCallIndices?: number[];
}

const ROLE_CONFIG: Record<string, { label: string; color: string }> = {
  user: { label: "You", color: "var(--info)" },
  tool: { label: "Tool", color: "var(--warning)" },
  assistant: { label: "AI", color: "var(--success)" },
};

export default function ChatMessage({ message, onToolCallClick, toolCallIndices }: Props) {
  const isUser = message.role === "user";
  const hasTool = message.tool_calls && message.tool_calls.length > 0;
  const roleKey = isUser ? "user" : hasTool ? "tool" : "assistant";
  const role = ROLE_CONFIG[roleKey];

  return (
    <div className="py-1.5">
      {/* Role indicator */}
      <div className="flex items-center gap-1.5 mb-0.5">
        <div
          className="w-1 h-1 rounded-full"
          style={{ background: role.color }}
        />
        <span
          className="text-[10px] uppercase tracking-wider font-semibold"
          style={{ color: role.color }}
        >
          {role.label}
        </span>
      </div>

      {/* Content */}
      {message.content && (
        isUser ? (
          <div
            className="text-xs leading-relaxed pl-2.5"
            style={{ color: "var(--text-primary)" }}
          >
            {message.content}
          </div>
        ) : (
          <div
            className="text-xs leading-relaxed pl-2.5 chat-markdown"
            style={{ color: "var(--text-secondary)" }}
          >
            <Markdown>{message.content}</Markdown>
          </div>
        )
      )}

      {/* Tool calls */}
      {message.tool_calls && message.tool_calls.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1 pl-2.5">
          {message.tool_calls.map((tc, i) => (
            <span
              key={`${tc.name}-${i}`}
              className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded cursor-pointer hover:brightness-125"
              style={{
                background: "var(--bg-primary)",
                border: "1px solid var(--border)",
                color: tc.has_result ? "var(--success)" : "var(--text-muted)",
              }}
              onClick={() => onToolCallClick?.(tc.name, toolCallIndices?.[i] ?? 0)}
            >
              {tc.has_result ? "\u2713" : "\u2022"} {tc.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
