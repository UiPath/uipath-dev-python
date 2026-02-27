import { useState, useCallback } from "react";
import type { InterruptEvent } from "../../types/run";

interface Props {
  interrupt: InterruptEvent;
  onRespond: (data: Record<string, unknown>) => void;
}

/* ── JSON Schema helpers ─────────────────────────────────── */

interface SchemaProperty {
  type?: string;
  description?: string;
  enum?: unknown[];
}

interface JsonSchema {
  properties?: Record<string, SchemaProperty>;
}

function hasProperties(
  schema: unknown,
): schema is JsonSchema & { properties: Record<string, SchemaProperty> } {
  if (typeof schema !== "object" || schema === null) return false;
  const s = schema as Record<string, unknown>;
  return (
    typeof s.properties === "object" &&
    s.properties !== null &&
    Object.keys(s.properties as object).length > 0
  );
}

/* ── Per-field form input ────────────────────────────────── */

const inputStyle = {
  color: "var(--text-primary)",
  border: "1px solid var(--border)",
  background: "var(--bg-primary)",
};
const inputClass =
  "w-full text-[11px] font-mono py-1 px-2 rounded focus:outline-none";

function FormField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const label = (
    <label
      className="text-[11px] font-medium block mb-1"
      style={{ color: "var(--text-muted)" }}
    >
      {name}
      {prop.description && (
        <span
          className="font-normal normal-case tracking-normal ml-1"
          style={{ color: "var(--text-muted)", opacity: 0.7 }}
        >
          — {prop.description}
        </span>
      )}
    </label>
  );

  if (prop.enum && Array.isArray(prop.enum)) {
    return (
      <div>
        {label}
        <select
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
          style={inputStyle}
        >
          {prop.enum.map((opt) => (
            <option key={String(opt)} value={String(opt)}>
              {String(opt)}
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (prop.type === "boolean") {
    return (
      <div>
        {label}
        <label className="flex items-center gap-2 cursor-pointer py-1">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
            className="accent-[var(--accent)]"
          />
          <span
            className="text-[11px] font-mono"
            style={{ color: "var(--text-secondary)" }}
          >
            {value ? "true" : "false"}
          </span>
        </label>
      </div>
    );
  }

  if (prop.type === "number" || prop.type === "integer") {
    return (
      <div>
        {label}
        <input
          type="number"
          value={value == null ? "" : String(value)}
          onChange={(e) =>
            onChange(e.target.value === "" ? null : Number(e.target.value))
          }
          step={prop.type === "integer" ? 1 : "any"}
          className={inputClass}
          style={inputStyle}
        />
      </div>
    );
  }

  if (prop.type === "object" || prop.type === "array") {
    const str =
      typeof value === "string"
        ? value
        : JSON.stringify(value ?? null, null, 2);
    return (
      <div>
        {label}
        <textarea
          value={str}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className={`${inputClass} resize-y`}
          style={inputStyle}
        />
      </div>
    );
  }

  // string / unknown → text input or textarea for long values
  const strValue = value == null ? "" : String(value);
  if (strValue.length > 100 || strValue.includes("\n")) {
    return (
      <div>
        {label}
        <textarea
          value={strValue}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className={`${inputClass} resize-y`}
          style={inputStyle}
        />
      </div>
    );
  }

  return (
    <div>
      {label}
      <input
        type="text"
        value={strValue}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
        style={inputStyle}
      />
    </div>
  );
}

/* ── Styled button (avoids repeating hover handlers) ─────── */

function ActionButton({
  label,
  color,
  onClick,
}: {
  label: string;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="text-xs font-semibold px-3 py-1.5 rounded cursor-pointer transition-colors"
      style={{
        background: `color-mix(in srgb, var(--${color}) 15%, var(--bg-secondary))`,
        color: `var(--${color})`,
        border: `1px solid color-mix(in srgb, var(--${color}) 30%, var(--border))`,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = `color-mix(in srgb, var(--${color}) 25%, var(--bg-secondary))`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = `color-mix(in srgb, var(--${color}) 15%, var(--bg-secondary))`;
      }}
    >
      {label}
    </button>
  );
}

/* ── Main component ──────────────────────────────────────── */

export default function ChatInterrupt({ interrupt, onRespond }: Props) {
  const [responseText, setResponseText] = useState("");
  const [editing, setEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, unknown>>({});
  const [rawJson, setRawJson] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);

  const schema = interrupt.input_schema;
  const canEditWithForm = hasProperties(schema);

  const startEditing = useCallback(() => {
    const current =
      typeof interrupt.input_value === "object" && interrupt.input_value !== null
        ? (interrupt.input_value as Record<string, unknown>)
        : {};

    if (canEditWithForm) {
      const initial: Record<string, unknown> = { ...current };
      // Ensure every schema key is present
      for (const key of Object.keys(
        (schema as JsonSchema & { properties: Record<string, SchemaProperty> })
          .properties,
      )) {
        if (!(key in initial)) initial[key] = null;
      }
      // For object/array props, store as JSON string for editing
      const props = (
        schema as JsonSchema & { properties: Record<string, SchemaProperty> }
      ).properties;
      for (const [key, prop] of Object.entries(props)) {
        if (
          (prop.type === "object" || prop.type === "array") &&
          typeof initial[key] !== "string"
        ) {
          initial[key] = JSON.stringify(initial[key] ?? null, null, 2);
        }
      }
      setEditedValues(initial);
    } else {
      setRawJson(
        typeof interrupt.input_value === "string"
          ? interrupt.input_value
          : JSON.stringify(interrupt.input_value ?? null, null, 2),
      );
    }
    setJsonError(null);
    setEditing(true);
  }, [interrupt.input_value, canEditWithForm, schema]);

  const cancelEditing = () => {
    setEditing(false);
    setJsonError(null);
  };

  const handleApproveWithEdits = () => {
    if (canEditWithForm) {
      const resolved: Record<string, unknown> = {};
      const props = (
        schema as JsonSchema & { properties: Record<string, SchemaProperty> }
      ).properties;
      for (const [key, val] of Object.entries(editedValues)) {
        const prop = props[key];
        if (
          (prop?.type === "object" || prop?.type === "array") &&
          typeof val === "string"
        ) {
          try {
            resolved[key] = JSON.parse(val);
          } catch {
            setJsonError(`Invalid JSON for "${key}"`);
            return;
          }
        } else {
          resolved[key] = val;
        }
      }
      onRespond({ approved: true, input: resolved });
    } else {
      try {
        const parsed = JSON.parse(rawJson);
        onRespond({ approved: true, input: parsed });
      } catch {
        setJsonError("Invalid JSON");
        return;
      }
    }
  };

  const updateField = useCallback((key: string, value: unknown) => {
    setEditedValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  /* ── Tool call confirmation ───────────────────────────── */

  if (interrupt.interrupt_type === "tool_call_confirmation") {
    return (
      <div
        className="mx-3 my-2 rounded-lg overflow-hidden"
        style={{
          border:
            "1px solid color-mix(in srgb, var(--warning) 40%, var(--border))",
        }}
      >
        {/* Header */}
        <div
          className="px-3 py-2 flex items-center gap-2"
          style={{
            background:
              "color-mix(in srgb, var(--warning) 10%, var(--bg-secondary))",
          }}
        >
          <span
            className="text-[11px] font-semibold"
            style={{ color: "var(--warning)" }}
          >
            {editing ? "Edit Arguments" : "Action Required"}
          </span>
          {interrupt.tool_name && (
            <span
              className="text-[11px] font-mono px-1.5 py-0.5 rounded"
              style={{
                background:
                  "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))",
                color: "var(--text-primary)",
              }}
            >
              {interrupt.tool_name}
            </span>
          )}
          {!editing && (interrupt.input_value != null || canEditWithForm) && (
            <button
              onClick={startEditing}
              className="ml-auto p-1.5 rounded cursor-pointer transition-colors"
              style={{ color: "var(--text-muted)" }}
              aria-label="Edit arguments"
              onMouseEnter={(e) => {
                e.currentTarget.style.color = "var(--warning)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = "var(--text-muted)";
              }}
              title="Edit arguments"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </button>
          )}
        </div>

        {/* Body */}
        {editing ? (
          <div
            className="px-3 py-2 space-y-3 overflow-y-auto"
            style={{ background: "var(--bg-secondary)", maxHeight: 300 }}
          >
            {canEditWithForm ? (
              Object.entries(
                (
                  schema as JsonSchema & {
                    properties: Record<string, SchemaProperty>;
                  }
                ).properties,
              ).map(([key, prop]) => (
                <FormField
                  key={key}
                  name={key}
                  prop={prop}
                  value={editedValues[key]}
                  onChange={(v) => updateField(key, v)}
                />
              ))
            ) : (
              <textarea
                value={rawJson}
                onChange={(e) => {
                  setRawJson(e.target.value);
                  setJsonError(null);
                }}
                rows={8}
                className="w-full text-[11px] font-mono py-1 px-2 rounded focus:outline-none resize-y"
                style={inputStyle}
              />
            )}
            {jsonError && (
              <p className="text-[11px]" style={{ color: "var(--error)" }}>
                {jsonError}
              </p>
            )}
          </div>
        ) : (
          interrupt.input_value != null && (
            <pre
              className="px-3 py-2 text-[11px] font-mono whitespace-pre-wrap break-words overflow-y-auto leading-normal"
              style={{
                background: "var(--bg-secondary)",
                color: "var(--text-secondary)",
                maxHeight: 200,
              }}
            >
              {typeof interrupt.input_value === "string"
                ? interrupt.input_value
                : JSON.stringify(interrupt.input_value, null, 2)}
            </pre>
          )
        )}

        {/* Footer */}
        <div
          className="flex items-center gap-2 px-3 py-2"
          style={{
            background: "var(--bg-secondary)",
            borderTop: "1px solid var(--border)",
          }}
        >
          {editing ? (
            <>
              <ActionButton
                label="Approve"
                color="success"
                onClick={handleApproveWithEdits}
              />
              <ActionButton
                label="Cancel"
                color="text-muted"
                onClick={cancelEditing}
              />
            </>
          ) : (
            <>
              <ActionButton
                label="Approve"
                color="success"
                onClick={() => onRespond({ approved: true })}
              />
              <ActionButton
                label="Reject"
                color="error"
                onClick={() => onRespond({ approved: false })}
              />
            </>
          )}
        </div>
      </div>
    );
  }

  /* ── Generic interrupt ────────────────────────────────── */

  return (
    <div
      className="mx-3 my-2 rounded-lg overflow-hidden"
      style={{
        border:
          "1px solid color-mix(in srgb, var(--accent) 40%, var(--border))",
      }}
    >
      <div
        className="px-3 py-2"
        style={{
          background:
            "color-mix(in srgb, var(--accent) 10%, var(--bg-secondary))",
        }}
      >
        <span
          className="text-[11px] font-semibold"
          style={{ color: "var(--accent)" }}
        >
          Input Required
        </span>
      </div>
      {interrupt.content != null && (
        <div
          className="px-3 py-2 text-sm leading-relaxed"
          style={{
            background: "var(--bg-secondary)",
            color: "var(--text-secondary)",
          }}
        >
          {typeof interrupt.content === "string"
            ? interrupt.content
            : JSON.stringify(interrupt.content, null, 2)}
        </div>
      )}
      <div
        className="flex items-center gap-2 px-3 py-2"
        style={{
          background: "var(--bg-secondary)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <input
          value={responseText}
          onChange={(e) => setResponseText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && responseText.trim()) {
              e.preventDefault();
              onRespond({ response: responseText.trim() });
            }
          }}
          placeholder="Type your response..."
          className="flex-1 bg-transparent text-sm py-1 placeholder:text-[var(--text-muted)]"
          style={{ color: "var(--text-primary)" }}
        />
        <button
          onClick={() => {
            if (responseText.trim()) {
              onRespond({ response: responseText.trim() });
            }
          }}
          disabled={!responseText.trim()}
          className="text-xs font-semibold px-3 py-1.5 rounded transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
          style={{
            color: responseText.trim() ? "var(--accent)" : "var(--text-muted)",
            background: "transparent",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
