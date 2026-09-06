import { useState } from 'react'
import { apiPost } from '../lib/api'
import { draftForPick, offCatalog, seatRows } from '../lib/models'
import type { ConfigSetting, ModelGroup } from '../lib/types'
import ModelPicker from './ModelPicker'
import { Button, Select } from './ui'

/*
 * Advanced — one chair at a time.
 *
 * The section above seats the whole board from one choice, which is
 * what almost every reader wants and the only thing they should have to
 * decide. This is the exception surface underneath it: the model a
 * single seat sits on, the backend that model implies, and — where the
 * backend has one — the depth it thinks at. It is folded because
 * reaching for it means departing from the board, and a departure
 * should be a decision rather than the first thing on the page.
 *
 * Two things this says that a flat key list did not:
 *
 *   · whether the seated model is IN the machine's catalog. The yaml
 *     routinely seats a tier the declared list has not caught up with,
 *     and a picker that quietly showed it as an ordinary choice hid
 *     the one fact worth knowing about it.
 *   · when it takes effect. A write lands in `Asterism.yaml`; the
 *     daemon re-fingerprints the file on its own clock and hands off
 *     to a fresh process — nothing here reaches into a running one.
 *
 * The catalog arrives as a prop. Both halves of this section read the
 * same list, and two probes for one page would spend two subprocesses
 * to answer one question.
 */

/** Said once, here: the write is to a FILE, and the engine picks it up
 * on its own schedule. A settings page that implied otherwise would be
 * describing a mechanism the daemon does not have. */
export const WHEN =
  'takes effect on the daemon’s next config check (about a minute)'

function Row({
  label,
  pinned,
  children,
}: {
  label: string
  pinned: boolean
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 py-1">
      <span className="w-32 shrink-0 font-mono text-[11px] text-ink-dim">
        {label}
        {/* the settled norm earns no ink: only a seat that has LEFT the
            board is marked, and in the same word the control above
            uses for it */}
        {pinned && (
          <span className="ml-1.5 text-ink-faint" title="set here, not by the default">
            pinned
          </span>
        )}
      </span>
      {children}
    </div>
  )
}

export default function Seats({
  settings,
  groups,
  onAskCatalog,
  pinned,
  onSaved,
}: {
  settings: ConfigSetting[]
  groups: ModelGroup[]
  /** the catalog is asked for when a picker opens, never on mount */
  onAskCatalog: () => void
  /** seats the house's board does not explain — named by the control
   * above, so the two sections cannot disagree about which they are */
  pinned: string[]
  onSaved: () => void
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  const rows = seatRows(settings)
  const value = (s: ConfigSetting | null): string =>
    s === null ? '' : (drafts[s.key] ?? String(s.resolved ?? ''))
  const dirty = settings.filter(
    (s) => drafts[s.key] !== undefined && drafts[s.key] !== String(s.resolved ?? ''),
  )

  const save = async () => {
    setSaving(true)
    setNote(null)
    try {
      for (const s of dirty)
        await apiPost('/api/config', { key: s.key, value: drafts[s.key] })
      setDrafts({})
      onSaved()
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
        const picked = value(r.model)
        const stray = offCatalog(groups, picked)
        return (
          <Row key={r.seat} label={r.seat} pinned={pinned.includes(r.seat)}>
            <ModelPicker
              className="w-56"
              label={`${r.seat} model`}
              groups={groups}
              value={picked}
              onOpen={onAskCatalog}
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
