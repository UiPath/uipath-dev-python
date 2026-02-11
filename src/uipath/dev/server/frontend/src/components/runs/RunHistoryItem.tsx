import type { RunSummary } from "../../types/run";

const STATUS_ICONS: Record<string, string> = {
  pending: "\u25CF",
  running: "\u25B6",
  suspended: "\u23F8",
  completed: "\u2714",
  failed: "\u2716",
};

interface Props {
  run: RunSummary;
  isSelected: boolean;
  statusColor: string;
  onClick: () => void;
}

export default function RunHistoryItem({ run, isSelected, statusColor, onClick }: Props) {
  const icon = STATUS_ICONS[run.status] ?? "?";
  const name = run.entrypoint.split("/").pop()?.slice(0, 12) ?? run.entrypoint;
  const time = run.start_time
    ? new Date(run.start_time).toLocaleTimeString()
    : "";

  return (
    <button
      onClick={onClick}
      className={`w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-[var(--bg-hover)] transition-colors ${
        isSelected ? "bg-[var(--bg-hover)] border-l-2 border-[var(--accent)]" : ""
      }`}
    >
      <span className={statusColor}>{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="truncate text-[var(--text-primary)]">{name}</div>
        <div className="text-xs text-[var(--text-muted)]">
          {time} {run.duration && `[${run.duration}]`}
        </div>
      </div>
    </button>
  );
}
