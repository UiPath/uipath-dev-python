import type { EvaluatorInfo, LocalEvaluator, LlmModel, EvalSetSummary, EvalSetDetail, EvalItem, EvalRunSummary, EvalRunDetail } from "../types/eval";

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

export async function listEvaluators(): Promise<EvaluatorInfo[]> {
  return fetchJson(`${BASE}/evaluators`);
}

export async function listLlmModels(): Promise<LlmModel[]> {
  return fetchJson(`${BASE}/llm-models`);
}

export async function listEvalSets(): Promise<EvalSetSummary[]> {
  return fetchJson(`${BASE}/eval-sets`);
}

export async function createEvalSet(body: {
  name: string;
  evaluator_refs: string[];
}): Promise<EvalSetSummary> {
  return fetchJson(`${BASE}/eval-sets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function addEvalItem(
  evalSetId: string,
  item: {
    name: string;
    inputs: Record<string, unknown>;
    expected_output: unknown;
    evaluation_criterias?: Record<string, Record<string, unknown>>;
  },
): Promise<EvalItem> {
  return fetchJson(`${BASE}/eval-sets/${encodeURIComponent(evalSetId)}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(item),
  });
}

export async function updateEvalItem(
  evalSetId: string,
  itemName: string,
  body: {
    name?: string;
    inputs?: Record<string, unknown>;
    expected_output?: unknown;
    expected_behavior?: string;
    simulation_instructions?: string;
  },
): Promise<EvalItem> {
  return fetchJson(
    `${BASE}/eval-sets/${encodeURIComponent(evalSetId)}/items/${encodeURIComponent(itemName)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export async function updateEvalItemEvaluators(
  evalSetId: string,
  itemName: string,
  evaluationCriterias: Record<string, unknown>,
): Promise<EvalItem> {
  return fetchJson(
    `${BASE}/eval-sets/${encodeURIComponent(evalSetId)}/items/${encodeURIComponent(itemName)}/evaluators`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ evaluation_criterias: evaluationCriterias }),
    },
  );
}

export async function deleteEvalItem(
  evalSetId: string,
  itemName: string,
): Promise<void> {
  await fetchJson(`${BASE}/eval-sets/${encodeURIComponent(evalSetId)}/items/${encodeURIComponent(itemName)}`, {
    method: "DELETE",
  });
}

export async function getEvalSet(id: string): Promise<EvalSetDetail> {
  return fetchJson(`${BASE}/eval-sets/${encodeURIComponent(id)}`);
}

export async function startEvalRun(evalSetId: string): Promise<EvalRunSummary> {
  return fetchJson(`${BASE}/eval-sets/${encodeURIComponent(evalSetId)}/runs`, {
    method: "POST",
  });
}

export async function listEvalRuns(): Promise<EvalRunSummary[]> {
  return fetchJson(`${BASE}/eval-runs`);
}

export async function getEvalRun(id: string): Promise<EvalRunDetail> {
  return fetchJson(`${BASE}/eval-runs/${encodeURIComponent(id)}`);
}

export async function listLocalEvaluators(): Promise<LocalEvaluator[]> {
  return fetchJson(`${BASE}/local-evaluators`);
}

export async function createLocalEvaluator(body: {
  name: string;
  description: string;
  evaluator_type_id: string;
  config: Record<string, unknown>;
}): Promise<LocalEvaluator> {
  return fetchJson(`${BASE}/local-evaluators`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateEvalSetEvaluators(
  evalSetId: string,
  evaluatorRefs: string[],
): Promise<EvalSetDetail> {
  return fetchJson(`${BASE}/eval-sets/${encodeURIComponent(evalSetId)}/evaluators`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ evaluator_refs: evaluatorRefs }),
  });
}

export async function scaffoldCustomEvaluator(body: {
  name: string;
  description?: string;
}): Promise<{ file_path: string; filename: string; class_name: string; evaluator_id: string }> {
  return fetchJson(`${BASE}/custom-evaluators/scaffold`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function registerCustomEvaluator(filename: string): Promise<{ evaluator_id: string; spec_path: string }> {
  return fetchJson(`${BASE}/custom-evaluators/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
}

export async function updateLocalEvaluator(
  id: string,
  body: {
    description?: string;
    evaluator_type_id?: string;
    config?: Record<string, unknown>;
  },
): Promise<LocalEvaluator> {
  return fetchJson(`${BASE}/local-evaluators/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
