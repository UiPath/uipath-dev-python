import { useEffect, useCallback, useRef } from "react";
import Editor, { DiffEditor, type OnMount, type BeforeMount } from "@monaco-editor/react";
import { useExplorerStore } from "../../store/useExplorerStore";
import { useTheme } from "../../store/useTheme";
import { useHashRoute } from "../../hooks/useHashRoute";
import { readFile, saveFile } from "../../api/explorer-client";
import AgentStatePanel from "../agent/AgentStatePanel";
import ExplorerCanvas from "./ExplorerCanvas";
import StateDbViewer from "./StateDbViewer";

const AGENT_STATE_TAB = "__agent_state__";
const CANVAS_TAB = "__canvas__";
const STATEDB_TAB_PREFIX = "__statedb__:";

function tabToHash(tab: string): string {
  if (tab === CANVAS_TAB) return "#/explorer/canvas";
  if (tab.startsWith(STATEDB_TAB_PREFIX))
    return `#/explorer/statedb/${encodeURIComponent(tab.slice(STATEDB_TAB_PREFIX.length))}`;
  return `#/explorer/file/${encodeURIComponent(tab)}`;
}

const handleBeforeMount: BeforeMount = (monaco) => {
  monaco.editor.defineTheme("uipath-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "64748b", fontStyle: "italic" },
      { token: "keyword", foreground: "c084fc" },
      { token: "string", foreground: "86efac" },
      { token: "number", foreground: "fcd34d" },
      { token: "type", foreground: "7dd3fc" },
    ],
    colors: {
      "editor.background": "#0f172a",
      "editor.foreground": "#cbd5e1",
      "editor.lineHighlightBackground": "#1e293b",
      "editor.selectionBackground": "#334155",
      "editor.inactiveSelectionBackground": "#263348",
      "editorLineNumber.foreground": "#64748b",
      "editorLineNumber.activeForeground": "#94a3b8",
      "editorCursor.foreground": "#fa4616",
      "editorIndentGuide.background": "#334155",
      "editorIndentGuide.activeBackground": "#64748b",
      "editorWidget.background": "#1e293b",
      "editorWidget.border": "#334155",
      "editorSuggestWidget.background": "#1e293b",
      "editorSuggestWidget.border": "#334155",
      "editorSuggestWidget.selectedBackground": "#263348",
      "editorHoverWidget.background": "#1e293b",
      "editorHoverWidget.border": "#334155",
      "scrollbarSlider.background": "#33415580",
      "scrollbarSlider.hoverBackground": "#33415599",
      "scrollbarSlider.activeBackground": "#334155cc",
    },
  });

  monaco.editor.defineTheme("uipath-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "comment", foreground: "94a3b8", fontStyle: "italic" },
      { token: "keyword", foreground: "7c3aed" },
      { token: "string", foreground: "16a34a" },
      { token: "number", foreground: "d97706" },
      { token: "type", foreground: "0284c7" },
    ],
    colors: {
      "editor.background": "#f8fafc",
      "editor.foreground": "#0f172a",
      "editor.lineHighlightBackground": "#f1f5f9",
      "editor.selectionBackground": "#e2e8f0",
      "editor.inactiveSelectionBackground": "#f1f5f9",
      "editorLineNumber.foreground": "#94a3b8",
      "editorLineNumber.activeForeground": "#475569",
      "editorCursor.foreground": "#fa4616",
      "editorIndentGuide.background": "#e2e8f0",
      "editorIndentGuide.activeBackground": "#94a3b8",
      "editorWidget.background": "#ffffff",
      "editorWidget.border": "#e2e8f0",
      "editorSuggestWidget.background": "#ffffff",
      "editorSuggestWidget.border": "#e2e8f0",
      "editorSuggestWidget.selectedBackground": "#f1f5f9",
      "editorHoverWidget.background": "#ffffff",
      "editorHoverWidget.border": "#e2e8f0",
      "scrollbarSlider.background": "#d1d5db80",
      "scrollbarSlider.hoverBackground": "#d1d5db99",
      "scrollbarSlider.activeBackground": "#d1d5dbcc",
    },
  });
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function basename(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

export default function FileEditor() {
  const openTabs = useExplorerStore((s) => s.openTabs);
  const selectedFile = useExplorerStore((s) => s.selectedFile);
  const filePath = selectedFile;
  const fileContent = useExplorerStore((s) => (filePath ? s.fileCache[filePath] : undefined));
  const isDirty = useExplorerStore((s) => (filePath ? !!s.dirty[filePath] : false));
  const buffer = useExplorerStore((s) => (filePath ? s.buffers[filePath] : undefined));
  const loadingFile = useExplorerStore((s) => s.loadingFile);
  const dirty = useExplorerStore((s) => s.dirty);
  const diffView = useExplorerStore((s) => s.diffView);
  const isAgentChanged = useExplorerStore((s) => (filePath ? !!s.agentChangedFiles[filePath] : false));
  const { setFileContent, updateBuffer, markClean, setLoadingFile, openTab, closeTab, setDiffView } =
    useExplorerStore();
  const { navigate } = useHashRoute();
  const theme = useTheme((s) => s.theme);
  const editorRef = useRef<any>(null);

  // Sync route → open tab (e.g. on direct URL navigation)
  const { explorerFile } = useHashRoute();
  useEffect(() => {
    if (explorerFile) {
      openTab(explorerFile);
    }
  }, [explorerFile, openTab]);

  // Load file content when selectedFile changes
  useEffect(() => {
    if (!filePath || filePath === AGENT_STATE_TAB || filePath === CANVAS_TAB || filePath.startsWith(STATEDB_TAB_PREFIX)) return;
    if (!useExplorerStore.getState().fileCache[filePath]) {
      setLoadingFile(true);
      readFile(filePath)
        .then((fc) => setFileContent(filePath, fc))
        .catch(console.error)
        .finally(() => setLoadingFile(false));
    }
  }, [filePath, setFileContent, setLoadingFile]);

  // Save handler
  const handleSave = useCallback(() => {
    if (!filePath) return;
    const fc = useExplorerStore.getState().fileCache[filePath];
    const buf = useExplorerStore.getState().buffers[filePath];
    const content = buf ?? fc?.content;
    if (content == null) return;
    saveFile(filePath, content)
      .then(() => {
        markClean(filePath);
        setFileContent(filePath, { ...fc!, content });
      })
      .catch(console.error);
  }, [filePath, markClean, setFileContent]);

  // Ctrl+S / Cmd+S
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleSave]);

  const handleEditorMount: OnMount = (editor) => {
    editorRef.current = editor;
  };

  const handleChange = useCallback(
    (value: string | undefined) => {
      if (value !== undefined && filePath) {
        updateBuffer(filePath, value);
      }
    },
    [filePath, updateBuffer],
  );

  const handleTabClick = useCallback(
    (path: string) => {
      openTab(path);
      navigate(tabToHash(path));
    },
    [openTab, navigate],
  );

  const handleTabClose = useCallback(
    (e: React.MouseEvent, path: string) => {
      e.stopPropagation();
      const state = useExplorerStore.getState();
      const tabs = state.openTabs.filter((t) => t !== path);
      closeTab(path);
      if (state.selectedFile === path) {
        const idx = state.openTabs.indexOf(path);
        const next = tabs[Math.min(idx, tabs.length - 1)];
        navigate(next ? tabToHash(next) : "#/explorer");
      }
    },
    [closeTab, navigate],
  );

  const handleTabMiddleClick = useCallback(
    (e: React.MouseEvent, path: string) => {
      if (e.button === 1) {
        handleTabClose(e, path);
      }
    },
    [handleTabClose],
  );

  // --- Tab bar ---
  const tabBar = openTabs.length > 0 && (
    <div
      className="h-10 flex items-end overflow-x-auto shrink-0"
      style={{ background: "var(--bg-secondary)", borderBottom: "1px solid var(--border)" }}
    >
      {openTabs.map((tab) => {
        const isActive = tab === filePath;
        const tabDirty = !!dirty[tab];
        return (
          <button
            key={tab}
            onClick={() => handleTabClick(tab)}
            onMouseDown={(e) => handleTabMiddleClick(e, tab)}
            className="h-full flex items-center gap-1.5 px-3 text-[12px] shrink-0 cursor-pointer transition-colors relative"
            style={{
              background: isActive ? "var(--bg-primary)" : "transparent",
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              border: "none",
              borderBottom: isActive ? "2px solid var(--accent)" : "2px solid transparent",
              maxWidth: "180px",
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.background = "var(--bg-hover)";
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.background = "transparent";
            }}
          >
            <span className="truncate">{tab === AGENT_STATE_TAB ? "Agent Trace" : tab === CANVAS_TAB ? "Visualization" : tab.startsWith(STATEDB_TAB_PREFIX) ? `db:${tab.slice(STATEDB_TAB_PREFIX.length)}` : basename(tab)}</span>
            {tabDirty ? (
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ background: "var(--accent)" }}
                title="Unsaved changes"
              />
            ) : (
              <span
                className="w-4 h-4 flex items-center justify-center rounded shrink-0 transition-colors"
                style={{ color: "var(--text-muted)" }}
                onClick={(e) => handleTabClose(e, tab)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-hover)";
                  e.currentTarget.style.color = "var(--text-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--text-muted)";
                }}
              >
                <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 8.707l3.646 3.647.708-.707L8.707 8l3.647-3.646-.707-.708L8 7.293 4.354 3.646l-.708.708L7.293 8l-3.647 3.646.708.708L8 8.707z" />
                </svg>
              </span>
            )}
          </button>
        );
      })}
    </div>
  );

  // Agent Trace special tab
  if (filePath === AGENT_STATE_TAB) {
    return (
      <div className="flex flex-col h-full">
        {tabBar}
        <div className="flex-1 overflow-hidden">
          <AgentStatePanel />
        </div>
      </div>
    );
  }

  // Canvas special tab
  if (filePath === CANVAS_TAB) {
    return (
      <div className="flex flex-col h-full">
        {tabBar}
        <div className="flex-1 overflow-hidden">
          <ExplorerCanvas />
        </div>
      </div>
    );
  }

  // State Database special tab
  if (filePath?.startsWith(STATEDB_TAB_PREFIX)) {
    const table = filePath.slice(STATEDB_TAB_PREFIX.length);
    return (
      <div className="flex flex-col h-full">
        {tabBar}
        <div className="flex-1 overflow-hidden">
          <StateDbViewer table={table} />
        </div>
      </div>
    );
  }

  // No file selected
  if (!filePath) {
    return (
      <div className="flex flex-col h-full">
        {tabBar}
        <div className="flex-1 flex items-center justify-center" style={{ color: "var(--text-muted)" }}>
          Select a file to view
        </div>
      </div>
    );
  }

  // Loading state
  if (loadingFile && !fileContent) {
    return (
      <div className="flex flex-col h-full">
        {tabBar}
        <div className="flex-1 flex items-center justify-center" style={{ color: "var(--text-muted)" }}>
          <div className="text-sm">Loading file...</div>
        </div>
      </div>
    );
  }

  // Error state
  if (!fileContent && !loadingFile) {
    return (
      <div className="flex flex-col h-full">
        {tabBar}
        <div className="flex-1 flex items-center justify-center" style={{ color: "var(--text-muted)" }}>
          <div className="text-sm">Failed to load file</div>
        </div>
      </div>
    );
  }

  if (!fileContent) return null;

  // Binary file
  if (fileContent.binary) {
    return (
      <div className="flex flex-col h-full">
        {tabBar}
        <div
          className="h-8 flex items-center px-3 gap-2 text-xs shrink-0 border-b"
          style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
        >
          <span style={{ color: "var(--text-muted)" }}>{formatSize(fileContent.size)}</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-3" style={{ color: "var(--text-muted)" }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="9" y1="15" x2="15" y2="15" />
          </svg>
          <span className="text-sm">Binary file — preview not available</span>
        </div>
      </div>
    );
  }

  const showDiff = diffView && diffView.path === filePath;

  return (
    <div className="flex flex-col h-full">
      {tabBar}
      {/* Info bar */}
      <div
        className="h-8 flex items-center px-3 gap-2 text-xs shrink-0 border-b"
        style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
      >
        {fileContent.language && (
          <span
            className="px-1.5 py-0.5 rounded text-[10px]"
            style={{ background: "var(--bg-hover)", color: "var(--text-muted)" }}
          >
            {fileContent.language}
          </span>
        )}
        <span style={{ color: "var(--text-muted)" }}>{formatSize(fileContent.size)}</span>
        {isAgentChanged && (
          <span
            className="px-1.5 py-0.5 rounded text-[10px] font-medium"
            style={{ background: "color-mix(in srgb, var(--info) 20%, transparent)", color: "var(--info)" }}
          >
            Agent modified
          </span>
        )}
        <div className="flex-1" />
        {isDirty && (
          <span className="text-[10px] font-medium" style={{ color: "var(--accent)" }}>
            Modified
          </span>
        )}
        <button
          onClick={handleSave}
          className="px-2 py-0.5 rounded text-[11px] font-medium cursor-pointer transition-colors"
          style={{
            background: isDirty ? "var(--accent)" : "var(--bg-hover)",
            color: isDirty ? "white" : "var(--text-muted)",
            border: "none",
          }}
        >
          Save
        </button>
      </div>
      {/* Diff banner */}
      {showDiff && (
        <div
          className="h-8 flex items-center px-3 gap-2 text-xs shrink-0 border-b"
          style={{ borderColor: "var(--border)", background: "color-mix(in srgb, var(--info) 10%, var(--bg-secondary))" }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--info)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span style={{ color: "var(--info)" }}>Agent modified this file</span>
          <div className="flex-1" />
          <button
            onClick={() => setDiffView(null)}
            className="px-2 py-0.5 rounded text-[11px] font-medium cursor-pointer transition-colors"
            style={{ background: "var(--bg-hover)", color: "var(--text-secondary)", border: "none" }}
          >
            Dismiss
          </button>
        </div>
      )}
      {/* Editor or DiffEditor */}
      <div className="flex-1 overflow-hidden">
        {showDiff ? (
          <DiffEditor
            key={`diff-${filePath}`}
            original={diffView.original}
            modified={diffView.modified}
            language={diffView.language ?? "plaintext"}
            theme={theme === "dark" ? "uipath-dark" : "uipath-light"}
            beforeMount={handleBeforeMount}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbersMinChars: 4,
              scrollBeyondLastLine: false,
              automaticLayout: true,
              renderSideBySide: true,
            }}
          />
        ) : (
          <Editor
            key={filePath}
            language={fileContent.language ?? "plaintext"}
            theme={theme === "dark" ? "uipath-dark" : "uipath-light"}
            value={buffer ?? fileContent.content ?? ""}
            onChange={handleChange}
            beforeMount={handleBeforeMount}
            onMount={handleEditorMount}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbersMinChars: 4,
              scrollBeyondLastLine: false,
              wordWrap: "on",
              automaticLayout: true,
              tabSize: 2,
              renderWhitespace: "selection",
            }}
          />
        )}
      </div>
    </div>
  );
}
