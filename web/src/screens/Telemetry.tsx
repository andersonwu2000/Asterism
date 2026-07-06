import { Fragment, useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { compactNumber, duration } from '../lib/format'
import { SectionLabel } from '../components/ui'
import type { DaemonStatus, LibraryProblem, UsageProblem } from '../lib/types'

/** Engine panel + usage telemetry + Library browser (charter §3.4). */

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
      <div className="mb-3 flex items-center gap-3">
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            d?.stopping ? 'bg-warn' : d?.running ? 'bg-ok' : 'bg-ink-faint'
          }`}
        />
        <span className="text-sm text-ink">
          {d?.stopping
            ? `stopping (pid ${d.pid}) — draining in-flight work`
            : d?.running
              ? `running (pid ${d.pid})`
              : 'not running'}
        </span>
        {d && d.in_flight_leases > 0 && (
          <span className="text-xs text-ink-dim">{d.in_flight_leases} in-flight lease(s)</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {!d?.running ? (
          <>
            <input
              className="w-64 rounded-md border border-edge bg-bg px-2 py-1.5 font-mono text-xs text-ink focus:border-accent focus:outline-none"
              placeholder="scope (optional, e.g. Logic.%)"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
            />
            <button
              className="rounded-md bg-accent/20 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/30 disabled:opacity-50"
              disabled={busy}
              onClick={() => void act('/api/daemon/start', { scope: scope || null })}
            >
              Start daemon
            </button>
          </>
        ) : (
          <>
            <button
              className="rounded-md border border-edge px-3 py-1.5 text-xs text-ink-dim hover:text-ink disabled:opacity-50"
              disabled={busy || d.stopping}
              onClick={() => void act('/api/daemon/stop', { force: false })}
            >
              Stop (graceful)
            </button>
            <button
              className="rounded-md border border-danger/40 px-3 py-1.5 text-xs text-danger hover:bg-danger/10 disabled:opacity-50"
              disabled={busy}
              onClick={() => void act('/api/daemon/stop', { force: true })}
            >
              Force stop
            </button>
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

  return (
    <div
      ref={boxRef}
      className="h-64 overflow-y-auto rounded-lg border border-edge bg-bg p-3"
      onScroll={(e) => {
        const el = e.currentTarget
        stickBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 30
      }}
    >
      {lines.length === 0 ? (
        <div className="text-xs text-ink-faint">
          No log output — the tail follows the current daemon run and picks up when one starts.
        </div>
      ) : (
        <pre className="font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink-dim">
          {lines.join('\n')}
        </pre>
      )}
    </div>
  )
}

function UsageTable() {
  const { data } = usePoll<{ problems: UsageProblem[] }>('/api/telemetry/usage', 10000)
  const [expanded, setExpanded] = useState<string | null>(null)
  const rows = data?.problems ?? []
  if (rows.length === 0)
    return (
      <div className="rounded-lg border border-edge bg-surface px-4 py-6 text-center text-xs text-ink-faint">
        No spawn usage recorded yet — rows appear as agents run.
      </div>
    )
  return (
    <table className="w-full border-collapse text-left">
      <thead>
        <tr className="border-b border-edge text-xs text-ink-faint">
          <th className="py-2 pr-4 pl-2 font-medium">problem</th>
          <th className="py-2 pr-4 text-right font-medium">spawns</th>
          <th className="py-2 pr-4 text-right font-medium">input tok</th>
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
                {compactNumber(p.input_tokens)}
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
                    {compactNumber(k.input_tokens)}
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

function LibraryBrowser() {
  const { data } = usePoll<{ problems: LibraryProblem[] }>('/api/library', 30000)
  const rows = data?.problems ?? []
  if (rows.length === 0)
    return (
      <div className="rounded-lg border border-edge bg-surface px-4 py-6 text-center text-xs text-ink-faint">
        Nothing bridged to the Library yet — approved harvests land here.
      </div>
    )
  return (
    <div className="flex flex-col gap-3">
      {rows.map((p) => (
        <div key={p.problem} className="rounded-lg border border-edge bg-surface">
          <div className="border-b border-edge px-4 py-2 font-mono text-xs text-star">
            {p.problem}
            <span className="ml-2 text-ink-faint">{p.decls.length} declarations</span>
          </div>
          <div className="px-4 py-2">
            {p.decls.map((d) => (
              <div key={d.slug} className="flex items-baseline gap-3 py-0.5">
                <span className="shrink-0 font-mono text-xs text-ink">{d.name ?? d.slug}</span>
                {d.signature && (
                  <span className="truncate font-mono text-[11px] text-ink-faint">
                    {d.signature}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function Telemetry() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <h1 className="mb-4 text-lg font-semibold">Engine</h1>
      <div className="flex flex-col gap-6">
        <section>
          <SectionLabel>daemon</SectionLabel>
          <DaemonPanel />
        </section>
        <section>
          <SectionLabel>live log</SectionLabel>
          <LogTail />
        </section>
        <section>
          <SectionLabel>usage</SectionLabel>
          <UsageTable />
        </section>
        <section>
          <SectionLabel>library</SectionLabel>
          <LibraryBrowser />
        </section>
      </div>
    </div>
  )
}
