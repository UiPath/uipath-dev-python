import { useEffect, useMemo, useRef, useState } from "react";
import type { RunSummary } from "../../types/run";
import type { LocalEvaluator } from "../../types/eval";
import { useEvalStore } from "../../store/useEvalStore";
import { listEvalSets, listLocalEvaluators, addEvalItem } from "../../api/eval-client";

interface Props {
  run: RunSummary;
  onClose: () => void;
}

/** Maps evaluator_type_id → default criteria given the run output. */
const CRITERIA_TEMPLATES: Record<
  string,
  (output: unknown) => Record<string, unknown>
> = {
  "uipath-exact-match": (o) => ({ expectedOutput: o }),
  "uipath-json-similarity": (o) => ({ expectedOutput: o }),
  "uipath-contains": () => ({ searchText: "" }),
  "uipath-llm-judge-output-semantic-similarity": (o) => ({
    expectedOutput: o,
  }),
  "uipath-llm-judge-output-strict-json-similarity": (o) => ({
    expectedOutput: o,
  }),
  "uipath-llm-judge-trajectory-similarity": () => ({
    expectedAgentBehavior: "",
  }),
  "uipath-llm-judge-trajectory-simulation": () => ({
    expectedAgentBehavior: "",
  }),
  "uipath-tool-call-count": () => ({}),
  "uipath-tool-call-args": () => ({}),
  "uipath-tool-call-order": () => ({}),
  "uipath-tool-call-output": () => ({}),
};

/** Build default criteria for an evaluator, with category-based fallback. */
function getDefaultCriteria(
  ev: LocalEvaluator | undefined,
  output: unknown,
): Record<string, unknown> {
  if (!ev) return {};
  const template = CRITERIA_TEMPLATES[ev.evaluator_type_id];
  if (template) return template(output);
  // Fallback: infer from type/category
  if (ev.type === "tool") return {};
  if (ev.evaluator_type_id.includes("trajectory")) return { expectedAgentBehavior: "" };
  return { expectedOutput: output };
}

function isToolEvaluator(ev: LocalEvaluator | undefined): boolean {
  if (!ev) return false;
  if (ev.type === "tool") return true;
  return ev.evaluator_type_id.includes("tool-call");
}

function getCategoryBadge(ev: LocalEvaluator | undefined): { label: string; color: string } {
  if (!ev) return { label: "output", color: "var(--success, #22c55e)" };
  if (isToolEvaluator(ev))
    return { label: "tools", color: "var(--warning, #e5a00d)" };
  if (ev.evaluator_type_id.includes("trajectory"))
    return { label: "quality", color: "var(--info, #3b82f6)" };
  return { label: "output", color: "var(--success, #22c55e)" };
}

