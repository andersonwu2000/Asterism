import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { RouterProvider, useRoute, Link } from './lib/router'
import { apiPost, usePoll } from './lib/api'
import Board from './screens/Board'
import Inbox from './screens/Inbox'
import Library from './screens/Library'
import LibraryChapterScreen from './screens/LibraryChapter'
import New from './screens/New'
import Papers, { PaperReader } from './screens/Papers'
import Problem from './screens/Problem'
import Run from './screens/Run'
import Setup from './screens/Setup'
import Telemetry from './screens/Telemetry'
import type { Meta } from './lib/types'

/** Global run strip: from any page, what is the engine doing right
 * now? Running → the problem it works (click lands on its cockpit) +
 * elapsed; idle → quiet; crashed last run → say so (a crash must not
 * wear the same face as a clean finish). */
function DaemonChip({ meta }: { meta: Meta | null }) {
  if (!meta) return <span className="px-2.5 text-xs text-ink-faint">engine…</span>
  const d = meta.daemon
  if (d.running) {
    const leaf = d.scope ? (d.scope.split('.').pop() ?? d.scope) : 'running'
    const mins = d.started_at
      ? Math.max(0, Math.floor((Date.now() - Date.parse(d.started_at)) / 60000))
      : null
    const elapsed = mins === null ? '' : mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h ${mins % 60}m`
    return (
      <Link
        to="/run"
        className="group flex min-w-0 items-center gap-2 rounded-md px-2.5 py-1.5 text-xs whitespace-nowrap text-ink transition-colors hover:bg-surface-2"
        title={
          d.stopping
            ? 'engine stopping — finishing in-flight work'
            : `engine working on ${d.scope ?? 'all problems'}${elapsed ? ` for ${elapsed}` : ''} — open the run console`
        }
      >
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${d.stopping ? 'bg-warn' : 'bg-ok animate-pulse'}`}
        />
        <span className="truncate font-mono text-[12px]">
          {d.stopping ? 'stopping' : leaf}
        </span>
        {!d.stopping && elapsed && <span className="tnum shrink-0 text-ink-faint">{elapsed}</span>}
      </Link>
    )
  }
  const crashed = d.last_exit !== null && d.last_exit.rc !== null && d.last_exit.rc !== 0
  return (
    <Link
      to="/run"
      className="group flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs whitespace-nowrap text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
      title={
        crashed
          ? `the last run exited abnormally: ${d.last_exit?.error ?? 'unknown error'} — open the run console`
          : 'engine not running — open the run console'
      }
    >
      <span className={`h-1.5 w-1.5 rounded-full ${crashed ? 'bg-warn' : 'bg-ink-faint'}`} />
      {crashed ? <span className="text-warn">last run crashed</span> : 'engine idle'}
    </Link>
  )
}

/** Engine-readiness banner: a missing Lean toolchain or Mathlib cache
 * fails every run just as silently as a missing login — point at the
 * wizard. 30s poll (cheap checks), hidden on the wizard itself. */
function SetupBanner({ section }: { section: string }) {
  const { data } = usePoll<{
    lake: { found: boolean }
    mathlib: { present: boolean }
  }>('/api/setup/status', 30000)
  if (!data || section === 'setup') return null
  if (data.lake.found && data.mathlib.present) return null
  return (
    <div className="flex items-center gap-3 border-b border-edge bg-surface-2 px-4 py-2 text-xs">
      <span className="bg-warn h-1.5 w-1.5 shrink-0 rounded-full" />
      <span className="text-ink">
        {data.lake.found
          ? 'The math library is not fetched yet — runs will fail.'
          : 'The Lean prover is not set up yet — runs will fail.'}
      </span>
      <Link
        to="/setup"
        className="rounded-md border border-edge bg-surface px-2.5 py-1 text-ink transition-colors hover:bg-surface-3"
      >
        Open the setup wizard
      </Link>
    </div>
  )
}

/** Auth banner — the one condition that silently fails EVERY run.
 * The login flow itself is Claude Code's own wizard; the button just
 * opens it in a terminal window, and the 3s meta poll turns the
 * banner off the moment the credentials land. */
