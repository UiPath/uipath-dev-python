import { BaseEdge, type EdgeProps } from "reactflow";

export interface ElkEdgeData {
  sourcePoint: { x: number; y: number };
  targetPoint: { x: number; y: number };
  bendPoints: { x: number; y: number }[];
  highlighted?: boolean;
}

/** Build an SVG path with rounded corners at bend points. */
function buildRoundedPath(
  points: { x: number; y: number }[],
  radius = 8,
): string {
  if (points.length < 2) return "";
  if (points.length === 2) {
    return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`;
  }

  let d = `M ${points[0].x} ${points[0].y}`;

  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1];
    const curr = points[i];
    const next = points[i + 1];

    const dx1 = curr.x - prev.x;
    const dy1 = curr.y - prev.y;
    const dx2 = next.x - curr.x;
    const dy2 = next.y - curr.y;

    const len1 = Math.hypot(dx1, dy1);
    const len2 = Math.hypot(dx2, dy2);

    if (len1 === 0 || len2 === 0) {
      d += ` L ${curr.x} ${curr.y}`;
      continue;
    }

    const r = Math.min(radius, len1 / 2, len2 / 2);

    const bx = curr.x - (dx1 / len1) * r;
    const by = curr.y - (dy1 / len1) * r;
    const ax = curr.x + (dx2 / len2) * r;
    const ay = curr.y + (dy2 / len2) * r;

    d += ` L ${bx} ${by} Q ${curr.x} ${curr.y} ${ax} ${ay}`;
  }

  const last = points[points.length - 1];
  d += ` L ${last.x} ${last.y}`;
  return d;
}

export default function ElkEdge({
  data,
  style,
  markerEnd,
  label,
  labelStyle,
  labelBgStyle,
  sourceX,
  sourceY,
  targetX,
  targetY,
}: EdgeProps<ElkEdgeData>) {
  let pathD: string;
  let labelX: number;
  let labelY: number;

  if (data?.sourcePoint && data?.targetPoint) {
    const points = [
      data.sourcePoint,
      ...(data.bendPoints ?? []),
      data.targetPoint,
    ];
    pathD = buildRoundedPath(points);
    const mid = points[Math.floor(points.length / 2)];
    labelX = mid.x;
    labelY = mid.y;
  } else {
    pathD = `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`;
    labelX = (sourceX + targetX) / 2;
    labelY = (sourceY + targetY) / 2;
  }

  return (
    <BaseEdge
      path={pathD}
      style={style}
      markerEnd={markerEnd}
      label={label}
      labelX={labelX}
      labelY={labelY}
      labelStyle={labelStyle}
      labelBgStyle={labelBgStyle}
      labelShowBg={!!label}
      labelBgPadding={[4, 2]}
      labelBgBorderRadius={3}
    />
  );
}
