import { useState } from 'react'
import { usePoll } from '../lib/api'
import { Link } from '../lib/router'
import RunConsole, { CycleLine } from './Run'
import { SettingsTab, UsageTab } from './Telemetry'
import IntentEditor from '../components/IntentEditor'
import ProgrammeView from '../components/ProgrammeView'
import Timeline from '../components/Timeline'
import { cycleForGroup, resolveGroup, seatedGroups } from '../lib/programmeFocus'
import { ErrorState, TabNav } from '../components/ui'
import type { DaemonStatus, Programme, RunStatus } from '../lib/types'

/*
 * Engine — the machine's one door (owner, 2026-07-14: Run + Settings
 * described the same machine from two pages, and the cost surfaces
 * had started duplicating). Four faces of one thing:
 *   Console  — what is it doing right now (instruments, not knobs)
 *   Intent   — steer the live run (hot-reloaded instructions)
 *   Settings — knobs + account (read once at run start)
 *   Usage    — the ledger (per-problem, per-agent-kind)
 * Page anatomy matches Problem/Library chapter exactly: title, TabNav,
 * content — one container, no extra rules.
 */

export type EngineTab =
  | 'console'
  | 'intent'
  | 'programme'
  | 'timeline'
  | 'settings'
  | 'usage'

const TABS: { id: EngineTab; label: string; href: string; title?: string }[] = [
  { id: 'console', label: 'Console', href: '/engine' },
  {
    id: 'intent',
    label: 'Intent',
    href: '/engine/intent',
    title: 'steer the live run — what you asked for, saved straight to the next agent,'
      + ' no restart',
  },
  {
    id: 'programme',
    label: 'Programme',
    href: '/engine/programme',
    title: "what the engine currently argues — its own case for the route it is taking",
  },
  {
    id: 'timeline',
    label: 'Timeline',
    href: '/engine/timeline',
    title:
      'what has happened on this run — every state change, newest first,' +
      ' across every problem under the scope',
  },
  { id: 'settings', label: 'Settings', href: '/engine/settings' },
  { id: 'usage', label: 'Usage', href: '/engine/usage' },
]

/** The steering face: the LIVE run's intent, editable in place —
 * the goal and your standing word are read fresh by each agent at
 * spawn, so this is the one lever that reaches a run in flight. */
function SteerIntent() {
  const { data } = usePoll<DaemonStatus>('/api/daemon', 3000)
  const { data: run } = usePoll<RunStatus>('/api/run', 5000)
  const [, setDirty] = useState(false)
  // the engine's scope while running; the last run's focus when idle
  const problem = data?.scope ?? run?.problem ?? null
  if (!problem)
    return (
      <p className="mt-6 text-xs text-ink-faint">
        No run in focus — open a problem on the{' '}
        <Link to="/" className="underline decoration-edge-strong underline-offset-2 hover:text-ink">
          Board
        </Link>{' '}
        to edit its instructions there.
      </p>
    )
  return (
    <div className="mt-4">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs">
        <Link
          to={`/problems/${encodeURIComponent(problem)}`}
          className="font-mono text-ink underline decoration-edge-strong underline-offset-2 hover:text-starlight"
          title="open the problem — sky, goals, timeline"
        >
          {problem}
        </Link>
        <span className="text-ink-faint">
          {data?.running
            ? 'the run is live — saved instructions reach the next agent it spawns, no restart'
            : 'saved instructions apply when the next run starts'}
        </span>
      </div>
      <IntentEditor problem={problem} onDirtyChange={setDirty} bridged={false} />
    </div>
  )
}

/** The argument face: the SAME Programme the problem page archives,
 * read while the machine argues it. Two things the archive has no use
 * for ride along — the live proposal↔reviewer cycle, and which group
 * is actually seated right now (the tab follows the run, so a watcher
 * never has to pick). Owner, 2026-08-02: during a run this is the most
 * readable account of where the work is — more so than opening stars
 * one Lean statement at a time. */
