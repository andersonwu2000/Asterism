import { useCallback, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { boardDrafts, houseInEffect, pinnedSeats, seatRows } from '../lib/models'
import type { HouseBoard, SeatRow } from '../lib/models'
import type { ConfigSetting, ModelGroup } from '../lib/types'
import Seats, { WHEN } from './Seats'

/*
 * The default model — ONE choice, and it seats the whole board.
 *
 * A pipeline is not seven independent chairs. It is three LAYERS, and
 * they are ordered: the theory layer writes mathematics the record does
 * not have, the planning layer decides how the programme runs inside
 * the known, the formal layer does the volume. So the setting is which
 * HOUSE the machine works in — gpt or claude — and the three layers
 * follow from it by RANK: top series, second, third.
 *
 * By rank, never by name. The ordering is data (`serve/model_catalog`
 * walks the catalog's own order, which for codex is the vendor's own
 * `priority`), so the day a series appears above `fable` or `astra`
 * every layer shifts down one and nothing here is edited. That is the
 * whole reason this is a derivation and not three pickers: three
 * pickers have to be re-pointed by hand at every tier a vendor ships,
 * which is exactly what left the console offering four retired claude
 * names while the board ran `claude-opus-5` (2026-09-06).
 *
 * The exception surface is underneath, folded: `Seats` sets one chair
 * at a time, and a chair that has left the board is PINNED — said in
 * both places out of one computation, so they cannot disagree.
 */

/** The three layers, and what each is FOR. The membership of the last
 * one is "everything else" by construction, so a seat added to the
 * engine later is seated rather than forgotten. */
const LAYERS: [string, string[], string][] = [
  ['theory', ['theorist', 'theory_reviewer'], 'writes what the record does not have'],
  ['planning', ['strategist', 'adversary'], 'decides how the programme runs'],
  ['formal', [], 'does the volume — Lean, search, the library'],
]

/** What a person calls each house. The KEY is the backend the engine
 * spawns, because that is the word that lands in the yaml; `gpt` is the
 * word on the button. */
const HOUSE_LABEL: Record<string, string> = { claude: 'claude', codex: 'gpt' }

const membersOf = (seats: string[], rows: SeatRow[]): string[] => {
  if (seats.length > 0) return seats
  const named = LAYERS.flatMap(([, s]) => s)
  return rows.map((r) => r.seat).filter((s) => !named.includes(s))
}

export default function DefaultModel() {
  const { data, refresh } = usePoll<{ settings: ConfigSetting[] }>(
    '/api/config',
    60000,
  )
  // The catalog is an ACTION — one subprocess per backend that can be
  // asked — so it waits for someone to reach for it, never a mount.
  // Until then this section still says where every seat IS, out of the
  // polled config; what it will not do is guess a board.
  const [live, setLive] = useState<ModelGroup[] | null>(null)
  const [houses, setHouses] = useState<Record<string, HouseBoard> | null>(null)
  const [asking, setAsking] = useState(false)
  const asked = useRef(false)
  const askCatalog = useCallback(() => {
    if (asked.current) return
    asked.current = true
    setAsking(true)
    apiPost<{ groups: ModelGroup[]; houses: Record<string, HouseBoard> }>(
      '/api/models/refresh',
      {},
    )
      .then((r) => {
        setLive(r.groups)
        setHouses(r.houses)
      })
      .catch(() => {
        /* keep the declared lists — never blank the picker */
      })
      .finally(() => setAsking(false))
  }, [])

  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  if (!data) return <div className="text-[11px] text-ink-faint">…</div>
  const rows = seatRows(data.settings)
  const groups = live ?? rows[0]?.model?.groups ?? []
  const boards = houses ?? {}
  const here = houseInEffect(rows, boards)
  const pinned = here === null ? [] : pinnedSeats(rows, boards[here])

  const seat = async (house: string) => {
    setBusy(house)
    setNote(null)
    try {
      // the existing seat-write path, one key at a time: it preserves
      // the file's comments, and that file is mostly the owner's own
      // reasoning about why each seat is where it is
      for (const [key, value] of Object.entries(boardDrafts(boards[house] ?? {})))
        await apiPost('/api/config', { key, value })
      refresh()
      setNote(WHEN)
    } catch (e) {
      setNote(String((e as Error).message))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div data-default-model>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-ink">Default model</span>
        <span className="text-[11px] text-ink-faint">
          one house; the three layers follow it by rank
        </span>
        {/* the lit half IS the current value — one control with a
            state, not two things to press (DESIGN.md, the appearance
            control's own shape) */}
        <span className="ml-auto flex overflow-hidden rounded-lg border border-edge">
          {Object.keys(HOUSE_LABEL).map((h) => {
            const ready = Object.keys(boards[h] ?? {}).length > 0
            return (
              <button
                key={h}
                data-house={h}
                aria-pressed={here === h}
                disabled={busy !== null || !ready}
                className={`cursor-pointer px-2.5 py-1 text-xs transition-colors disabled:cursor-default ${
                  here === h
                    ? 'bg-surface-3 text-ink'
                    : 'text-ink-faint hover:text-ink-dim disabled:text-ink-faint/50'
                }`}
                title={
                  ready
                    ? `seat all three layers on ${HOUSE_LABEL[h]}`
                    : 'ask the backends what they can run first'
                }
                onClick={() => void seat(h)}
              >
                {busy === h ? 'seating…' : HOUSE_LABEL[h]}
              </button>
            )
          })}
        </span>
      </div>

      <div className="mt-3 flex flex-col gap-1">
        {LAYERS.map(([layer, seats, what]) => {
          const members = membersOf(seats, rows)
          const board = here === null ? null : boards[here]
          const derived = board === null ? null : (board[members[0]] ?? null)
          // what is SEATED, always; what the house WOULD seat, once the
          // machine has said what it has. A row that showed only the
          // derivation would describe a board nobody is running.
          const now = rows.find((r) => r.seat === members[0])
          const model = derived?.model ?? String(now?.model?.resolved ?? '—')
          const depth = derived?.effort ??
            (now?.effort?.applies ? String(now.effort.resolved ?? '') : '')
          return (
            <div key={layer} className="flex flex-wrap items-baseline gap-2 py-0.5">
              <span className="w-20 shrink-0 text-[11px] text-ink-dim">{layer}</span>
              <span className="w-56 shrink-0 font-mono text-[11px] text-ink">
                {model}
                {depth !== '' && <span className="text-ink-faint"> · {depth}</span>}
              </span>
              <span className="min-w-0 text-[11px] text-ink-faint">
                {what} — {members.join(', ')}
              </span>
            </div>
          )
        })}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-ink-faint">
        {here === null ? (
          /* the way out, exactly: nothing can be derived until the
             machine has said what it can run, so the sentence that says
             so is also the button that fixes it */
          <button
            className="cursor-pointer underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink disabled:no-underline"
            disabled={asking}
            onClick={askCatalog}
          >
            {asking ? 'asking the backends…' : 'ask the backends what they can run'}
          </button>
        ) : pinned.length > 0 ? (
          <span title="these seats are set in Advanced; the default does not explain them">
            pinned: {pinned.join(' · ')}
          </span>
        ) : (
          <span>every seat is where {HOUSE_LABEL[here] ?? here} puts it</span>
        )}
        <span>{note ?? WHEN}</span>
      </div>

      <div className="mt-3 border-t border-edge pt-2">
        <button
          className="flex cursor-pointer items-baseline gap-2 text-[11px] text-ink-faint transition-colors hover:text-ink-dim"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
        >
          <span
            className={`inline-block text-[9px] transition-transform ${open ? 'rotate-90' : ''}`}
          >
            ▸
          </span>
          Advanced — one seat at a time
          {!open && pinned.length > 0 && (
            <span className="tnum">{pinned.length} pinned</span>
          )}
        </button>
        {open && (
          <div className="mt-2">
            <Seats
              settings={data.settings}
              groups={groups}
              onAskCatalog={askCatalog}
              pinned={pinned}
              onSaved={refresh}
            />
          </div>
        )}
      </div>
    </div>
  )
}
