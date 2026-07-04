import { Link } from 'react-router-dom'
import { api, type Meta } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Card, Loading, MatchList, StatTile } from '../components/ui'

export default function Dashboard({ meta }: { meta: Meta | null }) {
  const { data: recent } = useApi(() => api.recentMatches(undefined, 12), [])
  const { data: intlTop } = useApi(() => api.rankings('international', 10), [])
  const { data: backtest } = useApi(() => api.backtest(), [])

  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="Matches in database" value={meta ? meta.total_matches.toLocaleString() : '—'}
          sub={meta ? `${meta.date_range.from} → ${meta.date_range.to}` : undefined} />
        <StatTile label="Competitions" value={meta ? String(meta.groups.length) : '—'}
          sub="International + top-5 leagues" />
        <StatTile label="Model accuracy (international)"
          value={fmtPct(backtest?.results.find(
            (r) => r.rating_group === 'international' && r.model === 'ensemble')?.accuracy)}
          sub="Ensemble, walk-forward backtest, last 2 years" />
        <StatTile label="Model accuracy (leagues)"
          value={fmtPct(avgLeagueAcc(backtest?.results))}
          sub="Ensemble, average across the 5 leagues" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <Card title="Recent matches (all competitions)">
          {recent ? <MatchList matches={recent} /> : <Loading />}
        </Card>
        <Card title="Elo top 10 — international">
          {intlTop ? (
            <ol className="grid gap-1 text-sm">
              {intlTop.rankings.map((t, i) => (
                <li key={t.team} className="flex items-center gap-2">
                  <span className="w-5 text-right tabular" style={{ color: 'var(--muted)' }}>{i + 1}</span>
                  <span className="flex-1">{t.team}</span>
                  <span className="font-semibold tabular">{Math.round(t.elo)}</span>
                </li>
              ))}
            </ol>
          ) : <Loading />}
          <Link to="/rankings" className="mt-3 block text-xs underline" style={{ color: 'var(--ink-2)' }}>
            Full rankings →
          </Link>
        </Card>
      </div>
    </div>
  )
}

function fmtPct(x?: number | null): string {
  return x == null ? '—' : `${(x * 100).toFixed(1)}%`
}

function avgLeagueAcc(results?: { rating_group: string; model: string; accuracy: number }[]): number | null {
  const leagues = (results ?? []).filter(
    (r) => r.rating_group !== 'international' && r.model === 'ensemble')
  if (!leagues.length) return null
  return leagues.reduce((s, r) => s + r.accuracy, 0) / leagues.length
}
