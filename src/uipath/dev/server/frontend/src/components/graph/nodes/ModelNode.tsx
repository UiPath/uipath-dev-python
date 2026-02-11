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

export default function ModelNode({ data }: NodeProps) {
  const status = data.status as string | undefined;
  const w = data.nodeWidth as number | undefined;
  const modelName = data.model_name as string | undefined;
  const label = (data.label as string) ?? "Model";

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
      <Handle type="target" position={Position.Top} style={hiddenHandle} />
      <div style={{ color: "var(--info)", fontSize: 9, marginBottom: 1 }}>model</div>
      <div className="overflow-hidden text-ellipsis whitespace-nowrap">{label}</div>
      {modelName && (
        <div
          className="overflow-hidden text-ellipsis whitespace-nowrap"
          style={{ color: "var(--text-muted)", fontSize: 9, marginTop: 1 }}
          title={modelName}
        >
          {modelName}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={hiddenHandle} />
    </div>
  );
}
