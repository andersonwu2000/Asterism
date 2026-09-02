import { useEffect, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { draftForPick } from '../lib/models'
import { duration } from '../lib/format'
import { Button, Select } from './ui'
import type { ConfigSetting, ModelGroup } from '../lib/types'

/*
 * The engine's editable knobs, split by WHOSE question they answer
 * (human_interface_design.md §1.4): what this run does is a run
 * parameter and lives beside Run — "每次 run 都可能改的東西不藏在設定" —
 * and what this installation is lives on the settings page.
 *
 * One renderer for both, because they are the same rows against the
 * same endpoint; only the key filter differs. Two copies would drift
 * the moment a knob was added, and the reader would meet two dialects
 * of the same control.
 */

/** What a run does. Everything else is the installation's business, so
 * a knob added later surfaces in Settings rather than vanishing.
 *
 * `dispatch.blocked_kinds` is here rather than in the gear because §1.4
 * puts the operator's hold beside the Run controls: it is a thing you
 * reconsider for THIS run, not a property of the installation. */
const RUN_KEYS = (key: string): boolean =>
  key.endsWith('.model') ||
  key === 'dispatch.budget_sec' ||
  key === 'dispatch.shelve_threshold' ||
  key === 'dispatch.quota_wait' ||
  key === 'dispatch.blocked_kinds'

function ConfigPanel({ owns }: { owns: (key: string) => boolean }) {
  const { data, refresh } = usePoll<{ settings: ConfigSetting[] }>('/api/config', 60000)
  // The polled read carries the DECLARED lists and never spawns. Asking
  // the backends what they actually run is an action, taken once when
  // this panel opens — a kept list goes stale the day a vendor ships a
  // tier (agy's live list was 14 while the file still said 3).
  const [live, setLive] = useState<ModelGroup[] | null>(null)
  useEffect(() => {
    let gone = false
    apiPost<{ groups: ModelGroup[] }>('/api/models/refresh', {})
      .then((r) => !gone && setLive(r.groups))
      .catch(() => {
        /* keep the declared lists — never blank the picker */
      })
    return () => {
      gone = true
    }
  }, [])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [msg, setMsg] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  if (!data) return null
  const settings = data.settings.filter((s) => owns(s.key) || s.key.endsWith('.provider'))
  // ONE Save for the whole panel: edits collect as drafts, dirty rows
  // mark themselves, one click lands them all.
  const dirtyKeys = settings
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
  // ONE control per seat: a seat's backend is implied by the model, so
  // a separate provider field would draw the same fact twice and let
  // the two disagree (`provider: codex` with `claude-sonnet-5` dies at
  // its first spawn). Vendors become optgroups; picking writes both.
  const models = settings.filter((s) => s.key.endsWith('.model'))
  const providerOf = new Map(
    settings.filter((s) => s.key.endsWith('.provider')).map((s) => [s.key.split('.')[0], s]),
  )
  const knobs = settings.filter(
    (s) => !s.key.endsWith('.model') && !s.key.endsWith('.provider'),
  )
  const modelPicker = (s: ConfigSetting) => {
    const seat = s.key.split('.')[0]
    const prov = providerOf.get(seat)
    const current = String(drafts[s.key] ?? s.resolved ?? '')
    const groups = live ?? s.groups ?? []
    const known = groups.some((g) => g.models.includes(current))
    return (
      <Select
        className="w-56 shrink-0"
        value={current}
        onChange={(e) =>
          setDrafts((d) => ({
            ...d,
            ...draftForPick(groups, s.key, prov?.key ?? null, e.target.value),
          }))
        }
      >
        {current === '' && (
          <option value="" disabled>
            not set — the provider's default
          </option>
        )}
        {!known && current !== '' && (
          <optgroup label="set outside this page">
            <option value={current}>{current}</option>
          </optgroup>
        )}
        {groups.map((g) => (
          <optgroup
            key={g.provider}
            label={
              g.provider +
              (g.installed ? '' : ' (not installed)') +
              (g.source === 'declared' ? ' — list not live' : '')
            }
          >
            {g.models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </optgroup>
        ))}
      </Select>
    )
  }
  const row = (s: ConfigSetting) => {
    const draft = drafts[s.key]
    const current = String(s.resolved ?? '')
    const dirty = draft !== undefined && draft !== current
    return (
      <div key={s.key} className="flex items-center gap-3 py-1">
        <span className="w-56 shrink-0 font-mono text-xs text-ink-dim">{s.key}</span>
        {s.choices ? (
          <Select
            className="w-56 shrink-0"
            value={draft ?? current}
            onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
          >
            {(draft ?? current) === '' && (
              <option value="" disabled>
                not set — the provider's default
              </option>
            )}
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
    <div>
      {models.map((s) => {
        const seat = s.key.split('.')[0]
        const prov = providerOf.get(seat)
        const provDirty = prov !== undefined && drafts[prov.key] !== undefined
        return (
          <div key={s.key} className="flex items-center gap-3 py-1">
            <span className="w-56 shrink-0 font-mono text-xs text-ink-dim">{s.key}</span>
            {modelPicker(s)}
            <span className="min-w-0 truncate text-[11px] text-ink-faint">
              {(drafts[s.key] !== undefined || provDirty) && (
                <span className="mr-1.5 text-star" title="unsaved change">
                  ·
                </span>
              )}
              {s.description}
            </span>
          </div>
        )
      })}
      {knobs.map(row)}
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

/** Beside Run: what the next run will do. Folded, because the answer
 * is usually "the same as last time" — and the summary line says what
 * is set, so opening it is a decision, not a check. */
export function RunParameters({ running }: { running: boolean }) {
  const [open, setOpen] = useState(false)
  const { data } = usePoll<{ settings: ConfigSetting[] }>('/api/config', 60000)
  const budget = data?.settings.find((s) => s.key === 'dispatch.budget_sec')
  const held = String(
    data?.settings.find((s) => s.key === 'dispatch.blocked_kinds')?.resolved ?? '',
  ).trim()
  const seats = (data?.settings ?? []).filter((s) => s.key.endsWith('.model')).length
  return (
    <div>
      <button
        className="flex cursor-pointer items-baseline gap-2 text-[11px] text-ink-faint transition-colors hover:text-ink-dim"
        onClick={() => setOpen((o) => !o)}
      >
        <span className={`inline-block text-[9px] transition-transform ${open ? 'rotate-90' : ''}`}>
          ▸
        </span>
        run parameters
        {!open && data && (
          <span className="tnum font-normal">
            {seats} models
            {budget?.resolved ? ` · ${duration(Number(budget.resolved))} budget` : ''}
          </span>
        )}
        {/* a hold is why a run can dispatch nothing at all — it is the
            one parameter whose value must be legible while folded */}
        {!open && held !== '' && (
          <span className="text-warn" title="these kinds are held on this machine">
            holding {held}
          </span>
        )}
      </button>
      {open && (
        <div className="mt-2">
          {running && (
            <div className="mb-3 rounded-lg border border-edge bg-surface-2 px-3 py-2 text-[11px] text-ink-dim">
              A run is live — saving here makes the engine finish its in-flight work, then
              hand off to a fresh process on the new parameters (~1 min, nothing is lost).
            </div>
          )}
          <ConfigPanel owns={RUN_KEYS} />
        </div>
      )}
    </div>
  )
}

/** On the settings page: what this installation is. Not folded — the
 * page exists to be read. */
export function MachineParameters() {
  return <ConfigPanel owns={(key) => !RUN_KEYS(key)} />
}

export default RunParameters
