import { useEffect, useState } from "react";
import { useRunStore } from "../../store/useRunStore";
import { useHashRoute } from "../../hooks/useHashRoute";

export default function NewRunPanel() {
  const { navigate } = useHashRoute();
  const entrypoints = useRunStore((s) => s.entrypoints);
  const [selectedEp, setSelectedEp] = useState("");

  useEffect(() => {
    if (!selectedEp && entrypoints.length > 0) {
      setSelectedEp(entrypoints[0]);
    }
  }, [entrypoints, selectedEp]);

  const handleModeSelect = (mode: "run" | "chat") => {
    if (!selectedEp) return;
    navigate(`#/setup/${encodeURIComponent(selectedEp)}/${mode}`);
  };

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-xl px-6">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: "var(--accent)" }}
            />
            <span
              className="text-[10px] uppercase tracking-widest font-semibold"
              style={{ color: "var(--text-muted)" }}
            >
              New Run
            </span>
          </div>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Select an entrypoint and choose a mode
          </p>
        </div>

        {/* Entrypoint */}
        <div className="mb-8">
          <label
            className="block text-[10px] uppercase tracking-wider font-semibold mb-2"
            style={{ color: "var(--text-muted)" }}
          >
            Entrypoint
          </label>
          <select
            value={selectedEp}
            onChange={(e) => setSelectedEp(e.target.value)}
            className="w-full rounded-md px-3 py-1.5 text-xs font-mono cursor-pointer appearance-auto"
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          >
            {entrypoints.length === 0 && (
              <option value="">Loading...</option>
            )}
            {entrypoints.map((ep) => (
              <option key={ep} value={ep}>
                {ep}
              </option>
            ))}
          </select>
        </div>

        {/* Mode cards */}
        <div className="grid grid-cols-2 gap-4">
          <ModeCard
            title="Autonomous"
            description="Run the agent end-to-end. Set breakpoints to pause and inspect execution."
            icon={<BoltIcon />}
            color="var(--success)"
            onClick={() => handleModeSelect("run")}
            disabled={!selectedEp}
          />
          <ModeCard
            title="Conversational"
            description="Interactive chat session. Send messages and receive responses in real time."
            icon={<ChatIcon />}
            color="var(--accent)"
            onClick={() => handleModeSelect("chat")}
            disabled={!selectedEp}
          />
        </div>
      </div>
    </div>
  );
}

function ModeCard({
  title,
  description,
  icon,
  color,
  onClick,
  disabled,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="group flex flex-col items-center text-center p-6 rounded-lg border transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
      style={{
        background: "var(--bg-secondary)",
        borderColor: "var(--border)",
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.borderColor = color;
          e.currentTarget.style.background = `color-mix(in srgb, ${color} 5%, var(--bg-secondary))`;
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "var(--border)";
        e.currentTarget.style.background = "var(--bg-secondary)";
      }}
    >
      <div
        className="mb-4 p-3 rounded-xl transition-colors"
        style={{
          background: `color-mix(in srgb, ${color} 10%, var(--bg-primary))`,
          color,
        }}
      >
        {icon}
      </div>
      <h3
        className="text-sm font-semibold mb-1.5"
        style={{ color: "var(--text-primary)" }}
      >
        {title}
      </h3>
      <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
        {description}
      </p>
    </button>
  );
}

function BoltIcon() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}
