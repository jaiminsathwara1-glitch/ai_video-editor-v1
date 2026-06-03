/**
 * Circular score ring SVG — shows score 0-10 as a filled arc.
 */
export default function ScoreRing({ score, size = 48, strokeWidth = 4 }) {
  const r = (size - strokeWidth) / 2
  const circ = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(10, score ?? 0)) / 10
  const offset = circ * (1 - pct)

  const color =
    pct >= 0.7 ? '#22c55e' :
    pct >= 0.4 ? '#f59e0b' :
                 '#ef4444'

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Track */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none"
        stroke="#2e2e2e"
        strokeWidth={strokeWidth}
      />
      {/* Arc */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        style={{ transform: 'rotate(-90deg)', transformOrigin: 'center', transition: 'stroke-dashoffset 0.5s ease' }}
      />
      {/* Label */}
      <text
        x={size / 2} y={size / 2 + 4}
        textAnchor="middle"
        fill={color}
        fontSize={size * 0.26}
        fontWeight="600"
        fontFamily="Inter, sans-serif"
      >
        {score != null ? score.toFixed(1) : '—'}
      </text>
    </svg>
  )
}
