import { useCallback, useRef, useState } from "react";
import type { RunSummary } from "../../types/run";
import type { WsClient } from "../../api/websocket";
import { useRunStore } from "../../store/useRunStore";
import GraphPanel from "../graph/GraphPanel";
import TraceTree from "../traces/TraceTree";
import LogPanel from "../logs/LogPanel";
import ChatPanel from "../chat/ChatPanel";

type Tab = "traces" | "output";

interface Props {
  run: RunSummary;
  ws: WsClient;
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

// Stable empty arrays to avoid infinite re-renders
const EMPTY_TRACES: never[] = [];
const EMPTY_LOGS: never[] = [];
const EMPTY_CHAT: never[] = [];

export default function RunDetailsPanel({ run, ws, activeTab, onTabChange }: Props) {
  const isChatMode = run.mode === "chat";
  const [graphHeight, setGraphHeight] = useState(280);
  const [chatWidth, setChatWidth] = useState(() => {
    const saved = localStorage.getItem("chatPanelWidth");
    return saved ? parseInt(saved, 10) : 380;
  });
  const [outputSplit, setOutputSplit] = useState(() => {
    const saved = localStorage.getItem("outputSplitPercent");
    return saved ? parseFloat(saved) : 50;
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const tracesContainerRef = useRef<HTMLDivElement>(null);
  const outputContainerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const traces = useRunStore((s) => s.traces[run.id] || EMPTY_TRACES);
  const logs = useRunStore((s) => s.logs[run.id] || EMPTY_LOGS);
  const chatMessages = useRunStore((s) => s.chatMessages[run.id] || EMPTY_CHAT);

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

  const onOutputSplitStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();

    const startX = e.clientX;
    const startPct = outputSplit;

    const onMove = (ev: MouseEvent) => {
      const container = outputContainerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const deltaPct = ((ev.clientX - startX) / rect.width) * 100;
      const newPct = Math.max(20, Math.min(80, startPct + deltaPct));
      setOutputSplit(newPct);
    };

    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      localStorage.setItem("outputSplitPercent", String(outputSplit));
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [outputSplit]);

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "traces", label: "Trace", count: traces.length },
    { id: "output", label: "Output", count: logs.length },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-[var(--border)] bg-[var(--bg-primary)]">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
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
        {activeTab === "traces" && (
          <div ref={tracesContainerRef} className="flex h-full">
            {/* Main traces content */}
            <div ref={containerRef} className="flex flex-col flex-1 min-w-0">
              {/* Graph panel — resizable */}
              <div className="shrink-0" style={{ height: graphHeight }}>
                <GraphPanel entrypoint={run.entrypoint} traces={traces} runId={run.id} />
              </div>
              {/* Drag handle */}
              <div
                onMouseDown={onResizeStart}
                className="shrink-0 h-1.5 cursor-row-resize bg-[var(--border)] hover:bg-[var(--accent)] transition-colors relative"
              >
                <div className="absolute inset-0 -top-1 -bottom-1" />
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
                  className="shrink-0 w-1.5 cursor-col-resize bg-[var(--border)] hover:bg-[var(--accent)] transition-colors relative"
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
        {activeTab === "output" && (
          <div className="flex flex-col h-full">
            {/* Summary bar — full width */}
            <OutputSummary run={run} />
            {/* Split panels */}
            <div ref={outputContainerRef} className="flex flex-1 min-h-0">
              {/* I/O panel */}
              <div className="overflow-hidden flex flex-col pr-1" style={{ width: `${outputSplit}%` }}>
                <PanelHeader title="I/O" count={run.output_data ? 2 : 1} />
                <div className="flex-1 overflow-hidden">
                  <IOView run={run} />
                </div>
              </div>
              {/* Drag handle */}
              <div
                onMouseDown={onOutputSplitStart}
                className="shrink-0 w-1.5 cursor-col-resize bg-[var(--border)] hover:bg-[var(--accent)] transition-colors relative"
              >
                <div className="absolute inset-0 -left-1 -right-1" />
              </div>
              {/* Logs panel */}
              <div className="flex-1 overflow-hidden min-w-0 flex flex-col">
                <PanelHeader title="Logs" count={logs.length} />
                <div className="flex-1 overflow-hidden">
                  <LogPanel logs={logs} />
                </div>
              </div>
            </div>
          </div>
        )}
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

function OutputSummary({ run }: { run: RunSummary }) {
  const badge = STATUS_BADGE[run.status] ?? STATUS_BADGE.pending;
  const entrypointName = run.entrypoint.split("/").pop() ?? run.entrypoint;

  return (
    <div
      className="shrink-0 px-4 py-3 flex items-center gap-3 flex-wrap border-b"
      style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}
    >
      {/* Name + ID */}
      <div className="min-w-0 mr-2">
        <div className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
          {entrypointName}
        </div>
        <div className="text-[10px] font-mono truncate" style={{ color: "var(--text-muted)" }}>
          {run.id}
        </div>
      </div>

      {/* Status badge */}
      <div
        className="shrink-0 px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
        style={{ background: badge.bg, color: badge.text }}
      >
        {badge.label}
      </div>

      {/* Pills */}
      <Pill label="Duration" value={run.duration || "--"} color="var(--warning)" />
      <Pill
        label="Started"
        value={run.start_time ? new Date(run.start_time).toLocaleTimeString() : "--"}
      />
      <Pill
        label="Ended"
        value={run.end_time ? new Date(run.end_time).toLocaleTimeString() : "--"}
      />
      <Pill label="Traces" value={String(run.trace_count)} color="var(--info)" />
      <Pill label="Logs" value={String(run.log_count)} color="var(--warning)" />
      <Pill label="Messages" value={String(run.message_count)} color="var(--success)" />
    </div>
  );
}

function IOView({ run }: { run: RunSummary }) {
  return (
    <div className="p-4 overflow-y-auto h-full space-y-4">
      {/* Input */}
      <DataSection title="Input" color="var(--success)" copyText={JSON.stringify(run.input_data, null, 2)}>
        <pre
          className="p-3 rounded-lg text-xs overflow-x-auto font-mono"
          style={{ background: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
        >
          {JSON.stringify(run.input_data, null, 2)}
        </pre>
      </DataSection>

      {/* Output */}
      {run.output_data && (
        <DataSection
          title="Output"
          color="var(--accent)"
          copyText={typeof run.output_data === "string" ? run.output_data : JSON.stringify(run.output_data, null, 2)}
        >
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

function PanelHeader({ title, count }: { title: string; count?: number }) {
  return (
    <div
      className="shrink-0 px-3 py-1 text-[10px] uppercase font-bold tracking-wider border-b"
      style={{ color: "var(--text-muted)", borderColor: "var(--border)", background: "var(--bg-secondary)" }}
    >
      {title}
      {count !== undefined && count > 0 && (
        <span className="ml-1 font-normal">({count})</span>
      )}
    </div>
  );
}

function Pill({
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
      className="shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px]"
      style={{ background: "var(--bg-primary)", border: "1px solid var(--border)" }}
    >
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <span className="font-semibold" style={{ color: color ?? "var(--text-primary)" }}>{value}</span>
    </div>
  );
}

function DataSection({
  title,
  color,
  copyText,
  children,
}: {
  title: string;
  color: string;
  copyText?: string;
  children: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(() => {
    if (!copyText) return;
    navigator.clipboard.writeText(copyText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [copyText]);

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-1 h-4 rounded-full" style={{ background: color }} />
        <span className="text-xs font-semibold uppercase" style={{ color }}>{title}</span>
        {copyText && (
          <button
            onClick={copy}
            className="ml-auto text-[10px] cursor-pointer px-1.5 py-0.5 rounded"
            style={{
              color: copied ? "var(--success)" : "var(--text-muted)",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
            }}
          >
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </div>
      {children}
    </div>
  );
}
