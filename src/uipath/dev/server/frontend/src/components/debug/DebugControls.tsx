import type { WsClient } from "../../api/websocket";

interface Props {
  runId: string;
  status: string;
  ws: WsClient;
}

export default function DebugControls({ runId, status, ws }: Props) {
  const isSuspended = status === "suspended";

  return (
    <div
      className="flex gap-2 p-2 border-b"
      style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
    >
      <button
        onClick={() => ws.debugStep(runId)}
        disabled={!isSuspended}
        className="px-3 py-1 text-xs text-white rounded transition-colors disabled:opacity-50"
        style={{ background: isSuspended ? "var(--info)" : "var(--bg-tertiary)" }}
      >
        Step
      </button>
      <button
        onClick={() => ws.debugContinue(runId)}
        disabled={!isSuspended}
        className="px-3 py-1 text-xs text-white rounded transition-colors disabled:opacity-50"
        style={{ background: isSuspended ? "var(--success)" : "var(--bg-tertiary)" }}
      >
        Continue
      </button>
      <button
        onClick={() => ws.debugStop(runId)}
        disabled={!isSuspended}
        className="px-3 py-1 text-xs text-white rounded transition-colors disabled:opacity-50"
        style={{ background: isSuspended ? "var(--error)" : "var(--bg-tertiary)" }}
      >
        Stop
      </button>
      <span className="text-xs self-center ml-2" style={{ color: "var(--text-muted)" }}>
        {isSuspended ? "Paused at breakpoint" : `Status: ${status}`}
      </span>
    </div>
  );
}
