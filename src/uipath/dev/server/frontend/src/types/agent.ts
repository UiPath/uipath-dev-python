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

export interface AgentQuestion {
  question_id: string;
  question: string;
  options: string[];
}

export type AgentStatus = "idle" | "thinking" | "planning" | "executing" | "awaiting_approval" | "awaiting_input" | "done" | "error";

export interface AgentModel {
  model_name: string;
  vendor: string | null;
}

export interface AgentSkill {
  id: string;
  name: string;
  description: string;
}

export interface AgentSessionState {
  session_id: string;
  status: string;
  model: string;
  messages: AgentMessage[];
  plan: AgentPlanItem[];
  total_prompt_tokens: number;
  total_completion_tokens: number;
  turn_count: number;
  compaction_count: number;
}
