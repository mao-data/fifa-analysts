import type { Shot } from '../lib/api'

/** Full-pitch shot map. StatsBomb records every shot attacking the right
 * goal on a 120x80 pitch; we mirror the away team's shots to the left goal
 * so the two sides read like a real match. Dot area encodes xG; goals are
 * filled, other outcomes hollow. */
export function ShotMap({ shots, home, away }: { shots: Shot[]; home: string; away: string }) {
  const W = 120
  const H = 80
  const r = (xg: number) => 1.2 + Math.sqrt(xg) * 4.5

  const place = (s: Shot) =>
    s.team === home ? { cx: s.x, cy: s.y } : { cx: W - s.x, cy: H - s.y }
  const color = (s: Shot) => (s.team === home ? 'var(--series-1)' : 'var(--series-6)')

  return (
    <div>
      <svg viewBox={`-2 -2 ${W + 4} ${H + 4}`} className="w-full" role="img"
        aria-label={`Shot map: ${home} attacking right, ${away} attacking left`}>
        {/* pitch chrome — hairline, recessive */}
        <g fill="none" stroke="var(--axis)" strokeWidth={0.4}>
          <rect x={0} y={0} width={W} height={H} />
          <line x1={W / 2} y1={0} x2={W / 2} y2={H} />
          <circle cx={W / 2} cy={H / 2} r={10} />
          {/* penalty areas + six-yard boxes, both ends */}
          <rect x={0} y={18} width={18} height={44} />
          <rect x={0} y={30} width={6} height={20} />
          <rect x={W - 18} y={18} width={18} height={44} />
          <rect x={W - 6} y={30} width={6} height={20} />
        </g>
        {shots.map((s, i) => {
          const { cx, cy } = place(s)
          const isGoal = s.outcome === 'Goal'
          return (
            <circle key={i} cx={cx} cy={cy} r={r(s.xg)}
              fill={isGoal ? color(s) : 'transparent'}
              stroke={color(s)} strokeWidth={isGoal ? 0.5 : 0.7}
              opacity={isGoal ? 1 : 0.55}>
              <title>
                {`${s.minute}' ${s.player} (${s.team}) — xG ${s.xg.toFixed(2)}, ${s.outcome}`}
              </title>
            </circle>
          )
        })}
      </svg>
      <div className="mt-2 flex flex-wrap gap-4 text-xs" style={{ color: 'var(--ink-2)' }}>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: 'var(--series-1)' }} />
          {home} (attacking →)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: 'var(--series-6)' }} />
          {away} (attacking ←)
        </span>
        <span style={{ color: 'var(--muted)' }}>
          Dot size = xG · filled = goal · hover a dot for details
        </span>
      </div>
    </div>
  )
}
