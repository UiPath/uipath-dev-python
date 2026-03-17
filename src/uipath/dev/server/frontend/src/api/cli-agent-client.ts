export interface CliAgentInfo {
  id: string;
  name: string;
  installed: boolean;
}

export async function listCliAgents(): Promise<CliAgentInfo[]> {
  const res = await fetch("/api/cli-agent/available");
  if (!res.ok) return [];
  return res.json();
}
