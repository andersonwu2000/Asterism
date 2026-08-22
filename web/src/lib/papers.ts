import type { PaperShelfItem } from './types'

/*
 * The shelf, arranged by WHO each paper serves. A flat 28-row table
 * answered "what is on the shelf" but not the reader's actual
 * question — "which problem is this registered under" (owner,
 * 2026-08-22) — and the pile keeps growing now that the strategist
 * fetches with its own tools.
 */

export interface ShelfGroup {
  /** null = registered under no problem (uploaded and never bound, or
   * its problem was reset/deleted and the binding went with it) */
  problem: string | null
  papers: PaperShelfItem[]
}

/** Groups sorted by problem name, the unregistered pile last. A paper
 * bound to several problems appears under EACH — it is registered
 * there, and hiding one registration to avoid a duplicate row would
 * misstate the smaller group. */
export function shelfGroups(papers: PaperShelfItem[]): ShelfGroup[] {
  const by = new Map<string, PaperShelfItem[]>()
  const none: PaperShelfItem[] = []
  for (const p of papers) {
    if (p.bound.length === 0) {
      none.push(p)
      continue
    }
    // a paper can carry two bindings to the same problem in principle
    // (defensive: origins differ); one row per problem regardless
    const seen = new Set<string>()
    for (const b of p.bound) {
      if (seen.has(b.problem)) continue
      seen.add(b.problem)
      const list = by.get(b.problem)
      if (list) list.push(p)
      else by.set(b.problem, [p])
    }
  }
  const out: ShelfGroup[] = [...by.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([problem, list]) => ({ problem, papers: list }))
  if (none.length > 0) out.push({ problem: null, papers: none })
  return out
}
