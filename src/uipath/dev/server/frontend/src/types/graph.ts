export interface GraphNode {
  id: string;
  type: string;
  data: {
    label: string;
    tool_names?: string[];
    tool_count?: number;
    model_name?: string;
    subgraph?: GraphData;
  };
  position: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  conditional?: boolean;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
