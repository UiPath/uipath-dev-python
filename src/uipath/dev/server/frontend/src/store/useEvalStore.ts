import { create } from "zustand";
import type { EvaluatorInfo, LocalEvaluator, EvalSetSummary, EvalRunSummary, EvalItemResult } from "../types/eval";

interface EvalStore {
  evaluators: EvaluatorInfo[];
  localEvaluators: LocalEvaluator[];
  evalSets: Record<string, EvalSetSummary>;
  evalRuns: Record<string, EvalRunSummary>;

  setEvaluators: (evaluators: EvaluatorInfo[]) => void;
  setLocalEvaluators: (evaluators: LocalEvaluator[]) => void;
  addLocalEvaluator: (evaluator: LocalEvaluator) => void;
  upsertLocalEvaluator: (evaluator: LocalEvaluator) => void;
  setEvalSets: (sets: EvalSetSummary[]) => void;
  addEvalSet: (evalSet: EvalSetSummary) => void;
  updateEvalSetEvaluators: (setId: string, evaluatorIds: string[]) => void;
  incrementEvalSetCount: (setId: string, by?: number) => void;
  setEvalRuns: (runs: EvalRunSummary[]) => void;
  upsertEvalRun: (run: EvalRunSummary) => void;
  updateEvalRunProgress: (runId: string, completed: number, total: number, itemResult?: EvalItemResult) => void;
  completeEvalRun: (runId: string, overallScore: number, evaluatorScores: Record<string, number>) => void;
}

export const useEvalStore = create<EvalStore>((set) => ({
  evaluators: [],
  localEvaluators: [],
  evalSets: {},
  evalRuns: {},

  setEvaluators: (evaluators) => set({ evaluators }),

  setLocalEvaluators: (localEvaluators) => set({ localEvaluators }),

  addLocalEvaluator: (evaluator) =>
    set((state) => ({ localEvaluators: [...state.localEvaluators, evaluator] })),

  upsertLocalEvaluator: (evaluator) =>
    set((state) => ({
      localEvaluators: state.localEvaluators.some((e) => e.id === evaluator.id)
        ? state.localEvaluators.map((e) => (e.id === evaluator.id ? evaluator : e))
        : [...state.localEvaluators, evaluator],
    })),

  setEvalSets: (sets) =>
    set({ evalSets: Object.fromEntries(sets.map((s) => [s.id, s])) }),

  addEvalSet: (evalSet) =>
    set((state) => ({ evalSets: { ...state.evalSets, [evalSet.id]: evalSet } })),

  updateEvalSetEvaluators: (setId, evaluatorIds) =>
    set((state) => {
      const existing = state.evalSets[setId];
      if (!existing) return state;
      return {
        evalSets: {
          ...state.evalSets,
          [setId]: { ...existing, evaluator_ids: evaluatorIds },
        },
      };
    }),

  incrementEvalSetCount: (setId, by = 1) =>
    set((state) => {
      const existing = state.evalSets[setId];
      if (!existing) return state;
      return {
        evalSets: {
          ...state.evalSets,
          [setId]: { ...existing, eval_count: existing.eval_count + by },
        },
      };
    }),

  setEvalRuns: (runs) =>
    set({ evalRuns: Object.fromEntries(runs.map((r) => [r.id, r])) }),

  upsertEvalRun: (run) =>
    set((state) => ({ evalRuns: { ...state.evalRuns, [run.id]: run } })),

  updateEvalRunProgress: (runId, completed, total) =>
    set((state) => {
      const existing = state.evalRuns[runId];
      if (!existing) return state;
      return {
        evalRuns: {
          ...state.evalRuns,
          [runId]: { ...existing, progress_completed: completed, progress_total: total, status: "running" },
        },
      };
    }),

  completeEvalRun: (runId, overallScore, evaluatorScores) =>
    set((state) => {
      const existing = state.evalRuns[runId];
      if (!existing) return state;
      return {
        evalRuns: {
          ...state.evalRuns,
          [runId]: {
            ...existing,
            status: "completed",
            overall_score: overallScore,
            evaluator_scores: evaluatorScores,
            end_time: new Date().toISOString(),
          },
        },
      };
    }),
}));
