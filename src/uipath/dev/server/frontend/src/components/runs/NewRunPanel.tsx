import { useEffect, useState } from "react";
import { useRunStore } from "../../store/useRunStore";
import { useHashRoute } from "../../hooks/useHashRoute";
import { getEntrypointSchema } from "../../api/client";

export default function NewRunPanel() {
  const { navigate } = useHashRoute();
  const entrypoints = useRunStore((s) => s.entrypoints);
  const [selectedEp, setSelectedEp] = useState("");
  const [chatSupported, setChatSupported] = useState(true);
  const [entrypointError, setEntrypointError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedEp && entrypoints.length > 0) {
      setSelectedEp(entrypoints[0]);
    }
  }, [entrypoints, selectedEp]);

  useEffect(() => {
    if (!selectedEp) return;
    setChatSupported(true);
    setEntrypointError(null);
    getEntrypointSchema(selectedEp)
      .then((schema) => {
        const props = (schema.input as any)?.properties;
        setChatSupported(!!props?.messages);
      })
      .catch((err: any) => {
        const detail = err.detail || {};
        setEntrypointError(
          detail.error || detail.message || `Failed to load entrypoint "${selectedEp}"`
        );
      });
  }, [selectedEp]);

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
              style={{ background: entrypointError ? "var(--error)" : "var(--accent)" }}
            />
            <span
              className="text-xs uppercase tracking-widest font-semibold"
              style={{ color: "var(--text-muted)" }}
            >
              New Run
            </span>
          </div>
          {!entrypointError && (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              {entrypoints.length > 1 ? "Select an entrypoint and choose a mode" : "Choose a mode"}
            </p>
          )}
        </div>

        {/* Entrypoint */}
        {entrypoints.length > 1 && (
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
              {entrypoints.map((ep) => (
                <option key={ep} value={ep}>
                  {ep}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Mode cards or error */}
        {entrypointError ? (
          <div
            className="rounded-md border overflow-hidden"
            style={{
              borderColor: "color-mix(in srgb, var(--error) 25%, var(--border))",
              background: "var(--bg-secondary)",
            }}
          >
            <div
              className="px-3 py-2 flex items-center gap-2"
              style={{
                borderBottom: "1px solid color-mix(in srgb, var(--error) 15%, var(--border))",
                background: "color-mix(in srgb, var(--error) 4%, var(--bg-secondary))",
              }}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
                <path
                  d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM7.25 4.75h1.5v4h-1.5v-4zm.75 6.75a.75.75 0 110-1.5.75.75 0 010 1.5z"
                  fill="var(--error)"
                />
              </svg>
              <span className="text-[11px] font-medium" style={{ color: "var(--error)" }}>
                Failed to load entrypoint
              </span>
            </div>
            <div className="overflow-auto max-h-48 p-3">
              <pre
                className="text-[11px] font-mono whitespace-pre-wrap break-words leading-relaxed m-0"
                style={{ color: "var(--text-muted)" }}
              >
                {entrypointError}
              </pre>
            </div>
          </div>
        ) : (
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
              description={
                !chatSupported
                  ? "Requires a \"messages\" property in the input schema."
                  : "Interactive chat session. Send messages and receive responses in real time."
              }
              icon={<ChatIcon />}
              color="var(--accent)"
              onClick={() => handleModeSelect("chat")}
              disabled={!selectedEp || !chatSupported}
            />
          </div>
        )}
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
      <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
        {description}
      </p>
    </button>
  );
}

function BoltIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 26 26" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M23.832 15.166H22.7487C22.7487 10.9735 19.3579 7.58268 15.1654 7.58268H14.082V6.20685C14.732 5.83852 15.1654 5.13435 15.1654 4.33268C15.1654 3.14102 14.2012 2.16602 12.9987 2.16602C11.7962 2.16602 10.832 3.14102 10.832 4.33268C10.832 5.13435 11.2654 5.83852 11.9154 6.20685V7.58268H10.832C6.63953 7.58268 3.2487 10.9735 3.2487 15.166H2.16536C1.56953 15.166 1.08203 15.6535 1.08203 16.2493V19.4993C1.08203 20.0952 1.56953 20.5827 2.16536 20.5827H3.2487V21.666C3.2487 22.8685 4.2237 23.8327 5.41536 23.8327H20.582C21.7845 23.8327 22.7487 22.8685 22.7487 21.666V20.5827H23.832C24.4279 20.5827 24.9154 20.0952 24.9154 19.4993V16.2493C24.9154 15.6535 24.4279 15.166 23.832 15.166ZM22.7487 18.416H20.582V21.666H5.41536V18.416H3.2487V17.3327H5.41536V15.166C5.41536 12.176 7.84203 9.74935 10.832 9.74935H15.1654C18.1554 9.74935 20.582 12.176 20.582 15.166V17.3327H22.7487V18.416ZM9.20703 14.6243L11.7637 17.181L10.4854 18.4594L9.20703 17.181L7.9287 18.4594L6.65036 17.181L9.20703 14.6243ZM16.7904 14.6243L19.347 17.181L18.0687 18.4594L16.7904 17.181L15.512 18.4594L14.2337 17.181L16.7904 14.6243Z" fill="currentColor" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 26 26" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M9.20901 13.541L11.7657 16.0977L10.4873 17.376L9.20901 16.0977L7.93068 17.376L6.65234 16.0977L9.20901 13.541ZM16.7923 13.541L19.349 16.0977L18.0707 17.376L16.7923 16.0977L15.514 17.376L14.2357 16.0977L16.7923 13.541Z" fill="currentColor" />
      <path d="M5.25 8.58398H20.75C21.3023 8.58398 21.75 9.0317 21.75 9.58398V23.5293L16.874 21.9043C16.5683 21.8024 16.248 21.751 15.9258 21.751H5.25C4.69782 21.751 4.25018 21.3031 4.25 20.751V9.58398C4.25 9.0317 4.69772 8.58398 5.25 8.58398Z" stroke="currentColor" strokeWidth="2" />
      <ellipse cx="12.9987" cy="4.33268" rx="2.16667" ry="2.16667" fill="currentColor" />
      <rect x="11.918" y="5.41602" width="2.16667" height="2.16667" fill="currentColor" />
      <path d="M1.08203 14C1.08203 13.4477 1.52975 13 2.08203 13H3.2487V18.4167H2.08203C1.52975 18.4167 1.08203 17.969 1.08203 17.4167V14Z" fill="currentColor" />
      <rect x="3.25" y="15.166" width="2.16667" height="1.08333" fill="currentColor" />
      <path d="M22.75 13H23.9167C24.4689 13 24.9167 13.4477 24.9167 14V17.4167C24.9167 17.969 24.469 18.4167 23.9167 18.4167H22.75V13Z" fill="currentColor" />
      <rect x="20.582" y="15.166" width="2.16667" height="1.08333" fill="currentColor" />
    </svg>
  );
}
