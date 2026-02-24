import { useEvalStore } from "../../store/useEvalStore";
import { useHashRoute } from "../../hooks/useHashRoute";

function formatScore(score: number | null): string {
  if (score === null) return "-";
  return `${Math.round(score * 100)}%`;
}

function scoreColor(score: number | null): string {
  if (score === null) return "var(--text-muted)";
  const pct = score * 100;
  if (pct >= 80) return "var(--success)";
  if (pct >= 50) return "var(--warning)";
  return "var(--error)";
}

const statusIcons: Record<string, { color: string; label: string }> = {
  pending: { color: "var(--text-muted)", label: "Pending" },
  running: { color: "var(--info)", label: "Running" },
  completed: { color: "var(--success)", label: "Completed" },
  failed: { color: "var(--error)", label: "Failed" },
};

export default function EvalsSidebar() {
  const evalSets = useEvalStore((s) => s.evalSets);
  const evalRuns = useEvalStore((s) => s.evalRuns);
  const { evalSetId, evalRunId, navigate } = useHashRoute();

  const sets = Object.values(evalSets);
  const runs = Object.values(evalRuns).sort(
    (a, b) => new Date(b.start_time ?? 0).getTime() - new Date(a.start_time ?? 0).getTime(),
  );

  return (
    <div className="flex-1 overflow-y-auto">
      {/* New Eval Set */}
      <button
        onClick={() => navigate("#/evals/new")}
        className="w-[calc(100%-24px)] mx-3 mt-2.5 mb-1 px-3 py-1.5 text-[11px] text-center font-medium rounded border border-[var(--border)] bg-transparent transition-colors cursor-pointer"
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
        + New Eval Set
      </button>

      {/* Eval Sets */}
      <div
        className="px-3 pt-3 pb-1 text-[11px] uppercase tracking-widest font-semibold"
        style={{ color: "var(--text-muted)" }}
      >
        Eval Sets
      </div>
      {sets.map((es) => {
        const active = evalSetId === es.id;
        return (
          <button
            key={es.id}
            onClick={() => navigate(`#/evals/sets/${es.id}`)}
            className="w-full text-left px-3 py-1.5 text-xs cursor-pointer transition-colors"
            style={{
              background: active ? "color-mix(in srgb, var(--accent) 15%, var(--bg-primary))" : "transparent",
              color: active ? "var(--text-primary)" : "var(--text-secondary)",
              borderLeft: active ? "3px solid var(--accent)" : "3px solid transparent",
            }}
            onMouseEnter={(e) => {
              if (!active) e.currentTarget.style.background = "var(--bg-hover)";
            }}
            onMouseLeave={(e) => {
              if (!active) e.currentTarget.style.background = "transparent";
            }}
          >
            <div className="truncate font-medium">{es.name}</div>
            <div className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>
              {es.eval_count} items · {es.evaluator_ids.length} evaluator{es.evaluator_ids.length !== 1 ? "s" : ""}
            </div>
          </button>
        );
      })}
      {sets.length === 0 && (
        <p className="text-[11px] px-3 py-2" style={{ color: "var(--text-muted)" }}>
          No eval sets yet
        </p>
      )}

      {/* Run History */}
      <div
        className="px-3 pt-4 pb-1 text-[11px] uppercase tracking-widest font-semibold"
        style={{ color: "var(--text-muted)" }}
      >
        History
      </div>
      {runs.map((run) => {
        const active = evalRunId === run.id;
        const si = statusIcons[run.status] ?? statusIcons.pending;
        return (
          <button
            key={run.id}
            onClick={() => navigate(`#/evals/runs/${run.id}`)}
            className="w-full text-left px-3 py-1.5 text-xs cursor-pointer transition-colors"
            style={{
              background: active ? "color-mix(in srgb, var(--accent) 15%, var(--bg-primary))" : "transparent",
              color: active ? "var(--text-primary)" : "var(--text-secondary)",
              borderLeft: active ? "3px solid var(--accent)" : "3px solid transparent",
            }}
            onMouseEnter={(e) => {
              if (!active) e.currentTarget.style.background = "var(--bg-hover)";
            }}
            onMouseLeave={(e) => {
              if (!active) e.currentTarget.style.background = "transparent";
            }}
          >
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ background: si.color }} />
              <div className="flex-1 min-w-0">
                <div className="truncate font-medium">{run.eval_set_name}</div>
                <div className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                  {run.start_time ? new Date(run.start_time).toLocaleString() : si.label}
                </div>
              </div>
              <span className="font-mono shrink-0" style={{ color: scoreColor(run.overall_score) }}>
                {formatScore(run.overall_score)}
              </span>
            </div>
          </button>
        );
      })}
      {runs.length === 0 && (
        <p className="text-[11px] px-3 py-2" style={{ color: "var(--text-muted)" }}>
          No eval runs yet
        </p>
      )}
    </div>
  );
}
