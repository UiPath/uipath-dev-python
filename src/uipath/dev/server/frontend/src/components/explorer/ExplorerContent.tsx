import { useCallback, useEffect, useRef, useState } from "react";
import { useCliAgentStore } from "../../store/useCliAgentStore";
import { useExplorerStore } from "../../store/useExplorerStore";
import { listCliAgents } from "../../api/cli-agent-client";
import { getWs } from "../../store/useWebSocket";
import { useHashRoute } from "../../hooks/useHashRoute";
import FileEditor from "./FileEditor";
import CliAgentTerminal from "../cli-agent/CliAgentTerminal";
import type { CliAgentEvent } from "../../store/useCliAgentStore";

function generateSessionId(): string {
  return crypto.randomUUID();
}

export default function ExplorerContent() {
  const ws = useRef(getWs()).current;
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const [terminalHeight, setTerminalHeight] = useState(250);
  const [sidebarWidth, setSidebarWidth] = useState(280);
  const [terminalCollapsed, setTerminalCollapsed] = useState(false);

  const explorerTabs = useExplorerStore((s) => s.openTabs);
  const { explorerFile } = useHashRoute();

  const {
    availableAgents,
    selectedAgentId,
    sessionId,
    status,
    exitCode,
    events,
    setAvailableAgents,
    setSelectedAgentId,
    setSessionId,
    setStatus,
    setExitCode,
    addEvent,
  } = useCliAgentStore();

  // Load available agents on mount
  useEffect(() => {
    listCliAgents().then((agents) => setAvailableAgents(agents));
  }, [setAvailableAgents]);

  const installedAgents = availableAgents.filter((a) => a.installed);

  const handleStart = () => {
    if (!selectedAgentId) return;
    const sid = generateSessionId();
    const agentName = installedAgents.find((a) => a.id === selectedAgentId)?.name ?? selectedAgentId;
    setSessionId(sid);
    setStatus("running");
    setExitCode(null);
    setTerminalCollapsed(false);
    ws.sendCliAgentStart(selectedAgentId, sid, 120, 40);
    addEvent({ type: "session", timestamp: Date.now(), agentName, action: "started" });
  };

  const handleStop = () => {
    if (sessionId) {
      const agentName = installedAgents.find((a) => a.id === selectedAgentId)?.name ?? selectedAgentId ?? "Unknown";
      ws.sendCliAgentStop(sessionId);
      addEvent({ type: "session", timestamp: Date.now(), agentName, action: "stopped" });
      setStatus("idle");
      setSessionId(null);
    }
  };

  // --- Terminal panel row resize ---
  const onTerminalResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    dragging.current = true;

    const startY = "touches" in e ? e.touches[0].clientY : e.clientY;
    const startH = terminalHeight;

    const onMove = (ev: MouseEvent | TouchEvent) => {
      if (!dragging.current) return;
      const container = containerRef.current;
      if (!container) return;
      const clientY = "touches" in ev ? ev.touches[0].clientY : ev.clientY;
      const maxH = container.clientHeight - 100;
      // Dragging up increases terminal height
      const newH = Math.max(100, Math.min(maxH, startH - (clientY - startY)));
      setTerminalHeight(newH);
    };

    const onUp = () => {
      dragging.current = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend", onUp);
  }, [terminalHeight]);

  // --- Sidebar col resize ---
  const onSidebarResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();

    const startX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const startW = sidebarWidth;

    const onMove = (ev: MouseEvent | TouchEvent) => {
      const clientX = "touches" in ev ? ev.touches[0].clientX : ev.clientX;
      const newW = Math.max(180, Math.min(500, startW - (clientX - startX)));
      setSidebarWidth(newW);
    };

    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend", onUp);
  }, [sidebarWidth]);

  const hasEditorContent = explorerTabs.length > 0 || !!explorerFile;

  return (
    <div className="flex h-full">
      {/* Left: editor + terminal */}
      <div ref={containerRef} className="flex flex-col flex-1 min-w-0">
        {/* File editor */}
        <div className="flex-1 overflow-hidden min-h-0">
          {hasEditorContent ? (
            <FileEditor />
          ) : (
            <div className="flex items-center justify-center h-full text-[var(--text-muted)]">
              Select a file to view
            </div>
          )}
        </div>

        {/* Drag handle */}
        {!terminalCollapsed && (
          <div
            onMouseDown={onTerminalResizeStart}
            onTouchStart={onTerminalResizeStart}
            className="shrink-0 drag-handle-row"
          />
        )}

        {/* Terminal panel */}
        <div
          className="shrink-0 flex flex-col overflow-hidden"
          style={{
            height: terminalCollapsed ? 32 : terminalHeight,
            borderTop: "1px solid var(--border)",
            background: "var(--bg-primary)",
          }}
        >
          {/* Terminal header */}
          <div
            className="shrink-0 flex items-center gap-2 px-3"
            style={{
              height: 32,
              borderBottom: terminalCollapsed ? "none" : "1px solid var(--border)",
              background: "var(--bg-secondary)",
            }}
          >
            <button
              onClick={() => setTerminalCollapsed(!terminalCollapsed)}
              className="shrink-0 flex items-center justify-center"
              style={{ width: 18, height: 18, border: "none", background: "none", color: "var(--text-muted)", cursor: "pointer" }}
            >
              <svg
                width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                style={{ transform: terminalCollapsed ? "rotate(0deg)" : "rotate(180deg)", transition: "transform 0.15s" }}
              >
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>

            <span className="text-[11px] uppercase tracking-wider font-semibold shrink-0" style={{ color: "var(--text-muted)" }}>
              Terminal
            </span>

            <select
              value={selectedAgentId ?? ""}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              disabled={status === "running"}
              style={{
                fontSize: 11,
                padding: "2px 4px",
                borderRadius: 4,
                border: "1px solid var(--border)",
                background: "var(--bg-primary)",
                color: "var(--text-primary)",
                cursor: status === "running" ? "not-allowed" : "pointer",
                opacity: status === "running" ? 0.6 : 1,
                maxWidth: 160,
              }}
            >
              {installedAgents.length === 0 && <option value="">No agents found</option>}
              {installedAgents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>

            {status === "idle" || status === "exited" ? (
              <button
                onClick={handleStart}
                disabled={!selectedAgentId || installedAgents.length === 0}
                style={{
                  fontSize: 10,
                  padding: "2px 8px",
                  borderRadius: 4,
                  border: "none",
                  background: selectedAgentId ? "var(--accent)" : "var(--bg-primary)",
                  color: selectedAgentId ? "#fff" : "var(--text-muted)",
                  cursor: selectedAgentId ? "pointer" : "not-allowed",
                  fontWeight: 500,
                }}
              >
                {status === "exited" ? "Restart" : "Start"}
              </button>
            ) : (
              <button
                onClick={handleStop}
                style={{
                  fontSize: 10,
                  padding: "2px 8px",
                  borderRadius: 4,
                  border: "none",
                  background: "#ef4444",
                  color: "#fff",
                  cursor: "pointer",
                  fontWeight: 500,
                }}
              >
                Stop
              </button>
            )}

            {/* Status dot */}
            <span
              className="ml-auto"
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background:
                  status === "running" ? "#4ade80"
                    : status === "exited" ? "#ef4444"
                      : "var(--text-muted)",
              }}
            />
          </div>

          {/* Terminal body */}
          {!terminalCollapsed && (
            <div className="flex-1 min-h-0">
              {sessionId && status === "running" ? (
                <CliAgentTerminal sessionId={sessionId} />
              ) : (
                <div className="flex items-center justify-center h-full" style={{ color: "var(--text-muted)" }}>
                  <p className="text-xs">
                    {installedAgents.length === 0
                      ? "No CLI agents detected. Install Claude Code, Codex, or GitHub Copilot CLI."
                      : status === "exited"
                        ? `Process exited${exitCode !== null ? ` (code ${exitCode})` : ""}. Click Restart.`
                        : "Select an agent and click Start."}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Sidebar drag handle */}
      <div
        onMouseDown={onSidebarResizeStart}
        onTouchStart={onSidebarResizeStart}
        className="shrink-0 drag-handle-col"
      />

      {/* Events sidebar */}
      <div
        className="shrink-0 flex flex-col"
        style={{ width: sidebarWidth, background: "var(--bg-primary)", borderLeft: "1px solid var(--border)" }}
      >
        <div
          className="shrink-0 flex items-center px-3 h-10 border-b"
          style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
        >
          <span className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: "var(--text-muted)" }}>
            Events
          </span>
          <span className="ml-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
            {events.length > 0 && events.length}
          </span>
        </div>
        <div className="flex-1 overflow-y-auto">
          {events.length === 0 ? (
            <div className="flex items-center justify-center h-full" style={{ color: "var(--text-muted)" }}>
              <p className="text-xs">No events yet</p>
            </div>
          ) : (
            <div className="py-1">
              {events.map((ev, i) => (
                <EventRow key={i} event={ev} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Shared event row: dot + label + detail + timestamp. Click to expand children. */
function EventRowShell({ dot, label, detail, time, children }: {
  dot: string;
  label: string;
  detail?: string;
  time: string;
  children?: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const expandable = !!children;

  return (
    <div
      className="px-3 py-2"
      style={{ borderBottom: "1px solid var(--border)", cursor: expandable ? "pointer" : undefined }}
      onClick={expandable ? () => setExpanded(!expanded) : undefined}
    >
      <div className="flex items-center gap-2">
        <span className="shrink-0" style={{ width: 6, height: 6, borderRadius: "50%", background: dot }} />
        <span className="text-xs font-medium truncate" style={{ color: "var(--text-primary)" }}>{label}</span>
        {detail && (
          <span className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{detail}</span>
        )}
        <span className="text-xs ml-auto shrink-0" style={{ color: "var(--text-muted)" }}>{time}</span>
      </div>
      {expanded && children}
    </div>
  );
}

function EventRow({ event }: { event: CliAgentEvent }) {
  const timeStr = new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  if (event.type === "mcp_tool_call") {
    const hasArgs = Object.keys(event.args).length > 0;
    return (
      <EventRowShell dot="#a78bfa" label={event.tool} time={timeStr}>
        {hasArgs && (
          <div className="mt-1" style={{ marginLeft: 14 }}>
            {Object.entries(event.args).map(([k, v]) => (
              <div key={k} className="text-xs truncate" style={{ color: "var(--text-muted)" }}>
                {k}={JSON.stringify(v)}
              </div>
            ))}
          </div>
        )}
      </EventRowShell>
    );
  }

  if (event.type === "run_lifecycle") {
    const dot =
      event.status === "running" ? "#facc15"
        : event.status === "completed" ? "#4ade80"
          : event.status === "failed" ? "#ef4444"
            : "var(--text-muted)";
    return <EventRowShell dot={dot} label={event.entrypoint} detail={event.status} time={timeStr} />;
  }

  if (event.type === "files_changed") {
    const label = `${event.files.length} file${event.files.length !== 1 ? "s" : ""} changed`;

    return (
      <EventRowShell dot="#60a5fa" label={label} time={timeStr}>
        <div className="mt-1" style={{ marginLeft: 14 }}>
          {event.files.map((f) => (
            <div key={f} className="text-xs truncate" style={{ color: "var(--text-primary)" }}>{f}</div>
          ))}
        </div>
      </EventRowShell>
    );
  }

  // session event
  const dot =
    event.action === "started" ? "#4ade80"
      : event.action === "exited" ? "#ef4444"
        : "var(--text-muted)";
  const detail = event.action + (event.action === "exited" && event.exitCode !== undefined ? ` (${event.exitCode})` : "");
  return <EventRowShell dot={dot} label={event.agentName} detail={detail} time={timeStr} />;
}
