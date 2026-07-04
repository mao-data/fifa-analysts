import { useState } from 'react'
import { api, type GroupMeta } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Card, Empty, ErrorNote, Loading, MatchList, StatTile } from '../components/ui'
import { GroupSelect } from '../components/GroupSelect'
import { TeamSelect } from '../components/TeamSelect'
import { ProbBar } from '../components/charts'

export default function H2HPage({ groups }: { groups: GroupMeta[] }) {
  const [group, setGroup] = useState('international')
  const [team1, setTeam1] = useState('')
  const [team2, setTeam2] = useState('')

  const { data: teams } = useApi(groups.length ? () => api.teams(group) : null, [group, groups.length])
  const valid = (t: string) => teams?.some((x) => x.team === t) ?? false
  const ready = valid(team1) && valid(team2) && team1 !== team2

  const { data, error, loading } = useApi(
    ready ? () => api.h2h(team1, team2, group) : null, [ready, team1, team2, group])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <GroupSelect groups={groups} value={group}
          onChange={(g) => { setGroup(g); setTeam1(''); setTeam2('') }} />
        <div className="w-60">
          <TeamSelect teams={teams ?? []} value={team1} onChange={setTeam1} placeholder="Team 1…" />
        </div>
        <span className="text-sm" style={{ color: 'var(--muted)' }}>vs</span>
        <div className="w-60">
          <TeamSelect teams={teams ?? []} value={team2} onChange={setTeam2} placeholder="Team 2…" />
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {loading && <Loading />}
      {!ready && !loading && <Empty text="Pick two different teams to compare." />}

      {data && (
        <>
          {data.played === 0 ? (
            <Empty text="These teams have never met in this competition." />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <StatTile label="Meetings" value={String(data.played)} />
                <StatTile label={`${data.team1} wins`} value={String(data.team1_wins)} />
                <StatTile label="Draws" value={String(data.draws)} />
                <StatTile label={`${data.team2} wins`} value={String(data.team2_wins)} />
              </div>
              <Card title="Result split">
                <ProbBar segments={[
                  { label: `${data.team1} wins`, value: data.team1_wins / data.played, color: 'var(--series-1)' },
                  { label: 'Draws', value: data.draws / data.played, color: 'var(--series-3)' },
                  { label: `${data.team2} wins`, value: data.team2_wins / data.played, color: 'var(--series-6)' },
                ]} />
                <p className="mt-3 text-xs" style={{ color: 'var(--ink-2)' }}>
                  Goals: {data.team1} {data.team1_goals} – {data.team2_goals} {data.team2}
                </p>
              </Card>
              <Card title={`Last ${data.matches.length} meetings`}>
                <MatchList matches={data.matches} perspective={data.team1} />
              </Card>
            </>
          )}
        </>
      )}
    </div>
  )
}
