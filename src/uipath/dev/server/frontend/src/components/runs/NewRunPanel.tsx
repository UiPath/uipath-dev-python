import { useEffect, useState, useCallback } from "react";
import { useRunStore } from "../../store/useRunStore";
import { getEntrypointMockInput, createRun } from "../../api/client";

interface Props {
  onRunCreated: (runId: string) => void;
}

export default function NewRunPanel({ onRunCreated }: Props) {
  const entrypoints = useRunStore((s) => s.entrypoints);
  const [selectedEp, setSelectedEp] = useState("");
  const [inputJson, setInputJson] = useState("{}");
  const [loading, setLoading] = useState<string | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [schemaError, setSchemaError] = useState("");

  // Cache mock inputs so we don't re-fetch on every switch
  const [mockCache, setMockCache] = useState<Record<string, string>>({});

  // Select first entrypoint when available and none selected
  useEffect(() => {
    if (!selectedEp && entrypoints.length > 0) {
      setSelectedEp(entrypoints[0]);
    }
  }, [entrypoints, selectedEp]);

  // Fetch mock input when entrypoint changes
  const loadMockInput = useCallback(
    async (ep: string) => {
      if (!ep) return;

      // Use cache if available
      if (mockCache[ep]) {
        setInputJson(mockCache[ep]);
        setSchemaError("");
        return;
      }

      setLoadingSchema(true);
      setSchemaError("");
      try {
        const result = await getEntrypointMockInput(ep);
        const json = JSON.stringify(result.mock_input, null, 2);
        setInputJson(json);
        setMockCache((prev) => ({ ...prev, [ep]: json }));
      } catch (err) {
        console.error("Failed to load mock input:", err);
        setSchemaError(`Failed to load schema for "${ep}"`);
        setInputJson("{}");
      } finally {
        setLoadingSchema(false);
      }
    },
    [mockCache],
  );

  useEffect(() => {
    if (selectedEp) {
      loadMockInput(selectedEp);
    }
  }, [selectedEp, loadMockInput]);

  const handleSubmit = async (mode: "run" | "debug" | "chat") => {
    if (!selectedEp) return;

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(inputJson);
    } catch {
      alert("Invalid JSON input");
      return;
    }

    setLoading(mode);
    try {
      const run = await createRun(selectedEp, parsed, mode);
      onRunCreated(run.id);
    } catch (err) {
      console.error("Failed to create run:", err);
    } finally {
      setLoading(null);
    }
  };

  const isDisabled = !!loading || !selectedEp || loadingSchema;

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-6">New Run</h2>

      <div className="space-y-4">
        <div>
          <label className="block text-sm text-[var(--text-secondary)] mb-1">Entrypoint</label>
          <select
            value={selectedEp}
            onChange={(e) => setSelectedEp(e.target.value)}
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border)] rounded px-3 py-2 text-sm text-[var(--text-primary)] appearance-auto"
          >
            {entrypoints.length === 0 && (
              <option value="">Loading entrypoints...</option>
            )}
            {entrypoints.map((ep) => (
              <option key={ep} value={ep}>
                {ep}
              </option>
            ))}
          </select>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-[var(--text-secondary)]">Input (JSON)</label>
            {loadingSchema && (
              <span className="text-xs text-[var(--accent)]">Loading schema...</span>
            )}
          </div>
          {schemaError && (
            <div className="text-xs text-[var(--error)] mb-1">{schemaError}</div>
          )}
          <textarea
            value={inputJson}
            onChange={(e) => setInputJson(e.target.value)}
            rows={10}
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border)] rounded px-3 py-2 text-sm text-[var(--text-primary)] font-mono"
          />
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => handleSubmit("run")}
            disabled={isDisabled}
            className="flex-1 py-2.5 bg-[var(--success)] hover:brightness-110 disabled:opacity-40 text-white text-sm font-medium rounded transition-all"
          >
            {loading === "run" ? "Starting..." : "Run"}
          </button>
        </div>
      </div>
    </div>
  );
}
