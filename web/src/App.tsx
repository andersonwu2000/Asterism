import type { ReactNode } from 'react'
import { RouterProvider, useRoute, Link } from './lib/router'
import { usePoll } from './lib/api'
import Board from './screens/Board'
import Inbox from './screens/Inbox'
import Library from './screens/Library'
import New from './screens/New'
import Problem from './screens/Problem'
import Telemetry from './screens/Telemetry'
import type { Meta } from './lib/types'

function DaemonChip({ meta }: { meta: Meta | null }) {
  if (!meta) return <span className="px-2.5 text-xs text-ink-faint">engine…</span>
  const d = meta.daemon
  // a stop marker with no live process is idle, not stopping-forever
  const label = d.running ? (d.stopping ? 'stopping' : 'running') : 'idle'
  const dot = d.running ? (d.stopping ? 'bg-warn' : 'bg-ok animate-pulse') : 'bg-ink-faint'
  return (
    <Link
      to="/telemetry"
      className="group flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs whitespace-nowrap text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
      title={d.pid ? `engine pid ${d.pid} — open the Engine page` : 'engine not running — open the Engine page'}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      engine {label}
      {d.running && d.in_flight_leases > 0 && (
        <span className="tnum text-ink-faint">·{d.in_flight_leases}</span>
      )}
    </Link>
  )
}

const ICONS: Record<string, ReactNode> = {
  board: (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="4" cy="4" r="1.6" fill="currentColor" />
      <circle cx="12" cy="5.5" r="1.2" fill="currentColor" opacity="0.7" />
      <circle cx="7" cy="11.5" r="1.4" fill="currentColor" opacity="0.85" />
      <path d="M4 4l8 1.5M12 5.5l-5 6" stroke="currentColor" strokeWidth="0.8" opacity="0.45" />
    </svg>
  ),
  inbox: (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M2.5 9.5V12a1.5 1.5 0 001.5 1.5h8A1.5 1.5 0 0013.5 12V9.5M2.5 9.5L4.6 3.6A1.5 1.5 0 016 2.5h4a1.5 1.5 0 011.4 1.1l2.1 5.9M2.5 9.5H6l1 1.5h2l1-1.5h3.5"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  telemetry: (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M1.5 8.5h3l2-5 3 9 2-4h3"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  library: (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="5.7" y="5.7" width="4.6" height="4.6" transform="rotate(45 8 8)" fill="currentColor" opacity="0.9" />
      <circle cx="3" cy="12.5" r="1.1" fill="currentColor" opacity="0.6" />
      <circle cx="13" cy="3.5" r="1.1" fill="currentColor" opacity="0.6" />
    </svg>
  ),
}

function NavItem({
  to,
  icon,
  label,
  active,
  badge,
}: {
  to: string
  icon: string
  label: string
  active: boolean
  badge?: number
}) {
  return (
    <Link
      to={to}
      className={`group relative flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors duration-150 ${
        active ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:bg-surface-2/60 hover:text-ink'
      }`}
    >
      {active && (
        <span className="absolute top-1.5 bottom-1.5 -left-2 w-0.5 rounded-full bg-star" />
      )}
      <span className={active ? 'text-star' : 'text-ink-faint group-hover:text-ink-dim'}>
        {ICONS[icon]}
      </span>
      <span className="flex-1">{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="tnum rounded-full bg-warn/15 px-1.5 py-px text-[11px] font-medium text-warn">
          {badge}
        </span>
      )}
    </Link>
  )
}

function Shell() {
  const route = useRoute()
  const { data: meta } = usePoll<Meta>('/api/meta', 3000)
  const section = route.segments[0] ?? ''
  const workspaceName = meta ? (meta.workspace.split(/[\\/]/).pop() ?? '') : ''

  return (
    <div className="flex h-full">
      <aside className="flex w-52 shrink-0 flex-col border-r border-edge bg-surface px-3 py-4">
        <Link to="/" className="mb-1 flex items-center gap-2 px-2.5">
          {/* the mark IS an asterism: three stars, one line of sky */}
          <svg width="18" height="18" viewBox="0 0 20 20" className="text-star" aria-hidden>
            <path
              d="M4 14.5L10.5 5l5 6.5"
              stroke="currentColor"
              strokeWidth="0.9"
              opacity="0.5"
              fill="none"
            />
            <circle cx="4" cy="14.5" r="1.7" fill="currentColor" />
            <circle cx="10.5" cy="5" r="2.1" fill="currentColor" />
            <circle cx="15.5" cy="11.5" r="1.4" fill="currentColor" />
          </svg>
          <span className="font-display text-[17px] font-medium">Asterism</span>
        </Link>
        {/* workspace label only when it differs from the product name —
            otherwise "Asterism" would render three times in one column */}
        {workspaceName && workspaceName.toLowerCase() !== 'asterism' ? (
          <div className="mb-5 truncate px-2.5 text-[11px] text-ink-faint" title={meta?.workspace}>
            {workspaceName}
          </div>
        ) : (
          <div className="mb-4" />
        )}
        <nav className="flex flex-col gap-0.5">
          <NavItem
            to="/"
            icon="board"
            label="Board"
            active={section === '' || section === 'problems'}
          />
          <NavItem
            to="/library"
            icon="library"
            label="Library"
            active={section === 'library'}
          />
          <NavItem
            to="/inbox"
            icon="inbox"
            label="Inbox"
            active={section === 'inbox'}
            badge={meta?.inbox_count}
          />
          <NavItem
            to="/telemetry"
            icon="telemetry"
            label="Engine"
            active={section === 'telemetry'}
          />
        </nav>
        <div className="mt-auto flex flex-col gap-1">
          <DaemonChip meta={meta} />
          {meta?.db === 'behind' && (
            <span className="px-2.5 text-[11px] text-warn">db needs migration</span>
          )}
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        {/* no top chrome — the sidebar carries "where am I", each screen
            carries its own title, the constellation gets the sky */}
        <main className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
          {section === 'new' ? (
            <New />
          ) : section === 'inbox' ? (
            <Inbox />
          ) : section === 'library' ? (
            <Library />
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
