export type ServerEventType =
  | "run.updated"
  | "log"
  | "trace"
  | "chat"
  | "chat.interrupt"
  | "state"
  | "reload"
  | "files.changed"
  | "eval_run.created"
  | "eval_run.progress"
  | "eval_run.completed"
  | "cli_agent.output"
  | "cli_agent.exit"
  | "mcp.tool_call";

export interface ServerMessage {
  type: ServerEventType;
  payload: Record<string, unknown>;
}

export type ClientCommandType =
  | "subscribe"
  | "unsubscribe"
  | "chat.message"
  | "chat.interrupt_response"
  | "debug.step"
  | "debug.continue"
  | "debug.stop"
  | "debug.set_breakpoints"
  | "cli_agent.start"
  | "cli_agent.input"
  | "cli_agent.resize"
  | "cli_agent.stop";

export interface ClientMessage {
  type: ClientCommandType;
  payload: Record<string, unknown>;
}
