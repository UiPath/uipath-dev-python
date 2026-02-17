import { Handle, Position, type NodeProps } from "reactflow";
import MarchingBorder from "./MarchingBorder";

const invisibleHandle = {
  opacity: 0,
  width: 1,
  height: 1,
  minWidth: 0,
  minHeight: 0,
  border: "none",
  padding: 0,
};

/** Container node for subgraph children. */
export default function GroupNode({ data }: NodeProps) {
  const label = (data.label as string) ?? "";
  const status = data.status as string | undefined;
  const hasBreakpoint = data.hasBreakpoint as boolean | undefined;
  const isPausedHere = data.isPausedHere as boolean | undefined;
  const isActiveNode = data.isActiveNode as boolean | undefined;
  const isExecutingNode = data.isExecutingNode as boolean | undefined;

  const borderColor = isPausedHere
    ? "var(--error)"
    : isExecutingNode
      ? "var(--success)"
      : isActiveNode
        ? "transparent"
        : status === "completed"
          ? "var(--success)"
          : status === "running"
            ? "var(--warning)"
            : status === "failed"
              ? "var(--error)"
              : "var(--bg-tertiary)";

  const glowColor = isPausedHere ? "var(--error)" : isExecutingNode ? "var(--success)" : "var(--accent)";

  return (
    <div
      className="relative cursor-pointer"
      style={{
        width: "100%",
        height: "100%",
        background: "var(--bg-secondary)",
        border: `1.5px ${isPausedHere || isActiveNode || isExecutingNode ? "solid" : "dashed"} ${borderColor}`,
        borderRadius: 8,
        boxShadow: isPausedHere || isActiveNode || isExecutingNode ? `0 0 4px ${glowColor}` : undefined,
        animation: isPausedHere || isActiveNode || isExecutingNode ? `node-pulse-${isPausedHere ? "red" : isExecutingNode ? "green" : "accent"} 1.5s ease-in-out infinite` : undefined,
      }}
    >
      {hasBreakpoint && (
        <div
          className="absolute"
          style={{
            top: 4,
            left: 4,
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: "var(--error)",
            border: "2px solid var(--bg-tertiary)",
            boxShadow: "0 0 4px var(--error)",
            zIndex: 1,
          }}
        />
      )}
      {isActiveNode && <MarchingBorder strokeWidth={3} />}
      <Handle type="target" position={Position.Top} style={invisibleHandle} />
      <div
        style={{
          padding: "4px 10px",
          fontSize: 10,
          color: "var(--text-muted)",
          fontWeight: 600,
          textAlign: "center",
          borderBottom: `1px solid ${isActiveNode ? "var(--accent)" : borderColor}`,
          background: "var(--bg-tertiary)",
          borderRadius: "8px 8px 0 0",
        }}
      >
        {label}
      </div>
      <Handle type="source" position={Position.Bottom} style={invisibleHandle} />
    </div>
  );
}
