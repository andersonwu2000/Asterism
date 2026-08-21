import { describe, expect, it } from 'vitest'
import {
  charterTitle,
  groupMeta,
  groupState,
  groupTone,
  isStub,
  prunedTreeRows,
  stubBreakdown,
  treeRows,
} from './groupTree'
import type { SettledStub } from './groupTree'
import type { Group } from './types'

const g = (over: Partial<Group> & { id: number }): Group => ({
  problem: 'P',
  parent_id: null,
  is_top: false,
  charter: '',
  status: 'active',
  anchor_goal_id: null,
  created_at: '2026-08-07T00:00:00+00:00',
  ...over,
})

describe('the tree a flat chip row could not show', () => {
  it('walks parent before child, siblings by id', () => {
    const rows = treeRows([
      g({ id: 382, parent_id: 379 }),
      g({ id: 379, parent_id: null, is_top: true }),
      g({ id: 381, parent_id: 379 }),
      g({ id: 390, parent_id: 381 }), // a sub-group delegating further
    ])
    expect(rows.map((r) => [r.group.id, r.depth])).toEqual([
      [379, 0],
      [381, 1],
      [390, 2],
      [382, 1],
    ])
  })

  it('draws an orphan at the root rather than dropping it', () => {
    // a group the reader cannot see is worse than one drawn shallow
    const rows = treeRows([g({ id: 5, parent_id: 999 })])
    expect(rows.map((r) => r.group.id)).toEqual([5])
  })

  it('survives a parent cycle without spinning', () => {
    const rows = treeRows([
      g({ id: 1, parent_id: 2 }),
      g({ id: 2, parent_id: 1 }),
    ])
    expect(rows.map((r) => r.group.id).sort()).toEqual([1, 2])
  })

  it('is empty when nothing was ever delegated', () => {
    expect(treeRows([])).toEqual([])
    expect(treeRows(undefined)).toEqual([])
  })
})

describe('naming a charter', () => {
  it('drops the decoration the strategist writes around its title', () => {
    expect(
      charterTitle(g({ id: 1, charter: '# Charter: explicit-constant abundance\n\nbody' })),
    ).toBe('explicit-constant abundance')
    expect(charterTitle(g({ id: 2, charter: 'Roadmap: structure track (Poonen)' }))).toBe(
      'structure track (Poonen)',
    )
  })

  it('names the top group for what it is', () => {
    expect(charterTitle(g({ id: 3, is_top: true }))).toBe('the problem')
  })

  it('falls back to the id rather than an empty row', () => {
    expect(charterTitle(g({ id: 7, charter: '   \n\n' }))).toBe('group 7')
  })
})

describe('how loudly a row reads', () => {
  it('gives the light to what is still alive', () => {
    expect(groupTone(g({ id: 1, status: 'active' }), true)).toBe('live')
    expect(groupTone(g({ id: 1, status: 'active' }), false)).toBe('idle')
  })

  it('lets a delivered branch recede without striking it out', () => {
    // `line-through` means DELETED text in this UI (the diff view);
    // a delivered group succeeded, and the sky dims what is settled
    // rather than crossing it off
    expect(groupTone(g({ id: 1, status: 'delivered' }), false)).toBe('delivered')
  })

  it('separates "came home settled" from "came back with nothing"', () => {
    expect(groupTone(g({ id: 1, status: 'returned' }), false)).toBe('settled')
    expect(groupTone(g({ id: 1, status: 'closed' }), false)).toBe('settled')
  })

  it('never calls a terminal group live, whatever a stale lane says', () => {
    // a seat can linger in the poll after the group settles
    expect(groupTone(g({ id: 1, status: 'delivered' }), true)).toBe('delivered')
  })
})

describe('the row line', () => {
  it('says where it was handed out, its own chain, and its size', () => {
    const row = g({
      id: 381,
      parent_id: 379,
      opened_at_rev: 3,
      rev: 7,
      bricks: 10,
    })
    expect(groupMeta(row)).toBe(
      'handed out of rev 3 · rev 7 · between wakes · 10 bricks',
    )
  })

  it('shows the live argument phase over the resting status', () => {
    const row = g({ id: 381, parent_id: 379, opened_at_rev: 3, rev: 1, bricks: 8 })
    expect(groupMeta(row, 'round 2 judging')).toContain('round 2 judging')
    expect(groupMeta(row, 'round 2 judging')).not.toContain('between wakes')
  })

  it('does not pretend a fresh group has a revision', () => {
    expect(groupMeta(g({ id: 9, parent_id: 1, opened_at_rev: 6 }))).toBe(
      'handed out of rev 6 · no rev yet · between wakes',
    )
  })

  it('names each terminal state in the reader s words', () => {
    expect(groupState(g({ id: 1, status: 'delivered' }))).toBe('delivered')
    expect(groupState(g({ id: 1, status: 'returned' }))).toBe('handed back')
    expect(groupState(g({ id: 1, status: 'closed' }))).toBe('retired')
  })
})

