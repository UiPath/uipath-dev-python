import type { ClientCommandType, ServerMessage } from "../types/ws";

type MessageHandler = (msg: ServerMessage) => void;

export class WsClient {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: Set<MessageHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;
  private pendingMessages: string[] = [];
  private activeSubscriptions: Set<string> = new Set();

  constructor(url?: string) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    this.url = url ?? `${protocol}//${window.location.host}/ws`;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(this.url);

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
      try {
        const msg: ServerMessage = JSON.parse(event.data);
        this.handlers.forEach((h) => h(msg));
      } catch {
        console.warn("[ws] failed to parse message", event.data);
      }
    };

    this.ws.onclose = () => {
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
}
