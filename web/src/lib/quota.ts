import type { RunStatus } from './types'

type Scoped = NonNullable<RunStatus['quota']>['scoped'][number]

/*
 * Per-model weekly caps, prepared for display.
 *
 * The account's own usage endpoint decides what exists here: the cap
 * was Sonnet's, it is Fable's now, and there may be stretches with no
 * scoped cap at all. So nothing about the model is ever assumed — the
 * console renders what is reported, in a stable order, and shows
 * nothing when nothing is reported (owner, 2026-08-03: "either drop
 * this row or do it properly").
 */
export function scopedRows(scoped: Scoped[] | undefined | null): Scoped[] {
  const best = new Map<string, Scoped>()
  for (const s of scoped ?? []) {
    const name = (s?.name ?? '').trim()
    if (name === '') continue
    const row: Scoped = {
      ...s,
      name,
      percent: Number.isFinite(s.percent) ? s.percent : 0,
    }
    const prev = best.get(name)
    // a duplicate name should not happen; if it does, the binding
    // reading (then the larger one) is the one that matters
    if (
      prev === undefined ||
      (row.is_active && !prev.is_active) ||
      (row.is_active === prev.is_active && row.percent > prev.percent)
    )
      best.set(name, row)
  }
  // binding first, then alphabetical — the API's array order is not
  // ours to depend on, and a row that reshuffles between 2s polls
  // reads as flicker
  return [...best.values()].sort(
    (a, b) =>
      Number(b.is_active) - Number(a.is_active) || a.name.localeCompare(b.name),
  )
}
