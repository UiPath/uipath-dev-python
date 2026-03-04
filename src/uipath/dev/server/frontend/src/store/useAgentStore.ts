import { create } from "zustand";
import type { AgentMessage, AgentPlanItem, AgentQuestion, AgentSessionState, AgentStatus, AgentModel, AgentSkill, AgentToolCall } from "../types/agent";

let msgCounter = 0;
function nextId() {
  return `agent-msg-${++msgCounter}`;
}

interface AgentStore {
  sessionId: string | null;
  status: AgentStatus;
  _lastActiveAt: number | null;
  messages: AgentMessage[];
  plan: AgentPlanItem[];
  activeQuestion: AgentQuestion | null;
  models: AgentModel[];
  selectedModel: string | null;
  modelsLoading: boolean;
  skills: AgentSkill[];
  selectedSkillIds: string[];
  skillsLoading: boolean;

  setStatus: (status: AgentStatus) => void;
  addUserMessage: (text: string) => void;
  appendAssistantText: (content: string, done: boolean) => void;
  setPlan: (items: AgentPlanItem[]) => void;
  addToolUse: (toolCallId: string, tool: string, args: Record<string, unknown>) => void;
  addToolResult: (toolCallId: string, result: string, isError: boolean) => void;
  addToolApprovalRequest: (toolCallId: string, tool: string, args: Record<string, unknown>) => void;
  resolveToolApproval: (toolCallId: string, approved: boolean) => void;
  appendThinking: (content: string) => void;
  addError: (message: string) => void;
  setActiveQuestion: (q: AgentQuestion | null) => void;
  setSessionId: (id: string) => void;
  setModels: (models: AgentModel[]) => void;
  setSelectedModel: (model: string) => void;
  setModelsLoading: (loading: boolean) => void;
  setSkills: (skills: AgentSkill[]) => void;
  setSelectedSkillIds: (ids: string[]) => void;
  toggleSkill: (id: string) => void;
  setSkillsLoading: (loading: boolean) => void;
  hydrateSession: (state: AgentSessionState) => void;
  clearSession: () => void;
}

