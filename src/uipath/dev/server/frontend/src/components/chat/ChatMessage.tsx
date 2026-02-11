interface ChatMsg {
  message_id: string;
  role: string;
  content: string;
  tool_calls?: { name: string; has_result: boolean }[];
}

interface Props {
  message: ChatMsg;
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";
  const hasTool = message.tool_calls && message.tool_calls.length > 0;

  const roleLabel = isUser ? "You" : hasTool ? "Tool" : "AI";

  return (
    <div
      className="rounded-lg border p-3"
      style={{
        background: isUser
          ? "color-mix(in srgb, var(--info) 10%, var(--bg-secondary))"
          : hasTool
            ? "color-mix(in srgb, var(--warning) 8%, var(--bg-secondary))"
            : "var(--bg-secondary)",
        borderColor: isUser
          ? "color-mix(in srgb, var(--info) 30%, var(--border))"
          : hasTool
            ? "color-mix(in srgb, var(--warning) 30%, var(--border))"
            : "var(--border)",
      }}
    >
      <div
        className="text-xs font-semibold mb-1"
        style={{
          color: isUser
            ? "var(--info)"
            : hasTool
              ? "var(--warning)"
              : "var(--success)",
        }}
      >
        {roleLabel}
      </div>

      {message.content && (
        <div className="text-sm whitespace-pre-wrap" style={{ color: "var(--text-primary)" }}>
          {message.content}
        </div>
      )}

      {message.tool_calls?.map((tc) => (
        <div key={tc.name} className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
          {tc.has_result ? "\u2713" : "\u2699"} <strong>{tc.name}</strong>
        </div>
      ))}
    </div>
  );
}
