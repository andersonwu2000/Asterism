import { describe, expect, it } from 'vitest'
import { cycleForGroup, defaultGroup, fleetProblem, resolveGroup } from './programmeFocus'
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

describe("the reader's choice vs the run's default", () => {
  const seated = [strategist(group(7, false))]

  it('follows the run until the reader chooses', () => {
    expect(resolveGroup(undefined, seated)).toBe(7)
  })

  it('honours a choice of the problem itself while a sub-group runs', () => {
    // the bug: `pick ?? defaultGroup(...)` folded "chose the problem"
    // into "made no choice", so the chip could not be selected at all
    // and the top group's Programme was unreachable
    expect(resolveGroup(null, seated)).toBe(null)
  })

  it('honours a choice of a group nobody is sitting in', () => {
    expect(resolveGroup(9, seated)).toBe(9)
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

describe('which problem a fleet face opens on', () => {
  const gOn = (id: number, problem: string): Group => ({ ...group(id, true), problem })
  const seatOn = (id: number, problem: string): RunWorker => strategist(gOn(id, problem))

  it('never treats a pattern scope as a problem', () => {
    // the bug that hid the whole tab (2026-08-22): scope "Erdos.%"
    expect(fleetProblem(null, { problem: null, workers: [] }, 'Erdos.%')).toBeNull()
    expect(fleetProblem(null, null, 'Erdos.*')).toBeNull()
  })

  it('a plain single-problem scope still serves as the last resort', () => {
    expect(fleetProblem(null, { problem: null, workers: [] }, 'Combinatorics.union_closed')).toBe(
      'Combinatorics.union_closed',
    )
  })

  it('follows the one problem where a strategist is seated', () => {
    const run = { problem: 'Erdos.p358', workers: [seatOn(516, 'Erdos.p143'), formalizer] }
    expect(fleetProblem(null, run, 'Erdos.%')).toBe('Erdos.p143')
  })

  it('several seated problems fall back to the run focus — picking one would be arbitrary', () => {
    const run = {
      problem: 'Erdos.p358',
      workers: [seatOn(516, 'Erdos.p143'), seatOn(520, 'Erdos.p1')],
    }
    expect(fleetProblem(null, run, 'Erdos.%')).toBe('Erdos.p358')
  })

  it('the reader pin beats everything', () => {
    const run = { problem: 'Erdos.p358', workers: [seatOn(516, 'Erdos.p143')] }
    expect(fleetProblem('Erdos.p912', run, 'Erdos.%')).toBe('Erdos.p912')
  })

  it('two seats in ONE problem still follow that problem', () => {
    // concurrent sibling groups are the same argument's fan, not a tie
    const run = {
      problem: 'Erdos.p358',
      workers: [seatOn(516, 'Erdos.p143'), seatOn(517, 'Erdos.p143')],
    }
    expect(fleetProblem(null, run, 'Erdos.%')).toBe('Erdos.p143')
  })
})
