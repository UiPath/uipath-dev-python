// Shared diff view for edit_file tool calls

export function computeUnifiedDiff(oldStr: string, newStr: string): { type: "ctx" | "del" | "add"; text: string }[] {
  const oldLines = oldStr.split("\n");
  const newLines = newStr.split("\n");

  const m = oldLines.length;
  const n = newLines.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = oldLines[i - 1] === newLines[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  const result: { type: "ctx" | "del" | "add"; text: string }[] = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      result.push({ type: "ctx", text: oldLines[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ type: "add", text: newLines[j - 1] });
      j--;
    } else {
      result.push({ type: "del", text: oldLines[i - 1] });
      i--;
    }
  }
  result.reverse();
  return result;
}

const DIFF_STYLES: Record<string, { bg: string; color: string; prefix: string }> = {
  del: { bg: "color-mix(in srgb, #ef4444 12%, transparent)", color: "#f87171", prefix: "-" },
  add: { bg: "color-mix(in srgb, #22c55e 12%, transparent)", color: "#4ade80", prefix: "+" },
  ctx: { bg: "transparent", color: "var(--text-muted)", prefix: " " },
};

export function DiffView({ path, oldStr, newStr }: { path?: string; oldStr: string; newStr: string }) {
  const lines = computeUnifiedDiff(oldStr, newStr);
  const delCount = lines.filter((l) => l.type === "del").length;
  const addCount = lines.filter((l) => l.type === "add").length;

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Diff</span>
        {path && <span className="text-[11px] font-mono truncate" style={{ color: "var(--text-secondary)" }}>{path}</span>}
        <div className="flex-1" />
        <span className="text-[11px] font-mono font-medium" style={{ color: "#4ade80" }}>+{addCount}</span>
        <span className="text-[11px] font-mono font-medium" style={{ color: "#f87171" }}>-{delCount}</span>
      </div>
      <div className="rounded overflow-auto max-h-64" style={{ background: "var(--bg-primary)" }}>
        {lines.map((line, i) => {
          const s = DIFF_STYLES[line.type];
          return (
            <div key={i} className="flex" style={{ background: s.bg }}>
              <span className="shrink-0 w-5 text-right pr-1 select-none text-[11px] font-mono leading-relaxed"
                style={{ color: s.color, opacity: 0.6 }}>
                {s.prefix}
              </span>
              <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words font-mono m-0 pl-1 flex-1"
                style={{ color: s.color }}>
                {line.text}
              </pre>
            </div>
          );
        })}
      </div>
    </div>
  );
}
