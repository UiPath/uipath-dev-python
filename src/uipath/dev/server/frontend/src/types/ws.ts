export type ServerEventType = "run.updated" | "log" | "trace" | "chat" | "state";

export interface ServerMessage {
  type: ServerEventType;
  payload: Record<string, unknown>;
}

export type ClientCommandType =
  | "subscribe"
  | "unsubscribe"
  | "chat.message"
  | "debug.step"
  | "debug.continue"
  | "debug.stop"
  | "debug.set_breakpoints";

export interface ClientMessage {
  type: ClientCommandType;
  payload: Record<string, unknown>;
}
