import type { RunSummary } from "../../types/run";
import RunHistoryItem from "../runs/RunHistoryItem";

interface Props {
  runs: RunSummary[];
  selectedRunId: string | null;
  onSelectRun: (id: string) => void;
  onNewRun: () => void;
}

export default function DebugSidebar({ runs, selectedRunId, onSelectRun, onNewRun }: Props) {
  const sorted = [...runs].sort(
    (a, b) =>
      new Date(b.start_time ?? 0).getTime() -
      new Date(a.start_time ?? 0).getTime(),
  );

  return (
    <>
      {/* New Run */}
      <button
        onClick={onNewRun}
        className="mx-3 mt-2.5 mb-1 px-3 py-1.5 text-[11px] font-medium rounded border border-[var(--border)] bg-transparent transition-colors cursor-pointer"
        style={{ color: "var(--text-secondary)" }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = "var(--text-primary)";
          e.currentTarget.style.borderColor = "var(--text-muted)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = "var(--text-secondary)";
          e.currentTarget.style.borderColor = "";
        }}
      >
        + New Run
      </button>

      {/* Runs label */}
      <div
        className="px-3 pt-3 pb-1 text-[11px] uppercase tracking-widest font-semibold"
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
    </>
  );
}
