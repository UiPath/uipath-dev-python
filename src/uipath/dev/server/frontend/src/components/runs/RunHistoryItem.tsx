import { useEffect, useRef, useState } from "react";
import type { RunSummary } from "../../types/run";
import AddToEvalModal from "./AddToEvalModal";

const STATUS_COLORS: Record<string, string> = {
  pending: "var(--text-muted)",
  running: "var(--warning)",
  suspended: "var(--info)",
  completed: "var(--success)",
  failed: "var(--error)",
};

interface Props {
  run: RunSummary;
  isSelected: boolean;
  onClick: () => void;
}

export default function RunHistoryItem({ run, isSelected, onClick }: Props) {
  const color = STATUS_COLORS[run.status] ?? "var(--text-muted)";
  const name = run.entrypoint.split("/").pop()?.slice(0, 16) ?? run.entrypoint;
  const time = run.start_time
    ? new Date(run.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  const [menuOpen, setMenuOpen] = useState(false);
  const [showAddToEval, setShowAddToEval] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  return (
    <>
      <div
        className="group relative w-full text-left px-3 py-1.5 flex items-center gap-2 transition-colors cursor-pointer"
        style={{
          background: isSelected
            ? "color-mix(in srgb, var(--accent) 15%, var(--bg-primary))"
            : undefined,
          borderLeft: isSelected ? "3px solid var(--accent)" : "3px solid transparent",
        }}
        onMouseEnter={(e) => {
          if (!isSelected) e.currentTarget.style.background = "var(--bg-hover)";
        }}
        onMouseLeave={(e) => {
          if (!isSelected) e.currentTarget.style.background = "";
        }}
        onClick={onClick}
      >
        {/* Status dot */}
        <span
          className="shrink-0 w-2 h-2 rounded-full"
          style={{ background: color }}
        />
        {/* Details */}
        <div className="flex-1 min-w-0">
          <div
            className="text-xs truncate"
            style={{ color: isSelected ? "var(--text-primary)" : "var(--text-secondary)" }}
          >
            {name}
          </div>
          <div className="text-[11px] tabular-nums" style={{ color: "var(--text-muted)" }}>
            {time}{run.duration ? ` \u00b7 ${run.duration}` : ""}
          </div>
        </div>

        {/* Three-dot menu — only for completed runs */}
        {run.status === "completed" && (
          <div ref={menuRef} className="relative shrink-0">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen((v) => !v);
              }}
              className="opacity-40 group-hover:opacity-100 focus:opacity-100 w-7 h-7 flex items-center justify-center rounded transition-opacity cursor-pointer"
              style={{ color: "var(--text-muted)" }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.background = "var(--bg-secondary)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.background = ""; }}
              aria-label="Actions"
              title="Actions"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                <circle cx="8" cy="3" r="1.5" />
                <circle cx="8" cy="8" r="1.5" />
                <circle cx="8" cy="13" r="1.5" />
              </svg>
            </button>

            {menuOpen && (
              <div
                className="absolute right-0 top-full mt-1 z-50 min-w-[140px] rounded-md shadow-lg py-1"
                style={{ background: "var(--bg-primary)", border: "1px solid var(--border)" }}
              >
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuOpen(false);
                    setShowAddToEval(true);
                  }}
                  className="w-full text-left px-3 py-1.5 text-xs cursor-pointer transition-colors"
                  style={{ color: "var(--text-secondary)" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.color = "var(--text-primary)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ""; e.currentTarget.style.color = "var(--text-secondary)"; }}
                >
                  Add to Eval Set
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {showAddToEval && (
        <AddToEvalModal run={run} onClose={() => setShowAddToEval(false)} />
      )}
    </>
  );
}
