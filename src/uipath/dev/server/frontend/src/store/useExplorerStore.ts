import { create } from "zustand";
import type { FileEntry, FileContent } from "../types/explorer";

interface DiffView {
  path: string;
  original: string;
  modified: string;
  language: string | null;
}

interface ExplorerStore {
  children: Record<string, FileEntry[]>;
  expanded: Record<string, boolean>;
  selectedFile: string | null;
  openTabs: string[];
  fileCache: Record<string, FileContent>;
  dirty: Record<string, boolean>;
  buffers: Record<string, string>;
  loadingDirs: Record<string, boolean>;
  loadingFile: boolean;
  agentChangedFiles: Record<string, number>;
  diffView: DiffView | null;

  setChildren: (path: string, entries: FileEntry[]) => void;
  toggleExpanded: (path: string) => void;
  setSelectedFile: (path: string | null) => void;
  openTab: (path: string) => void;
  closeTab: (path: string) => void;
  setFileContent: (path: string, content: FileContent) => void;
  updateBuffer: (path: string, content: string) => void;
  markClean: (path: string) => void;
  setLoadingDir: (path: string, loading: boolean) => void;
  setLoadingFile: (loading: boolean) => void;
  markAgentChanged: (path: string) => void;
  clearAgentChanged: (path: string) => void;
  setDiffView: (diff: DiffView | null) => void;
  expandPath: (filePath: string) => void;
}

export const useExplorerStore = create<ExplorerStore>((set) => ({
  children: {},
  expanded: {},
  selectedFile: null,
  openTabs: [],
  fileCache: {},
  dirty: {},
  buffers: {},
  loadingDirs: {},
  loadingFile: false,
  agentChangedFiles: {},
  diffView: null,

  setChildren: (path, entries) =>
    set((state) => ({ children: { ...state.children, [path]: entries } })),

  toggleExpanded: (path) =>
    set((state) => ({
      expanded: { ...state.expanded, [path]: !state.expanded[path] },
    })),

  setSelectedFile: (path) => set({ selectedFile: path }),

  openTab: (path) =>
    set((state) => ({
      selectedFile: path,
      openTabs: state.openTabs.includes(path)
        ? state.openTabs
        : [...state.openTabs, path],
    })),

  closeTab: (path) =>
    set((state) => {
      const tabs = state.openTabs.filter((t) => t !== path);
      let selected = state.selectedFile;
      if (selected === path) {
        const idx = state.openTabs.indexOf(path);
        selected = tabs[Math.min(idx, tabs.length - 1)] ?? null;
      }
      const { [path]: _d, ...dirty } = state.dirty;
      const { [path]: _b, ...buffers } = state.buffers;
      return { openTabs: tabs, selectedFile: selected, dirty, buffers };
    }),

  setFileContent: (path, content) =>
    set((state) => ({ fileCache: { ...state.fileCache, [path]: content } })),

  updateBuffer: (path, content) =>
    set((state) => ({
      buffers: { ...state.buffers, [path]: content },
      dirty: { ...state.dirty, [path]: true },
    })),

  markClean: (path) =>
    set((state) => {
      const { [path]: _, ...dirty } = state.dirty;
      const { [path]: __, ...buffers } = state.buffers;
      return { dirty, buffers };
    }),

  setLoadingDir: (path, loading) =>
    set((state) => ({ loadingDirs: { ...state.loadingDirs, [path]: loading } })),

  setLoadingFile: (loading) => set({ loadingFile: loading }),

  markAgentChanged: (path) =>
    set((state) => ({ agentChangedFiles: { ...state.agentChangedFiles, [path]: Date.now() } })),

  clearAgentChanged: (path) =>
    set((state) => {
      const { [path]: _, ...rest } = state.agentChangedFiles;
      return { agentChangedFiles: rest };
    }),

  setDiffView: (diff) => set({ diffView: diff }),

  expandPath: (filePath) =>
    set((state) => {
      const parts = filePath.split("/");
      const expanded = { ...state.expanded };
      for (let i = 1; i < parts.length; i++) {
        expanded[parts.slice(0, i).join("/")] = true;
      }
      return { expanded };
    }),
}));
