import { Fragment, useState } from 'react'
import { usePoll } from '../lib/api'
import { weightedBurn } from '../lib/burn'
import { compactNumber, duration } from '../lib/format'
import { SectionLabel } from '../components/ui'
import type { ConfigSetting, RunStatus, UsageProblem } from '../lib/types'

/*
 * The ledger: what the engine has spent, per task and per agent kind,
 * and what this run is burning against the subscription window. It
 * belongs to the engine room (human_interface_design.md §1.4-2, fourth
 * bullet lists Usage among its four instruments) — accounting lives
 * with the machine, not with the mathematics.
 */

function Stat({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="rounded-xl border border-edge bg-surface px-4 py-3" title={title}>
      <div className="font-display tnum text-[26px] font-medium text-ink">{value}</div>
      <div className="mt-0.5 text-[11px] text-ink-faint">{label}</div>
    </div>
  )
}


function UsageTable({ project }: { project?: string }) {
  const { data } = usePoll<{ problems: UsageProblem[]; window?: 'run' | 'all' }>(
    `/api/telemetry/usage${project ? `?project=${encodeURIComponent(project)}` : ''}`,
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
        <div className="rounded-xl border border-edge bg-surface px-4 py-2 text-xs text-ink-faint">
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

/** The ledger face: usage per problem and per agent kind. */
/** The run's burn figures — moved here from the console (owner,
 * 2026-07-18): accounting lives with accounting. Weighted units
 * against the subscription window (no USD, no pretend ceiling). */
function BurnStrip({ project }: { project?: string }) {
  // the shelf's burn, not the workspace's — the engine room lives
  // inside a Project (§1.4) and the run read is scoped by the FK
  const { data } = usePoll<RunStatus>(
    `/api/run${project ? `?project=${encodeURIComponent(project)}` : ''}`,
    5000,
  )
  const { data: cfg } = usePoll<{ settings: ConfigSetting[] }>('/api/config', 60000)
  if (!data) return null
  const d = data.daemon
  const running = d.running
  const sumBurn = (b: { problems: { kinds: never[] }[] } | null): number =>
    b ? b.problems.reduce((s, p) => s + weightedBurn(p.kinds, cfg?.settings), 0) : 0
  const burnRun = sumBurn(data.burn_run as never)
  const burn5h = sumBurn(data.burn_5h as never)
  const elapsedMin = d.started_at
    ? Math.max(1 / 60, (Date.now() - Date.parse(d.started_at)) / 60000)
    : null
  const rate = running && elapsedMin ? burnRun / elapsedMin : null
  if (!running && burn5h <= 0) return null
  return (
    <div className="mb-6">
      <SectionLabel>burn</SectionLabel>
      <div className="flex flex-wrap gap-x-8 gap-y-2 rounded-xl border border-edge bg-surface px-4 py-3">
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
            <div
              className="text-[11px] text-ink-faint"
              title="run total ÷ elapsed — a whole-run average, not the last minute (bursts don't show here)"
            >
              avg burn
            </div>
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
    </div>
  )
}

/** The engine room's usage face: the run's burn, then the ledger. */
export function UsageLedger({ project }: { project?: string }) {
  return (
    <>
      <BurnStrip project={project} />
      {/* the engine room is a per-Project surface (§1.4), so its ledger
          answers for the shelf the reader is standing on. Membership is
          the FK, not the name's first segment — serve does that half. */}
      <UsageTable project={project} />
    </>
  )
}
