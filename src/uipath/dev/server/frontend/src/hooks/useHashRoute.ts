import { useSyncExternalStore, useCallback } from "react";

type Tab = "traces" | "output";

interface Route {
  view: "new" | "details";
  runId: string | null;
  tab: Tab;
}

function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, "");

  if (!path || path === "new") {
    return { view: "new", runId: null, tab: "traces" };
  }

  // runs/:runId or runs/:runId/traces or runs/:runId/output
  const match = path.match(/^runs\/([^/]+)(?:\/(traces|output))?$/);
  if (match) {
    return {
      view: "details",
      runId: match[1],
      tab: (match[2] as Tab) ?? "traces",
    };
  }

  return { view: "new", runId: null, tab: "traces" };
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
