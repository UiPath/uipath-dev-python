import { useEffect, useRef } from "react";
import { WsClient } from "../api/websocket";
import { listEntrypoints } from "../api/client";
import { useRunStore } from "./useRunStore";
import { useEvalStore } from "./useEvalStore";
import { useCliAgentStore } from "./useCliAgentStore";
import { useExplorerStore } from "./useExplorerStore";
import { getTerminalWriter } from "../api/cli-terminal-bridge";
import { readFile, listDirectory } from "../api/explorer-client";
import type { RunSummary, TraceSpan, LogEntry, InterruptEvent } from "../types/run";
import type { EvalRunSummary, EvalItemResult } from "../types/eval";
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
  const { upsertRun, addTrace, addLog, addChatEvent, setActiveInterrupt, setActiveNode, removeActiveNode, resetRunGraphState, addStateEvent } = useRunStore();
  const { upsertEvalRun, updateEvalRunProgress, completeEvalRun } = useEvalStore();

  useEffect(() => {
    const client = ws.current;

    const unsub = client.onMessage((msg) => {
      switch (msg.type) {
        case "run.updated": {
          const runPayload = msg.payload as unknown as RunSummary;
          upsertRun(runPayload);
          // Log key run lifecycle transitions to the events sidebar
          if (runPayload.status === "running" || runPayload.status === "completed" || runPayload.status === "failed") {
            useCliAgentStore.getState().addEvent({
              type: "run_lifecycle",
              timestamp: Date.now(),
              runId: runPayload.id,
              entrypoint: runPayload.entrypoint,
              status: runPayload.status,
            });
          }
          break;
        }
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
        case "reload": {
          const alreadyReloaded = msg.payload.reloaded as boolean | undefined;
          if (alreadyReloaded) {
            // Server already reloaded the factory — just refresh entrypoints
            listEntrypoints()
              .then((eps) => {
                const store = useRunStore.getState();
                store.setEntrypoints(eps.map((e) => e.name));
                store.setReloadPending(false);
              })
              .catch((err) => console.error("Failed to refresh entrypoints:", err));
          } else {
            // Runs active or reload failed — show manual reload prompt
            useRunStore.getState().setReloadPending(true);
          }
          break;
        }
        case "files.changed": {
          const changedFiles = msg.payload.files as string[];
          const changedSet = new Set(changedFiles);
          const explorer = useExplorerStore.getState();

          // Filter out directory paths — file watcher reports both files and dirs.
          const fileChanges = changedFiles.filter((p) => {
            if (p in explorer.children) return false;
            const lastSegment = p.split("/").pop() ?? "";
            return lastSegment.includes(".");
          });

          // Log file changes as events in the explorer sidebar
          if (fileChanges.length > 0) {
            useCliAgentStore.getState().addEvent({
              type: "files_changed",
              timestamp: Date.now(),
              files: fileChanges,
            });
          }

          // Refresh open tabs with new content
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
        // CLI agent events
        case "cli_agent.output": {
          const { session_id, data } = msg.payload as { session_id: string; data: string };
          const writer = getTerminalWriter(session_id);
          if (writer) {
            const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
            writer(bytes);
          }
          break;
        }
        case "cli_agent.exit": {
          const { session_id, exit_code } = msg.payload as { session_id: string; exit_code: number };
          const cliStore = useCliAgentStore.getState();
          if (cliStore.sessionId === session_id) {
            cliStore.setStatus("exited");
            cliStore.setExitCode(exit_code);
            const agent = cliStore.availableAgents.find((a) => a.id === cliStore.selectedAgentId);
            cliStore.addEvent({
              type: "session",
              timestamp: Date.now(),
              agentName: agent?.name ?? "Unknown",
              action: "exited",
              exitCode: exit_code,
            });
          }
          break;
        }
        case "mcp.tool_call": {
          const { tool, args } = msg.payload as { tool: string; args: Record<string, unknown> };
          useCliAgentStore.getState().addEvent({
            type: "mcp_tool_call",
            timestamp: Date.now(),
            tool,
            args,
          });
          break;
        }
      }
    });

    return unsub;
  }, [upsertRun, addTrace, addLog, addChatEvent, setActiveInterrupt, setActiveNode, removeActiveNode, resetRunGraphState, addStateEvent, upsertEvalRun, updateEvalRunProgress, completeEvalRun]);

  return ws.current;
}
