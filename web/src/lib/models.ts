import type { ConfigSetting, ModelGroup } from './types'

/*
 * One picker decides two settings.
 *
 * A seat's backend is not an independent choice — it is implied by the
 * model — so the console offers ONE control and writes both keys. Two
 * controls would draw the same fact twice and, worse, let them
 * disagree: `provider: codex` with `claude-sonnet-5` is a run that dies
 * at its first spawn, and nothing before the spawn would have said so
 * (owner, 2026-08-14).
 *
 * That makes "which backend owns this model name" a rule, not a
 * lookup, and rules get pinned.
 */

/** The backend that runs `model`, or null when nothing offers it —
 * an env/yaml override may name anything, and inventing an owner for
 * it would silently move the seat to a backend nobody chose. */
export function providerForModel(
  groups: ModelGroup[],
  model: string,
): string | null {
  for (const g of groups) if (g.models.includes(model)) return g.provider
  return null
}

/** What a pick writes: the model always, and the backend whenever the
 * model names one. Never the backend alone — that is the pairing this
 * control exists to keep. */
export function draftForPick(
  groups: ModelGroup[],
  modelKey: string,
  providerKey: string | null,
  picked: string,
): Record<string, string> {
  const owner = providerForModel(groups, picked)
  const out: Record<string, string> = { [modelKey]: picked }
  if (owner && providerKey) out[providerKey] = owner
  return out
}

// -- a seat, out of the flat settings list ------------------------------------

/** One pipeline seat's whole posture: which backend, which model, and
 * how deep it thinks. */
export interface SeatRow {
  seat: string
  model: ConfigSetting | null
  provider: ConfigSetting | null
  /** codex's own ladder; `applies` says whether THIS seat's backend
   * reads it at all */
  effort: ConfigSetting | null
}

/** The seats `/api/config` describes, in the order it describes them.
 *
 * The wire is flat because `set_ui_setting` writes one key at a time,
 * and it must stay that way — but a SEAT is what the reader is setting,
 * and three rows saying `formalizer` is three readings of one thing.
 * A `.model` key is what makes a seat: `dispatch.pool` is a knob, not a
 * chair. */
export function seatRows(settings: ConfigSetting[]): SeatRow[] {
  const at = (suffix: string, seat: string) =>
    settings.find((s) => s.key === `${seat}.${suffix}`) ?? null
  return settings
    .filter((s) => s.key.endsWith('.model'))
    .map((s) => s.key.split('.')[0])
    .map((seat) => ({
      seat,
      model: at('model', seat),
      provider: at('provider', seat),
      effort: at('reasoning_effort', seat),
    }))
}

/** Is the seated model absent from the machine's own catalog?
 *
 * The yaml routinely seats a tier the declared list has not caught up
 * with (`claude-opus-5`, `claude-fable-5-1` on 2026-09-06). That is not
 * an error — it is the truth about the seat — so the row shows it and
 * SAYS it is off-list, rather than redrawing it as something else or
 * dropping it. Empty is not off-list: nothing is seated. */
export function offCatalog(groups: ModelGroup[], model: string): boolean {
  return model !== '' && providerForModel(groups, model) === null
}

// -- one choice seats a whole board ------------------------------------------

/** What one seat is set to, as a house derives it. */
export interface SeatChoice {
  provider: string
  model: string
  /** only where the backend reads a depth at all (codex writes
   * `model_reasoning_effort`; claude has no such knob) */
  effort?: string
}

/** A house's whole board: seat -> what it sits on.
 *
 * Derived engine-side by RANK, never by name (`serve/model_catalog`):
 * the theory layer takes the provider's top series, the planning layer
 * the second, the formal layer the third. Which is why nothing on this
 * side knows a model name — a series above today's top shifts all three
 * layers and no code here changes. */
export type HouseBoard = Record<string, SeatChoice>

/** What the page hands the existing seat-write path, one key at a time.
 *
 * ONLY seat keys. The default control seats a board; it is not a licence
 * to rewrite the file, and `Asterism.yaml` is mostly the owner's own
 * reasoning in comments. */
export function boardDrafts(board: HouseBoard): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [seat, s] of Object.entries(board)) {
    out[`${seat}.model`] = s.model
    out[`${seat}.provider`] = s.provider
    if (s.effort !== undefined) out[`${seat}.reasoning_effort`] = s.effort
  }
  return out
}

