import type { RunSummary } from "../../types/run";
import { useTheme } from "../../store/useTheme";
import RunHistoryItem from "../runs/RunHistoryItem";

interface Props {
  runs: RunSummary[];
  selectedRunId: string | null;
  onSelectRun: (id: string) => void;
  onNewRun: () => void;
  isMobile?: boolean;
  isOpen?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ runs, selectedRunId, onSelectRun, onNewRun, isMobile, isOpen, onClose }: Props) {
  const { theme, toggleTheme } = useTheme();

  const sorted = [...runs].sort(
    (a, b) =>
      new Date(b.start_time ?? 0).getTime() -
      new Date(a.start_time ?? 0).getTime(),
  );

  // On mobile: hidden unless open, renders as overlay drawer
  if (isMobile) {
    if (!isOpen) return null;
    return (
      <>
        {/* Backdrop */}
        <div
          className="fixed inset-0 z-50"
          style={{ background: "rgba(0,0,0,0.5)" }}
          onClick={onClose}
        />
        {/* Drawer */}
        <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-[var(--sidebar-bg)] border-r border-[var(--border)] flex flex-col">
          {/* Header */}
          <div className="px-3 h-10 border-b border-[var(--border)] flex items-center justify-between">
            <button
              onClick={onNewRun}
              className="flex items-center gap-1.5 cursor-pointer transition-opacity hover:opacity-80"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <rect width="24" height="24" rx="4" fill="var(--accent)" />
                <text x="12" y="17" textAnchor="middle" fill="white" fontSize="14" fontWeight="700" fontFamily="Arial, sans-serif">U</text>
              </svg>
              <span
                className="text-[11px] uppercase tracking-widest font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                Dev Console
              </span>
            </button>
            <div className="flex items-center gap-1">
              <button
                onClick={toggleTheme}
                className="w-6 h-6 flex items-center justify-center rounded cursor-pointer transition-colors"
                style={{ color: "var(--text-muted)" }}
                title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  {theme === "dark" ? (
                    <><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></>
                  ) : (
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                  )}
                </svg>
              </button>
              {/* Close button */}
              <button
                onClick={onClose}
                className="w-6 h-6 flex items-center justify-center rounded cursor-pointer transition-colors"
                style={{ color: "var(--text-muted)" }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>

          {/* New Run */}
          <button
            onClick={onNewRun}
            className="mx-3 mt-2.5 mb-1 px-2 py-1.5 text-[10px] uppercase tracking-wider font-semibold rounded border border-[var(--border)] bg-transparent transition-colors cursor-pointer"
            style={{ color: "var(--text-muted)" }}
          >
            + New Run
          </button>

          {/* Runs label */}
          <div
            className="px-3 pt-3 pb-1 text-[10px] uppercase tracking-widest font-semibold"
            style={{ color: "var(--text-muted)" }}
          >
            History
          </div>

          {/* Run list */}
          <div className="flex-1 overflow-y-auto">
            {sorted.map((run) => (
              <RunHistoryItem
                key={run.id}
                run={run}
                isSelected={run.id === selectedRunId}
                onClick={() => onSelectRun(run.id)}
              />
            ))}
            {sorted.length === 0 && (
              <p className="text-xs px-3 py-4 text-center" style={{ color: "var(--text-muted)" }}>
                No runs yet
              </p>
            )}
          </div>
        </aside>
      </>
    );
  }

  // Desktop: unchanged
  return (
    <aside className="w-44 bg-[var(--sidebar-bg)] border-r border-[var(--border)] flex flex-col">
      {/* Header */}
      <div className="px-3 h-10 border-b border-[var(--border)] flex items-center justify-between">
        <button
          onClick={onNewRun}
          className="flex items-center gap-1.5 cursor-pointer transition-opacity hover:opacity-80"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <rect width="24" height="24" rx="4" fill="var(--accent)" />
            <text x="12" y="17" textAnchor="middle" fill="white" fontSize="14" fontWeight="700" fontFamily="Arial, sans-serif">U</text>
          </svg>
          <span
            className="text-[11px] uppercase tracking-widest font-semibold"
            style={{ color: "var(--text-muted)" }}
          >
            Dev Console
          </span>
        </button>
        <button
          onClick={toggleTheme}
          className="w-6 h-6 flex items-center justify-center rounded cursor-pointer transition-colors"
          style={{ color: "var(--text-muted)" }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {theme === "dark" ? (
              <><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></>
            ) : (
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            )}
          </svg>
        </button>
      </div>

      {/* New Run */}
      <button
        onClick={onNewRun}
        className="mx-3 mt-2.5 mb-1 px-2 py-1 text-[10px] uppercase tracking-wider font-semibold rounded border border-[var(--border)] bg-transparent transition-colors cursor-pointer"
        style={{ color: "var(--text-muted)" }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = "var(--text-primary)";
          e.currentTarget.style.borderColor = "var(--text-muted)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = "var(--text-muted)";
          e.currentTarget.style.borderColor = "var(--border)";
        }}
      >
        + New Run
      </button>

      {/* Runs label */}
      <div
        className="px-3 pt-3 pb-1 text-[10px] uppercase tracking-widest font-semibold"
        style={{ color: "var(--text-muted)" }}
      >
        History
      </div>

      {/* Run list */}
      <div className="flex-1 overflow-y-auto">
        {sorted.map((run) => (
          <RunHistoryItem
            key={run.id}
            run={run}
            isSelected={run.id === selectedRunId}
            onClick={() => onSelectRun(run.id)}
          />
        ))}
        {sorted.length === 0 && (
          <p className="text-xs px-3 py-4 text-center" style={{ color: "var(--text-muted)" }}>
            No runs yet
          </p>
        )}
      </div>
    </aside>
  );
}
