import { useEffect, useRef } from "react";

interface StateEvent {
  node_name: string;
  timestamp: number;
}

interface Props {
  events: StateEvent[];
  runStatus: string;
}

export default function RunEventsPanel({ events, runStatus }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

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
      className="h-full overflow-y-auto font-mono text-xs"
    >
      {events.map((event, i) => {
        const time = new Date(event.timestamp).toLocaleTimeString(undefined, {
          hour12: false,
        });
        return (
          <div
            key={i}
            className="flex items-center gap-2 px-3 py-1.5"
            style={{
              background: i % 2 === 0 ? "var(--bg-primary)" : "var(--bg-secondary)",
            }}
          >
            <span className="shrink-0" style={{ color: "var(--text-muted)" }}>
              {time}
            </span>
            <span className="shrink-0" style={{ color: "var(--accent)" }}>
              &#9656;
            </span>
            <span style={{ color: "var(--text-primary)" }}>{event.node_name}</span>
          </div>
        );
      })}
    </div>
  );
}
