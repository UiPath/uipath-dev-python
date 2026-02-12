import type { RunSummary } from "../../types/run";
import { useTheme } from "../../store/useTheme";
import RunHistoryItem from "../runs/RunHistoryItem";

interface Props {
  runs: RunSummary[];
  selectedRunId: string | null;
  onSelectRun: (id: string) => void;
  onNewRun: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "text-[var(--text-muted)]",
  running: "text-[var(--warning)]",
  suspended: "text-[var(--info)]",
  completed: "text-[var(--success)]",
  failed: "text-[var(--error)]",
};

export default function Sidebar({ runs, selectedRunId, onSelectRun, onNewRun }: Props) {
  const { theme, toggleTheme } = useTheme();

  const sorted = [...runs].sort(
    (a, b) =>
      new Date(b.start_time ?? 0).getTime() -
      new Date(a.start_time ?? 0).getTime(),
  );

  return (
    <aside className="w-48 bg-[var(--sidebar-bg)] border-r border-[var(--border)] flex flex-col">
      <div className="p-3 border-b border-[var(--border)] flex items-center justify-between">
        <h1 className="text-sm font-semibold text-[var(--text-primary)]">UiPath Dev Console</h1>
        <button
          onClick={toggleTheme}
          className="w-7 h-4 rounded-full relative transition-colors"
          style={{
            background: theme === "dark"
              ? "var(--text-muted)"
              : "var(--accent)",
          }}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          <span
            className="absolute top-0.5 w-3 h-3 rounded-full transition-all"
            style={{
              background: "var(--bg-primary)",
              left: theme === "dark" ? "2px" : "14px",
            }}
          />
        </button>
      </div>

      <button
        onClick={onNewRun}
        className="mx-3 mt-3 px-3 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm rounded transition-colors"
      >
        + New Run
      </button>

      <div className="flex-1 overflow-y-auto mt-3">
        {sorted.map((run) => (
          <RunHistoryItem
            key={run.id}
            run={run}
            isSelected={run.id === selectedRunId}
            statusColor={STATUS_COLORS[run.status] ?? "text-[var(--text-muted)]"}
            onClick={() => onSelectRun(run.id)}
          />
        ))}
        {sorted.length === 0 && (
          <p className="text-sm text-[var(--text-muted)] px-3 py-4 text-center">
            No runs yet
          </p>
        )}
      </div>
    </aside>
  );
}
