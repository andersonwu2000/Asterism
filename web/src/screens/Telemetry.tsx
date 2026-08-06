import { Fragment, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { weightedBurn } from '../lib/burn'
import { compactNumber, duration } from '../lib/format'
import { Link } from '../lib/router'
import { Button, SectionLabel, Select } from '../components/ui'
import type { ConfigSetting, RunStatus, UsageProblem } from '../lib/types'

/** The Engine page's two quiet faces: the machine's knobs, and the
 * all-time usage ledger. Accounts and appearance are the console's
 * own and live at #/settings; liveness, lanes and the engine log live
 * on the Console tab. */


function ConfigPanel() {
  const { data, refresh } = usePoll<{ settings: ConfigSetting[] }>('/api/config', 60000)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [msg, setMsg] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  if (!data) return null
  // ONE Save for the whole panel (owner, 2026-07-14): per-row buttons
  // either shoved the layout or reserved awkward gaps — edits collect
  // as drafts, dirty rows tint their border, one click lands them all
  const dirtyKeys = data.settings
    .filter((s) => {
      const d = drafts[s.key]
      return d !== undefined && d !== String(s.resolved ?? '')
    })
    .map((s) => s.key)
  const saveAll = async () => {
    setSaving(true)
    setMsg(null)
    const notes: string[] = []
    try {
      for (const key of dirtyKeys) {
        const r = await apiPost<{ message: string }>('/api/config', {
          key,
          value: drafts[key],
        })
        notes.push(r.message)
      }
      setDrafts({})
      setMsg(notes[notes.length - 1] ?? null)
      refresh()
    } catch (e) {
      setMsg(String((e as Error).message))
    } finally {
      setSaving(false)
    }
  }
  const models = data.settings.filter((s) => s.key.endsWith('.model'))
  const knobs = data.settings.filter((s) => !s.key.endsWith('.model'))
  const row = (s: ConfigSetting) => {
    const draft = drafts[s.key]
    const current = String(s.resolved ?? '')
    const dirty = draft !== undefined && draft !== current
    return (
      <div key={s.key} className="flex items-center gap-3 py-1">
        {/* wide enough for the longest key (strategist.audit_interval_min)
            — w-44 rammed dispatch.shelve_threshold into its input (cold-eye) */}
        <span className="w-56 shrink-0 font-mono text-xs text-ink-dim">{s.key}</span>
        {s.choices ? (
          // a select kills the free-text failure mode (a typo'd model
          // name only explodes at the NEXT run) — power users can
          // still put anything in yaml/.env; it shows up as a choice
          <Select
            // shrink-0: when the chat drawer squeezes the page, the
            // shrink must land on the truncating description — a
            // base-select's minimum width is its CURRENT value's text
            // (a classic select's was the longest option), so letting
            // these compress gives every row a different width
            className="w-56 shrink-0"
            value={draft ?? current}
            onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
          >
            {s.choices.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        ) : (
          <input
            className={`w-56 shrink-0 rounded-lg border bg-surface px-2 py-1 font-mono text-xs text-ink focus:outline-none ${
              dirty ? 'border-star/50' : 'border-edge focus:border-ink-faint'
            }`}
            value={draft ?? current}
            onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
          />
        )}
        <span className="min-w-0 truncate text-[11px] text-ink-faint">
          {dirty && (
            <span className="mr-1.5 text-star" title="unsaved change">
              ·
            </span>
          )}
          {s.description}
        </span>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-edge bg-surface px-4 py-3">
      <div className="mb-1 text-[11px] text-ink-faint">
        which model does each job — a live run picks changes up within a minute (it
        gracefully hands off to a fresh engine); an .env override, if you have one,
        still wins
      </div>
      {models.map(row)}
      <div className="mt-3 mb-1 text-[11px] text-ink-faint">engine knobs</div>
      {knobs.map(row)}
      {/* the ONE Save: always present (no layout shift), disabled until
          something is dirty; the count says how much it will land */}
      <div className="mt-3 flex items-center gap-3 border-t border-edge pt-3">
        <Button
          variant="ok"
          disabled={saving || dirtyKeys.length === 0}
          onClick={() => void saveAll()}
        >
          {saving ? 'Saving…' : 'Save changes'}
        </Button>
        <span className="tnum text-[11px] text-ink-faint">
          {dirtyKeys.length > 0
            ? `${dirtyKeys.length} unsaved change${dirtyKeys.length === 1 ? '' : 's'}`
            : 'no unsaved changes'}
        </span>
        {msg && <span className="min-w-0 truncate font-mono text-[11px] text-ink-dim">{msg}</span>}
      </div>
    </div>
  )
}


function Stat({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="rounded-xl border border-edge bg-surface px-4 py-3" title={title}>
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

/** The MACHINE's knobs. Config is read once at run start (the banner
 * says so while a run is live); the Manifest tab next door is the
 * hot-reloaded lever. The account moved to the console's own Settings
 * page (owner, 2026-08-07): which model a role uses is the engine's
 * business, but who is paying for it is yours. */
export function SettingsTab() {
  const { data: daemon } = usePoll<{ running: boolean }>('/api/daemon', 5000)
  return (
    <div>
      {daemon?.running && (
        <div className="mb-4 rounded-lg border border-edge bg-surface-2 px-3 py-2 text-xs text-ink-dim">
          A run is live — a change here makes the engine finish its in-flight work, then
          hand off to a fresh process on the new settings (
          <span className="text-ink">~1 min</span>, nothing is interrupted).
        </div>
      )}
      <ConfigPanel />
      <p className="mt-4 text-[11px] text-ink-faint">
        Accounts and appearance live in{' '}
        <Link
          to="/settings"
          className="underline decoration-edge-strong underline-offset-2 hover:text-ink"
        >
          Settings
        </Link>{' '}
        — these knobs steer the machine, not the console.
      </p>
    </div>
  )
}

/** The ledger face: usage per problem and per agent kind. */
/** The run's burn figures — moved here from the console (owner,
 * 2026-07-18): accounting lives with accounting. Weighted units
 * against the subscription window (no USD, no pretend ceiling). */
function BurnStrip() {
  const { data } = usePoll<RunStatus>('/api/run', 5000)
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

export function UsageTab() {
  return (
    <>
      <BurnStrip />
      <UsageTable />
    </>
  )
}
