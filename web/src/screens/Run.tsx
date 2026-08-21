import { useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import {
  emitGoalOpen,
  onGoalHover,
  onGoalOpen,
  takePendingGoalOpen,
} from '../lib/goalFocus'
import { duration } from '../lib/format'
import { goalStatusLabel } from '../lib/vocab'
import { Lean } from '../lib/lean'
import { splitSignature } from '../lib/leanSig'
import { renderInline, renderProse } from '../lib/prose'
import { scopedRows } from '../lib/quota'
import { providerLabel } from '../lib/vocab'
import { Link, navigate } from '../lib/router'
import { Button } from '../components/ui'
import Constellation from '../components/Constellation'
import GoalPanel from '../components/GoalPanel'
import StrategyPanel from '../components/StrategyPanel'
import LogTail from '../components/LogTail'
import type {
  Meta, ConfigSetting, ProblemDetail, RunStatus, RunWorker } from '../lib/types'

/*
 * Run — mission control. The one page that answers "what is the
 * machine doing RIGHT NOW" without reading logs: status light + phase
 * in plain words, the scoped problem's progress, one lane per live
 * agent (its unit, its statement, the tail of the file it is writing),
 * burn against the subscription window, and the recent decisions.
 * Idle, it keeps telling the last run's story. Settings live at
 * #/settings — this page is instruments, not knobs.
 */

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
function GoalLink({ problem, slug }: { problem: string; slug: string }) {
  return (
    <button
      className="max-w-72 truncate text-left font-mono text-xs text-ink-dim transition-colors hover:text-ink"
      title={`${slug} — open this node`}
      onClick={() => {
        if (!emitGoalOpen({ problem, slug }))
          navigate(`/problems/${encodeURIComponent(problem)}`)
      }}
    >
      {slug}
    </button>
  )
}

/** One agent, one lane: what it is, what it's on, what it's writing. */
function Lane({ w, problem, multi }: { w: RunWorker; problem: string | null; multi?: boolean }) {
  const quiet = w.file?.quiet_sec ?? null
  // the lane's OWN problem outranks the console's lens — a pattern
  // scope runs agents across several problems at once
  const laneProblem = w.problem ?? problem
  return (
    <div className="rounded-xl border border-edge bg-surface p-3">
      <div className="flex items-baseline gap-2.5">
        <span className="text-xs font-medium text-ink">{w.kind.toLowerCase()}</span>
        {laneProblem ? (
          <GoalLink problem={laneProblem} slug={w.slug} />
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
        {/* a sub-group argues a delegated claim, not the problem's own:
            say so, or two strategists on one problem read identically.
            The top group IS the problem and wears no tag. */}
        {w.group && !w.group.is_top && (
          <span
            className="shrink-0 rounded-md border border-edge px-1 py-px text-[10px] text-ink-faint"
            title={`this agent argues a delegated claim, not the problem's own — engine term: discussion group ${w.group.id}`}
          >
            delegated
          </span>
        )}
        <span
          className="tnum ml-auto text-[11px] text-ink-faint"
          title="how long this agent has worked this goal (engine term: unit lease)"
        >
          on it {laneAge(w.leased_at) ?? '—'}
        </span>
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
            <div className="mt-1.5 max-h-96 overflow-y-auto rounded-lg border border-edge bg-bg px-3.5 py-2.5 text-[12.5px] leading-relaxed text-ink-dim">
              {renderProse(stableMdTail(w.file.tail, w.file.size), { mode: 'document' })}
            </div>
          ) : (
            <pre className="mt-1.5 max-h-96 overflow-y-auto rounded-lg border border-edge bg-bg px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink-dim">
              <Lean code={w.file.tail} />
            </pre>
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

export default function Run() {
  // lens pick: a pattern scope runs several problems in one daemon —
  // the raw scope ("PutnamCmp.%") used to reach the UI as a problem
  // name, 404 the detail fetch and blank the sky (owner, 2026-07-19).
  // The server resolves candidates; this picks among them.
  const [lens, setLens] = useState<string | null>(null)
  const { data, refresh } = usePoll<RunStatus>(
    lens ? `/api/run?problem=${encodeURIComponent(lens)}` : '/api/run',
    2000,
  )
  const { data: cfg } = usePoll<{ settings: ConfigSetting[] }>('/api/config', 60000)
  // which backend each seat rides — the quota strip must NAME whose
  // window it shows and stay silent about accounts nothing spends
  // (owner 2026-08-22: a zen fleet ran under an unlabeled Claude meter)
  const { data: meta } = usePoll<Meta>('/api/meta', 15000)
  // the sky rides along (owner: the console shows the constellation):
  // full problem detail only when a problem is in focus
  const focusProblem = data?.problem ?? null
  const { data: detail } = usePoll<ProblemDetail>(
    focusProblem ? `/api/problems/${encodeURIComponent(focusProblem)}` : null,
    3000,
  )
  const [selGoal, setSelGoal] = useState<number | null>(null)
  // routes open in the console too: reading a lane's goal and then its
  // decomposition is one thought, and it used to cost a page change
  const [selStrategy, setSelStrategy] = useState<number | null>(null)
  const [routeHover, setRouteHover] = useState<number[] | null>(null)
  const skyRef = useRef<HTMLElement | null>(null)
  useEffect(() => {
    setSelGoal(null)
    setSelStrategy(null)
  }, [focusProblem])
  // lane ↔ star umbilical: hovering an agent's lane lights the star
  // it is working (design round — the lanes and the sky were two
  // disconnected worlds)
  const [laneHover, setLaneHover] = useState<number[] | null>(null)
  // chat ↔ star: same law for the drawer's [goal:…] citations — when
  // the console's sky IS that problem, hover lights the star and click
  // selects it here (claimed open → the citation skips navigation)
  const [chatHoverSlug, setChatHoverSlug] = useState<string | null>(null)
  useEffect(
    () =>
      onGoalHover((ref) =>
        setChatHoverSlug(ref !== null && ref.problem === focusProblem ? ref.slug : null),
      ),
    [focusProblem],
  )
  useEffect(() => {
    if (!detail || focusProblem === null) return
    const claim = (ref: { problem: string; slug: string } | null): boolean => {
      if (ref === null || ref.problem !== focusProblem) return false
      const goal = detail.goals.find((x) => x.slug === ref.slug)
      if (goal === undefined) return false
      setSelGoal(goal.id)
      setSelStrategy(null)
      // the sky sits above the slots: opening a node from a lane
      // must bring the thing it opened into view, or the click reads
      // as having done nothing
      skyRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return true
    }
    // an open requested from ANOTHER Engine tab (a delivered brick on
    // the Programme page) arrives before this screen exists — the
    // console is a sky like any other and consumes it on mount
    claim(takePendingGoalOpen(focusProblem))
    return onGoalOpen(claim)
  }, [detail, focusProblem])
  useTick(1000)
  const logPulse = useLogPulse(Boolean(data?.daemon.running))
  // landed receipts: an agent that vanishes between polls leaves a
  // 30s ghost card naming what it was on
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
            leased_at: p.leased_at,
            until: Date.now() + 30_000,
          })
      }
    } else {
      ghostsRef.current = []
    }
    prevWorkersRef.current = ws
  }, [data])

  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [logOpen, setLogOpen] = useState(false)
  const [confirmForce, setConfirmForce] = useState(false)
  const forceTimer = useRef<number | null>(null)
  useEffect(
    () => () => {
      if (forceTimer.current !== null) window.clearTimeout(forceTimer.current)
    },
    [],
  )
  const stop = async (force: boolean) => {
    setBusy(true)
    setMsg(null)
    try {
      const r = await apiPost<{ message: string }>('/api/daemon/stop', { force })
      setMsg(r.message)
    } catch (e) {
      setMsg(String((e as Error).message))
    } finally {
      setBusy(false)
      setConfirmForce(false)
      refresh()
    }
  }
  const start = async () => {
    setBusy(true)
    setMsg(null)
    try {
      await apiPost('/api/daemon/start', { scope: focusProblem })
    } catch (e) {
      setMsg(String((e as Error).message))
    } finally {
      setBusy(false)
      refresh()
    }
  }

  if (!data) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>

  const d = data.daemon
  const running = d.running
  // boot window (Run pressed, lock not yet claimed): not running, but
  // calling it Idle flashed the Run button back mid-start (owner)
  const starting = !running && d.starting
  const workers = data.workers
  const phase = !running
    ? starting
      ? 'Starting'
      : 'Idle'
    : d.stopping
      ? 'Stopping'
      : d.gateway === 'warming'
        ? 'Warming up'
        : workers.length === 0 || workers.every((w) => w.kind === 'Strategist')
          ? 'Planning'
          : workers.every((w) => w.kind === 'Librarian')
            ? 'Harvesting'
            : 'Proving'
  const phaseHint: Record<string, string> = {
    Idle: lastExitLine(d.last_exit),
    Starting: 'the engine is booting — a few seconds, then it claims the run',
    Stopping: 'finishing in-flight work, then a clean exit — Force stop skips the wait',
    'Warming up': 'first start heats the Lean toolchain — a few minutes, then proving begins',
    Planning: 'the Strategist is reading the state and deciding the next moves',
    Proving: 'agents are attempting goals right now',
    Harvesting: 'finished work is being curated into the Library',
  }
  const wall = running ? wallClock(d.started_at) : null
  const crashed = !running && d.last_exit && d.last_exit.rc !== 0 && d.last_exit.rc !== null

  const g = data.goals

  return (
    // no own container: the console renders inside the Engine page's
    // (title → tabs → content, one anatomy across every tabbed screen)
    <div className="pt-5">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <span className="flex items-center gap-3">
          <span
            className={`h-3 w-3 rounded-full ${
              running || starting
                ? d.stopping
                  ? 'bg-warn'
                  : 'bg-ok animate-pulse'
                : crashed
                  ? 'bg-warn'
                  : 'bg-ink-faint'
            }`}
          />
          <h1 className="font-display text-[26px] font-medium text-ink">{phase}</h1>
        </span>
        {data.problem && (
          <Link
            to={`/problems/${encodeURIComponent(data.problem)}`}
            className="font-mono text-sm text-ink-dim underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink"
            title="open the problem — its sky, goals, intent"
          >
            {data.problem}
          </Link>
        )}
        {wall && (
          <span
            className="tnum font-mono text-sm text-ink-dim"
            title="how long this run has been going (wall clock)"
          >
            {wall}
          </span>
        )}
        {running && (
          <span className="ml-auto flex items-center gap-2">
            {confirmForce ? (
              <Button
                variant="danger"
                disabled={busy}
                onClick={() => void stop(true)}
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
                    if (forceTimer.current !== null) window.clearTimeout(forceTimer.current)
                    forceTimer.current = window.setTimeout(() => setConfirmForce(false), 3000)
                  } else {
                    void stop(false)
                  }
                }}
                title={
                  d.stopping
                    ? 'already stopping — press again to force'
                    : 'finish in-flight work, then exit'
                }
              >
                {d.stopping ? 'Force stop…' : 'Stop'}
              </Button>
            )}
          </span>
        )}
        {/* idle with a problem in focus: Run lives where Stop lives —
            the console can restart the last story without a detour
            through the problem page (owner, 2026-07-11). Not during
            the boot window: that Run would only bounce off the
            anti-double-spawn guard */}
        {!running && !starting && focusProblem && (
          <span className="ml-auto">
            <Button
              variant="ok"
              disabled={busy}
              onClick={() => void start()}
              title={`run the engine on ${focusProblem} — one problem at a time`}
            >
              {busy ? 'Starting…' : 'Run'}
            </Button>
          </span>
        )}
      </div>
      <div className="mt-1 text-xs text-ink-faint">
        {phaseHint[phase]}
        {running && !d.stopping && (
          // users assumed closing the tab stops the run (owner) — say
          // the truth where the run is watched
          <span> · closing this page does NOT stop it — only Stop does</span>
        )}
      </div>

      {/* lens pills: a pattern scope works several problems at once —
          the tallies, sky and recent feed below follow the picked one */}
      {(data.problems?.length ?? 0) > 1 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          {data.problems!.map((p) => {
            const leaf = p.split('.').pop() ?? p
            const active = p === data.problem
            return (
              <button
                key={p}
                className={`cursor-pointer rounded-full border px-2.5 py-0.5 font-mono text-[11px] transition-colors ${
                  active
                    ? 'border-star/60 bg-star/10 text-star'
                    : 'border-edge text-ink-faint hover:text-ink'
                }`}
                onClick={() => setLens(p)}
                title={`${p} — focus the console on it`}
              >
                {leaf}
              </button>
            )
          })}
        </div>
      )}

      {g && g.total > 0 && (
        <div className="mt-4 flex items-center gap-3">
          <div className="h-1 max-w-md flex-1 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full bg-starlight/70 transition-[width] duration-700"
              style={{ width: `${(g.proved / g.total) * 100}%` }}
            />
          </div>
          <span className="tnum text-xs text-ink-dim">
            {g.proved}/{g.total} proved
          </span>
          {(g.open > 0 || g.attempting > 0) && (
            <span className="tnum text-xs text-ink-faint">
              {g.attempting > 0 && `${g.attempting} attempting · `}
              {g.open} open
            </span>
          )}
          {/* the arithmetic must close on screen: "161/164 · 1 open"
              left two goals unaccounted for and the reader asking
              (cold-eye) — name the shelved/dead remainder */}
          {g.total - g.proved - g.open - g.attempting > 0 && (
            <span
              className="tnum text-xs text-ink-faint"
              title="shelved or dead — set aside by the strategist, not part of the live count"
            >
              {g.total - g.proved - g.open - g.attempting} set aside
            </span>
          )}
        </div>
      )}

      {msg && <div className="mt-3 text-xs text-ink-dim">{msg}</div>}

      {detail && focusProblem && detail.goals.length > 0 && (
        <section className="mt-6" ref={skyRef}>
          <div className="flex h-[52vh] overflow-hidden rounded-xl border border-edge bg-bg">
            <div className="relative min-w-0 flex-1">
              <Constellation
                goals={detail.goals}
                strategies={detail.strategies}
                strategyEdges={detail.strategy_edges}
                anchorEdges={detail.anchor_edges}
                citationEdges={detail.citation_edges}
                selectedId={selGoal}
                onSelect={setSelGoal}
                shelveThreshold={detail.shelve_threshold}
                engineWorking={detail.engine_working}
                highlightIds={
                  laneHover ??
                  routeHover ??
                  (chatHoverSlug !== null
                    ? (() => {
                        const ids = detail.goals
                          .filter((x) => x.slug === chatHoverSlug)
                          .map((x) => x.id)
                        return ids.length > 0 ? ids : null
                      })()
                    : null)
                }
              />
            </div>
            {/* the same panels the problem page opens — a node's
                routes, its subgoals and its dead attempts are all
                readable HERE; leaving the console to read them was
                the console's own link audit (owner, 2026-08-02) */}
            {selGoal !== null && (
              <GoalPanel
                problem={focusProblem}
                goalId={selGoal}
                onClose={() => {
                  setSelGoal(null)
                  setRouteHover(null)
                }}
                onSelectStrategy={(id) => {
                  setSelStrategy(id)
                  setSelGoal(null)
                }}
                onSelectGoal={setSelGoal}
                onHoverGoals={setRouteHover}
              />
            )}
            {selGoal === null && selStrategy !== null && (
              <StrategyPanel
                problem={focusProblem}
                strategyId={selStrategy}
                onClose={() => setSelStrategy(null)}
                onSelectGoal={(id) => {
                  setSelGoal(id)
                  setSelStrategy(null)
                }}
              />
            )}
          </div>
        </section>
      )}

      {running && (
        <section className="mt-7">
          {/* the pool IS the machine's width: dispatch.pool slots,
              each busy (a lane) or free (a dashed vacancy) — parallel
              capacity readable at a glance (owner's ask) */}
          {(() => {
            const pool =
              Number(cfg?.settings.find((s) => s.key === 'dispatch.pool')?.resolved ?? 0) || 0
            const slotCount = Math.max(pool, workers.length)
            const freeHint =
              d.gateway === 'warming'
                ? 'free — agents spawn once the toolchain is hot'
                : 'free — waiting for work'
            return (
              <>
                <div className="mb-3 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
                  slots
                  {slotCount > 0 && (
                    <span className="tnum ml-2 font-normal tracking-normal normal-case text-ink-faint/80">
                      {workers.length}/{slotCount} busy
                    </span>
                  )}
                </div>
                {slotCount === 0 ? (
                  <div className="text-xs text-ink-faint">
                    none this instant — between batches
                  </div>
                ) : (
                  <div className="grid gap-3 lg:grid-cols-2">
                    {workers.map((w, i) => {
                      const gid = detail?.goals.find((g) => g.slug === w.slug)?.id
                      return (
                        <div
                          key={`${w.kind}:${w.slug}:${i}`}
                          onMouseEnter={() =>
                            gid !== undefined && setLaneHover([gid])
                          }
                          onMouseLeave={() => setLaneHover(null)}
                        >
                          <Lane
                            w={w}
                            problem={data.problem}
                            multi={(data.problems?.length ?? 0) > 1}
                          />
                        </div>
                      )
                    })}
                    {/* receipts occupy the slots they just vacated —
                        never MORE cells than dispatch.pool (owner:
                        slot=4 means the grid tops out at 4) */}
                    {(ghostsRef.current = ghostsRef.current.filter(
                      (g) => g.until > Date.now(),
                    ))
                      .slice(0, Math.max(0, slotCount - workers.length))
                      .map((g) => {
                      const goal = detail?.goals.find((x) => x.slug === g.slug)
                      const held = g.leased_at
                        ? duration(
                            Math.max(
                              0,
                              (g.until - 30_000 - Date.parse(g.leased_at)) / 1000,
                            ),
                          )
                        : null
                      return (
                        <div
                          key={`${g.k}:${g.until}`}
                          className="min-h-24 rounded-xl border border-edge/60 bg-surface/50 p-3 opacity-70"
                        >
                          <div className="flex items-baseline gap-2.5">
                            <span className="text-xs text-ink-dim">
                              {g.kind.toLowerCase()}
                            </span>
                            {/* a receipt is the moment you most want to
                                READ what landed — the name opens it */}
                            {focusProblem ? (
                              <GoalLink problem={focusProblem} slug={g.slug} />
                            ) : (
                              <span className="max-w-72 truncate font-mono text-xs text-ink-faint">
                                {g.slug}
                              </span>
                            )}
                            <span className="tnum ml-auto text-[11px] text-ink-faint">
                              landed{held ? ` · ${held} on it` : ''}
                            </span>
                          </div>
                          <div className="mt-2 text-[11px] text-ink-faint">
                            {goal
                              ? `the goal is now ${goalStatusLabel(goal.status)}`
                              : 'finished — the result lands on the problem page'}
                          </div>
                        </div>
                      )
                    })}
                    {/* one card PER free slot — a slot is a fixed berth
                        (owner, 2026-07-14: collapsing them broke the
                        spatial metaphor); quieter ink than the working
                        lanes so the vacancies never compete */}
                    {(() => {
                      const ghostsShown = Math.min(
                        ghostsRef.current.length,
                        Math.max(0, slotCount - workers.length),
                      )
                      const free = slotCount - workers.length - ghostsShown
                      return Array.from({ length: Math.max(0, free) }).map((_, i) => (
                        <div
                          key={`free${i}`}
                          className="flex min-h-24 items-center justify-center rounded-xl border border-dashed border-edge/60 text-[11px] text-ink-faint/70"
                          title="an open slot for one more agent (engine setting: dispatch.pool)"
                        >
                          {freeHint}
                        </div>
                      ))
                    })()}
                  </div>
                )}
              </>
            )
          })()}
        </section>
      )}

      {(() => {
        // seats per backend, from the declaration-driven rows. Until
        // meta answers, show the meter as before — hiding a real
        // reading on a flaky poll would be the worse lie.
        const seated = (meta?.providers ?? []).filter((p) => p.seats.length > 0)
        const claudeSeats =
          meta === null
            ? null
            : (seated.find((p) => p.name === 'claude')?.seats ?? []).map((x) => x.seat)
        const others = seated.filter((p) => p.name !== 'claude')
        const showMeter = data.quota && (claudeSeats === null || claudeSeats.length > 0)
        if (!showMeter && others.length === 0 && (claudeSeats?.length ?? 0) === 0) return null
        return (
        <section className="mt-7">
          {/* the gloss and the switch-account move both moved to the
              console's own Settings page (owner, 2026-08-07): here the
              meters are what you watch while it burns, and a label is
              enough — but the label must SAY WHOSE window this is:
              an unlabeled meter under a zen fleet read as the run's
              own quota when nothing on screen was spending Claude */}
          <div className="mb-3 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
            {showMeter ? (
              <span title="engine term: quota windows — usage read live from your Claude subscription. Shown while any seat rides it.">
                claude plan
                {claudeSeats !== null && claudeSeats.length > 0 && (
                  <span className="ml-2 font-normal tracking-normal normal-case">
                    · {claudeSeats.join(' · ')}
                  </span>
                )}
              </span>
            ) : (
              <span title="what each seated backend lets this console know about its remaining allowance">
                plan usage
              </span>
            )}
          </div>
          {!showMeter ? null : (
          <div className="flex max-w-xl flex-col gap-2">
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
          {/* the other seated backends: none of them can be ASKED
              before spending (usage_endpoint is claude's alone), so
              the honest row is who rides them and why no meter —
              silence here read as "no other account is being spent" */}
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

      {/* a fresh workspace has nothing to (re)run from here — point at
          the Board instead of describing a button that isn't on screen */}
      {!running && !focusProblem && (
        <p className="mt-8 text-xs text-ink-faint">
          Nothing has run yet — pick a problem on the{' '}
          <Link
            to="/"
            className="underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink"
          >
            Board
          </Link>
          ; its page has the Run button.
        </p>
      )}
    </div>
  )
}
