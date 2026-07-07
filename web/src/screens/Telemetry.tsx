import { Fragment, useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { weightedBurn } from '../lib/burn'
import { compactNumber, duration } from '../lib/format'
import { SectionLabel } from '../components/ui'
import type { ConfigSetting, UsageProblem } from '../lib/types'

/** Settings — the machine room: model/knob config, the all-time usage
 * ledger, and the developer log. Liveness, lanes and burn-of-the-run
 * live on the Run console (#/run). */


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
        {s.choices ? (
          // a select kills the free-text failure mode (a typo'd model
          // name only explodes at the NEXT run) — power users can
          // still put anything in yaml/.env; it shows up as a choice
          <select
            className="w-56 rounded border border-edge bg-bg px-2 py-1 font-mono text-xs text-ink focus:border-ink-faint focus:outline-none"
            value={draft ?? current}
            onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
          >
            {s.choices.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        ) : (
          <input
            className="w-56 rounded border border-edge bg-bg px-2 py-1 font-mono text-xs text-ink focus:border-ink-faint focus:outline-none"
            value={draft ?? current}
            onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
          />
        )}
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
  const weighted = weightedBurn(
    rows.flatMap((p) => p.kinds),
    cfg?.settings,
  )
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
  const { data: daemon } = usePoll<{ running: boolean }>('/api/daemon', 5000)
  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <h1 className="font-display mb-4 text-[22px] font-medium text-ink">Settings</h1>
      {/* liveness, lanes and burn live on the Run console (#/run) —
          this page is the machine room: knobs, the ledger, the log */}
      {daemon?.running && (
        <div className="mb-4 rounded-md border border-edge bg-surface-2 px-3 py-2 text-xs text-ink-dim">
          A run is live — the engine reads its configuration once at start, so every change
          here lands on the <span className="text-ink">next</span> run.
        </div>
      )}
      <div className="flex flex-col gap-6">
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
