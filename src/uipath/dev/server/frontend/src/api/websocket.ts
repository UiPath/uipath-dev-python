import type { ClientCommandType, ServerMessage } from "../types/ws";
import { withToken } from "./token";

type MessageHandler = (msg: ServerMessage) => void;

const WS_POLICY_VIOLATION = 1008;

export class WsClient {
  private ws: WebSocket | null = null;
  private baseUrl?: string;
  private handlers: Set<MessageHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;
  private pendingMessages: string[] = [];
  private activeSubscriptions: Set<string> = new Set();

  constructor(url?: string) {
    this.baseUrl = url;
  }

  /** Built per attempt: the token is not known when the client is constructed. */
  private currentUrl(): string {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return withToken(this.baseUrl ?? `${protocol}//${window.location.host}/ws`);
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(this.currentUrl());

    this.ws.onopen = () => {
      console.log("[ws] connected");
      // Re-subscribe to active subscriptions after reconnect
      for (const runId of this.activeSubscriptions) {
        this.sendRaw(JSON.stringify({ type: "subscribe", payload: { run_id: runId } }));
      }
      // Flush any messages queued while connecting
      for (const msg of this.pendingMessages) {
        this.sendRaw(msg);
      }
      this.pendingMessages = [];
    };

    this.ws.onmessage = (event) => {
      let msg: ServerMessage;
      try {
        msg = JSON.parse(event.data);
      } catch {
        console.warn("[ws] failed to parse message", event.data);
        return;
      }
      this.handlers.forEach((h) => {
        try {
          h(msg);
        } catch (e) {
          console.error("[ws] handler error", e);
        }
      });
    };

    this.ws.onclose = (event) => {
      if (event.code === WS_POLICY_VIOLATION) {
        this.shouldReconnect = false;
        console.error(
          "[ws] refused: this page has no valid developer server token. " +
            "Open the URL printed by `uipath dev`, including its ?token=.",
        );
        return;
      }
      console.log("[ws] disconnected");
      if (this.shouldReconnect) {
        this.reconnectTimer = setTimeout(() => this.connect(), 2000);
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  onMessage(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  private sendRaw(data: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    }
  }

  send(type: ClientCommandType, payload: Record<string, unknown>): void {
    const data = JSON.stringify({ type, payload });
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    } else {
      this.pendingMessages.push(data);
    }
  }

  subscribe(runId: string): void {
    this.activeSubscriptions.add(runId);
    this.send("subscribe", { run_id: runId });
  }

  unsubscribe(runId: string): void {
    this.activeSubscriptions.delete(runId);
    this.send("unsubscribe", { run_id: runId });
  }

  sendChatMessage(runId: string, text: string): void {
    this.send("chat.message", { run_id: runId, text });
  }

  sendInterruptResponse(runId: string, data: Record<string, unknown>): void {
    this.send("chat.interrupt_response", { run_id: runId, data });
  }

  debugStep(runId: string): void {
    this.send("debug.step", { run_id: runId });
  }

  debugContinue(runId: string): void {
    this.send("debug.continue", { run_id: runId });
  }

  debugStop(runId: string): void {
    this.send("debug.stop", { run_id: runId });
  }

  setBreakpoints(runId: string, breakpoints: string[]): void {
    this.send("debug.set_breakpoints", { run_id: runId, breakpoints });
  }

  sendCliAgentStart(agentId: string, sessionId: string, cols: number, rows: number): void {
    this.send("cli_agent.start", { agent_id: agentId, session_id: sessionId, cols, rows });
  }

  sendCliAgentInput(sessionId: string, data: string): void {
    this.send("cli_agent.input", { session_id: sessionId, data });
  }

  sendCliAgentResize(sessionId: string, cols: number, rows: number): void {
    this.send("cli_agent.resize", { session_id: sessionId, cols, rows });
  }

  sendCliAgentStop(sessionId: string): void {
    this.send("cli_agent.stop", { session_id: sessionId });
  }
}
