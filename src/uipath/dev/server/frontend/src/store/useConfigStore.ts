import { create } from "zustand";

interface ConfigStore {
  projectName: string | null;
  projectVersion: string | null;
  projectAuthors: string | null;
  init: () => Promise<void>;
}

export const useConfigStore = create<ConfigStore>((set) => ({
  projectName: null,
  projectVersion: null,
  projectAuthors: null,

  init: async () => {
    try {
      const res = await fetch("/api/config");
      if (res.ok) {
        const data = await res.json();
        set({
          projectName: data.project_name ?? null,
          projectVersion: data.project_version ?? null,
          projectAuthors: data.project_authors ?? null,
        });
      }
    } catch {
      // ignore
    }
  },
}));
