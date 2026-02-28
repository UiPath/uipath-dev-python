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
  | "agent.status"
  | "agent.text"
  | "agent.plan"
  | "agent.tool_use"
  | "agent.tool_result"
  | "agent.tool_approval"
  | "agent.error"
  | "agent.thinking"
  | "agent.text_delta"
  | "agent.token_usage"
  | "agent.question";

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
  | "agent.message"
  | "agent.stop"
  | "agent.tool_response"
  | "agent.question_response";

export interface ClientMessage {
  type: ClientCommandType;
  payload: Record<string, unknown>;
}
