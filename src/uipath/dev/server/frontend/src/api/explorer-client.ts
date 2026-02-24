import type { FileEntry, FileContent } from "../types/explorer";

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

export async function listDirectory(path: string): Promise<FileEntry[]> {
  return fetchJson(`${BASE}/files/tree?path=${encodeURIComponent(path)}`);
}

export async function readFile(path: string): Promise<FileContent> {
  return fetchJson(`${BASE}/files/content?path=${encodeURIComponent(path)}`);
}

export async function saveFile(path: string, content: string): Promise<void> {
  await fetchJson(`${BASE}/files/content?path=${encodeURIComponent(path)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}
