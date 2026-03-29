import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useEvalStore } from "../../store/useEvalStore";
import { useHashRoute } from "../../hooks/useHashRoute";
import { listLocalEvaluators, listLlmModels, updateLocalEvaluator } from "../../api/eval-client";
import type { EvaluatorInfo, LocalEvaluator } from "../../types/eval";

// --- Badge styles ---
const typeBadge: Record<string, { label: string; color: string; bg: string }> = {
  deterministic: { label: "Deterministic", color: "var(--success)", bg: "rgba(34,197,94,0.1)" },
  llm: { label: "LLM Judge", color: "#a78bfa", bg: "rgba(167,139,250,0.1)" },
  tool: { label: "Tool-Based", color: "var(--info)", bg: "rgba(59,130,246,0.1)" },
};

export const categoryLabel: Record<string, string> = {
  deterministic: "Deterministic",
  llm: "LLM Judge",
  tool: "Tool-Based",
};

// Built-in evaluator types grouped by category
export const typesByCategory: Record<string, { id: string; name: string }[]> = {
  deterministic: [
    { id: "uipath-exact-match", name: "Exact Match" },
    { id: "uipath-contains", name: "Contains" },
    { id: "uipath-json-similarity", name: "JSON Similarity" },
  ],
  llm: [
    { id: "uipath-llm-judge-output-semantic-similarity", name: "LLM Judge Output" },
    { id: "uipath-llm-judge-output-strict-json-similarity", name: "LLM Judge Strict JSON" },
    { id: "uipath-llm-judge-trajectory-similarity", name: "LLM Judge Trajectory" },
    { id: "uipath-llm-judge-trajectory-simulation", name: "LLM Judge Trajectory Simulation" },
  ],
  tool: [
    { id: "uipath-tool-call-order", name: "Tool Call Order" },
    { id: "uipath-tool-call-args", name: "Tool Call Args" },
    { id: "uipath-tool-call-count", name: "Tool Call Count" },
    { id: "uipath-tool-call-output", name: "Tool Call Output" },
  ],
};

// Which types show which extra fields (legacy, kept for compatibility)
export function getTypeFields(typeId: string): { targetOutputKey: boolean; prompt: boolean } {
  if (typeId.includes("trajectory")) return { targetOutputKey: false, prompt: true };
  if (typeId.includes("llm-judge")) return { targetOutputKey: true, prompt: true };
  if (typeId.includes("tool-call-output")) return { targetOutputKey: true, prompt: false };
  if (typeId.includes("exact-match") || typeId.includes("contains") || typeId.includes("json-similarity")) {
    return { targetOutputKey: true, prompt: false };
  }
  return { targetOutputKey: false, prompt: false };
}

// Fields managed at the evaluator level (name/description handled separately)
const SKIP_CONFIG_FIELDS = new Set(["name", "description", "default_evaluation_criteria"]);

interface ConfigFieldDef {
  key: string;
  title: string;
  description?: string;
  type: string; // "string" | "boolean" | "number" | "integer"
  default_value: unknown;
  is_nullable: boolean;
}

/** Extract renderable config fields from an evaluatorConfigSchema. */
export function getSchemaConfigFields(configSchema: Record<string, unknown>): ConfigFieldDef[] {
  const props = configSchema?.properties as Record<string, Record<string, unknown>> | undefined;
  if (!props) return [];

  const fields: ConfigFieldDef[] = [];
  for (const [key, prop] of Object.entries(props)) {
    if (SKIP_CONFIG_FIELDS.has(key)) continue;

    // Resolve type from "type" or from "anyOf"
    let type = prop.type as string | undefined;
    let isNullable = false;
    if (!type && Array.isArray(prop.anyOf)) {
      const nonNull = (prop.anyOf as Record<string, unknown>[]).filter((a) => a.type !== "null");
      if (nonNull.length === 1) type = nonNull[0].type as string;
      isNullable = (prop.anyOf as Record<string, unknown>[]).some((a) => a.type === "null");
    }
    if (!type) continue;

    fields.push({
      key,
      title: (prop.title as string) ?? key.replace(/_/g, " "),
      description: prop.description as string | undefined,
      type,
      default_value: prop.default,
      is_nullable: isNullable,
    });
  }
  return fields;
}

