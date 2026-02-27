import { create } from "zustand";
import type { FileEntry, FileContent } from "../types/explorer";

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
}));
