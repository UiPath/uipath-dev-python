import { useCallback, useEffect, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Panel,
  MarkerType,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type ReactFlowInstance,
} from "reactflow";
import "reactflow/dist/style.css";
import ELK, { type ElkNode, type ElkExtendedEdge } from "elkjs/lib/elk.bundled.js";
import type { TraceSpan } from "../../types/run";
import type { GraphData } from "../../types/graph";
import { getEntrypointGraph } from "../../api/client";
import { useRunStore } from "../../store/useRunStore";
import StartNode from "./nodes/StartNode";
import EndNode from "./nodes/EndNode";
import ModelNode from "./nodes/ModelNode";
import ToolNode from "./nodes/ToolNode";
import GroupNode from "./nodes/GroupNode";
import DefaultNode from "./nodes/DefaultNode";
import ElkEdge from "./edges/ElkEdge";

const nodeTypes = {
  startNode: StartNode,
  endNode: EndNode,
  modelNode: ModelNode,
  toolNode: ToolNode,
  groupNode: GroupNode,
  defaultNode: DefaultNode,
};

const edgeTypes = { elk: ElkEdge };

// ─── Node size helpers ───────────────────────────────────────────────
const MIN_NODE_WIDTH = 80;
const BASE_NODE_HEIGHT = 36;

function computeNodeWidth(data: Record<string, unknown>): number {
  const label = (data?.label as string) ?? "";
  // No hard cap — let ELK handle spacing; nodes must fit their labels
  return Math.max(MIN_NODE_WIDTH, label.length * 8 + 32);
}

