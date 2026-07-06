import { Fragment, useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { compactNumber, duration } from '../lib/format'
import { Button, SectionLabel } from '../components/ui'
import type { ConfigSetting, DaemonStatus, UsageProblem } from '../lib/types'

/** Engine panel + usage telemetry (charter §3.4); the Library browses at #/library. */

/** "for 42m" / "for 3h 07m" — how long the current run has been going. */
function runElapsed(startedAt: string): string {
  const sec = Math.max(0, (Date.now() - Date.parse(startedAt)) / 1000)
  return duration(sec)
}

/** Idle must not wear one face for three endings: clean finish,
 * user's force stop, and a crash each say what happened. */
function lastExitLine(e: DaemonStatus['last_exit']): string {
  if (!e) return 'the engine is not running'
  if (e.rc === 0) return 'the engine is not running — the last run finished cleanly'
  if (e.rc === null) return 'the engine is not running — you force-stopped the last run'
  return `the last run exited abnormally (${e.error ?? 'unknown error'}) — details in the developer log`
}

function DaemonPanel() {
  const { data: d, refresh } = usePoll<DaemonStatus>('/api/daemon', 2000)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  // Force stop is two-step (same pattern as the Inbox's Reject →
  // Confirm reject): first press arms it, 3s of silence disarms.
  const [confirmForce, setConfirmForce] = useState(false)
  const forceTimer = useRef<number | null>(null)
  useEffect(
    () => () => {
      if (forceTimer.current !== null) window.clearTimeout(forceTimer.current)
    },
    [],
  )
  const armForce = () => {
    setConfirmForce(true)
    if (forceTimer.current !== null) window.clearTimeout(forceTimer.current)
    forceTimer.current = window.setTimeout(() => setConfirmForce(false), 3000)
  }
  const disarmForce = () => {
    if (forceTimer.current !== null) window.clearTimeout(forceTimer.current)
    forceTimer.current = null
    setConfirmForce(false)
  }

  const act = async (path: string, body: Record<string, unknown>) => {
    setBusy(true)
    setMsg(null)
    try {
      const r = await apiPost<{ message: string }>(path, body)
      setMsg(r.message)
    } catch (e) {
      setMsg(String((e as Error).message))
    } finally {
      setBusy(false)
      refresh()
    }
  }

  return (
    <div className="rounded-lg border border-edge bg-surface p-4">
      <div className="mb-3 flex items-baseline gap-3">
        <span className="flex items-center gap-2.5">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              d?.running ? (d.stopping ? 'bg-warn' : 'bg-ok animate-pulse') : 'bg-ink-faint'
            }`}
          />
          <span className="font-display text-[22px] font-medium text-ink">
            {d?.running ? (d.stopping ? 'Stopping' : 'Running') : 'Idle'}
          </span>
        </span>
        <span className="text-xs text-ink-faint">
          {d?.running && d.stopping
            ? `pid ${d.pid} — draining ${d.in_flight_leases} in-flight lease${d.in_flight_leases === 1 ? '' : 's'}; if this hangs on a stale lease, Force stop is safe`
            : d?.running
              ? `working on ${d.scope ?? 'all problems'}${
                  d.gateway === 'warming' ? ' · warming the Lean toolchain' : ''
                }${
                  d.started_at ? ` · for ${runElapsed(d.started_at)}` : ''
                } · pid ${d.pid}${d.in_flight_leases > 0 ? ` · ${d.in_flight_leases} in flight` : ''}`
              : lastExitLine(d?.last_exit ?? null)}
        </span>
      </div>
      {d && !d.running && d.in_flight_leases > 0 && (
        <div className="mb-3 rounded-md border border-edge bg-surface-2 px-3 py-1.5 text-xs text-ink-dim">
          {d.in_flight_leases} orphaned work lease(s) from a previous run — reclaimed
          automatically on the next engine start.
        </div>
      )}
      <div className="flex items-center gap-2">
        {!d?.running ? (
          <span className="text-xs text-ink-faint">
            to run a problem, press Run on its page — the engine works one problem at a time
          </span>
        ) : (
          <>
            <Button
              variant="outline"
              disabled={busy || d.stopping}
              onClick={() => void act('/api/daemon/stop', { force: false })}
            >
              Stop (graceful)
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => {
                if (confirmForce) {
                  disarmForce()
                  void act('/api/daemon/stop', { force: true })
                } else {
                  armForce()
                }
              }}
            >
              {confirmForce ? 'Confirm force stop' : 'Force stop'}
            </Button>
            {confirmForce && (
              <span className="text-[11px] text-ink-faint">
                kills agents mid-attempt — unfinished work is reclaimed on the next run
              </span>
            )}
          </>
        )}
      </div>
      {msg && <div className="mt-2 font-mono text-[11px] text-ink-dim">{msg}</div>}
    </div>
  )
}

function ConfigPanel() {
  const { data, refresh } = usePoll<{ settings: ConfigSetting[] }>('/api/config', 60000)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [msg, setMsg] = useState<string | null>(null)
  if (!data) return null
  const save = async (key: string) => {
    setMsg(null)
    try {
      const r = await apiPost<{ message: string }>('/api/config', {
        key,
        value: drafts[key],
      })
      setMsg(r.message)
      setDrafts((d) => {
        const next = { ...d }
        delete next[key]
        return next
      })
      refresh()
    } catch (e) {
      setMsg(String((e as Error).message))
    }
  }
  const models = data.settings.filter((s) => s.key.endsWith('.model'))
  const knobs = data.settings.filter((s) => !s.key.endsWith('.model'))
  const row = (s: ConfigSetting) => {
    const draft = drafts[s.key]
    const current = String(s.resolved ?? '')
    return (
      <div key={s.key} className="flex items-center gap-3 py-1">
        <span className="w-44 shrink-0 font-mono text-xs text-ink-dim">{s.key}</span>
        <input
          className="w-56 rounded border border-edge bg-bg px-2 py-1 font-mono text-xs text-ink focus:border-ink-faint focus:outline-none"
          value={draft ?? current}
          onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
        />
        {draft !== undefined && draft !== current && (
          <button
            className="rounded-md bg-ink px-2 py-1 text-[11px] font-semibold text-bg transition-colors hover:bg-starlight"
            onClick={() => void save(s.key)}
          >
            Save
          </button>
        )}
        <span className="min-w-0 truncate text-[11px] text-ink-faint">{s.description}</span>
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-edge bg-surface px-4 py-3">
      <div className="mb-1 text-[11px] text-ink-faint">
        which model does each job — changes apply from the next run (an .env override, if
        you have one, still wins)
      </div>
      {models.map(row)}
      <div className="mt-3 mb-1 text-[11px] text-ink-faint">engine knobs</div>
      {knobs.map(row)}
      {msg && <div className="mt-2 font-mono text-[11px] text-ink-dim">{msg}</div>}
    </div>
  )
}


function LogTail() {
  const [lines, setLines] = useState<string[]>([])
  const boxRef = useRef<HTMLDivElement>(null)
  const stickBottom = useRef(true)

  useEffect(() => {
    const es = new EventSource('/api/events/stream')
    es.onmessage = (e) => {
      setLines((prev) => {
        const next = [...prev, e.data as string]
        return next.length > 500 ? next.slice(next.length - 500) : next
      })
    }
    return () => es.close()
  }, [])

  useEffect(() => {
    const el = boxRef.current
    if (el && stickBottom.current) el.scrollTop = el.scrollHeight
  }, [lines])

  // Empty panels collapse to one line — a 260px empty box conveys one
  // sentence (design review).
  if (lines.length === 0) {
    return (
      <div className="rounded-lg border border-edge bg-surface px-3 py-2 text-xs text-ink-faint">
        No log output yet — the tail picks up when a daemon run starts.
      </div>
    )
  }
  return (
    <div
      ref={boxRef}
      className="h-64 overflow-y-auto rounded-lg border border-edge bg-bg p-3"
      onScroll={(e) => {
        const el = e.currentTarget
        stickBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 30
      }}
    >
      <pre className="font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink-dim">
        {lines.join('\n')}
      </pre>
    </div>
  )
}

function Stat({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="rounded-lg border border-edge bg-surface px-4 py-3" title={title}>
      <div className="font-display tnum text-[26px] font-medium text-ink">{value}</div>
      <div className="mt-0.5 text-[11px] text-ink-faint">{label}</div>
    </div>
  )
}

/** Per-model price weights, Opus-output ≡ 1 unit (demo/watcher.py
 * lineage — the owner's quota-burn axis: on a subscription, quota is
 * metered roughly by backend cost, so weighted units beat raw token
 * counts). Unknown models assume Sonnet tier — never under-count a
 * release this table hasn't met. */
const PRICE_TIERS: [RegExp, { in: number; cw: number; cr: number; out: number }][] = [
  [/fable|mythos|opus-4-[5-9]/, { in: 0.2, cw: 0.25, cr: 0.02, out: 1.0 }],
  [/opus/, { in: 0.6, cw: 0.75, cr: 0.06, out: 3.0 }],
  [/haiku/, { in: 0.04, cw: 0.05, cr: 0.004, out: 0.2 }],
]
const SONNET_TIER = { in: 0.12, cw: 0.15, cr: 0.012, out: 0.6 }
function priceWeights(model: string) {
  for (const [re, w] of PRICE_TIERS) if (re.test(model)) return w
  return SONNET_TIER
}

function UsageTable() {
  const { data } = usePoll<{ problems: UsageProblem[]; window?: 'run' | 'all' }>(
    '/api/telemetry/usage',
    10000,
  )
  // kind → model (from settings) turns raw tokens into weighted burn
  const { data: cfg } = usePoll<{ settings: ConfigSetting[] }>('/api/config', 60000)
  const [expanded, setExpanded] = useState<string | null>(null)
  const rows = data?.problems ?? []
  // the server says which window it aggregated — never claim "this
  // run" over an all-time ledger (it used to)
  const label = data?.window === 'run' ? 'usage — this run' : 'usage — all time'
  if (rows.length === 0)
    return (
      <>
        <SectionLabel>{label}</SectionLabel>
        <div className="rounded-lg border border-edge bg-surface px-4 py-2 text-xs text-ink-faint">
          {data?.window === 'run'
            ? 'Nothing burned yet this run — figures appear as the engine works.'
            : 'No usage yet — figures appear once the engine runs.'}
        </div>
      </>
    )
  const total = rows.reduce(
    (a, p) => ({
      spawns: a.spawns + p.spawns,
      out: a.out + p.output_tokens,
      inTok: a.inTok + p.input_tokens + p.cache_read_tokens,
      inRaw: a.inRaw + p.input_tokens,
      cr: a.cr + p.cache_read_tokens,
      cw: a.cw + p.cache_new_tokens,
      wall: a.wall + p.wall_sec,
    }),
    { spawns: 0, out: 0, inTok: 0, inRaw: 0, cr: 0, cw: 0, wall: 0 },
  )
  const modelFor = (kind: string): string =>
    String(cfg?.settings.find((s) => s.key === `${kind.toLowerCase()}.model`)?.resolved ?? '')
  const weighted = rows
    .flatMap((p) => p.kinds)
    .reduce((a, k) => {
      const w = priceWeights(modelFor(k.kind))
      return (
        a +
        k.input_tokens * w.in +
        (k.cache_new_tokens ?? 0) * w.cw +
        k.cache_read_tokens * w.cr +
        k.output_tokens * w.out
      )
    }, 0)
  const cacheDenom = total.inRaw + total.cw + total.cr
  return (
    <>
      <SectionLabel>{label}</SectionLabel>
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="agent spawns" value={String(total.spawns)} />
        <Stat label="output tokens" value={compactNumber(total.out)} />
        <Stat label="input + cache read" value={compactNumber(total.inTok)} />
        <Stat
          label="weighted burn"
          value={compactNumber(Math.round(weighted))}
          title="≈ share of quota: tokens weighted by each pipeline's model price (top-model output = 1 unit) — comparable across model tiers, unlike raw counts"
        />
        <Stat label="agent wall time" value={duration(total.wall)} />
      </div>
      {cacheDenom > 0 && (
        <div className="mb-3 -mt-1 text-[11px] text-ink-faint">
          cache hit share{' '}
          <span className="tnum text-ink-dim">{((total.cr / cacheDenom) * 100).toFixed(1)}%</span>{' '}
          — the slice of the prompt bill served from cache instead of re-billed
        </div>
      )}
      {(rows.length > 1 || expanded !== null) && inner(rows, expanded, setExpanded)}
      {rows.length === 1 && expanded === null && (
        <button
          className="text-[11px] text-ink-faint transition-colors hover:text-ink"
          onClick={() => setExpanded(rows[0].problem)}
        >
          everything above is{' '}
          <span className="font-mono">{rows[0].problem}</span> — break it down by agent kind
        </button>
      )}
    </>
  )
}

function inner(
  rows: UsageProblem[],
  expanded: string | null,
  setExpanded: (v: string | null) => void,
) {
  return (
    <table className="w-full border-collapse text-left">
      <thead>
        <tr className="border-b border-edge text-xs text-ink-faint">
          <th className="py-2 pr-4 pl-2 font-medium">problem</th>
          <th className="py-2 pr-4 text-right font-medium">spawns</th>
          <th className="py-2 pr-4 text-right font-medium">input+cache</th>
          <th className="py-2 pr-4 text-right font-medium">output tok</th>
          <th className="py-2 pr-4 text-right font-medium">turns</th>
          <th className="py-2 pr-4 text-right font-medium">wall</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p) => (
          <Fragment key={p.problem}>
            <tr
              className="cursor-pointer border-b border-edge/60 hover:bg-surface"
              onClick={() => setExpanded(expanded === p.problem ? null : p.problem)}
            >
              <td className="py-2 pr-4 pl-2 font-mono text-xs text-ink">{p.problem}</td>
              <td className="py-2 pr-4 text-right text-xs text-ink-dim">{p.spawns}</td>
              <td className="py-2 pr-4 text-right text-xs text-ink-dim">
                {compactNumber(p.input_tokens + p.cache_read_tokens)}
              </td>
              <td className="py-2 pr-4 text-right text-xs text-ink-dim">
                {compactNumber(p.output_tokens)}
              </td>
              <td className="py-2 pr-4 text-right text-xs text-ink-dim">{p.turns}</td>
              <td className="py-2 pr-4 text-right text-xs text-ink-dim">{duration(p.wall_sec)}</td>
            </tr>
            {expanded === p.problem &&
              p.kinds.map((k) => (
                <tr key={`${p.problem}-${k.kind}`} className="border-b border-edge/40 bg-bg">
                  <td className="py-1.5 pr-4 pl-8 font-mono text-[11px] text-ink-faint">
                    {k.kind}
                  </td>
                  <td className="py-1.5 pr-4 text-right text-[11px] text-ink-faint">{k.spawns}</td>
                  <td className="py-1.5 pr-4 text-right text-[11px] text-ink-faint">
                    {compactNumber(k.input_tokens + k.cache_read_tokens)}
                  </td>
                  <td className="py-1.5 pr-4 text-right text-[11px] text-ink-faint">
                    {compactNumber(k.output_tokens)}
                  </td>
                  <td className="py-1.5 pr-4 text-right text-[11px] text-ink-faint">{k.turns}</td>
                  <td className="py-1.5 pr-4 text-right text-[11px] text-ink-faint">
                    {duration(k.wall_sec)}
                  </td>
                </tr>
              ))}
          </Fragment>
        ))}
      </tbody>
    </table>
  )
}

export default function Telemetry() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <h1 className="font-display mb-4 text-[22px] font-medium text-ink">Engine</h1>
      <div className="flex flex-col gap-6">
        <section>
          <DaemonPanel />
        </section>
        <section>
          <SectionLabel>settings</SectionLabel>
          <ConfigPanel />
        </section>
        <section>
          <details className="group">
            <summary className="cursor-pointer list-none text-[11px] font-medium tracking-widest text-ink-faint/70 uppercase transition-colors hover:text-ink-dim">
              <span className="mr-1 inline-block text-[9px] transition-transform duration-150 group-open:rotate-90">▸</span>
              developer log
            </summary>
            <div className="mt-2">
              <LogTail />
            </div>
          </details>
        </section>
        <section>
          <UsageTable />
        </section>
      </div>
    </div>
  )
}
