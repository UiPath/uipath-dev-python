export interface AgentPlanItem {
  title: string;
  status: "pending" | "in_progress" | "completed";
}

export interface AgentToolCall {
  tool: string;
  args: Record<string, unknown>;
  result?: string;
  is_error?: boolean;
  tool_call_id?: string;
  status?: "pending" | "approved" | "denied";
}

export interface AgentMessage {
  id: string;
  role: "user" | "assistant" | "plan" | "tool" | "thinking";
  content: string;
  timestamp: number;
  toolCall?: AgentToolCall;
  toolCalls?: AgentToolCall[];
  planItems?: AgentPlanItem[];
  done?: boolean;
}

export type AgentStatus = "idle" | "thinking" | "planning" | "executing" | "awaiting_approval" | "done" | "error";

export interface AgentModel {
  model_name: string;
  vendor: string | null;
}

export interface AgentSkill {
  id: string;
  name: string;
  description: string;
}
