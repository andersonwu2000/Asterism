import { useCallback, useEffect, useState } from 'react'
import { RouterProvider, useRoute, navigate } from './lib/router'
import { apiPost, usePoll } from './lib/api'
import { parseProjectRoute, projectPath } from './lib/projectRoute'
import Projects from './screens/Projects'
import ProjectShell from './screens/ProjectShell'
import New from './screens/New'
import Papers, { PaperReader } from './screens/Papers'
import Settings from './screens/Settings'
import AssistantPanel from './components/AssistantPanel'
import type { BoardResponse, Meta } from './lib/types'
import { isStopped, onStopped } from './lib/shutdown'

/*
 * The shell (human_interface_design.md §1.4). Two frames, and only
 * two: the Project picker, and the inside of one Project. There is no
 * sidebar any more — a Project's sections are a horizontal menu in its
 * own header, and the tasks are the column beside them.
 *
 * Everything global that is not a Project lives at one address each:
 * #/settings is the gear, #/new mints a task, #/papers is the shelf a
 * task binds its sources from. The banners below are the exception the
 * old shell also made: a state that silently fails EVERY run has to
 * speak wherever the reader is standing.
 */

/** An update was unzipped over a LIVE console: the pages now come from
 * the new release while this process still answers with the old
 * endpoints. Nothing else can say so — the stale process cannot know on
 * its own which of its answers are lies. */
function UpdateBanner({ meta }: { meta: Meta | null }) {
  const v = meta?.version ?? null
  const disk = meta?.disk_version ?? null
  if (!v || !disk || v === disk) return null
  return (
    <div className="flex items-center gap-3 border-b border-edge bg-surface-2 px-4 py-2 text-xs">
      <span className="bg-warn h-1.5 w-1.5 shrink-0 rounded-full" />
      <span className="text-ink">
        a newer Asterism is on disk — quit from Settings, then open Asterism.exe again to
        finish the update
      </span>
      <span className="font-mono text-[10px] text-ink-faint">
        {v.slice(0, 8)} → {disk.slice(0, 8)}
      </span>
    </div>
  )
}

/** Auth: the one condition that silently fails every run. The login
 * flow is Claude Code's own wizard; the button opens it in a terminal,
 * and the meta poll turns the banner off when the credentials land. */
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

/** The OTHER silently-fatal state: a missing toolchain or math library
 * fails every run just like a missing login, and it can break long
 * after install (a moved .elan, a cleaned disk). */
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

/** The addresses the old app used, kept working. A problem's page is
 * now inside its Project, and only the DB knows which shelf that is
 * (§3.1: the name's first segment is a default, not the answer) — so
 * the redirect asks, rather than splitting the name and guessing. */
function LegacyProblem({ name, goal }: { name: string; goal: number | null }) {
  const { data, error } = usePoll<BoardResponse>('/api/problems', 0)
  useEffect(() => {
    if (!data) return
    const row = data.problems.find((p) => p.name === name)
    if (!row?.project) {
      navigate('/')
      return
    }
    navigate(projectPath(row.project, 'sky', name, goal))
  }, [data, name, goal])
  if (error) {
    navigate('/')
    return null
  }
  return <div className="late-fade p-8 text-sm text-ink-faint">Opening {name}…</div>
}

