import { useCallback, useEffect, useRef, useState } from "react";
import { useRunStore } from "./store/useRunStore";
import { useAuthStore } from "./store/useAuthStore";
import { useConfigStore } from "./store/useConfigStore";
import { useWebSocket } from "./store/useWebSocket";
import { listRuns, listEntrypoints, getRun } from "./api/client";
import type { RunDetail } from "./types/run";
import { useHashRoute } from "./hooks/useHashRoute";
import type { Section } from "./hooks/useHashRoute";
import { useIsMobile } from "./hooks/useIsMobile";
import ActivityBar from "./components/layout/ActivityBar";
import DebugSidebar from "./components/layout/DebugSidebar";
import StatusBar from "./components/layout/StatusBar";
import NewRunPanel from "./components/runs/NewRunPanel";
import SetupView from "./components/runs/SetupView";
import RunDetailsPanel from "./components/runs/RunDetailsPanel";
import ReloadToast from "./components/shared/ReloadToast";
import ToastContainer from "./components/shared/ToastContainer";
import { useEvalStore } from "./store/useEvalStore";
import { listEvalSets, listEvaluators, listEvalRuns, listLocalEvaluators } from "./api/eval-client";
import EvalsSidebar from "./components/evals/EvalsSidebar";
import EvalSetDetail from "./components/evals/EvalSetDetail";
import EvalRunResults from "./components/evals/EvalRunResults";
import CreateEvalSetView from "./components/evals/CreateEvalSetView";
import EvaluatorsSidebar from "./components/evaluators/EvaluatorsSidebar";
import EvaluatorsView from "./components/evaluators/EvaluatorDetail";
import CreateEvaluatorView from "./components/evaluators/CreateEvaluatorView";
import ExplorerSidebar from "./components/explorer/ExplorerSidebar";
import FileEditor from "./components/explorer/FileEditor";
import StateDbViewer from "./components/explorer/StateDbViewer";
import AgentChatSidebar from "./components/agent/AgentChatSidebar";
import { useExplorerStore } from "./store/useExplorerStore";

