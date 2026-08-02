import { describe, expect, it } from 'vitest'
import { cycleForGroup, defaultGroup } from './programmeFocus'
import type { Group, RunWorker } from './types'

const group = (id: number, is_top: boolean): Group => ({
  id,
  problem: 'P',
  parent_id: is_top ? null : 1,
  is_top,
  charter: is_top ? '' : `settle claim ${id}`,
  status: 'active',
  anchor_goal_id: null,
  created_at: '2026-08-02T00:00:00+00:00',
})

const strategist = (g: Group | null, phase?: 'judging' | 'proposing'): RunWorker => ({
  kind: 'Strategist',
  slug: 'P',
  group: g,
  statement: null,
  leased_at: null,
  mode: 'routine',
  path: null,
  file: null,
  cycle: phase
    ? { phase, round: 2, objections: [], since_sec: 10 }
    : null,
})

const formalizer: RunWorker = {
  kind: 'Formalizer',
  slug: 'some_goal',
  group: null,
  statement: null,
  leased_at: null,
  mode: null,
  path: null,
  file: null,
}

describe('which argument the run-scoped Programme opens on', () => {
  it('is the problem itself when nothing is delegated', () => {
    expect(defaultGroup([strategist(group(1, true)), formalizer])).toBe(null)
    expect(defaultGroup([])).toBe(null)
  })

  it('follows the ONE delegated claim being argued right now', () => {
    expect(defaultGroup([strategist(group(7, false))])).toBe(7)
  })

  it('stays on the problem when several groups argue at once', () => {
    // sibling groups run concurrently by design — picking one of them
    // would be arbitrary, and the picker's live dots say where they are
    expect(
      defaultGroup([strategist(group(7, false)), strategist(group(8, false))]),
    ).toBe(null)
  })
})

describe('whose cycle is narrated above the body', () => {
  const workers = [
    strategist(group(7, false), 'judging'),
    strategist(group(8, false), 'proposing'),
  ]

  it('belongs to the chain on screen, never a sibling', () => {
    expect(cycleForGroup(workers, 7)?.phase).toBe('judging')
    expect(cycleForGroup(workers, 8)?.phase).toBe('proposing')
  })

  it('is silent when the shown chain has nobody seated', () => {
    expect(cycleForGroup(workers, 1)).toBe(null)
    expect(cycleForGroup(workers, null)).toBe(null)
    expect(cycleForGroup([], 7)).toBe(null)
  })
})
