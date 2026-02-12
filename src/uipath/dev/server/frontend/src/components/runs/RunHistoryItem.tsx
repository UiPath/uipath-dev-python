import type { RunSummary } from "../../types/run";

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

  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-1.5 flex items-center gap-2 transition-colors cursor-pointer"
      style={{
        background: isSelected
          ? "color-mix(in srgb, var(--accent) 8%, var(--bg-primary))"
          : undefined,
        borderLeft: isSelected ? "2px solid var(--accent)" : "2px solid transparent",
      }}
      onMouseEnter={(e) => {
        if (!isSelected) e.currentTarget.style.background = "var(--bg-hover)";
      }}
      onMouseLeave={(e) => {
        if (!isSelected) e.currentTarget.style.background = "";
      }}
    >
      {/* Status dot */}
      <span
        className="shrink-0 w-1.5 h-1.5 rounded-full"
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
        <div className="text-[10px] tabular-nums" style={{ color: "var(--text-muted)" }}>
          {time}{run.duration ? ` \u00b7 ${run.duration}` : ""}
        </div>
      </div>
    </button>
  );
}
