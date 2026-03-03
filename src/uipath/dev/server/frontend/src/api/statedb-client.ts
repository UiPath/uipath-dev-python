import type {
  StateDbTable,
  StateDbTableData,
  StateDbQueryResult,
} from "../types/statedb";

const BASE = "/api";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
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

export async function getStateDbStatus(): Promise<{ exists: boolean }> {
  return fetchJson(`${BASE}/statedb/status`);
}

export async function getStateDbTables(): Promise<StateDbTable[]> {
  return fetchJson(`${BASE}/statedb/tables`);
}

export async function getStateDbTableData(
  table: string,
  limit = 100,
  offset = 0,
): Promise<StateDbTableData> {
  return fetchJson(
    `${BASE}/statedb/tables/${encodeURIComponent(table)}?limit=${limit}&offset=${offset}`,
  );
}

export async function executeStateDbQuery(
  sql: string,
  limit?: number,
): Promise<StateDbQueryResult> {
  return fetchJson(`${BASE}/statedb/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql, limit }),
  });
}
