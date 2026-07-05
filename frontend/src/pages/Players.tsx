import { useState } from 'react'
import { api, type GroupMeta } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Card, Empty, ErrorNote, Loading, StatTile } from '../components/ui'
import { TeamSelect } from '../components/TeamSelect'
import { ColumnChart } from '../components/charts'

const ERAS = [
  { label: 'All time', value: undefined },
  { label: 'Since 2000', value: '2000-01-01' },
  { label: 'Since 2010', value: '2010-01-01' },
  { label: 'Since 2020', value: '2020-01-01' },
]

export default function PlayersPage({ groups }: { groups: GroupMeta[] }) {
  const [team, setTeam] = useState('')
  const [since, setSince] = useState<string | undefined>(undefined)
  const [selected, setSelected] = useState<string | null>(null)

  const { data: teams } = useApi(
    groups.length ? () => api.teams('international') : null, [groups.length])
  const teamValid = teams?.some((t) => t.team === team) ?? false
  const teamFilter = teamValid ? team : undefined

  const { data: scorers, error, loading } = useApi(
    () => api.topScorers(teamFilter, since), [teamFilter, since])
  const { data: profile } = useApi(
    selected ? () => api.playerProfile(selected) : null, [selected])
  const { data: scoring } = useApi(
    teamFilter ? () => api.teamScoring(teamFilter, since) : null, [teamFilter, since])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="w-64">
          <TeamSelect teams={teams ?? []} value={team} placeholder="All countries — type to filter…"
            onChange={(t) => { setTeam(t); setSelected(null) }} />
        </div>
        <select aria-label="Era" className="card px-3 py-1.5 text-sm"
          value={since ?? ''} onChange={(e) => setSince(e.target.value || undefined)}>
          {ERAS.map((e) => <option key={e.label} value={e.value ?? ''}>{e.label}</option>)}
        </select>
        <span className="text-xs" style={{ color: 'var(--muted)' }}>
          International goals only · own goals excluded
        </span>
      </div>

      {error && <ErrorNote message={error} />}

      {scoring && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatTile label="Team goals" value={scoring.total_goals.toLocaleString()}
            sub={`${scoring.distinct_scorers} different scorers`} />
          <StatTile label="Top scorer share" value={`${(scoring.top_scorer_share * 100).toFixed(1)}%`}
            sub="Goals by the single top scorer" />
          <StatTile label="Concentration (HHI)" value={scoring.concentration_hhi.toFixed(3)}
            sub="1 = one player scores everything" />
          <StatTile label="Penalty share" value={`${(scoring.penalty_share * 100).toFixed(1)}%`}
            sub="Goals from the spot" />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_24rem]">
        <Card title={teamFilter ? `Top scorers — ${teamFilter}` : 'Top scorers — all nations'}>
          {loading && <Loading />}
          {scorers && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-sm">
                <thead>
                  <tr className="text-left text-xs" style={{ color: 'var(--muted)' }}>
                    <th className="py-1 pr-2 text-right">#</th>
                    <th className="py-1">Player</th>
                    <th className="py-1">Team</th>
                    <th className="py-1 text-right">Goals</th>
                    <th className="py-1 text-right">Pens</th>
                    <th className="py-1 pl-3">Career span</th>
                  </tr>
                </thead>
                <tbody>
                  {scorers.scorers.map((s, i) => (
                    <tr key={`${s.scorer}-${s.team}`}
                      className="cursor-pointer border-t hover:opacity-80"
                      style={{
                        borderColor: 'var(--grid)',
                        background: selected === s.scorer ? 'var(--page)' : undefined,
                      }}
                      onClick={() => setSelected(s.scorer)}>
                      <td className="py-1.5 pr-2 text-right tabular" style={{ color: 'var(--muted)' }}>{i + 1}</td>
                      <td className="py-1.5 font-medium">{s.scorer}</td>
                      <td className="py-1.5" style={{ color: 'var(--ink-2)' }}>{s.team}</td>
                      <td className="py-1.5 text-right font-semibold tabular">{s.goals}</td>
                      <td className="py-1.5 text-right tabular" style={{ color: 'var(--ink-2)' }}>{s.penalties}</td>
                      <td className="py-1.5 pl-3 text-xs tabular" style={{ color: 'var(--muted)' }}>
                        {s.first_goal.slice(0, 4)}–{s.last_goal.slice(0, 4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title={profile ? `${profile.scorer} (${profile.team})` : 'Player detail'}>
          {!selected && <Empty text="Click a player in the table." />}
          {profile && (
            <div className="grid gap-4">
              <div className="flex gap-6 text-sm">
                <div><span className="text-2xl font-semibold tabular">{profile.goals}</span>
                  <span className="ml-1 text-xs" style={{ color: 'var(--muted)' }}>goals</span></div>
                <div><span className="text-2xl font-semibold tabular">{profile.penalties}</span>
                  <span className="ml-1 text-xs" style={{ color: 'var(--muted)' }}>penalties</span></div>
              </div>
              <div>
                <h3 className="mb-1 text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>
                  Goals by match period
                </h3>
                <ColumnChart name="goals" data={profile.minute_distribution.map((b) => ({
                  label: b.period, value: b.goals,
                }))} />
              </div>
              <div>
                <h3 className="mb-1 text-xs font-semibold" style={{ color: 'var(--ink-2)' }}>
                  Favourite opponents
                </h3>
                <ul className="grid gap-0.5 text-sm">
                  {profile.favourite_opponents.slice(0, 6).map((o) => (
                    <li key={o.opponent} className="flex justify-between">
                      <span>{o.opponent}</span>
                      <span className="font-semibold tabular">{o.goals}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
