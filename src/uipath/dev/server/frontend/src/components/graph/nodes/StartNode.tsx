import { Handle, Position, type NodeProps } from "reactflow";
import MarchingBorder from "./MarchingBorder";

const hiddenHandle = {
  opacity: 0,
  width: 1,
  height: 1,
  minWidth: 0,
  minHeight: 0,
  border: "none",
  padding: 0,
};

export default function StartNode({ data }: NodeProps) {
  const status = data.status as string | undefined;
  const w = data.nodeWidth as number | undefined;
  const label = (data.label as string) ?? "Start";
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
            : "var(--node-border)";

  const glowColor = isPausedHere ? "var(--error)" : isExecutingNode ? "var(--success)" : "var(--accent)";

  return (
    <div
      className="px-3 py-1.5 rounded-full text-center text-xs overflow-hidden text-ellipsis whitespace-nowrap cursor-pointer relative"
      style={{
        width: w,
        background: "var(--node-bg)",
        color: "var(--text-primary)",
        border: `2px solid ${borderColor}`,
        boxShadow: isPausedHere || isActiveNode || isExecutingNode ? `0 0 4px ${glowColor}` : undefined,
        animation: isPausedHere || isActiveNode || isExecutingNode ? `node-pulse-${isPausedHere ? "red" : isExecutingNode ? "green" : "accent"} 1.5s ease-in-out infinite` : undefined,
      }}
      title={label}
    >
      {hasBreakpoint && (
        <div
          className="absolute"
          style={{
            top: 2,
            left: 2,
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: "var(--error)",
            border: "2px solid var(--node-bg)",
            boxShadow: "0 0 4px var(--error)",
          }}
        />
      )}
      {isActiveNode && <MarchingBorder rx={999} />}
      {label}
      <Handle type="source" position={Position.Bottom} style={hiddenHandle} />
    </div>
  );
}
