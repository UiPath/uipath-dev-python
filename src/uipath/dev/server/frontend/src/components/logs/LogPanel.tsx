import { useEffect, useRef } from "react";
import type { LogEntry } from "../../types/run";

const LEVEL_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  DEBUG: { color: "var(--text-muted)", bg: "color-mix(in srgb, var(--text-muted) 15%, var(--bg-secondary))", border: "var(--text-muted)" },
  INFO: { color: "var(--info)", bg: "color-mix(in srgb, var(--info) 15%, var(--bg-secondary))", border: "var(--info)" },
  WARN: { color: "var(--warning)", bg: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))", border: "var(--warning)" },
  WARNING: { color: "var(--warning)", bg: "color-mix(in srgb, var(--warning) 15%, var(--bg-secondary))", border: "var(--warning)" },
  ERROR: { color: "var(--error)", bg: "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))", border: "var(--error)" },
  CRITICAL: { color: "var(--error)", bg: "color-mix(in srgb, var(--error) 15%, var(--bg-secondary))", border: "var(--error)" },
};

const DEFAULT_STYLE = { color: "var(--text-muted)", bg: "transparent", border: "var(--text-muted)" };

interface Props {
  logs: LogEntry[];
}

export default function LogPanel({ logs }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  if (logs.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-[var(--text-muted)] text-sm">No logs yet</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto font-mono text-xs">
      {logs.map((log, i) => {
        const time = new Date(log.timestamp).toLocaleTimeString(undefined, {
          hour12: false,
        });
        const levelKey = log.level.toUpperCase();
        const levelShort = levelKey.slice(0, 4);
        const style = LEVEL_STYLES[levelKey] ?? DEFAULT_STYLE;
        const isEven = i % 2 === 0;

        return (
          <div
            key={i}
            className="flex gap-3 px-3 py-1.5"
            style={{
              background: isEven ? "var(--bg-primary)" : "var(--bg-secondary)",
            }}
          >
            <span className="text-[var(--text-muted)] shrink-0">{time}</span>
            <span
              className="shrink-0 self-start px-1.5 py-0.5 rounded text-[10px] font-semibold leading-none inline-flex items-center"
              style={{ color: style.color, background: style.bg }}
            >
              {levelShort}
            </span>
            <span className="text-[var(--text-primary)] whitespace-pre-wrap break-all">
              {log.message}
            </span>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