function RunProgramme() {
  const { data: daemon } = usePoll<DaemonStatus>('/api/daemon', 3000)
  const { data: run } = usePoll<RunStatus>('/api/run', 5000)
  // three states, not two: undefined = follow the run, null = the
  // reader chose the problem's own argument, a number = that group
  const [pick, setPick] = useState<number | null | undefined>(undefined)
  const problem = daemon?.scope ?? run?.problem ?? null
  // Sibling groups run CONCURRENTLY (that is what the tree buys), so
  // "the seated strategist" can be several — the selection and cycle
  // laws live in lib/programmeFocus, tested there.
  const workers = run?.workers ?? []
  const seats = seatedGroups(workers)
  const liveIds = seats.map((s) => s.group.id)
  // each seated group's argument phase, so the tree says what every
  // branch is doing without opening them one at a time
  const livePhase: Record<number, string> = {}
  for (const s of seats) {
    const c = s.worker.cycle
    livePhase[s.group.id] = c
      ? c.phase === 'proposing'
        ? 'proposing'
        : `round ${c.round} ${c.phase}`
      : 'thinking'
  }
  const group = resolveGroup(pick, workers)
  const { data, error, stale } = usePoll<Programme>(
    problem
      ? `/api/problems/${encodeURIComponent(problem)}/programme` +
          (group !== null ? `?group=${group}` : '')
      : null,
    15000,
    // switching branch swaps ONE panel on an otherwise unchanged page:
    // unmounting it read as a flash (owner, 2026-08-07)
    { keepPrevious: true },
  )
  // The cycle shown must belong to the argument ON SCREEN — matched by
  // the resolved group id the server reports, so a sibling's round is
  // never narrated over this body.
  const cycle = cycleForGroup(workers, data?.group_id)
  if (!problem)
    return (
      <p className="mt-6 text-xs text-ink-faint">
        No run in focus — open a problem on the{' '}
        <Link to="/" className="underline decoration-edge-strong underline-offset-2 hover:text-ink">
          Board
        </Link>{' '}
        to read its programme there.
      </p>
    )
  if (error) return <ErrorState error={error} />
  if (!data) return null
  return (
    <div className="mt-4">
      <ProgrammeView
        data={data}
        group={group}
        liveIds={liveIds}
        livePhase={livePhase}
        onPickGroup={setPick}
        stale={stale}
        // a brick opens on the Engine's OWN sky — the console is one
        // tab away, and leaving the Engine to read a node it can show
        // is the defect the link audit removed
        brickHome="/engine"
        extra={
          cycle ? (
            <div className="mb-4 rounded-xl border border-edge bg-surface px-3.5 py-2.5">
              <div className="text-[11px] tracking-wider text-ink-faint uppercase">
                being revised right now
              </div>
              <CycleLine cycle={cycle} />
            </div>
          ) : null
        }
      />
    </div>
  )
}

export default function Engine({ tab }: { tab: EngineTab }) {
  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <h1 className="font-display text-[22px] font-medium text-ink">Engine</h1>
      <TabNav className="mt-3" tabs={TABS} active={tab} />
      {tab === 'console' && <RunConsole />}
      {tab === 'intent' && <SteerIntent />}
      {tab === 'programme' && <RunProgramme />}
      {tab === 'timeline' && (
        /* The run's own framing of the problem page's log (`419dcb31`'s
           law: what you read while watching belongs on the page you
           watch from). A tab, not a strip under the slots — the
           Intent and the Programme are carried over the same way, and
           a document does not live in an instrument's footer (owner,
           2026-08-07). */
        <div className="mt-5">
          <Timeline path="/api/run/events" pollMs={10000} showProblem />
        </div>
      )}
      {tab === 'settings' && (
        <div className="mt-5">
          <SettingsTab />
        </div>
      )}
      {tab === 'usage' && (
        <div className="mt-5">
          <UsageTab />
        </div>
      )}
    </div>
  )
}
