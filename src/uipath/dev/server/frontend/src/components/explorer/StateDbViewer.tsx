import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import hljs from "highlight.js/lib/core";
import json from "highlight.js/lib/languages/json";
import { getStateDbTableData, getStateDbTables, executeStateDbQuery } from "../../api/statedb-client";
import { useHashRoute } from "../../hooks/useHashRoute";
import type { StateDbColumn, StateDbTable } from "../../types/statedb";

hljs.registerLanguage("json", json);

const PAGE_SIZE = 100;

function isObject(val: unknown): val is Record<string, unknown> | unknown[] {
  return val !== null && typeof val === "object";
}

function blobPreview(value: Record<string, unknown> | unknown[]): string {
  if (Array.isArray(value)) return `Array(${value.length})`;
  const keys = Object.keys(value);
  return keys.length <= 3
    ? `{${keys.join(", ")}}`
    : `{${keys.slice(0, 3).join(", ")}, \u2026} (${keys.length} keys)`;
}

function BlobModal({ value, onClose }: { value: Record<string, unknown> | unknown[]; onClose: () => void }) {
  const codeRef = useRef<HTMLElement>(null);
  const formatted = useMemo(() => JSON.stringify(value, null, 2), [value]);
  const highlighted = useMemo(() => hljs.highlight(formatted, { language: "json" }).value, [formatted]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0, 0, 0, 0.5)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-2xl rounded-lg shadow-xl flex flex-col"
        style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", maxHeight: "80vh" }}
      >
        <div className="flex items-center justify-between px-4 py-3 shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <span className="text-[13px] font-medium" style={{ color: "var(--text-primary)" }}>
            {Array.isArray(value) ? `Array (${value.length} items)` : `Object (${Object.keys(value).length} keys)`}
          </span>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded cursor-pointer"
            style={{ color: "var(--text-muted)", background: "transparent", border: "none" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-auto chat-markdown">
          <pre className="m-0 p-4" style={{ background: "transparent" }}>
            <code
              ref={codeRef}
              className="hljs language-json text-[13px] leading-relaxed"
              style={{ background: "transparent", whiteSpace: "pre-wrap", wordBreak: "break-all" }}
              dangerouslySetInnerHTML={{ __html: highlighted }}
            />
          </pre>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function BlobCell({ value }: { value: Record<string, unknown> | unknown[] }) {
  const [open, setOpen] = useState(false);
  const preview = blobPreview(value);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-left text-[12px] cursor-pointer flex items-center gap-1 max-w-[300px]"
        style={{ background: "none", border: "none", padding: 0, color: "var(--accent)" }}
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <line x1="9" y1="3" x2="9" y2="21" />
        </svg>
        <span className="truncate" style={{ color: "var(--text-secondary)" }}>{preview}</span>
      </button>
      {open && <BlobModal value={value} onClose={() => setOpen(false)} />}
    </>
  );
}

function TableListView() {
  const [tables, setTables] = useState<StateDbTable[]>([]);
  const [loading, setLoading] = useState(true);
  const { navigate } = useHashRoute();

  useEffect(() => {
    setLoading(true);
    getStateDbTables()
      .then(setTables)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 h-10 shrink-0 border-b" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        <span className="text-[13px] font-medium" style={{ color: "var(--text-primary)" }}>State Database Tables</span>
      </div>
      {loading ? (
        <div className="flex items-center justify-center flex-1" style={{ color: "var(--text-muted)" }}>
          Loading tables...
        </div>
      ) : tables.length === 0 ? (
        <div className="flex items-center justify-center flex-1" style={{ color: "var(--text-muted)" }}>
          No tables found in state.db
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          <div className="grid gap-2">
            {tables.map((t) => (
              <button
                key={t.name}
                onClick={() => navigate(`#/explorer/statedb/${encodeURIComponent(t.name)}`)}
                className="flex items-center justify-between px-4 py-3 rounded-lg text-left cursor-pointer transition-colors"
                style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
              >
                <div className="flex items-center gap-2">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--accent)" }}>
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <line x1="3" y1="9" x2="21" y2="9" />
                    <line x1="3" y1="15" x2="21" y2="15" />
                    <line x1="9" y1="3" x2="9" y2="21" />
                  </svg>
                  <span className="text-[13px]">{t.name}</span>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ background: "var(--bg-hover)", color: "var(--text-muted)" }}>
                  {t.row_count} rows
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function StateDbViewer({ table }: { table: string }) {
  // Empty string means "show table list"
  if (!table) return <TableListView />;

  return <TableDataView table={table} />;
}

function TableDataView({ table }: { table: string }) {
  const { navigate } = useHashRoute();

  const [columns, setColumns] = useState<StateDbColumn[]>([]);
  const [rows, setRows] = useState<unknown[][]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Custom query state
  const [sql, setSql] = useState("");
  const [queryMode, setQueryMode] = useState(false);

  const loadTable = useCallback((newOffset: number) => {
    setLoading(true);
    setError(null);
    setQueryMode(false);
    getStateDbTableData(table, PAGE_SIZE, newOffset)
      .then((data) => {
        setColumns(data.columns);
        setRows(data.rows);
        setTotal(data.total);
        setOffset(newOffset);
      })
      .catch((err) => setError(err.detail || err.message))
      .finally(() => setLoading(false));
  }, [table]);

  useEffect(() => {
    loadTable(0);
    setSql("");
  }, [table, loadTable]);

  const runQuery = useCallback(() => {
    if (!sql.trim()) return;
    setLoading(true);
    setError(null);
    setQueryMode(true);
    executeStateDbQuery(sql)
      .then((data) => {
        setColumns(data.columns);
        setRows(data.rows);
        setTotal(data.row_count);
        setOffset(0);
      })
      .catch((err) => setError(err.detail || err.message))
      .finally(() => setLoading(false));
  }, [sql]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      runQuery();
    }
  };

  const hasPrev = !queryMode && offset > 0;
  const hasNext = !queryMode && offset + PAGE_SIZE < total;
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 h-10 shrink-0 border-b" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        <button
          onClick={() => navigate("#/explorer/statedb")}
          className="flex items-center gap-1 text-[12px] cursor-pointer transition-colors"
          style={{ background: "none", border: "none", color: "var(--text-muted)" }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Tables
        </button>
        <span style={{ color: "var(--border)" }}>|</span>
        <span className="text-[13px] font-medium" style={{ color: "var(--text-primary)" }}>{table}</span>
        <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ background: "var(--bg-hover)", color: "var(--text-muted)" }}>
          {total} rows
        </span>
      </div>

      {/* Query bar */}
      <div className="flex items-center gap-2 px-4 py-2 shrink-0 border-b" style={{ borderColor: "var(--border)" }}>
        <input
          type="text"
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`SELECT * FROM [${table}] WHERE ...`}
          className="flex-1 text-[13px] px-3 py-1.5 rounded"
          style={{
            background: "var(--bg-primary)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
            outline: "none",
          }}
        />
        <button
          onClick={runQuery}
          disabled={!sql.trim()}
          className="text-[12px] px-3 py-1.5 rounded cursor-pointer shrink-0"
          style={{
            background: sql.trim() ? "var(--accent)" : "var(--bg-hover)",
            color: sql.trim() ? "#fff" : "var(--text-muted)",
            border: "none",
          }}
        >
          Run
        </button>
        {queryMode && (
          <button
            onClick={() => loadTable(0)}
            className="text-[12px] px-3 py-1.5 rounded cursor-pointer shrink-0"
            style={{ background: "var(--bg-hover)", color: "var(--text-secondary)", border: "none" }}
          >
            Reset
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-2 text-[12px] shrink-0" style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444" }}>
          {error}
        </div>
      )}

      {/* Data grid */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32" style={{ color: "var(--text-muted)" }}>
            Loading...
          </div>
        ) : rows.length === 0 ? (
          <div className="flex items-center justify-center h-32" style={{ color: "var(--text-muted)" }}>
            No rows
          </div>
        ) : (
          <table className="w-full text-[12px]" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.name}
                    className="text-left px-3 py-2 whitespace-nowrap sticky top-0"
                    style={{
                      background: "var(--bg-secondary)",
                      borderBottom: "1px solid var(--border)",
                      color: "var(--text-primary)",
                      fontWeight: 600,
                    }}
                  >
                    {col.name}
                    <span className="ml-1 font-normal" style={{ color: "var(--text-muted)", fontSize: "10px" }}>
                      {col.type}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={i}
                  style={{ borderBottom: "1px solid var(--border)" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  {row.map((cell, j) => (
                    <td
                      key={j}
                      className="px-3 py-1.5"
                      style={{
                        color: cell == null ? "var(--text-muted)" : "var(--text-secondary)",
                        maxWidth: isObject(cell) ? undefined : "300px",
                        overflow: isObject(cell) ? undefined : "hidden",
                        textOverflow: isObject(cell) ? undefined : "ellipsis",
                        whiteSpace: isObject(cell) ? undefined : "nowrap",
                        verticalAlign: "top",
                      }}
                      title={cell != null && !isObject(cell) ? String(cell) : undefined}
                    >
                      {cell == null ? (
                        <span style={{ fontStyle: "italic" }}>NULL</span>
                      ) : isObject(cell) ? (
                        <BlobCell value={cell} />
                      ) : (
                        String(cell)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {(hasPrev || hasNext) && !loading && (
        <div className="flex items-center justify-center gap-3 py-2 shrink-0 border-t" style={{ borderColor: "var(--border)" }}>
          <button
            onClick={() => loadTable(offset - PAGE_SIZE)}
            disabled={!hasPrev}
            className="text-[12px] px-3 py-1 rounded cursor-pointer"
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              color: hasPrev ? "var(--text-secondary)" : "var(--text-muted)",
              opacity: hasPrev ? 1 : 0.5,
            }}
          >
            Previous
          </button>
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => loadTable(offset + PAGE_SIZE)}
            disabled={!hasNext}
            className="text-[12px] px-3 py-1 rounded cursor-pointer"
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              color: hasNext ? "var(--text-secondary)" : "var(--text-muted)",
              opacity: hasNext ? 1 : 0.5,
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
