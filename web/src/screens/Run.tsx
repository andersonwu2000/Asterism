import { useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { weightedBurn } from '../lib/burn'
import { switchAccount } from '../lib/claudeAuth'
import { compactNumber, duration } from '../lib/format'
import { Lean } from '../lib/lean'
import { Link } from '../lib/router'
import { Button } from '../components/ui'
import Constellation from '../components/Constellation'
import GoalPanel from '../components/GoalPanel'
import type { ConfigSetting, ProblemDetail, RunStatus, RunWorker } from '../lib/types'

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

/** One agent, one lane: what it is, what it's on, what it's writing. */
function Lane({ w, problem }: { w: RunWorker; problem: string | null }) {
  const quiet = w.file?.quiet_sec ?? null
  return (
    <div className="rounded-lg border border-edge bg-surface p-3">
      <div className="flex items-baseline gap-2.5">
        <span className="text-xs font-medium text-ink">{w.kind.toLowerCase()}</span>
        {problem ? (
          <Link
            to={`/problems/${encodeURIComponent(problem)}`}
            className="max-w-72 truncate font-mono text-xs text-ink-dim transition-colors hover:text-ink"
            title={`${w.slug} — open the problem`}
          >
            {w.slug}
          </Link>
        ) : (
          <span className="max-w-72 truncate font-mono text-xs text-ink-dim">{w.slug}</span>
        )}
        <span className="tnum ml-auto text-[11px] text-ink-faint" title="how long this agent has held the unit">
          on it {laneAge(w.leased_at) ?? '—'}
        </span>
      </div>
      {w.statement && (
        <div className="mt-1 truncate font-mono text-[11px] text-ink-faint" title={w.statement}>
          <Lean code={w.statement} />
        </div>
      )}
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
            {' · '}
            {compactNumber(w.file.size)} bytes
            {w.path && <span className="ml-1 font-mono">· {w.path.split('/').pop()}</span>}
          </summary>
          <pre className="mt-1.5 max-h-44 overflow-hidden rounded-md border border-edge bg-bg px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink-dim">
            <Lean code={w.file.tail} />
          </pre>
        </details>
      ) : (
        <div className="mt-2 text-[11px] text-ink-faint">
          {w.kind === 'Strategist'
            ? 'reading the state, deciding the next moves — nothing on disk yet'
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
 * with the reset moment — spend against the REAL ceiling. */
function QuotaMeter({
  label,
  pct,
  resetsAt,
}: {
  label: string
  pct: number
  resetsAt: string | null
}) {
  const clamped = Math.max(0, Math.min(100, pct))
  const resets = resetsAt
    ? new Date(resetsAt).toLocaleString(undefined, {
        weekday: clamped >= 0 && label.includes('week') ? 'short' : undefined,
        hour: '2-digit',
        minute: '2-digit',
      })
    : null
  return (
    <div className="flex items-center gap-3">
      <span className="w-32 shrink-0 text-xs text-ink-dim">{label}</span>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-surface-2">
        <div
          className={`h-full ${clamped >= 85 ? 'bg-warn' : 'bg-starlight/60'}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="tnum w-10 text-right text-xs text-ink">{Math.round(clamped)}%</span>
      <span className="tnum w-28 text-[11px] text-ink-faint">
        {resets ? `resets ${resets}` : ''}
      </span>
    </div>
  )
}

export default function Run() {
  const { data, refresh } = usePoll<RunStatus>('/api/run', 2000)
  const { data: cfg } = usePoll<{ settings: ConfigSetting[] }>('/api/config', 60000)
  // the sky rides along (owner: the console shows the constellation):
  // full problem detail only when a problem is in focus
  const focusProblem = data?.problem ?? null
  const { data: detail } = usePoll<ProblemDetail>(
    focusProblem ? `/api/problems/${encodeURIComponent(focusProblem)}` : null,
    3000,
  )
  const [selGoal, setSelGoal] = useState<number | null>(null)
  useEffect(() => setSelGoal(null), [focusProblem])
  useTick(1000)

  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [switching, setSwitching] = useState(false)
  const [switchMsg, setSwitchMsg] = useState<string | null>(null)
  const doSwitch = async () => {
    setSwitching(true)
    try {
      setSwitchMsg(await switchAccount())
    } catch (e) {
      setSwitchMsg(String((e as Error).message))
    } finally {
      setSwitching(false)
    }
  }
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

  if (!data) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>

  const d = data.daemon
  const running = d.running
  const workers = data.workers
  const phase = !running
    ? 'Idle'
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
    Stopping: 'finishing in-flight work, then a clean exit — Force stop skips the wait',
    'Warming up': 'first start heats the Lean toolchain — a few minutes, then proving begins',
    Planning: 'the Strategist is reading the state and deciding the next moves',
    Proving: 'agents are attempting goals right now',
    Harvesting: 'finished work is being curated into the Library',
  }
  const wall = running ? wallClock(d.started_at) : null
  const crashed = !running && d.last_exit && d.last_exit.rc !== 0 && d.last_exit.rc !== null

  // burn: weighted units against the subscription window (no USD, no
  // pretend quota ceiling — spend and rate, honestly labelled)
  const sumBurn = (b: { problems: { kinds: never[] }[] } | null): number =>
    b ? b.problems.reduce((s, p) => s + weightedBurn(p.kinds, cfg?.settings), 0) : 0
  const burnRun = sumBurn(data.burn_run as never)
  const burn5h = sumBurn(data.burn_5h as never)
  const elapsedMin = d.started_at
    ? Math.max(1 / 60, (Date.now() - Date.parse(d.started_at)) / 60000)
    : null
  const rate = running && elapsedMin ? burnRun / elapsedMin : null

  const g = data.goals

  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <span className="flex items-center gap-3">
          <span
            className={`h-3 w-3 rounded-full ${
              running
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
            title="open the problem — its sky, goals, manifest"
          >
            {data.problem}
          </Link>
        )}
        {wall && <span className="tnum font-mono text-sm text-ink-dim">{wall}</span>}
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
      </div>
      <div className="mt-1 text-xs text-ink-faint">{phaseHint[phase]}</div>

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
        </div>
      )}

      {msg && <div className="mt-3 text-xs text-ink-dim">{msg}</div>}

      {detail && focusProblem && detail.goals.length > 0 && (
        <section className="mt-6">
          <div className="flex h-[52vh] overflow-hidden rounded-lg border border-edge bg-bg">
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
              />
            </div>
            {selGoal !== null && (
              <GoalPanel
                problem={focusProblem}
                goalId={selGoal}
                onClose={() => setSelGoal(null)}
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
                : 'free — waiting for the dispatcher'
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
                    {workers.map((w, i) => (
                      <Lane key={`${w.kind}:${w.slug}:${i}`} w={w} problem={data.problem} />
                    ))}
                    {Array.from({ length: Math.max(0, slotCount - workers.length) }).map(
                      (_, i) => (
                        <div
                          key={`free${i}`}
                          className="flex min-h-24 items-center justify-center rounded-lg border border-dashed border-edge text-[11px] text-ink-faint"
                          title="one of dispatch.pool parallel work slots"
                        >
                          {freeHint}
                        </div>
                      ),
                    )}
                  </div>
                )}
              </>
            )
          })()}
        </section>
      )}

      {data.quota && (
        <section className="mt-7">
          <div className="mb-3 flex items-baseline text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
            plan windows
            <span className="ml-2 font-normal tracking-normal normal-case text-ink-faint/80">
              your subscription's own meters
            </span>
            {/* the quota-reset move lives WHERE you watch the quota:
                switch accounts without leaving the console (owner) */}
            <button
              className="ml-auto cursor-pointer font-normal tracking-normal normal-case underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink disabled:opacity-50"
              disabled={switching}
              onClick={() => void doSwitch()}
              title="log this account out and open the login window for another — running agents keep their session; new work uses the new account"
            >
              switch account
            </button>
          </div>
          {switchMsg && <div className="mb-2 text-[11px] text-ink-faint">{switchMsg}</div>}
          <div className="flex max-w-xl flex-col gap-2">
            {(
              [
                ['5-hour window', data.quota.five_hour],
                ['week', data.quota.seven_day],
              ] as const
            ).map(
              ([label, w]) =>
                w && (
                  <QuotaMeter key={label} label={label} pct={w.utilization} resetsAt={w.resets_at} />
                ),
            )}
            {data.quota.scoped
              .filter((s) => s.is_active)
              .map((s) => (
                <QuotaMeter
                  key={s.name}
                  label={`${s.name} · week`}
                  pct={s.percent}
                  resetsAt={s.resets_at}
                />
              ))}
          </div>
        </section>
      )}

      {(running || burn5h > 0) && (
      <section className="mt-7">
        <div className="mb-3 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
          burn
        </div>
        <div className="flex flex-wrap gap-x-8 gap-y-2">
          {running && (
            <div>
              <div className="tnum font-display text-[20px] text-ink">
                {compactNumber(Math.round(burnRun))}
              </div>
              <div
                className="text-[11px] text-ink-faint"
                title="tokens weighted by each pipeline's model price (top-model output = 1 unit) — a quota share, not a token count"
              >
                weighted, this run
              </div>
            </div>
          )}
          {rate !== null && rate > 0 && (
            <div>
              <div className="tnum font-display text-[20px] text-ink">
                {compactNumber(Math.round(rate))}
                <span className="text-[12px] text-ink-dim">/min</span>
              </div>
              <div className="text-[11px] text-ink-faint">burn rate</div>
            </div>
          )}
          <div>
            <div className="tnum font-display text-[20px] text-ink">
              {compactNumber(Math.round(burn5h))}
            </div>
            <div
              className="text-[11px] text-ink-faint"
              title="everything spent in the trailing 5 hours — the same window your subscription meters; Asterism cannot see the plan's ceiling, so it shows the spend"
            >
              weighted, last 5h
            </div>
          </div>
        </div>
      </section>
      )}

      {!running && (
        <p className="mt-8 text-xs text-ink-faint">
          To run a problem, press Run on its page — the engine works one problem at a time.
        </p>
      )}
    </div>
  )
}
