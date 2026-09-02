import { useEffect, useRef, useState } from 'react'
import { usePoll } from '../lib/api'
import { duration, goalCode, goalLabel, groupCode, relTime } from '../lib/format'
import { Lean } from '../lib/lean'
import { splitSignature } from '../lib/leanSig'
import { emitGoalHover, emitGoalOpen } from '../lib/goalFocus'
import { providerLabel, windowLabel } from '../lib/vocab'
import { scopedRows } from '../lib/quota'
import { projectPath } from '../lib/projectRoute'
import { navigate } from '../lib/router'
import { frameClass } from '../lib/textFrame'
import { renderInline, renderProse } from '../lib/prose'
import { LeanProbe } from '../components/LeanProbe'
import LogTail from '../components/LogTail'
import { SignalSheet } from '../components/CommandSheet'
import { SectionLabel } from '../components/ui'
import { UsageLedger } from './Usage'
import type { Meta, RunStatus, RunWorker } from '../lib/types'

/*
 * The engine room (human_interface_design.md §1.4-2, fourth bullet):
 * the SLOTS pulled out from under the sky, plus the engine log, the
 * usage ledger and each provider's quota bar. Read-only observation —
 * starting and stopping a run is the Tasks section's job, because that
 * is where you choose what to run.
 *
 * Everything here is the old console's instrument panel, re-homed. The
 * three things that left it: the constellation (its own section now),
 * the goal tallies (the shelf states them per task), and the lens pills
 * (the task column IS the lens).
 */

/** A departed agent's 30s receipt — completions used to simply
 * evaporate between polls (design round). */
interface Ghost {
  k: string
  kind: string
  slug: string
  problem: string | null
  leased_at: string | null
  until: number
}

function useTick(ms: number) {
  const [, tick] = useState(0)
  useEffect(() => {
    const t = window.setInterval(() => tick((n) => n + 1), ms)
    return () => window.clearInterval(t)
  }, [ms])
}

