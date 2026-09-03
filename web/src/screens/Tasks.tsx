import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { projectPath } from '../lib/projectRoute'
import { scopeCovers } from '../lib/programmeFocus'
import { RunConfirm } from '../components/CommandConfirm'
import { Button, StatusBadge } from '../components/ui'
import IntentEditor from '../components/IntentEditor'
import RunControl from '../components/RunControl'
import RunParameters from '../components/RunParameters'
import Inbox from './Inbox'
import type { BoardProblem, DaemonStatus } from '../lib/types'

/*
 * Tasks — the shelf, and the engine control that acts on it
 * (human_interface_design.md §1.4-2, first bullet).
 *
 * Two addresses, because they answer two questions. `#/p/<x>/tasks` is
 * the shelf: what is here, what needs you, what to run. Add a task name
 * and it is that task's own page: run it, and say what you want proved.
 *
 * The run PARAMETERS live here rather than in the settings page for the
 * owner's stated reason — "每次 run 都可能改的東西不藏在設定": a thing you
 * reconsider every run is part of pressing Run, not part of configuring
 * the installation.
 */

/* ------------------------------------------------------------------ */
/* the shelf                                                          */
/* ------------------------------------------------------------------ */

const STATUS_ORDER = [
  'awaiting_human',
  'signoff_pending',
  'stalled',
  'proving',
  'paused',
  'ingested',
  'bridged',
  'idle',
]

const WEEK_MS = 7 * 86400_000

function GoalCounts({ p }: { p: BoardProblem }) {
  if (p.goals.total === 0 || (p.goals.open === 0 && p.goals.proved === 0)) return null
  const rest = Math.max(0, p.goals.total - p.goals.proved - p.goals.open)
  return (
    <span
      className="tnum text-xs whitespace-nowrap text-ink-dim"
      title={`${p.goals.proved} proved · ${p.goals.open} open${
        rest > 0 ? ` · ${rest} shelved/dead` : ''
      } of ${p.goals.total} goals`}
    >
      {p.goals.proved}/{p.goals.total} proved
    </span>
  )
}

function Row({
  p,
  project,
  picked,
  onPick,
}: {
  p: BoardProblem
  project: string
  picked: boolean
  onPick: (name: string, on: boolean) => void
}) {
  const to = projectPath(project, 'tasks', p.name)
  return (
    <tr
      data-kind="task"
      className="cursor-pointer border-b border-edge/60 transition-colors duration-150 hover:bg-surface"
      title={p.last_event ? `last event ${relTime(p.last_event)}` : undefined}
      onClick={() => navigate(to)}
    >
      <td className="w-8 pl-3">
        <input
          type="checkbox"
          checked={picked}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onPick(p.name, e.target.checked)}
          title="run this task in the next run"
          className="cursor-pointer align-middle"
        />
      </td>
      <td className="h-9 pr-4">
        <span className="flex min-w-0 items-center gap-2">
          <Link
            to={to}
            className="truncate font-mono text-[13px] text-ink"
            title={p.name}
            onClick={(e) => e.stopPropagation()}
          >
            {p.name.replace(/^.*\./, '')}
          </Link>
          {p.in_flight > 0 && (
            <span
              className="tnum flex shrink-0 items-center gap-1.5 text-[11px] text-accent"
              title={`${p.in_flight} agent${p.in_flight === 1 ? '' : 's'} working this task right now`}
            >
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
              {p.in_flight}
            </span>
          )}
          {/* exception ink only: a benched task reads "paused"/"idle"
              like any other quiet one, so the chip cannot say a PERSON
              took it off the live path — this is the only mark that
              tells the two apart */}
          {p.benched === true && (
            <span
              className="shrink-0 font-sans text-[11px] text-ink-faint"
              title="you took this task off the live path — dispatch skips it until you put it back"
            >
              benched
            </span>
          )}
        </span>
      </td>
      <td className="pr-4">
        <StatusBadge status={p.status} />
      </td>
      <td className="pr-3 text-right">
        <GoalCounts p={p} />
      </td>
    </tr>
  )
}

