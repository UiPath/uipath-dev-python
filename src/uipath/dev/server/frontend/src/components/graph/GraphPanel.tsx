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
import type { ElkNode, ElkExtendedEdge } from "elkjs/lib/elk.bundled.js";
import type ELKType from "elkjs/lib/elk.bundled.js";
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
const BASE_NODE_HEIGHT = 32; // 2(border) + 6(py) + 16(text-xs) + 6(py) + 2(border)
const TYPE_LABEL_HEIGHT = 13; // fontSize 9 (~11px line) + marginBottom 1

function computeNodeWidth(data: Record<string, unknown>): number {
  const label = (data?.label as string) ?? "";
  // No hard cap — let ELK handle spacing; nodes must fit their labels
  return Math.max(MIN_NODE_WIDTH, label.length * 8 + 32);
}

function computeNodeHeight(
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

// ─── Component ───────────────────────────────────────────────────────
interface Props {
  entrypoint: string;
  traces: TraceSpan[];
  runId: string;
  breakpointNode?: string | null;
  breakpointNextNodes?: string[];
  onBreakpointChange?: (breakpoints: string[]) => void;
  fitViewTrigger?: number;
}

export default function GraphPanel({ entrypoint, runId, breakpointNode, breakpointNextNodes, onBreakpointChange, fitViewTrigger }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [graphUnavailable, setGraphUnavailable] = useState(false);
  const [layoutSeq, setLayoutSeq] = useState(0);
  const layoutRef = useRef(0);
  const rfInstance = useRef<ReactFlowInstance | null>(null);

  const bpMap = useRunStore((s) => s.breakpoints[runId]);
  const toggleBreakpoint = useRunStore((s) => s.toggleBreakpoint);
  const clearBreakpoints = useRunStore((s) => s.clearBreakpoints);
  const activeNode = useRunStore((s) => s.activeNodes[runId]);
  const runStatus = useRunStore((s) => s.runs[runId]?.status);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.type === "startNode" || node.type === "endNode") return;
      // For compound children, extract the plain ID from "parentId/childId"
      // For group nodes (subgraphs), use the node ID directly
      const plainId = node.type === "groupNode" ? node.id : node.id.includes("/") ? node.id.split("/").pop()! : node.id;
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
      // Set breakpoints on all non-start, non-end, non-subgraph-child nodes
      const nodeIds: string[] = [];
      for (const n of nodes) {
        if (n.type === "startNode" || n.type === "endNode") continue;
        if (n.parentNode) continue; // skip subgraph children — use the group node instead
        const plainId = n.type === "groupNode" ? n.id : n.id.includes("/") ? n.id.split("/").pop()! : n.id;
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
        if (n.type === "startNode" || n.type === "endNode") return n;
        const plainId = n.type === "groupNode" ? n.id : n.id.includes("/") ? n.id.split("/").pop()! : n.id;
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
        if (n.type === "startNode" || n.type === "endNode") return n;
        const plainId = n.type === "groupNode" ? n.id : n.id.includes("/") ? n.id.split("/").pop()! : n.id;
        const label = n.data?.label as string | undefined;
        const paused = bpNames != null && (bpNames.has(plainId) || (label != null && bpNames.has(label)));
        return paused !== !!n.data?.isPausedHere
          ? { ...n, data: { ...n.data, isPausedHere: paused } }
          : n;
      }),
    );
  }, [breakpointNode, layoutSeq, setNodes]);

  // Highlight edges + nodes during execution
  // - Paused at breakpoint: edges INTO breakpoint node + edges to next_nodes
  // - Running: edges OUT of completed node, target nodes of those edges
  // - __start__: highlighted on first state event; __end__: highlighted when run completes
  useEffect(() => {
    const isPaused = !!breakpointNode;
    let matchIds = new Set<string>(); // Full React Flow node IDs of the "current" node
    const prevNodeIds = new Set<string>(); // Full RF IDs of the previous node (for edge filtering when paused)
    const nextNodeIds = new Set<string>(); // Full RF IDs of breakpoint next_nodes
    const activeTargetIds = new Set<string>(); // Full RF IDs for isActiveNode
    const nodeTypeById = new Map<string, string>();

    // 1) Build matchIds, nextNodeIds, node type map
    setNodes((nds) => {
      for (const n of nds) {
        if (n.type) nodeTypeById.set(n.id, n.type);
      }

      // Helper: find full RF node ID(s) matching a plain name
      const findNodeIds = (name: string): string[] => {
        const result: string[] = [];
        for (const n of nds) {
          const plainId = n.type === "groupNode" ? n.id : n.id.includes("/") ? n.id.split("/").pop()! : n.id;
          const label = n.data?.label as string | undefined;
          if (plainId === name || (label != null && label === name)) {
            result.push(n.id);
          }
        }
        return result;
      };

      if (isPaused && breakpointNode) {
        const bpNames = breakpointNode.split(",").map((s) => s.trim()).filter(Boolean);
        for (const name of bpNames) {
          findNodeIds(name).forEach((id) => matchIds.add(id));
        }
        // Resolve next_nodes to full RF IDs
        if (breakpointNextNodes?.length) {
          for (const name of breakpointNextNodes) {
            findNodeIds(name).forEach((id) => nextNodeIds.add(id));
          }
        }
        // Resolve previous node so we only highlight the incoming edge from it
        if (activeNode?.prev) {
          findNodeIds(activeNode.prev).forEach((id) => prevNodeIds.add(id));
        }
      } else if (activeNode) {
        // Try qualified name first (exact match via "subgraph:node" → "subgraph/node")
        const qualifiedName = activeNode.qualifiedNodeName;
        if (qualifiedName) {
          const qualifiedId = qualifiedName.replace(/:/g, "/");
          for (const n of nds) {
            if (n.id === qualifiedId) {
              matchIds.add(n.id);
            }
          }
        }
        // Fallback: label/plainId matching
        if (matchIds.size === 0) {
          const labelToIds = new Map<string, Set<string>>();
          for (const n of nds) {
            const label = n.data?.label as string | undefined;
            if (!label) continue;
            const plainId = n.id.includes("/") ? n.id.split("/").pop()! : n.id;
            for (const key of [plainId, label]) {
              let s = labelToIds.get(key);
              if (!s) { s = new Set(); labelToIds.set(key, s); }
              s.add(n.id);
            }
          }
          matchIds = labelToIds.get(activeNode.current) ?? new Set<string>();
        }

      }

      return nds;
    });

    // 2) Highlight edges
    setEdges((eds) => {
      // Check if prev node actually has a direct edge into the breakpoint node.
      // If not (e.g. prev is a sibling child of the same parent), fall back to
      // highlighting all incoming edges to the breakpoint node.
      const prevHasDirectEdge = prevNodeIds.size === 0
        || eds.some((e) => matchIds.has(e.target) && prevNodeIds.has(e.source));

      return eds.map((e) => {
        let isActive: boolean;
        if (isPaused) {
          const intoBreakpoint = matchIds.has(e.target)
            && (prevNodeIds.size === 0 || !prevHasDirectEdge || prevNodeIds.has(e.source));
          isActive = intoBreakpoint
            || (matchIds.has(e.source) && nextNodeIds.has(e.target));
        } else {
          // Running: edges OUT of completed node
          isActive = matchIds.has(e.source);
          // For __end__: also highlight edges INTO it
          if (!isActive && nodeTypeById.get(e.target) === "endNode" && matchIds.has(e.target)) {
            isActive = true;
          }
        }

        if (isActive) {
          if (!isPaused) activeTargetIds.add(e.target);
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
      });
    });

    // 3) Mark nodes as active
    // - Running: targets of highlighted edges + __start__/__end__ when matched
    // - Paused: next_nodes get isActiveNode (about to execute)
    // - Executing: matchIds get isExecutingNode (currently running node, green glow)
    setNodes((nds) =>
      nds.map((n) => {
        const executing = !isPaused && matchIds.has(n.id);
        if (n.type === "startNode" || n.type === "endNode") {
          const active = activeTargetIds.has(n.id) || (!isPaused && matchIds.has(n.id));
          return active !== !!n.data?.isActiveNode || executing !== !!n.data?.isExecutingNode
            ? { ...n, data: { ...n.data, isActiveNode: active, isExecutingNode: executing } }
            : n;
        }
        const active = isPaused
          ? nextNodeIds.has(n.id)
          : activeTargetIds.has(n.id);
        return active !== !!n.data?.isActiveNode || executing !== !!n.data?.isExecutingNode
          ? { ...n, data: { ...n.data, isActiveNode: active, isExecutingNode: executing } }
          : n;
      }),
    );
  }, [activeNode, breakpointNode, breakpointNextNodes, runStatus, layoutSeq, setNodes, setEdges]);

  const stateEvents = useRunStore((s) => s.stateEvents[runId]);

  // Subscribe to cached graph reactively (populated async from run detail)
  const cachedGraph = useRunStore((s) => s.graphCache[runId]);

  // Fetch graph data and run ELK layout
  useEffect(() => {
    // For non-setup runs, wait for cache to be populated from run detail
    if (!cachedGraph && runId !== "__setup__") return;

    const graphPromise = cachedGraph
      ? Promise.resolve(cachedGraph)
      : getEntrypointGraph(entrypoint);

    const layoutId = ++layoutRef.current;
    setLoading(true);
    setGraphUnavailable(false);

    graphPromise
      .then(async (graphData) => {
        if (layoutRef.current !== layoutId) return;
        if (!graphData.nodes.length) {
          setGraphUnavailable(true);
          return;
        }
        const { nodes: laidNodes, edges: laidEdges } =
          await runElkLayout(graphData);
        if (layoutRef.current !== layoutId) return;
        // Inject persisted breakpoints into freshly laid-out nodes
        const curBp = useRunStore.getState().breakpoints[runId];
        const nodesWithBp = curBp
          ? laidNodes.map((n) => {
              if (n.type === "startNode" || n.type === "endNode") return n;
              const plainId = n.type === "groupNode" ? n.id : n.id.includes("/") ? n.id.split("/").pop()! : n.id;
              return curBp[plainId] ? { ...n, data: { ...n.data, hasBreakpoint: true } } : n;
            })
          : laidNodes;
        setNodes(nodesWithBp);
        setEdges(laidEdges);
        setLayoutSeq((s) => s + 1);
        // Fit view after nodes are rendered
        setTimeout(() => {
          rfInstance.current?.fitView({ padding: 0.1, duration: 200 });
        }, 100);
      })
      .catch(() => {
        if (layoutRef.current === layoutId) setGraphUnavailable(true);
      })
      .finally(() => {
        if (layoutRef.current === layoutId) setLoading(false);
      });
  }, [entrypoint, runId, cachedGraph, setNodes, setEdges]);

  // Fit view when switching runs (even if entrypoint is the same)
  useEffect(() => {
    const t = setTimeout(() => {
      rfInstance.current?.fitView({ padding: 0.1, duration: 200 });
    }, 100);
    return () => clearTimeout(t);
  }, [runId]);

  // Fit view when parent container is resized (drag handles)
  useEffect(() => {
    if (fitViewTrigger) {
      rfInstance.current?.fitView({ padding: 0.1, duration: 200 });
    }
  }, [fitViewTrigger]);

  // Update node status from state events (uses qualified_node_name for precise subgraph matching)
  useEffect(() => {
    setNodes((nds) => {
      const hasEvents = !!stateEvents?.length;
      const isTerminal = runStatus === "completed" || runStatus === "failed";

      // Build set of completed React Flow node IDs from state events
      const completedIds = new Set<string>();
      const allNodeIds = new Set(nds.map((n) => n.id));
      const labelToIds = new Map<string, Set<string>>();
      for (const n of nds) {
        const label = n.data?.label as string | undefined;
        if (!label) continue;
        const plainId = n.id.includes("/") ? n.id.split("/").pop()! : n.id;
        for (const key of [plainId, label]) {
          let s = labelToIds.get(key);
          if (!s) { s = new Set(); labelToIds.set(key, s); }
          s.add(n.id);
        }
      }

      if (hasEvents) {
        for (const evt of stateEvents) {
          let matched = false;
          if (evt.qualified_node_name) {
            const qId = evt.qualified_node_name.replace(/:/g, "/");
            if (allNodeIds.has(qId)) {
              completedIds.add(qId);
              matched = true;
            }
          }
          if (!matched) {
            const ids = labelToIds.get(evt.node_name);
            if (ids) ids.forEach((id) => completedIds.add(id));
          }
        }
      }

      // Track which subgraphs were actually visited
      const visitedParents = new Set<string>();
      for (const n of nds) {
        if (n.parentNode && completedIds.has(n.id)) {
          visitedParents.add(n.parentNode);
        }
      }

      // When run failed and no nodes were highlighted, mark the root node as failed
      let failedRootId: string | undefined;
      if (runStatus === "failed" && completedIds.size === 0) {
        failedRootId = nds.find((n) => !n.parentNode && n.type !== "startNode" && n.type !== "endNode" && n.type !== "groupNode")?.id;
      }

      // When run completed and root node is not already highlighted, mark it as completed
      let completedRootId: string | undefined;
      if (runStatus === "completed") {
        const rootId = nds.find((n) => !n.parentNode && n.type !== "startNode" && n.type !== "endNode" && n.type !== "groupNode")?.id;
        if (rootId && !completedIds.has(rootId)) {
          completedRootId = rootId;
        }
      }

      return nds.map((n) => {
        let status: string | undefined;

        if (n.id === failedRootId) {
          status = "failed";
        } else if (n.id === completedRootId) {
          status = "completed";
        } else if (completedIds.has(n.id)) {
          status = "completed";
        } else if (n.type === "startNode") {
          // Top-level: completed once execution begins; subgraph: only if visited
          if (!n.parentNode && hasEvents) status = "completed";
          else if (n.parentNode && visitedParents.has(n.parentNode)) status = "completed";
        } else if (n.type === "endNode") {
          // Top-level: completed when run finishes; subgraph: as soon as visited
          if (!n.parentNode && isTerminal) {
            status = runStatus === "failed" ? "failed" : "completed";
          } else if (n.parentNode && visitedParents.has(n.parentNode)) {
            status = "completed";
          }
        } else if (n.type === "groupNode") {
          // Group is completed if any child completed
          if (visitedParents.has(n.id)) status = "completed";
        }

        return status !== n.data?.status
          ? { ...n, data: { ...n.data, status } }
          : n;
      });
    });
    // layoutSeq ensures this re-runs after graph layout completes
  }, [stateEvents, runStatus, layoutSeq, setNodes]);

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

  if (graphUnavailable) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full gap-4"
        style={{ color: "var(--text-muted)" }}
      >
        <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
          {/* Top node */}
          <rect x="38" y="10" width="44" height="24" rx="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.4" />
          <line x1="60" y1="34" x2="60" y2="46" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          {/* Middle-left node */}
          <rect x="12" y="46" width="44" height="24" rx="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          {/* Middle-right node */}
          <rect x="64" y="46" width="44" height="24" rx="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          {/* Lines from top to middle nodes */}
          <line x1="60" y1="46" x2="34" y2="46" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="60" y1="46" x2="86" y2="46" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          {/* Lines from middle to bottom */}
          <line x1="34" y1="70" x2="34" y2="82" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="86" y1="70" x2="86" y2="82" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          {/* Converge lines */}
          <line x1="34" y1="82" x2="60" y2="82" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="86" y1="82" x2="60" y2="82" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="60" y1="82" x2="60" y2="86" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          {/* Bottom node */}
          <rect x="38" y="86" width="44" height="24" rx="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.4" />
        </svg>
        <span className="text-xs">No graph schema available</span>
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
        @keyframes node-pulse-accent {
          0%, 100% { box-shadow: 0 0 4px var(--accent); }
          50% { box-shadow: 0 0 10px var(--accent); }
        }
        @keyframes node-pulse-green {
          0%, 100% { box-shadow: 0 0 4px var(--success); }
          50% { box-shadow: 0 0 10px var(--success); }
        }
        @keyframes node-pulse-red {
          0%, 100% { box-shadow: 0 0 4px var(--error); }
          50% { box-shadow: 0 0 10px var(--error); }
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
              fontSize: 12,
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
