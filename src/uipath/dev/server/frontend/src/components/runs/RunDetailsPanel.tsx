import { useCallback, useRef, useState, useEffect } from "react";
import type { RunSummary } from "../../types/run";
import type { WsClient } from "../../api/websocket";
import { useRunStore } from "../../store/useRunStore";
import GraphPanel from "../graph/GraphPanel";
import TraceTree from "../traces/TraceTree";
import LogPanel from "../logs/LogPanel";
import ChatPanel from "../chat/ChatPanel";

type Tab = "details" | "traces" | "logs";

interface Props {
  run: RunSummary;
  ws: WsClient;
}

// Stable empty arrays to avoid infinite re-renders
const EMPTY_TRACES: never[] = [];
const EMPTY_LOGS: never[] = [];
const EMPTY_CHAT: never[] = [];

export default function RunDetailsPanel({ run, ws }: Props) {
  const isChatMode = run.mode === "chat";
  const [activeTab, setActiveTab] = useState<Tab>(isChatMode ? "traces" : "details");
  const [graphHeight, setGraphHeight] = useState(280);
  const [chatWidth, setChatWidth] = useState(() => {
    const saved = localStorage.getItem("chatPanelWidth");
    return saved ? parseInt(saved, 10) : 380;
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const tracesContainerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const traces = useRunStore((s) => s.traces[run.id] || EMPTY_TRACES);
  const logs = useRunStore((s) => s.logs[run.id] || EMPTY_LOGS);
  const chatMessages = useRunStore((s) => s.chatMessages[run.id] || EMPTY_CHAT);

  // Auto-switch to traces tab when entering chat mode
  useEffect(() => {
    if (isChatMode) {
      setActiveTab("traces");
    }
  }, [isChatMode, run.id]);

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;

    const startY = e.clientY;
    const startH = graphHeight;

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const container = containerRef.current;
      if (!container) return;
      const maxH = container.clientHeight - 100; // leave room for traces
      const newH = Math.max(80, Math.min(maxH, startH + (ev.clientY - startY)));
      setGraphHeight(newH);
    };

    const onUp = () => {
      dragging.current = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [graphHeight]);

  const onChatResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();

    const startX = e.clientX;
    const startW = chatWidth;

    const onMove = (ev: MouseEvent) => {
      const container = tracesContainerRef.current;
      if (!container) return;
      const maxW = container.clientWidth - 300; // leave room for traces
      const newW = Math.max(280, Math.min(maxW, startW + (startX - ev.clientX)));
      setChatWidth(newW);
    };

    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      localStorage.setItem("chatPanelWidth", String(chatWidth));
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [chatWidth]);

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "details", label: "Details" },
    { id: "traces", label: "Traces", count: traces.length },
    { id: "logs", label: "Logs", count: logs.length },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-[var(--border)] bg-[var(--bg-primary)]">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm transition-colors ${
              activeTab === tab.id
                ? "border-b-2 border-[var(--tab-active)] text-[var(--tab-text-active)]"
                : "text-[var(--tab-text)] hover:text-[var(--text-primary)]"
            }`}
          >
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className="ml-1 text-xs text-[var(--text-muted)]">({tab.count})</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "details" && <DetailsView run={run} />}
        {activeTab === "traces" && (
          <div ref={tracesContainerRef} className="flex h-full">
            {/* Main traces content */}
            <div ref={containerRef} className="flex flex-col flex-1 min-w-0">
              {/* Graph panel — resizable */}
              <div className="shrink-0" style={{ height: graphHeight }}>
                <GraphPanel entrypoint={run.entrypoint} traces={traces} />
              </div>
              {/* Drag handle */}
              <div
                onMouseDown={onResizeStart}
                className="shrink-0 h-1.5 cursor-row-resize flex items-center justify-center"
                style={{ background: "var(--border)" }}
              >
                <div
                  className="w-8 h-0.5 rounded-full"
                  style={{ background: "var(--text-muted)" }}
                />
              </div>
              {/* Trace tree */}
              <div className="flex-1 overflow-hidden">
                <TraceTree traces={traces} />
              </div>
            </div>
            {/* Chat sidebar with drag handle */}
            {isChatMode && (
              <>
                <div
                  onMouseDown={onChatResizeStart}
                  className="shrink-0 w-1.5 cursor-col-resize flex items-center justify-center hover:bg-[var(--accent)] transition-colors relative"
                  style={{ background: "var(--border)" }}
                >
                  <div className="absolute inset-0 -left-1 -right-1" />
                </div>
                <div
                  className="shrink-0 flex flex-col"
                  style={{
                    width: chatWidth,
                    background: "var(--bg-primary)",
                  }}
                >
                  <div
                    className="px-4 py-2 text-xs font-semibold uppercase border-b flex items-center gap-2"
                    style={{
                      color: "var(--text-muted)",
                      borderColor: "var(--border)",
                      background: "var(--bg-secondary)",
                    }}
                  >
                    <span style={{ color: "var(--accent)" }}>&#9679;</span>
                    Chat
                    {run.status === "running" && (
                      <span
                        className="ml-auto text-[10px] px-2 py-0.5 rounded-full"
                        style={{
                          background: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))",
                          color: "var(--warning)",
                        }}
                      >
                        Thinking...
                      </span>
                    )}
                  </div>
                  <div className="flex-1 overflow-hidden">
                    <ChatPanel
                      messages={chatMessages}
                      runId={run.id}
                      runStatus={run.status}
                      ws={ws}
                    />
                  </div>
                </div>
              </>
            )}
          </div>
        )}
        {activeTab === "logs" && <LogPanel logs={logs} />}
      </div>
    </div>
  );
}

const STATUS_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  pending: { bg: "color-mix(in srgb, var(--text-muted) 15%, var(--bg-secondary))", text: "var(--text-muted)", label: "Pending" },
  running: { bg: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))", text: "var(--warning)", label: "Running" },
  suspended: { bg: "color-mix(in srgb, var(--info) 15%, var(--bg-secondary))", text: "var(--info)", label: "Suspended" },
  completed: { bg: "color-mix(in srgb, var(--success) 15%, var(--bg-secondary))", text: "var(--success)", label: "Completed" },
  failed: { bg: "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))", text: "var(--error)", label: "Failed" },
};

const MODE_ICONS: Record<string, string> = {
  run: "\u25B6",
  debug: "\uD83D\uDC1B",
  chat: "\uD83D\uDCAC",
};

function DetailsView({ run }: { run: RunSummary }) {
  const badge = STATUS_BADGE[run.status] ?? STATUS_BADGE.pending;
  const modeIcon = MODE_ICONS[run.mode] ?? "";
  const entrypointName = run.entrypoint.split("/").pop() ?? run.entrypoint;

  return (
    <div className="p-6 overflow-y-auto h-full space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2
            className="text-lg font-semibold truncate"
            style={{ color: "var(--text-primary)" }}
          >
            {entrypointName}
          </h2>
          <div
            className="text-xs font-mono mt-1 truncate"
            style={{ color: "var(--text-muted)" }}
          >
            {run.id}
          </div>
        </div>
        <div
          className="shrink-0 px-3 py-1 rounded-full text-xs font-semibold"
          style={{ background: badge.bg, color: badge.text }}
        >
          {badge.label}
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <InfoCard label="Mode" value={`${modeIcon} ${run.mode}`} />
        <InfoCard label="Duration" value={run.duration || "--"} color="var(--warning)" />
        <InfoCard
          label="Started"
          value={run.start_time ? new Date(run.start_time).toLocaleTimeString() : "--"}
        />
        <InfoCard
          label="Ended"
          value={run.end_time ? new Date(run.end_time).toLocaleTimeString() : "--"}
        />
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Traces" value={run.trace_count} color="var(--info)" />
        <StatCard label="Logs" value={run.log_count} color="var(--warning)" />
        <StatCard label="Messages" value={run.message_count} color="var(--success)" />
      </div>

      {/* Entrypoint full path */}
      <div
        className="rounded-lg p-3 text-xs font-mono"
        style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
      >
        <div className="text-[10px] uppercase font-semibold mb-1" style={{ color: "var(--text-muted)" }}>
          Entrypoint
        </div>
        <div style={{ color: "var(--text-primary)" }}>{run.entrypoint}</div>
      </div>

      {/* Input */}
      <DataSection title="Input" color="var(--success)">
        <pre
          className="p-3 rounded-lg text-xs overflow-x-auto font-mono"
          style={{ background: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
        >
          {JSON.stringify(run.input_data, null, 2)}
        </pre>
      </DataSection>

      {/* Output */}
      {run.output_data && (
        <DataSection title="Output" color="var(--accent)">
          <pre
            className="p-3 rounded-lg text-xs overflow-x-auto font-mono"
            style={{ background: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
          >
            {typeof run.output_data === "string"
              ? run.output_data
              : JSON.stringify(run.output_data, null, 2)}
          </pre>
        </DataSection>
      )}

      {/* Error */}
      {run.error && (
        <div
          className="rounded-lg overflow-hidden"
          style={{
            border: "1px solid color-mix(in srgb, var(--error) 40%, var(--border))",
          }}
        >
          <div
            className="px-4 py-2 text-xs font-semibold flex items-center gap-2"
            style={{
              background: "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))",
              color: "var(--error)",
            }}
          >
            <span>Error</span>
            <span
              className="px-1.5 py-0.5 rounded text-[10px] font-mono"
              style={{ background: "color-mix(in srgb, var(--error) 20%, var(--bg-secondary))" }}
            >
              {run.error.code}
            </span>
          </div>
          <div className="p-4 text-xs" style={{ background: "var(--bg-secondary)" }}>
            <div className="font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
              {run.error.title}
            </div>
            <pre
              className="whitespace-pre-wrap font-mono text-[11px]"
              style={{ color: "var(--text-secondary)" }}
            >
              {run.error.detail}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

function InfoCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div
      className="rounded-lg p-3"
      style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
    >
      <div
        className="text-[10px] uppercase font-semibold mb-1"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </div>
      <div
        className="text-sm font-medium truncate"
        style={{ color: color ?? "var(--text-primary)" }}
      >
        {value}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div
      className="rounded-lg p-3 text-center"
      style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
    >
      <div className="text-xl font-bold" style={{ color }}>{value}</div>
      <div className="text-[10px] uppercase font-semibold mt-0.5" style={{ color: "var(--text-muted)" }}>
        {label}
      </div>
    </div>
  );
}

function DataSection({
  title,
  color,
  children,
}: {
  title: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-1 h-4 rounded-full" style={{ background: color }} />
        <span className="text-xs font-semibold uppercase" style={{ color }}>{title}</span>
      </div>
      {children}
    </div>
  );
}