function SectionRow({ label, count, note }: { label: string; count: number; note?: ReactNode }) {
  return (
    <tr>
      <td colSpan={4} className="pt-5 pb-1.5 pl-3">
        <span className="text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
          {label}
        </span>
        <span className="tnum ml-2 text-[11px] text-ink-faint/70">{count}</span>
        {note && <span className="ml-3 text-[11px] text-ink-dim">{note}</span>}
      </td>
    </tr>
  )
}

/** Start a run over the ticked tasks — the explicit-list endpoint
 * (§3.3): every name is verified, no pattern is ever accepted. Stop is
 * here too, with the force step, because this is the page that owns the
 * engine's start and end. */
function RunBar({
  project,
  picked,
  onClear,
}: {
  project: string
  picked: string[]
  onClear: () => void
}) {
  const { data: d, refresh } = usePoll<DaemonStatus>('/api/daemon', 2000)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [confirmForce, setConfirmForce] = useState(false)
  /** the run's confirm window (§1.3): a preview per ticked name, in the
   * same floating window every other consequential act wears */
  const [confirmRun, setConfirmRun] = useState(false)
  const timer = useRef<number | null>(null)
  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )
  // never nothing: the control is the reason this card exists, and a
  // vanished button for the beat before the first poll answers reads as
  // "you cannot run this" (screenshot pass, 2026-09-03)
  if (!d)
    return (
      <div className="flex items-center gap-3">
        <Button variant="primary" disabled>
          Run
        </Button>
        <span className="text-[11px] text-ink-faint">asking the engine what it is doing…</span>
      </div>
    )
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setMsg(null)
    try {
      await fn()
      onClear()
    } catch (e) {
      setMsg(String((e as Error).message))
    } finally {
      setBusy(false)
      setConfirmForce(false)
      refresh()
    }
  }
  const running = d.running || d.starting
  return (
    <div className="flex flex-wrap items-center gap-3">
      {running ? (
        <>
          <span className="flex items-center gap-2 text-xs text-accent">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            {d.stopping
              ? 'stopping — finishing in-flight work'
              : d.gateway === 'warming'
                ? 'warming the Lean toolchain'
                : 'engine running'}
          </span>
          <span className="font-mono text-[11px] text-ink-faint">{d.scope ?? 'all tasks'}</span>
          {confirmForce ? (
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => void act(() => apiPost('/api/daemon/stop', { force: true }))}
              title="kill the engine now; stranded leases are reclaimed"
            >
              Confirm force stop
            </Button>
          ) : (
            <Button
              disabled={busy}
              onClick={() => {
                if (d.stopping) {
                  setConfirmForce(true)
                  if (timer.current !== null) window.clearTimeout(timer.current)
                  timer.current = window.setTimeout(() => setConfirmForce(false), 3000)
                } else {
                  void act(() => apiPost('/api/daemon/stop', { force: false }))
                }
              }}
              title={d.stopping ? 'already stopping — press again to force' : 'finish in-flight work, then exit'}
            >
              {d.stopping ? 'Force stop…' : 'Stop'}
            </Button>
          )}
        </>
      ) : (
        <>
          <Button
            variant="primary"
            disabled={busy || picked.length === 0}
            title={
              picked.length === 0
                ? 'tick the tasks to run — the engine takes an explicit list, never a pattern'
                : `read what running ${picked.length} task${picked.length === 1 ? '' : 's'} would do`
            }
            onClick={() => setConfirmRun(true)}
          >
            {busy ? 'Starting…' : `Run${picked.length > 0 ? ` ${picked.length}` : ''}…`}
          </Button>
          {/* the names are no longer the sentence: WHAT would happen to
              them is, and the window is where that is read */}
          <span className="text-[11px] text-ink-faint">
            {picked.length === 0
              ? 'tick a task to run it — several is one run over an explicit list'
              : 'the next step reads what each one would do'}
          </span>
        </>
      )}
      {msg && <span className="text-[11px] text-danger">{msg}</span>}
      {confirmRun && (
        <RunConfirm
          project={project}
          problems={picked}
          onClose={() => setConfirmRun(false)}
          onStarted={() => {
            onClear()
            refresh()
          }}
        />
      )}
    </div>
  )
}

