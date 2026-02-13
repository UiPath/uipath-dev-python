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
  const hasBreakpoint = data.hasBreakpoint as boolean | undefined;
  const isPausedHere = data.isPausedHere as boolean | undefined;
  const isActiveNode = data.isActiveNode as boolean | undefined;

  const borderColor = isPausedHere
    ? "var(--accent)"
    : isActiveNode
      ? "var(--accent)"
      : status === "completed"
        ? "var(--success)"
        : status === "running"
          ? "var(--warning)"
          : status === "failed"
            ? "var(--error)"
            : "var(--node-border)";

  return (
    <div
      className="px-3 py-1.5 rounded-lg text-center text-xs overflow-hidden cursor-pointer relative"
      style={{
        width: w,
        background: "var(--node-bg)",
        color: "var(--text-primary)",
        border: `2px solid ${borderColor}`,
        boxShadow: isPausedHere || isActiveNode ? "0 0 4px var(--accent)" : undefined,
        animation: isActiveNode && !isPausedHere ? "node-pulse 1.5s ease-in-out infinite" : undefined,
      }}
      title={modelName ? `${label}\n${modelName}` : label}
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
