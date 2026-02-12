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

  const borderColor = isPausedHere
    ? "var(--warning)"
    : status === "completed"
      ? "var(--success)"
      : status === "failed"
        ? "var(--error)"
        : "var(--node-border)";

  return (
    <div
      className="px-3 py-1.5 rounded-full text-center text-xs overflow-hidden text-ellipsis whitespace-nowrap cursor-pointer relative"
      style={{
        width: w,
        background: "var(--node-bg)",
        color: "var(--text-primary)",
        border: `2px solid ${borderColor}`,
        boxShadow: isPausedHere ? "0 0 8px var(--warning), 0 0 2px var(--warning)" : undefined,
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