/** Render dynamic config fields from schema. */
export function SchemaConfigFields({
  fields,
  values,
  onChange,
  llmModels,
  inputStyle,
}: {
  fields: ConfigFieldDef[];
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  llmModels?: { model_name: string; vendor: string | null }[];
  inputStyle: React.CSSProperties;
}) {
  return (
    <>
      {fields.map((f) => {
        const val = values[f.key] ?? f.default_value ?? "";

        // Special: model field with LLM models dropdown
        if (f.key === "model" && llmModels && llmModels.length > 0) {
          return (
            <div key={f.key} className="mb-6">
              <label className="block text-[11px] font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>
                {f.title}
              </label>
              <select
                value={String(val)}
                onChange={(e) => onChange(f.key, e.target.value)}
                className="w-full rounded-md px-3 py-2 text-xs cursor-pointer appearance-auto"
                style={inputStyle}
              >
                <option value="">Select a model</option>
                {llmModels.map((m) => (
                  <option key={m.model_name} value={m.model_name}>
                    {m.model_name}{m.vendor ? ` (${m.vendor})` : ""}
                  </option>
                ))}
              </select>
              {f.description && <div className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>{f.description}</div>}
            </div>
          );
        }

        if (f.type === "boolean") {
          return (
            <div key={f.key} className="mb-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={Boolean(val)}
                  onChange={(e) => onChange(f.key, e.target.checked)}
                  className="accent-[var(--accent)]"
                />
                <span className="text-[11px] font-medium" style={{ color: "var(--text-muted)" }}>{f.title}</span>
              </label>
              {f.description && <div className="text-[11px] mt-0.5 pl-5" style={{ color: "var(--text-muted)" }}>{f.description}</div>}
            </div>
          );
        }

        if (f.type === "number" || f.type === "integer") {
          return (
            <div key={f.key} className="mb-6">
              <label className="block text-[11px] font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>
                {f.title}
              </label>
              <input
                type="number"
                value={val === null || val === "" ? "" : Number(val)}
                onChange={(e) => onChange(f.key, e.target.value === "" ? null : Number(e.target.value))}
                step={f.type === "integer" ? 1 : 0.1}
                className="w-full rounded-md px-3 py-2 text-xs"
                style={inputStyle}
              />
              {f.description && <div className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>{f.description}</div>}
            </div>
          );
        }

        // Default: string (textarea for prompt, input for others)
        const isLong = f.key === "prompt" || (typeof val === "string" && val.length > 100);
        return (
          <div key={f.key} className="mb-6">
            <label className="block text-[11px] font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>
              {f.title}
            </label>
            {isLong ? (
              <textarea
                value={String(val)}
                onChange={(e) => onChange(f.key, e.target.value)}
                rows={6}
                className="w-full rounded-md px-3 py-2 text-xs font-mono leading-relaxed resize-y"
                style={inputStyle}
              />
            ) : (
              <input
                type="text"
                value={String(val)}
                onChange={(e) => onChange(f.key, e.target.value)}
                className="w-full rounded-md px-3 py-2 text-xs"
                style={inputStyle}
              />
            )}
            {f.description && <div className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>{f.description}</div>}
          </div>
        );
      })}
    </>
  );
}

