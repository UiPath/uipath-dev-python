import { useCallback, useEffect, useRef, useState } from "react";
import type { RunSummary } from "../../types/run";
import type { WsClient } from "../../api/websocket";
import { useRunStore } from "../../store/useRunStore";
import GraphPanel from "../graph/GraphPanel";
import TraceTree from "../traces/TraceTree";
import LogPanel from "../logs/LogPanel";
import ChatPanel from "../chat/ChatPanel";
import RunEventsPanel from "./RunEventsPanel";
import JsonHighlight from "../shared/JsonHighlight";
import DebugControls from "../debug/DebugControls";

type SidebarTab = "primary" | "io" | "logs";

interface Props {
  run: RunSummary;
  ws: WsClient;
}

// Stable empty arrays to avoid infinite re-renders
const EMPTY_TRACES: never[] = [];
const EMPTY_LOGS: never[] = [];
const EMPTY_CHAT: never[] = [];
const EMPTY_STATE_EVENTS: never[] = [];

export default function RunDetailsPanel({ run, ws }: Props) {
  const isChatMode = run.mode === "chat";
  const [graphHeight, setGraphHeight] = useState(280);
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem("chatPanelWidth");
    return saved ? parseInt(saved, 10) : 380;
  });
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("primary");
  const [fitViewTrigger, setFitViewTrigger] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const outerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const traces = useRunStore((s) => s.traces[run.id] || EMPTY_TRACES);
  const logs = useRunStore((s) => s.logs[run.id] || EMPTY_LOGS);
  const chatMessages = useRunStore((s) => s.chatMessages[run.id] || EMPTY_CHAT);
  const stateEvents = useRunStore((s) => s.stateEvents[run.id] || EMPTY_STATE_EVENTS);
  const bpMap = useRunStore((s) => s.breakpoints[run.id]);

  // Sync breakpoints to server when switching to this run
  useEffect(() => {
    ws.setBreakpoints(run.id, bpMap ? Object.keys(bpMap) : []);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on run switch
  }, [run.id]);

  // Send breakpoints to server immediately when toggled on graph nodes
  const handleBreakpointChange = useCallback(
    (breakpoints: string[]) => {
      ws.setBreakpoints(run.id, breakpoints);
    },
    [run.id, ws],
  );

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;

    const startY = e.clientY;
    const startH = graphHeight;

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const container = containerRef.current;
      if (!container) return;
      const maxH = container.clientHeight - 100;
      const newH = Math.max(80, Math.min(maxH, startH + (ev.clientY - startY)));
      setGraphHeight(newH);
    };

    const onUp = () => {
      dragging.current = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      setFitViewTrigger((n) => n + 1);
    };

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [graphHeight]);

  const onSidebarResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();

    const startX = e.clientX;
    const startW = sidebarWidth;

    const onMove = (ev: MouseEvent) => {
      const container = outerRef.current;
      if (!container) return;
      const maxW = container.clientWidth - 300;
      const newW = Math.max(280, Math.min(maxW, startW + (startX - ev.clientX)));
      setSidebarWidth(newW);
    };

    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      localStorage.setItem("chatPanelWidth", String(sidebarWidth));
      setFitViewTrigger((n) => n + 1);
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [sidebarWidth]);

  const primaryLabel = isChatMode ? "Chat" : "Events";
  const primaryColor = isChatMode ? "var(--accent)" : "var(--success)";

  const sidebarTabs: { id: SidebarTab; label: string; count?: number }[] = [
    { id: "primary", label: primaryLabel },
    { id: "io", label: "I/O" },
    { id: "logs", label: "Logs", count: logs.length },
  ];

  const interrupt = useRunStore((s) => s.activeInterrupt[run.id] ?? null);

  // Status indicator for the tab bar
  const statusIndicator =
    run.status === "running" ? (
      <span
        className="ml-auto text-[10px] px-2 py-0.5 rounded-full shrink-0"
        style={{
          background: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))",
          color: "var(--warning)",
        }}
      >
        {isChatMode ? "Thinking..." : "Running..."}
      </span>
    ) : isChatMode && run.status === "suspended" && interrupt ? (
      <span
        className="ml-auto text-[10px] px-2 py-0.5 rounded-full shrink-0"
        style={{
          background: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))",
          color: "var(--warning)",
        }}
      >
        Action Required
      </span>
    ) : null;

  return (
    <div ref={outerRef} className="flex h-full">
      {/* Main content: graph + trace tree */}
      <div ref={containerRef} className="flex flex-col flex-1 min-w-0">
        {/* Debug controls */}
        {(run.mode === "debug" || (run.status === "suspended" && !interrupt) || (bpMap && Object.keys(bpMap).length > 0)) && (
          <DebugControls runId={run.id} status={run.status} ws={ws} breakpointNode={run.breakpoint_node} />
        )}
        {/* Graph panel — resizable */}
        <div className="shrink-0" style={{ height: graphHeight }}>
          <GraphPanel entrypoint={run.entrypoint} traces={traces} runId={run.id} breakpointNode={run.breakpoint_node} breakpointNextNodes={run.breakpoint_next_nodes} onBreakpointChange={handleBreakpointChange} fitViewTrigger={fitViewTrigger} />
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

      {/* Sidebar drag handle */}
      <div
        onMouseDown={onSidebarResizeStart}
        className="shrink-0 w-1.5 cursor-col-resize bg-[var(--border)] hover:bg-[var(--accent)] transition-colors relative"
      >
        <div className="absolute inset-0 -left-1 -right-1" />
      </div>

      {/* Sidebar */}
      <div
        className="shrink-0 flex flex-col"
        style={{ width: sidebarWidth, background: "var(--bg-primary)" }}
      >
        {/* Sidebar tab bar */}
        <div
          className="flex items-center gap-1 px-2 py-2.5 border-b shrink-0"
          style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
        >
          {sidebarTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSidebarTab(tab.id)}
              className="px-2 py-0.5 h-5 text-[11px] uppercase tracking-wider font-semibold rounded transition-colors cursor-pointer"
              style={{
                color:
                  sidebarTab === tab.id
                    ? tab.id === "primary"
                      ? primaryColor
                      : "var(--accent)"
                    : "var(--text-muted)",
                background:
                  sidebarTab === tab.id
                    ? `color-mix(in srgb, ${tab.id === "primary" ? primaryColor : "var(--accent)"} 10%, transparent)`
                    : "transparent",
              }}
              onMouseEnter={(e) => {
                if (sidebarTab !== tab.id) e.currentTarget.style.color = "var(--text-primary)";
              }}
              onMouseLeave={(e) => {
                if (sidebarTab !== tab.id) e.currentTarget.style.color = "var(--text-muted)";
              }}
            >
              {tab.label}
              {tab.count !== undefined && tab.count > 0 && (
                <span className="ml-1 font-normal" style={{ color: "var(--text-muted)" }}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
          {statusIndicator}
        </div>

        {/* Sidebar content */}
        <div className="flex-1 overflow-hidden">
          {sidebarTab === "primary" && (
            isChatMode ? (
              <ChatPanel
                messages={chatMessages}
                runId={run.id}
                runStatus={run.status}
                ws={ws}
              />
            ) : (
              <RunEventsPanel events={stateEvents} runStatus={run.status} />
            )
          )}
          {sidebarTab === "io" && (
            <IOView run={run} />
          )}
          {sidebarTab === "logs" && (
            <LogPanel logs={logs} />
          )}
        </div>
      </div>
    </div>
  );
}

function IOView({ run }: { run: RunSummary }) {
  return (
    <div className="p-4 overflow-y-auto h-full space-y-4">
      <DataSection title="Input" color="var(--success)" copyText={JSON.stringify(run.input_data, null, 2)}>
        <JsonHighlight
          json={JSON.stringify(run.input_data, null, 2)}
          className="p-3 rounded-lg text-xs font-mono whitespace-pre-wrap break-words"
          style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
        />
      </DataSection>

      {run.output_data && (
        <DataSection
          title="Output"
          color="var(--accent)"
          copyText={typeof run.output_data === "string" ? run.output_data : JSON.stringify(run.output_data, null, 2)}
        >
          <JsonHighlight
            json={typeof run.output_data === "string"
              ? run.output_data
              : JSON.stringify(run.output_data, null, 2)}
            className="p-3 rounded-lg text-xs font-mono whitespace-pre-wrap break-words"
            style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
          />
        </DataSection>
      )}

      {run.error && (
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: "1px solid color-mix(in srgb, var(--error) 40%, var(--border))" }}
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
            <span
              className="px-1.5 py-0.5 rounded text-[10px] font-mono"
              style={{ background: "color-mix(in srgb, var(--error) 20%, var(--bg-secondary))" }}
            >
              {run.error.category}
            </span>
          </div>
          <div className="p-4 text-xs leading-normal" style={{ background: "var(--bg-secondary)" }}>
            <div className="font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
              {run.error.title}
            </div>
            <pre
              className="whitespace-pre-wrap font-mono text-[11px] max-w-prose"
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
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color }}>{title}</span>
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
