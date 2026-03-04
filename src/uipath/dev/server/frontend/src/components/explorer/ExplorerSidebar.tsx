import { useEffect, useCallback, useState } from "react";
import { useExplorerStore } from "../../store/useExplorerStore";
import { useHashRoute } from "../../hooks/useHashRoute";
import { listDirectory } from "../../api/explorer-client";
import { getStateDbStatus, getStateDbTables } from "../../api/statedb-client";
import type { StateDbTable } from "../../types/statedb";

function FileTreeNode({ path, name, type, depth }: {
  path: string;
  name: string;
  type: "file" | "directory";
  depth: number;
}) {
  const children = useExplorerStore((s) => s.children[path]);
  const isExpanded = useExplorerStore((s) => !!s.expanded[path]);
  const isLoading = useExplorerStore((s) => !!s.loadingDirs[path]);
  const isDirty = useExplorerStore((s) => !!s.dirty[path]);
  const isAgentChanged = useExplorerStore((s) => !!s.agentChangedFiles[path]);
  const selectedFile = useExplorerStore((s) => s.selectedFile);
  const { setChildren, toggleExpanded, setLoadingDir, openTab } = useExplorerStore();
  const { navigate } = useHashRoute();

  const isDir = type === "directory";
  const isSelected = !isDir && selectedFile === path;

  const handleClick = useCallback(() => {
    if (isDir) {
      if (!children && !isLoading) {
        setLoadingDir(path, true);
        listDirectory(path)
          .then((entries) => setChildren(path, entries))
          .catch(console.error)
          .finally(() => setLoadingDir(path, false));
      }
      toggleExpanded(path);
    } else {
      openTab(path);
      navigate(`#/explorer/file/${encodeURIComponent(path)}`);
    }
  }, [isDir, children, isLoading, path, setChildren, toggleExpanded, setLoadingDir, openTab, navigate]);

  return (
    <>
      <button
        onClick={handleClick}
        className={`w-full text-left flex items-center gap-1 py-[3px] text-[13px] cursor-pointer transition-colors group${isAgentChanged ? " agent-changed-file" : ""}`}
        style={{
          paddingLeft: `${12 + depth * 16}px`,
          paddingRight: "8px",
          background: isSelected
            ? "color-mix(in srgb, var(--accent) 15%, var(--bg-primary))"
            : "transparent",
          color: isSelected ? "var(--text-primary)" : "var(--text-secondary)",
          border: "none",
        }}
        onMouseEnter={(e) => {
          if (!isSelected) e.currentTarget.style.background = "var(--bg-hover)";
        }}
        onMouseLeave={(e) => {
          if (!isSelected) e.currentTarget.style.background = "transparent";
        }}
      >
        {/* Chevron / spacer */}
        <span className="w-3 shrink-0 flex items-center justify-center" style={{ color: "var(--text-muted)" }}>
          {isDir && (
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              fill="currentColor"
              style={{ transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.15s" }}
            >
              <path d="M3 1.5L7 5L3 8.5z" />
            </svg>
          )}
        </span>
        {/* Icon */}
        <span className="shrink-0" style={{ color: isDir ? "var(--accent)" : "var(--text-muted)" }}>
          {isDir ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          )}
        </span>
        {/* Label */}
        <span className="truncate flex-1">{name}</span>
        {/* Dirty dot */}
        {isDirty && (
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: "var(--accent)" }}
          />
        )}
        {isLoading && (
          <span className="text-[10px] shrink-0" style={{ color: "var(--text-muted)" }}>...</span>
        )}
      </button>
      {isDir && isExpanded && children && (
        children.map((child) => (
          <FileTreeNode
            key={child.path}
            path={child.path}
            name={child.name}
            type={child.type}
            depth={depth + 1}
          />
        ))
      )}
    </>
  );
}

const STATEDB_TAB_PREFIX = "__statedb__:";

