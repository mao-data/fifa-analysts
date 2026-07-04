import { useMemo, useState } from 'react'
import { api, type GroupMeta } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Card, Empty, ErrorNote, FormChips, Loading } from '../components/ui'
import { GroupSelect } from '../components/GroupSelect'

export default function StandingsPage({ groups }: { groups: GroupMeta[] }) {
  const leagues = useMemo(() => groups.filter((g) => g.scope === 'league'), [groups])
  const [group, setGroup] = useState('en.1')
  const seasons = leagues.find((g) => g.id === group)?.seasons ?? []
  const [season, setSeason] = useState<string | null>(null)
  const effectiveSeason = season && seasons.includes(season) ? season : seasons[0]

  const { data, error, loading } = useApi(
    effectiveSeason ? () => api.standings(group, effectiveSeason) : null,
    [group, effectiveSeason])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <GroupSelect groups={leagues} value={group}
          onChange={(g) => { setGroup(g); setSeason(null) }} />
        <select aria-label="Season" className="card px-3 py-1.5 text-sm"
          value={effectiveSeason ?? ''} onChange={(e) => setSeason(e.target.value)}>
          {seasons.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {error && <ErrorNote message={error} />}
      {loading && <Loading />}
      {!leagues.length && <Empty text="No league data loaded yet — run the ETL." />}

      {data && (
        <Card title={`${leagues.find((g) => g.id === group)?.name ?? group} — ${data.season}`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[540px] text-sm">
              <thead>
                <tr className="text-left text-xs" style={{ color: 'var(--muted)' }}>
                  <th className="py-1 pr-2 text-right">#</th>
                  <th className="py-1 pr-2">Team</th>
                  {['P', 'W', 'D', 'L', 'GF', 'GA', 'GD', 'Pts'].map((h) => (
                    <th key={h} className="px-1.5 py-1 text-right">{h}</th>
                  ))}
                  <th className="py-1 pl-3">Form</th>
                </tr>
              </thead>
              <tbody>
                {data.table.map((r) => (
                  <tr key={r.team} className="border-t" style={{ borderColor: 'var(--grid)' }}>
                    <td className="py-1.5 pr-2 text-right tabular" style={{ color: 'var(--muted)' }}>
                      {r.position}
                    </td>
                    <td className="py-1.5 pr-2 font-medium">{r.team}</td>
                    {[r.played, r.wins, r.draws, r.losses, r.goals_for, r.goals_against].map((v, i) => (
                      <td key={i} className="px-1.5 py-1.5 text-right tabular">{v}</td>
                    ))}
                    <td className="px-1.5 py-1.5 text-right tabular"
                      style={{ color: r.goal_diff > 0 ? 'var(--good)' : r.goal_diff < 0 ? 'var(--series-6)' : undefined }}>
                      {r.goal_diff > 0 ? `+${r.goal_diff}` : r.goal_diff}
                    </td>
                    <td className="px-1.5 py-1.5 text-right font-semibold tabular">{r.points}</td>
                    <td className="py-1.5 pl-3"><FormChips form={r.form} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
