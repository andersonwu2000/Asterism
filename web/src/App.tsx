import { RouterProvider, useRoute, Link } from './lib/router'
import { usePoll } from './lib/api'
import Board from './screens/Board'
import Inbox from './screens/Inbox'
import Problem from './screens/Problem'
import Telemetry from './screens/Telemetry'

interface MetaResponse {
  workspace: string
  daemon: { running: boolean; pid: number | null; stopping: boolean; in_flight_leases: number }
  inbox_count: number
}

function DaemonChip({ meta }: { meta: MetaResponse | null }) {
  if (!meta) return <span className="text-ink-faint text-xs">engine…</span>
  const d = meta.daemon
  const label = d.stopping ? 'stopping' : d.running ? 'running' : 'idle'
  const dot = d.stopping ? 'bg-warn' : d.running ? 'bg-ok' : 'bg-ink-faint'
  return (
    <Link
      to="/telemetry"
      className="flex items-center gap-2 rounded-full border border-edge px-3 py-1 text-xs text-ink-dim hover:border-edge-strong"
      title={d.pid ? `daemon pid ${d.pid}` : 'daemon not running'}
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      daemon {label}
      {d.running && d.in_flight_leases > 0 && (
        <span className="text-ink-faint">· {d.in_flight_leases} in flight</span>
      )}
    </Link>
  )
}

function NavItem({ to, label, active, badge }: { to: string; label: string; active: boolean; badge?: number }) {
  return (
    <Link
      to={to}
      className={`flex items-center justify-between rounded-md px-3 py-1.5 text-sm ${
        active ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:text-ink'
      }`}
    >
      {label}
      {badge !== undefined && badge > 0 && (
        <span className="ml-2 rounded-full bg-danger/20 px-2 py-0.5 text-xs text-danger">{badge}</span>
      )}
    </Link>
  )
}

function Shell() {
  const route = useRoute()
  const { data: meta } = usePoll<MetaResponse>('/api/meta', 3000)
  const section = route.segments[0] ?? ''

  return (
    <div className="flex h-full">
      <aside className="flex w-52 shrink-0 flex-col border-r border-edge bg-surface px-3 py-4">
        <Link to="/" className="mb-6 flex items-center gap-2 px-3">
          <svg width="18" height="18" viewBox="0 0 24 24" className="text-star" aria-hidden>
            <path
              fill="currentColor"
              d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z"
            />
          </svg>
          <span className="text-base font-semibold tracking-wide">Asterism</span>
        </Link>
        <nav className="flex flex-col gap-1">
          <NavItem to="/" label="Board" active={section === '' || section === 'problems'} />
          <NavItem to="/inbox" label="Inbox" active={section === 'inbox'} badge={meta?.inbox_count} />
          <NavItem to="/telemetry" label="Telemetry" active={section === 'telemetry'} />
        </nav>
        <div className="mt-auto px-3 text-xs text-ink-faint" title={meta?.workspace}>
          {meta ? meta.workspace.split(/[\\/]/).pop() : ''}
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-end border-b border-edge px-4">
          <DaemonChip meta={meta} />
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          {section === 'inbox' ? (
            <Inbox />
          ) : section === 'telemetry' ? (
            <Telemetry />
          ) : section === 'problems' && route.segments[1] ? (
            <Problem name={route.segments[1]} />
          ) : (
            <Board />
          )}
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <RouterProvider>
      <Shell />
    </RouterProvider>
  )
}
