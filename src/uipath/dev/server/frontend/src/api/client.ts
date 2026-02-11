import type { RunSummary, RunDetail } from "../types/run";
import type { GraphData } from "../types/graph";

const BASE = "/api";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function listEntrypoints(): Promise<{ name: string }[]> {
  return fetchJson(`${BASE}/entrypoints`);
}

export async function getEntrypointSchema(
  entrypoint: string,
): Promise<{ entrypoint: string; input: Record<string, unknown>; output: Record<string, unknown> }> {
  return fetchJson(`${BASE}/entrypoints/${encodeURIComponent(entrypoint)}/schema`);
}

export async function getEntrypointMockInput(
  entrypoint: string,
): Promise<{ entrypoint: string; mock_input: Record<string, unknown> }> {
  return fetchJson(`${BASE}/entrypoints/${encodeURIComponent(entrypoint)}/mock-input`);
}

export async function getEntrypointGraph(
  entrypoint: string,
): Promise<GraphData> {
  return fetchJson(`${BASE}/entrypoints/${encodeURIComponent(entrypoint)}/graph`);
}

export async function createRun(
  entrypoint: string,
  inputData: Record<string, unknown>,
  mode: string = "run",
): Promise<RunSummary> {
  return fetchJson(`${BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entrypoint, input_data: inputData, mode }),
  });
}

export async function listRuns(): Promise<RunSummary[]> {
  return fetchJson(`${BASE}/runs`);
}

export async function getRun(runId: string): Promise<RunDetail> {
  return fetchJson(`${BASE}/runs/${runId}`);
}
