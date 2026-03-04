import { MarkerType, type Node, type Edge } from "reactflow";
import type { ElkNode, ElkExtendedEdge } from "elkjs/lib/elk.bundled.js";
import type ELKType from "elkjs/lib/elk.bundled.js";
import type { GraphData } from "../../types/graph";

// ─── Node size helpers ───────────────────────────────────────────────
const MIN_NODE_WIDTH = 80;
const BASE_NODE_HEIGHT = 32; // 2(border) + 6(py) + 16(text-xs) + 6(py) + 2(border)
const TYPE_LABEL_HEIGHT = 13; // fontSize 9 (~11px line) + marginBottom 1

export function computeNodeWidth(data: Record<string, unknown>): number {
  const label = (data?.label as string) ?? "";
  // No hard cap — let ELK handle spacing; nodes must fit their labels
  return Math.max(MIN_NODE_WIDTH, label.length * 8 + 32);
}

export function computeNodeHeight(
  data: Record<string, unknown>,
  type?: string,
): number {
  let h = BASE_NODE_HEIGHT;
  // ModelNode and ToolNode always render a type label above the main label
  if (type === "modelNode" || type === "toolNode") {
    h += TYPE_LABEL_HEIGHT;
  }
  const toolNames = data?.tool_names as string[] | undefined;
  if (toolNames && toolNames.length > 0) {
    h +=
      Math.min(toolNames.length, 3) * 12 +
      (toolNames.length > 3 ? 12 : 0) +
      4;
  }
  if (data?.model_name) h += 14;
  return h;
}

// ─── ELK layout engine (lazy-loaded) ────────────────────────────────
let elk: InstanceType<typeof ELKType> | null = null;
async function getElk() {
  if (!elk) {
    const { default: ELK } = await import("elkjs/lib/elk.bundled.js");
    elk = new ELK();
  }
  return elk;
}

const ELK_OPTIONS: Record<string, string> = {
  "elk.algorithm": "layered",
  "elk.direction": "DOWN",
  "elk.edgeRouting": "ORTHOGONAL",
  "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.spacing.nodeNode": "25",
  "elk.layered.spacing.nodeNodeBetweenLayers": "50",
  "elk.spacing.edgeNode": "30",
  "elk.spacing.edgeEdge": "15",
  "elk.layered.spacing.edgeNodeBetweenLayers": "25",
  "elk.layered.spacing.edgeEdgeBetweenLayers": "15",
  "elk.portAlignment.default": "CENTER",
  "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
};

const SUBGRAPH_PADDING = "[top=35,left=15,bottom=15,right=15]";

/** Build ELK hierarchical graph from our graph data. */
function buildElkGraph(graphData: GraphData): ElkNode {
  const children: ElkNode[] = [];
  const edges: ElkExtendedEdge[] = [];

  for (const node of graphData.nodes) {
    const data = node.data as Record<string, unknown>;
    const elkNode: ElkNode = {
      id: node.id,
      width: computeNodeWidth(data),
      height: computeNodeHeight(data, node.type),
    };

    // Compound node with subgraph children
    if (node.data.subgraph) {
      const sub = node.data.subgraph;
      // Let ELK compute compound node size from children + padding
      delete elkNode.width;
      delete elkNode.height;
      elkNode.layoutOptions = {
        ...ELK_OPTIONS,
        "elk.padding": SUBGRAPH_PADDING,
      };
      elkNode.children = sub.nodes.map((cn) => ({
        id: `${node.id}/${cn.id}`,
        width: computeNodeWidth(cn.data as Record<string, unknown>),
        height: computeNodeHeight(cn.data as Record<string, unknown>, cn.type),
      }));
      elkNode.edges = sub.edges.map((e) => ({
        id: `${node.id}/${e.id}`,
        sources: [`${node.id}/${e.source}`],
        targets: [`${node.id}/${e.target}`],
      }));
    }

    children.push(elkNode);
  }

  for (const edge of graphData.edges) {
    edges.push({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    });
  }

  return { id: "root", layoutOptions: ELK_OPTIONS, children, edges };
}

/** Marker for edge arrow heads. */
export const arrowMarker = {
  type: MarkerType.ArrowClosed,
  width: 12,
  height: 12,
  color: "var(--node-border)",
};

/** Style an edge, dashed if conditional. */
export function mkEdgeStyle(conditional?: boolean) {
  return {
    stroke: "var(--node-border)",
    strokeWidth: 1.5,
    ...(conditional ? { strokeDasharray: "6 3" } : {}),
  };
}

