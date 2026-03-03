import { useSyncExternalStore, useCallback } from "react";

export type Section = "debug" | "evals" | "evaluators" | "explorer";
type Tab = "traces" | "output";

interface Route {
  section: Section;
  view: "new" | "setup" | "details";
  runId: string | null;
  tab: Tab;
  setupEntrypoint: string | null;
  setupMode: "run" | "chat" | null;
  evalCreating: boolean;
  evalSetId: string | null;
  evalRunId: string | null;
  evalRunItemName: string | null;
  evaluatorId: string | null;
  evaluatorCreateType: string | null;
  evaluatorFilter: string | null;
  explorerFile: string | null;
  stateDbTable: string | null;
}

function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, "");

  const base: Route = {
    section: "debug",
    view: "new",
    runId: null,
    tab: "traces",
    setupEntrypoint: null,
    setupMode: null,
    evalCreating: false,
    evalSetId: null,
    evalRunId: null,
    evalRunItemName: null,
    evaluatorId: null,
    evaluatorCreateType: null,
    evaluatorFilter: null,
    explorerFile: null,
    stateDbTable: null,
  };

  if (!path || path === "new" || path === "debug" || path === "debug/new") {
    return base;
  }

  // --- Debug section ---

  // #/debug/setup/:entrypoint/:mode
  const debugSetup = path.match(/^(?:debug\/)?setup\/([^/]+)\/(run|chat)$/);
  if (debugSetup) {
    return {
      ...base,
      view: "setup",
      setupEntrypoint: decodeURIComponent(debugSetup[1]),
      setupMode: debugSetup[2] as "run" | "chat",
    };
  }

  // #/debug/runs/:runId or #/debug/runs/:runId/traces|output
  const debugRun = path.match(/^(?:debug\/)?runs\/([^/]+)(?:\/(traces|output))?$/);
  if (debugRun) {
    return {
      ...base,
      view: "details",
      runId: debugRun[1],
      tab: (debugRun[2] as Tab) ?? "traces",
    };
  }

  // --- Evals section ---

  // #/evals/new
  if (path === "evals/new") {
    return { ...base, section: "evals", evalCreating: true };
  }

  // #/evals/runs/:id or #/evals/runs/:id/:itemName
  const evalRun = path.match(/^evals\/runs\/([^/]+?)(?:\/([^/]+))?$/);
  if (evalRun) {
    return {
      ...base,
      section: "evals",
      evalRunId: evalRun[1],
      evalRunItemName: evalRun[2] ? decodeURIComponent(evalRun[2]) : null,
    };
  }

  // #/evals/sets/:id
  const evalSet = path.match(/^evals\/sets\/([^/]+)$/);
  if (evalSet) {
    return { ...base, section: "evals", evalSetId: evalSet[1] };
  }

  // #/evals
  if (path === "evals") {
    return { ...base, section: "evals" };
  }

  // --- Evaluators section ---

  // #/evaluators/new/:type or #/evaluators/new
  const evaluatorNew = path.match(/^evaluators\/new(?:\/(deterministic|llm|tool))?$/);
  if (evaluatorNew) {
    return { ...base, section: "evaluators", evaluatorCreateType: evaluatorNew[1] ?? "any" };
  }

  // #/evaluators/category/:type
  const evaluatorCategory = path.match(/^evaluators\/category\/(deterministic|llm|tool)$/);
  if (evaluatorCategory) {
    return { ...base, section: "evaluators", evaluatorFilter: evaluatorCategory[1] };
  }

  // #/evaluators/:id
  const evaluatorDetail = path.match(/^evaluators\/([^/]+)$/);
  if (evaluatorDetail) {
    return { ...base, section: "evaluators", evaluatorId: evaluatorDetail[1] };
  }

  // #/evaluators
  if (path === "evaluators") {
    return { ...base, section: "evaluators" };
  }

  // --- Explorer section ---

  // #/explorer/statedb/:tableName
  const stateDbTable = path.match(/^explorer\/statedb\/(.+)$/);
  if (stateDbTable) {
    return { ...base, section: "explorer", stateDbTable: decodeURIComponent(stateDbTable[1]) };
  }

  // #/explorer/statedb (no table selected)
  if (path === "explorer/statedb") {
    return { ...base, section: "explorer", stateDbTable: "" };
  }

  // #/explorer/file/:path
  const explorerFile = path.match(/^explorer\/file\/(.+)$/);
  if (explorerFile) {
    return { ...base, section: "explorer", explorerFile: decodeURIComponent(explorerFile[1]) };
  }

  // #/explorer
  if (path === "explorer") {
    return { ...base, section: "explorer" };
  }

  return base;
}

function getSnapshot(): string {
  return window.location.hash;
}

function subscribe(cb: () => void): () => void {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}

export function useHashRoute() {
  const hash = useSyncExternalStore(subscribe, getSnapshot);
  const route = parseHash(hash);

  const navigate = useCallback((newHash: string) => {
    window.location.hash = newHash;
  }, []);

  return { ...route, navigate };
}
