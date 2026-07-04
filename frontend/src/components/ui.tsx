import type { ReactNode } from 'react'
import type { MatchInfo } from '../lib/api'

export function Card({ title, children, className = '' }: {
  title?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`card p-4 ${className}`}>
      {title && (
        <h2 className="mb-3 text-sm font-semibold" style={{ color: 'var(--ink-2)' }}>
          {title}
        </h2>
      )}
      {children}
    </section>
  )
}

export function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-4">
      <div className="text-xs" style={{ color: 'var(--muted)' }}>{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-1 text-xs" style={{ color: 'var(--ink-2)' }}>{sub}</div>}
    </div>
  )
}

const FORM_COLOR: Record<string, string> = {
  W: 'var(--series-2)',
  D: 'var(--series-3)',
  L: 'var(--series-6)',
}

export function FormChips({ form }: { form: string[] }) {
  return (
    <span className="inline-flex gap-1">
      {form.map((r, i) => (
        <span
          key={i}
          title={r === 'W' ? 'Win' : r === 'D' ? 'Draw' : 'Loss'}
          className="inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold text-white"
          style={{ background: FORM_COLOR[r] ?? 'var(--muted)' }}
        >
          {r}
        </span>
      ))}
    </span>
  )
}

export function MatchList({ matches, perspective }: { matches: MatchInfo[]; perspective?: string }) {
  if (!matches.length) return <Empty text="No matches" />
  return (
    <ul className="divide-y" style={{ borderColor: 'var(--grid)' }}>
      {matches.map((m, i) => (
        <li key={i} className="flex items-center gap-3 py-2 text-sm">
          <span className="w-20 shrink-0 text-xs tabular" style={{ color: 'var(--muted)' }}>
            {m.date}
          </span>
          {perspective && m.result && <FormChips form={[m.result]} />}
          <span className={`flex-1 text-right ${m.home_team === perspective ? 'font-semibold' : ''}`}>
            {m.home_team}
          </span>
          <span className="tabular rounded px-2 py-0.5 text-xs font-semibold"
            style={{ background: 'var(--page)', border: '1px solid var(--border)' }}>
            {m.home_score} – {m.away_score}
          </span>
          <span className={`flex-1 ${m.away_team === perspective ? 'font-semibold' : ''}`}>
            {m.away_team}
          </span>
          <span className="hidden w-40 shrink-0 truncate text-right text-xs sm:block"
            style={{ color: 'var(--muted)' }} title={m.competition}>
            {m.competition}
          </span>
        </li>
      ))}
    </ul>
  )
}

export function Empty({ text }: { text: string }) {
  return <div className="py-8 text-center text-sm" style={{ color: 'var(--muted)' }}>{text}</div>
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="card p-4 text-sm" role="alert" style={{ color: 'var(--series-6)' }}>
      {message}
    </div>
  )
}

export function Loading() {
  return <div className="py-8 text-center text-sm animate-pulse" style={{ color: 'var(--muted)' }}>Loading…</div>
}
