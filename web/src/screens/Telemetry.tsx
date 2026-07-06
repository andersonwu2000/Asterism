import { Fragment, useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { compactNumber, duration } from '../lib/format'
import { Button, SectionLabel } from '../components/ui'
import type { DaemonStatus, UsageProblem } from '../lib/types'

/** Engine panel + usage telemetry (charter §3.4); the Library browses at #/library. */

function DaemonPanel() {
  const { data: d, refresh } = usePoll<DaemonStatus>('/api/daemon', 2000)
  const [scope, setScope] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

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
              d?.stopping ? 'bg-warn' : d?.running ? 'bg-ok animate-pulse' : 'bg-ink-faint'
            }`}
          />
          <span className="font-display text-[22px] font-medium text-ink">
            {d?.stopping ? 'Stopping' : d?.running ? 'Running' : 'Idle'}
          </span>
        </span>
        <span className="text-xs text-ink-faint">
          {d?.stopping
            ? `pid ${d.pid} — draining in-flight work`
            : d?.running
              ? `pid ${d.pid}${d.in_flight_leases > 0 ? ` · ${d.in_flight_leases} in flight` : ''}`
              : 'the daemon is not running'}
        </span>
      </div>
      {d && !d.running && d.in_flight_leases > 0 && (
        <div className="mb-3 rounded-md border border-edge bg-surface-2 px-3 py-1.5 text-xs text-ink-dim">
          {d.in_flight_leases} orphaned work lease(s) from a previous run — reclaimed
          automatically on the next daemon start.
        </div>
      )}
      <div className="flex items-center gap-2">
        {!d?.running ? (
          <>
            <input
              className="w-64 rounded-md border border-edge bg-bg px-2 py-1.5 font-mono text-xs text-ink focus:border-accent focus:outline-none"
              placeholder="scope (optional, e.g. Logic.%)"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
            />
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => void act('/api/daemon/start', { scope: scope || null })}
            >
              Start daemon
            </Button>
          </>
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
              onClick={() => void act('/api/daemon/stop', { force: true })}
            >
              Force stop
            </Button>
          </>
        )}
      </div>
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-edge bg-surface px-4 py-3">
      <div className="font-display tnum text-[26px] font-medium text-ink">{value}</div>
      <div className="mt-0.5 text-[11px] text-ink-faint">{label}</div>
    </div>
  )
}

function UsageTable() {
  const { data } = usePoll<{ problems: UsageProblem[] }>('/api/telemetry/usage', 10000)
  const [expanded, setExpanded] = useState<string | null>(null)
  const rows = data?.problems ?? []
  if (rows.length === 0)
    return (
      <div className="rounded-lg border border-edge bg-surface px-4 py-2 text-xs text-ink-faint">
        No spawn usage recorded yet — rows appear as agents run.
      </div>
    )
  const total = rows.reduce(
    (a, p) => ({
      spawns: a.spawns + p.spawns,
      out: a.out + p.output_tokens,
      inTok: a.inTok + p.input_tokens + p.cache_read_tokens,
      wall: a.wall + p.wall_sec,
    }),
    { spawns: 0, out: 0, inTok: 0, wall: 0 },
  )
  return (
    <>
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="agent spawns" value={String(total.spawns)} />
        <Stat label="output tokens" value={compactNumber(total.out)} />
        <Stat label="input + cache read" value={compactNumber(total.inTok)} />
        <Stat label="agent wall time" value={duration(total.wall)} />
      </div>
      {inner(rows, expanded, setExpanded)}
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
          <SectionLabel>daemon</SectionLabel>
          <DaemonPanel />
        </section>
        <section>
          <SectionLabel>run log</SectionLabel>
          <LogTail />
        </section>
        <section>
          <SectionLabel>usage — this run</SectionLabel>
          <UsageTable />
        </section>
      </div>
    </div>
  )
}
