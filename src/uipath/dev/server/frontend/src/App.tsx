import { useEffect } from "react";
import { useRunStore } from "./store/useRunStore";
import { useWebSocket } from "./store/useWebSocket";
import { listRuns, listEntrypoints, getRun } from "./api/client";
import { useHashRoute } from "./hooks/useHashRoute";
import Sidebar from "./components/layout/Sidebar";
import NewRunPanel from "./components/runs/NewRunPanel";
import SetupView from "./components/runs/SetupView";
import RunDetailsPanel from "./components/runs/RunDetailsPanel";
import ReloadToast from "./components/shared/ReloadToast";

export default function App() {
  const ws = useWebSocket();
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
  } = useRunStore();
  const { view, runId: routeRunId, setupEntrypoint, setupMode, navigate } = useHashRoute();

  // Sync route runId → store selection
  useEffect(() => {
    if (view === "details" && routeRunId && routeRunId !== selectedRunId) {
      selectRun(routeRunId);
    }
  }, [view, routeRunId, selectedRunId, selectRun]);

  // Load existing runs and entrypoints on mount
  useEffect(() => {
    listRuns().then(setRuns).catch(console.error);
    listEntrypoints()
      .then((eps) => setEntrypoints(eps.map((e) => e.name)))
      .catch(console.error);
  }, [setRuns, setEntrypoints]);

  // Subscribe to selected run
  useEffect(() => {
    if (!selectedRunId) return;
    ws.subscribe(selectedRunId);

    const applyRunDetail = (detail: Awaited<ReturnType<typeof getRun>>) => {
      upsertRun(detail);
      setTraces(selectedRunId, detail.traces);
      setLogs(selectedRunId, detail.logs);
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
      setChatMessages(selectedRunId, chatMsgs);
      // Cache graph data per run (persists across reloads)
      if (detail.graph && detail.graph.nodes.length > 0) {
        setGraphCache(selectedRunId, detail.graph);
      }
      // Load persisted state events
      if (detail.states && detail.states.length > 0) {
        setStateEvents(
          selectedRunId,
          detail.states.map((s) => ({
            node_name: s.node_name,
            qualified_node_name: s.qualified_node_name,
            timestamp: new Date(s.timestamp).getTime(),
            payload: s.payload,
          })),
        );
      }
    };

    // Fetch full run details (includes fresh status in case we missed run.updated events)
    getRun(selectedRunId).then(applyRunDetail).catch(console.error);

    // Safety net: re-fetch if run is still in progress after WS subscribe + initial fetch.
    // Covers the race where the run completes before WS subscription is processed.
    const retryTimer = setTimeout(() => {
      const run = useRunStore.getState().runs[selectedRunId];
      if (run && (run.status === "pending" || run.status === "running")) {
        getRun(selectedRunId).then(applyRunDetail).catch(console.error);
      }
    }, 2000);

    return () => {
      clearTimeout(retryTimer);
      ws.unsubscribe(selectedRunId);
    };
  }, [selectedRunId, ws, upsertRun, setTraces, setLogs, setChatMessages, setStateEvents, setGraphCache]);

  const handleRunCreated = (runId: string) => {
    navigate(`#/runs/${runId}/traces`);
    selectRun(runId);
  };

  const handleSelectRun = (runId: string) => {
    navigate(`#/runs/${runId}/traces`);
    selectRun(runId);
  };

  const handleNewRun = () => {
    navigate("#/new");
  };

  const selectedRun = selectedRunId ? runs[selectedRunId] : null;

  return (
    <div className="flex h-screen w-screen">
      <Sidebar
        runs={Object.values(runs)}
        selectedRunId={selectedRunId}
        onSelectRun={handleSelectRun}
        onNewRun={handleNewRun}
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
          />
        ) : selectedRun ? (
          <RunDetailsPanel run={selectedRun} ws={ws} />
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
