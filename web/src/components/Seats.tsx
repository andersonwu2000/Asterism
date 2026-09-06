import { useEffect, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { draftForPick, offCatalog, seatRows } from '../lib/models'
import type { ConfigSetting, ModelGroup } from '../lib/types'
import ModelPicker from './ModelPicker'
import { Button, Select } from './ui'

/*
 * Seats — who the engine sends, and how hard they think.
 *
 * The Tasks page's run parameters already set a seat's model, one row
 * per key. This section reads the same `/api/config` and the same
 * catalog the Assistant's picker reads, and draws a SEAT: the model,
 * the backend implied by it, and — where the backend has one — the
 * depth it thinks at. Three keys describing one chair were three rows
 * on a flat list; the reader is setting a chair.
 *
 * Two things this says that the flat list did not:
 *
 *   · whether the seated model is IN the machine's catalog. The yaml
 *     routinely seats a tier the declared list has not caught up with,
 *     and a picker that quietly showed it as an ordinary choice hid
 *     the one fact worth knowing about it.
 *   · when it takes effect. A write lands in `Asterism.yaml`; the
 *     daemon re-fingerprints the file on its own clock and hands off
 *     to a fresh process — nothing here reaches into a running one.
 */

/** Said once, here: the write is to a FILE, and the engine picks it up
 * on its own schedule. A settings page that implied otherwise would be
 * describing a mechanism the daemon does not have. */
const WHEN = 'takes effect on the daemon’s next config check (about a minute)'

function Row({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 py-1">
      <span className="w-32 shrink-0 font-mono text-[11px] text-ink-dim">{label}</span>
      {children}
    </div>
  )
}

export default function Seats() {
  const { data, refresh } = usePoll<{ settings: ConfigSetting[] }>(
    '/api/config',
    60000,
  )
  // which models exist is a question only the machine can answer, and a
  // kept list goes stale the day a vendor ships a tier — one probe per
  // mount, exactly as the Assistant's picker and RunParameters do it
  const [live, setLive] = useState<ModelGroup[] | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [note, setNote] = useState<string | null>(null)

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

  if (!data) return <div className="text-[11px] text-ink-faint">…</div>
  const rows = seatRows(data.settings)
  const value = (s: ConfigSetting | null): string =>
    s === null ? '' : (drafts[s.key] ?? String(s.resolved ?? ''))
  const dirty = data.settings.filter(
    (s) => drafts[s.key] !== undefined && drafts[s.key] !== String(s.resolved ?? ''),
  )

  const save = async () => {
    setSaving(true)
    setNote(null)
    try {
      for (const s of dirty)
        await apiPost('/api/config', { key: s.key, value: drafts[s.key] })
      setDrafts({})
      refresh()
      setNote(WHEN)
    } catch (e) {
      setNote(String((e as Error).message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div data-seats>
      {rows.map((r) => {
        const groups = live ?? r.model?.groups ?? []
        const picked = value(r.model)
        const stray = offCatalog(groups, picked)
        return (
          <Row key={r.seat} label={r.seat}>
            <ModelPicker
              className="w-56"
              label={`${r.seat} model`}
              groups={groups}
              value={picked}
              onChange={(m) =>
                setDrafts((d) => ({
                  ...d,
                  ...draftForPick(groups, r.model?.key ?? '', r.provider?.key ?? null, m),
                }))
              }
            />
            {/* the backend is not a control — it is what the model
                implies, and drawing it as one would let the two
                disagree (lib/models). It is shown because a seat's
                whole posture is what this section is for. */}
            <span className="w-24 shrink-0 text-[11px] text-ink-faint">
              {value(r.provider) || 'claude'}
            </span>
            {r.effort !== null && (
              <span
                className="flex items-center gap-1.5"
                title={
                  r.effort.applies
                    ? 'how deep this seat thinks'
                    : 'this backend has no such knob — it is kept for the day the seat moves to one that does'
                }
              >
                <Select
                  className={`w-24 ${r.effort.applies ? '' : 'opacity-50'}`}
                  value={value(r.effort)}
                  onChange={(e) =>
                    setDrafts((d) => ({ ...d, [r.effort!.key]: e.target.value }))
                  }
                >
                  {(r.effort.choices ?? []).map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
                {!r.effort.applies && (
                  <span className="text-[10px] text-ink-faint">unread here</span>
                )}
              </span>
            )}
            {/* the one fact about a seated model worth an exception's
                ink: the machine's own catalog does not name it */}
            {stray && (
              <span
                className="text-[10px] text-ink-faint"
                title="the yaml seats this name; the machine's catalog does not list it. It still runs — this is what is actually seated."
              >
                off-catalog
              </span>
            )}
          </Row>
        )
      })}
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <Button
          variant="ok"
          size="xs"
          disabled={dirty.length === 0 || saving}
          onClick={() => void save()}
        >
          {saving ? 'Saving…' : `Save${dirty.length ? ` (${dirty.length})` : ''}`}
        </Button>
        <span className="text-[11px] text-ink-faint">{note ?? WHEN}</span>
      </div>
    </div>
  )
}
