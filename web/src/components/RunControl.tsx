import { useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { SCHEMA_BEHIND_LINE, schemaBehind } from '../lib/daemon'
import { scopeCovers } from '../lib/programmeFocus'
import { Link } from '../lib/router'
import { RunConfirm } from './CommandConfirm'
import { Button } from './ui'
import type { DaemonStatus } from '../lib/types'

/*
 * Per-problem engine control — the default way to run Asterism is one
 * problem at a time, from that problem's page. Honesty constraint: the
 * engine is ONE process per workspace with a scope filter, so when it
 * is busy on another scope this control says so instead of pretending
 * per-problem runs are independent.
 *
 * There is exactly ONE Run and ONE Stop in the console, and they are
 * here (2026-09-04). Before that the shelf's Run read the engine first
 * and confirmed in a window while this page started on a bare click,
 * and the shelf's Stop had the force step while this one did not — so
 * a benched task, an engine already running, or a drain that will not
 * finish read differently depending on which page you pressed the
 * button from.
 */

/** Stop, and the force step behind it.
 *
 * A plain Stop DRAINS: in-flight work finishes and then the daemon
 * exits, which can take minutes. So while it is draining the button
 * renames itself, and a second press inside three seconds is the
 * escalation — the window closes on its own, because a kill nobody
 * asked for twice in a row is not a kill the reader meant. */
export function StopButton({
  stopping,
  title,
  onDone,
}: {
  /** the daemon is already draining — the next press escalates */
  stopping: boolean
  /** what a plain Stop does here, when the page knows something the
   * button does not (a fleet scope stops more than this one task) */
  title?: string
  /** the request settled; `ok` is false if the engine refused it */
  onDone?: (ok: boolean) => void
}) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [confirmForce, setConfirmForce] = useState(false)
  const timer = useRef<number | null>(null)
  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )
  const stop = async (force: boolean) => {
    setBusy(true)
    setErr(null)
    let ok = true
    try {
      await apiPost('/api/daemon/stop', { force })
    } catch (e) {
      // stays until the next attempt clears it — a failure that fades
      // on its own is a failure the user can miss
      ok = false
      setErr(`couldn't stop: ${String((e as Error).message)}`)
    } finally {
      setBusy(false)
      setConfirmForce(false)
      onDone?.(ok)
    }
  }
  return (
    <>
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
            if (stopping) {
              setConfirmForce(true)
              if (timer.current !== null) window.clearTimeout(timer.current)
              timer.current = window.setTimeout(() => setConfirmForce(false), 3000)
            } else {
              void stop(false)
            }
          }}
          title={
            stopping
              ? 'already stopping — press again to force'
              : (title ?? 'finish in-flight work, then exit')
          }
        >
          {stopping ? 'Force stop…' : 'Stop'}
        </Button>
      )}
      {err && <span className="max-w-72 text-[11px] leading-snug text-danger">{err}</span>}
    </>
  )
}

export default function RunControl({
  project,
  problem,
  engineHref,
}: {
  /** the shelf this task is filed on — the run preview is asked about
   * it, the way the shelf's own Run asks */
  project: string
  problem: string
  /** the engine room of the Project this control sits in — the busy
   * message has to name a place the reader can actually reach */
  engineHref?: string
}) {
  const { data: d, refresh } = usePoll<DaemonStatus>('/api/daemon', 2000)
  /** the run's confirm window (§1.3) — the same one the shelf opens,
   * over a list of exactly this task */
  const [confirmRun, setConfirmRun] = useState(false)

  if (!d) return null
  // the status could not open the DB (its schema trails this engine's
  // code), so nothing it would say about THIS problem's run is a
  // reading. Say the one thing that is true and name the action.
  if (schemaBehind(d))
    return <span className="text-[11px] text-ink-faint">{SCHEMA_BEHIND_LINE}</span>
  // COVERS, not equals: a fleet's scope is a LIKE pattern, and every
  // member's page read "engine busy elsewhere" about its own run
  // (2026-08-22, the first Erdos fleet)
  const mine = d.running && scopeCovers(d.scope, problem)
  const fleet = mine && d.scope !== problem
  // boot window: the engine hasn't claimed its lock yet — without this
  // state the button flashed Run again seconds after being pressed
  // (owner, 2026-07-12). No Stop here: a stop request during boot is
  // swept by the child's own startup hygiene.
  const startingMine = !d.running && d.starting && scopeCovers(d.scope, problem)
  const busyElsewhere = (d.running || d.starting) && !mine && !startingMine

  return (
    <span className="flex items-center gap-2">
      {startingMine ? (
        <span className="flex items-center gap-1.5 text-[11px] text-accent">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          engine starting — a few seconds
        </span>
      ) : mine ? (
        <>
          <span
            className="flex items-center gap-1.5 text-[11px] text-accent"
            title="the engine runs on this machine — closing this page does not stop it; only Stop does"
          >
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            {/* the first minutes of a cold run are Lean warm-up — name
                the phase or it reads as dead air */}
            {d.stopping
              ? 'engine running — stopping'
              : d.gateway === 'warming'
                ? 'warming the Lean toolchain — a few minutes on a cold start'
                : fleet
                  ? 'engine running — this problem rides a fleet'
                  : 'engine running'}
          </span>
          <StopButton
            stopping={d.stopping}
            title={fleet ? `stops the whole run — every problem under ${d.scope}` : undefined}
            onDone={() => refresh()}
          />
        </>
      ) : busyElsewhere ? (
        <span className="text-[11px] text-ink-faint">
          engine busy — <span className="font-mono">{d.scope ?? 'all tasks'}</span>
          {engineHref && (
            <>
              {' · '}
              <Link
                to={engineHref}
                className="underline decoration-ink-faint underline-offset-2 hover:text-ink"
              >
                engine room
              </Link>
            </>
          )}
        </span>
      ) : (
        <>
          {/* the last run on THIS problem crashed — say so where the
              user will retry, in words they can act on */}
          {d.last_exit !== null &&
            d.last_exit.rc !== null &&
            d.last_exit.rc !== 0 &&
            scopeCovers(d.last_exit.scope, problem) && (
              <span className="max-w-96 text-[11px] leading-snug text-danger">
                the last run crashed
                {d.last_exit.error?.includes('gateway')
                  ? ' while starting the Lean toolchain — Run again usually clears it; if it repeats, read the engine log in the engine room'
                  : ` (${d.last_exit.error ?? 'unknown error'}) — read the engine log in the engine room`}
              </span>
            )}
          <Button
            variant="primary"
            title="read what running this task would do — the run starts from the next step"
            onClick={() => setConfirmRun(true)}
          >
            Run…
          </Button>
        </>
      )}
      {confirmRun && (
        <RunConfirm
          project={project}
          problems={[problem]}
          onClose={() => setConfirmRun(false)}
          onStarted={refresh}
        />
      )}
    </span>
  )
}
