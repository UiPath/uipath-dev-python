import { useState } from "react";
import { useEvalStore } from "../../store/useEvalStore";
import { useHashRoute } from "../../hooks/useHashRoute";
import { createEvalSet } from "../../api/eval-client";

const typeBadgeColors: Record<string, string> = {
  deterministic: "var(--success)",
  llm: "#a78bfa",
  tool: "var(--info)",
};

export default function CreateEvalSetView() {
  const localEvaluators = useEvalStore((s) => s.localEvaluators);
  const addEvalSet = useEvalStore((s) => s.addEvalSet);
  const { navigate } = useHashRoute();

  const [name, setName] = useState("");
  const [selectedRefs, setSelectedRefs] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const toggleRef = (id: string) => {
    setSelectedRefs((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      const created = await createEvalSet({
        name: name.trim(),
        evaluator_refs: Array.from(selectedRefs),
      });
      addEvalSet(created);
      navigate(`#/evals/sets/${created.id}`);
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to create eval set");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-xl px-6">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent)" }} />
            <span className="text-sm font-semibold" style={{ color: "var(--text-muted)" }}>
              New Eval Set
            </span>
          </div>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Create an evaluation set with a name and evaluators
          </p>
        </div>

        {/* Name */}
        <div className="mb-6">
          <label
            className="block text-[11px] font-medium mb-1.5"
            style={{ color: "var(--text-muted)" }}
          >
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Basic QA Tests"
            className="w-full rounded-md px-3 py-2 text-xs"
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && name.trim()) handleCreate();
            }}
          />
        </div>

        {/* Evaluators */}
        <div className="mb-6">
          <label
            className="block text-[11px] font-medium mb-1.5"
            style={{ color: "var(--text-muted)" }}
          >
            Evaluators
          </label>
          {localEvaluators.length === 0 ? (
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              No evaluators configured.{" "}
              <button
                onClick={() => navigate("#/evaluators/new")}
                className="underline cursor-pointer"
                style={{ color: "var(--accent)", background: "none", border: "none", padding: 0, font: "inherit" }}
              >
                Create one first
              </button>
            </p>
          ) : (
            <div
              className="rounded-md border overflow-hidden"
              style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
            >
              {localEvaluators.map((ev) => (
                <label
                  key={ev.id}
                  className="flex items-center gap-2.5 px-3 py-2 text-xs cursor-pointer transition-colors"
                  style={{ borderBottom: "1px solid var(--border)" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  <input
                    type="checkbox"
                    checked={selectedRefs.has(ev.id)}
                    onChange={() => toggleRef(ev.id)}
                    className="accent-[var(--accent)]"
                  />
                  <span className="flex-1 truncate" style={{ color: "var(--text-primary)" }}>{ev.name}</span>
                  <span
                    className="text-[11px] font-medium px-1.5 py-0.5 rounded"
                    style={{
                      background: `color-mix(in srgb, ${typeBadgeColors[ev.type] ?? "var(--text-muted)"} 15%, transparent)`,
                      color: typeBadgeColors[ev.type] ?? "var(--text-muted)",
                    }}
                  >
                    {ev.type}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <p className="text-xs mb-4 px-3 py-2 rounded" style={{ color: "var(--error)", background: "color-mix(in srgb, var(--error) 10%, var(--bg-secondary))" }}>{error}</p>
        )}

        {/* Create button */}
        <button
          onClick={handleCreate}
          disabled={!name.trim() || submitting}
          className="w-full py-2 rounded-md text-[13px] font-semibold transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          style={{
            background: "var(--accent)",
            color: "var(--bg-primary)",
            border: "none",
          }}
        >
          {submitting ? "Creating..." : "Create Eval Set"}
        </button>
      </div>
    </div>
  );
}