/** Absolute rect for a laid-out node. */
export interface NodeRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Build an RF edge from an ELK edge, using ELK's native section data. */
function buildRfEdge(
  elkEdge: ElkExtendedEdge,
  nodeRects: Map<string, NodeRect>,
  origLabel?: string,
  origConditional?: boolean,
  parentOffset?: { x: number; y: number },
): Edge {
  const section = elkEdge.sections?.[0];
  const ox = parentOffset?.x ?? 0;
  const oy = parentOffset?.y ?? 0;

  let edgeData;
  if (section) {
    edgeData = {
      sourcePoint: {
        x: section.startPoint.x + ox,
        y: section.startPoint.y + oy,
      },
      targetPoint: {
        x: section.endPoint.x + ox,
        y: section.endPoint.y + oy,
      },
      bendPoints: (section.bendPoints ?? []).map((bp) => ({
        x: bp.x + ox,
        y: bp.y + oy,
      })),
    };
  } else {
    // Fallback: compute straight path from source bottom-center to target top-center
    const src = nodeRects.get(elkEdge.sources[0]);
    const tgt = nodeRects.get(elkEdge.targets[0]);
    if (src && tgt) {
      edgeData = {
        sourcePoint: { x: src.x + src.width / 2, y: src.y + src.height },
        targetPoint: { x: tgt.x + tgt.width / 2, y: tgt.y },
        bendPoints: [],
      };
    }
  }

  return {
    id: elkEdge.id,
    source: elkEdge.sources[0],
    target: elkEdge.targets[0],
    type: "elk",
    data: edgeData,
    style: mkEdgeStyle(origConditional),
    markerEnd: arrowMarker,
    ...(origLabel
      ? {
          label: origLabel,
          labelStyle: { fill: "var(--text-muted)", fontSize: 10 },
          labelBgStyle: { fill: "var(--bg-primary)", fillOpacity: 0.8 },
        }
      : {}),
  };
}

/** Run ELK layout and convert result to React Flow nodes + edges. */
export async function runElkLayout(
  graphData: GraphData,
): Promise<{ nodes: Node[]; edges: Edge[] }> {
  const elkGraph = buildElkGraph(graphData);
  const elkInstance = await getElk();
  const layout = await elkInstance.layout(elkGraph);

  // Build lookup: prefixed-id → { type, data } from original graph data
  const nodeInfo = new Map<
    string,
    { type: string; data: Record<string, unknown> }
  >();
  for (const n of graphData.nodes) {
    nodeInfo.set(n.id, {
      type: n.type,
      data: n.data as Record<string, unknown>,
    });
    if (n.data.subgraph) {
      for (const cn of n.data.subgraph.nodes) {
        nodeInfo.set(`${n.id}/${cn.id}`, {
          type: cn.type,
          data: cn.data as Record<string, unknown>,
        });
      }
    }
  }

  const rfNodes: Node[] = [];
  const rfEdges: Edge[] = [];

  // Build absolute-position lookup for all nodes (needed for edge fallback)
  const nodeRects = new Map<string, NodeRect>();
  for (const elkNode of layout.children ?? []) {
    const nx = elkNode.x ?? 0;
    const ny = elkNode.y ?? 0;
    nodeRects.set(elkNode.id, {
      x: nx,
      y: ny,
      width: elkNode.width ?? 0,
      height: elkNode.height ?? 0,
    });
    for (const child of elkNode.children ?? []) {
      nodeRects.set(child.id, {
        x: nx + (child.x ?? 0),
        y: ny + (child.y ?? 0),
        width: child.width ?? 0,
        height: child.height ?? 0,
      });
    }
  }

  // ── Nodes ──
  for (const elkNode of layout.children ?? []) {
    const info = nodeInfo.get(elkNode.id);
    const hasChildren = (elkNode.children?.length ?? 0) > 0;

    if (hasChildren) {
      // Group node (subgraph container) — must come before children in array
      rfNodes.push({
        id: elkNode.id,
        type: "groupNode",
        data: {
          ...(info?.data ?? {}),
          nodeWidth: elkNode.width,
          nodeHeight: elkNode.height,
        },
        position: { x: elkNode.x ?? 0, y: elkNode.y ?? 0 },
        style: { width: elkNode.width, height: elkNode.height },
      });

      // Children (positions are relative to parent)
      for (const child of elkNode.children ?? []) {
        const ci = nodeInfo.get(child.id);
        rfNodes.push({
          id: child.id,
          type: ci?.type ?? "defaultNode",
          data: { ...(ci?.data ?? {}), nodeWidth: child.width },
          position: { x: child.x ?? 0, y: child.y ?? 0 },
          parentNode: elkNode.id,
          extent: "parent",
        });
      }

      // Subgraph internal edges — offset to absolute coords
      const px = elkNode.x ?? 0;
      const py = elkNode.y ?? 0;
      for (const elkEdge of elkNode.edges ?? []) {
        const origNode = graphData.nodes.find((n) => n.id === elkNode.id);
        const origEdge = origNode?.data.subgraph?.edges.find(
          (e) => `${elkNode.id}/${e.id}` === elkEdge.id,
        );
        rfEdges.push(
          buildRfEdge(
            elkEdge,
            nodeRects,
            origEdge?.label,
            origEdge?.conditional,
            { x: px, y: py },
          ),
        );
      }
    } else {
      // Regular (leaf) node
      rfNodes.push({
        id: elkNode.id,
        type: info?.type ?? "defaultNode",
        data: { ...(info?.data ?? {}), nodeWidth: elkNode.width },
        position: { x: elkNode.x ?? 0, y: elkNode.y ?? 0 },
      });
    }
  }

  // ── Top-level edges ──
  for (const elkEdge of layout.edges ?? []) {
    const origEdge = graphData.edges.find((e) => e.id === elkEdge.id);
    rfEdges.push(
      buildRfEdge(elkEdge, nodeRects, origEdge?.label, origEdge?.conditional),
    );
  }

  return { nodes: rfNodes, edges: rfEdges };
}
