import { useSyncExternalStore, useCallback } from "react";

type Tab = "traces" | "output";

interface Route {
  view: "new" | "setup" | "details";
  runId: string | null;
  tab: Tab;
  setupEntrypoint: string | null;
  setupMode: "run" | "chat" | null;
}

function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, "");

  if (!path || path === "new") {
    return { view: "new", runId: null, tab: "traces", setupEntrypoint: null, setupMode: null };
  }

  // setup/:entrypoint/:mode
  const setupMatch = path.match(/^setup\/([^/]+)\/(run|chat)$/);
  if (setupMatch) {
    return {
      view: "setup",
      runId: null,
      tab: "traces",
      setupEntrypoint: decodeURIComponent(setupMatch[1]),
      setupMode: setupMatch[2] as "run" | "chat",
    };
  }

  // runs/:runId or runs/:runId/traces or runs/:runId/output
  const match = path.match(/^runs\/([^/]+)(?:\/(traces|output))?$/);
  if (match) {
    return {
      view: "details",
      runId: match[1],
      tab: (match[2] as Tab) ?? "traces",
      setupEntrypoint: null,
      setupMode: null,
    };
  }

  return { view: "new", runId: null, tab: "traces", setupEntrypoint: null, setupMode: null };
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
