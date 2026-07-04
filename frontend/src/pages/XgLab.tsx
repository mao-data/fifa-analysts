import { useState } from 'react'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Card, Empty, ErrorNote, Loading } from '../components/ui'
import { ShotMap } from '../components/ShotMap'

export default function XgLabPage() {
  const { data: comps, error: compsError } = useApi(() => api.xgCompetitions(), [])
  const [compKey, setCompKey] = useState<string | null>(null)
  const list = comps?.competitions ?? []
  const current = list.find((c) => `${c.competition}|${c.season}` === compKey) ?? list[0]

  const { data: teams, error } = useApi(
    current ? () => api.xgTeams(current.competition, current.season) : null,
    [current?.competition, current?.season])
  const { data: playersData } = useApi(
    current ? () => api.xgPlayers(current.competition, current.season) : null,
    [current?.competition, current?.season])
  const { data: matches } = useApi(
    current ? () => api.xgMatches(current.competition, current.season) : null,
    [current?.competition, current?.season])

  const [matchId, setMatchId] = useState<number | null>(null)
  const { data: matchDetail } = useApi(
    matchId ? () => api.xgMatch(matchId) : null, [matchId])

  if (compsError) return <ErrorNote message={compsError} />
  if (comps && !list.length) {
    return <Empty text="No shot data loaded — run `python -m app.etl.cli statsbomb` in the backend." />
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Tournament" className="card px-3 py-1.5 text-sm"
          value={current ? `${current.competition}|${current.season}` : ''}
          onChange={(e) => { setCompKey(e.target.value); setMatchId(null) }}>
          {list.map((c) => (
            <option key={`${c.competition}|${c.season}`} value={`${c.competition}|${c.season}`}>
              {c.competition} {c.season}
            </option>
          ))}
        </select>
        <span className="text-xs" style={{ color: 'var(--muted)' }}>
          Event data: StatsBomb open data · xG = chance quality of each shot
        </span>
      </div>

      {error && <ErrorNote message={error} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Teams — xG for/against and finishing">
          {teams ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[460px] text-sm">
                <thead>
                  <tr className="text-left text-xs" style={{ color: 'var(--muted)' }}>
                    <th className="py-1">Team</th>
                    <th className="py-1 text-right">P</th>
                    <th className="py-1 text-right">G</th>
                    <th className="py-1 text-right">xG</th>
                    <th className="py-1 text-right">GA</th>
                    <th className="py-1 text-right">xGA</th>
                    <th className="py-1 text-right" title="Goals minus xG: + clinical, - wasteful">
                      Finishing ±
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {teams.teams.map((t) => (
                    <tr key={t.team} className="border-t" style={{ borderColor: 'var(--grid)' }}>
                      <td className="py-1.5 font-medium">{t.team}</td>
                      <td className="py-1.5 text-right tabular">{t.matches}</td>
                      <td className="py-1.5 text-right tabular">{t.goals}</td>
                      <td className="py-1.5 text-right tabular">{t.xg_for.toFixed(1)}</td>
                      <td className="py-1.5 text-right tabular">{t.goals_against}</td>
                      <td className="py-1.5 text-right tabular">{t.xg_against.toFixed(1)}</td>
                      <td className="py-1.5 text-right font-semibold tabular"
                        style={{ color: t.finishing_delta > 0 ? 'var(--good)' : t.finishing_delta < 0 ? 'var(--series-6)' : undefined }}>
                        {t.finishing_delta > 0 ? '+' : ''}{t.finishing_delta.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <Loading />}
        </Card>

        <Card title="Players — goals vs expected goals">
          {playersData ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[440px] text-sm">
                <thead>
                  <tr className="text-left text-xs" style={{ color: 'var(--muted)' }}>
                    <th className="py-1">Player</th>
                    <th className="py-1">Team</th>
                    <th className="py-1 text-right">Shots</th>
                    <th className="py-1 text-right">G</th>
                    <th className="py-1 text-right">xG</th>
                    <th className="py-1 text-right">±</th>
                  </tr>
                </thead>
                <tbody>
                  {playersData.players.slice(0, 15).map((p) => (
                    <tr key={`${p.player}`} className="border-t" style={{ borderColor: 'var(--grid)' }}>
                      <td className="py-1.5 font-medium">{p.player}</td>
                      <td className="py-1.5 text-xs" style={{ color: 'var(--ink-2)' }}>{p.team}</td>
                      <td className="py-1.5 text-right tabular">{p.shots}</td>
                      <td className="py-1.5 text-right font-semibold tabular">{p.goals}</td>
                      <td className="py-1.5 text-right tabular">{p.xg.toFixed(1)}</td>
                      <td className="py-1.5 text-right tabular"
                        style={{ color: p.finishing_delta > 0 ? 'var(--good)' : p.finishing_delta < 0 ? 'var(--series-6)' : undefined }}>
                        {p.finishing_delta > 0 ? '+' : ''}{p.finishing_delta.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <Loading />}
        </Card>
      </div>

      <Card title="Match shot map">
        <div className="mb-3">
          <select aria-label="Match" className="card w-full max-w-xl px-3 py-1.5 text-sm"
            value={matchId ?? ''} onChange={(e) => setMatchId(Number(e.target.value) || null)}>
            <option value="">Pick a match…</option>
            {(matches?.matches ?? []).map((m) => (
              <option key={m.match_id} value={m.match_id}>
                {m.date} · {m.home_team} {m.home_score}–{m.away_score} {m.away_team}
                {m.stage ? ` (${m.stage})` : ''}
              </option>
            ))}
          </select>
        </div>
        {matchDetail ? (
          <div className="grid gap-3">
            <div className="text-sm" style={{ color: 'var(--ink-2)' }}>
              xG totals:{' '}
              <strong style={{ color: 'var(--ink)' }}>
                {matchDetail.match.home_team} {matchDetail.xg_totals[matchDetail.match.home_team]?.toFixed(2) ?? '0.00'}
              </strong>
              {' — '}
              <strong style={{ color: 'var(--ink)' }}>
                {matchDetail.xg_totals[matchDetail.match.away_team]?.toFixed(2) ?? '0.00'} {matchDetail.match.away_team}
              </strong>
              {matchDetail.match.stadium && <span> · {matchDetail.match.stadium}</span>}
            </div>
            <ShotMap shots={matchDetail.shots}
              home={matchDetail.match.home_team} away={matchDetail.match.away_team} />
          </div>
        ) : <Empty text="Pick a match to see every shot with its xG." />}
      </Card>
    </div>
  )
}
