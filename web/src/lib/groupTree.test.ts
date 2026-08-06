import { describe, expect, it } from 'vitest'
import { charterTitle, groupMeta, groupState, treeRows } from './groupTree'
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
