import { useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Edge,
  type ReactFlowInstance,
} from "reactflow";
import "reactflow/dist/style.css";
import { getEntrypointGraph } from "../../api/client";
import { useRunStore } from "../../store/useRunStore";
import { getWs } from "../../store/useWebSocket";
import { runElkLayout, arrowMarker, mkEdgeStyle } from "../graph/elkLayout";
import StartNode from "../graph/nodes/StartNode";
import EndNode from "../graph/nodes/EndNode";
import ModelNode from "../graph/nodes/ModelNode";
import ToolNode from "../graph/nodes/ToolNode";
import GroupNode from "../graph/nodes/GroupNode";
import DefaultNode from "../graph/nodes/DefaultNode";
import ElkEdge from "../graph/edges/ElkEdge";

const nodeTypes = {
  startNode: StartNode,
  endNode: EndNode,
  modelNode: ModelNode,
  toolNode: ToolNode,
  groupNode: GroupNode,
  defaultNode: DefaultNode,
};

const edgeTypes = { elk: ElkEdge };

export default function ExplorerCanvas() {
  const entrypoints = useRunStore((s) => s.entrypoints);
  const runs = useRunStore((s) => s.runs);
  const [selectedEp, setSelectedEp] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [graphUnavailable, setGraphUnavailable] = useState(false);
  const layoutRef = useRef(0);
  const lastGraphHash = useRef<string>("");
  const rfInstance = useRef<ReactFlowInstance | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const ws = useRef(getWs()).current;

  // Find the latest active or most recent run for selected entrypoint
  const activeRunId = useMemo(() => {
    if (!selectedEp) return null;
    let best: { id: string; start_time: string | null } | null = null;
    for (const r of Object.values(runs)) {
      if (r.entrypoint !== selectedEp) continue;
      // Prefer running/pending runs
      if (r.status === "running" || r.status === "pending") return r.id;
      // Otherwise pick the most recent by start_time
      if (!best || (r.start_time && (!best.start_time || r.start_time > best.start_time))) {
        best = r;
      }
    }
    return best?.id ?? null;
  }, [runs, selectedEp]);

  // Subscribe to the active run's WebSocket events
  useEffect(() => {
    if (!activeRunId) return;
    ws.subscribe(activeRunId);
    return () => { ws.unsubscribe(activeRunId); };
  }, [activeRunId, ws]);

  const stateEvents = useRunStore((s) => activeRunId ? s.stateEvents[activeRunId] : undefined);
  const runStatus = useRunStore((s) => activeRunId ? s.runs[activeRunId]?.status : undefined);

  // Auto-select first entrypoint
  useEffect(() => {
    if (entrypoints.length > 0 && (!selectedEp || !entrypoints.includes(selectedEp))) {
      setSelectedEp(entrypoints[0]);
    }
  }, [entrypoints, selectedEp]);

  // Fetch graph and run ELK layout when entrypoint changes or entrypoints refresh
  useEffect(() => {
    if (!selectedEp) return;

    const layoutId = ++layoutRef.current;
    // Only show loading spinner on first load (no graph rendered yet)
    const isFirstLoad = !lastGraphHash.current;
    if (isFirstLoad) setLoading(true);
    setGraphUnavailable(false);

    getEntrypointGraph(selectedEp)
      .then(async (graphData) => {
        if (layoutRef.current !== layoutId) return;
        if (!graphData.nodes.length) {
          setGraphUnavailable(true);
          return;
        }
        // Skip re-layout if the graph structure hasn't changed
        const hash = JSON.stringify(graphData);
        if (hash === lastGraphHash.current) {
          return;
        }
        lastGraphHash.current = hash;
        const { nodes: laidNodes, edges: laidEdges } =
          await runElkLayout(graphData);
        if (layoutRef.current !== layoutId) return;
        setNodes(laidNodes);
        setEdges(laidEdges);
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
  }, [selectedEp, entrypoints, setNodes, setEdges]);

  // --- Execution highlighting (mirrors GraphPanel logic, no breakpoints) ---

  // Highlight edges + nodes during execution
  useEffect(() => {
    if (!activeRunId) return;

    // Derive currently-executing nodes from event log
    const executingNodes = new Map<string, string | null>();
    if (stateEvents) {
      for (const evt of stateEvents) {
        if (evt.phase === "started") {
          executingNodes.set(evt.node_name, evt.qualified_node_name ?? null);
        } else if (evt.phase === "completed") {
          executingNodes.delete(evt.node_name);
        }
      }
    }

    let matchIds = new Set<string>();
    const activeTargetIds = new Set<string>();
    const nodeTypeById = new Map<string, string>();

    setNodes((nds) => {
      for (const n of nds) {
        if (n.type) nodeTypeById.set(n.id, n.type);
      }

      if (executingNodes.size > 0) {
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

        for (const [nodeName, qualifiedNodeName] of executingNodes) {
          let found = false;
          if (qualifiedNodeName) {
            const qualifiedId = qualifiedNodeName.replace(/:/g, "/");
            for (const n of nds) {
              if (n.id === qualifiedId) { matchIds.add(n.id); found = true; }
            }
          }
          if (!found) {
            const ids = labelToIds.get(nodeName);
            if (ids) ids.forEach((id) => matchIds.add(id));
          }
        }
      }

      return nds;
    });

    // Highlight edges
    setEdges((eds) =>
      eds.map((e) => {
        let isActive = matchIds.has(e.source);
        if (!isActive && nodeTypeById.get(e.target) === "endNode" && matchIds.has(e.target)) {
          isActive = true;
        }

        if (isActive) {
          activeTargetIds.add(e.target);
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

    // Mark executing + active nodes
    setNodes((nds) =>
      nds.map((n) => {
        const executing = matchIds.has(n.id);
        const active = activeTargetIds.has(n.id) || matchIds.has(n.id);
        return active !== !!n.data?.isActiveNode || executing !== !!n.data?.isExecutingNode
          ? { ...n, data: { ...n.data, isActiveNode: active, isExecutingNode: executing } }
          : n;
      }),
    );
  }, [activeRunId, stateEvents, setNodes, setEdges]);

  // Update node completion status from state events
  useEffect(() => {
    if (!activeRunId) return;

    setNodes((nds) => {
      const hasEvents = !!stateEvents?.length;
      const isTerminal = runStatus === "completed" || runStatus === "failed";

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
            if (allNodeIds.has(qId)) { completedIds.add(qId); matched = true; }
          }
          if (!matched) {
            const ids = labelToIds.get(evt.node_name);
            if (ids) ids.forEach((id) => completedIds.add(id));
          }
        }
      }

      const visitedParents = new Set<string>();
      for (const n of nds) {
        if (n.parentNode && completedIds.has(n.id)) visitedParents.add(n.parentNode);
      }

      return nds.map((n) => {
        let status: string | undefined;

        if (completedIds.has(n.id)) {
          status = "completed";
        } else if (n.type === "startNode") {
          if (!n.parentNode && hasEvents) status = "completed";
          else if (n.parentNode && visitedParents.has(n.parentNode)) status = "completed";
        } else if (n.type === "endNode") {
          if (!n.parentNode && isTerminal) status = runStatus === "failed" ? "failed" : "completed";
          else if (n.parentNode && visitedParents.has(n.parentNode)) status = "completed";
        } else if (n.type === "groupNode") {
          if (visitedParents.has(n.id)) status = "completed";
        }

        return status !== n.data?.status
          ? { ...n, data: { ...n.data, status } }
          : n;
      });
    });
  }, [activeRunId, stateEvents, runStatus, setNodes]);

  // Fit view on container resize
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      rfInstance.current?.fitView({ padding: 0.1, duration: 200 });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [loading, graphUnavailable]);

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
          <rect x="38" y="10" width="44" height="24" rx="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.4" />
          <line x1="60" y1="34" x2="60" y2="46" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <rect x="12" y="46" width="44" height="24" rx="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <rect x="64" y="46" width="44" height="24" rx="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="60" y1="46" x2="34" y2="46" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="60" y1="46" x2="86" y2="46" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="34" y1="70" x2="34" y2="82" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="86" y1="70" x2="86" y2="82" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="34" y1="82" x2="60" y2="82" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="86" y1="82" x2="60" y2="82" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <line x1="60" y1="82" x2="60" y2="86" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.3" />
          <rect x="38" y="86" width="44" height="24" rx="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.4" />
        </svg>
        <span className="text-xs">No graph schema available</span>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full explorer-canvas">
      <style>{`
        .explorer-canvas .react-flow__handle {
          opacity: 0 !important;
          width: 0 !important;
          height: 0 !important;
          min-width: 0 !important;
          min-height: 0 !important;
          border: none !important;
          pointer-events: none !important;
        }
        .explorer-canvas .react-flow__edges {
          overflow: visible !important;
          z-index: 1 !important;
        }
        .explorer-canvas .react-flow__edge.animated path {
          stroke-dasharray: 8 4;
          animation: explorer-edge-flow 0.6s linear infinite;
        }
        @keyframes explorer-edge-flow {
          to { stroke-dashoffset: -12; }
        }
      `}</style>
      {entrypoints.length > 1 && (
        <div style={{
          position: "absolute",
          top: 8,
          left: 8,
          zIndex: 10,
        }}>
          <select
            value={selectedEp ?? ""}
            onChange={(e) => setSelectedEp(e.target.value)}
            style={{
              background: "var(--bg-secondary)",
              color: "var(--text-primary)",
              border: "1px solid var(--node-border)",
              borderRadius: 6,
              padding: "4px 8px",
              fontSize: 12,
            }}
          >
            {entrypoints.map((ep) => (
              <option key={ep} value={ep}>{ep}</option>
            ))}
          </select>
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onInit={(instance) => { rfInstance.current = instance; }}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background color="var(--bg-tertiary)" gap={16} />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) => {
            if (n.type === "groupNode") return "var(--bg-tertiary)";
            const status = n.data?.status as string | undefined;
            if (status === "completed") return "var(--success)";
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
