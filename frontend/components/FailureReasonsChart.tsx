type Reason = { reason: string; count: number };

export default function FailureReasonsChart({ reasons }: { reasons: Reason[] }) {
  if (reasons.length === 0) return null;
  const max = Math.max(...reasons.map((r) => r.count));
  const rowHeight = 30;
  const height = reasons.length * rowHeight + 8;

  return (
    <svg width="100%" height={height} viewBox={`0 0 400 ${height}`} preserveAspectRatio="none">
      {reasons.map((r, i) => {
        const barWidth = max > 0 ? (r.count / max) * 220 : 0;
        const y = i * rowHeight;
        return (
          <g key={r.reason}>
            <text
              x="0"
              y={y + rowHeight / 2}
              dominantBaseline="middle"
              className="fill-muted"
              style={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11 }}
            >
              {r.reason.replaceAll("_", " ")}
            </text>
            <rect
              x="150"
              y={y + 6}
              width={Math.max(barWidth, 3)}
              height={rowHeight - 14}
              rx="3"
              fill="#7B3B49"
              opacity={0.85}
            />
            <text
              x={150 + Math.max(barWidth, 3) + 8}
              y={y + rowHeight / 2}
              dominantBaseline="middle"
              className="fill-ink"
              style={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11, fontWeight: 600 }}
            >
              {r.count}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
