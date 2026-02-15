import { useState } from "react";
import type { InterruptEvent } from "../../types/run";

interface Props {
  interrupt: InterruptEvent;
  onRespond: (data: Record<string, unknown>) => void;
}

export default function ChatInterrupt({ interrupt, onRespond }: Props) {
  const [responseText, setResponseText] = useState("");

  if (interrupt.interrupt_type === "tool_call_confirmation") {
    return (
      <div
        className="mx-3 my-2 rounded-lg overflow-hidden"
        style={{ border: "1px solid color-mix(in srgb, var(--warning) 40%, var(--border))" }}
      >
        <div
          className="px-3 py-2 flex items-center gap-2"
          style={{
            background: "color-mix(in srgb, var(--warning) 10%, var(--bg-secondary))",
          }}
        >
          <span
            className="text-[10px] uppercase tracking-wider font-semibold"
            style={{ color: "var(--warning)" }}
          >
            Action Required
          </span>
          {interrupt.tool_name && (
            <span
              className="text-[11px] font-mono px-1.5 py-0.5 rounded"
              style={{
                background: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))",
                color: "var(--text-primary)",
              }}
            >
              {interrupt.tool_name}
            </span>
          )}
        </div>
        {interrupt.input_value != null && (
          <pre
            className="px-3 py-2 text-[11px] font-mono whitespace-pre-wrap break-words overflow-y-auto leading-normal"
            style={{
              background: "var(--bg-secondary)",
              color: "var(--text-secondary)",
              maxHeight: 200,
            }}
          >
            {typeof interrupt.input_value === "string"
              ? interrupt.input_value
              : JSON.stringify(interrupt.input_value, null, 2)}
          </pre>
        )}
        <div
          className="flex items-center gap-2 px-3 py-2"
          style={{
            background: "var(--bg-secondary)",
            borderTop: "1px solid var(--border)",
          }}
        >
          <button
            onClick={() => onRespond({ approved: true })}
            className="text-[10px] uppercase tracking-wider font-semibold px-3 py-1 rounded cursor-pointer transition-colors"
            style={{
              background: "color-mix(in srgb, var(--success) 15%, var(--bg-secondary))",
              color: "var(--success)",
              border: "1px solid color-mix(in srgb, var(--success) 30%, var(--border))",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "color-mix(in srgb, var(--success) 25%, var(--bg-secondary))";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "color-mix(in srgb, var(--success) 15%, var(--bg-secondary))";
            }}
          >
            Approve
          </button>
          <button
            onClick={() => onRespond({ approved: false })}
            className="text-[10px] uppercase tracking-wider font-semibold px-3 py-1 rounded cursor-pointer transition-colors"
            style={{
              background: "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))",
              color: "var(--error)",
              border: "1px solid color-mix(in srgb, var(--error) 30%, var(--border))",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "color-mix(in srgb, var(--error) 25%, var(--bg-secondary))";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))";
            }}
          >
            Reject
          </button>
        </div>
      </div>
    );
  }

  // Generic interrupt
  return (
    <div
      className="mx-3 my-2 rounded-lg overflow-hidden"
      style={{ border: "1px solid color-mix(in srgb, var(--accent) 40%, var(--border))" }}
    >
      <div
        className="px-3 py-2"
        style={{
          background: "color-mix(in srgb, var(--accent) 10%, var(--bg-secondary))",
        }}
      >
        <span
          className="text-[10px] uppercase tracking-wider font-semibold"
          style={{ color: "var(--accent)" }}
        >
          Input Required
        </span>
      </div>
      {interrupt.content != null && (
        <div
          className="px-3 py-2 text-sm leading-relaxed"
          style={{
            background: "var(--bg-secondary)",
            color: "var(--text-secondary)",
          }}
        >
          {typeof interrupt.content === "string"
            ? interrupt.content
            : JSON.stringify(interrupt.content, null, 2)}
        </div>
      )}
      <div
        className="flex items-center gap-2 px-3 py-2"
        style={{
          background: "var(--bg-secondary)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <input
          value={responseText}
          onChange={(e) => setResponseText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && responseText.trim()) {
              e.preventDefault();
              onRespond({ response: responseText.trim() });
            }
          }}
          placeholder="Type your response..."
          className="flex-1 bg-transparent text-sm py-1 focus:outline-none placeholder:text-[var(--text-muted)]"
          style={{ color: "var(--text-primary)" }}
        />
        <button
          onClick={() => {
            if (responseText.trim()) {
              onRespond({ response: responseText.trim() });
            }
          }}
          disabled={!responseText.trim()}
          className="text-[11px] uppercase tracking-wider font-semibold px-2 py-1 rounded transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
          style={{
            color: responseText.trim() ? "var(--accent)" : "var(--text-muted)",
            background: "transparent",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
