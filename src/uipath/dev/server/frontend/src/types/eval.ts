export interface EvaluatorInfo {
  id: string;
  name: string;
  type: "deterministic" | "llm" | "tool";
  category: string;
  description: string;
  config_schema: Record<string, unknown>;
}

export interface LocalEvaluator {
  id: string;
  name: string;
  description: string;
  evaluator_type_id: string;
  category: string;
  type: string;
  target_output_key: string;
  config: Record<string, unknown>;
}

export interface EvalSetSummary {
  id: string;
  name: string;
  eval_count: number;
  evaluator_ids: string[];
}

export interface EvalItem {
  name: string;
  inputs: Record<string, unknown>;
  expected_behavior: string;
  expected_output: unknown;
  simulation_instructions: string;
  evaluation_criterias: Record<string, Record<string, unknown>>;
  evaluator_ids: string[];
}

export interface EvalSetDetail extends EvalSetSummary {
  items: EvalItem[];
}

export interface EvalItemResult {
  name: string;
  inputs: Record<string, unknown>;
  expected_output: unknown;
  scores: Record<string, number>;
  overall_score: number;
  output: unknown;
  justifications: Record<string, string>;
  duration_ms: number | null;
  status: "pending" | "running" | "completed" | "failed";
  error?: string | null;
  traces: import("./run").TraceSpan[];
}

export interface EvalRunSummary {
  id: string;
  eval_set_id: string;
  eval_set_name: string;
  status: "pending" | "running" | "completed" | "failed";
  progress_completed: number;
  progress_total: number;
  overall_score: number | null;
  evaluator_scores: Record<string, number>;
  start_time: string | null;
  end_time: string | null;
}

export interface EvalRunDetail extends EvalRunSummary {
  results: EvalItemResult[];
}
