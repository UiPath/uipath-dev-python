import { useEffect, useState } from "react";
import { useRunStore } from "./store/useRunStore";
import { useWebSocket } from "./store/useWebSocket";
import { listRuns, listEntrypoints, getRun } from "./api/client";
import Sidebar from "./components/layout/Sidebar";
import NewRunPanel from "./components/runs/NewRunPanel";
import RunDetailsPanel from "./components/runs/RunDetailsPanel";

export default function App() {
  const ws = useWebSocket();
  const {
    runs,
    selectedRunId,
    setRuns,
    selectRun,
    setTraces,
    setLogs,
    setChatMessages,
    setEntrypoints,
  } = useRunStore();
  const [view, setView] = useState<"new" | "details">("new");

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

    // Fetch full run details
    getRun(selectedRunId).then((detail) => {
      setTraces(selectedRunId, detail.traces);
      setLogs(selectedRunId, detail.logs);
      // Convert messages to chat format
      const chatMsgs = detail.messages.map((m) => ({
        message_id: m.message_id,
        role: m.role,
        content:
          m.content_parts
            ?.filter(
              (p) =>
                p.mime_type.startsWith("text/") ||
                p.mime_type === "application/json",
            )
            .map((p) => p.data?.inline ?? "")
            .join("\n")
            .trim() ?? "",
        tool_calls: m.tool_calls?.map((tc) => ({
          name: tc.name,
          has_result: !!tc.result,
        })),
      }));
      setChatMessages(selectedRunId, chatMsgs);
    }).catch(console.error);

    return () => ws.unsubscribe(selectedRunId);
  }, [selectedRunId, ws, setTraces, setLogs, setChatMessages]);

  const handleRunCreated = (runId: string) => {
    selectRun(runId);
    setView("details");
  };

  const handleSelectRun = (runId: string) => {
    selectRun(runId);
    setView("details");
  };

  const handleNewRun = () => {
    setView("new");
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
          <NewRunPanel onRunCreated={handleRunCreated} />
        ) : selectedRun ? (
          <RunDetailsPanel run={selectedRun} ws={ws} />
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--text-muted)]">
            Select a run or create a new one
          </div>
        )}
      </main>
    </div>
  );
}
