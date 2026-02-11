import { Handle, Position, type NodeProps } from "reactflow";

export default function DefaultNode({ data }: NodeProps) {
  const status = data.status as string | undefined;
  const w = data.nodeWidth as number | undefined;
  const label = (data.label as string) ?? "";

  const borderColor =
    status === "completed"
      ? "var(--success)"
      : status === "running"
        ? "var(--warning)"
        : status === "failed"
          ? "var(--error)"
          : "var(--node-border)";

  return (
    <div
      className="px-3 py-1.5 rounded-lg text-center text-xs overflow-hidden"
      style={{
        width: w,
        background: "var(--node-bg)",
        color: "var(--text-primary)",
        border: `1px solid ${borderColor}`,
      }}
      title={label}
    >
      <Handle type="target" position={Position.Top} />
      <div className="overflow-hidden text-ellipsis whitespace-nowrap">
        {label}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