function wallClock(startedAt: string | null | undefined): string | null {
  if (!startedAt) return null
  const sec = Math.max(0, Math.floor((Date.now() - Date.parse(startedAt)) / 1000))
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/** Idle wears three faces: clean finish, force stop, crash. */
function lastExitLine(e: RunStatus['daemon']['last_exit']): string {
  if (!e) return 'the engine has not run yet'
  if (e.rc === 0) return 'the last run finished cleanly'
  if (e.rc === null) return 'you force-stopped the last run'
  return `the last run exited abnormally (${e.error ?? 'unknown error'})`
}

function laneAge(iso: string | null): string | null {
  if (!iso) return null
  const sec = Math.max(0, (Date.now() - Date.parse(iso)) / 1000)
  return duration(sec)
}

/** A whisper from the collapsed engine log: latest line + anomaly
 * count — the fold header used to transmit zero bits while a
 * swallowed-error line scrolled beneath it (design round). One
 * lightweight stream; the full tail keeps its own when opened. */
function useLogPulse(active: boolean) {
  const [last, setLast] = useState<string | null>(null)
  const [alerts, setAlerts] = useState(0)
  useEffect(() => {
    if (!active) return
    const es = new EventSource('/api/events/stream')
    // reset on every (re)connect: the stream replays its backlog, so
    // counting from zero each time yields the true total instead of
    // doubling it after an auto-reconnect (self-audit, 2026-07-14)
    es.onopen = () => setAlerts(0)
    es.onmessage = (e) => {
      const line = e.data as string
      setLast(line)
      if (/\berror\b|\bfatal\b|traceback|swallowed|exception/i.test(line))
        setAlerts((n) => n + 1)
    }
    return () => es.close()
  }, [active])
  return { last, alerts }
}

/** A departed agent's 30s receipt — completions used to simply
 * evaporate between polls (design round). */
interface Ghost {
  k: string
  kind: string
  slug: string
  problem: string | null
  leased_at: string | null
  until: number
}

/** the Strategist's wake reason (trigger_kind) in human words — which
 * MODE this think is, not just "thinking" (owner, 2026-07-12) */
const STRATEGIST_MODE: Record<string, string> = {
  pending_review: 'reviewing a finished attempt — accept, redirect, or shelve',
  inject_batch_done: 'its last batch of moves has landed — planning the next ones',
  // the standalone audit wake merged into routine (38616b68): the
  // belief sweep is now routine's first phase, so the copy has to
  // carry both halves — 'audit' survives only on historical rows
  audit: 'auditing its own beliefs against the sources',
  routine: 'fresh eyes on the whole problem — auditing its beliefs, then re-deciding the plan',
}

/* The wake's admin turn had its own line here from 2026-08-03. The
 * split is gone (`2cac1812`, 2026-08-11 — the exit condition had ended
 * up spread across the two turns), so a strategist wake is one turn
 * again. serve still emits `stage`, deliberately as a null, so an old
 * bundle reads "no stage" instead of throwing; this bundle stops asking.
 * Copy describing a machine that no longer exists is worse than no
 * copy: a reader believes it. */

/** The proposal↔reviewer cycle, narrated (research mode): the
 * strategist's main deliverable is the Programme, and the argument
 * with the adversarial reviewer lives in files the plan note never
 * touches — without this line the card reads as half an hour of
 * silence (owner, 2026-07-18). */
export function CycleLine({ cycle }: { cycle: NonNullable<RunWorker['cycle']> }) {
  const dur = cycle.since_sec !== null ? duration(cycle.since_sec) : null
  const text =
    cycle.phase === 'proposing'
      ? 'drafting a programme proposal — the adversarial reviewer reads it next'
      : cycle.phase === 'judging'
        ? `round ${cycle.round} — the reviewer is examining the proposal${dur ? ` (${dur})` : ''}`
        : cycle.phase === 'revising'
          ? `round ${cycle.round} — rejected with ${cycle.objections.length} objection${cycle.objections.length === 1 ? '' : 's'}; revising the proposal`
          : `round ${cycle.round} — passed review; committing the programme`
  return (
    <div className="mt-1.5 text-[11px] text-ink-dim">
      <span title="the proposal-review cycle: the strategist argues its research programme past an adversarial reviewer before it can act on it">
        {text}
      </span>
      {cycle.objections.length > 0 && (
        <details className="group/obj mt-0.5">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[10px] text-ink-faint transition-colors hover:text-ink-dim">
            <span
              className="inline-block text-[9px] transition-transform duration-150 group-open/obj:rotate-90"
              aria-hidden
            >
              ▸
            </span>
            the reviewer's objections
          </summary>
          <ul className="mt-1 space-y-1 pl-4 text-[11px] text-ink-faint">
            {cycle.objections.map((o, i) => (
              <li key={i} className="list-disc marker:text-ink-faint/60">
                {renderInline(o, `obj${i}`)}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

/** serve's tail window (run.py _TAIL_BYTES) — under this size the tail
 * is the whole file and needs no window repair. */
const TAIL_WINDOW_BYTES = 32768

/** A truncated tail can open INSIDE a code fence; the first ``` below
 * is then a CLOSER, and a naive prose render inverts code/prose for
 * the whole tail. Heuristic repair: truncated + odd fence count + the
 * first fence line is bare (openers usually carry a language tag) ⇒
 * drop the orphaned fence body. A trailing fence the agent is still
 * writing renders as code-in-progress, which is honest. */
function stableMdTail(tail: string, size: number): string {
  if (size <= TAIL_WINDOW_BYTES) return tail
  const lines = tail.split('\n')
  const fenceIdx = lines.findIndex((l) => l.trimStart().startsWith('```'))
  if (fenceIdx < 0) return tail
  const fences = lines.filter((l) => l.trimStart().startsWith('```')).length
  if (fences % 2 === 1 && lines[fenceIdx].trim() === '```')
    return lines.slice(fenceIdx + 1).join('\n')
  return tail
}

/** The name of the node an agent is on — a link that OPENS it rather
 * than merely landing you near it. The console's own sky claims the
 * open when it is showing that problem (you stay on the console); a
 * lane on another problem navigates, and the problem screen selects
 * the node on arrival. It used to jump to the problem page and select
 * nothing, which is the worst of both (owner, 2026-08-02). */
function GoalLink({
  project,
  problem,
  slug,
  goalId,
}: {
  project: string
  problem: string
  slug: string
  goalId?: number
}) {
  return (
    <button
      className="flex max-w-72 min-w-0 items-baseline gap-2 text-left font-mono text-xs transition-colors hover:text-ink"
      title={`${goalId === undefined ? slug : goalLabel(goalId, slug)} — open this node`}
      onClick={() => {
        // no sky is mounted in this room, so the click walks to the one
        // that holds this node and lets it consume the pending open
        if (!emitGoalOpen({ problem, slug }))
          navigate(projectPath(project, 'sky', problem))
      }}
    >
      {goalId !== undefined && (
        <span className="shrink-0 text-ink-faint">{goalCode(goalId)}</span>
      )}
      <span className="truncate text-ink-dim">{slug}</span>
    </button>
  )
}

/** One agent, one lane: what it is, what it's on, what it's writing. */
function Lane({
  w,
  problem,
  project,
  multi,
}: {
  w: RunWorker
  problem: string | null
  project: string
  multi?: boolean
}) {
  const quiet = w.file?.quiet_sec ?? null
  // the lane's OWN problem outranks the console's lens — a pattern
  // scope runs agents across several problems at once
  const laneProblem = w.problem ?? problem
  // "run a snapshot": the tail as it stood at press time, copied into
  // the reader's Lean slot as an interactive probe — the cursor shows
  // the goal at any line while the agent keeps writing the original
  const [probe, setProbe] = useState<{ seed: string; seq: number } | null>(null)
  // §3.7: a person may stop ONE in-flight Formalizer. Only a Formalizer
  // — the applier refuses every other kind — and only when the run feed
  // names the pipeline, because a kill is aimed at an id and never at a
  // kind or a name (CLAUDE.md's broad-filter rule, in the engine).
  const [stopping, setStopping] = useState(false)
  const killable = w.kind === 'Formalizer' && laneProblem !== null && laneProblem !== undefined
  const pipelineId = (w.pipeline_id ?? '').trim()
  return (
    <div className="rounded-xl border border-edge bg-surface p-3">
      <div className="flex items-baseline gap-2.5">
        <span className="text-xs font-medium text-ink">{w.kind.toLowerCase()}</span>
        {laneProblem ? (
          <GoalLink project={project} problem={laneProblem} slug={w.slug} />
        ) : (
          <span className="max-w-72 truncate font-mono text-xs text-ink-dim">{w.slug}</span>
        )}
        {multi && w.problem && (
          <span
            className="truncate font-mono text-[10px] text-ink-faint"
            title={w.problem}
          >
            {w.problem.split('.').pop()}
          </span>
        )}
        {/* every group keeps its stable code; a delegated one also says
            how it relates to the problem's own argument */}
        {w.group && (
          <span
            className="shrink-0 font-mono text-[10.5px] text-ink-faint"
            title={
              w.group.is_top
                ? `the problem's own argument — ${groupCode(w.group.id)}`
                : `a delegated claim — discussion group ${groupCode(w.group.id)}`
            }
          >
            {groupCode(w.group.id)}
            {!w.group.is_top && <span className="font-sans"> · delegated</span>}
          </span>
        )}
        <span
          className="tnum ml-auto text-[11px] text-ink-faint"
          title="how long this agent has worked this goal (engine term: unit lease)"
        >
          on it {laneAge(w.leased_at) ?? '—'}
        </span>
        {killable && pipelineId !== '' && !stopping && (
          <button
            className="shrink-0 cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
            onClick={() => setStopping(true)}
            title="stop this worker — you choose what becomes of its goal"
          >
            stop…
          </button>
        )}
      </div>
      {w.statement &&
        (() => {
          // the lane statement now carries binders (serve reads the
          // stub) — two lines: hypotheses faint, ⊢ conclusion under
          // them, so the card means something without the full file
          const sig = splitSignature(w.statement)
          return sig !== null && sig.binders.length > 0 ? (
            <div className="mt-1 font-mono text-[11px] text-ink-faint" title={w.statement}>
              <div className="truncate opacity-75">
                <Lean code={sig.binders.join(' ')} />
              </div>
              <div className="truncate">
                <Lean code={'⊢ ' + sig.conclusion} />
              </div>
            </div>
          ) : (
            <div className="mt-1 truncate font-mono text-[11px] text-ink-faint" title={w.statement}>
              <Lean code={sig !== null ? '⊢ ' + sig.conclusion : w.statement} />
            </div>
          )
        })()}
      {/* the charter IS what a sub-group's strategist is working on —
          the same role the statement plays on a goal lane */}
      {w.group && !w.group.is_top && w.group.charter && (
        <div className="mt-1 text-[11px] text-ink-dim" title={w.group.charter}>
          {renderInline(w.group.charter, `ch${w.group.id}`)}
        </div>
      )}
      {killable && pipelineId === '' && (
        /* the one lane control with no door: a kill names ONE pipeline
           id, and `/api/run` reports the queue lease, which does not
           carry it. Saying so beats a button over nothing — the same
           answer the run parameters give for a knob with no endpoint. */
        <div className="mt-1.5 text-[11px] text-ink-faint">
          this console cannot stop this worker: the run feed does not name the pipeline it
          is, and a kill signal must name one.
        </div>
      )}
      {killable && pipelineId !== '' && stopping && (
        <SignalSheet
          problem={laneProblem!}
          pipelineId={pipelineId}
          label={`${w.kind.toLowerCase()} · ${w.slug}`}
          onClose={() => setStopping(false)}
        />
      )}
      {w.kind === 'Strategist' && w.cycle && <CycleLine cycle={w.cycle} />}
      {w.file ? (
        // the tail folds away (owner: the sky owns the space) — the
        // activity line IS the summary, one click opens the text
        <details className="group/tail mt-2">
          <summary className="tnum flex cursor-pointer list-none items-center gap-1.5 text-[10px] text-ink-faint transition-colors hover:text-ink-dim">
            <span
              className="inline-block text-[9px] transition-transform duration-150 group-open/tail:rotate-90"
              aria-hidden
            >
              ▸
            </span>
            {quiet !== null && quiet <= 12
              ? 'writing now'
              : `last write ${duration(quiet ?? 0)} ago`}
            {w.path && (
              <span className="min-w-0 truncate font-mono" title={w.path}>
                · {w.path.split('/').pop()}
              </span>
            )}
          </summary>
          {w.path?.endsWith('.md') ? (
            // prose the agent writes FOR humans (proposal, plan note)
            // reads as prose — headings, lists, $TeX$ typeset; the Lean
            // tokenizer was colouring `have` red mid-sentence (owner
            // screenshot, 2026-07-25). Unbalanced $ mid-write simply
            // stays raw (withMath needs the closing $).
            <div className={frameClass({ cap: 'lg', size: 'md', mono: false, className: 'mt-1.5' })}>
              {renderProse(stableMdTail(w.file.tail, w.file.size), { mode: 'document' })}
            </div>
          ) : (
            <>
              {/* The probe TAKES the frame, exactly as it does in the
                  Library (owner, 2026-08-27): opening one BELOW left
                  the agent's text standing above it and ran the card
                  off the page. One frame, two states — and the button
                  rides inside it on hover, as the Library's does. */}
              {!probe && (
                <div className="group/snap relative mt-1.5">
                  <pre className={frameClass({ cap: 'lg' })}>
                    <Lean code={w.file.tail} />
                  </pre>
                  {laneProblem && (
                    <button
                      className="absolute right-2 bottom-2 cursor-pointer rounded-md border border-edge bg-surface px-2.5 py-0.5 font-mono text-[11px] text-ink-dim opacity-0 transition-opacity group-hover/snap:opacity-100 hover:border-edge-strong hover:text-ink"
                      title="copy the patch as it stands into the reader's Lean slot — the cursor then shows the goal at any line; edits land in the copy, never in the agent's file"
                      onClick={() =>
                        setProbe((p) => ({
                          seed: `namespace Problems.${laneProblem}\n${w.file!.tail}\nend Problems.${laneProblem}`,
                          seq: (p?.seq ?? 0) + 1,
                        }))
                      }
                    >
                      ▸ run a snapshot
                    </button>
                  )}
                </div>
              )}
              {/* the snapshot probe (the Library's own block):
                  interactive, cursor-goal, editable — the copy is the
                  reader's; the agent's file streams on, untouched.

                  `Mathlib`, not the `Problems.<p>.Defs` this used to
                  invent: the agent writes a scratch file under
                  .attempts/ whose real prelude is `import Mathlib`
                  (596/596 problem Roots open with it; not one sampled
                  attempt file imported a Defs). ~29 problems have no
                  Defs.lean at all — union_closed among them — and lake
                  refused the entire build rather than the one import
                  (owner screenshot, 2026-08-27). The FILE's own
                  prelude is the real answer, and serve strips it
                  before the UI ever sees it (`run.py::_tail`); until
                  it comes through, name the one import the framework
                  guarantees rather than a module that may not exist. */}
              {probe && laneProblem && (
                <LeanProbe
                  key={probe.seq}
                  seed={probe.seed}
                  imports={['Mathlib']}
                  className="mt-1.5"
                  // the cap the streaming frame carries, so opening a
                  // snapshot swaps the card's height for nothing
                  heightClass="min-h-16 h-auto max-h-96 field-sizing-content"
                  onClose={() => setProbe(null)}
                />
              )}
            </>
          )}
        </details>
      ) : (
        <div className="mt-2 text-[11px] text-ink-faint">
          {w.kind === 'Strategist'
            ? (STRATEGIST_MODE[w.mode ?? ''] ??
              'reading the state, deciding the next moves — nothing on disk yet')
            : /* one worker turns the argued proof into Lean since the
                 v33 merge; Forward/Backward/Builder lanes only appear
                 on historical rows now */
              w.kind === 'Formalizer'
              ? 'reading the goal against the programme — it will prove it, split it, or decline'
              : w.kind === 'Forward'
                ? 'building new vocabulary and claims — each landed brick appears as a new star'
                : w.kind === 'Librarian'
                  ? 'curating finished work into the Library'
                  : 'nothing on disk yet — composing its prompt'}
        </div>
      )}
    </div>
  )
}

/** One subscription window: a thin bar that brightens as it fills,
 * with the reset moment — spend against the REAL ceiling. Exported:
 * the Settings page reads the same meters as the account's allowance,
 * one renderer under two framings (2026-08-07). */
export function QuotaMeter({
  label,
  pct,
  resetsAt,
  title,
  quiet,
}: {
  label: string
  pct: number
  resetsAt: string | null
  /** what this window IS, for the rows that are not self-evident */
  title?: string
  /** a real ceiling that is not the one currently binding — readable,
   * but it must not compete with the window that will actually stop
   * the run */
  quiet?: boolean
}) {
  const clamped = Math.max(0, Math.min(100, pct))
  // pinned to en-US: the UI speaks English — a system-locale weekday
  // ("週四上午") in an otherwise English page reads as a glitch
  const resets = resetsAt
    ? new Date(resetsAt).toLocaleString('en-US', {
        weekday: clamped >= 0 && label.includes('week') ? 'short' : undefined,
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    : null
  return (
    <div className="flex items-center gap-3" title={title}>
      <span
        className={`w-32 shrink-0 truncate text-xs ${quiet ? 'text-ink-faint' : 'text-ink-dim'}`}
      >
        {label}
      </span>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-surface-2">
        <div
          className={`h-full ${
            clamped >= 85 && !quiet ? 'bg-warn' : quiet ? 'bg-starlight/25' : 'bg-starlight/60'
          }`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span
        className={`tnum w-10 text-right text-xs ${quiet ? 'text-ink-dim' : 'text-ink'}`}
      >
        {Math.round(clamped)}%
      </span>
      <span className="tnum w-28 text-[11px] text-ink-faint">
        {resets ? `resets ${resets}` : ''}
      </span>
    </div>
  )
}

export interface SkyJump {
  id: number
  problem: string
  /** grows per click so the same goal can be jumped twice */
  seq: number
}

export default function EngineRoom({
  project,
  pin,
  rows,
}: {
  project: string
  /** the task column's pick, pinning the lanes to one task */
  pin: string | null
  rows: { name: string }[]
}) {
  const { data } = usePoll<RunStatus>(
    pin ? `/api/run?problem=${encodeURIComponent(pin)}` : '/api/run',
    2000,
  )
  // which backend each seat rides - the quota strip must NAME whose
  // window it shows and stay silent about accounts nothing spends
  const { data: meta } = usePoll<Meta>('/api/meta', 15000)
  useTick(1000)
  const [logOpen, setLogOpen] = useState(false)
  const logPulse = useLogPulse(Boolean(data?.daemon.running))

  // landed receipts: an agent that vanishes between polls leaves a 30s
  // ghost card naming what it was on
  const ghostsRef = useRef<Ghost[]>([])
  const prevWorkersRef = useRef<RunWorker[]>([])
  useEffect(() => {
    const ws = data?.workers ?? []
    if (data?.daemon.running) {
      const cur = new Set(ws.map((w) => `${w.kind}:${w.slug}`))
      for (const p of prevWorkersRef.current) {
        const k = `${p.kind}:${p.slug}`
        if (!cur.has(k))
          ghostsRef.current.push({
            k,
            kind: p.kind,
            slug: p.slug,
            problem: p.problem ?? data.problem,
            leased_at: p.leased_at,
            until: Date.now() + 30_000,
          })
      }
    } else {
      ghostsRef.current = []
    }
    prevWorkersRef.current = ws
  }, [data])

  if (!data) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>

  const d = data.daemon
  const running = d.running
  const starting = !running && d.starting
  const workers = data.workers
  const builds = d.promotion_builds ?? []
  const phase = !running
    ? starting
      ? 'starting'
      : 'idle'
    : d.stopping
      ? 'stopping'
      : d.gateway === 'warming'
        ? 'warming the Lean toolchain'
        : workers.length === 0 || workers.every((w) => w.kind === 'Strategist')
          ? 'planning'
          : workers.every((w) => w.kind === 'Librarian')
            ? 'harvesting'
            : 'proving'
  const crashed =
    !running && d.last_exit && d.last_exit.rc !== 0 && d.last_exit.rc !== null
  const st = d.slots
  const target = st?.target ?? 0
  const ghostsShown = st
    ? Math.min(ghostsRef.current.length, Math.max(0, target - workers.length))
    : 0
  const free = st
    ? Math.max(0, Math.min(st.free, target - workers.length - ghostsShown))
    : 0

  return (
    <div className="mx-auto max-w-4xl px-6 py-6">
      {/* one status line, no page title: the menu already said which
          room this is, and drawing that twice is the law the shell
          exists to keep */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            running || starting
              ? d.stopping
                ? 'bg-warn'
                : 'bg-accent animate-pulse'
              : crashed
                ? 'bg-warn'
                : 'bg-ink-faint'
          }`}
        />
        <span className="text-ink">{phase}</span>
        {data.problem && <span className="font-mono text-ink-dim">{data.problem}</span>}
        {running && d.started_at && (
          <span className="tnum text-ink-faint" title="how long this run has been going">
            {wallClock(d.started_at)}
          </span>
        )}
        {!running && (
          <span className="text-ink-faint">{lastExitLine(d.last_exit)}</span>
        )}
        {running && !d.stopping && (
          <span className="text-ink-faint">
            closing this page does NOT stop it — Stop lives on the task
          </span>
        )}
      </div>

      <section className="mt-7">
        <SectionLabel>
          slots
          {(workers.length > 0 || st) && (
            <span className="tnum ml-2 font-normal tracking-normal normal-case text-ink-faint/80">
              {st ? `${workers.length}/${target} busy · ${free} free` : `${workers.length} busy`}
            </span>
          )}
        </SectionLabel>
        {workers.length === 0 && free === 0 && builds.length === 0 ? (
          <div className="text-xs text-ink-faint">
            {!running
              ? 'the engine is not running — Run lives on a task'
              : d.gateway === 'warming'
                ? 'none yet — agents spawn once the toolchain is hot'
                : 'none this instant — between batches'}
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {workers.map((w, i) => {
              const laneProblem = w.problem ?? data.problem
              return (
                <div
                  key={`${w.kind}:${w.slug}:${i}`}
                  onMouseEnter={() =>
                    laneProblem && emitGoalHover({ problem: laneProblem, slug: w.slug })
                  }
                  onMouseLeave={() => emitGoalHover(null)}
                >
                  <Lane
                    w={w}
                    problem={data.problem}
                    project={project}
                    multi={(data.problems?.length ?? 0) > 1 || rows.length > 1}
                  />
                </div>
              )
            })}
            {/* promotion cold builds (§1.5-2): the gate is a background
                thread, not a pipeline, so `in_flight` says 0 while it
                holds the machine for ten minutes — the operator read
                that as "nobody on the field" */}
            {builds.map((b) => (
              <div
                key={b.strategy_id}
                className="flex min-h-24 flex-col justify-center rounded-xl border border-edge bg-surface p-3"
              >
                <div className="flex items-baseline gap-2.5">
                  <span className="text-xs text-ink-dim">cold-building</span>
                  <span className="font-mono text-xs text-ink-faint">s{b.strategy_id}</span>
                  <span className="tnum ml-auto text-[11px] text-ink-faint">
                    {b.started_at ? relTime(b.started_at) : ''}
                  </span>
                </div>
                <div className="mt-1 truncate font-mono text-[11px] text-ink-faint">
                  {(b.modules ?? []).join(' ')}
                </div>
                <div className="mt-1 text-[11px] text-ink-faint">
                  a proved route is compiling from cold before it is promoted
                </div>
              </div>
            ))}
            {(ghostsRef.current = ghostsRef.current.filter((g) => g.until > Date.now()))
              .slice(0, ghostsShown)
              .map((g) => {
                const held = g.leased_at
                  ? duration(Math.max(0, (g.until - 30_000 - Date.parse(g.leased_at)) / 1000))
                  : null
                return (
                  <div
                    key={`${g.k}:${g.until}`}
                    className="min-h-24 rounded-xl border border-edge/60 bg-surface/50 p-3 opacity-70"
                  >
                    <div className="flex items-baseline gap-2.5">
                      <span className="text-xs text-ink-dim">{g.kind.toLowerCase()}</span>
                      <span className="max-w-72 truncate font-mono text-xs text-ink-faint">
                        {g.slug}
                      </span>
                      <span className="tnum ml-auto text-[11px] text-ink-faint">
                        landed{held ? ` · ${held} on it` : ''}
                      </span>
                    </div>
                    <div className="mt-2 text-[11px] text-ink-faint">
                      finished — the result lands on the task's sky
                    </div>
                  </div>
                )
              })}
            {Array.from({ length: free }).map((_, i) => (
              <div
                key={`free${i}`}
                className="flex min-h-24 items-center justify-center rounded-xl border border-dashed border-edge/60 text-[11px] text-ink-faint/70"
                title="an open berth — the RAM ledger's current target has room for one more agent"
              >
                free — waiting for work
              </div>
            ))}
          </div>
        )}
      </section>

      {(() => {
        // seats per backend, from the declaration-driven rows. Until
        // meta answers, show the meter as before — hiding a real
        // reading on a flaky poll would be the worse lie.
        const seated = (meta?.providers ?? []).filter((p) => p.seats.length > 0)
        const claudeSeats =
          meta === null
            ? null
            : (seated.find((p) => p.name === 'claude')?.seats ?? []).map((x) => x.seat)
        // the ledger-writing backends (codex): a meter only while that
        // backend is SEATED, exactly claude's rule — a reading from
        // yesterday's run is not this run's instrument
        const logged = (data.quota_logged ?? []).filter((l) =>
          seated.some((p) => p.name === l.provider),
        )
        const others = seated.filter(
          (p) => p.name !== 'claude' && !logged.some((l) => l.provider === p.name),
        )
        const showMeter = data.quota && (claudeSeats === null || claudeSeats.length > 0)
        if (
          !showMeter &&
          others.length === 0 &&
          logged.length === 0 &&
          (claudeSeats?.length ?? 0) === 0
        )
          return null
        return (
        <section className="mt-7">
          {/* the gloss and the switch-account move both moved to the
              console's own Settings page (owner, 2026-08-07): here the
              meters are what you watch while it burns. One heading over
              all of them, each block naming WHOSE window it is — an
              unlabeled meter under a zen fleet read as the run's own
              quota when nothing on screen was spending Claude, and the
              cure does not scale by promoting one vendor to the
              heading (owner, 2026-08-26: codex reads the same). */}
          <div className="mb-3 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
            <span title="what each seated backend lets this console know about its remaining allowance">
              plan usage
            </span>
          </div>
          {/* Two seated backends read SIDE BY SIDE (owner, 2026-08-27):
              stacked, each one column wide, the second sat below a
              screenful of empty right-hand page. One block still takes
              its own max-w-xl; a third wraps. */}
          <div className="flex flex-wrap items-start gap-x-10 gap-y-5">
          {!showMeter ? null : (
          <div className="flex min-w-[17rem] max-w-xl flex-1 basis-0 flex-col gap-2">
            <div className="text-[11px] text-ink-dim">
              <span title="read live from your Claude subscription's own usage endpoint">
                {providerLabel('claude')}
              </span>
              {claudeSeats !== null && claudeSeats.length > 0 && (
                <span className="text-ink-faint"> · {claudeSeats.join(' · ')}</span>
              )}
            </div>
            {(
              [
                ['5-hour window', data.quota!.five_hour],
                ['week', data.quota!.seven_day],
              ] as const
            ).map(
              ([label, w]) =>
                w && (
                  <QuotaMeter key={label} label={label} pct={w.utilization} resetsAt={w.resets_at} />
                ),
            )}
            {/* Per-model weekly caps: whatever the account reports,
                whatever it is called. Anthropic decides which model
                carries one (it was Sonnet's, it is Fable's now) and
                whether one exists at all, so this list is never
                hard-coded and simply disappears when the plan stops
                reporting one. `is_active` marks the cap currently
                BINDING, not the cap's existence — filtering on it made
                a real reading blink in and out (owner, two accounts
                showing different rows, 2026-08-03). */}
            {scopedRows(data.quota!.scoped).map((s) => (
              <QuotaMeter
                key={s.name}
                label={`${s.name} · week`}
                pct={s.percent}
                resetsAt={s.resets_at}
                quiet={!s.is_active}
                title={
                  `${s.name}: a per-model weekly cap your plan reports.` +
                  (s.is_active
                    ? ' It is the limit binding your spend right now.'
                    : ' Another window is binding right now; this one is still counting.')
                }
              />
            ))}
          </div>
          )}
          {/* the ledger meters. Same component, same scale, one line of
              difference that decides how the number is read: nobody
              ASKED this backend anything — it is the reading its last
              agent left in its own rollout, so the age travels with it
              and the number does not move while the engine is idle. */}
          {logged.map((l) => {
            const provSeats = (seated.find((p) => p.name === l.provider)?.seats ?? []).map(
              (x) => x.seat,
            )
            return (
              <div
                key={l.provider}
                className="flex min-w-[17rem] max-w-xl flex-1 basis-0 flex-col gap-2"
              >
                <div className="text-[11px] text-ink-dim">
                  {providerLabel(l.provider)}
                  {provSeats.length > 0 && (
                    <span className="text-ink-faint"> · {provSeats.join(' · ')}</span>
                  )}
                  {l.plan && <span className="text-ink-faint"> · {l.plan} plan</span>}
                </div>
                {l.windows.map((w) => (
                  <QuotaMeter
                    key={w.minutes ?? 'w'}
                    label={windowLabel(w.minutes)}
                    pct={w.utilization}
                    resetsAt={w.resets_at}
                  />
                ))}
                <div className="text-[11px] text-ink-faint">
                  <span title="this backend has no usage endpoint to ask — it writes its own quota reading into each agent's session log, so the meter moves when an agent finishes a turn and stands still while the engine is idle">
                    {l.measured_at
                      ? `as its last agent measured it, ${relTime(l.measured_at)}`
                      : 'as its last agent measured it'}
                  </span>
                  {l.reached && (
                    <span className="text-warn"> · the window is spent ({l.reached})</span>
                  )}
                </div>
              </div>
            )
          })}
          </div>
          {/* the remaining seated backends: nothing to ask and nothing
              written down, so the honest row is who rides them and why
              no meter — silence here read as "no other account is being
              spent" */}
          {(others.length > 0 || (!showMeter && (claudeSeats?.length ?? 0) > 0)) && (
            <div className="mt-2 flex max-w-xl flex-col gap-1">
              {/* claude seated but its endpoint is not answering right
                  now (429/offline): silence would read as "nothing
                  spends Claude" — the same lie the other rows exist
                  to prevent */}
              {!showMeter && (claudeSeats?.length ?? 0) > 0 && (
                <div className="text-[11px] text-ink-faint">
                  <span className="text-ink-dim">Claude Code</span>
                  {' — '}
                  {claudeSeats!.join(' · ')}
                  <span title="the subscription's usage endpoint is not answering right now (rate-limited or offline) — the meter returns by itself">
                    {' · meter unreachable right now'}
                  </span>
                </div>
              )}
              {others.map((p) => (
                <div key={p.name} className="text-[11px] text-ink-faint">
                  <span className="text-ink-dim">{providerLabel(p.name)}</span>
                  {' — '}
                  {p.seats.map((x) => x.seat).join(' · ')}
                  <span
                    title="this backend offers no way to read its usage from here — the engine reacts to its quota markers when they arrive"
                  >
                    {' · no live meter'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
        )
      })()}

      {/* burn figures moved to the Usage tab (owner, 2026-07-18):
          accounting lives with accounting; the console keeps the live
          quota meters because spend-against-window is a run instrument */}

      {/* the run's own log lives where the run's story is told —
          collapsed: it's the "what actually happened" window for a
          crashed or misbehaving run, not part of the narrative. The
          tail mounts only while open (a collapsed <details> still
          mounts children — the SSE stream would run forever) */}
      <section className="mt-7">
        <details
          className="group"
          onToggle={(e) => setLogOpen((e.currentTarget as HTMLDetailsElement).open)}
        >
          <summary className="flex cursor-pointer list-none items-baseline gap-2 text-[11px] font-medium tracking-[0.14em] text-ink-faint/70 uppercase transition-colors hover:text-ink-dim">
            <span className="mr-1 inline-block text-[9px] transition-transform duration-150 group-open:rotate-90">▸</span>
            engine log
            {logPulse.alerts > 0 && (
              <span
                className="tnum rounded-full bg-warn/15 px-1.5 font-normal tracking-normal normal-case text-warn"
                title="lines that look like errors — open the log"
              >
                {logPulse.alerts}
              </span>
            )}
            {/* the fold whispers its latest line instead of
                transmitting zero bits (design round) */}
            {!logOpen && logPulse.last && (
              <span className="min-w-0 flex-1 truncate font-mono text-[10px] font-normal tracking-normal normal-case text-ink-faint/60">
                {logPulse.last}
              </span>
            )}
          </summary>
          <div className="mt-2">{logOpen && <LogTail />}</div>
        </details>
      </section>

      <section className="mt-7">
        <UsageLedger />
      </section>
    </div>
  )
}
