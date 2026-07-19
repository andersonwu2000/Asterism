import { useCallback, useEffect, useState } from 'react'
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
import Engine from './screens/Engine'
import type { EngineTab } from './screens/Engine'
import ChatDrawer from './components/ChatDrawer'
import type { Meta } from './lib/types'

/** The explainer's door — the one utility slot at the sidebar's foot
 * (owner, 2026-07-18: chat entry outranks the old engine-status chip;
 * run liveness lives on the Engine nav row now). Pulse = an answer is
 * streaming behind a closed drawer. */
function AskChip({
  open,
  streaming,
  onToggle,
}: {
  open: boolean
  streaming: boolean
  onToggle: () => void
}) {
  return (
    <button
      onClick={onToggle}
      className={`group flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors duration-150 ${
        open ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:bg-surface-2/60 hover:text-ink'
      }`}
      title="ask the engine to explain progress, code or mechanics (Ctrl+/) — read-only, it never acts"
    >
      <span className={open ? 'text-star' : 'text-ink-faint group-hover:text-ink-dim'}>
        {ICONS.ask}
      </span>
      <span className="flex-1 text-left">ask</span>
      {streaming && !open && <span className="bg-ok h-1.5 w-1.5 animate-pulse rounded-full" />}
    </button>
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
          ? 'a browser tab opened — click Authorize; this banner clears itself'
          : `couldn't open a terminal — run "${r.manual ?? 'claude auth login'}" yourself`,
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
          : 'Claude Code is not installed — double-click Asterism.exe to install it.'}
      </span>
      {installed && (
        <button
          className="cursor-pointer rounded-lg border border-edge bg-surface px-2.5 py-1 text-ink transition-colors hover:bg-surface-3"
          disabled={busy}
          onClick={() => void openLogin()}
        >
          Log in with your browser
        </button>
      )}
      {msg && <span className="text-ink-faint">{msg}</span>}
    </div>
  )
}

/** Lean-layer self-check banner — the OTHER silently-fatal state (a
 * missing toolchain or math library fails every run just like a
 * missing login), and it can break long after install: a moved .elan,
 * a cleaned disk. Rides the same meta poll (server memoizes the
 * check); the remedy is re-running the setup, which skips whatever is
 * still healthy. */
