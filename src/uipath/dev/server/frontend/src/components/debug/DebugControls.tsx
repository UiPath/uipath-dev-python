import { useRunStore } from "../../store/useRunStore";
import type { WsClient } from "../../api/websocket";

interface Props {
  runId: string;
  entrypoint: string;
  status: string;
  ws: WsClient;
  breakpointNode?: string | null;
}

export default function DebugControls({ runId, entrypoint, status, ws, breakpointNode }: Props) {
  const isSuspended = status === "suspended";

  // Sync breakpoints to server before sending a debug command to avoid race conditions
  const syncBreakpointsThenSend = (command: "step" | "continue" | "stop") => {
    const bpMap = useRunStore.getState().breakpoints[entrypoint] ?? {};
    ws.setBreakpoints(runId, Object.keys(bpMap));
    if (command === "step") ws.debugStep(runId);
    else if (command === "continue") ws.debugContinue(runId);
    else ws.debugStop(runId);
  };

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 border-b shrink-0"
      style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
    >
      <button
        onClick={() => syncBreakpointsThenSend("step")}
        disabled={!isSuspended}
        className="px-3 py-1 text-xs text-white rounded transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ background: isSuspended ? "var(--info)" : "var(--bg-tertiary)" }}
      >
        Step
      </button>
      <button
        onClick={() => syncBreakpointsThenSend("continue")}
        disabled={!isSuspended}
        className="px-3 py-1 text-xs text-white rounded transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ background: isSuspended ? "var(--success)" : "var(--bg-tertiary)" }}
      >
        Continue
      </button>
      <button
        onClick={() => syncBreakpointsThenSend("stop")}
        disabled={!isSuspended}
        className="px-3 py-1 text-xs text-white rounded transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ background: isSuspended ? "var(--error)" : "var(--bg-tertiary)" }}
      >
        Stop
      </button>
      <span className="text-xs ml-2" style={{ color: isSuspended ? "var(--warning)" : "var(--text-muted)" }}>
        {isSuspended
          ? breakpointNode
            ? `Paused at: ${breakpointNode}`
            : "Paused — click Continue to start"
          : `Status: ${status}`}
      </span>
    </div>
  );
}
