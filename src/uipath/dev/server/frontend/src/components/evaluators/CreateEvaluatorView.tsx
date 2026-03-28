import { useEffect, useState } from "react";
import { useEvalStore } from "../../store/useEvalStore";
import { useHashRoute } from "../../hooks/useHashRoute";
import { createLocalEvaluator, listLlmModels } from "../../api/eval-client";
import { typesByCategory, typeDefaults, getTypeFields, categoryLabel } from "./EvaluatorDetail";

const allCategories = ["deterministic", "llm", "tool"] as const;

interface Props {
  category: string;
}

export default function CreateEvaluatorView({ category: initialCategory }: Props) {
  const addLocalEvaluator = useEvalStore((s) => s.addLocalEvaluator);
  const llmModels = useEvalStore((s) => s.llmModels);
  const setLlmModels = useEvalStore((s) => s.setLlmModels);
  const { navigate } = useHashRoute();

  const isFixed = initialCategory !== "any";
  const [category, setCategory] = useState(isFixed ? initialCategory : "deterministic");
  const types = typesByCategory[category] ?? [];
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [typeId, setTypeId] = useState(types[0]?.id ?? "");
  const [targetOutputKey, setTargetOutputKey] = useState("*");
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [descriptionTouched, setDescriptionTouched] = useState(false);
  const [promptTouched, setPromptTouched] = useState(false);

  useEffect(() => {
    if (llmModels.length === 0) {
      listLlmModels().then(setLlmModels).catch(() => {});
    }
  }, []);

  // Reset form when initial category prop changes
  useEffect(() => {
    const cat = isFixed ? initialCategory : "deterministic";
    setCategory(cat);
    const t = typesByCategory[cat] ?? [];
    const firstId = t[0]?.id ?? "";
    const defaults = typeDefaults[firstId];
    setName("");
    setDescription(defaults?.description ?? "");
    setTypeId(firstId);
    setTargetOutputKey("*");
    setPrompt(defaults?.prompt ?? "");
    setModel("");
    setError(null);
    setDescriptionTouched(false);
    setPromptTouched(false);
  }, [initialCategory, isFixed]);

  const handleCategoryChange = (newCat: string) => {
    setCategory(newCat);
    const t = typesByCategory[newCat] ?? [];
    const firstId = t[0]?.id ?? "";
    const defaults = typeDefaults[firstId];
    setTypeId(firstId);
    if (!descriptionTouched) setDescription(defaults?.description ?? "");
    if (!promptTouched) setPrompt(defaults?.prompt ?? "");
  };

  const handleTypeChange = (newTypeId: string) => {
    setTypeId(newTypeId);
    const defaults = typeDefaults[newTypeId];
    if (defaults) {
      if (!descriptionTouched) setDescription(defaults.description);
      if (!promptTouched) setPrompt(defaults.prompt);
    }
  };

  const fields = getTypeFields(typeId);
  const isLlm = category === "llm";

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const config: Record<string, unknown> = {};
      if (fields.targetOutputKey) config.targetOutputKey = targetOutputKey;
      if (fields.prompt && prompt.trim()) config.prompt = prompt;
      if (isLlm && model) config.model = model;

      const result = await createLocalEvaluator({
        name: name.trim(),
        description: description.trim(),
        evaluator_type_id: typeId,
        config,
      });
      addLocalEvaluator(result);
      navigate("#/evaluators");
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail;
      setError(detail ?? "Failed to create evaluator");
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = {
    background: "var(--bg-secondary)",
    border: "1px solid var(--border)",
    color: "var(--text-primary)",
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="flex items-center justify-center min-h-full py-8">
        <div className="w-full max-w-xl px-6">
          {/* Header */}
          <div className="mb-8 text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent)" }} />
              <span className="text-sm font-semibold" style={{ color: "var(--text-muted)" }}>
                New Evaluator
              </span>
            </div>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Create an evaluator to score agent outputs
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
              placeholder="e.g. MyEvaluator"
              className="w-full rounded-md px-3 py-2 text-xs"
              style={inputStyle}
              onKeyDown={(e) => {
                if (e.key === "Enter" && name.trim()) handleSubmit();
              }}
            />
          </div>

          {/* Category */}
          <div className="mb-6">
            <label
              className="block text-[11px] font-medium mb-1.5"
              style={{ color: "var(--text-muted)" }}
            >
              Category
            </label>
            {isFixed ? (
              <div
                className="px-3 py-2 rounded-md text-xs"
                style={{ background: "var(--bg-tertiary)", color: "var(--text-secondary)" }}
              >
                {categoryLabel[category] ?? category}
              </div>
            ) : (
              <select
                value={category}
                onChange={(e) => handleCategoryChange(e.target.value)}
                className="w-full rounded-md px-3 py-2 text-xs cursor-pointer appearance-auto"
                style={inputStyle}
              >
                {allCategories.map((cat) => (
                  <option key={cat} value={cat}>{categoryLabel[cat]}</option>
                ))}
              </select>
            )}
          </div>

          {/* Type */}
          <div className="mb-6">
            <label
              className="block text-[11px] font-medium mb-1.5"
              style={{ color: "var(--text-muted)" }}
            >
              Type
            </label>
            <select
              value={typeId}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="w-full rounded-md px-3 py-2 text-xs cursor-pointer appearance-auto"
              style={inputStyle}
            >
              {types.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          {/* Description */}
          <div className="mb-6">
            <label
              className="block text-[11px] font-medium mb-1.5"
              style={{ color: "var(--text-muted)" }}
            >
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => { setDescription(e.target.value); setDescriptionTouched(true); }}
              placeholder="What does this evaluator check?"
              rows={3}
              className="w-full rounded-md px-3 py-2 text-xs leading-relaxed resize-y"
              style={inputStyle}
            />
          </div>

          {/* Target Output Key (conditional) */}
          {fields.targetOutputKey && (
            <div className="mb-6">
              <label
                className="block text-[11px] font-medium mb-1.5"
                style={{ color: "var(--text-muted)" }}
              >
                Target Output Key
              </label>
              <input
                type="text"
                value={targetOutputKey}
                onChange={(e) => setTargetOutputKey(e.target.value)}
                placeholder="*"
                className="w-full rounded-md px-3 py-2 text-xs"
                style={inputStyle}
              />
              <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                Use * for entire output or a specific key name
              </div>
            </div>
          )}

          {/* Prompt (conditional) */}
          {fields.prompt && (
            <div className="mb-6">
              <label
                className="block text-[11px] font-medium mb-1.5"
                style={{ color: "var(--text-muted)" }}
              >
                Prompt
              </label>
              <textarea
                value={prompt}
                onChange={(e) => { setPrompt(e.target.value); setPromptTouched(true); }}
                placeholder="Evaluation prompt for the LLM judge..."
                rows={6}
                className="w-full rounded-md px-3 py-2 text-xs font-mono leading-relaxed resize-y"
                style={inputStyle}
              />
            </div>
          )}

          {/* Model (LLM evaluators only) */}
          {isLlm && (
            <div className="mb-6">
              <label
                className="block text-[11px] font-medium mb-1.5"
                style={{ color: "var(--text-muted)" }}
              >
                Model
              </label>
              {llmModels.length > 0 ? (
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
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
              ) : (
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="e.g. gpt-4.1-mini-2025-04-14"
                  className="w-full rounded-md px-3 py-2 text-xs"
                  style={inputStyle}
                />
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-xs mb-4 px-3 py-2 rounded" style={{ color: "var(--error)", background: "color-mix(in srgb, var(--error) 10%, var(--bg-secondary))" }}>{error}</p>
          )}

          {/* Create button */}
          <button
            onClick={handleSubmit}
            disabled={saving || !name.trim()}
            className="w-full py-2 rounded-md text-[13px] font-semibold transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: "var(--accent)",
              color: "var(--bg-primary)",
              border: "none",
            }}
          >
            {saving ? "Creating..." : "Create Evaluator"}
          </button>
        </div>
      </div>
    </div>
  );
}