describe('folding the settled mass (union_closed grew 101 corpses)', () => {
  // the real shape in miniature: a live spine, a settled pile under
  // the top, and a deep settled chain
  const forest = [
    g({ id: 1, parent_id: null, is_top: true }),
    g({ id: 2, parent_id: 1 }), // alive
    g({ id: 3, parent_id: 1, status: 'delivered' }),
    g({ id: 4, parent_id: 1, status: 'closed' }),
    g({ id: 5, parent_id: 4, status: 'returned' }), // chain under a corpse
    g({ id: 6, parent_id: 5, status: 'closed' }),
    g({ id: 7, parent_id: 2, status: 'delivered' }), // settled under a living one
  ]

  it('default view = the living skeleton + one stub per parent', () => {
    const rows = prunedTreeRows(forest, null, new Set())
    // siblings keep id order (creation order), so the pile sits after
    // the older living child; 3 + the whole 4→5→6 chain = 4 groups
    expect(rows.map((r) => (isStub(r) ? `stub:${r.hidden}@${r.parent}` : r.group.id))).toEqual([
      1,
      2,
      'stub:1@2',
      'stub:4@1',
    ])
    const stub = rows.find((r) => isStub(r) && r.parent === 1) as SettledStub
    expect([stub.delivered, stub.returned, stub.retired]).toEqual([1, 1, 2])
    expect(stubBreakdown(stub)).toBe('1 delivered · 1 handed back · 2 retired')
  })

  it('a settled ancestor of a living group stays on the skeleton', () => {
    // defensive: the cascade should keep this from arising, but the
    // picker must never hide the branch a living group hangs from
    const rows = prunedTreeRows(
      [
        g({ id: 1, parent_id: null, is_top: true }),
        g({ id: 2, parent_id: 1, status: 'closed' }),
        g({ id: 3, parent_id: 2 }), // alive under a corpse
      ],
      null,
      new Set(),
    )
    expect(rows.map((r) => (isStub(r) ? 'stub' : r.group.id))).toEqual([1, 2, 3])
  })

  it('the picked group is always visible, settled or not', () => {
    const rows = prunedTreeRows(forest, 6, new Set())
    // 6's whole ancestor chain (4 → 5) surfaces with it; 3 still folds
    expect(rows.map((r) => (isStub(r) ? `stub:${r.hidden}` : r.group.id))).toEqual([
      1,
      2,
      'stub:1', // 7, under the living 2
      'stub:1', // 3
      4,
      5,
      6,
    ])
  })

  it('unfolds one level per click — the grandchildren fold again', () => {
    const rows = prunedTreeRows(forest, null, new Set([1]))
    // 3 and 4 appear; 4's own settled child folds into a fresh stub
    expect(rows.map((r) => (isStub(r) ? `stub:${r.hidden}@${r.parent}` : r.group.id))).toEqual([
      1,
      2,
      'stub:1@2',
      3,
      4,
      'stub:2@4',
    ])
  })

  it('a finished problem folds to the top group and one stub', () => {
    const done = [
      g({ id: 1, parent_id: null, is_top: true, status: 'delivered' }),
      g({ id: 2, parent_id: 1, status: 'delivered' }),
      g({ id: 3, parent_id: 2, status: 'closed' }),
    ]
    const rows = prunedTreeRows(done, null, new Set())
    expect(rows.map((r) => (isStub(r) ? `stub:${r.hidden}` : r.group.id))).toEqual([1, 'stub:2'])
  })

  it('survives a parent cycle without spinning, folded or not', () => {
    const rows = prunedTreeRows(
      [g({ id: 1, parent_id: 2, status: 'closed' }), g({ id: 2, parent_id: 1, status: 'closed' })],
      null,
      new Set(),
    )
    // both are reachable one way or another — nothing is dropped
    const ids = rows.flatMap((r) => (isStub(r) ? [] : [r.group.id]))
    const hidden = rows.filter(isStub).reduce((n, s) => n + s.hidden, 0)
    expect(ids.length + hidden).toBe(2)
  })
})
