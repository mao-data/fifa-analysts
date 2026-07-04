import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'

const AXIS_TICK = { fill: 'var(--muted)', fontSize: 11 }

function ChartTooltip({ active, payload, label, unit }: {
  active?: boolean
  payload?: { name?: string; value?: number | string; color?: string }[]
  label?: string | number
  unit?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-xs shadow-sm">
      <div style={{ color: 'var(--muted)' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="mt-0.5 flex items-center gap-2">
          <span className="inline-block h-0.5 w-3" style={{ background: p.color }} />
          <span className="font-semibold tabular">{p.value}{unit}</span>
          <span style={{ color: 'var(--ink-2)' }}>{p.name}</span>
        </div>
      ))}
    </div>
  )
}

export function EloTrendChart({ series }: {
  series: { name: string; color: string; data: { date: string; elo: number }[] }[]
}) {
  // Merge on date for a single-readout tooltip across series.
  const byDate = new Map<string, Record<string, number | string>>()
  for (const s of series) {
    for (const p of s.data) {
      const row = byDate.get(p.date) ?? { date: p.date }
      row[s.name] = p.elo
      byDate.set(p.date, row)
    }
  }
  const data = [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)))
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grid)" strokeWidth={1} vertical={false} />
        <XAxis dataKey="date" tick={AXIS_TICK} stroke="var(--axis)" tickLine={false}
          minTickGap={60} />
        <YAxis tick={AXIS_TICK} stroke="var(--axis)" tickLine={false} axisLine={false}
          domain={['auto', 'auto']} width={44} />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--axis)', strokeWidth: 1 }} />
        {series.map((s) => (
          <Line key={s.name} type="monotone" dataKey={s.name} stroke={s.color}
            strokeWidth={2} dot={false} connectNulls
            activeDot={{ r: 4, stroke: 'var(--surface-1)', strokeWidth: 2 }} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

export function GoalsDistChart({ data }: { data: { goals: number; matches: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap="25%">
        <CartesianGrid stroke="var(--grid)" strokeWidth={1} vertical={false} />
        <XAxis dataKey="goals" tick={AXIS_TICK} stroke="var(--axis)" tickLine={false} />
        <YAxis tick={AXIS_TICK} stroke="var(--axis)" tickLine={false} axisLine={false} width={40} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--grid)', opacity: 0.4 }} />
        <Bar dataKey="matches" name="matches" fill="var(--series-1)"
          radius={[4, 4, 0, 0]} maxBarSize={24} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Horizontal 3-segment probability bar with 2px surface gaps and a legend. */
export function ProbBar({ segments }: {
  segments: { label: string; value: number; color: string }[]
}) {
  return (
    <div>
      <div className="flex h-8 w-full overflow-hidden rounded-lg"
        style={{ background: 'var(--surface-1)', gap: 2 }}
        role="img"
        aria-label={segments.map((s) => `${s.label} ${(s.value * 100).toFixed(1)}%`).join(', ')}>
        {segments.map((s) => (
          <div key={s.label} title={`${s.label}: ${(s.value * 100).toFixed(1)}%`}
            className="flex items-center justify-center rounded-sm text-xs font-semibold text-white"
            style={{ width: `${s.value * 100}%`, background: s.color, minWidth: 2 }}>
            {s.value >= 0.12 ? `${(s.value * 100).toFixed(0)}%` : ''}
          </div>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-4 text-xs" style={{ color: 'var(--ink-2)' }}>
        {segments.map((s) => (
          <span key={s.label} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
            {s.label}
            <span className="font-semibold tabular" style={{ color: 'var(--ink)' }}>
              {(s.value * 100).toFixed(1)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}

const SEQ = ['var(--seq-100)', 'var(--seq-250)', 'var(--seq-400)', 'var(--seq-550)', 'var(--seq-700)']

/** Scoreline probability heatmap (rows = home goals, cols = away goals). */
export function ScoreHeatmap({ matrix, home, away }: {
  matrix: number[][]
  home: string
  away: string
}) {
  const max = Math.max(...matrix.flat())
  const step = (p: number) => Math.min(SEQ.length - 1, Math.floor((p / max) * SEQ.length))
  const color = (p: number) => SEQ[step(p)]
  // The ramp always runs surface→ink, so the surface color is readable on the
  // strong end and secondary ink on the weak end — in both light and dark mode.
  const textColor = (p: number) => (step(p) >= 2 ? 'var(--surface-1)' : 'var(--ink-2)')
  return (
    <div className="overflow-x-auto">
      <table className="border-separate text-center text-xs" style={{ borderSpacing: 2 }}>
        <caption className="mb-1 text-left text-xs" style={{ color: 'var(--muted)' }}>
          Scoreline probability — rows: {home} goals, columns: {away} goals
        </caption>
        <thead>
          <tr>
            <th aria-label="corner" />
            {matrix[0].map((_, j) => (
              <th key={j} className="px-1 font-normal tabular" style={{ color: 'var(--muted)' }}>{j}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <th className="px-1 font-normal tabular" style={{ color: 'var(--muted)' }}>{i}</th>
              {row.map((p, j) => (
                <td key={j} title={`${i}-${j}: ${(p * 100).toFixed(1)}%`}
                  className="h-9 w-9 rounded tabular"
                  style={{ background: color(p), color: textColor(p) }}>
                  {(p * 100).toFixed(0)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
