import type { GraphData } from "./graph";

export interface RunSummary {
  id: string;
  entrypoint: string;
  input_data: Record<string, unknown>;
  mode: "run" | "debug" | "chat";
  status: string;
  start_time: string | null;
  end_time: string | null;
  duration: string;
  output_data: Record<string, unknown> | string | null;
  error: RunError | null;
  trace_count: number;
  log_count: number;
  message_count: number;
  breakpoint_node: string | null;
  breakpoint_next_nodes: string[];
  breakpoints: string[];
}

export interface StateEventData {
  run_id: string;
  node_name: string;
  qualified_node_name?: string | null;
  phase?: string | null;
  timestamp: string;
  payload?: Record<string, unknown>;
}

export interface RunDetail extends RunSummary {
  traces: TraceSpan[];
  logs: LogEntry[];
  messages: ChatMessageData[];
  states: StateEventData[];
  graph: GraphData | null;
}

export interface TraceSpan {
  run_id: string;
  span_name: string;
  span_id: string;
  parent_span_id: string | null;
  trace_id: string | null;
  status: string;
  duration_ms: number | null;
  timestamp: string;
  attributes: Record<string, unknown>;
}

export interface LogEntry {
  run_id: string;
  level: string;
  message: string;
  timestamp: string;
}

export interface ChatMessageData {
  message_id: string;
  role: string;
  content_parts?: ContentPart[];
  tool_calls?: ToolCall[];
  created_at: string;
  updated_at: string;
}

export interface ContentPart {
  content_part_id: string;
  mime_type: string;
  data: { inline?: string; uri?: string };
}

export interface ToolCall {
  tool_call_id: string;
  name: string;
  input: unknown;
  result?: { value: unknown; is_error?: boolean };
}

export interface RunError {
  code: string;
  title: string;
  detail: string;
  category: string;
}

export interface InterruptEvent {
  run_id: string;
  interrupt_id: string;
  interrupt_type: "tool_call_confirmation" | "generic";
  tool_call_id?: string;
  tool_name?: string;
  input_schema?: unknown;
  input_value?: unknown;
  content?: unknown;
}