function Shell() {
  const route = useRoute()
  const section = route.segments[0] ?? ''
  const project = parseProjectRoute(route.segments)
  const { data: meta } = usePoll<Meta>(
    project ? `/api/meta?project=${encodeURIComponent(project.project)}` : '/api/meta',
    3000,
  )

  // the tab title names where you are and carries the count of things
  // waiting on you — the one fact that can change while you look at
  // another tab
  const inboxCount = meta?.inbox_count ?? 0
  useEffect(() => {
    const leaf = project
      ? (project.problem?.split('.').pop() ?? project.project)
      : { settings: 'Settings', new: 'New task', papers: 'Papers' }[section]
    const base = leaf ? `${leaf} — Asterism` : 'Asterism'
    document.title = inboxCount > 0 ? `(${inboxCount}) ${base}` : base
  }, [inboxCount, section, project])

  // the Assistant drawer: open state persists, width does not
  const [chatOpen, setChatOpen] = useState(
    () => localStorage.getItem('asterism.chatOpen') === '1',
  )
  const [chatStreaming, setChatStreaming] = useState(false)
  // an answer that landed while the panel was closed: the glyph says so
  // until the panel is opened (§1.4-2 — the closed glyph carries state)
  const [chatUnread, setChatUnread] = useState(false)
  const setChat = useCallback((v: boolean | ((o: boolean) => boolean)) => {
    setChatOpen((o) => {
      const next = typeof v === 'function' ? v(o) : v
      localStorage.setItem('asterism.chatOpen', next ? '1' : '0')
      if (next) setChatUnread(false)
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

  // the task column's fold, remembered: it is a reading posture, not a
  // per-page choice
  const [railOpen, setRailOpen] = useState(
    () => localStorage.getItem('asterism.railOpen') !== '0',
  )
  const toggleRail = useCallback(
    () =>
      setRailOpen((o) => {
        localStorage.setItem('asterism.railOpen', o ? '0' : '1')
        return !o
      }),
    [],
  )

  // NO beforeunload prompt for a live run (owner, 2026-07-18): the
  // browser's generic dialog implies unsaved work that doesn't exist.
  // The truth ("closing this page does NOT stop the engine") is plain
  // words on the surfaces where the run is watched.

  return (
    <div className="flex h-full flex-col">
      <UpdateBanner meta={meta} />
      <ClaudeBanner meta={meta} />
      <LeanBanner meta={meta} />
      <div className="flex min-h-0 flex-1">
        <main className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
          {project ? (
            <ProjectShell
              route={project}
              railOpen={railOpen}
              onToggleRail={toggleRail}
              chatOpen={chatOpen}
              chatStreaming={chatStreaming}
              chatUnread={chatUnread}
              onToggleChat={() => setChat((o) => !o)}
            />
          ) : section === 'settings' ? (
            <Settings />
          ) : section === 'new' ? (
            /* `#/new/<project>` files the task on that shelf (§3.1: the
               name's first segment is only a default) */
            <New project={route.segments[1] ?? null} />
          ) : section === 'papers' ? (
            route.segments[1] ? (
              <PaperReader id={route.segments[1]} />
            ) : (
              <Papers />
            )
          ) : section === 'problems' && route.segments[1] ? (
            <LegacyProblem
              name={route.segments[1]}
              goal={
                route.segments[2] === 'g' && route.segments[3]
                  ? Number(route.segments[3])
                  : null
              }
            />
          ) : (
            <Projects />
          )}
        </main>
        <AssistantPanel
          open={chatOpen}
          onClose={() => setChat(false)}
          onStreamingChange={setChatStreaming}
          onReplyWaiting={setChatUnread}
        />
      </div>
    </div>
  )
}

/** After the console quits itself, the page outlives its server. It
 * says so plainly instead of decaying into failed polls — and names the
 * way back, because the launcher is how this starts again. */
function Farewell() {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-3 bg-bg text-center">
      <svg width="30" height="30" viewBox="0 0 20 20" className="text-ink-faint" aria-hidden>
        <path d="M4 14.5L10.5 5l5 6.5" stroke="currentColor" strokeWidth="0.8" opacity="0.4" fill="none" />
        <circle cx="4" cy="14.5" r="1.5" fill="currentColor" opacity="0.35" />
        <circle cx="10.5" cy="5" r="1.9" fill="currentColor" opacity="0.35" />
        <circle cx="15.5" cy="11.5" r="1.2" fill="currentColor" opacity="0.35" />
      </svg>
      <div className="font-display text-[19px] text-ink-dim">Asterism has stopped</div>
      <div className="max-w-sm text-xs leading-relaxed text-ink-faint">
        The engine, the Lean gateway and this console are all closed, and the port is
        free. Your work is on disk — start Asterism again whenever you like.
      </div>
      <div className="mt-1 text-[11px] text-ink-faint/70">You can close this tab.</div>
    </div>
  )
}

export default function App() {
  const [gone, setGone] = useState(isStopped())
  useEffect(() => onStopped(() => setGone(true)), [])
  if (gone) return <Farewell />
  return (
    <RouterProvider>
      <Shell />
    </RouterProvider>
  )
}