function computeNodeHeight(data: Record<string, unknown>): number {
  let h = BASE_NODE_HEIGHT;
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

// ─── ELK layout engine ──────────────────────────────────────────────
const elk = new ELK();

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
      height: computeNodeHeight(data),
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
        height: computeNodeHeight(cn.data as Record<string, unknown>),
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
const arrowMarker = {
  type: MarkerType.ArrowClosed,
  width: 12,
  height: 12,
  color: "var(--node-border)",
};

/** Style an edge, dashed if conditional. */
function mkEdgeStyle(conditional?: boolean) {
  return {
    stroke: "var(--node-border)",
    strokeWidth: 1.5,
    ...(conditional ? { strokeDasharray: "6 3" } : {}),
  };
}

/** Absolute rect for a laid-out node. */
interface NodeRect {
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
async function runElkLayout(
  graphData: GraphData,
): Promise<{ nodes: Node[]; edges: Edge[] }> {
  const elkGraph = buildElkGraph(graphData);
  const layout = await elk.layout(elkGraph);

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

// ─── Component ───────────────────────────────────────────────────────
interface Props {
  entrypoint: string;
  traces: TraceSpan[];
  runId: string;
  breakpointNode?: string | null;
  onBreakpointChange?: (breakpoints: string[]) => void;
}

export default function GraphPanel({ entrypoint, traces, runId, breakpointNode, onBreakpointChange }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const layoutRef = useRef(0);
  const rfInstance = useRef<ReactFlowInstance | null>(null);

  const bpMap = useRunStore((s) => s.breakpoints[runId]);
  const toggleBreakpoint = useRunStore((s) => s.toggleBreakpoint);
  const clearBreakpoints = useRunStore((s) => s.clearBreakpoints);
  const activeNode = useRunStore((s) => s.activeNodes[runId]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.type === "groupNode") return;
      // For compound children, extract the plain ID from "parentId/childId"
      const plainId = node.id.includes("/") ? node.id.split("/").pop()! : node.id;
      toggleBreakpoint(runId, plainId);
      // Immediately notify parent with the updated breakpoints
      const updated = useRunStore.getState().breakpoints[runId] ?? {};
      onBreakpointChange?.(Object.keys(updated));
    },
    [runId, toggleBreakpoint, onBreakpointChange],
  );

  const hasAnyBreakpoint = bpMap && Object.keys(bpMap).length > 0;

  const onToggleAllBreakpoints = useCallback(() => {
    if (hasAnyBreakpoint) {
      clearBreakpoints(runId);
      onBreakpointChange?.([]);
    } else {
      // Set breakpoints on all non-group, non-start, non-end nodes
      const nodeIds: string[] = [];
      for (const n of nodes) {
        if (n.type === "groupNode" || n.type === "startNode" || n.type === "endNode") continue;
        const plainId = n.id.includes("/") ? n.id.split("/").pop()! : n.id;
        nodeIds.push(plainId);
      }
      for (const id of nodeIds) {
        if (!bpMap?.[id]) toggleBreakpoint(runId, id);
      }
      const updated = useRunStore.getState().breakpoints[runId] ?? {};
      onBreakpointChange?.(Object.keys(updated));
    }
  }, [runId, hasAnyBreakpoint, bpMap, nodes, clearBreakpoints, toggleBreakpoint, onBreakpointChange]);

  // Inject hasBreakpoint into node data when breakpoints change
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.type === "groupNode") return n;
        const plainId = n.id.includes("/") ? n.id.split("/").pop()! : n.id;
        const has = !!(bpMap && bpMap[plainId]);
        return has !== !!n.data?.hasBreakpoint
          ? { ...n, data: { ...n.data, hasBreakpoint: has } }
          : n;
      }),
    );
  }, [bpMap, setNodes]);

  // Highlight the node where execution is paused at a breakpoint
  useEffect(() => {
    const bpNames = breakpointNode
      ? new Set(breakpointNode.split(",").map((s) => s.trim()).filter(Boolean))
      : null;
    setNodes((nds) =>
      nds.map((n) => {
        if (n.type === "groupNode") return n;
        const plainId = n.id.includes("/") ? n.id.split("/").pop()! : n.id;
        const label = n.data?.label as string | undefined;
        const paused = bpNames != null && (bpNames.has(plainId) || (label != null && bpNames.has(label)));
        return paused !== !!n.data?.isPausedHere
          ? { ...n, data: { ...n.data, isPausedHere: paused } }
          : n;
      }),
    );
  }, [breakpointNode, setNodes]);

  // Highlight edges + nodes during execution
  // - Paused at breakpoint (before node X): edges INTO X, node X (via isPausedHere)
  // - Running (state event after node Y completes): edges OUT of Y, target nodes of those edges
  useEffect(() => {
    const isPaused = !!breakpointNode;
    let matchIds = new Set<string>();
    const activeTargetIds = new Set<string>();

    // 1) Build label→ID lookup (read-only pass, returns nds unchanged)
    setNodes((nds) => {
      const labelToIds = new Map<string, Set<string>>();
      for (const n of nds) {
        const label = n.data?.label as string | undefined;
        if (!label) continue;
        const plainId = n.id.includes("/") ? n.id.split("/").pop()! : n.id;
        for (const key of [plainId, label]) {
          let s = labelToIds.get(key);
          if (!s) { s = new Set(); labelToIds.set(key, s); }
          s.add(plainId);
        }
      }

      if (isPaused && breakpointNode) {
        const bpNames = breakpointNode.split(",").map((s) => s.trim()).filter(Boolean);
        for (const name of bpNames) {
          (labelToIds.get(name) ?? new Set()).forEach((id) => matchIds.add(id));
        }
      } else if (activeNode) {
        matchIds = labelToIds.get(activeNode.current) ?? new Set<string>();
      }

      return nds;
    });

    // 2) Highlight edges + collect target IDs for running mode
    setEdges((eds) =>
      eds.map((e) => {
        const srcPlain = e.source.includes("/") ? e.source.split("/").pop()! : e.source;
        const tgtPlain = e.target.includes("/") ? e.target.split("/").pop()! : e.target;

        const isActive = isPaused
          ? matchIds.has(tgtPlain)   // breakpoint: edges INTO paused node
          : matchIds.has(srcPlain);  // running: edges OUT of completed node

        if (isActive) {
          if (!isPaused) activeTargetIds.add(tgtPlain);
          return {
            ...e,
            style: { stroke: "var(--accent)", strokeWidth: 2.5 },
            markerEnd: { ...arrowMarker, color: "var(--accent)" },
            data: { ...e.data, highlighted: true },
            animated: true,
          };
        }

        if (e.data?.highlighted) {
          return {
            ...e,
            style: mkEdgeStyle((e as Edge & { data?: { conditional?: boolean } }).data?.conditional),
            markerEnd: arrowMarker,
            data: { ...e.data, highlighted: false },
            animated: false,
          };
        }

        return e;
      }),
    );

    // 3) Mark target nodes as active (running mode only; breakpoint uses isPausedHere)
    setNodes((nds) =>
      nds.map((n) => {
        if (n.type === "groupNode") return n;
        const plainId = n.id.includes("/") ? n.id.split("/").pop()! : n.id;
        const active = activeTargetIds.has(plainId);
        return active !== !!n.data?.isActiveNode
          ? { ...n, data: { ...n.data, isActiveNode: active } }
          : n;
      }),
    );
  }, [activeNode, breakpointNode, setNodes, setEdges]);

  const nodeStatusMap = useCallback(() => {
    const map: Record<string, string> = {};
    traces.forEach((t) => {
      const current = map[t.span_name];
      if (
        !current ||
        t.status === "failed" ||
        (t.status === "running" && current !== "failed")
      ) {
        map[t.span_name] = t.status;
      }
    });
    return map;
  }, [traces]);

  // Fetch graph data and run ELK layout
  useEffect(() => {
    const layoutId = ++layoutRef.current;
    setLoading(true);

    getEntrypointGraph(entrypoint)
      .then(async (graphData) => {
        if (layoutRef.current !== layoutId) return;
        const { nodes: laidNodes, edges: laidEdges } =
          await runElkLayout(graphData);
        if (layoutRef.current !== layoutId) return;
        // Inject persisted breakpoints into freshly laid-out nodes
        const curBp = useRunStore.getState().breakpoints[runId];
        const nodesWithBp = curBp
          ? laidNodes.map((n) => {
              if (n.type === "groupNode") return n;
              const plainId = n.id.includes("/") ? n.id.split("/").pop()! : n.id;
              return curBp[plainId] ? { ...n, data: { ...n.data, hasBreakpoint: true } } : n;
            })
          : laidNodes;
        setNodes(nodesWithBp);
        setEdges(laidEdges);
        // Fit view after nodes are rendered
        setTimeout(() => {
          rfInstance.current?.fitView({ padding: 0.1, duration: 200 });
        }, 100);
      })
      .catch(console.error)
      .finally(() => {
        if (layoutRef.current === layoutId) setLoading(false);
      });
  }, [entrypoint, setNodes, setEdges]);

  // Fit view when switching runs (even if entrypoint is the same)
  useEffect(() => {
    const t = setTimeout(() => {
      rfInstance.current?.fitView({ padding: 0.1, duration: 200 });
    }, 100);
    return () => clearTimeout(t);
  }, [runId]);

  // Update node status from traces
  useEffect(() => {
    const statusMap = nodeStatusMap();
    setNodes((nds) =>
      nds.map((n) => {
        if (n.type === "groupNode") {
          const label = n.data?.label as string | undefined;
          const status = label ? statusMap[label] : undefined;
          return status !== n.data?.status
            ? { ...n, data: { ...n.data, status } }
            : n;
        }
        const label = n.data?.label as string | undefined;
        const plainId = n.id.includes("/") ? n.id.split("/").pop()! : n.id;
        const status =
          (label ? statusMap[label] : undefined) ?? statusMap[plainId];
        return status !== n.data?.status
          ? { ...n, data: { ...n.data, status } }
          : n;
      }),
    );
  }, [nodeStatusMap, setNodes]);

  if (loading) {
    return (
      <div
        className="flex items-center justify-center h-full"
        style={{ color: "var(--text-muted)" }}
      >
        Loading graph...
      </div>
    );
  }

  return (
    <div className="h-full graph-panel">
      <style>{`
        .graph-panel .react-flow__handle {
          opacity: 0 !important;
          width: 0 !important;
          height: 0 !important;
          min-width: 0 !important;
          min-height: 0 !important;
          border: none !important;
          pointer-events: none !important;
        }
        .graph-panel .react-flow__edges {
          overflow: visible !important;
          z-index: 1 !important;
        }
        .graph-panel .react-flow__edge.animated path {
          stroke-dasharray: 8 4;
          animation: edge-flow 0.6s linear infinite;
        }
        @keyframes edge-flow {
          to { stroke-dashoffset: -12; }
        }
        @keyframes node-pulse {
          0%, 100% { box-shadow: 0 0 4px var(--accent); }
          50% { box-shadow: 0 0 10px var(--accent); }
        }
      `}</style>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onInit={(instance) => { rfInstance.current = instance; }}
        onNodeClick={onNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background color="var(--bg-tertiary)" gap={16} />
        <Controls showInteractive={false} />
        <Panel position="top-right">
          <button
            onClick={onToggleAllBreakpoints}
            title={hasAnyBreakpoint ? "Remove all breakpoints" : "Set breakpoints on all nodes"}
            style={{
              background: "var(--bg-secondary)",
              color: hasAnyBreakpoint ? "var(--error)" : "var(--text-muted)",
              border: `1px solid ${hasAnyBreakpoint ? "var(--error)" : "var(--node-border)"}`,
              borderRadius: 6,
              padding: "4px 10px",
              fontSize: 11,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: hasAnyBreakpoint ? "var(--error)" : "var(--node-border)",
            }} />
            {hasAnyBreakpoint ? "Clear all" : "Break all"}
          </button>
        </Panel>
        <MiniMap
          nodeColor={(n) => {
            if (n.type === "groupNode") return "var(--bg-tertiary)";
            const status = n.data?.status as string | undefined;
            if (status === "completed") return "var(--success)";
            if (status === "running") return "var(--warning)";
            if (status === "failed") return "var(--error)";
            return "var(--node-border)";
          }}
          nodeStrokeWidth={0}
          style={{ background: "var(--bg-secondary)", width: 120, height: 80 }}
        />
      </ReactFlow>
    </div>
  );
}
