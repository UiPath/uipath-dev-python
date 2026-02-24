import type { ReactNode } from "react";

interface Props {
  title: string;
  children: ReactNode;
}

export default function SidePanel({ title, children }: Props) {
  return (
    <aside className="w-[200px] bg-[var(--sidebar-bg)] border-r border-[var(--border)] flex flex-col shrink-0">
      {/* Header */}
      <div className="px-3 h-10 border-b border-[var(--border)] flex items-center">
        <span
          className="text-[10px] uppercase tracking-widest font-semibold"
          style={{ color: "var(--text-muted)" }}
        >
          {title}
        </span>
      </div>
      {children}
    </aside>
  );
}