function LeanBanner({ meta }: { meta: Meta | null }) {
  if (!meta?.lean_ready || (meta.lean_ready.lake && meta.lean_ready.mathlib)) return null
  return (
    <div className="flex items-center gap-3 border-b border-edge bg-surface-2 px-4 py-2 text-xs">
      <span className="bg-warn h-1.5 w-1.5 shrink-0 rounded-full" />
      <span className="text-ink">
        {meta.lean_ready.lake
          ? 'The math library is missing or incomplete — runs will fail. Double-click Asterism.exe to repair; finished parts are skipped.'
          : 'The Lean prover is missing or broken — runs will fail. Double-click Asterism.exe to repair; finished parts are skipped.'}
      </span>
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
    // two sliders — the machine room's knobs (three read as noise at 15px)
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M2 5.5h12M2 10.5h12" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" opacity="0.55" />
      <circle cx="10" cy="5.5" r="1.7" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
      <circle cx="6" cy="10.5" r="1.7" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
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
  ask: (
    // a speech bubble with a star inside — conversation about the sky
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M2.5 3.5A1.5 1.5 0 014 2h8a1.5 1.5 0 011.5 1.5v6A1.5 1.5 0 0112 11H7.2L4.5 13.6V11H4a1.5 1.5 0 01-1.5-1.5v-6z"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
      <circle cx="8" cy="6.5" r="1.3" fill="currentColor" opacity="0.85" />
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
  warn = false,
  title,
}: {
  to: string
  icon: string
  label: string
  active: boolean
  badge?: number
  /** a pulsing dot: the machine is working behind this entry */
  live?: boolean
  /** a steady warn dot: something behind this entry ended badly */
  warn?: boolean
  title?: string
}) {
  return (
    <Link
      to={to}
      title={title}
      className={`group relative flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors duration-150 ${
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
      {!live && warn && <span className="bg-warn h-1.5 w-1.5 rounded-full" />}
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
  // can wait on the human while they look at another tab — and names
  // the route (first-time QA: five open tabs all read "Asterism")
  const inboxCount = meta?.inbox_count ?? 0
  useEffect(() => {
    const detail = route.segments[1]
    const leaf =
      (section === 'problems' || section === 'library') && detail
        ? (detail.split('.').pop() ?? detail)
        : {
            engine: 'Engine',
            run: 'Engine',
            settings: 'Engine',
            telemetry: 'Engine',
            library: 'Library',
            papers: 'Papers',
            inbox: 'Inbox',
            new: 'New problem',
          }[section]
    const base = leaf ? `${leaf} — Asterism` : 'Asterism'
    document.title = inboxCount > 0 ? `(${inboxCount}) ${base}` : base
  }, [inboxCount, section, route.segments])

  // explainer drawer: open state persists (QPaper shape), width doesn't
  const [chatOpen, setChatOpen] = useState(
    () => localStorage.getItem('asterism.chatOpen') === '1',
  )
  const [chatStreaming, setChatStreaming] = useState(false)
  const setChat = useCallback((v: boolean | ((o: boolean) => boolean)) => {
    setChatOpen((o) => {
      const next = typeof v === 'function' ? v(o) : v
      localStorage.setItem('asterism.chatOpen', next ? '1' : '0')
      return next
    })
  }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && !e.altKey && !e.metaKey && e.key === '/') {
        e.preventDefault()
        setChat((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setChat])

  const d = meta?.daemon
  const engineCrashed =
    d != null && !d.running && d.last_exit !== null &&
    d.last_exit.rc !== null && d.last_exit.rc !== 0

  // NO beforeunload prompt for a live run (owner, 2026-07-18, same
  // day it shipped): the browser's generic dialog says "changes may
  // not be saved" — implying unsaved work that doesn't exist — and
  // cannot carry the actual message. The truth ("closing this page
  // does NOT stop the engine") lives as plain words on the surfaces
  // where the run is watched: the console status line and the problem
  // page's engine strip.

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
          {/* ONE door for the machine (owner, 2026-07-14): console,
              manifest steering, settings and the usage ledger are four
              faces of the same engine — Run + Settings had begun
              duplicating its cost surfaces across two pages */}
          <NavItem
            to="/engine"
            icon="run"
            label="Engine"
            active={
              section === 'engine' ||
              section === 'run' ||
              section === 'settings' ||
              section === 'telemetry'
            }
            live={(d?.running || d?.starting) ?? false}
            warn={engineCrashed}
            title={
              engineCrashed
                ? `the last run exited abnormally: ${d?.last_exit?.error ?? 'unknown error'} — open the console`
                : undefined
            }
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
        </nav>
        <div className="mt-auto flex flex-col gap-1">
          <AskChip
            open={chatOpen}
            streaming={chatStreaming}
            onToggle={() => setChat((o) => !o)}
          />
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
        <LeanBanner meta={meta} />
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
          ) : section === 'engine' ? (
            <Engine
              tab={
                (['manifest', 'settings', 'usage'].includes(
                  route.segments[1] ?? '',
                )
                  ? route.segments[1]
                  : 'console') as EngineTab
              }
            />
          ) : section === 'run' ? (
            // legacy routes keep working — same machine, new door
            <Engine tab="console" />
          ) : section === 'settings' || section === 'telemetry' ? (
            <Engine tab="settings" />
          ) : section === 'problems' && route.segments[1] ? (
            <Problem name={route.segments[1]} />
          ) : (
            <Board />
          )}
        </main>
      </div>
      <ChatDrawer
        open={chatOpen}
        onClose={() => setChat(false)}
        onStreamingChange={setChatStreaming}
      />
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