// Predefined defaults per evaluator type
export const typeDefaults: Record<string, { description: string; prompt: string }> = {
  "uipath-exact-match": {
    description: "Checks whether the agent output exactly matches the expected output.",
    prompt: "",
  },
  "uipath-contains": {
    description: "Checks whether the agent output contains the expected substring.",
    prompt: "",
  },
  "uipath-json-similarity": {
    description: "Compares JSON structures for semantic similarity, ignoring key ordering and whitespace.",
    prompt: "",
  },
  "uipath-llm-judge-output-semantic-similarity": {
    description: "Uses an LLM to score semantic similarity between the agent's actual output and the expected output, accounting for synonyms, paraphrases, and equivalent expressions.",
    prompt: `As an expert evaluator, analyze the semantic similarity between the expected and actual outputs and determine a score from 0 to 100. Focus on comparing meaning and contextual equivalence of corresponding fields, accounting for alternative valid expressions, synonyms, and reasonable variations in language while maintaining high standards for accuracy and completeness. Provide your score with a brief justification.
----
ExpectedOutput:
{{ExpectedOutput}}
----
ActualOutput:
{{ActualOutput}}`,
  },
  "uipath-llm-judge-output-strict-json-similarity": {
    description: "Uses an LLM to perform strict structural and value comparison between JSON outputs, checking key names, nesting, types, and values.",
    prompt: `As an expert evaluator, perform a strict comparison of the expected and actual JSON outputs and determine a score from 0 to 100. Check that all keys are present, values match in type and content, and nesting structure is preserved. Minor formatting differences (whitespace, key ordering) should not affect the score. Provide your score with a brief justification.
----
ExpectedOutput:
{{ExpectedOutput}}
----
ActualOutput:
{{ActualOutput}}`,
  },
  "uipath-llm-judge-trajectory-similarity": {
    description: "Uses an LLM to evaluate whether the agent's tool-call trajectory matches the expected sequence of actions, considering order, arguments, and completeness.",
    prompt: `As an expert evaluator, compare the agent's actual tool-call trajectory against the expected trajectory and determine a score from 0 to 100. Consider the order of tool calls, the correctness of arguments passed, and whether all expected steps were completed. Minor variations in argument formatting are acceptable if semantically equivalent. Provide your score with a brief justification.
----
ExpectedTrajectory:
{{ExpectedTrajectory}}
----
ActualTrajectory:
{{ActualTrajectory}}`,
  },
  "uipath-llm-judge-trajectory-simulation": {
    description: "Uses an LLM to evaluate the agent's behavior against simulation instructions and expected outcomes by analyzing the full run history.",
    prompt: `As an expert evaluator, determine how well the agent performed on a scale of 0 to 100. Focus on whether the simulation was successful and whether the agent behaved according to the expected output, accounting for alternative valid expressions and reasonable variations in language while maintaining high standards for accuracy and completeness. Provide your score with a brief justification.
----
UserOrSyntheticInputGivenToAgent:
{{UserOrSyntheticInput}}
----
SimulationInstructions:
{{SimulationInstructions}}
----
ExpectedAgentBehavior:
{{ExpectedAgentBehavior}}
----
AgentRunHistory:
{{AgentRunHistory}}`,
  },
  "uipath-tool-call-order": {
    description: "Validates that the agent called tools in the expected sequence.",
    prompt: "",
  },
  "uipath-tool-call-args": {
    description: "Checks whether the agent called tools with the expected arguments.",
    prompt: "",
  },
  "uipath-tool-call-count": {
    description: "Validates that the agent made the expected number of tool calls.",
    prompt: "",
  },
  "uipath-tool-call-output": {
    description: "Validates the output returned by the agent's tool calls.",
    prompt: "",
  },
};

// Reverse-lookup: given an evaluator_type_id, find which category it belongs to
function categoryForTypeId(typeId: string): string {
  for (const [cat, types] of Object.entries(typesByCategory)) {
    if (types.some((t) => t.id === typeId)) return cat;
  }
  return "deterministic";
}

interface Props {
  evaluatorId?: string | null;
  evaluatorFilter?: string | null;
}