export const useAgentStore = create<AgentStore>((set) => ({
  sessionId: null,
  status: "idle",
  _lastActiveAt: null,
  messages: [],
  plan: [],
  activeQuestion: null,
  models: [],
  selectedModel: null,
  modelsLoading: false,
  skills: [],
  selectedSkillIds: [],
  skillsLoading: false,

  setStatus: (status) =>
    set((state) => {
      const wasActive = state.status === "thinking" || state.status === "planning" || state.status === "executing" || state.status === "awaiting_approval";
      const isActive = status === "thinking" || status === "planning" || status === "executing" || status === "awaiting_approval";
      return {
        status,
        _lastActiveAt: wasActive && !isActive ? Date.now() : state._lastActiveAt,
      };
    }),

  addUserMessage: (text) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: nextId(),
          role: "user",
          content: text,
          timestamp: Date.now(),
        },
      ],
    })),

  appendAssistantText: (content, done) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant" && !last.done) {
        // Append to existing assistant message
        msgs[msgs.length - 1] = { ...last, content: last.content + content, done };
      } else {
        msgs.push({
          id: nextId(),
          role: "assistant",
          content,
          timestamp: Date.now(),
          done,
        });
      }
      return { messages: msgs };
    }),

  setPlan: (items) =>
    set((state) => {
      const msgs = [...state.messages];
      // Find existing plan message and update it, or insert new one
      const planIdx = msgs.findIndex((m) => m.role === "plan");
      const planMsg: AgentMessage = {
        id: planIdx >= 0 ? msgs[planIdx].id : nextId(),
        role: "plan",
        content: "",
        timestamp: Date.now(),
        planItems: items,
      };
      if (planIdx >= 0) {
        msgs[planIdx] = planMsg;
      } else {
        msgs.push(planMsg);
      }
      return { messages: msgs, plan: items };
    }),

  addToolUse: (toolCallId, tool, args) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      const newCall: AgentToolCall = { tool, args, tool_call_id: toolCallId };
      // Merge into last tool message if it exists
      if (last && last.role === "tool" && last.toolCalls) {
        msgs[msgs.length - 1] = {
          ...last,
          toolCalls: [...last.toolCalls, newCall],
        };
      } else {
        msgs.push({
          id: nextId(),
          role: "tool",
          content: "",
          timestamp: Date.now(),
          toolCalls: [newCall],
        });
      }
      return { messages: msgs };
    }),

  addToolResult: (toolCallId, result, isError) =>
    set((state) => {
      const msgs = [...state.messages];
      // Match result to its tool call by tool_call_id
      for (let i = msgs.length - 1; i >= 0; i--) {
        const msg = msgs[i];
        if (msg.role === "tool" && msg.toolCalls) {
          const calls = [...msg.toolCalls];
          for (let j = 0; j < calls.length; j++) {
            if (calls[j].tool_call_id === toolCallId && calls[j].result === undefined) {
              calls[j] = { ...calls[j], result, is_error: isError };
              msgs[i] = { ...msg, toolCalls: calls };
              return { messages: msgs };
            }
          }
        }
      }
      return { messages: msgs };
    }),

  addToolApprovalRequest: (toolCallId, tool, args) =>
    set((state) => {
      const msgs = [...state.messages];
      // ToolStarted fires before ToolApprovalRequired, so an existing
      // chip (same tool_call_id, no status, no result) may already be present.
      // Upgrade it in-place instead of adding a duplicate.
      for (let i = msgs.length - 1; i >= 0; i--) {
        const msg = msgs[i];
        if (msg.role === "tool" && msg.toolCalls) {
          const calls = [...msg.toolCalls];
          for (let j = calls.length - 1; j >= 0; j--) {
            if (calls[j].tool_call_id === toolCallId && !calls[j].status && calls[j].result === undefined) {
              calls[j] = { ...calls[j], status: "pending" };
              msgs[i] = { ...msg, toolCalls: calls };
              return { messages: msgs };
            }
          }
        }
        if (msg.role !== "tool") break;
      }
      // No existing chip found — create new
      const newCall: AgentToolCall = { tool, args, tool_call_id: toolCallId, status: "pending" };
      const last = msgs[msgs.length - 1];
      if (last && last.role === "tool" && last.toolCalls) {
        msgs[msgs.length - 1] = {
          ...last,
          toolCalls: [...last.toolCalls, newCall],
        };
      } else {
        msgs.push({
          id: nextId(),
          role: "tool",
          content: "",
          timestamp: Date.now(),
          toolCalls: [newCall],
        });
      }
      return { messages: msgs };
    }),

  resolveToolApproval: (toolCallId, approved) =>
    set((state) => {
      const msgs = [...state.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        const msg = msgs[i];
        if (msg.role === "tool" && msg.toolCalls) {
          const calls = [...msg.toolCalls];
          for (let j = calls.length - 1; j >= 0; j--) {
            if (calls[j].tool_call_id === toolCallId) {
              calls[j] = { ...calls[j], status: approved ? "approved" : "denied" };
              msgs[i] = { ...msg, toolCalls: calls };
              return { messages: msgs };
            }
          }
        }
      }
      return { messages: msgs };
    }),

  appendThinking: (content) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "thinking") {
        // Append to existing thinking message
        msgs[msgs.length - 1] = { ...last, content: last.content + content };
      } else {
        msgs.push({
          id: nextId(),
          role: "thinking",
          content,
          timestamp: Date.now(),
        });
      }
      return { messages: msgs };
    }),

  addError: (message) =>
    set((state) => ({
      status: "error" as AgentStatus,
      messages: [
        ...state.messages,
        {
          id: nextId(),
          role: "assistant",
          content: `Error: ${message}`,
          timestamp: Date.now(),
          done: true,
        },
      ],
    })),

  setActiveQuestion: (q) => set({ activeQuestion: q }),
  setSessionId: (id) => {
    sessionStorage.setItem("agent_session_id", id);
    set({ sessionId: id });
  },
  setModels: (models) => set({ models }),
  setSelectedModel: (model) => set({ selectedModel: model }),
  setModelsLoading: (loading) => set({ modelsLoading: loading }),
  setSkills: (skills) => set({ skills }),
  setSelectedSkillIds: (ids) => set({ selectedSkillIds: ids }),
  toggleSkill: (id) =>
    set((state) => {
      const selected = state.selectedSkillIds.includes(id)
        ? state.selectedSkillIds.filter((s) => s !== id)
        : [...state.selectedSkillIds, id];
      return { selectedSkillIds: selected };
    }),
  setSkillsLoading: (loading) => set({ skillsLoading: loading }),

  hydrateSession: (state: AgentSessionState) =>
    set({
      sessionId: state.session_id,
      status: (state.status as AgentStatus) || "done",
      messages: state.messages,
      plan: state.plan,
      selectedModel: state.model || null,
    }),

  clearSession: () => {
    sessionStorage.removeItem("agent_session_id");
    set({
      sessionId: null,
      status: "idle",
      _lastActiveAt: null,
      messages: [],
      plan: [],
      activeQuestion: null,
    });
  },
}));
