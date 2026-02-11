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

export default function StartNode({ data }: NodeProps) {
  const status = data.status as string | undefined;
  const w = data.nodeWidth as number | undefined;
  const label = (data.label as string) ?? "Start";

  const borderColor =
    status === "completed"
      ? "var(--success)"
      : status === "running"
        ? "var(--warning)"
        : "var(--node-border)";

  return (
    <div
      className="px-3 py-1.5 rounded-full text-center text-xs overflow-hidden text-ellipsis whitespace-nowrap"
      style={{
        width: w,
        background: "var(--node-bg)",
        color: "var(--text-primary)",
        border: `2px solid ${borderColor}`,
      }}
      title={label}
    >
      {label}
      <Handle type="source" position={Position.Bottom} style={hiddenHandle} />
    </div>
  );
}
