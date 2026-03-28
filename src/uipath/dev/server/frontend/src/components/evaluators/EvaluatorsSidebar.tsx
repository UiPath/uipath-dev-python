import { useState } from "react";
import { useEvalStore } from "../../store/useEvalStore";
import { useHashRoute } from "../../hooks/useHashRoute";
import { useToastStore } from "../../store/useToastStore";
import { scaffoldCustomEvaluator } from "../../api/eval-client";

const categories: { type: string; label: string; badgeColor: string }[] = [
  { type: "deterministic", label: "Deterministic", badgeColor: "var(--success)" },
  { type: "llm", label: "LLM Judge", badgeColor: "#a78bfa" },
  { type: "tool", label: "Tool-Based", badgeColor: "var(--info)" },
];

export default function EvaluatorsSidebar() {
  const localEvaluators = useEvalStore((s) => s.localEvaluators);
  const { evaluatorFilter, evaluatorCreateType, navigate } = useHashRoute();
  const addToast = useToastStore((s) => s.addToast);
  const [customName, setCustomName] = useState("");
  const [showCustom, setShowCustom] = useState(false);
  const [scaffolding, setScaffolding] = useState(false);

  const handleScaffold = async () => {
    if (!customName.trim()) return;
    setScaffolding(true);
    try {
      const result = await scaffoldCustomEvaluator({ name: customName.trim() });
      addToast("success", `Created ${result.filename} — implement evaluate() then run: uv run uipath register evaluator ${result.filename}`);
      setCustomName("");
      setShowCustom(false);
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail;
      addToast("error", detail ?? "Failed to scaffold evaluator");
    } finally {
      setScaffolding(false);
    }
  };

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

      {/* Create Custom */}
      {showCustom ? (
        <div className="mx-3 mb-1 p-2 rounded border" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
          <input
            type="text"
            value={customName}
            onChange={(e) => setCustomName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleScaffold(); if (e.key === "Escape") setShowCustom(false); }}
            placeholder="e.g. DiscountEvaluator"
            autoFocus
            className="w-full rounded px-2 py-1 text-[11px] mb-1.5"
            style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
          <div className="flex gap-1.5">
            <button
              onClick={handleScaffold}
              disabled={scaffolding || !customName.trim()}
              className="flex-1 py-1 text-[10px] font-semibold rounded cursor-pointer disabled:opacity-40"
              style={{ background: "var(--accent)", color: "var(--bg-primary)", border: "none" }}
            >
              {scaffolding ? "Creating..." : "Create"}
            </button>
            <button
              onClick={() => setShowCustom(false)}
              className="px-2 py-1 text-[10px] rounded cursor-pointer"
              style={{ color: "var(--text-muted)", background: "transparent", border: "1px solid var(--border)" }}
            >
              Cancel
            </button>
          </div>
          <a
            href="https://uipath.github.io/uipath-python/eval/custom_evaluators/"
            target="_blank"
            rel="noopener noreferrer"
            className="block mt-1.5 text-[10px] no-underline"
            style={{ color: "var(--accent)" }}
          >
            Custom evaluator docs &rarr;
          </a>
        </div>
      ) : (
        <button
          onClick={() => setShowCustom(true)}
          className="mx-3 mb-1 px-3 py-1.5 text-[11px] font-medium rounded border border-dashed transition-colors cursor-pointer"
          style={{ color: "var(--text-muted)", borderColor: "var(--border)", background: "transparent" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "var(--text-primary)";
            e.currentTarget.style.borderColor = "var(--text-muted)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "var(--text-muted)";
            e.currentTarget.style.borderColor = "var(--border)";
          }}
        >
          + Custom Evaluator (Python)
        </button>
      )}

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
