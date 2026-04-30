import { create } from "zustand";
import type { RunSummary, TraceSpan, LogEntry, ToolCallConfirmation } from "../types/run";
import type { GraphData } from "../types/graph";

export interface ChatToolCall {
  tool_call_id: string;
  name: string;
  has_result: boolean;
  cancelled?: boolean;
  require_confirmation?: boolean;
  input?: unknown;
  input_schema?: unknown;
  confirmation?: ToolCallConfirmation;
}

export function projectToolCall(tc: Record<string, unknown>): ChatToolCall {
  const confirmationRaw = (tc.confirmation as Record<string, unknown> | undefined) ?? undefined;
  const resultRaw = tc.result as Record<string, unknown> | undefined;
  return {
    tool_call_id: ((tc.toolCallId ?? tc.tool_call_id) as string) ?? "",
    name: (tc.name as string) ?? "",
    has_result: !!resultRaw,
    cancelled: resultRaw ? ((resultRaw.cancelled as boolean | undefined) ?? undefined) : undefined,
    require_confirmation:
      (tc.requireConfirmation ?? tc.require_confirmation) as boolean | undefined,
    input: tc.input,
    input_schema: tc.inputSchema ?? tc.input_schema,
    confirmation: confirmationRaw
      ? {
          approved: (confirmationRaw.approved as boolean) ?? false,
          input: confirmationRaw.input,
          confirmed_at: (confirmationRaw.confirmedAt ?? confirmationRaw.confirmed_at) as
            | string
            | null
            | undefined,
        }
      : undefined,
  };
}

interface ChatMsg {
  message_id: string;
  role: string;
  content: string;
  tool_calls?: ChatToolCall[];
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
  toggleBreakpoint: (runId: string, nodeId: string) => void;
  clearBreakpoints: (runId: string) => void;

  activeNodes: Record<string, { executing: Record<string, string | null>; prev: string | null }>;
  setActiveNode: (runId: string, nodeName: string, qualifiedNodeName?: string | null) => void;
  removeActiveNode: (runId: string, nodeName: string) => void;
  resetRunGraphState: (runId: string) => void;

  stateEvents: Record<string, { node_name: string; qualified_node_name?: string | null; phase?: string | null; timestamp: number; payload?: Record<string, unknown> }[]>;
  addStateEvent: (runId: string, nodeName: string, payload?: Record<string, unknown>, qualifiedNodeName?: string | null, phase?: string | null) => void;
  setStateEvents: (runId: string, events: { node_name: string; qualified_node_name?: string | null; phase?: string | null; timestamp: number; payload?: Record<string, unknown> }[]) => void;

  focusedSpan: { name: string; index: number } | null;
  setFocusedSpan: (span: { name: string; index: number } | null) => void;

  reloadPending: boolean;
  setReloadPending: (val: boolean) => void;

  graphCache: Record<string, GraphData>;
  setGraphCache: (runId: string, data: GraphData) => void;
}