const seatIsOn = (row: SeatRow, s: SeatChoice): boolean => {
  const at = (c: ConfigSetting | null) => String(c?.resolved ?? '')
  if (at(row.model) !== s.model) return false
  if (at(row.provider) !== s.provider) return false
  return s.effort === undefined || at(row.effort) === s.effort
}

/** The seats sitting somewhere other than where the house would put
 * them — PINNED, in the default control's word for it.
 *
 * A seat the board says nothing about is not pinned: silence is not an
 * override, and marking it would tell the reader they had made a choice
 * they did not make. */
export function pinnedSeats(rows: SeatRow[], board: HouseBoard): string[] {
  return rows
    .filter((r) => board[r.seat] !== undefined && !seatIsOn(r, board[r.seat]))
    .map((r) => r.seat)
}

/** Which house this machine is on — the one whose board it departs from
 * least.
 *
 * There is no stored answer to this and there must not be: the truth is
 * the yaml, and a remembered "you chose claude" that the seats no longer
 * agree with is a second answer to one question. A house that derives
 * nothing (its backend offers no models) cannot be the one in effect. */
export function houseInEffect(
  rows: SeatRow[],
  houses: Record<string, HouseBoard>,
): string | null {
  let best: string | null = null
  let fewest = Infinity
  for (const [name, board] of Object.entries(houses)) {
    if (Object.keys(board).length === 0) continue
    const off = pinnedSeats(rows, board).length
    if (off < fewest) {
      fewest = off
      best = name
    }
  }
  return best
}

// -- the picker's own shape --------------------------------------------------

/** A provider, and what is true of the WHOLE of it. */
export interface PickerHeader {
  kind: 'header'
  provider: string
  /** `(not installed)` / `— list not live`, or nothing at all */
  note: string
}

/** One model, under the provider that runs it. */
export interface PickerModel {
  kind: 'model'
  provider: string
  model: string
}

export type PickerRow = PickerHeader | PickerModel

/** Where a model the offer does not name is filed. An env or yaml
 * override may seat anything; dropping it would show the reader a
 * picker that disagrees with the seat it is describing. */
export const OFF_LIST = 'set outside this list'

/** The picker as a HIERARCHY: a header per provider, its models under
 * it, in the offer's own order.
 *
 * The two caveats — a backend that is not installed, a list that is
 * declared rather than probed — are facts about the PROVIDER. They
 * belong on its header once, not on each of its models, where they
 * would draw one fact as many times as the vendor ships tiers
 * (DESIGN.md: never draw the same fact twice). A provider offering
 * nothing draws no header: an empty group is not a group.
 *
 * `current` keeps a seated model visible even when no group claims it,
 * under a header that says exactly that rather than inventing an owner
 * for it (`providerForModel` is the same rule from the other side). */
export function pickerRows(groups: ModelGroup[], current = ''): PickerRow[] {
  const rows: PickerRow[] = []
  if (current !== '' && providerForModel(groups, current) === null) {
    rows.push({ kind: 'header', provider: OFF_LIST, note: '' })
    rows.push({ kind: 'model', provider: OFF_LIST, model: current })
  }
  for (const g of groups) {
    if (g.models.length === 0) continue
    rows.push({
      kind: 'header',
      provider: g.provider,
      note:
        (g.installed ? '' : ' (not installed)') +
        (g.source === 'declared' ? ' — list not live' : ''),
    })
    for (const m of g.models) rows.push({ kind: 'model', provider: g.provider, model: m })
  }
  return rows
}

/** The groups the Assistant may actually seat.
 *
 * `/api/models/refresh` answers for every backend installed on this
 * machine; `/api/chat/state` answers for the ones that can EXPLAIN. The
 * probe is the better list where the two overlap — it is live — but a
 * provider the state never offered cannot answer a question at all, and
 * offering its models seats a conversation on a spawn that dies (field
 * test, 2026-09-06: the picker showed `codex — list not live`). A seat
 * the probe was silent about keeps its declared list rather than
 * vanishing. */
export function explainerGroups(
  stateGroups: ModelGroup[],
  refreshed: ModelGroup[] | null,
): ModelGroup[] {
  if (refreshed === null) return stateGroups
  const seats = new Set(stateGroups.map((g) => g.provider))
  const live = refreshed.filter((g) => seats.has(g.provider))
  const answered = new Set(live.map((g) => g.provider))
  return [...live, ...stateGroups.filter((g) => !answered.has(g.provider))]
}
