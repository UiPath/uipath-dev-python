import { useState, type KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
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

  return (
    <div className="border-t p-3 flex gap-2" style={{ borderColor: "var(--border)" }}>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={disabled ? "Waiting for response..." : "Type your message..."}
        className="flex-1 rounded px-3 py-2 text-sm disabled:opacity-50"
        style={{
          background: "var(--input-bg)",
          border: "1px solid var(--border)",
          color: "var(--text-primary)",
        }}
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !text.trim()}
        className="px-4 py-2 text-white text-sm rounded transition-colors disabled:opacity-50"
        style={{
          background: disabled || !text.trim() ? "var(--bg-tertiary)" : "var(--accent)",
        }}
      >
        Send
      </button>
    </div>
  );
}
