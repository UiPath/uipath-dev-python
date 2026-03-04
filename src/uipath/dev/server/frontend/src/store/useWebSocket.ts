import { useEffect, useRef } from "react";
import { WsClient } from "../api/websocket";
import { listEntrypoints } from "../api/client";
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
  const { upsertRun, addTrace, addLog, addChatEvent, setActiveInterrupt, setActiveNode, removeActiveNode, resetRunGraphState, addStateEvent } = useRunStore();
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
          const agentState = useAgentStore.getState();
          const agentStatus = agentState.status;
          const agentIsActive = agentStatus === "thinking" || agentStatus === "planning" || agentStatus === "executing" || agentStatus === "awaiting_approval";
          // Grace period: treat changes within 3s of agent finishing as agent-driven
          // (file watcher debounce can delay files.changed past agent.status:done)
          const recentlyActive = !agentIsActive && agentState._lastActiveAt != null && (Date.now() - agentState._lastActiveAt) < 3000;

          // Filter out directory paths — file watcher reports both files and dirs.
          // A path with a dot in the last segment is likely a file; no dot = likely a directory.
          // Also skip paths already known as directories in the tree.
          const fileChanges = changedFiles.filter((p) => {
            if (p in explorer.children) return false; // known directory
            const lastSegment = p.split("/").pop() ?? "";
            return lastSegment.includes(".");
          });

          console.log("[files.changed]", { all: changedFiles, files: fileChanges, agentStatus, agentIsActive, recentlyActive });

          if (agentIsActive || recentlyActive) {
            // Agent is running (or just finished) — treat file changes as agent-driven
            // We track diff candidate across async calls; first file to resolve wins
            let diffShown = false;

            for (const filePath of fileChanges) {
              // Skip dirty files (user is editing)
              if (explorer.dirty[filePath]) continue;

              // Snapshot old content before fetching new (for diff)
              const oldContent = explorer.fileCache[filePath]?.content ?? null;
              const oldLanguage = explorer.fileCache[filePath]?.language ?? null;

              // Fetch new content — this also validates the file still exists
              readFile(filePath).then((fc) => {
                const s = useExplorerStore.getState();
                if (s.dirty[filePath]) return;
                s.setFileContent(filePath, fc);

                // Expand tree to reveal the file (but don't auto-open a new tab)
                s.expandPath(filePath);

                // Load unloaded parent directories so tree reveals the file
                const parts = filePath.split("/");
                for (let j = 1; j < parts.length; j++) {
                  const dir = parts.slice(0, j).join("/");
                  if (!(dir in useExplorerStore.getState().children)) {
                    listDirectory(dir)
                      .then((entries) => useExplorerStore.getState().setChildren(dir, entries))
                      .catch(() => {});
                  }
                }

                // Show diff for the first eligible file (only if already open in a tab)
                const isOpenInTab = useExplorerStore.getState().openTabs.includes(filePath);
                if (!diffShown && isOpenInTab && oldContent !== null && fc.content !== null && oldContent !== fc.content) {
                  diffShown = true;
                  s.setDiffView({ path: filePath, original: oldContent, modified: fc.content, language: oldLanguage });
                  setTimeout(() => {
                    const cur = useExplorerStore.getState().diffView;
                    if (cur && cur.path === filePath && cur.original === oldContent) {
                      useExplorerStore.getState().setDiffView(null);
                    }
                  }, 5000);
                }

                s.markAgentChanged(filePath);
                setTimeout(() => useExplorerStore.getState().clearAgentChanged(filePath), 10000);
              }).catch(() => {
                // File doesn't exist (deleted) — close tab if it was open
                const s = useExplorerStore.getState();
                if (s.openTabs.includes(filePath)) {
                  s.closeTab(filePath);
                }
              });
            }
          } else {
            // No agent running — regular refresh logic
            for (const tab of explorer.openTabs) {
              if (explorer.dirty[tab] || !changedSet.has(tab)) continue;
              readFile(tab).then((fc) => {
                const s = useExplorerStore.getState();
                if (s.dirty[tab]) return;
                if (s.fileCache[tab]?.content === fc.content) return;
                s.setFileContent(tab, fc);
              }).catch(() => {});
            }
          }

          // Refresh directory listings for already-loaded parent dirs (always)
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
          // Clear pending question when agent finishes or errors
          if (status === "done" || status === "error" || status === "idle") {
            agent.setActiveQuestion(null);
          }
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
          const { session_id, tool_call_id, tool, args } = msg.payload as { session_id: string; tool_call_id: string; tool: string; args: Record<string, unknown> };
          const agent = useAgentStore.getState();
          if (!agent.sessionId) agent.setSessionId(session_id);
          agent.addToolUse(tool_call_id, tool, args);
          break;
        }
        case "agent.tool_result": {
          const { tool_call_id, result, is_error } = msg.payload as { session_id: string; tool_call_id: string; result: string; is_error: boolean };
          useAgentStore.getState().addToolResult(tool_call_id, result, is_error);
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
        case "agent.thinking": {
          const { content } = msg.payload as { session_id: string; content: string };
          useAgentStore.getState().appendThinking(content);
          break;
        }
        case "agent.text_delta": {
          const { session_id: deltaSid, delta } = msg.payload as { session_id: string; delta: string };
          const agentDelta = useAgentStore.getState();
          if (!agentDelta.sessionId) agentDelta.setSessionId(deltaSid);
          agentDelta.appendAssistantText(delta, false);
          break;
        }
        case "agent.question": {
          const { session_id: qSid, question_id, question, options } = msg.payload as {
            session_id: string;
            question_id: string;
            question: string;
            options: string[];
          };
          const agentQ = useAgentStore.getState();
          if (!agentQ.sessionId) agentQ.setSessionId(qSid);
          agentQ.setActiveQuestion({ question_id, question, options });
          break;
        }
        case "agent.token_usage": {
          // Token usage received — could store for display if needed
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
  }, [upsertRun, addTrace, addLog, addChatEvent, setActiveInterrupt, setActiveNode, removeActiveNode, resetRunGraphState, addStateEvent, upsertEvalRun, updateEvalRunProgress, completeEvalRun]);

  return ws.current;
}
