import { useState } from 'react'
import { api, type GroupMeta } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Card, Empty, ErrorNote, Loading } from '../components/ui'
import { GroupSelect } from '../components/GroupSelect'
import { TeamSelect } from '../components/TeamSelect'
import { ProbBar, ScoreHeatmap } from '../components/charts'

export default function PredictPage({ groups }: { groups: GroupMeta[] }) {
  const [group, setGroup] = useState('international')
  const [home, setHome] = useState('')
  const [away, setAway] = useState('')
  const [neutral, setNeutral] = useState(false)

  const { data: teams } = useApi(groups.length ? () => api.teams(group) : null, [group, groups.length])
  const valid = (t: string) => teams?.some((x) => x.team === t) ?? false
  const ready = valid(home) && valid(away) && home !== away

  const { data, error, loading } = useApi(
    ready ? () => api.predict(home, away, group, neutral) : null,
    [ready, home, away, group, neutral])

  const { data: backtest } = useApi(() => api.backtest(), [])
  const bt = backtest?.results.find((r) => r.rating_group === group)

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <GroupSelect groups={groups} value={group}
          onChange={(g) => { setGroup(g); setHome(''); setAway('') }} />
        <div className="w-56">
          <TeamSelect teams={teams ?? []} value={home} onChange={setHome} placeholder="Home team…" />
        </div>
        <span className="text-sm" style={{ color: 'var(--muted)' }}>vs</span>
        <div className="w-56">
          <TeamSelect teams={teams ?? []} value={away} onChange={setAway} placeholder="Away team…" />
        </div>
        <label className="flex items-center gap-1.5 text-sm" style={{ color: 'var(--ink-2)' }}>
          <input type="checkbox" checked={neutral} onChange={(e) => setNeutral(e.target.checked)} />
          Neutral venue
        </label>
      </div>

      {error && <ErrorNote message={error} />}
      {loading && <Loading />}
      {!ready && !loading && <Empty text="Pick two different teams to get a forecast." />}

      {data && (
        <>
          <Card title={`Forecast — ${data.home} vs ${data.away}${data.neutral ? ' (neutral venue)' : ''}`}>
            <ProbBar segments={[
              { label: `${data.home} win`, value: data.probabilities.home_win, color: 'var(--series-1)' },
              { label: 'Draw', value: data.probabilities.draw, color: 'var(--series-3)' },
              { label: `${data.away} win`, value: data.probabilities.away_win, color: 'var(--series-6)' },
            ]} />
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-4"
              style={{ color: 'var(--ink-2)' }}>
              <div><dt className="inline">Elo:</dt> <dd className="inline font-semibold tabular"
                style={{ color: 'var(--ink)' }}>{Math.round(data.elo.home)} vs {Math.round(data.elo.away)}</dd></div>
              <div><dt className="inline">Expected goals:</dt> <dd className="inline font-semibold tabular"
                style={{ color: 'var(--ink)' }}>{data.lambdas.home.toFixed(2)} – {data.lambdas.away.toFixed(2)}</dd></div>
              <div className="col-span-2"><dt className="inline">Most likely scores:</dt>{' '}
                <dd className="inline font-semibold tabular" style={{ color: 'var(--ink)' }}>
                  {data.most_likely_scores.slice(0, 3).map((s) =>
                    `${s.score} (${(s.probability * 100).toFixed(0)}%)`).join(', ')}
                </dd></div>
            </dl>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Scoreline probabilities">
              <ScoreHeatmap matrix={data.score_matrix} home={data.home} away={data.away} />
            </Card>
            <Card title="How good is this model?">
              {bt ? (
                <div className="grid gap-2 text-sm" style={{ color: 'var(--ink-2)' }}>
                  <p>
                    Backtested on the last 2 years of this competition
                    ({bt.n_matches.toLocaleString()} matches, walk-forward — the model never
                    sees the future):
                  </p>
                  <ul className="grid gap-1">
                    <li>3-way accuracy: <strong style={{ color: 'var(--ink)' }}>{(bt.accuracy * 100).toFixed(1)}%</strong>{' '}
                      (always-pick-home baseline: {(bt.baseline_home_accuracy * 100).toFixed(1)}%)</li>
                    <li>Brier score: <strong style={{ color: 'var(--ink)' }}>{bt.brier.toFixed(3)}</strong>{' '}
                      (baseline {bt.baseline_brier.toFixed(3)}; 0 is perfect, lower is better)</li>
                  </ul>
                  <p>
                    Football is a low-scoring, high-variance sport — even bookmaker models top out
                    around 53–55% on leagues. Treat these as calibrated probabilities, not certainties.
                  </p>
                </div>
              ) : <Loading />}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
