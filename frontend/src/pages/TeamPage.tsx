import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, type GroupMeta, type Record_ } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Card, Empty, ErrorNote, FormChips, Loading, MatchList, StatTile } from '../components/ui'
import { GroupSelect } from '../components/GroupSelect'
import { TeamSelect } from '../components/TeamSelect'
import { ColumnChart, EloTrendChart } from '../components/charts'

export default function TeamPage({ groups }: { groups: GroupMeta[] }) {
  const [params, setParams] = useSearchParams()
  const group = params.get('group') ?? 'international'
  const [team, setTeam] = useState(params.get('team') ?? '')

  const { data: teams } = useApi(groups.length ? () => api.teams(group) : null, [group, groups.length])
  const selected = teams?.some((t) => t.team === team) ? team : null

  const { data: stats, error, loading } = useApi(
    selected ? () => api.teamStats(selected, group) : null, [selected, group])
  const { data: elo } = useApi(
    selected ? () => api.eloHistory(selected, group) : null, [selected, group])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <GroupSelect groups={groups} value={group}
          onChange={(g) => { setParams({ group: g }); setTeam('') }} />
        <div className="w-72">
          <TeamSelect teams={teams ?? []} value={team} placeholder="Type a team name…"
            onChange={(t) => { setTeam(t); setParams({ group, team: t }) }} />
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {loading && <Loading />}
      {!selected && !loading && <Empty text="Pick a competition and start typing a team name." />}

      {stats && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatTile label="Matches" value={stats.overall.played.toLocaleString()} />
            <StatTile label="Win rate" value={pct(stats.overall.win_rate)}
              sub={`${stats.overall.wins}W ${stats.overall.draws}D ${stats.overall.losses}L`} />
            <StatTile label="Home win rate" value={pct(stats.home.win_rate)}
              sub={rec(stats.home)} />
            <StatTile label="Away win rate" value={pct(stats.away.win_rate)}
              sub={rec(stats.away)} />
          </div>

          {elo && (
            <Card title={`Elo rating over time — ${stats.team}`}>
              <EloTrendChart series={[{ name: stats.team, color: 'var(--series-1)', data: elo.history }]} />
            </Card>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Last 10 matches">
              <div className="mb-2"><FormChips form={stats.form.map((m) => m.result!)} /></div>
              <MatchList matches={stats.form} perspective={stats.team} />
            </Card>
            <Card title="Goals scored per match (all time)">
              <ColumnChart name="matches" data={stats.goals_scored_distribution
                .filter((d) => d.goals <= 8)
                .map((d) => ({ label: d.goals, value: d.matches }))} />
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function pct(x: number | null): string {
  return x == null ? '—' : `${(x * 100).toFixed(1)}%`
}

function rec(r: Record_): string {
  return `${r.wins}W ${r.draws}D ${r.losses}L`
}
