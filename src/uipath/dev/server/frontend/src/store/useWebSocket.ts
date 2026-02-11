import { useEffect, useRef } from "react";
import { WsClient } from "../api/websocket";
import { useRunStore } from "./useRunStore";
import type { RunSummary, TraceSpan, LogEntry } from "../types/run";

let sharedWs: WsClient | null = null;

function getWs(): WsClient {
  if (!sharedWs) {
    sharedWs = new WsClient();
    sharedWs.connect();
  }
  return sharedWs;
}

export function useWebSocket() {
  const ws = useRef(getWs());
  const { upsertRun, addTrace, addLog, addChatEvent } = useRunStore();

  useEffect(() => {
    const client = ws.current;

    const unsub = client.onMessage((msg) => {
      switch (msg.type) {
        case "run.updated":
          upsertRun(msg.payload as unknown as RunSummary);
          break;
        case "trace":
          addTrace(msg.payload as unknown as TraceSpan);
          break;
        case "log":
          addLog(msg.payload as unknown as LogEntry);
          break;
        case "chat": {
          const runId = msg.payload.run_id as string;
          addChatEvent(runId, msg.payload);
          break;
        }
      }
    });

    return unsub;
  }, [upsertRun, addTrace, addLog, addChatEvent]);

  return ws.current;
}