function ClaudeBanner({ meta }: { meta: Meta | null }) {
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (!meta || (meta.claude?.installed && meta.claude?.logged_in)) return null
  const installed = meta.claude?.installed ?? false
  const openLogin = async () => {
    setBusy(true)
    setMsg(null)
    try {
      const r = await apiPost<{ opened: boolean; manual?: string }>('/api/claude/login', {})
      setMsg(
        r.opened
          ? 'a login window opened — finish there; this banner clears itself'
          : `couldn't open a terminal — run "${r.manual ?? 'claude'}" yourself`,
      )
    } catch (e) {
      setMsg(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex items-center gap-3 border-b border-edge bg-surface-2 px-4 py-2 text-xs">
      <span className="bg-warn h-1.5 w-1.5 shrink-0 rounded-full" />
      <span className="text-ink">
        {installed
          ? 'Claude Code is not logged in — runs will fail until you log in.'
          : 'Claude Code is not installed — double-click installer\\install.bat to set everything up.'}
      </span>
      {installed && (
        <button
          className="cursor-pointer rounded-md border border-edge bg-surface px-2.5 py-1 text-ink transition-colors hover:bg-surface-3"
          disabled={busy}
          onClick={() => void openLogin()}
        >
          Open the login window
        </button>
      )}
      {msg && <span className="text-ink-faint">{msg}</span>}
    </div>
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
  run: (
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
  settings: (
    // three sliders — the machine room's knobs
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M2 4.5h12M2 8h12M2 11.5h12" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" opacity="0.55" />
      <circle cx="10.5" cy="4.5" r="1.6" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
      <circle cx="5" cy="8" r="1.6" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
      <circle cx="8.5" cy="11.5" r="1.6" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
    </svg>
  ),
  library: (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="5.7" y="5.7" width="4.6" height="4.6" transform="rotate(45 8 8)" fill="currentColor" opacity="0.9" />
      <circle cx="3" cy="12.5" r="1.1" fill="currentColor" opacity="0.6" />
      <circle cx="13" cy="3.5" r="1.1" fill="currentColor" opacity="0.6" />
    </svg>
  ),
  papers: (
    // a sheet with a folded corner — the shelf of source papers
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M4.5 1.8h5.2l3 3v8.4a1 1 0 01-1 1H4.5a1 1 0 01-1-1V2.8a1 1 0 011-1z"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
      <path d="M9.7 1.8v3h3" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round" />
      <path d="M5.8 8h4.4M5.8 10.5h3" stroke="currentColor" strokeWidth="0.9" strokeLinecap="round" opacity="0.55" />
    </svg>
  ),
}

function NavItem({
  to,
  icon,
  label,
  active,
  badge,
  live = false,
}: {
  to: string
  icon: string
  label: string
  active: boolean
  badge?: number
  /** a pulsing dot: the machine is working behind this entry */
  live?: boolean
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
      {live && <span className="bg-ok h-1.5 w-1.5 animate-pulse rounded-full" />}
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
  // the tab title carries the inbox count — the one place a decision
  // can wait on the human while they look at another tab
  const inboxCount = meta?.inbox_count ?? 0
  useEffect(() => {
    document.title = inboxCount > 0 ? `(${inboxCount}) Asterism` : 'Asterism'
  }, [inboxCount])

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
            to="/run"
            icon="run"
            label="Run"
            active={section === 'run'}
            live={meta?.daemon.running ?? false}
          />
          <NavItem
            to="/library"
            icon="library"
            label="Library"
            active={section === 'library'}
          />
          <NavItem
            to="/papers"
            icon="papers"
            label="Papers"
            active={section === 'papers'}
          />
          <NavItem
            to="/inbox"
            icon="inbox"
            label="Inbox"
            active={section === 'inbox'}
            badge={meta?.inbox_count}
          />
          <NavItem
            to="/settings"
            icon="settings"
            label="Settings"
            active={section === 'settings' || section === 'telemetry'}
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
            carries its own title, the constellation gets the sky. The
            ONE exception: the auth banner (a silently-fatal state) */}
        <ClaudeBanner meta={meta} />
        <SetupBanner section={section} />
        <main className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
          {section === 'new' ? (
            <New />
          ) : section === 'inbox' ? (
            <Inbox />
          ) : section === 'library' ? (
            route.segments[1] ? (
              <LibraryChapterScreen problem={route.segments[1]} />
            ) : (
              <Library />
            )
          ) : section === 'papers' ? (
            route.segments[1] ? (
              <PaperReader id={route.segments[1]} />
            ) : (
              <Papers />
            )
          ) : section === 'run' ? (
            <Run />
          ) : section === 'setup' ? (
            <Setup />
          ) : section === 'settings' || section === 'telemetry' ? (
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
