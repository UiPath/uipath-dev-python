import { useEffect, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type ReactFlowInstance,
} from "reactflow";
import "reactflow/dist/style.css";
import { getEntrypointGraph } from "../../api/client";
import { useRunStore } from "../../store/useRunStore";
import { runElkLayout } from "../graph/elkLayout";
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
  const [selectedEp, setSelectedEp] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [graphUnavailable, setGraphUnavailable] = useState(false);
  const layoutRef = useRef(0);
  const lastGraphHash = useRef<string>("");
  const rfInstance = useRef<ReactFlowInstance | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

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
            return "var(--node-border)";
          }}
          nodeStrokeWidth={0}
          style={{ background: "var(--bg-secondary)", width: 120, height: 80 }}
        />
      </ReactFlow>
    </div>
  );
}
