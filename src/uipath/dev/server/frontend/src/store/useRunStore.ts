import { create } from "zustand";
import type { RunSummary, TraceSpan, LogEntry } from "../types/run";

interface ChatMsg {
  message_id: string;
  role: string;
  content: string;
  tool_calls?: { name: string; has_result: boolean }[];
}

interface RunStore {
  runs: Record<string, RunSummary>;
  selectedRunId: string | null;
  traces: Record<string, TraceSpan[]>;
  logs: Record<string, LogEntry[]>;
  chatMessages: Record<string, ChatMsg[]>;
  entrypoints: string[];

  setRuns: (runs: RunSummary[]) => void;
  upsertRun: (run: RunSummary) => void;
  selectRun: (runId: string | null) => void;

  addTrace: (trace: TraceSpan) => void;
  setTraces: (runId: string, traces: TraceSpan[]) => void;

  addLog: (log: LogEntry) => void;
  setLogs: (runId: string, logs: LogEntry[]) => void;

  addChatEvent: (runId: string, payload: Record<string, unknown>) => void;
  addLocalChatMessage: (runId: string, msg: ChatMsg) => void;
  setChatMessages: (runId: string, messages: ChatMsg[]) => void;

  setEntrypoints: (eps: string[]) => void;

  breakpoints: Record<string, Record<string, boolean>>;
  toggleBreakpoint: (entrypoint: string, nodeId: string) => void;
  clearBreakpoints: (entrypoint: string) => void;

  focusedSpan: { name: string; index: number } | null;
  setFocusedSpan: (span: { name: string; index: number } | null) => void;
}

export const useRunStore = create<RunStore>((set) => ({
  runs: {},
  selectedRunId: null,
  traces: {},
  logs: {},
  chatMessages: {},
  entrypoints: [],

  setRuns: (runs) =>
    set({
      runs: Object.fromEntries(runs.map((r) => [r.id, r])),
    }),

  upsertRun: (run) =>
    set((state) => ({
      runs: { ...state.runs, [run.id]: run },
    })),

  selectRun: (runId) => set({ selectedRunId: runId }),

  addTrace: (trace) =>
    set((state) => {
      const existing = state.traces[trace.run_id] ?? [];
      const idx = existing.findIndex((t) => t.span_id === trace.span_id);
      const updated =
        idx >= 0
          ? existing.map((t, i) => (i === idx ? trace : t))
          : [...existing, trace];
      return { traces: { ...state.traces, [trace.run_id]: updated } };
    }),

  setTraces: (runId, traces) =>
    set((state) => ({ traces: { ...state.traces, [runId]: traces } })),

  addLog: (log) =>
    set((state) => {
      const existing = state.logs[log.run_id] ?? [];
      return { logs: { ...state.logs, [log.run_id]: [...existing, log] } };
    }),

  setLogs: (runId, logs) =>
    set((state) => ({ logs: { ...state.logs, [runId]: logs } })),

  addChatEvent: (runId, payload) =>
    set((state) => {
      const existing = state.chatMessages[runId] ?? [];
      const msg = payload.message as Record<string, unknown> | undefined;
      if (!msg) return state;

      // Server serializes with by_alias=True → camelCase
      const messageId = (msg.messageId ?? msg.message_id) as string;
      const role = (msg.role as string) ?? "assistant";

      // Extract text content (camelCase: contentParts, mimeType)
      const parts =
        ((msg.contentParts ?? msg.content_parts) as Array<Record<string, unknown>>) ?? [];
      const textParts = parts
        .filter((p) => {
          const mime = ((p.mimeType ?? p.mime_type) as string) ?? "";
          return mime.startsWith("text/") || mime === "application/json";
        })
        .map((p) => {
          const data = p.data as Record<string, unknown>;
          return (data?.inline as string) ?? "";
        });
      const content = textParts.join("\n").trim();

      // Extract tool calls (camelCase: toolCalls)
      const toolCalls = (
        ((msg.toolCalls ?? msg.tool_calls) as Array<Record<string, unknown>>) ?? []
      ).map((tc) => ({
        name: (tc.name as string) ?? "",
        has_result: !!tc.result,
      }));

      const chatMsg: ChatMsg = {
        message_id: messageId,
        role,
        content,
        tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
      };

      // Check for existing message by server ID first
      const idx = existing.findIndex((m) => m.message_id === messageId);
      if (idx >= 0) {
        return { chatMessages: { ...state.chatMessages, [runId]: existing.map((m, i) => (i === idx ? chatMsg : m)) } };
      }

      // For user messages, replace the optimistic local-* entry if one matches
      if (role === "user") {
        const localIdx = existing.findIndex(
          (m) => m.message_id.startsWith("local-") && m.role === "user" && m.content === content,
        );
        if (localIdx >= 0) {
          return { chatMessages: { ...state.chatMessages, [runId]: existing.map((m, i) => (i === localIdx ? chatMsg : m)) } };
        }
      }

      const updated = [...existing, chatMsg];

      return { chatMessages: { ...state.chatMessages, [runId]: updated } };
    }),

  addLocalChatMessage: (runId, msg) =>
    set((state) => {
      const existing = state.chatMessages[runId] ?? [];
      return { chatMessages: { ...state.chatMessages, [runId]: [...existing, msg] } };
    }),

  setChatMessages: (runId, messages) =>
    set((state) => ({
      chatMessages: { ...state.chatMessages, [runId]: messages },
    })),

  setEntrypoints: (eps) => set({ entrypoints: eps }),

  breakpoints: {},
  toggleBreakpoint: (entrypoint, nodeId) =>
    set((state) => {
      const epBps = { ...(state.breakpoints[entrypoint] ?? {}) };
      if (epBps[nodeId]) {
        delete epBps[nodeId];
      } else {
        epBps[nodeId] = true;
      }
      return { breakpoints: { ...state.breakpoints, [entrypoint]: epBps } };
    }),
  clearBreakpoints: (entrypoint) =>
    set((state) => {
      const { [entrypoint]: _, ...rest } = state.breakpoints;
      return { breakpoints: rest };
    }),

  focusedSpan: null,
  setFocusedSpan: (span) => set({ focusedSpan: span }),
}));
