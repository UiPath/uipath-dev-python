import { useEffect, useMemo, useState } from "react";
import { useEvalStore } from "../../store/useEvalStore";
import { useHashRoute } from "../../hooks/useHashRoute";
import { createLocalEvaluator, listLlmModels } from "../../api/eval-client";
import { typesByCategory, typeDefaults, categoryLabel, getSchemaConfigFields, SchemaConfigFields } from "./EvaluatorDetail";

const allCategories = ["deterministic", "llm", "tool"] as const;

interface Props {
  category: string;
}

export default function CreateEvaluatorView({ category: initialCategory }: Props) {
  const addLocalEvaluator = useEvalStore((s) => s.addLocalEvaluator);
  const evaluators = useEvalStore((s) => s.evaluators);
  const llmModels = useEvalStore((s) => s.llmModels);
  const setLlmModels = useEvalStore((s) => s.setLlmModels);
  const { navigate } = useHashRoute();

  const isFixed = initialCategory !== "any";
  const [category, setCategory] = useState(isFixed ? initialCategory : "deterministic");
  const types = typesByCategory[category] ?? [];
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [typeId, setTypeId] = useState(types[0]?.id ?? "");
  const [configValues, setConfigValues] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [descriptionTouched, setDescriptionTouched] = useState(false);

  useEffect(() => {
    if (llmModels.length === 0) {
      listLlmModels().then(setLlmModels).catch(() => {});
    }
  }, []);

  const schemaFields = useMemo(() => {
    const ev = evaluators.find((e) => e.id === typeId);
    return ev ? getSchemaConfigFields(ev.config_schema) : [];
  }, [typeId, evaluators]);

  // Build default config values from schema + typeDefaults
  const buildDefaults = (tid: string) => {
    const ev = evaluators.find((e) => e.id === tid);
    const fields = ev ? getSchemaConfigFields(ev.config_schema) : [];
    const defaults: Record<string, unknown> = {};
    for (const f of fields) {
      if (f.default_value !== undefined && f.default_value !== null) {
        defaults[f.key] = f.default_value;
      }
    }
    // Override prompt from typeDefaults if available
    const td = typeDefaults[tid];
    if (td?.prompt) defaults.prompt = td.prompt;
    return defaults;
  };

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
    setConfigValues(buildDefaults(firstId));
    setError(null);
    setDescriptionTouched(false);
  }, [initialCategory, isFixed, evaluators]);

  const handleCategoryChange = (newCat: string) => {
    setCategory(newCat);
    const t = typesByCategory[newCat] ?? [];
    const firstId = t[0]?.id ?? "";
    const defaults = typeDefaults[firstId];
    setTypeId(firstId);
    if (!descriptionTouched) setDescription(defaults?.description ?? "");
    setConfigValues(buildDefaults(firstId));
  };

  const handleTypeChange = (newTypeId: string) => {
    setTypeId(newTypeId);
    const defaults = typeDefaults[newTypeId];
    if (defaults && !descriptionTouched) setDescription(defaults.description);
    setConfigValues(buildDefaults(newTypeId));
  };

  const handleConfigChange = (key: string, value: unknown) => {
    setConfigValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      // Build config from schema fields, only including non-default values
      const config: Record<string, unknown> = {};
      for (const f of schemaFields) {
        const val = configValues[f.key];
        if (val !== undefined && val !== null && val !== "") {
          config[f.key] = val;
        }
      }

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
            <label className="block text-[11px] font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. MyEvaluator"
              className="w-full rounded-md px-3 py-2 text-xs"
              style={inputStyle}
              onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) handleSubmit(); }}
            />
          </div>

          {/* Category */}
          <div className="mb-6">
            <label className="block text-[11px] font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>
              Category
            </label>
            {isFixed ? (
              <div className="px-3 py-2 rounded-md text-xs" style={{ background: "var(--bg-tertiary)", color: "var(--text-secondary)" }}>
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
            <label className="block text-[11px] font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>
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
            <label className="block text-[11px] font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>
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

          {/* Dynamic config fields from schema */}
          <SchemaConfigFields
            fields={schemaFields}
            values={configValues}
            onChange={handleConfigChange}
            llmModels={llmModels}
            inputStyle={inputStyle}
          />

          {/* Error */}
          {error && (
            <p className="text-xs mb-4 px-3 py-2 rounded" style={{ color: "var(--error)", background: "color-mix(in srgb, var(--error) 10%, var(--bg-secondary))" }}>{error}</p>
          )}

          {/* Create button */}
          <button
            onClick={handleSubmit}
            disabled={saving || !name.trim()}
            className="w-full py-2 rounded-md text-[13px] font-semibold transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: "var(--accent)", color: "var(--bg-primary)", border: "none" }}
          >
            {saving ? "Creating..." : "Create Evaluator"}
          </button>
        </div>
      </div>
    </div>
  );
}
