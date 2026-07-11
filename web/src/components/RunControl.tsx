import { useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link } from '../lib/router'
import type { DaemonStatus } from '../lib/types'

/*
 * Per-problem engine control — the default way to run Asterism is one
 * problem at a time, from that problem's page. Honesty constraint: the
 * engine is ONE process per workspace with a scope filter, so when it
 * is busy on another scope this control says so instead of pretending
 * per-problem runs are independent.
 */

export default function RunControl({ problem }: { problem: string }) {
  const { data: d, refresh } = usePoll<DaemonStatus>('/api/daemon', 2000)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const act = async (path: string, body: Record<string, unknown>, verb: 'start' | 'stop') => {
    setBusy(true)
    setErr(null)
    try {
      await apiPost(path, body)
    } catch (e) {
      // stays until the next attempt clears it — a failure that fades
      // on its own is a failure the user can miss
      setErr(`couldn't ${verb}: ${String((e as Error).message)}`)
    } finally {
      setBusy(false)
      refresh()
    }
  }

  if (!d) return null
  const mine = d.running && d.scope === problem
  // boot window: the engine hasn't claimed its lock yet — without this
  // state the button flashed Run again seconds after being pressed
  // (owner, 2026-07-12). No Stop here: a stop request during boot is
  // swept by the child's own startup hygiene.
  const startingMine = !d.running && d.starting && d.scope === problem
  const busyElsewhere = (d.running || d.starting) && !mine && !startingMine

  return (
    <span className="flex items-center gap-2">
      {err && (
        <span className="max-w-72 text-[11px] leading-snug text-danger">
          {err}
        </span>
      )}
      {startingMine ? (
        <span className="flex items-center gap-1.5 text-[11px] text-accent">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          engine starting — a few seconds
        </span>
      ) : mine ? (
        <>
          <span className="flex items-center gap-1.5 text-[11px] text-accent">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            {/* the first minutes of a cold run are Lean warm-up — name
                the phase or it reads as dead air */}
            {d.stopping
              ? 'engine running — stopping'
              : d.gateway === 'warming'
                ? 'warming the Lean toolchain — a few minutes on a cold start'
                : 'engine running'}
          </span>
          <button
            className="rounded-md border border-edge px-3 py-1.5 text-xs text-ink-dim transition-colors hover:border-edge-strong hover:text-ink disabled:pointer-events-none disabled:opacity-45"
            disabled={busy || d.stopping}
            onClick={() => void act('/api/daemon/stop', { force: false }, 'stop')}
          >
            Stop
          </button>
        </>
      ) : busyElsewhere ? (
        <span className="text-[11px] text-ink-faint">
          engine busy — <span className="font-mono">{d.scope ?? 'all problems'}</span> ·{' '}
          <Link to="/telemetry" className="underline decoration-ink-faint underline-offset-2 hover:text-ink">
            Engine
          </Link>
        </span>
      ) : (
        <>
          {/* the last run on THIS problem crashed — say so where the
              user will retry, in words they can act on */}
          {err === null &&
            d.last_exit !== null &&
            d.last_exit.rc !== null &&
            d.last_exit.rc !== 0 &&
            d.last_exit.scope === problem && (
              <span className="max-w-96 text-[11px] leading-snug text-danger">
                the last run crashed
                {d.last_exit.error?.includes('gateway')
                  ? ' while starting the Lean toolchain — Run again usually clears it; if it repeats, see the engine log on the Run page'
                  : ` (${d.last_exit.error ?? 'unknown error'}) — see the engine log on the Run page`}
              </span>
            )}
          <button
            className="rounded-md bg-ink px-3 py-1.5 text-xs font-semibold text-bg transition-colors hover:bg-starlight disabled:pointer-events-none disabled:opacity-45"
            disabled={busy}
            title="run the engine on this problem only"
            onClick={() => void act('/api/daemon/start', { scope: problem }, 'start')}
          >
            {busy ? 'Starting…' : 'Run'}
          </button>
        </>
      )}
    </span>
  )
}