function Shelf({ project, rows }: { project: string; rows: BoardProblem[] }) {
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')
  const { data: daemon } = usePoll<DaemonStatus>('/api/daemon', 5000)
  const q = query.trim().toLowerCase()
  const filtering = q !== ''
  const sorted = [...rows]
    .filter((p) => q === '' || p.name.toLowerCase().includes(q))
    .sort(
      (a, b) =>
        STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) ||
        (b.last_event ?? '').localeCompare(a.last_event ?? ''),
    )
  const now = Date.now()
  const needsYou = sorted.filter(
    (p) =>
      p.status === 'awaiting_human' || p.status === 'signoff_pending' || p.status === 'stalled',
  )
  const inMotion = sorted.filter(
    (p) => !needsYou.includes(p) && (p.status === 'proving' || p.in_flight > 0),
  )
  const hot = new Set([...needsYou, ...inMotion].map((p) => p.name))
  const recent = sorted.filter(
    (p) =>
      !hot.has(p.name) &&
      ((p.last_event !== null && now - Date.parse(p.last_event) < WEEK_MS) ||
        (p.status === 'idle' && now - Date.parse(p.created_at) < 2 * 86400_000)),
  )
  for (const p of recent) hot.add(p.name)
  const settled = sorted.filter((p) => !hot.has(p.name))

  const pick = (name: string, on: boolean) =>
    setPicked((old) => {
      const next = new Set(old)
      if (on) next.add(name)
      else next.delete(name)
      return next
    })
  const row = (p: BoardProblem) => (
    <Row key={p.name} p={p} project={project} picked={picked.has(p.name)} onPick={pick} />
  )

  return (
    <div className="mx-auto max-w-4xl px-6 py-6">
      <Inbox project={project} />
      <section className="mb-6 flex flex-col gap-3 rounded-xl border border-edge bg-surface px-4 py-3">
        <RunBar project={project} picked={[...picked]} onClear={() => setPicked(new Set())} />
        <RunParameters running={daemon?.running ?? false} />
      </section>

      <div className="mb-2 flex items-center gap-3">
        <input
          className="w-64 rounded-lg border border-edge bg-surface px-2.5 py-1.5 text-xs text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          placeholder="filter tasks…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setQuery('')
              e.currentTarget.blur()
            }
          }}
        />
        {filtering && <span className="tnum text-[11px] text-ink-faint">{sorted.length}</span>}
        <Link
          to={`/new/${encodeURIComponent(project)}`}
          className="ml-auto rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-bg transition-colors hover:bg-starlight"
          title={`a new task, filed on ${project}`}
        >
          New task
        </Link>
      </div>

      {rows.length === 0 ? (
        <div className="py-16 text-center text-xs text-ink-faint">
          No tasks on this shelf yet — “New task” describes one in plain language.
        </div>
      ) : (
        <table className="w-full table-fixed border-collapse text-left">
          <colgroup>
            <col className="w-8" />
            <col />
            <col className="w-[132px]" />
            <col className="w-[128px]" />
          </colgroup>
          <tbody>
            {filtering ? (
              sorted.map(row)
            ) : (
              <>
                {needsYou.length > 0 && (
                  <>
                    <SectionRow label="Needs you" count={needsYou.length} />
                    {needsYou.map(row)}
                  </>
                )}
                {inMotion.length > 0 && (
                  <>
                    <SectionRow label="In motion" count={inMotion.length} />
                    {inMotion.map(row)}
                  </>
                )}
                {recent.length > 0 && (
                  <>
                    <SectionRow label="Recent" count={recent.length} />
                    {recent.map(row)}
                  </>
                )}
                {settled.length > 0 && (
                  <>
                    <SectionRow label="Older" count={settled.length} />
                    {settled.map(row)}
                  </>
                )}
              </>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* one task                                                           */
/* ------------------------------------------------------------------ */

/** Destruction tier (owner, 2026-07-09): deleting a task erases its
 * folder, proofs and history — a floating confirm whose red button (the
 * achromatic law's one sanctioned exception) unlocks only when the name
 * is typed back. The real guards live in the chokepoint. */
function DeleteTask({ problem, project }: { problem: string; project: string }) {
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const match = typed === problem
  useEffect(() => {
    if (!open || busy) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, busy])
  const doDelete = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiPost(`/api/problems/${encodeURIComponent(problem)}/delete`, {})
      navigate(projectPath(project, 'tasks'))
    } catch (e) {
      setError(String((e as Error).message))
      setBusy(false)
    }
  }
  return (
    <div className="pt-1 pb-8">
      <button
        className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink-dim"
        onClick={() => {
          setTyped('')
          setError(null)
          setOpen(true)
        }}
      >
        delete this task…
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-bg/70"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-[26rem] rounded-xl border border-edge bg-surface p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-sm font-medium text-ink">Delete {problem}?</div>
            <p className="mt-2 text-xs leading-relaxed text-ink-dim">
              Erases this task's folder, proofs and history. It cannot be undone.
            </p>
            <input
              className="mt-3 w-full rounded-md border border-edge bg-bg px-2 py-1.5 font-mono text-xs text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
              placeholder={`type ${problem} to confirm`}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoFocus
            />
            {error && <div className="mt-2 text-xs text-danger">{error}</div>}
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <button
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  match && !busy
                    ? 'cursor-pointer bg-destruct text-starlight hover:opacity-90'
                    : 'cursor-default border border-edge text-ink-faint'
                }`}
                disabled={!match || busy}
                onClick={() => void doDelete()}
              >
                {busy ? 'Deleting…' : 'Delete forever'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function OneTask({
  project,
  problem,
  row,
}: {
  project: string
  problem: string
  row: BoardProblem | undefined
}) {
  const { data: daemon } = usePoll<DaemonStatus>('/api/daemon', 3000)
  const [, setDirty] = useState(false)
  const mine = daemon?.running === true && scopeCovers(daemon.scope, problem)
  return (
    // no horizontal padding of its own: the intent editor brings the
    // page's gutter, and two of them put the header a notch left of
    // everything it introduces
    <div className="mx-auto max-w-4xl py-6">
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 px-6">
        <span className="font-mono text-sm text-ink">{problem}</span>
        {row && <StatusBadge status={row.status} />}
        <span className="ml-auto flex items-center gap-3">
          <RunControl problem={problem} engineHref={projectPath(project, 'engine')} />
        </span>
      </div>
      <div className="px-6">
        <RunParameters running={daemon?.running ?? false} />
      </div>
      <div className="mt-3 mb-3 px-6 text-[11px] text-ink-faint">
        {mine
          ? 'the run is live — what you save below reaches the next agent it spawns, no restart'
          : 'what you save below applies when the next run starts'}
      </div>
      <IntentEditor
        problem={problem}
        project={project}
        onDirtyChange={setDirty}
        bridged={row?.status === 'bridged'}
        shelfHref={projectPath(project, 'tasks')}
      />
      <div className="px-6">
        <DeleteTask problem={problem} project={project} />
      </div>
    </div>
  )
}

export default function Tasks({
  project,
  rows,
  problem,
}: {
  project: string
  rows: BoardProblem[]
  problem: string | null
}) {
  if (problem === null) return <Shelf project={project} rows={rows} />
  return (
    <OneTask
      key={problem}
      project={project}
      problem={problem}
      row={rows.find((p) => p.name === problem)}
    />
  )
}
