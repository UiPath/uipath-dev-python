import { useEffect, useState, useCallback } from "react";
import { useRunStore } from "../../store/useRunStore";
import { getEntrypointMockInput, createRun } from "../../api/client";

interface Props {
  onRunCreated: (runId: string) => void;
}

interface SchemaError {
  message: string;
  type?: string;
  error?: string;
  traceback?: string;
}

export default function NewRunPanel({ onRunCreated }: Props) {
  const entrypoints = useRunStore((s) => s.entrypoints);
  const [selectedEp, setSelectedEp] = useState("");
  const [inputJson, setInputJson] = useState("{}");
  const [loading, setLoading] = useState<string | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [schemaError, setSchemaError] = useState<SchemaError | null>(null);

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
        setSchemaError(null);
        return;
      }

      setLoadingSchema(true);
      setSchemaError(null);
      try {
        const result = await getEntrypointMockInput(ep);
        const json = JSON.stringify(result.mock_input, null, 2);
        setInputJson(json);
        setMockCache((prev) => ({ ...prev, [ep]: json }));
      } catch (err: any) {
        console.error("Failed to load mock input:", err);
        // Parse error details from the HTTP exception
        const errorDetail = err.detail || {};
        setSchemaError({
          message: errorDetail.message || `Failed to load schema for "${ep}"`,
          type: errorDetail.type,
          error: errorDetail.error,
          traceback: errorDetail.traceback,
        });
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
      // Immediately add the run to the store so it's available when switching views
      useRunStore.getState().upsertRun(run);
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

        {schemaError ? (
          <SchemaErrorDisplay error={schemaError} />
        ) : (
          <>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-sm text-[var(--text-secondary)]">Input (JSON)</label>
                {loadingSchema && (
                  <span className="text-xs text-[var(--accent)]">Loading schema...</span>
                )}
              </div>
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
              <button
                onClick={() => handleSubmit("chat")}
                disabled={isDisabled}
                className="flex-1 py-2.5 bg-[var(--accent)] hover:brightness-110 disabled:opacity-40 text-white text-sm font-medium rounded transition-all"
              >
                {loading === "chat" ? "Starting..." : "Chat"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function SchemaErrorDisplay({ error }: { error: SchemaError }) {
  const [copied, setCopied] = useState(false);

  const copyStacktrace = () => {
    if (error.traceback) {
      navigator.clipboard.writeText(error.traceback).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }
  };

  return (
    <div
      className="rounded-lg border max-h-96 overflow-y-auto"
      style={{
        borderColor: "var(--error)",
        background: "color-mix(in srgb, var(--error) 5%, var(--bg-secondary))",
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-2.5 flex items-center justify-between"
        style={{
          background: "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))",
          borderBottom: "1px solid var(--error)",
        }}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold" style={{ color: "var(--error)" }}>
            Schema Error
          </span>
          {error.type && (
            <span
              className="text-xs font-mono px-2 py-0.5 rounded"
              style={{
                background: "color-mix(in srgb, var(--error) 20%, var(--bg-secondary))",
                color: "var(--error)",
              }}
            >
              {error.type}
            </span>
          )}
        </div>
        {error.traceback && (
          <button
            onClick={copyStacktrace}
            className="text-xs font-semibold px-2.5 py-1 rounded transition-colors"
            style={{
              background: copied ? "var(--success)" : "var(--bg-primary)",
              color: copied ? "white" : "var(--text-primary)",
              border: `1px solid ${copied ? "var(--success)" : "var(--border)"}`,
            }}
          >
            {copied ? "Copied!" : "Copy Stacktrace"}
          </button>
        )}
      </div>

      {/* Message */}
      <div className="px-4 py-3">
        <p className="text-sm" style={{ color: "var(--text-primary)" }}>
          {error.message}
        </p>
        {error.error && (
          <p className="text-xs mt-2 font-mono" style={{ color: "var(--text-secondary)" }}>
            {error.error}
          </p>
        )}
      </div>

      {/* Stacktrace */}
      {error.traceback && (
        <div
          className="px-4 py-3"
          style={{
            background: "var(--bg-primary)",
            borderTop: "1px solid var(--border)",
          }}
        >
          <div className="text-[10px] uppercase font-semibold mb-2" style={{ color: "var(--text-muted)" }}>
            Stacktrace
          </div>
          <pre
            className="text-xs font-mono whitespace-pre-wrap"
            style={{ color: "var(--text-secondary)" }}
          >
            {error.traceback}
          </pre>
        </div>
      )}
    </div>
  );
}
