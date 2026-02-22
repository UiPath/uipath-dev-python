import { useCallback, useEffect, useRef, useState } from "react";
import { useRunStore } from "./store/useRunStore";
import { useAuthStore } from "./store/useAuthStore";
import { useWebSocket } from "./store/useWebSocket";
import { listRuns, listEntrypoints, getRun } from "./api/client";
import type { RunDetail } from "./types/run";
import { useHashRoute } from "./hooks/useHashRoute";
import { useIsMobile } from "./hooks/useIsMobile";
import Sidebar from "./components/layout/Sidebar";
import NewRunPanel from "./components/runs/NewRunPanel";
import SetupView from "./components/runs/SetupView";
import RunDetailsPanel from "./components/runs/RunDetailsPanel";
import ReloadToast from "./components/shared/ReloadToast";

export default function App() {
  const ws = useWebSocket();
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const {
    runs,
    selectedRunId,
    setRuns,
    upsertRun,
    selectRun,
    setTraces,
    setLogs,
    setChatMessages,
    setEntrypoints,
    setStateEvents,
    setGraphCache,
    setActiveNode,
    removeActiveNode,
  } = useRunStore();
  const { view, runId: routeRunId, setupEntrypoint, setupMode, navigate } = useHashRoute();

  // Sync route runId → store selection
  useEffect(() => {
    if (view === "details" && routeRunId && routeRunId !== selectedRunId) {
      selectRun(routeRunId);
    }
  }, [view, routeRunId, selectedRunId, selectRun]);

  // Load existing runs, entrypoints, and auth status on mount
  const initAuth = useAuthStore((s) => s.init);
  useEffect(() => {
    listRuns().then(setRuns).catch(console.error);
    listEntrypoints()
      .then((eps) => setEntrypoints(eps.map((e) => e.name)))
      .catch(console.error);
    initAuth();
  }, [setRuns, setEntrypoints, initAuth]);

  const selectedRun = selectedRunId ? runs[selectedRunId] : null;

  // Shared helper: apply a full run detail response to the store
  const applyRunDetail = useCallback((runId: string, detail: RunDetail) => {
    upsertRun(detail);
    setTraces(runId, detail.traces);
    setLogs(runId, detail.logs);
    // Convert messages to chat format (server uses camelCase aliases)
    const chatMsgs = (detail.messages as unknown as Record<string, unknown>[]).map((m: Record<string, unknown>) => {
      const parts = ((m.contentParts ?? m.content_parts) as Array<Record<string, unknown>>) ?? [];
      const toolCalls = ((m.toolCalls ?? m.tool_calls) as Array<Record<string, unknown>>) ?? [];
      return {
        message_id: ((m.messageId ?? m.message_id) as string),
        role: (m.role as string) ?? "assistant",
        content:
          parts
            .filter((p) => {
              const mime = ((p.mimeType ?? p.mime_type) as string) ?? "";
              return mime.startsWith("text/") || mime === "application/json";
            })
            .map((p) => {
              const data = p.data as Record<string, unknown>;
              return (data?.inline as string) ?? "";
            })
            .join("\n")
            .trim() ?? "",
        tool_calls: toolCalls.length > 0
          ? toolCalls.map((tc) => ({
              name: (tc.name as string) ?? "",
              has_result: !!tc.result,
            }))
          : undefined,
      };
    });
    setChatMessages(runId, chatMsgs);
    // Cache graph data per run (persists across reloads)
    if (detail.graph && detail.graph.nodes.length > 0) {
      setGraphCache(runId, detail.graph);
    }
    // Load persisted state events
    if (detail.states && detail.states.length > 0) {
      setStateEvents(
        runId,
        detail.states.map((s) => ({
          node_name: s.node_name,
          qualified_node_name: s.qualified_node_name,
          phase: s.phase,
          timestamp: new Date(s.timestamp).getTime(),
          payload: s.payload,
        })),
      );
      // Seed activeNodes from historical events (replay all to get correct prev + executing)
      if (detail.status !== "completed" && detail.status !== "failed") {
        for (const s of detail.states) {
          if (s.phase === "started") {
            setActiveNode(runId, s.node_name, s.qualified_node_name);
          } else if (s.phase === "completed") {
            removeActiveNode(runId, s.node_name);
          }
        }
      }
    }
  }, [upsertRun, setTraces, setLogs, setChatMessages, setStateEvents, setGraphCache, setActiveNode, removeActiveNode]);

  // Subscribe to selected run
  useEffect(() => {
    if (!selectedRunId) return;
    ws.subscribe(selectedRunId);

    // Fetch full run details (includes fresh status in case we missed run.updated events)
    getRun(selectedRunId).then((d) => applyRunDetail(selectedRunId, d)).catch(console.error);

    // Safety net: re-fetch if run is still in progress after WS subscribe + initial fetch.
    // Covers the race where the run completes before WS subscription is processed.
    const retryTimer = setTimeout(() => {
      const run = useRunStore.getState().runs[selectedRunId];
      if (run && (run.status === "pending" || run.status === "running")) {
        getRun(selectedRunId).then((d) => applyRunDetail(selectedRunId, d)).catch(console.error);
      }
    }, 2000);

    return () => {
      clearTimeout(retryTimer);
      ws.unsubscribe(selectedRunId);
    };
  }, [selectedRunId, ws, applyRunDetail]);

  // Refetch full details when run reaches terminal status, but only if WS events were missed
  const prevStatusRef = useRef<string | null>(null);
  useEffect(() => {
    if (!selectedRunId) return;
    const status = selectedRun?.status;
    const prev = prevStatusRef.current;
    prevStatusRef.current = status ?? null;

    if (
      status &&
      (status === "completed" || status === "failed") &&
      prev !== status
    ) {
      // Compare what we received via WS against the counts in the run summary.
      // Only refetch if something was missed — avoids unnecessary re-renders / flicker.
      const state = useRunStore.getState();
      const haveTraces = state.traces[selectedRunId]?.length ?? 0;
      const haveLogs = state.logs[selectedRunId]?.length ?? 0;
      const expectedTraces = selectedRun?.trace_count ?? 0;
      const expectedLogs = selectedRun?.log_count ?? 0;

      if (haveTraces < expectedTraces || haveLogs < expectedLogs) {
        getRun(selectedRunId).then((d) => applyRunDetail(selectedRunId, d)).catch(console.error);
      }
    }
  }, [selectedRunId, selectedRun?.status, applyRunDetail]);

  const handleRunCreated = (runId: string) => {
    navigate(`#/runs/${runId}/traces`);
    selectRun(runId);
    setSidebarOpen(false);
  };

  const handleSelectRun = (runId: string) => {
    navigate(`#/runs/${runId}/traces`);
    selectRun(runId);
    setSidebarOpen(false);
  };

  const handleNewRun = () => {
    navigate("#/new");
    setSidebarOpen(false);
  };

  return (
    <div className="flex h-screen w-screen relative">
      {/* Mobile hamburger button */}
      {isMobile && !sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed top-2 left-2 z-40 w-9 h-9 flex items-center justify-center rounded-lg cursor-pointer"
          style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
      )}
      <Sidebar
        runs={Object.values(runs)}
        selectedRunId={selectedRunId}
        onSelectRun={handleSelectRun}
        onNewRun={handleNewRun}
        isMobile={isMobile}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <main className="flex-1 overflow-hidden bg-[var(--bg-primary)]">
        {view === "new" ? (
          <NewRunPanel />
        ) : view === "setup" && setupEntrypoint && setupMode ? (
          <SetupView
            entrypoint={setupEntrypoint}
            mode={setupMode}
            ws={ws}
            onRunCreated={handleRunCreated}
            isMobile={isMobile}
          />
        ) : selectedRun ? (
          <RunDetailsPanel run={selectedRun} ws={ws} isMobile={isMobile} />
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--text-muted)]">
            Select a run or create a new one
          </div>
        )}
      </main>
      <ReloadToast />
    </div>
  );
}
