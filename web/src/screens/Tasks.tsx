import { useCallback, useState } from 'react'
import type { ReactNode } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { projectPath, shelfOrder } from '../lib/projectRoute'
import { scopeCovers } from '../lib/programmeFocus'
import { RunConfirm } from '../components/CommandConfirm'
import { ConfirmWindow } from '../components/ConfirmWindow'
import { Button, StatusBadge } from '../components/ui'
import IntentEditor from '../components/IntentEditor'
import RunControl, { StopButton } from '../components/RunControl'
import RunParameters from '../components/RunParameters'
import CollectionSearch from '../components/CollectionSearch'
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

const WEEK_MS = 7 * 86400_000

function GoalCounts({ p }: { p: BoardProblem }) {
  if (p.goals.total === 0 || (p.goals.open === 0 && p.goals.proved === 0)) return null
  return (
    <span
      className="tnum text-xs whitespace-nowrap text-ink-dim"
      title="Proof inventory, not a completion percentage for the main question"
    >
      {p.goals.proved} proved · {p.goals.open} open
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
          aria-label={`Select ${p.name} for the next run`}
          className="cursor-pointer align-middle"
        />
      </td>
      <td className="py-4 pr-4">
        <span className="flex min-w-0 items-center gap-2">
          <Link
            to={to}
            className="truncate font-mono text-sm text-ink"
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
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-dim">
          {(['sky', 'groups', 'timeline'] as const).map(section => (
            <Link key={section} to={projectPath(project, section, p.name)}
              onClick={e => e.stopPropagation()}
              className="transition-colors hover:text-ink hover:underline"
              aria-label={`${section === 'sky' ? 'Proof map' : section === 'groups' ? 'Read the argument' : 'History'} — ${p.name}`}>
              {section === 'sky' ? 'proof map' : section === 'groups' ? 'read the argument' : 'history'}
            </Link>
          ))}
        </div>
      </td>
      <td className="pr-4">
        <StatusBadge status={p.status} />
      </td>
      <td className="pr-3 text-right">
        <GoalCounts p={p} />
        {p.last_event && <div className="mt-1 text-[11px] text-ink-faint" title={p.last_event}>updated {relTime(p.last_event)}</div>}
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
  /** the run's confirm window (§1.3): a preview per ticked name, in the
   * same floating window every other consequential act wears */
  const [confirmRun, setConfirmRun] = useState(false)
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
          {/* the console's one Stop, force step and all — the same
              control a task's own page presses (RunControl.tsx) */}
          <StopButton
            stopping={d.stopping}
            onDone={(ok) => {
              if (ok) onClear()
              refresh()
            }}
          />
        </>
      ) : (
        <>
          <Button
            variant="primary"
            disabled={picked.length === 0}
            title={
              picked.length === 0
                ? 'tick the tasks to run — the engine takes an explicit list, never a pattern'
                : `read what running ${picked.length} task${picked.length === 1 ? '' : 's'} would do`
            }
            onClick={() => setConfirmRun(true)}
          >
            {`Run${picked.length > 0 ? ` ${picked.length}` : ''}…`}
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

function Shelf({
  project,
  rows,
  loaded,
}: {
  project: string
  rows: BoardProblem[]
  /** has the shelf answered? an unanswered question is not an answer of
   * zero, and saying "No tasks on this shelf yet" for the beat before
   * the first poll lands is a false sentence on every open */
  loaded: boolean
}) {
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')
  const { data: daemon } = usePoll<DaemonStatus>('/api/daemon', 5000)
  const q = query.trim().toLowerCase()
  const filtering = q !== ''
  // the shelf's ONE order, shared with the task column and with the
  // task a section opens on — the sections below GROUP this list, they
  // do not re-rank it
  const sorted = shelfOrder(rows.filter((p) => q === '' || p.name.toLowerCase().includes(q)))
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
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-7">
        <h1 className="font-display text-3xl text-ink">Questions in progress.</h1>
        <p className="mt-2 text-xs leading-relaxed text-ink-dim">Read the argument, trace a proof, or choose what runs next.</p>
      </div>
      <Inbox project={project} />
      <section className="mb-6 flex flex-col gap-3 rounded-xl border border-edge bg-surface px-4 py-3">
        <RunBar project={project} picked={[...picked]} onClear={() => setPicked(new Set())} />
        <RunParameters running={daemon?.running ?? false} />
      </section>

      <div className="mb-2 flex flex-wrap items-center gap-3">
        <div className="w-72 max-w-full">
          <CollectionSearch value={query} onChange={setQuery} label="Search tasks" placeholder="filter tasks…" />
        </div>
        <span className="tnum text-[11px] text-ink-faint">{loaded ? `${sorted.length} task${sorted.length === 1 ? '' : 's'}` : '—'}</span>
        {picked.size > 0 && <button className="cursor-pointer text-xs text-ink-dim underline" onClick={() => setPicked(new Set())}>clear {picked.size} selected</button>}
        <Link
          to={`/new/${encodeURIComponent(project)}`}
          className="ml-auto rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-bg transition-colors hover:bg-starlight"
          title={`a new task, filed on ${project}`}
        >
          New task
        </Link>
      </div>

      {rows.length === 0 ? (
        loaded ? (
          <div className="py-16 text-center text-xs text-ink-faint">
            No tasks on this shelf yet — “New task” describes one in plain language.
          </div>
        ) : (
          <div className="late-fade py-16 text-center text-xs text-ink-faint">Loading…</div>
        )
      ) : sorted.length === 0 ? (
        <div role="status" className="py-12 text-center">
          <p className="font-display text-2xl">No matching tasks.</p>
          <button className="mt-3 cursor-pointer text-xs text-ink-dim underline" onClick={() => setQuery('')}>Clear the search</button>
        </div>
      ) : (
        <div className="overflow-x-auto"><table className="w-full min-w-[620px] table-fixed border-collapse text-left">
          <caption className="sr-only">Tasks and their proof inventory; counts do not measure completion of the main question.</caption>
          <colgroup>
            <col className="w-8" />
            <col />
            <col className="w-[132px]" />
            <col className="w-[180px]" />
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
        </table></div>
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
  // the DELETE is in flight — neither Escape nor the backdrop may take
  // the window away before it has answered
  const close = useCallback(() => {
    if (!busy) setOpen(false)
  }, [busy])
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
        // the name field is the ceremony, so it takes the focus and the
        // window stands back (`autoFocus={false}`)
        <ConfirmWindow
          title={`Delete ${problem}?`}
          width="sm"
          autoFocus={false}
          onClose={close}
        >
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
            <Button variant="outline" onClick={close} disabled={busy}>
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
        </ConfirmWindow>
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
    <div className="mx-auto max-w-4xl py-8">
      <Link to={projectPath(project, 'tasks')} className="mx-6 mb-4 inline-block text-xs text-ink-dim hover:text-ink">‹ All tasks</Link>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 px-6">
        <span className="font-mono text-sm text-ink">{problem}</span>
        {row && <StatusBadge status={row.status} />}
        <span className="ml-auto flex items-center gap-3">
          <RunControl
            project={project}
            problem={problem}
            engineHref={projectPath(project, 'engine')}
          />
        </span>
      </div>
      <div className="px-6">
        <RunParameters running={daemon?.running ?? false} />
      </div>
      <nav aria-label="Read this task" className="mx-6 mt-6 grid gap-3 sm:grid-cols-3">
        {([
          ['groups', 'Read the argument', 'The current plan and its discussions.'],
          ['sky', 'Explore the proof', 'Claims, dependencies and proved steps.'],
          ['timeline', 'Follow the history', 'Decisions and what became of them.'],
        ] as const).map(([section, title, description]) => (
          <Link key={section} to={projectPath(project, section, problem)} className="group rounded-xl border border-edge bg-surface p-4 transition-colors hover:border-ink-faint hover:bg-surface-2">
            <span className="flex items-center justify-between gap-2 text-xs font-medium text-ink">{title}<span aria-hidden="true" className="text-ink-faint group-hover:text-ink">↗</span></span>
            <span className="mt-2 block text-[11px] leading-relaxed text-ink-dim">{description}</span>
          </Link>
        ))}
      </nav>
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
  loaded,
}: {
  project: string
  rows: BoardProblem[]
  problem: string | null
  loaded: boolean
}) {
  if (problem === null) return <Shelf key={project} project={project} rows={rows} loaded={loaded} />
  return (
    <OneTask
      key={problem}
      project={project}
      problem={problem}
      row={rows.find((p) => p.name === problem)}
    />
  )
}
