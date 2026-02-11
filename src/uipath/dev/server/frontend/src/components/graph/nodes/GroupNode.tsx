import { Handle, Position, type NodeProps } from "reactflow";

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

  const borderColor =
    status === "completed"
      ? "var(--success)"
      : status === "running"
        ? "var(--warning)"
        : status === "failed"
          ? "var(--error)"
          : "var(--bg-tertiary)";

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "var(--bg-secondary)",
        border: `1.5px dashed ${borderColor}`,
        borderRadius: 8,
      }}
    >
      <Handle type="target" position={Position.Top} style={invisibleHandle} />
      <div
        style={{
          padding: "4px 10px",
          fontSize: 10,
          color: "var(--text-muted)",
          fontWeight: 600,
          borderBottom: `1px solid ${borderColor}`,
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
