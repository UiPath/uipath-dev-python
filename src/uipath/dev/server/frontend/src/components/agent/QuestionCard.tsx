import { useState } from "react";
import { useAgentStore } from "../../store/useAgentStore";
import { getWs } from "../../store/useWebSocket";

export default function QuestionCard() {
  const activeQuestion = useAgentStore((s) => s.activeQuestion);
  const sessionId = useAgentStore((s) => s.sessionId);
  const setActiveQuestion = useAgentStore((s) => s.setActiveQuestion);
  const [customInput, setCustomInput] = useState("");

  if (!activeQuestion) return null;

  const handleAnswer = (answer: string) => {
    if (!sessionId) return;
    getWs().sendQuestionResponse(sessionId, activeQuestion.question_id, answer);
    setActiveQuestion(null);
    setCustomInput("");
  };

  const hasOptions = activeQuestion.options.length > 0;

  return (
    <div
      className="mx-3 mb-2 rounded-lg overflow-hidden"
      style={{ border: "1px solid color-mix(in srgb, var(--accent) 40%, var(--border))" }}
    >
      <div
        className="px-3 py-2"
        style={{ background: "color-mix(in srgb, var(--accent) 10%, var(--bg-secondary))" }}
      >
        <span className="text-[11px] font-semibold" style={{ color: "var(--accent)" }}>
          Question
        </span>
      </div>
      <div className="px-3 py-2" style={{ background: "var(--bg-secondary)" }}>
        <p className="text-sm mb-2" style={{ color: "var(--text-primary)" }}>
          {activeQuestion.question}
        </p>
        {hasOptions && (
          <div className="flex flex-col gap-1 mb-2">
            {activeQuestion.options.map((opt, i) => (
              <button
                key={i}
                onClick={() => handleAnswer(opt)}
                className="w-full text-left text-[13px] py-2 px-3 rounded cursor-pointer transition-colors flex items-center gap-2"
                style={{
                  background: "var(--bg-primary)",
                  border: "1px solid var(--border)",
                  borderLeft: "2px solid transparent",
                  color: "var(--text-primary)",
                  fontFamily: "var(--font-mono, ui-monospace, monospace)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderLeftColor = "var(--accent)";
                  e.currentTarget.style.background = "color-mix(in srgb, var(--accent) 8%, var(--bg-primary))";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderLeftColor = "transparent";
                  e.currentTarget.style.background = "var(--bg-primary)";
                }}
              >
                <span className="text-[11px] font-semibold shrink-0" style={{ color: "var(--text-muted)" }}>{i + 1}.</span>
                <span className="truncate">{opt}</span>
              </button>
            ))}
          </div>
        )}
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && customInput.trim()) {
                handleAnswer(customInput.trim());
              }
            }}
            placeholder={hasOptions ? "Or type a custom answer..." : "Type your answer..."}
            className="flex-1 text-sm px-2 py-1.5 rounded outline-none"
            style={{
              background: "var(--bg-primary)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
          <button
            onClick={() => {
              if (customInput.trim()) handleAnswer(customInput.trim());
            }}
            disabled={!customInput.trim()}
            className="text-xs font-semibold px-3 py-1.5 rounded cursor-pointer transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              background: "color-mix(in srgb, var(--accent) 15%, var(--bg-secondary))",
              color: "var(--accent)",
              border: "1px solid color-mix(in srgb, var(--accent) 30%, var(--border))",
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
