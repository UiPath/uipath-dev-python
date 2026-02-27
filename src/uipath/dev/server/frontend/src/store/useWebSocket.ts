import { useEffect, useRef } from "react";
import { WsClient } from "../api/websocket";
import { useRunStore } from "./useRunStore";
import { useEvalStore } from "./useEvalStore";
import { useAgentStore } from "./useAgentStore";
import { useExplorerStore } from "./useExplorerStore";
import { readFile, listDirectory } from "../api/explorer-client";
import type { RunSummary, TraceSpan, LogEntry, InterruptEvent } from "../types/run";
import type { EvalRunSummary, EvalItemResult } from "../types/eval";
import type { AgentPlanItem, AgentStatus } from "../types/agent";

let sharedWs: WsClient | null = null;

export function getWs(): WsClient {
  if (!sharedWs) {
    sharedWs = new WsClient();
    sharedWs.connect();
  }
  return sharedWs;
}

export function useWebSocket() {
  const ws = useRef(getWs());
  const { upsertRun, addTrace, addLog, addChatEvent, setActiveInterrupt, setActiveNode, removeActiveNode, resetRunGraphState, addStateEvent, setReloadPending } = useRunStore();
  const { upsertEvalRun, updateEvalRunProgress, completeEvalRun } = useEvalStore();

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
        case "chat.interrupt": {
          const runId = msg.payload.run_id as string;
          setActiveInterrupt(runId, msg.payload as unknown as InterruptEvent);
          break;
        }
        case "state": {
          const runId = msg.payload.run_id as string;
          const nodeName = msg.payload.node_name as string;
          const qualifiedNodeName = (msg.payload.qualified_node_name as string | undefined) ?? null;
          const phase = (msg.payload.phase as string | undefined) ?? null;
          const payload = msg.payload.payload as Record<string, unknown> | undefined;
          if (nodeName === "__start__" && phase === "started") {
            resetRunGraphState(runId);
          }
          if (phase === "started") {
            setActiveNode(runId, nodeName, qualifiedNodeName);
          } else if (phase === "completed") {
            removeActiveNode(runId, nodeName);
          }
          addStateEvent(runId, nodeName, payload, qualifiedNodeName, phase);
          break;
        }
        case "reload":
          setReloadPending(true);
          break;
        case "files.changed": {
          const changedFiles = msg.payload.files as string[];
          const changedSet = new Set(changedFiles);
          const explorer = useExplorerStore.getState();
          // Refresh open tab contents
          for (const tab of explorer.openTabs) {
            if (explorer.dirty[tab] || !changedSet.has(tab)) continue;
            readFile(tab).then((fc) => {
              const s = useExplorerStore.getState();
              if (s.dirty[tab]) return;
              if (s.fileCache[tab]?.content === fc.content) return;
              s.setFileContent(tab, fc);
            }).catch(() => {});
          }
          // Refresh directory listings for already-loaded parent dirs
          const dirsToRefresh = new Set<string>();
          for (const filePath of changedFiles) {
            const lastSlash = filePath.lastIndexOf("/");
            const parentDir = lastSlash === -1 ? "" : filePath.substring(0, lastSlash);
            if (parentDir in explorer.children) {
              dirsToRefresh.add(parentDir);
            }
          }
          for (const dir of dirsToRefresh) {
            listDirectory(dir)
              .then((entries) => useExplorerStore.getState().setChildren(dir, entries))
              .catch(() => {});
          }
          break;
        }
        // Eval events
        case "eval_run.created":
          upsertEvalRun(msg.payload as unknown as EvalRunSummary);
          break;
        case "eval_run.progress": {
          const { run_id, completed, total, item_result } = msg.payload as {
            run_id: string;
            completed: number;
            total: number;
            item_result?: EvalItemResult;
          };
          updateEvalRunProgress(run_id, completed, total, item_result);
          break;
        }
        case "eval_run.completed": {
          const { run_id, overall_score, evaluator_scores } = msg.payload as {
            run_id: string;
            overall_score: number;
            evaluator_scores: Record<string, number>;
          };
          completeEvalRun(run_id, overall_score, evaluator_scores);
          break;
        }
        // Agent events
        case "agent.status": {
          const { session_id, status } = msg.payload as { session_id: string; status: AgentStatus };
          const agent = useAgentStore.getState();
          if (!agent.sessionId) agent.setSessionId(session_id);
          agent.setStatus(status);
          break;
        }
        case "agent.text": {
          const { session_id, content, done } = msg.payload as { session_id: string; content: string; done: boolean };
          const agent = useAgentStore.getState();
          if (!agent.sessionId) agent.setSessionId(session_id);
          agent.appendAssistantText(content, done);
          break;
        }
        case "agent.plan": {
          const { session_id, items } = msg.payload as { session_id: string; items: AgentPlanItem[] };
          const agent = useAgentStore.getState();
          if (!agent.sessionId) agent.setSessionId(session_id);
          agent.setPlan(items);
          break;
        }
        case "agent.tool_use": {
          const { session_id, tool, args } = msg.payload as { session_id: string; tool: string; args: Record<string, unknown> };
          const agent = useAgentStore.getState();
          if (!agent.sessionId) agent.setSessionId(session_id);
          agent.addToolUse(tool, args);
          break;
        }
        case "agent.tool_result": {
          const { tool, result, is_error } = msg.payload as { session_id: string; tool: string; result: string; is_error: boolean };
          useAgentStore.getState().addToolResult(tool, result, is_error);
          break;
        }
        case "agent.tool_approval": {
          const { session_id, tool_call_id, tool, args } = msg.payload as {
            session_id: string;
            tool_call_id: string;
            tool: string;
            args: Record<string, unknown>;
          };
          const agent = useAgentStore.getState();
          if (!agent.sessionId) agent.setSessionId(session_id);
          agent.addToolApprovalRequest(tool_call_id, tool, args);
          break;
        }
        case "agent.error": {
          const { message: errMsg } = msg.payload as { session_id: string; message: string };
          useAgentStore.getState().addError(errMsg);
          break;
        }
      }
    });

    return unsub;
  }, [upsertRun, addTrace, addLog, addChatEvent, setActiveInterrupt, setActiveNode, removeActiveNode, resetRunGraphState, addStateEvent, setReloadPending, upsertEvalRun, updateEvalRunProgress, completeEvalRun]);

  return ws.current;
}
