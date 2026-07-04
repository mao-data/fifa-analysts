import { useState } from 'react'
import { api, type GroupMeta } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Card, ErrorNote, Loading } from '../components/ui'
import { GroupSelect } from '../components/GroupSelect'
import { EloTrendChart } from '../components/charts'

const TREND_COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-6)']

export default function RankingsPage({ groups }: { groups: GroupMeta[] }) {
  const [group, setGroup] = useState('international')
  const { data, error, loading } = useApi(() => api.rankings(group, 50), [group])
  const top4 = data?.rankings.slice(0, 4) ?? []

  const { data: trends } = useApi(
    top4.length
      ? () => Promise.all(top4.map((t) => api.eloHistory(t.team, group)))
      : null,
    [group, top4.map((t) => t.team).join('|')])

  const maxElo = data?.rankings[0]?.elo ?? 1
  const minElo = data?.rankings.at(-1)?.elo ?? 0

  return (
    <div className="grid gap-4">
      <GroupSelect groups={groups} value={group} onChange={setGroup} className="w-fit" />
      {error && <ErrorNote message={error} />}
      {loading && <Loading />}

      {trends && trends.length > 1 && (
        <Card title="Elo trend — current top 4 (last decade)">
          <EloTrendChart series={trends.map((t, i) => ({
            name: t.team,
            color: TREND_COLORS[i % TREND_COLORS.length],
            data: t.history.filter((h) => h.date >= '2016-01-01'),
          }))} />
        </Card>
      )}

      {data && (
        <Card title={`Elo ranking — ${groups.find((g) => g.id === group)?.name ?? group}`}>
          <ol className="grid gap-1">
            {data.rankings.map((t, i) => (
              <li key={t.team} className="flex items-center gap-3 text-sm">
                <span className="w-6 text-right tabular" style={{ color: 'var(--muted)' }}>{i + 1}</span>
                <span className="w-44 truncate font-medium sm:w-56" title={t.team}>{t.team}</span>
                <span className="h-4 flex-1 rounded-r"
                  style={{ background: 'var(--page)' }} aria-hidden>
                  <span className="block h-full rounded"
                    style={{
                      width: `${Math.max(2, ((t.elo - minElo) / Math.max(1, maxElo - minElo)) * 100)}%`,
                      background: 'var(--series-1)',
                    }} />
                </span>
                <span className="w-14 text-right font-semibold tabular">{Math.round(t.elo)}</span>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  )
}