function StateDbSection({ onDbMissing }: { onDbMissing: () => void }) {
  const [tables, setTables] = useState<StateDbTable[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const selectedFile = useExplorerStore((s) => s.selectedFile);
  const { openTab } = useExplorerStore();
  const { navigate } = useHashRoute();

  const refresh = useCallback(() => {
    setRefreshing(true);
    getStateDbStatus()
      .then(({ exists }) => {
        if (!exists) {
          onDbMissing();
          return;
        }
        return getStateDbTables().then(setTables);
      })
      .catch(console.error)
      .finally(() => setRefreshing(false));
  }, [onDbMissing]);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div>
      {/* Section header */}
      <div className="flex items-center">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex-1 text-left flex items-center gap-1 py-[5px] text-[11px] uppercase tracking-wider font-semibold cursor-pointer"
          style={{ paddingLeft: "12px", background: "none", border: "none", color: "var(--text-muted)" }}
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4.03 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
          </svg>
          State Database
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); refresh(); }}
          className="shrink-0 flex items-center justify-center w-5 h-5 rounded cursor-pointer"
          style={{ background: "none", border: "none", color: "var(--text-muted)", marginRight: "8px" }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
          title="Refresh tables"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={refreshing ? { animation: "spin 0.6s linear infinite" } : undefined}
          >
            <polyline points="23 4 23 10 17 10" />
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
        </button>
      </div>
      {expanded && tables.map((t) => {
        const tabKey = `${STATEDB_TAB_PREFIX}${t.name}`;
        const isSelected = selectedFile === tabKey;
        return (
          <button
            key={t.name}
            onClick={() => { openTab(tabKey); navigate(`#/explorer/statedb/${encodeURIComponent(t.name)}`); }}
            className="w-full text-left flex items-center gap-1 py-[3px] text-[13px] cursor-pointer transition-colors"
            style={{
              paddingLeft: "28px",
              paddingRight: "8px",
              background: isSelected
                ? "color-mix(in srgb, var(--accent) 15%, var(--bg-primary))"
                : "transparent",
              color: isSelected ? "var(--text-primary)" : "var(--text-secondary)",
              border: "none",
            }}
            onMouseEnter={(e) => {
              if (!isSelected) e.currentTarget.style.background = "var(--bg-hover)";
            }}
            onMouseLeave={(e) => {
              if (!isSelected) e.currentTarget.style.background = "transparent";
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--accent)" }} className="shrink-0">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="3" y1="9" x2="21" y2="9" />
              <line x1="3" y1="15" x2="21" y2="15" />
              <line x1="9" y1="3" x2="9" y2="21" />
            </svg>
            <span className="truncate flex-1">{t.name}</span>
            <span className="text-[10px] shrink-0" style={{ color: "var(--text-muted)" }}>
              {t.row_count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export default function ExplorerSidebar() {
  const rootChildren = useExplorerStore((s) => s.children[""]);
  const { setChildren } = useExplorerStore();
  const [hasStateDb, setHasStateDb] = useState(false);
  const [filesExpanded, setFilesExpanded] = useState(true);
  const { openTab } = useExplorerStore();
  const { navigate } = useHashRoute();

  // Load root directory on mount
  useEffect(() => {
    if (!rootChildren) {
      listDirectory("")
        .then((entries) => setChildren("", entries))
        .catch(console.error);
    }
  }, [rootChildren, setChildren]);

  // Check if state.db exists
  useEffect(() => {
    getStateDbStatus()
      .then(({ exists }) => setHasStateDb(exists))
      .catch(() => setHasStateDb(false));
  }, []);

  return (
    <div className="flex-1 overflow-y-auto py-1">
      {/* Canvas */}
      <button
        onClick={() => { openTab("__canvas__"); navigate("#/explorer/canvas"); }}
        className="w-full text-left flex items-center gap-1 py-[5px] text-[11px] uppercase tracking-wider font-semibold cursor-pointer"
        style={{ paddingLeft: "12px", paddingRight: "8px", background: "none", border: "none", color: "var(--text-muted)" }}
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
          <circle cx="5" cy="1.5" r="1.2" />
          <circle cx="2" cy="8" r="1.2" />
          <circle cx="8" cy="8" r="1.2" />
          <line x1="5" y1="2.7" x2="2" y2="6.8" stroke="currentColor" strokeWidth="0.8" />
          <line x1="5" y1="2.7" x2="8" y2="6.8" stroke="currentColor" strokeWidth="0.8" />
        </svg>
        Visualization
      </button>
      {hasStateDb && (
        <StateDbSection onDbMissing={() => setHasStateDb(false)} />
      )}
      {/* Collapsible FILES section */}
      <button
        onClick={() => setFilesExpanded(!filesExpanded)}
        className="w-full text-left flex items-center gap-1 py-[5px] text-[11px] uppercase tracking-wider font-semibold cursor-pointer"
        style={{ paddingLeft: "12px", paddingRight: "8px", background: "none", border: "none", color: "var(--text-muted)" }}
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z" />
        </svg>
        Files
      </button>
      {filesExpanded && (
        rootChildren ? (
          rootChildren.map((entry) => (
            <FileTreeNode
              key={entry.path}
              path={entry.path}
              name={entry.name}
              type={entry.type}
              depth={0}
            />
          ))
        ) : (
          <p className="text-[11px] px-3 py-2" style={{ color: "var(--text-muted)" }}>
            Loading...
          </p>
        )
      )}
    </div>
  );
}
