import type { RunSummary, RunDetail } from "../types/run";
import type { GraphData } from "../types/graph";

const BASE = "/api";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    // Try to get detailed error from response body
    let errorDetail;
    try {
      const body = await res.json();
      errorDetail = body.detail || res.statusText;
    } catch {
      errorDetail = res.statusText;
    }
    const error = new Error(`HTTP ${res.status}`);
    (error as any).detail = errorDetail;
    (error as any).status = res.status;
    throw error;
  }
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
  breakpoints: string[] = [],
): Promise<RunSummary> {
  return fetchJson(`${BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entrypoint, input_data: inputData, mode, breakpoints }),
  });
}

export async function listRuns(): Promise<RunSummary[]> {
  return fetchJson(`${BASE}/runs`);
}

export async function getRun(runId: string): Promise<RunDetail> {
  return fetchJson(`${BASE}/runs/${runId}`);
}

export async function reloadFactory(): Promise<{ status: string }> {
  return fetchJson(`${BASE}/reload`, { method: "POST" });
}
