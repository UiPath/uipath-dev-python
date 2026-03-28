export default function MarchingBorder({ rx = 8, strokeWidth = 4 }: { rx?: number; strokeWidth?: number }) {
  return (
    <svg className="absolute inset-0 pointer-events-none" width="100%" height="100%">
      <rect
        x="0" y="0" width="100%" height="100%"
        rx={rx} fill="none"
        stroke="var(--accent)" strokeWidth={strokeWidth}
        strokeDasharray="8 4"
        style={{ animation: 'edge-flow 0.6s linear infinite' }}
      />
    </svg>
  );
}
