import { lazy, Suspense } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { Loading } from './components/ui'
import { useApi } from './lib/useApi'
import { api } from './lib/api'

// Route-level code splitting: charts (recharts) only load with the pages
// that use them, keeping the initial bundle small.
const Dashboard = lazy(() => import('./pages/Dashboard'))
const TeamPage = lazy(() => import('./pages/TeamPage'))
const H2HPage = lazy(() => import('./pages/H2H'))
const StandingsPage = lazy(() => import('./pages/Standings'))
const RankingsPage = lazy(() => import('./pages/Rankings'))
const PredictPage = lazy(() => import('./pages/Predict'))
const PlayersPage = lazy(() => import('./pages/Players'))
const XgLabPage = lazy(() => import('./pages/XgLab'))
const ReportCardPage = lazy(() => import('./pages/ReportCard'))

const NAV = [
  { to: '/', label: 'Dashboard' },
  { to: '/teams', label: 'Teams' },
  { to: '/h2h', label: 'Head to head' },
  { to: '/standings', label: 'Standings' },
  { to: '/rankings', label: 'Elo rankings' },
  { to: '/predict', label: 'Predict' },
  { to: '/players', label: 'Players' },
  { to: '/xg', label: 'xG Lab' },
  { to: '/report', label: 'WC 2026' },
]

export default function App() {
  const { data: meta } = useApi(() => api.meta(), [])
  const groups = meta?.groups ?? []

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 py-5">
        <h1 className="text-lg font-bold">⚽ Football Analytics</h1>
        <nav className="flex flex-wrap gap-1 text-sm">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 ${isActive ? 'card font-semibold' : ''}`}
              style={({ isActive }) => ({ color: isActive ? 'var(--ink)' : 'var(--ink-2)' })}>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Dashboard meta={meta} />} />
          <Route path="/teams" element={<TeamPage groups={groups} />} />
          <Route path="/h2h" element={<H2HPage groups={groups} />} />
          <Route path="/standings" element={<StandingsPage groups={groups} />} />
          <Route path="/rankings" element={<RankingsPage groups={groups} />} />
          <Route path="/predict" element={<PredictPage groups={groups} />} />
          <Route path="/players" element={<PlayersPage groups={groups} />} />
          <Route path="/xg" element={<XgLabPage />} />
          <Route path="/report" element={<ReportCardPage />} />
        </Routes>
      </Suspense>
    </div>
  )
}
