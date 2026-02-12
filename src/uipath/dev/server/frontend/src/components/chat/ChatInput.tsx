import { useState, type KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSend, disabled, placeholder }: Props) {
  const [text, setText] = useState("");

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = !disabled && text.trim().length > 0;

  return (
    <div
      className="flex items-center gap-2 px-3 py-2 border-t"
      style={{ borderColor: "var(--border)" }}
    >
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder ?? "Message..."}
        className="flex-1 bg-transparent text-xs py-1 focus:outline-none disabled:opacity-40 placeholder:text-[var(--text-muted)]"
        style={{ color: "var(--text-primary)" }}
      />
      <button
        onClick={handleSubmit}
        disabled={!canSend}
        className="text-[10px] uppercase tracking-wider font-semibold px-2 py-1 rounded transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
        style={{
          color: canSend ? "var(--accent)" : "var(--text-muted)",
          background: "transparent",
        }}
        onMouseEnter={(e) => {
          if (canSend) {
            e.currentTarget.style.background = "color-mix(in srgb, var(--accent) 10%, transparent)";
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
        }}
      >
        Send
      </button>
    </div>
  );
}
