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

  const borderColor =
    status === "completed"
      ? "var(--success)"
      : status === "failed"
        ? "var(--error)"
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
      <Handle type="target" position={Position.Top} style={hiddenHandle} />
      {label}
    </div>
  );
}