export default function EvaluatorsView({ evaluatorId, evaluatorFilter }: Props) {
  const localEvaluators = useEvalStore((s) => s.localEvaluators);
  const setLocalEvaluators = useEvalStore((s) => s.setLocalEvaluators);
  const upsertLocalEvaluator = useEvalStore((s) => s.upsertLocalEvaluator);
  const evaluators = useEvalStore((s) => s.evaluators);
  const { navigate } = useHashRoute();

  const selectedEvaluator = evaluatorId ? localEvaluators.find((e) => e.id === evaluatorId) ?? null : null;
  const showSidebar = !!selectedEvaluator;

  const filteredEvaluators = evaluatorFilter
    ? localEvaluators.filter((e) => e.type === evaluatorFilter)
    : localEvaluators;

  // Sidebar width (resizable)
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem("evaluatorSidebarWidth");
    return saved ? parseInt(saved, 10) : 320;
  });
  const [isDragging, setIsDragging] = useState(false);
  const outerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem("evaluatorSidebarWidth", String(sidebarWidth));
  }, [sidebarWidth]);

  // Load local evaluators on mount
  useEffect(() => {
    listLocalEvaluators().then(setLocalEvaluators).catch(console.error);
  }, [setLocalEvaluators]);

  // --- Sidebar col resize ---
  const onSidebarResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    setIsDragging(true);
    const startX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const startW = sidebarWidth;

    const onMove = (ev: MouseEvent | TouchEvent) => {
      const container = outerRef.current;
      if (!container) return;
      const clientX = "touches" in ev ? ev.touches[0].clientX : ev.clientX;
      const maxW = container.clientWidth - 300;
      const newW = Math.max(280, Math.min(maxW, startW + (startX - clientX)));
      setSidebarWidth(newW);
    };

    const onUp = () => {
      setIsDragging(false);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend", onUp);
  }, [sidebarWidth]);

  const handleUpdated = (ev: LocalEvaluator) => {
    upsertLocalEvaluator(ev);
  };

  const handleCloseSidebar = () => {
    navigate("#/evaluators");
  };

  return (
    <div ref={outerRef} className="flex h-full">
      {/* Main content: header + cards */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header bar */}
        <div className="px-4 h-10 border-b shrink-0 flex items-center gap-4" style={{ borderColor: "var(--border)" }}>
          <h1 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
            Evaluators
          </h1>
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
            {filteredEvaluators.length}{evaluatorFilter ? ` / ${localEvaluators.length}` : ""} configured
          </span>
        </div>

        {/* Cards grid */}
        <div className="flex-1 overflow-y-auto p-4">
          {filteredEvaluators.length === 0 ? (
            <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-xs">
              {localEvaluators.length === 0 ? "No evaluators configured yet." : "No evaluators in this category."}
            </div>
          ) : (
            <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
              {filteredEvaluators.map((ev) => (
                <EvaluatorCard
                  key={ev.id}
                  evaluator={ev}
                  evaluators={evaluators}
                  selected={ev.id === evaluatorId}
                  onClick={() => navigate(ev.id === evaluatorId ? "#/evaluators" : `#/evaluators/${encodeURIComponent(ev.id)}`)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right sidebar: create or edit form (animated) */}
      {/* Drag handle */}
      <div
        onMouseDown={onSidebarResizeStart}
        onTouchStart={onSidebarResizeStart}
        className={`shrink-0 drag-handle-col${isDragging ? "" : " transition-all"}`}
        style={{ width: showSidebar ? 3 : 0, opacity: showSidebar ? 1 : 0 }}
      />

      <div
        className={`shrink-0 flex flex-col overflow-hidden${isDragging ? "" : " transition-[width] duration-200 ease-in-out"}`}
        style={{ width: showSidebar ? sidebarWidth : 0, background: "var(--bg-primary)" }}
      >
        {/* Tab bar */}
        <div
          className="flex items-center gap-1 px-2 h-10 border-b shrink-0"
          style={{ borderColor: "var(--border)", background: "var(--bg-secondary)", minWidth: sidebarWidth }}
        >
          <span
            className="px-2 py-0.5 h-7 text-xs font-semibold rounded inline-flex items-center"
            style={{
              color: "var(--accent)",
              background: "color-mix(in srgb, var(--accent) 10%, transparent)",
            }}
          >
            Edit Evaluator
          </span>
          <button
            onClick={handleCloseSidebar}
            aria-label="Close editor"
            className="ml-auto w-7 h-7 flex items-center justify-center rounded cursor-pointer transition-colors"
            style={{ color: "var(--text-muted)", background: "transparent", border: "none" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-hidden" style={{ minWidth: sidebarWidth }}>
          {selectedEvaluator && (
            <EditEvaluatorForm
              evaluator={selectedEvaluator}
              onUpdated={handleUpdated}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// --- Evaluator Card ---
function EvaluatorCard({ evaluator, evaluators, selected, onClick }: { evaluator: LocalEvaluator; evaluators: EvaluatorInfo[]; selected?: boolean; onClick?: () => void }) {
  const badge = typeBadge[evaluator.type] ?? typeBadge.deterministic;
  // Try to find the built-in evaluator name for the type
  const builtIn = evaluators.find((e) => e.id === evaluator.evaluator_type_id);
  const isCustom = evaluator.evaluator_type_id.startsWith("file://");

  return (
    <div
      className="rounded-md p-4 flex flex-col cursor-pointer transition-colors"
      style={{
        border: selected ? "1px solid var(--accent)" : "1px solid var(--border)",
        background: selected ? "color-mix(in srgb, var(--accent) 5%, var(--card-bg))" : "var(--card-bg)",
      }}
      onClick={onClick}
      onMouseEnter={(e) => { if (!selected) e.currentTarget.style.borderColor = "var(--text-muted)"; }}
      onMouseLeave={(e) => { if (!selected) e.currentTarget.style.borderColor = "var(--border)"; }}
    >
      {/* Name */}
      <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        {evaluator.name}
      </div>
      {/* Description */}
      {evaluator.description && (
        <div className="text-xs leading-relaxed mt-2" style={{ color: "var(--text-secondary)" }}>
          {evaluator.description}
        </div>
      )}
      {/* Pills — pinned to bottom */}
      <div className="flex flex-wrap gap-1.5 mt-auto pt-3">
        <span
          className="px-2 py-0.5 rounded text-[10px] font-medium"
          style={{ color: badge.color, background: badge.bg }}
        >
          Category: {badge.label}
        </span>
        <span
          className="px-2 py-0.5 rounded text-[10px] font-medium"
          style={{ background: "var(--bg-tertiary)", color: "var(--text-secondary)" }}
        >
          Type: {isCustom ? "Custom" : (builtIn?.name ?? evaluator.evaluator_type_id)}
        </span>
        <span
          className="px-2 py-0.5 rounded text-[10px] font-medium font-mono"
          style={{ background: "var(--bg-tertiary)", color: "var(--text-secondary)" }}
        >
          Target: {evaluator.target_output_key || "*"}
        </span>
      </div>
    </div>
  );
}

// --- Edit Evaluator Form ---

function EditEvaluatorForm({
  evaluator,
  onUpdated,
}: {
  evaluator: LocalEvaluator;
  onUpdated: (ev: LocalEvaluator) => void;
}) {
  const category = categoryForTypeId(evaluator.evaluator_type_id);
  const types = typesByCategory[category] ?? [];
  const builtInEvaluators = useEvalStore((s) => s.evaluators);
  const llmModels = useEvalStore((s) => s.llmModels);
  const setLlmModels = useEvalStore((s) => s.setLlmModels);

  const [description, setDescription] = useState(evaluator.description);
  const [typeId, setTypeId] = useState(evaluator.evaluator_type_id);
  const [configValues, setConfigValues] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (category === "llm" && llmModels.length === 0) {
      listLlmModels().then(setLlmModels).catch(() => {});
    }
  }, [category]);

  const schemaFields = useMemo(() => {
    const ev = builtInEvaluators.find((e) => e.id === typeId);
    return ev ? getSchemaConfigFields(ev.config_schema) : [];
  }, [typeId, builtInEvaluators]);

  // Reset form when switching to a different evaluator
  useEffect(() => {
    setDescription(evaluator.description);
    setTypeId(evaluator.evaluator_type_id);
    // Initialize configValues from evaluator.config, using snake_case keys
    const vals: Record<string, unknown> = {};
    const cfg = evaluator.config ?? {};
    // Map camelCase config keys to snake_case schema keys
    const keyMap: Record<string, string> = { targetOutputKey: "target_output_key", caseSensitive: "case_sensitive", maxTokens: "max_tokens" };
    for (const [k, v] of Object.entries(cfg)) {
      vals[keyMap[k] ?? k] = v;
    }
    setConfigValues(vals);
    setError(null);
    setSuccess(false);
  }, [evaluator.id]);

  const handleConfigChange = (key: string, value: unknown) => {
    setConfigValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const config: Record<string, unknown> = {};
      // Map snake_case schema keys back to camelCase for the evaluator JSON
      const keyMap: Record<string, string> = { target_output_key: "targetOutputKey", case_sensitive: "caseSensitive", max_tokens: "maxTokens" };
      for (const f of schemaFields) {
        const val = configValues[f.key];
        if (val !== undefined && val !== null && val !== "") {
          config[keyMap[f.key] ?? f.key] = val;
        }
      }

      const result = await updateLocalEvaluator(evaluator.id, {
        description: description.trim(),
        evaluator_type_id: typeId,
        config,
      });
      onUpdated(result);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail;
      setError(detail ?? "Failed to update evaluator");
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = {
    background: "var(--bg-secondary)",
    color: "var(--text-primary)",
    border: "1px solid var(--border)",
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 overflow-y-auto flex-1 space-y-4">
        {/* Name (readonly) */}
        <div>
          <label className="text-[11px] font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Name
          </label>
          <div
            className="px-3 py-2 rounded-lg text-xs"
            style={{ background: "var(--bg-tertiary)", color: "var(--text-secondary)" }}
          >
            {evaluator.name}
          </div>
        </div>

        {/* Category (readonly) */}
        <div>
          <label className="text-[11px] font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Category
          </label>
          <div
            className="px-3 py-2 rounded-lg text-xs"
            style={{ background: "var(--bg-tertiary)", color: "var(--text-secondary)" }}
          >
            {categoryLabel[category] ?? category}
          </div>
        </div>

        {/* Type dropdown */}
        <div>
          <label className="text-[11px] font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Type
          </label>
          <select
            value={typeId}
            onChange={(e) => setTypeId(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-xs outline-none cursor-pointer"
            style={inputStyle}
          >
            {types.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>

        {/* Description */}
        <div>
          <label className="text-[11px] font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What does this evaluator check?"
            rows={4}
            className="w-full px-3 py-2 rounded-lg text-xs leading-relaxed outline-none resize-y"
            style={inputStyle}
          />
        </div>

        {/* Dynamic config fields from schema */}
        <SchemaConfigFields
          fields={schemaFields}
          values={configValues}
          onChange={handleConfigChange}
          llmModels={llmModels}
          inputStyle={inputStyle}
        />
      </div>

      {/* Bottom pinned section */}
      <div className="shrink-0 p-4 space-y-2">
        {/* Error */}
        {error && (
          <div className="text-xs px-3 py-2 rounded-lg" style={{ background: "rgba(239,68,68,0.1)", color: "var(--error)" }}>
            {error}
          </div>
        )}

        {/* Success */}
        {success && (
          <div className="text-xs px-3 py-2 rounded-lg" style={{ background: "rgba(34,197,94,0.1)", color: "var(--success)" }}>
            Saved successfully
          </div>
        )}

        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full py-2.5 text-xs font-semibold rounded-md border cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          style={{
            background: "transparent",
            borderColor: "var(--accent)",
            color: "var(--accent)",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "color-mix(in srgb, var(--accent) 15%, transparent)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
        >
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </div>
  );
}
