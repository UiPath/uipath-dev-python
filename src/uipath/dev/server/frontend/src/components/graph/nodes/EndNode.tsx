import { Handle, Position, type NodeProps } from "reactflow";

const hiddenHandle = {
  opacity: 0,
  width: 1,
  height: 1,
  minWidth: 0,
  minHeight: 0,
  border: "none",
  padding: 0,
};

export default function EndNode({ data }: NodeProps) {
  const status = data.status as string | undefined;
  const w = data.nodeWidth as number | undefined;
  const label = (data.label as string) ?? "End";
  const hasBreakpoint = data.hasBreakpoint as boolean | undefined;
  const isPausedHere = data.isPausedHere as boolean | undefined;
  const isActiveNode = data.isActiveNode as boolean | undefined;
  const isExecutingNode = data.isExecutingNode as boolean | undefined;

  const borderColor = isPausedHere
    ? "var(--accent)"
    : isExecutingNode
      ? "var(--success)"
      : isActiveNode
        ? "var(--accent)"
        : status === "completed"
          ? "var(--success)"
          : status === "failed"
            ? "var(--error)"
            : "var(--node-border)";

  const glowColor = isExecutingNode ? "var(--success)" : "var(--accent)";

  return (
    <div
      className="px-3 py-1.5 rounded-full text-center text-xs overflow-hidden text-ellipsis whitespace-nowrap cursor-pointer relative"
      style={{
        width: w,
        background: "var(--node-bg)",
        color: "var(--text-primary)",
        border: `2px solid ${borderColor}`,
        boxShadow: isPausedHere || isActiveNode || isExecutingNode ? `0 0 4px ${glowColor}` : undefined,
        animation: (isActiveNode || isExecutingNode) && !isPausedHere ? `node-pulse-${isExecutingNode ? "green" : "accent"} 1.5s ease-in-out infinite` : undefined,
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
      <Handle type="target" position={Position.Top} style={hiddenHandle} />
      {label}
    </div>
  );
}
