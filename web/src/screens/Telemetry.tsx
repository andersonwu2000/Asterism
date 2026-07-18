import { Fragment, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { weightedBurn } from '../lib/burn'
import { compactNumber, duration } from '../lib/format'
import { Button, SectionLabel, Select } from '../components/ui'
import { logout, switchAccount } from '../lib/claudeAuth'
import type { ConfigSetting, Meta, UsageProblem } from '../lib/types'

/** Settings — the machine room: account, model/knob config, and the
 * all-time usage ledger. Liveness, lanes, burn-of-the-run and the
 * engine log live on the Run console (#/run). */


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
        which model does each job — changes apply from the next run (an .env override, if
        you have one, still wins)
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

/** The Claude account — who pays the quota. Switching mid-run is a
 * supported move (owner: quota reset): running agents keep the
 * session they hold, new spawns use the next login, and the plan
 * meters flip to the new account by themselves. */
function AccountPanel() {
  const { data: meta, refresh } = usePoll<Meta>('/api/meta', 5000)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (!meta) return null
  const c = meta.claude
  const run = async (fn: () => Promise<string>) => {
    setBusy(true)
    try {
      setMsg(await fn())
    } catch (e) {
      setMsg(String((e as Error).message))
    } finally {
      setBusy(false)
      refresh()
    }
  }
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-edge bg-surface px-4 py-3">
      <span
        className={`h-2 w-2 rounded-full ${c.logged_in ? 'bg-ok' : 'bg-warn'}`}
        aria-hidden
      />
      <span className="text-xs text-ink">
        {c.logged_in
          ? `Claude Code logged in${c.subscription ? ` · ${c.subscription} plan` : ''}`
          : c.installed
            ? 'Claude Code is not logged in'
            : 'Claude Code is not installed'}
      </span>
      {c.installed && (
        <span className="ml-auto flex items-center gap-2">
          <button
            className="cursor-pointer rounded-lg border border-edge bg-surface-2 px-2.5 py-1 text-xs text-ink transition-colors hover:bg-surface-3 disabled:opacity-50"
            disabled={busy}
            onClick={() => void run(switchAccount)}
            title="log this account out and open the login window for another — running agents keep their session; new work uses the new account"
          >
            Switch account
          </button>
          {c.logged_in && (
            <button
              className="cursor-pointer rounded-lg border border-edge px-2.5 py-1 text-xs text-ink-dim transition-colors hover:text-ink disabled:opacity-50"
              disabled={busy}
              onClick={() => void run(logout)}
            >
              Log out
            </button>
          )}
        </span>
      )}
      {msg && <span className="w-full text-[11px] text-ink-faint">{msg}</span>}
    </div>
  )
}

/** The knobs + account face of the Engine page. Config is read once
 * at run start (the banner says so while a run is live); the Manifest
 * tab next door is the hot-reloaded lever. */
export function SettingsTab() {
  const { data: daemon } = usePoll<{ running: boolean }>('/api/daemon', 5000)
  return (
    <div>
      {daemon?.running && (
        <div className="mb-4 rounded-lg border border-edge bg-surface-2 px-3 py-2 text-xs text-ink-dim">
          A run is live — the engine reads its configuration once at start, so every change
          here lands on the <span className="text-ink">next</span> run. (Instructions on the
          Manifest tab DO reach the live run.)
        </div>
      )}
      <div className="flex flex-col gap-6">
        <section>
          <SectionLabel>account</SectionLabel>
          <AccountPanel />
        </section>
        <section>
          <SectionLabel>settings</SectionLabel>
          <ConfigPanel />
        </section>
      </div>
    </div>
  )
}

/** The ledger face: usage per problem and per agent kind. */
export function UsageTab() {
  return <UsageTable />
}
