import { create } from "zustand";
import type { CliAgentInfo } from "../api/cli-agent-client";

export type CliAgentStatus = "idle" | "running" | "exited";

export type CliAgentEvent =
  | { type: "session"; timestamp: number; agentName: string; action: "started" | "stopped" | "exited"; exitCode?: number }
  | { type: "files_changed"; timestamp: number; files: string[] }
  | { type: "mcp_tool_call"; timestamp: number; tool: string; args: Record<string, unknown> }
  | { type: "run_lifecycle"; timestamp: number; runId: string; entrypoint: string; status: string };

interface CliAgentStore {
  availableAgents: CliAgentInfo[];
  selectedAgentId: string | null;
  sessionId: string | null;
  status: CliAgentStatus;
  exitCode: number | null;
  events: CliAgentEvent[];

  setAvailableAgents: (agents: CliAgentInfo[]) => void;
  setSelectedAgentId: (id: string) => void;
  setSessionId: (id: string | null) => void;
  setStatus: (status: CliAgentStatus) => void;
  setExitCode: (code: number | null) => void;
  addEvent: (event: CliAgentEvent) => void;
}

export const useCliAgentStore = create<CliAgentStore>((set) => ({
  availableAgents: [],
  selectedAgentId: null,
  sessionId: null,
  status: "idle",
  exitCode: null,
  events: [],

  setAvailableAgents: (agents) => {
    set((s) => {
      const update: Partial<CliAgentStore> = { availableAgents: agents };
      if (!s.selectedAgentId) {
        const first = agents.find((a) => a.installed);
        if (first) update.selectedAgentId = first.id;
      }
      return update;
    });
  },
  setSelectedAgentId: (id) => set({ selectedAgentId: id }),
  setSessionId: (id) => set({ sessionId: id }),
  setStatus: (status) => set({ status }),
  setExitCode: (code) => set({ exitCode: code }),
  addEvent: (event) => set((s) => ({ events: [...s.events, event] })),
}));
