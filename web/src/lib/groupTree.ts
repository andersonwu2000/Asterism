import type { Group } from './types'

/*
 * The discussion tree, prepared for reading.
 *
 * A flat chip row said three delegated burdens were three peer things;
 * they are one argument that handed pieces of itself out. Depth is the
 * delegation, and the row's own line says WHERE in the argument it was
 * handed out (`from rev N`) — the single fact that ties the document
 * to the tree (owner, 2026-08-07).
 */

export interface TreeRow {
  group: Group
  depth: number
}

/** Parent before child, siblings by id; a row whose parent is missing
 * (or which sits in a cycle) is shown at the root rather than dropped
 * — a group the reader cannot see is worse than one drawn shallow. */
export function treeRows(groups: Group[] | undefined | null): TreeRow[] {
  const all = groups ?? []
  if (all.length === 0) return []
  const byParent = new Map<number | null, Group[]>()
  const ids = new Set(all.map((g) => g.id))
  for (const g of all) {
    const key = g.parent_id !== null && ids.has(g.parent_id) ? g.parent_id : null
    const list = byParent.get(key)
    if (list) list.push(g)
    else byParent.set(key, [g])
  }
  for (const list of byParent.values()) list.sort((a, b) => a.id - b.id)
  const out: TreeRow[] = []
  const seen = new Set<number>()
  const walk = (parent: number | null, depth: number) => {
    for (const g of byParent.get(parent) ?? []) {
      if (seen.has(g.id)) continue // a cycle is a framework bug, not a hang
      seen.add(g.id)
      out.push({ group: g, depth })
      walk(g.id, depth + 1)
    }
  }
  walk(null, 0)
  // anything a cycle kept out of the walk still gets drawn
  for (const g of all) if (!seen.has(g.id)) out.push({ group: g, depth: 0 })
  return out
}

/** What a row is CALLED: the argument's own title, the way any
 * document names itself. The charter is the reason it was handed the
 * burden — a paragraph, and a poor label (owner, 2026-08-07); it
 * stands in only until the group's first revision names it, and it
 * appears in full inside that group's own read. */
export function charterTitle(g: Group): string {
  if (g.is_top) return 'the problem'
  const titled = (g.title ?? '').trim()
  if (titled !== '') return titled
  const first = (g.charter || '')
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l !== '')
  const cleaned = (first ?? '')
    .replace(/^#+\s*/, '')
    .replace(/^(charter|roadmap)\s*[:—-]\s*/i, '')
    .trim()
  return cleaned === '' ? `group ${g.id}` : cleaned
}

/** How loudly a row should read.
 *
 * The sky's law, applied to the tree: light belongs to what is still
 * alive, and what is settled RECEDES (`Constellation.nodeStyle` — a
 * proved star dims to 45% while anything is live, shelved sits at
 * 0.45 opacity). Nothing there is struck through, and nothing here
 * should be either: this UI already spends `line-through` on deleted
 * text in a diff, so striking a delivered group would say it was
 * retracted when it succeeded (owner, 2026-08-07).
 *
 *   live      — a strategist is seated in it this minute
 *   idle      — alive, between wakes
 *   delivered — settled, and its bricks came home (filled, receded)
 *   settled   — handed back or retired: nothing came home (hollow)
 */
export type GroupTone = 'live' | 'idle' | 'delivered' | 'settled'

export function groupTone(g: Group, seated: boolean): GroupTone {
  if (g.status === 'delivered') return 'delivered'
  if (g.status !== 'active') return 'settled'
  return seated ? 'live' : 'idle'
}

/** What this group is doing, in the reader's words: its live argument
 * phase when a strategist is seated, else where it ended up. */
export function groupState(g: Group, phase?: string): string {
  if (phase) return phase
  if (g.status === 'active') return 'between wakes'
  if (g.status === 'delivered') return 'delivered'
  if (g.status === 'returned') return 'handed back'
  if (g.status === 'closed') return 'retired'
  return g.status
}

/** The right-hand line: where it was handed out, its own revision
 * chain, what it is doing, how much it has built. */
export function groupMeta(g: Group, phase?: string): string {
  const bits: string[] = []
  if (!g.is_top && g.opened_at_rev != null)
    bits.push(`handed out of rev ${g.opened_at_rev}`)
  bits.push(g.rev != null ? `rev ${g.rev}` : 'no rev yet')
  if (!g.is_top) bits.push(groupState(g, phase))
  else if (phase) bits.push(phase)
  if (g.bricks) bits.push(`${g.bricks} brick${g.bricks === 1 ? '' : 's'}`)
  return bits.join(' · ')
}
