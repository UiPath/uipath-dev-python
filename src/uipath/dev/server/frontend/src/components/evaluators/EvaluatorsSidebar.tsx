import { useEvalStore } from "../../store/useEvalStore";
import { useHashRoute } from "../../hooks/useHashRoute";

const categories: { type: string; label: string; badgeColor: string }[] = [
  { type: "deterministic", label: "Deterministic", badgeColor: "var(--success)" },
  { type: "llm", label: "LLM Judge", badgeColor: "#a78bfa" },
  { type: "tool", label: "Tool-Based", badgeColor: "var(--info)" },
];

export default function EvaluatorsSidebar() {
  const localEvaluators = useEvalStore((s) => s.localEvaluators);
  const { evaluatorFilter, evaluatorCreateType, navigate } = useHashRoute();

  // "All" is active when on #/evaluators (no filter, no create, no detail)
  const isAllActive = !evaluatorFilter && !evaluatorCreateType;

  return (
    <>
      {/* New Evaluator */}
      <button
        onClick={() => navigate("#/evaluators/new")}
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
        + New Evaluator
      </button>

      {/* Categories label */}
      <div className="px-3 pt-3 pb-1 text-[11px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-muted)" }}>
        Categories
      </div>

      {/* Category list */}
      <div className="flex-1 overflow-y-auto">
        {/* All */}
        <button
          onClick={() => navigate("#/evaluators")}
          className="w-full text-left px-3 py-2 text-xs flex items-center gap-2 cursor-pointer transition-colors"
          style={{
            background: isAllActive ? "color-mix(in srgb, var(--accent) 15%, var(--bg-primary))" : "transparent",
            color: isAllActive ? "var(--text-primary)" : "var(--text-secondary)",
            borderLeft: isAllActive ? "3px solid var(--accent)" : "3px solid transparent",
          }}
          onMouseEnter={(e) => {
            if (!isAllActive) e.currentTarget.style.background = "var(--bg-hover)";
          }}
          onMouseLeave={(e) => {
            if (!isAllActive) e.currentTarget.style.background = "transparent";
          }}
        >
          <div
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: "var(--text-muted)" }}
          />
          <span className="flex-1 truncate">All</span>
          {localEvaluators.length > 0 && (
            <span className="text-[10px] px-1.5 rounded-full" style={{ background: "var(--bg-tertiary)", color: "var(--text-muted)" }}>
              {localEvaluators.length}
            </span>
          )}
        </button>

        {categories.map((cat) => {
          const count = localEvaluators.filter((e) => e.type === cat.type).length;
          const active = evaluatorFilter === cat.type;
          return (
            <button
              key={cat.type}
              onClick={() => navigate(active ? "#/evaluators" : `#/evaluators/category/${cat.type}`)}
              className="w-full text-left px-3 py-2 text-xs flex items-center gap-2 cursor-pointer transition-colors"
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
              <div
                className="w-2 h-2 rounded-full shrink-0"
                style={{ background: cat.badgeColor }}
              />
              <span className="flex-1 truncate">{cat.label}</span>
              {count > 0 && (
                <span className="text-[10px] px-1.5 rounded-full" style={{ background: "var(--bg-tertiary)", color: "var(--text-muted)" }}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </>
  );
}
