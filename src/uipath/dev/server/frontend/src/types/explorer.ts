export interface FileEntry {
  name: string;
  type: "file" | "directory";
  path: string;
}

export interface FileContent {
  content: string | null;
  binary: boolean;
  size: number;
  language: string | null;
}