export default function App() {
  const ws = useWebSocket();
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(248);
  const [isDraggingSidebar, setIsDraggingSidebar] = useState(false);
  const [agentWidth, setAgentWidth] = useState(380);
  const [isDraggingAgent, setIsDraggingAgent] = useState(false);
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
  const {
    section,
    view,
    runId: routeRunId,
    setupEntrypoint,
    setupMode,
    evalCreating,
    evalSetId,
    evalRunId,
    evalRunItemName,
    evaluatorCreateType,
    evaluatorId,
    evaluatorFilter,
    explorerFile,
    stateDbTable,
    navigate,
  } = useHashRoute();

  const { setEvalSets, setEvaluators, setLocalEvaluators, setEvalRuns } = useEvalStore();

  // Sync route runId → store selection
  useEffect(() => {
    if (section === "debug" && view === "details" && routeRunId && routeRunId !== selectedRunId) {
      selectRun(routeRunId);
    }
  }, [section, view, routeRunId, selectedRunId, selectRun]);

  // Load existing runs, entrypoints, auth status, and config on mount
  const initAuth = useAuthStore((s) => s.init);
  const initConfig = useConfigStore((s) => s.init);
  useEffect(() => {
    listRuns().then(setRuns).catch(console.error);
    listEntrypoints()
      .then((eps) => setEntrypoints(eps.map((e) => e.name)))
      .catch(console.error);
    initAuth();
    initConfig();
  }, [setRuns, setEntrypoints, initAuth, initConfig]);

  // Load eval data when switching to evals/evaluators section
  useEffect(() => {
    if (section === "evals") {
      listEvalSets().then((sets) => setEvalSets(sets)).catch(console.error);
      listEvalRuns().then((runs) => setEvalRuns(runs)).catch(console.error);
    }
    if (section === "evals" || section === "evaluators") {
      listEvaluators().then((evs) => setEvaluators(evs)).catch(console.error);
      listLocalEvaluators().then((evs) => setLocalEvaluators(evs)).catch(console.error);
    }
  }, [section, setEvalSets, setEvaluators, setLocalEvaluators, setEvalRuns]);

  // Auto-select latest run or first eval set when navigating to evals with no selection
  const evalSets = useEvalStore((s) => s.evalSets);
  const evalRuns = useEvalStore((s) => s.evalRuns);
  useEffect(() => {
    if (section !== "evals" || evalCreating || evalSetId || evalRunId) return;
    // Pick latest run by start_time
    const runs = Object.values(evalRuns).sort(
      (a, b) => new Date(b.start_time ?? 0).getTime() - new Date(a.start_time ?? 0).getTime(),
    );
    if (runs.length > 0) {
      navigate(`#/evals/runs/${runs[0].id}`);
      return;
    }
    // Fallback: first eval set
    const sets = Object.values(evalSets);
    if (sets.length > 0) {
      navigate(`#/evals/sets/${sets[0].id}`);
    }
  }, [section, evalCreating, evalSetId, evalRunId, evalRuns, evalSets, navigate]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && sidebarOpen) {
        setSidebarOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [sidebarOpen]);

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
    navigate(`#/debug/runs/${runId}/traces`);
    selectRun(runId);
    setSidebarOpen(false);
  };

  const handleSelectRun = (runId: string) => {
    navigate(`#/debug/runs/${runId}/traces`);
    selectRun(runId);
    setSidebarOpen(false);
  };

  const handleNewRun = () => {
    navigate("#/debug/new");
    setSidebarOpen(false);
  };

  const handleSectionChange = (s: Section) => {
    if (s === "debug") navigate("#/debug/new");
    else if (s === "evals") navigate("#/evals");
    else if (s === "evaluators") navigate("#/evaluators");
    else if (s === "explorer") navigate("#/explorer");
  };

  // --- Sidebar col resize ---
  const onSidebarResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    setIsDraggingSidebar(true);

    const startX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const startW = sidebarWidth;

    const onMove = (ev: MouseEvent | TouchEvent) => {
      const clientX = "touches" in ev ? ev.touches[0].clientX : ev.clientX;
      const newW = Math.max(200, Math.min(480, startW + (clientX - startX)));
      setSidebarWidth(newW);
    };

    const onUp = () => {
      setIsDraggingSidebar(false);
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

  // --- Agent panel col resize ---
  const onAgentResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    setIsDraggingAgent(true);

    const startX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const startW = agentWidth;

    const onMove = (ev: MouseEvent | TouchEvent) => {
      const clientX = "touches" in ev ? ev.touches[0].clientX : ev.clientX;
      // Dragging left increases width (panel is on the right)
      const newW = Math.max(280, Math.min(700, startW - (clientX - startX)));
      setAgentWidth(newW);
    };

    const onUp = () => {
      setIsDraggingAgent(false);
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
  }, [agentWidth]);

  const explorerTabs = useExplorerStore((s) => s.openTabs);

  // --- Render main content based on section ---
  const renderMainContent = () => {
    if (section === "explorer") {
      if (stateDbTable !== null) return <StateDbViewer table={stateDbTable} />;
      if (explorerTabs.length > 0 || explorerFile) return <FileEditor />;
      return (
        <div className="flex items-center justify-center h-full text-[var(--text-muted)]">
          Select a file to view
        </div>
      );
    }

    if (section === "evals") {
      if (evalCreating) return <CreateEvalSetView />;
      if (evalRunId) return <EvalRunResults evalRunId={evalRunId} itemName={evalRunItemName} />;
      if (evalSetId) return <EvalSetDetail evalSetId={evalSetId} />;
      return <CreateEvalSetView />;
    }

    if (section === "evaluators") {
      if (evaluatorCreateType) {
        return <CreateEvaluatorView category={evaluatorCreateType} />;
      }
      return <EvaluatorsView evaluatorId={evaluatorId} evaluatorFilter={evaluatorFilter} />;
    }

    // Debug section
    if (view === "new") {
      return <NewRunPanel />;
    }
    if (view === "setup" && setupEntrypoint && setupMode) {
      return (
        <SetupView
          entrypoint={setupEntrypoint}
          mode={setupMode}
          ws={ws}
          onRunCreated={handleRunCreated}
          isMobile={isMobile}
        />
      );
    }
    if (selectedRun) {
      return <RunDetailsPanel run={selectedRun} ws={ws} isMobile={isMobile} />;
    }
    return (
      <div className="flex items-center justify-center h-full text-[var(--text-muted)]">
        Select a run or create a new one
      </div>
    );
  };

  // --- Mobile layout ---
  if (isMobile) {
    return (
      <div className="flex flex-col h-screen w-screen">
        <div className="flex flex-1 overflow-hidden relative">
          {!sidebarOpen && (
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
          {sidebarOpen && (
            <>
              <div
                className="fixed inset-0 z-50"
                style={{ background: "rgba(0,0,0,0.5)" }}
                onClick={() => setSidebarOpen(false)}
              />
              <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-[var(--sidebar-bg)] border-r border-[var(--border)] flex flex-col">
                <div className="px-3 h-10 border-b border-[var(--border)] flex items-center justify-between">
                  <button
                    onClick={() => { navigate("#/debug/new"); setSidebarOpen(false); }}
                    className="flex items-center gap-2 cursor-pointer"
                    style={{ background: "none", border: "none" }}
                  >
                    <img src="/favicon.ico" width="14" height="14" alt="UiPath" />
                    <span className="text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-muted)" }}>
                      Developer Console
                    </span>
                  </button>
                  <button
                    onClick={() => setSidebarOpen(false)}
                    className="w-6 h-6 flex items-center justify-center rounded cursor-pointer transition-colors"
                    style={{ color: "var(--text-muted)", background: "transparent", border: "none" }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
                {section === "debug" && (
                  <DebugSidebar
                    runs={Object.values(runs)}
                    selectedRunId={selectedRunId}
                    onSelectRun={handleSelectRun}
                    onNewRun={handleNewRun}
                  />
                )}
                {section === "evals" && <EvalsSidebar />}
                {section === "evaluators" && <EvaluatorsSidebar />}
                {section === "explorer" && <ExplorerSidebar />}
              </aside>
            </>
          )}
          <main className="flex-1 overflow-hidden bg-[var(--bg-primary)]">
            {renderMainContent()}
          </main>
        </div>
        <StatusBar />
        <ReloadToast />
        <ToastContainer />
      </div>
    );
  }

  // --- Desktop layout ---
  return (
    <div className="flex flex-col h-screen w-screen">
      <div className="flex flex-1 overflow-hidden">
        {/* Left aside: shared header + ActivityBar + section sidebar */}
        <aside className="shrink-0 flex flex-col" style={{ width: sidebarWidth, background: "var(--sidebar-bg)" }}>
          {/* Split header: icon (left, aligned to ActivityBar) | section title (right) */}
          <div className="flex h-10 border-b shrink-0" style={{ borderColor: "var(--border)" }}>
            <button
              onClick={() => navigate("#/debug/new")}
              className="w-12 shrink-0 flex items-center justify-center cursor-pointer transition-colors border-r"
              style={{ background: "var(--activity-bar-bg)", border: "none", borderRight: "1px solid var(--border)" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "var(--activity-bar-bg)"; }}
            >
              <img src="/favicon.ico" width="20" height="20" alt="UiPath" />
            </button>
            <div className="flex-1 flex items-center px-3" style={{ background: "var(--sidebar-bg)" }}>
              <span className="text-[11px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-muted)" }}>
                {section === "debug" ? "Developer Console" : section === "evals" ? "Evaluations" : section === "evaluators" ? "Evaluators" : "Explorer"}
              </span>
            </div>
          </div>
          {/* ActivityBar (icons) + section content side by side */}
          <div className="flex flex-1 overflow-hidden">
            <ActivityBar section={section} onSectionChange={handleSectionChange} />
            <div className="flex-1 flex flex-col overflow-hidden">
              {section === "debug" && (
                <DebugSidebar
                  runs={Object.values(runs)}
                  selectedRunId={selectedRunId}
                  onSelectRun={handleSelectRun}
                  onNewRun={handleNewRun}
                />
              )}
              {section === "evals" && <EvalsSidebar />}
              {section === "evaluators" && <EvaluatorsSidebar />}
              {section === "explorer" && <ExplorerSidebar />}
            </div>
          </div>
        </aside>
        <div
          onMouseDown={onSidebarResizeStart}
          onTouchStart={onSidebarResizeStart}
          className="shrink-0 drag-handle-col"
          style={isDraggingSidebar ? { background: "var(--accent)" } : undefined}
        />
        <main className="flex-1 overflow-hidden bg-[var(--bg-primary)] flex">
          <div className="flex-1 overflow-hidden">
            {renderMainContent()}
          </div>
          {section === "explorer" && (
            <>
              <div
                onMouseDown={onAgentResizeStart}
                onTouchStart={onAgentResizeStart}
                className="shrink-0 drag-handle-col"
                style={isDraggingAgent ? { background: "var(--accent)" } : undefined}
              />
              <div className="shrink-0 overflow-hidden" style={{ width: agentWidth, borderLeft: "1px solid var(--border)" }}>
                <AgentChatSidebar />
              </div>
            </>
          )}
        </main>
      </div>
      <StatusBar />
      <ReloadToast />
      <ToastContainer />
    </div>
  );
}
