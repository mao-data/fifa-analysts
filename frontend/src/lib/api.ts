export interface GroupMeta {
  id: string
  name: string
  scope: 'international' | 'league'
  matches: number
  seasons: string[]
}

export interface Meta {
  groups: GroupMeta[]
  total_matches: number
  date_range: { from: string; to: string }
}

export interface Record_ {
  played: number
  wins: number
  draws: number
  losses: number
  win_rate: number | null
  goals_for: number
  goals_against: number
}

export interface MatchInfo {
  date: string
  competition: string
  season: string | null
  home_team: string
  away_team: string
  home_score: number
  away_score: number
  result?: 'W' | 'D' | 'L'
  group?: string
}

export interface TeamStats {
  team: string
  group: string
  overall: Record_
  home: Record_
  away: Record_
  form: MatchInfo[]
  goals_scored_distribution: { goals: number; matches: number }[]
}

export interface TeamListItem {
  team: string
  elo: number
  matches: number
  last_match: string
}

export interface H2H {
  team1: string
  team2: string
  played: number
  team1_wins: number
  draws: number
  team2_wins: number
  team1_goals: number
  team2_goals: number
  matches: MatchInfo[]
}

export interface StandingRow {
  position: number
  team: string
  played: number
  wins: number
  draws: number
  losses: number
  goals_for: number
  goals_against: number
  goal_diff: number
  points: number
  form: string[]
}

export interface Wdl {
  home_win: number
  draw: number
  away_win: number
}

export interface Prediction {
  home: string
  away: string
  group: string
  neutral: boolean
  model_used: string
  elo: { home: number; away: number; expected_score: number }
  lambdas: { home: number; away: number } | null
  probabilities: Wdl
  models: { dixon_coles?: Wdl & { rho: number }; ml?: Wdl; ensemble: Wdl }
  most_likely_scores: { score: string; probability: number }[]
  score_matrix: number[][] | null
}

export interface BacktestResult {
  rating_group: string
  model: 'elo' | 'dixon_coles' | 'ml' | 'ensemble'
  test_from: string
  n_matches: number
  accuracy: number
  brier: number
  baseline_home_accuracy: number
  baseline_brier: number
  draw_rate: number
}

export class ApiError extends Error {
  status: number
  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(path, window.location.origin)
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== '') url.searchParams.set(k, String(v))
  }
  const resp = await fetch(url)
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      detail = (await resp.json()).detail ?? detail
    } catch { /* non-JSON error body */ }
    throw new ApiError(resp.status, detail)
  }
  return resp.json()
}

export const api = {
  meta: () => get<Meta>('/api/meta'),
  recentMatches: (group?: string, limit = 20) =>
    get<MatchInfo[]>('/api/matches/recent', { group, limit }),
  teams: (group: string, q?: string) => get<TeamListItem[]>('/api/teams', { group, q }),
  teamStats: (team: string, group: string) =>
    get<TeamStats>(`/api/teams/${encodeURIComponent(team)}/stats`, { group }),
  eloHistory: (team: string, group: string) =>
    get<{ team: string; history: { date: string; elo: number }[] }>(
      `/api/teams/${encodeURIComponent(team)}/elo-history`, { group }),
  h2h: (team1: string, team2: string, group?: string) =>
    get<H2H>('/api/h2h', { team1, team2, group }),
  standings: (group: string, season: string) =>
    get<{ group: string; season: string; table: StandingRow[] }>(
      `/api/standings/${group}/${season}`),
  rankings: (group: string, limit = 50) =>
    get<{ group: string; rankings: TeamListItem[] }>('/api/rankings/elo', { group, limit }),
  predict: (home: string, away: string, group: string, neutral: boolean) =>
    get<Prediction>('/api/predict', { home, away, group, neutral }),
  backtest: () => get<{ results: BacktestResult[]; notes: string }>('/api/model/backtest'),
}
