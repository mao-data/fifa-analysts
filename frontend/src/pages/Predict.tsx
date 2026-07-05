import { useState } from 'react'
import { api, type GroupMeta, type Wdl } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Card, Empty, ErrorNote, Loading } from '../components/ui'
import { GroupSelect } from '../components/GroupSelect'
import { TeamSelect } from '../components/TeamSelect'
import { ProbBar, ScoreHeatmap } from '../components/charts'

const MODEL_NAMES: Record<string, string> = {
  elo: 'Elo + draw rate',
  dixon_coles: 'Dixon-Coles',
  ml: 'Gradient boosting',
  ensemble: 'Ensemble',
}
const MODEL_ORDER = ['elo', 'dixon_coles', 'ml', 'ensemble']

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
  const bt = (backtest?.results.filter((r) => r.rating_group === group) ?? [])
    .sort((a, b) => MODEL_ORDER.indexOf(a.model) - MODEL_ORDER.indexOf(b.model))
  const btHome = bt[0]?.baseline_home_accuracy

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
              <div><dt className="inline">Model:</dt> <dd className="inline font-semibold"
                style={{ color: 'var(--ink)' }}>{data.model_used}</dd></div>
              <div><dt className="inline">Elo:</dt> <dd className="inline font-semibold tabular"
                style={{ color: 'var(--ink)' }}>{Math.round(data.elo.home)} vs {Math.round(data.elo.away)}</dd></div>
              {data.lambdas && (
                <div><dt className="inline">Expected goals:</dt> <dd className="inline font-semibold tabular"
                  style={{ color: 'var(--ink)' }}>{data.lambdas.home.toFixed(2)} – {data.lambdas.away.toFixed(2)}</dd></div>
              )}
              {data.most_likely_scores.length > 0 && (
                <div><dt className="inline">Top scores:</dt>{' '}
                  <dd className="inline font-semibold tabular" style={{ color: 'var(--ink)' }}>
                    {data.most_likely_scores.slice(0, 3).map((s) =>
                      `${s.score} (${(s.probability * 100).toFixed(0)}%)`).join(', ')}
                  </dd></div>
              )}
            </dl>
          </Card>

          <Card title="What each model says">
            <ModelTable models={data.models} home={data.home} away={data.away} />
            <p className="mt-3 text-xs" style={{ color: 'var(--muted)' }}>
              Dixon-Coles: time-decayed attack/defence Poisson with a low-score correction —
              it also produces the scoreline matrix. Gradient boosting: trees trained on Elo,
              form, rolling goals, rest days and match importance. The ensemble averages the two.
            </p>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            {data.score_matrix && (
              <Card title="Scoreline probabilities (Dixon-Coles)">
                <ScoreHeatmap matrix={data.score_matrix} home={data.home} away={data.away} />
              </Card>
            )}
            <Card title="How good are these models?">
              {bt.length ? (
                <div className="grid gap-3 text-sm" style={{ color: 'var(--ink-2)' }}>
                  <p>
                    Walk-forward backtest on the last 2 years of this competition
                    ({bt[0].n_matches.toLocaleString()} matches — the models never see the future).
                    {btHome != null && <> Always-pick-home baseline: {(btHome * 100).toFixed(1)}% accuracy.</>}
                  </p>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left" style={{ color: 'var(--muted)' }}>
                        <th className="py-1">Model</th>
                        <th className="py-1 text-right">Accuracy</th>
                        <th className="py-1 text-right" title="0 is perfect, lower is better">Brier ↓</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bt.map((r) => (
                        <tr key={r.model} className="border-t" style={{ borderColor: 'var(--grid)' }}>
                          <td className={`py-1.5 ${r.model === 'ensemble' ? 'font-semibold' : ''}`}
                            style={{ color: 'var(--ink)' }}>
                            {MODEL_NAMES[r.model] ?? r.model}
                          </td>
                          <td className="py-1.5 text-right tabular">{(r.accuracy * 100).toFixed(1)}%</td>
                          <td className="py-1.5 text-right tabular">{r.brier.toFixed(3)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p>
                    Football is a low-scoring, high-variance sport — even bookmaker models top out
                    around 53–55% on leagues. The gains show up mostly in the Brier score
                    (probability calibration), which is what matters for trusting the percentages.
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

function ModelTable({ models, home, away }: {
  models: { dixon_coles?: Wdl; ml?: Wdl; ensemble: Wdl }
  home: string
  away: string
}) {
  const rows = (Object.entries(models) as [string, Wdl][])
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] text-sm">
        <thead>
          <tr className="text-left text-xs" style={{ color: 'var(--muted)' }}>
            <th className="py-1">Model</th>
            <th className="py-1 text-right">{home} win</th>
            <th className="py-1 text-right">Draw</th>
            <th className="py-1 text-right">{away} win</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, p]) => (
            <tr key={name} className="border-t" style={{ borderColor: 'var(--grid)' }}>
              <td className={`py-1.5 ${name === 'ensemble' ? 'font-semibold' : ''}`}>
                {MODEL_NAMES[name] ?? name}
              </td>
              {[p.home_win, p.draw, p.away_win].map((v, i) => (
                <td key={i} className={`py-1.5 text-right tabular ${name === 'ensemble' ? 'font-semibold' : ''}`}>
                  {(v * 100).toFixed(1)}%
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
