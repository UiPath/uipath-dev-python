import { useEffect, useRef, useState } from "react";
import JsonHighlight from "../shared/JsonHighlight";

interface StateEvent {
  node_name: string;
  timestamp: number;
  payload?: Record<string, unknown>;
}

interface Props {
  events: StateEvent[];
  runStatus: string;
}

export default function RunEventsPanel({ events, runStatus }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  useEffect(() => {
    if (stickToBottom.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  });

  if (events.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center h-full">
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          {runStatus === "running" ? "Waiting for events..." : "No events yet"}
        </p>
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="h-full overflow-y-auto font-mono text-xs leading-normal"
    >
      {events.map((event, i) => {
        const time = new Date(event.timestamp).toLocaleTimeString(undefined, {
          hour12: false,
        });
        const hasPayload = event.payload && Object.keys(event.payload).length > 0;
        const isExpanded = expandedIdx === i;

        return (
          <div key={i}>
            <div
              onClick={() => {
                if (hasPayload) setExpandedIdx(isExpanded ? null : i);
              }}
              className="flex items-center gap-2 px-3 py-1.5"
              style={{
                background: i % 2 === 0 ? "var(--bg-primary)" : "var(--bg-secondary)",
                cursor: hasPayload ? "pointer" : "default",
              }}
            >
              <span className="shrink-0" style={{ color: "var(--text-muted)" }}>
                {time}
              </span>
              <span className="shrink-0" style={{ color: "var(--accent)" }}>
                &#9656;
              </span>
              <span className="flex-1 truncate" style={{ color: "var(--text-primary)" }}>
                {event.node_name}
              </span>
              {hasPayload && (
                <span
                  className="shrink-0 text-[9px] transition-transform"
                  style={{
                    color: "var(--text-muted)",
                    transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                  }}
                >
                  &#9656;
                </span>
              )}
            </div>
            {isExpanded && hasPayload && (
              <div
                className="px-3 py-2 border-t border-b"
                style={{
                  borderColor: "var(--border)",
                  background: "color-mix(in srgb, var(--bg-secondary) 80%, var(--bg-primary))",
                }}
              >
                <JsonHighlight
                  json={JSON.stringify(event.payload, null, 2)}
                  className="text-[11px] font-mono whitespace-pre-wrap break-words"
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
