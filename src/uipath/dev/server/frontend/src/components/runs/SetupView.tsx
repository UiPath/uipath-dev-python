import { useCallback, useEffect, useRef, useState } from "react";
import { useRunStore } from "../../store/useRunStore";
import { getEntrypointMockInput, createRun } from "../../api/client";
import type { WsClient } from "../../api/websocket";
import GraphPanel from "../graph/GraphPanel";

const SETUP_RUN_ID = "__setup__";

interface Props {
  entrypoint: string;
  mode: "run" | "chat";
  ws: WsClient;
  onRunCreated: (runId: string) => void;
  isMobile?: boolean;
}

export default function SetupView({ entrypoint, mode, ws, onRunCreated, isMobile }: Props) {
  const [inputJson, setInputJson] = useState("{}");
  const [mockInput, setMockInput] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [loadingSchema, setLoadingSchema] = useState(true);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [chatText, setChatText] = useState("");
  const [fitViewTrigger, setFitViewTrigger] = useState(0);
  const [jsonValid, setJsonValid] = useState(true);
  const [textareaHeight, setTextareaHeight] = useState(() => {
    const saved = localStorage.getItem("setupTextareaHeight");
    return saved ? parseInt(saved, 10) : 140;
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const [panelWidth, setPanelWidth] = useState(() => {
    const saved = localStorage.getItem("setupPanelWidth");
    return saved ? parseInt(saved, 10) : 380;
  });

  const isRunMode = mode === "run";

  // Load mock input
  useEffect(() => {
    setLoadingSchema(true);
    setSchemaError(null);
    getEntrypointMockInput(entrypoint)
      .then((result) => {
        setMockInput(result.mock_input);
        setInputJson(JSON.stringify(result.mock_input, null, 2));
      })
      .catch((err: any) => {
        console.error("Failed to load mock input:", err);
        const detail = err.detail || {};
        setSchemaError(detail.message || `Failed to load schema for "${entrypoint}"`);
        setInputJson("{}");
      })
      .finally(() => setLoadingSchema(false));
  }, [entrypoint]);

  // Clear setup breakpoints on mount
  useEffect(() => {
    useRunStore.getState().clearBreakpoints(SETUP_RUN_ID);
  }, []);

  // Autonomous: execute with JSON input
  const handleExecute = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(inputJson);
    } catch {
      alert("Invalid JSON input");
      return;
    }

    setLoading(true);
    try {
      const bpMap = useRunStore.getState().breakpoints[SETUP_RUN_ID] ?? {};
      const breakpointList = Object.keys(bpMap);

      const run = await createRun(entrypoint, parsed, mode, breakpointList);

      useRunStore.getState().clearBreakpoints(SETUP_RUN_ID);
      useRunStore.getState().upsertRun(run);
      onRunCreated(run.id);
    } catch (err) {
      console.error("Failed to create run:", err);
    } finally {
      setLoading(false);
    }
  };

  // Conversational: send first chat message
  const handleChatSend = async () => {
    const text = chatText.trim();
    if (!text) return;

    setLoading(true);
    try {
      const bpMap = useRunStore.getState().breakpoints[SETUP_RUN_ID] ?? {};
      const breakpointList = Object.keys(bpMap);

      const run = await createRun(entrypoint, mockInput, "chat", breakpointList);

      useRunStore.getState().clearBreakpoints(SETUP_RUN_ID);
      useRunStore.getState().upsertRun(run);

      // Add the user message optimistically and send via WS
      useRunStore.getState().addLocalChatMessage(run.id, {
        message_id: `local-${Date.now()}`,
        role: "user",
        content: text,
      });
      ws.sendChatMessage(run.id, text);

      onRunCreated(run.id);
    } catch (err) {
      console.error("Failed to create chat run:", err);
    } finally {
      setLoading(false);
    }
  };

  // Validate JSON whenever inputJson changes
  useEffect(() => {
    try {
      JSON.parse(inputJson);
      setJsonValid(true);
    } catch {
      setJsonValid(false);
    }
  }, [inputJson]);

  // Textarea top-border drag resize
  const onTextareaDragStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault();
      const startY = "touches" in e ? e.touches[0].clientY : e.clientY;
      const startH = textareaHeight;

      const onMove = (ev: MouseEvent | TouchEvent) => {
        const clientY = "touches" in ev ? ev.touches[0].clientY : ev.clientY;
        const newH = Math.max(60, startH + (startY - clientY));
        setTextareaHeight(newH);
      };

      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.removeEventListener("touchmove", onMove);
        document.removeEventListener("touchend", onUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        localStorage.setItem("setupTextareaHeight", String(textareaHeight));
      };

      document.body.style.cursor = "row-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      document.addEventListener("touchmove", onMove, { passive: false });
      document.addEventListener("touchend", onUp);
    },
    [textareaHeight],
  );

  // Panel resize
  const onPanelResizeStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault();
      const startX = "touches" in e ? e.touches[0].clientX : e.clientX;
      const startW = panelWidth;

      const onMove = (ev: MouseEvent | TouchEvent) => {
        const container = containerRef.current;
        if (!container) return;
        const clientX = "touches" in ev ? ev.touches[0].clientX : ev.clientX;
        const maxW = container.clientWidth - 300;
        const newW = Math.max(280, Math.min(maxW, startW + (startX - clientX)));
        setPanelWidth(newW);
      };

      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.removeEventListener("touchmove", onMove);
        document.removeEventListener("touchend", onUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        localStorage.setItem("setupPanelWidth", String(panelWidth));
        setFitViewTrigger((n) => n + 1);
      };

      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      document.addEventListener("touchmove", onMove, { passive: false });
      document.addEventListener("touchend", onUp);
    },
    [panelWidth],
  );

  const modeLabel = isRunMode ? "Autonomous" : "Conversational";
  const modeColor = isRunMode ? "var(--success)" : "var(--accent)";

  // Shared input panel content
  const inputPanel = (
    <div className="shrink-0 flex flex-col" style={isMobile ? { background: "var(--bg-primary)" } : { width: panelWidth, background: "var(--bg-primary)" }}>
      {/* Header */}
      <div
        className="px-4 text-xs font-semibold uppercase tracking-wider border-b flex items-center gap-2 h-[33px]"
        style={{
          color: "var(--text-muted)",
          borderColor: "var(--border)",
          background: "var(--bg-secondary)",
        }}
      >
        <span style={{ color: modeColor }}>&#9679;</span>
        {modeLabel}
      </div>

      {/* Placeholder area */}
      <div className="flex-1 overflow-y-auto flex flex-col items-center justify-center gap-4 px-6">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: "var(--text-muted)", opacity: 0.5 }}
        >
          {isRunMode ? (
            <>
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </>
          ) : (
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          )}
        </svg>
        <div className="text-center space-y-1.5">
          <p
            className="text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            {isRunMode ? "Ready to execute" : "Ready to chat"}
          </p>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Click nodes to set breakpoints
            {isRunMode ? (
              <>,<br />configure input below, then run</>
            ) : (
              <>,<br />then send your first message</>
            )}
          </p>
        </div>
      </div>

      {/* Bottom input section */}
      {isRunMode ? (
        /* Autonomous: JSON textarea + Execute */
        <div className="flex flex-col" style={{ background: "var(--bg-primary)" }}>
          {/* Drag handle (the top border) — hidden on mobile */}
          {!isMobile && (
            <div
              onMouseDown={onTextareaDragStart}
              onTouchStart={onTextareaDragStart}
              className="shrink-0 h-1.5 cursor-row-resize bg-[var(--border)] hover:bg-[var(--accent)] transition-colors"
            />
          )}
        <div className="px-4 py-3">
          {schemaError ? (
            <div
              className="text-xs mb-3 px-3 py-2 rounded"
              style={{
                color: "var(--error)",
                background:
                  "color-mix(in srgb, var(--error) 10%, var(--bg-secondary))",
              }}
            >
              {schemaError}
            </div>
          ) : (
            <>
              <label
                className="block text-[10px] uppercase tracking-wider font-semibold mb-2"
                style={{ color: "var(--text-muted)" }}
              >
                Input
                {loadingSchema && (
                  <span className="ml-2 font-normal">Loading...</span>
                )}
              </label>
              <textarea
                value={inputJson}
                onChange={(e) => setInputJson(e.target.value)}
                spellCheck={false}
                className="w-full rounded-md px-3 py-2 text-xs font-mono leading-relaxed resize-none focus:outline-none mb-3"
                style={{
                  height: isMobile ? 120 : textareaHeight,
                  background: "var(--bg-secondary)",
                  border: `1px solid ${jsonValid ? "var(--border)" : "#b91c1c"}`,
                  color: "var(--text-primary)",
                }}
              />
            </>
          )}
          <button
            onClick={handleExecute}
            disabled={loading || loadingSchema || !!schemaError}
            className="w-full py-2 text-sm font-semibold rounded-md border cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            style={{
              background: "transparent",
              borderColor: modeColor,
              color: modeColor,
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                e.currentTarget.style.background = `color-mix(in srgb, ${modeColor} 10%, transparent)`;
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            {loading ? (
              "Starting..."
            ) : (
              <>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  stroke="none"
                >
                  <polygon points="5,3 19,12 5,21" />
                </svg>
                Execute
              </>
            )}
          </button>
        </div>
        </div>
      ) : (
        /* Conversational: chat input + Send */
        <div
          className="flex items-center gap-2 px-3 py-2 border-t"
          style={{ borderColor: "var(--border)" }}
        >
          <input
            value={chatText}
            onChange={(e) => setChatText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleChatSend();
              }
            }}
            disabled={loading || loadingSchema}
            placeholder={loading ? "Starting..." : "Message..."}
            className="flex-1 bg-transparent text-sm py-1 focus:outline-none disabled:opacity-40 placeholder:text-[var(--text-muted)]"
            style={{ color: "var(--text-primary)" }}
          />
          <button
            onClick={handleChatSend}
            disabled={loading || loadingSchema || !chatText.trim()}
            className="text-[11px] uppercase tracking-wider font-semibold px-2 py-1 rounded transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              color:
                !loading && chatText.trim()
                  ? "var(--accent)"
                  : "var(--text-muted)",
              background: "transparent",
            }}
            onMouseEnter={(e) => {
              if (!loading && chatText.trim()) {
                e.currentTarget.style.background =
                  "color-mix(in srgb, var(--accent) 10%, transparent)";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            Send
          </button>
        </div>
      )}
    </div>
  );

  // Mobile layout: stacked vertically
  if (isMobile) {
    return (
      <div className="flex flex-col h-full">
        {/* Graph on top */}
        <div className="shrink-0" style={{ height: "40vh" }}>
          <GraphPanel
            entrypoint={entrypoint}
            traces={[]}
            runId={SETUP_RUN_ID}
            fitViewTrigger={fitViewTrigger}
          />
        </div>
        {/* Input panel below — scrollable */}
        <div className="flex-1 overflow-y-auto flex flex-col min-h-0">
          {inputPanel}
        </div>
      </div>
    );
  }

  // Desktop layout (unchanged)
  return (
    <div ref={containerRef} className="flex h-full">
      {/* Graph */}
      <div className="flex-1 min-w-0">
        <GraphPanel
          entrypoint={entrypoint}
          traces={[]}
          runId={SETUP_RUN_ID}
          fitViewTrigger={fitViewTrigger}
        />
      </div>

      {/* Drag handle */}
      <div
        onMouseDown={onPanelResizeStart}
        onTouchStart={onPanelResizeStart}
        className="shrink-0 w-1.5 cursor-col-resize bg-[var(--border)] hover:bg-[var(--accent)] transition-colors relative"
      >
        <div className="absolute inset-0 -left-1 -right-1" />
      </div>

      {/* Side panel */}
      {inputPanel}
    </div>
  );
}