export const useRunStore = create<RunStore>((set) => ({
  runs: {},
  selectedRunId: null,
  traces: {},
  logs: {},
  chatMessages: {},
  entrypoints: [],

  setRuns: (runs) =>
    set((state) => {
      let bps = state.breakpoints;
      for (const r of runs) {
        if (r.breakpoints?.length && !bps[r.id]) {
          bps = { ...bps, [r.id]: Object.fromEntries(r.breakpoints.map((id) => [id, true])) };
        }
      }
      const result: Partial<RunStore> = { runs: Object.fromEntries(runs.map((r) => [r.id, r])) };
      if (bps !== state.breakpoints) result.breakpoints = bps;
      return result;
    }),

  upsertRun: (run) =>
    set((state) => {
      const result: Partial<RunStore> = { runs: { ...state.runs, [run.id]: run } };
      if (run.breakpoints?.length && !state.breakpoints[run.id]) {
        result.breakpoints = {
          ...state.breakpoints,
          [run.id]: Object.fromEntries(run.breakpoints.map((id) => [id, true])),
        };
      }
      // Clear active node tracking when run reaches terminal status
      if (
        (run.status === "completed" || run.status === "failed") &&
        state.activeNodes[run.id]
      ) {
        const { [run.id]: _, ...rest } = state.activeNodes;
        result.activeNodes = rest;
      }
      return result;
    }),

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

      // requireConfirmation/inputSchema/input live on event.toolCall.startToolCall,
      // not on the persisted message.toolCalls entry. Pull them from the current
      // event and merge with the existing in-store tool call so they survive
      // subsequent events (endToolCall, etc.) for the same toolCallId.
      const event = payload.event as Record<string, unknown> | undefined;
      const eventToolCall = event?.toolCall as Record<string, unknown> | undefined;
      const startToolCall = eventToolCall?.startToolCall as
        | Record<string, unknown>
        | undefined;
      const eventToolCallId = eventToolCall?.toolCallId as string | undefined;

      const previousById = new Map<string, ChatToolCall>();
      const previousMsg = existing.find((m) => m.message_id === messageId);
      if (previousMsg?.tool_calls) {
        for (const tc of previousMsg.tool_calls) {
          previousById.set(tc.tool_call_id, tc);
        }
      }

      // Extract tool calls (camelCase: toolCalls)
      const toolCalls = (
        ((msg.toolCalls ?? msg.tool_calls) as Array<Record<string, unknown>>) ?? []
      ).map((tc) => {
        const projected = projectToolCall(tc);
        const prev = previousById.get(projected.tool_call_id);
        if (prev) {
          if (projected.require_confirmation === undefined)
            projected.require_confirmation = prev.require_confirmation;
          if (projected.input_schema === undefined)
            projected.input_schema = prev.input_schema;
          if (projected.input === undefined) projected.input = prev.input;
        }
        if (startToolCall && eventToolCallId === projected.tool_call_id) {
          if (startToolCall.requireConfirmation !== undefined)
            projected.require_confirmation = startToolCall.requireConfirmation as boolean;
          if (startToolCall.inputSchema !== undefined)
            projected.input_schema = startToolCall.inputSchema;
          if (startToolCall.input !== undefined) projected.input = startToolCall.input;
        }
        return projected;
      });

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
  toggleBreakpoint: (runId, nodeId) =>
    set((state) => {
      const bps = { ...(state.breakpoints[runId] ?? {}) };
      if (bps[nodeId]) {
        delete bps[nodeId];
      } else {
        bps[nodeId] = true;
      }
      return { breakpoints: { ...state.breakpoints, [runId]: bps } };
    }),
  clearBreakpoints: (runId) =>
    set((state) => {
      const { [runId]: _, ...rest } = state.breakpoints;
      return { breakpoints: rest };
    }),

  activeNodes: {},
  setActiveNode: (runId, nodeName, qualifiedNodeName) =>
    set((state) => {
      const existing = state.activeNodes[runId] ?? { executing: {}, prev: null };
      return {
        activeNodes: {
          ...state.activeNodes,
          [runId]: {
            executing: { ...existing.executing, [nodeName]: qualifiedNodeName ?? null },
            prev: existing.prev,
          },
        },
      };
    }),
  removeActiveNode: (runId, nodeName) =>
    set((state) => {
      const existing = state.activeNodes[runId];
      if (!existing) return state;
      const { [nodeName]: _, ...rest } = existing.executing;
      return {
        activeNodes: {
          ...state.activeNodes,
          [runId]: { executing: rest, prev: nodeName },
        },
      };
    }),
  resetRunGraphState: (runId) =>
    set((state) => ({
      stateEvents: { ...state.stateEvents, [runId]: [] },
      activeNodes: { ...state.activeNodes, [runId]: { executing: {}, prev: null } },
    })),

  stateEvents: {},
  addStateEvent: (runId, nodeName, payload, qualifiedNodeName, phase) =>
    set((state) => {
      const existing = state.stateEvents[runId] ?? [];
      return {
        stateEvents: {
          ...state.stateEvents,
          [runId]: [...existing, { node_name: nodeName, qualified_node_name: qualifiedNodeName, phase, timestamp: Date.now(), payload }],
        },
      };
    }),
  setStateEvents: (runId, events) =>
    set((state) => ({
      stateEvents: { ...state.stateEvents, [runId]: events },
    })),

  focusedSpan: null,
  setFocusedSpan: (span) => set({ focusedSpan: span }),

  reloadPending: false,
  setReloadPending: (val) => set({ reloadPending: val }),

  graphCache: {},
  setGraphCache: (runId, data) =>
    set((state) => ({ graphCache: { ...state.graphCache, [runId]: data } })),
}));
