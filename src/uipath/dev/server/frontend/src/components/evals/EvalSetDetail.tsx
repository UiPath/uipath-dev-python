import { useCallback, useEffect, useRef, useState } from "react";
import { getEvalSet, startEvalRun, updateEvalSetEvaluators, updateEvalItemEvaluators, updateEvalItem, addEvalItem, deleteEvalItem } from "../../api/eval-client";
import { useEvalStore } from "../../store/useEvalStore";
import { useHashRoute } from "../../hooks/useHashRoute";
import type { EvalSetDetail as EvalSetDetailType, EvalItem, EvaluatorInfo, LocalEvaluator } from "../../types/eval";
import { getSchemaConfigFields } from "../evaluators/EvaluatorDetail";

interface Props {
  evalSetId: string;
}

function truncateJson(val: unknown, max = 60): string {
  const s = typeof val === "string" ? val : JSON.stringify(val);
  if (!s || s === "null") return "-";
  return s.length > max ? s.slice(0, max) + "..." : s;
}

type SidebarTab = "io" | "evaluators";

export default function EvalSetDetail({ evalSetId }: Props) {
  const [detail, setDetail] = useState<EvalSetDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedItemName, setSelectedItemName] = useState<string | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("io");
  const evaluators = useEvalStore((s) => s.evaluators);
  const localEvaluators = useEvalStore((s) => s.localEvaluators);
  const storeUpdateEvaluators = useEvalStore((s) => s.updateEvalSetEvaluators);
  const incrementEvalSetCount = useEvalStore((s) => s.incrementEvalSetCount);
  const upsertEvalRun = useEvalStore((s) => s.upsertEvalRun);
  const { navigate } = useHashRoute();

  // Evaluator edit popover state
  const [editOpen, setEditOpen] = useState(false);
  const [editRefs, setEditRefs] = useState<Set<string>>(new Set());
  const [editSaving, setEditSaving] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Sidebar width (resizable)
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem("evalSetSidebarWidth");
    return saved ? parseInt(saved, 10) : 320;
  });
  const [isDragging, setIsDragging] = useState(false);
  const outerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem("evalSetSidebarWidth", String(sidebarWidth));
  }, [sidebarWidth]);

  useEffect(() => {
    setLoading(true);
    setSelectedItemName(null);
    getEvalSet(evalSetId)
      .then((d) => {
        setDetail(d);
        if (d.items.length > 0) setSelectedItemName(d.items[0].name);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [evalSetId]);

  const handleRun = async () => {
    setRunLoading(true);
    try {
      const run = await startEvalRun(evalSetId);
      upsertEvalRun(run);
      navigate(`#/evals/runs/${run.id}`);
    } catch (err) {
      console.error(err);
    } finally {
      setRunLoading(false);
    }
  };

  const handleDeleteItem = async (itemName: string) => {
    if (!detail) return;
    try {
      await deleteEvalItem(evalSetId, itemName);
      setDetail((prev) => {
        if (!prev) return prev;
        const items = prev.items.filter((i) => i.name !== itemName);
        return { ...prev, items, eval_count: items.length };
      });
      incrementEvalSetCount(evalSetId, -1);
      if (selectedItemName === itemName) setSelectedItemName(null);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddItem = async () => {
    if (!detail) return;
    const itemName = `item-${detail.items.length + 1}`;
    try {
      const item = await addEvalItem(evalSetId, {
        name: itemName,
        inputs: {},
        expected_output: null,
      });
      setDetail((prev) => {
        if (!prev) return prev;
        return { ...prev, items: [...prev.items, item], eval_count: prev.eval_count + 1 };
      });
      incrementEvalSetCount(evalSetId);
      setSelectedItemName(itemName);
      setSidebarTab("io");
    } catch (err) {
      console.error(err);
    }
  };

  const handleItemUpdated = (updated: EvalItem, oldName?: string) => {
    setDetail((prev) => {
      if (!prev) return prev;
      const matchName = oldName ?? updated.name;
      return {
        ...prev,
        items: prev.items.map((it) => it.name === matchName ? updated : it),
      };
    });
    if (oldName && selectedItemName === oldName) {
      setSelectedItemName(updated.name);
    }
  };

  // --- Evaluator edit popover ---
  const openEditPopover = useCallback(() => {
    if (detail) {
      setEditRefs(new Set(detail.evaluator_ids));
    }
    setEditOpen(true);
  }, [detail]);

  const toggleEditRef = (id: string) => {
    setEditRefs((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSaveEvaluators = async () => {
    if (!detail) return;
    setEditSaving(true);
    try {
      const updated = await updateEvalSetEvaluators(evalSetId, Array.from(editRefs));
      setDetail(updated);
      storeUpdateEvaluators(evalSetId, updated.evaluator_ids);
      setEditOpen(false);
    } catch (err) {
      console.error(err);
    } finally {
      setEditSaving(false);
    }
  };

  // Click-outside to close popover
  useEffect(() => {
    if (!editOpen) return;
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setEditOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [editOpen]);

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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-sm">
        Loading...
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--text-muted)]">
        Eval set not found
      </div>
    );
  }

  const selectedItem = detail.items.find((i) => i.name === selectedItemName) ?? null;

  return (
    <div ref={outerRef} className="flex h-full">
      {/* Main content: header + item grid */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header bar */}
        <div className="px-4 h-10 border-b shrink-0 flex items-center gap-4" style={{ borderColor: "var(--border)" }}>
          <h1 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
            {detail.name}
          </h1>
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
            {detail.eval_count} items
          </span>
          <div className="flex gap-1 items-center ml-auto relative">
            <button
              onClick={openEditPopover}
              className="w-7 h-7 flex items-center justify-center rounded cursor-pointer transition-colors"
              style={{ color: "var(--text-muted)", background: "transparent", border: "none" }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.background = "var(--bg-secondary)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.background = "transparent"; }}
              title="Edit evaluators"
              aria-label="Edit evaluators"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                <path d="m15 5 4 4" />
              </svg>
            </button>
            {detail.evaluator_ids.map((id) => {
              const ev = evaluators.find((e) => e.id === id);
              return (
                <span
                  key={id}
                  className="px-1.5 py-0.5 rounded text-[11px] font-medium"
                  style={{ background: "var(--bg-tertiary)", color: "var(--text-secondary)" }}
                >
                  {ev?.name ?? id}
                </span>
              );
            })}
            {editOpen && (
              <div
                ref={popoverRef}
                className="absolute top-full right-0 mt-1 z-50 rounded-md border shadow-lg"
                style={{
                  background: "var(--bg-primary)",
                  borderColor: "var(--border)",
                  minWidth: 220,
                }}
              >
                <div className="px-3 py-2 border-b text-[10px] uppercase tracking-wide font-semibold"
                  style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}>
                  Evaluators
                </div>
                <div className="max-h-48 overflow-y-auto">
                  {localEvaluators.length === 0 ? (
                    <div className="px-3 py-3 text-xs" style={{ color: "var(--text-muted)" }}>
                      No evaluators available
                    </div>
                  ) : (
                    localEvaluators.map((ev) => (
                      <label
                        key={ev.id}
                        className="flex items-center gap-2 px-3 py-1.5 text-xs cursor-pointer transition-colors"
                        style={{ borderBottom: "1px solid var(--border)" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                      >
                        <input
                          type="checkbox"
                          checked={editRefs.has(ev.id)}
                          onChange={() => toggleEditRef(ev.id)}
                          className="accent-[var(--accent)]"
                        />
                        <span className="flex-1 truncate" style={{ color: "var(--text-primary)" }}>{ev.name}</span>
                      </label>
                    ))
                  )}
                </div>
                <div className="px-3 py-2 border-t flex justify-end" style={{ borderColor: "var(--border)" }}>
                  <button
                    onClick={handleSaveEvaluators}
                    disabled={editSaving}
                    className="px-3 py-1 text-[11px] font-semibold rounded cursor-pointer transition-colors disabled:opacity-50"
                    style={{ background: "var(--accent)", color: "var(--bg-primary)", border: "none" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--accent-hover)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "var(--accent)"; }}
                  >
                    {editSaving ? "Saving..." : "Update"}
                  </button>
                </div>
              </div>
            )}
          </div>
          <button
            onClick={handleRun}
            disabled={runLoading}
            className="ml-2 px-3 py-1 h-7 text-xs font-semibold rounded border flex items-center gap-1.5 cursor-pointer transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            style={{ color: "var(--success)", borderColor: "var(--success)", background: "transparent" }}
            onMouseEnter={(e) => { if (!runLoading) e.currentTarget.style.background = "color-mix(in srgb, var(--success) 10%, transparent)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            title="Run eval set"
            aria-label="Run eval set"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none">
              <polygon points="5,3 19,12 5,21" />
            </svg>
            {runLoading ? "Running..." : "Run"}
          </button>
          <button
            onClick={handleAddItem}
            className="ml-1 px-3 py-1 h-7 text-xs font-semibold rounded border flex items-center gap-1.5 cursor-pointer transition-colors"
            style={{ color: "var(--text-muted)", borderColor: "var(--border)", background: "transparent" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.borderColor = "var(--text-muted)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.borderColor = "var(--border)"; }}
            title="Add eval item"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Add Item
          </button>
        </div>

        {/* Table header */}
        <div
          className="flex items-center px-3 h-7 text-[11px] font-semibold shrink-0 border-b"
          style={{ color: "var(--text-muted)", background: "var(--bg-secondary)", borderColor: "var(--border)" }}
        >
          <span className="w-56 shrink-0">Name</span>
          <span className="flex-1 min-w-0">Input</span>
          <span className="w-32 shrink-0 pl-2">Expected Behavior</span>
          <span className="w-32 shrink-0 pl-2">Expected Output</span>
          <span className="w-32 shrink-0 pl-2">Simulation Instr.</span>
          <span className="w-20 shrink-0 pl-2">Evaluators</span>
        </div>

        {/* Scrollable item rows */}
        <div className="flex-1 overflow-y-auto">
          {detail.items.map((item: EvalItem) => {
            const isSelected = item.name === selectedItemName;
            return (
              <button
                key={item.name}
                onClick={() => setSelectedItemName(isSelected ? null : item.name)}
                className="group w-full text-left px-3 py-1.5 flex items-center text-xs border-b transition-colors cursor-pointer"
                style={{
                  borderColor: "var(--border)",
                  background: isSelected ? "color-mix(in srgb, var(--accent) 10%, var(--bg-primary))" : undefined,
                  borderLeft: isSelected ? "3px solid var(--accent)" : "3px solid transparent",
                }}
                onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "var(--bg-hover)"; }}
                onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = ""; }}
              >
                {/* Evaluation Name */}
                <span className="w-56 shrink-0 truncate" style={{ color: "var(--text-primary)" }}>
                  {item.name}
                </span>
                {/* Input */}
                <span className="flex-1 min-w-0 truncate font-mono text-[11px]" style={{ color: "var(--text-muted)" }}>
                  {truncateJson(item.inputs)}
                </span>
                {/* Expected Behavior */}
                <span className="w-32 shrink-0 truncate pl-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
                  {item.expected_behavior || "-"}
                </span>
                {/* Expected Output */}
                <span className="w-32 shrink-0 truncate pl-2 font-mono text-[11px]" style={{ color: "var(--text-muted)" }}>
                  {truncateJson(item.expected_output, 40)}
                </span>
                {/* Simulation Instructions */}
                <span className="w-32 shrink-0 truncate pl-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
                  {item.simulation_instructions || "-"}
                </span>
                {/* Evaluators count */}
                <span
                  className="w-20 shrink-0 pl-2 text-[11px]"
                  onClick={(e) => { e.stopPropagation(); setSelectedItemName(item.name); setSidebarTab("evaluators"); }}
                >
                  {(() => {
                    const count = Object.keys(item.evaluation_criterias ?? {}).length;
                    return count > 0 ? (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ background: "rgba(34,197,94,0.1)", color: "var(--success)" }}>
                        {count} active
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>none</span>
                    );
                  })()}
                </span>
              </button>
            );
          })}
          {detail.items.length === 0 && (
            <div className="flex items-center justify-center py-8 text-[var(--text-muted)] text-xs">
              No items in this eval set
            </div>
          )}
        </div>
      </div>

      {/* Sidebar drag handle */}
      <div
        onMouseDown={onSidebarResizeStart}
        onTouchStart={onSidebarResizeStart}
        className={`shrink-0 drag-handle-col${isDragging ? "" : " transition-all"}`}
        style={{ width: selectedItem ? 3 : 0, opacity: selectedItem ? 1 : 0 }}
      />

      {/* Right sidebar */}
      <div
        className={`shrink-0 flex flex-col overflow-hidden${isDragging ? "" : " transition-[width] duration-200 ease-in-out"}`}
        style={{ width: selectedItem ? sidebarWidth : 0, background: "var(--bg-primary)" }}
      >
        {/* Tab bar */}
        <div
          className="flex items-center gap-1 px-2 h-10 border-b shrink-0"
          style={{ borderColor: "var(--border)", background: "var(--bg-secondary)", minWidth: sidebarWidth }}
        >
          {(["io", "evaluators"] as const).map((tab) => {
            const active = sidebarTab === tab;
            const label = tab === "io" ? "I/O" : "Evaluators";
            return (
              <button
                key={tab}
                onClick={() => setSidebarTab(tab)}
                className="px-2.5 py-1 h-7 text-xs font-semibold rounded inline-flex items-center cursor-pointer transition-colors"
                style={{
                  color: active ? "var(--accent)" : "var(--text-muted)",
                  background: active ? "color-mix(in srgb, var(--accent) 10%, transparent)" : "transparent",
                  border: "none",
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden" style={{ minWidth: sidebarWidth }}>
          {selectedItem ? (
            sidebarTab === "io" ? (
              <ItemIOView item={selectedItem} evalSetId={evalSetId} onItemUpdated={handleItemUpdated} onDelete={handleDeleteItem} />
            ) : (
              <ItemEvaluatorsView
                item={selectedItem}
                evalSetId={evalSetId}
                evalSetEvaluatorIds={detail?.evaluator_ids ?? []}
                evaluators={evaluators}
                localEvaluators={localEvaluators}
                onItemUpdated={handleItemUpdated}
              />
            )
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** Inline-editable field: click to edit, blur/Enter to save, Escape to cancel. */
function InlineField({
  label,
  value,
  placeholder,
  onSave,
  mono,
  multiline,
}: {
  label: string;
  value: string;
  placeholder: string;
  onSave: (val: string) => void;
  mono?: boolean;
  multiline?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const ref = useRef<HTMLTextAreaElement | HTMLInputElement>(null);

  useEffect(() => { setDraft(value); }, [value]);
  useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);

  const save = () => {
    setEditing(false);
    if (draft !== value) onSave(draft);
  };
  const cancel = () => { setEditing(false); setDraft(value); };
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") cancel();
    if (e.key === "Enter" && !multiline) save();
    if (e.key === "Enter" && e.metaKey && multiline) save();
  };

  const inputStyle: React.CSSProperties = {
    background: "var(--bg-primary)",
    border: "1px solid var(--border)",
    color: "var(--text-primary)",
  };

  return (
    <div className="overflow-hidden" style={{ border: "1px solid var(--border)" }}>
      <div
        className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide"
        style={{ background: "var(--bg-secondary)", color: "var(--text-muted)" }}
      >
        {label}
      </div>
      {editing ? (
        <div className="px-2 py-1.5">
          {multiline ? (
            <textarea
              ref={ref as React.RefObject<HTMLTextAreaElement>}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={save}
              onKeyDown={onKeyDown}
              rows={Math.max(3, draft.split("\n").length + 1)}
              className={`w-full rounded px-2 py-1.5 text-xs resize-y outline-none ${mono ? "font-mono" : "leading-relaxed"}`}
              style={inputStyle}
            />
          ) : (
            <input
              ref={ref as React.RefObject<HTMLInputElement>}
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={save}
              onKeyDown={onKeyDown}
              className="w-full rounded px-2 py-1.5 text-xs outline-none"
              style={inputStyle}
            />
          )}
        </div>
      ) : (
        <div
          className={`px-3 py-2 text-xs cursor-text transition-colors ${mono ? "font-mono whitespace-pre-wrap break-words" : "leading-relaxed whitespace-pre-wrap"}`}
          style={{ color: value ? "var(--text-primary)" : "var(--text-muted)", minHeight: 28 }}
          onClick={() => setEditing(true)}
          title="Click to edit"
        >
          {value || placeholder}
        </div>
      )}
    </div>
  );
}

function ItemIOView({
  item,
  evalSetId,
  onItemUpdated,
  onDelete,
}: {
  item: EvalItem;
  evalSetId: string;
  onItemUpdated: (updated: EvalItem, oldName?: string) => void;
  onDelete: (name: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => { setError(null); setConfirmDelete(false); }, [item.name]);

  const saveField = async (field: string, value: string) => {
    setError(null);
    try {
      const body: Record<string, unknown> = {};
      if (field === "name") {
        body.name = value.trim() || item.name;
      } else if (field === "inputs") {
        try { body.inputs = JSON.parse(value); } catch { setError("Invalid JSON"); return; }
      } else if (field === "expected_output") {
        if (!value.trim()) { body.expected_output = null; }
        else { try { body.expected_output = JSON.parse(value); } catch { body.expected_output = value; } }
      } else if (field === "expected_behavior") {
        body.expected_behavior = value;
      } else if (field === "simulation_instructions") {
        body.simulation_instructions = value;
      }
      const oldName = item.name;
      const updated = await updateEvalItem(evalSetId, oldName, body);
      onItemUpdated(updated, field === "name" && updated.name !== oldName ? oldName : undefined);
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail;
      setError(detail ?? "Failed to save");
    }
  };

  const inputJson = JSON.stringify(item.inputs, null, 2);
  const expectedOutputStr = item.expected_output != null
    ? (typeof item.expected_output === "string" ? item.expected_output : JSON.stringify(item.expected_output, null, 2))
    : "";

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 overflow-y-auto flex-1 space-y-1.5">
        {error && (
          <div className="px-2 py-1.5 rounded text-[11px]" style={{ background: "rgba(239,68,68,0.1)", color: "var(--error)" }}>{error}</div>
        )}
        <InlineField label="Name" value={item.name} placeholder="Item name" onSave={(v) => saveField("name", v)} />
        <InlineField label="Input" value={inputJson} placeholder="{ }" onSave={(v) => saveField("inputs", v)} mono multiline />
        <InlineField label="Expected Output" value={expectedOutputStr} placeholder="+ Add expected output" onSave={(v) => saveField("expected_output", v)} mono multiline />
        <InlineField label="Expected Behavior" value={item.expected_behavior ?? ""} placeholder="+ Add expected behavior" onSave={(v) => saveField("expected_behavior", v)} multiline />
        <InlineField label="Simulation Instructions" value={item.simulation_instructions ?? ""} placeholder="+ Add simulation instructions" onSave={(v) => saveField("simulation_instructions", v)} multiline />
      </div>
      <div className="shrink-0 p-2 border-t" style={{ borderColor: "var(--border)" }}>
        {confirmDelete ? (
          <div className="flex items-center gap-2">
            <span className="text-[11px]" style={{ color: "var(--error)" }}>Delete this item?</span>
            <button
              onClick={() => onDelete(item.name)}
              className="px-2 py-1 text-[11px] font-semibold rounded cursor-pointer"
              style={{ background: "var(--error)", color: "#fff", border: "none" }}
            >
              Yes, delete
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="px-2 py-1 text-[11px] rounded cursor-pointer"
              style={{ color: "var(--text-muted)", background: "transparent", border: "1px solid var(--border)" }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="w-full py-1.5 text-[11px] rounded cursor-pointer transition-colors"
            style={{ color: "var(--error)", background: "transparent", border: "none" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(239,68,68,0.08)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            Delete Item
          </button>
        )}
      </div>
    </div>
  );
}

/** Resolve the criteria schema for a local evaluator via the built-in evaluator catalog. */
function getCriteriaFields(evId: string, localEvaluators: LocalEvaluator[], builtInEvaluators: EvaluatorInfo[]) {
  const local = localEvaluators.find((e) => e.id === evId);
  if (!local) return [];
  const builtIn = builtInEvaluators.find((e) => e.id === local.evaluator_type_id);
  if (!builtIn?.criteria_schema) return [];
  return getSchemaConfigFields(builtIn.criteria_schema as Record<string, unknown>);
}

/** Show a summary of the evaluator's config (from the evaluator JSON file). */
function EvaluatorConfigSummary({ evId, localEvaluators }: { evId: string; localEvaluators: LocalEvaluator[] }) {
  const local = localEvaluators.find((e) => e.id === evId);
  if (!local) return null;
  const cfg = local.config ?? {};
  const entries = Object.entries(cfg).filter(([k]) => k !== "name");
  if (entries.length === 0) return null;
  return (
    <div className="px-3 py-2 border-t space-y-1" style={{ borderColor: "var(--border)" }}>
      <div className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        Evaluator config
      </div>
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-start gap-2 text-[11px]">
          <span className="font-medium shrink-0" style={{ color: "var(--text-muted)" }}>{k}:</span>
          <span className="font-mono break-all" style={{ color: "var(--text-secondary)" }}>
            {typeof v === "string" && v.length > 80 ? v.slice(0, 80) + "..." : String(v)}
          </span>
        </div>
      ))}
    </div>
  );
}

function ItemEvaluatorsView({
  item,
  evalSetId,
  evalSetEvaluatorIds,
  evaluators,
  localEvaluators,
  onItemUpdated,
}: {
  item: EvalItem;
  evalSetId: string;
  evalSetEvaluatorIds: string[];
  evaluators: EvaluatorInfo[];
  localEvaluators: LocalEvaluator[];
  onItemUpdated: (updated: EvalItem) => void;
}) {
  const criterias = item.evaluation_criterias ?? {};
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEditingId(null);
    setError(null);
  }, [item.name]);

  const saveCriterias = async (newCriterias: Record<string, unknown>) => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateEvalItemEvaluators(evalSetId, item.name, newCriterias);
      onItemUpdated(updated);
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail;
      setError(detail ?? "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = (evId: string) => {
    const next = { ...criterias };
    if (evId in next) {
      delete next[evId];
    } else {
      next[evId] = null as unknown as Record<string, unknown>;
    }
    saveCriterias(next);
  };

  const handleStartEdit = (evId: string) => {
    const val = criterias[evId];
    setEditValues(val != null && typeof val === "object" ? { ...(val as Record<string, unknown>) } : {});
    setEditingId(evId);
    setError(null);
  };

  const handleSaveEdit = (evId: string) => {
    const fields = getCriteriaFields(evId, localEvaluators, evaluators);
    // If no schema fields, save the editValues as-is; empty object means null (defaults)
    const hasValues = fields.length > 0
      ? fields.some((f) => editValues[f.key] !== undefined && editValues[f.key] !== null && editValues[f.key] !== "")
      : Object.keys(editValues).length > 0;
    const val = hasValues ? editValues : null;
    const next = { ...criterias, [evId]: val as Record<string, unknown> };
    saveCriterias(next).then(() => setEditingId(null));
  };

  const enabled = Object.keys(criterias);
  const setRefIds = new Set(evalSetEvaluatorIds);
  const available = localEvaluators.filter((ev) => setRefIds.has(ev.id) && !(ev.id in criterias));
  const orphanedIds = enabled.filter((id) => !setRefIds.has(id));

  const inputStyle = {
    background: "var(--bg-primary)",
    border: "1px solid var(--border)",
    color: "var(--text-primary)",
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 overflow-y-auto flex-1 space-y-1.5">
        {error && (
          <div className="px-2 py-1.5 rounded text-[11px]" style={{ background: "rgba(239,68,68,0.1)", color: "var(--error)" }}>
            {error}
          </div>
        )}

        {orphanedIds.length > 0 && (
          <div className="px-2 py-1.5 rounded text-[11px]" style={{ background: "rgba(229,160,13,0.1)", color: "var(--warning)" }}>
            {orphanedIds.length} evaluator{orphanedIds.length > 1 ? "s" : ""} referenced but not in eval set: {orphanedIds.join(", ")}. Add {orphanedIds.length > 1 ? "them" : "it"} to the eval set or remove from this item.
          </div>
        )}

        {enabled.length > 0 && (
          <>
            {enabled.map((evId) => {
              const ev = evaluators.find((e) => e.id === evId) ?? localEvaluators.find((e) => e.id === evId);
              const val = criterias[evId];
              const isEditing = editingId === evId;
              const criteriaFields = getCriteriaFields(evId, localEvaluators, evaluators);
              return (
                <div
                  key={evId}
                  className="overflow-hidden"
                  style={{ border: "1px solid var(--border)" }}
                >
                  <div
                    className="px-3 py-2 flex items-center gap-2"
                    style={{ background: "var(--bg-secondary)" }}
                  >
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ background: "var(--success)" }} />
                    <span className="text-[11px] font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                      {ev?.name ?? evId}
                    </span>
                    <span className="ml-auto flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={() => isEditing ? setEditingId(null) : handleStartEdit(evId)}
                        className="text-[10px] px-1.5 py-0.5 rounded cursor-pointer transition-colors"
                        style={{ color: "var(--text-muted)", background: "transparent", border: "none" }}
                        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
                      >
                        {isEditing ? "Cancel" : "Edit"}
                      </button>
                      <button
                        onClick={() => handleToggle(evId)}
                        disabled={saving}
                        className="text-[10px] px-1.5 py-0.5 rounded cursor-pointer transition-colors"
                        style={{ color: "var(--error)", background: "transparent", border: "none" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(239,68,68,0.1)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                        title="Remove evaluator from this item"
                      >
                        Remove
                      </button>
                    </span>
                  </div>
                  {isEditing ? (
                    <div className="px-3 py-2 border-t space-y-2" style={{ borderColor: "var(--border)" }}>
                      {criteriaFields.length > 0 ? (
                        <>
                          {criteriaFields.map((f) => {
                            const fieldVal = editValues[f.key] ?? "";
                            if (f.type === "boolean") {
                              return (
                                <label key={f.key} className="flex items-center gap-2 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={Boolean(fieldVal)}
                                    onChange={(e) => setEditValues((prev) => ({ ...prev, [f.key]: e.target.checked }))}
                                    className="accent-[var(--accent)]"
                                  />
                                  <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>{f.title}</span>
                                </label>
                              );
                            }
                            if (f.type === "number" || f.type === "integer") {
                              return (
                                <div key={f.key}>
                                  <label className="block text-[10px] font-medium mb-1" style={{ color: "var(--text-muted)" }}>{f.title}</label>
                                  <input
                                    type="number"
                                    value={fieldVal === null ? "" : Number(fieldVal)}
                                    onChange={(e) => setEditValues((prev) => ({ ...prev, [f.key]: e.target.value === "" ? null : Number(e.target.value) }))}
                                    step={f.type === "integer" ? 1 : 0.1}
                                    className="w-full rounded px-2 py-1 text-[11px]"
                                    style={inputStyle}
                                  />
                                </div>
                              );
                            }
                            if (f.type === "array") {
                              const arrVal = Array.isArray(fieldVal) ? fieldVal : [];
                              return (
                                <div key={f.key}>
                                  <label className="block text-[10px] font-medium mb-1" style={{ color: "var(--text-muted)" }}>{f.title}</label>
                                  <textarea
                                    value={arrVal.length > 0 ? JSON.stringify(arrVal, null, 2) : ""}
                                    onChange={(e) => {
                                      try { setEditValues((prev) => ({ ...prev, [f.key]: JSON.parse(e.target.value) })); } catch { /* let them type */ }
                                    }}
                                    rows={3}
                                    placeholder='["item1", "item2"]'
                                    className="w-full rounded px-2 py-1 text-[11px] font-mono resize-y"
                                    style={inputStyle}
                                  />
                                </div>
                              );
                            }
                            // string / object
                            const isLong = typeof fieldVal === "string" && fieldVal.length > 60;
                            return (
                              <div key={f.key}>
                                <label className="block text-[10px] font-medium mb-1" style={{ color: "var(--text-muted)" }}>{f.title}</label>
                                {isLong || f.type === "object" ? (
                                  <textarea
                                    value={typeof fieldVal === "object" ? JSON.stringify(fieldVal, null, 2) : String(fieldVal)}
                                    onChange={(e) => setEditValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                                    rows={4}
                                    className="w-full rounded px-2 py-1 text-[11px] font-mono resize-y"
                                    style={inputStyle}
                                  />
                                ) : (
                                  <input
                                    type="text"
                                    value={String(fieldVal)}
                                    onChange={(e) => setEditValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                                    className="w-full rounded px-2 py-1 text-[11px]"
                                    style={inputStyle}
                                  />
                                )}
                              </div>
                            );
                          })}
                        </>
                      ) : (
                        <textarea
                          value={Object.keys(editValues).length > 0 ? JSON.stringify(editValues, null, 2) : ""}
                          onChange={(e) => { try { setEditValues(JSON.parse(e.target.value)); } catch { /* let them type */ } }}
                          rows={4}
                          placeholder="Custom criteria JSON (leave empty for defaults)"
                          className="w-full rounded px-2 py-1.5 text-[11px] font-mono resize-y"
                          style={inputStyle}
                        />
                      )}
                      <button
                        onClick={() => handleSaveEdit(evId)}
                        disabled={saving}
                        className="px-2.5 py-1 text-[10px] font-semibold rounded cursor-pointer transition-colors disabled:opacity-40"
                        style={{ background: "var(--accent)", color: "var(--bg-primary)", border: "none" }}
                      >
                        {saving ? "Saving..." : "Save"}
                      </button>
                    </div>
                  ) : (
                    <>
                      {val != null ? (
                        <div className="px-3 py-2 border-t" style={{ borderColor: "var(--border)" }}>
                          <div className="text-[10px] font-semibold uppercase tracking-wide mb-1" style={{ color: "var(--text-muted)" }}>
                            Custom criteria
                          </div>
                          <pre className="text-[11px] font-mono whitespace-pre-wrap break-words max-h-32 overflow-y-auto" style={{ color: "var(--text-secondary)" }}>
                            {JSON.stringify(val, null, 2)}
                          </pre>
                        </div>
                      ) : (
                        <EvaluatorConfigSummary evId={evId} localEvaluators={localEvaluators} />
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </>
        )}

        {available.length > 0 && (
          <>
            <div
              className="text-[10px] uppercase tracking-wide font-semibold pt-2 pb-1 px-1"
              style={{ color: "var(--text-muted)" }}
            >
              Add evaluator
            </div>
            {available.map((ev) => (
              <button
                key={ev.id}
                onClick={() => handleToggle(ev.id)}
                disabled={saving}
                className="w-full text-left px-3 py-2 rounded flex items-center gap-2 cursor-pointer transition-colors disabled:opacity-40"
                style={{ border: "1px dashed var(--border)", background: "transparent" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.borderColor = "var(--text-muted)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = "var(--border)"; }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <span className="text-[11px] truncate" style={{ color: "var(--text-primary)" }}>{ev.name}</span>
                <span className="ml-auto text-[10px]" style={{ color: "var(--text-muted)" }}>{ev.type}</span>
              </button>
            ))}
          </>
        )}

        {enabled.length === 0 && available.length === 0 && (
          <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-xs text-center px-4">
            {evalSetEvaluatorIds.length === 0
              ? "No evaluators on this eval set. Add evaluators to the eval set first using the edit button in the header."
              : "All eval set evaluators are assigned to this item."}
          </div>
        )}
      </div>
    </div>
  );
}
