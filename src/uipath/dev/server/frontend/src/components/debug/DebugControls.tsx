import { useRunStore } from "../../store/useRunStore";
import type { WsClient } from "../../api/websocket";

interface Props {
  runId: string;
  status: string;
  ws: WsClient;
  breakpointNode?: string | null;
}

export default function DebugControls({ runId, status, ws, breakpointNode }: Props) {
  const isSuspended = status === "suspended";

  // Sync breakpoints to server before sending a debug command to avoid race conditions
  const syncBreakpointsThenSend = (command: "step" | "continue" | "stop") => {
    const bpMap = useRunStore.getState().breakpoints[runId] ?? {};
    ws.setBreakpoints(runId, Object.keys(bpMap));
    if (command === "step") ws.debugStep(runId);
    else if (command === "continue") ws.debugContinue(runId);
    else ws.debugStop(runId);
  };

  return (
    <div
      className="flex items-center gap-1 px-4 py-2.5 border-b shrink-0"
      style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
    >
      <span className="text-[10px] uppercase tracking-wider font-semibold mr-1" style={{ color: "var(--text-muted)" }}>
        Debug
      </span>
      <DebugBtn label="Step" onClick={() => syncBreakpointsThenSend("step")} disabled={!isSuspended} color="var(--info)" active={isSuspended} />
      <DebugBtn label="Continue" onClick={() => syncBreakpointsThenSend("continue")} disabled={!isSuspended} color="var(--success)" active={isSuspended} />
      <DebugBtn label="Stop" onClick={() => syncBreakpointsThenSend("stop")} disabled={!isSuspended} color="var(--error)" active={isSuspended} />
      <span className="text-[10px] ml-auto truncate" style={{ color: isSuspended ? "var(--accent)" : "var(--text-muted)" }}>
        {isSuspended
          ? breakpointNode
            ? `Paused at ${breakpointNode}`
            : "Paused"
          : status}
      </span>
    </div>
  );
}

function DebugBtn({ label, onClick, disabled, color, active }: {
  label: string; onClick: () => void; disabled: boolean; color: string; active: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="px-2.5 py-0.5 h-5 text-[10px] uppercase tracking-wider font-semibold rounded transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
      style={{
        color: active ? color : "var(--text-muted)",
        background: active ? `color-mix(in srgb, ${color} 10%, transparent)` : "transparent",
      }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.background = `color-mix(in srgb, ${color} 20%, transparent)`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = active ? `color-mix(in srgb, ${color} 10%, transparent)` : "transparent";
      }}
    >
      {label}
    </button>
  );
}
