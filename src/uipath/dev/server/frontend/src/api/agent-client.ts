import type { AgentModel, AgentSkill } from "../types/agent";

const BASE = "/api";

export async function listAgentModels(): Promise<AgentModel[]> {
  const res = await fetch(`${BASE}/agent/models`);
  if (!res.ok) {
    if (res.status === 401) return [];
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
}

export async function listAgentSkills(): Promise<AgentSkill[]> {
  const res = await fetch(`${BASE}/agent/skills`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
}