export default function AddToEvalModal({ run, onClose }: Props) {
  const evalSets = useEvalStore((s) => s.evalSets);
  const setEvalSets = useEvalStore((s) => s.setEvalSets);
  const incrementEvalSetCount = useEvalStore((s) => s.incrementEvalSetCount);
  const localEvaluators = useEvalStore((s) => s.localEvaluators);
  const setLocalEvaluators = useEvalStore((s) => s.setLocalEvaluators);

  const [name, setName] = useState(`run-${run.id.slice(0, 8)}`);
  const [selectedSets, setSelectedSets] = useState<Set<string>>(new Set());
  const [criteriaMap, setCriteriaMap] = useState<Record<string, string>>({});
  const userEditedRef = useRef(new Set<string>());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const setsList = Object.values(evalSets);

  // Build a lookup: evaluator id → LocalEvaluator
  const evaluatorById = useMemo(
    () => Object.fromEntries(localEvaluators.map((e) => [e.id, e])),
    [localEvaluators],
  );

  // Collect unique evaluator IDs across all selected eval sets
  const selectedEvaluatorIds = useMemo(() => {
    const ids = new Set<string>();
    for (const setId of selectedSets) {
      const es = evalSets[setId];
      if (es) es.evaluator_ids.forEach((id) => ids.add(id));
    }
    return [...ids];
  }, [selectedSets, evalSets]);

  // Initialize criteria map when selected evaluators change
  useEffect(() => {
    const output = run.output_data;
    const edited = userEditedRef.current;
    setCriteriaMap((prev) => {
      const next: Record<string, string> = {};
      for (const evId of selectedEvaluatorIds) {
        if (edited.has(evId) && prev[evId] !== undefined) {
          // Preserve user edits
          next[evId] = prev[evId];
        } else {
          // (Re)generate default from evaluator type with category fallback
          const ev = evaluatorById[evId];
          const defaultCriteria = getDefaultCriteria(ev, output);
          next[evId] = JSON.stringify(defaultCriteria, null, 2);
        }
      }
      return next;
    });
  }, [selectedEvaluatorIds, evaluatorById, run.output_data]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (setsList.length === 0) {
      listEvalSets().then(setEvalSets).catch(() => {});
    }
    if (localEvaluators.length === 0) {
      listLocalEvaluators().then(setLocalEvaluators).catch(() => {});
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleSet = (id: string) => {
    setSelectedSets((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!name.trim() || selectedSets.size === 0) return;
    setError(null);
    setSubmitting(true);

    // Parse each evaluator's criteria JSON
    const evaluationCriterias: Record<string, Record<string, unknown>> = {};
    for (const evId of selectedEvaluatorIds) {
      const raw = criteriaMap[evId];
      if (raw !== undefined) {
        try {
          evaluationCriterias[evId] = JSON.parse(raw);
        } catch {
          setError(`Invalid JSON for evaluator "${evaluatorById[evId]?.name ?? evId}"`);
          setSubmitting(false);
          return;
        }
      }
    }

    try {
      for (const setId of selectedSets) {
        // Only send criteria for evaluators that belong to this eval set
        const es = evalSets[setId];
        const setEvIds = new Set(es?.evaluator_ids ?? []);
        const setCriterias: Record<string, Record<string, unknown>> = {};
        for (const [evId, criteria] of Object.entries(evaluationCriterias)) {
          if (setEvIds.has(evId)) setCriterias[evId] = criteria;
        }

        await addEvalItem(setId, {
          name: name.trim(),
          inputs: run.input_data,
          expected_output: null,
          evaluation_criterias: setCriterias,
        });
        incrementEvalSetCount(setId);
      }
      setSuccess(true);
      setTimeout(onClose, 3000);
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to add item");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0, 0, 0, 0.5)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-2xl rounded-lg p-6 shadow-xl max-h-[85vh] flex flex-col"
        style={{ background: "var(--bg-primary)", border: "1px solid var(--border)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent)" }} />
            <span
              className="text-sm font-semibold"
              style={{ color: "var(--text-muted)" }}
            >
              Add to Eval Set
            </span>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded cursor-pointer transition-colors"
            style={{ color: "var(--text-muted)", background: "transparent", border: "none" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
            aria-label="Close"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto min-h-0 space-y-4 pr-1">
          {/* Item name */}
          <div>
            <label
              className="block text-[11px] font-medium mb-1.5"
              style={{ color: "var(--text-muted)" }}
            >
              Item Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md px-3 py-2 text-xs"
              style={{
                background: "var(--bg-secondary)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
            />
          </div>

          {/* Inputs (read-only) */}
          <div>
            <label
              className="block text-[11px] font-medium mb-1.5"
              style={{ color: "var(--text-muted)" }}
            >
              Inputs
            </label>
            <pre
              className="rounded-md px-3 py-2 text-xs font-mono whitespace-pre-wrap break-words max-h-32 overflow-y-auto"
              style={{
                background: "var(--bg-secondary)",
                border: "1px solid var(--border)",
                color: "var(--text-secondary)",
              }}
            >
              {JSON.stringify(run.input_data, null, 2)}
            </pre>
          </div>

          {/* Eval set selection */}
          <div>
            <label
              className="block text-[11px] font-medium mb-1.5"
              style={{ color: "var(--text-muted)" }}
            >
              Eval Sets
            </label>
            {setsList.length === 0 ? (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                No eval sets found. Create one first.
              </p>
            ) : (
              <div
                className="rounded-md border overflow-hidden max-h-40 overflow-y-auto"
                style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
              >
                {setsList.map((es) => (
                  <label
                    key={es.id}
                    className="flex items-center gap-2.5 px-3 py-2 text-xs cursor-pointer transition-colors"
                    style={{ borderBottom: "1px solid var(--border)" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedSets.has(es.id)}
                      onChange={() => toggleSet(es.id)}
                      className="accent-[var(--accent)]"
                    />
                    <span className="flex-1 truncate" style={{ color: "var(--text-primary)" }}>
                      {es.name}
                    </span>
                    <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                      {es.eval_count} items
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Per-evaluator criteria editors */}
          {selectedEvaluatorIds.length > 0 && (
            <div>
              <label
                className="block text-[11px] font-medium mb-1.5"
                style={{ color: "var(--text-muted)" }}
              >
                Evaluation Criteria
              </label>
              <div className="space-y-2">
                {selectedEvaluatorIds.map((evId) => {
                  const ev = evaluatorById[evId];
                  const isTool = isToolEvaluator(ev);
                  const badge = getCategoryBadge(ev);

                  return (
                    <div
                      key={evId}
                      className="rounded-md"
                      style={{
                        border: "1px solid var(--border)",
                        background: "var(--bg-primary)",
                        opacity: isTool ? 0.6 : 1,
                      }}
                    >
                      {/* Card header */}
                      <div
                        className="flex items-center gap-2 px-3 py-2"
                        style={{ borderBottom: isTool ? "none" : "1px solid var(--border)" }}
                      >
                        <span
                          className="text-xs font-medium truncate flex-1"
                          style={{ color: "var(--text-primary)" }}
                        >
                          {ev?.name ?? evId}
                        </span>
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                          style={{
                            color: badge.color,
                            background: `color-mix(in srgb, ${badge.color} 12%, transparent)`,
                          }}
                        >
                          {badge.label}
                        </span>
                      </div>
                      {/* Card body */}
                      {isTool ? (
                        <div className="px-3 pb-2">
                          <span
                            className="text-[10px] italic"
                            style={{ color: "var(--text-muted)" }}
                          >
                            Default criteria — uses evaluator config
                          </span>
                        </div>
                      ) : (
                        <div className="px-3 pb-2 pt-1">
                          <textarea
                            value={criteriaMap[evId] ?? "{}"}
                            onChange={(e) => {
                              userEditedRef.current.add(evId);
                              setCriteriaMap((prev) => ({ ...prev, [evId]: e.target.value }));
                            }}
                            rows={8}
                            className="w-full rounded px-2 py-1.5 text-xs font-mono resize-y"
                            style={{
                              background: "var(--bg-secondary)",
                              border: "1px solid var(--border)",
                              color: "var(--text-primary)",
                            }}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer — outside scrollable area */}
        <div className="mt-4 space-y-3">
          {/* Error */}
          {error && (
            <p className="text-xs px-3 py-2 rounded" style={{ color: "var(--error)", background: "color-mix(in srgb, var(--error) 10%, var(--bg-secondary))" }}>{error}</p>
          )}

          {/* Success */}
          {success && (
            <p className="text-xs px-3 py-2 rounded" style={{ color: "var(--success)", background: "color-mix(in srgb, var(--success) 10%, var(--bg-secondary))" }}>
              Added to {selectedSets.size} eval set{selectedSets.size !== 1 ? "s" : ""}.
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="flex-1 py-2 rounded-md text-xs font-semibold cursor-pointer"
              style={{
                background: "var(--bg-secondary)",
                color: "var(--text-secondary)",
                border: "1px solid var(--border)",
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!name.trim() || selectedSets.size === 0 || submitting || success}
              className="flex-1 py-2 rounded-md text-[13px] font-semibold transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                background: "var(--accent)",
                color: "var(--bg-primary)",
                border: "none",
              }}
            >
              {submitting ? "Adding..." : success ? "Added" : "Add Item"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
