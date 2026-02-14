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
  const { upsertRun, addTrace, addLog, addChatEvent, setActiveNode, addStateEvent, setReloadPending } = useRunStore();

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
        case "state": {
          const runId = msg.payload.run_id as string;
          const nodeName = msg.payload.node_name as string;
          const qualifiedNodeName = (msg.payload.qualified_node_name as string | undefined) ?? null;
          const payload = msg.payload.payload as Record<string, unknown> | undefined;
          setActiveNode(runId, nodeName, qualifiedNodeName);
          addStateEvent(runId, nodeName, payload, qualifiedNodeName);
          break;
        }
        case "reload":
          setReloadPending(true);
          break;
      }
    });

    return unsub;
  }, [upsertRun, addTrace, addLog, addChatEvent, setActiveNode, addStateEvent, setReloadPending]);

  return ws.current;
}
