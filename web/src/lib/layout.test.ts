import { describe, expect, it } from 'vitest'
import { layoutConstellation, X_GAP } from './layout'
import type { ConstellationLayout } from './layout'
import type { Goal, Strategy, StrategyEdge } from './types'
import residueFixture from './__fixtures__/residue_thm.json'
import jordanFixture from './__fixtures__/jordan.json'
import a5CmpFixture from './__fixtures__/a5_cmp.json'

/*
 * Layout laws — the invariants the sky engine must hold on ANY input.
 * These are the regressions that actually happened (2026-07-08/09
 * optimisation rounds): trees beached outside the plate, NaN
 * coordinates from an empty band, nodes stacked on one point. Fixtures
 * are real problem states frozen from the live workspace (residue_thm
 * 500 goals / jordan 166 goals) so the laws are checked at production
 * scale, not toy scale.
 */

const PAD = 60 // layout.ts's plate padding (not exported by design)

interface Fixture {
  goals: Goal[]
  strategies: Strategy[]
  strategy_edges: StrategyEdge[]
  anchor_edges: { from: number; to: number }[]
  citation_edges: { from: number; to: number }[]
}

const FIXTURES: Record<string, Fixture> = {
  residue_thm: residueFixture as unknown as Fixture,
  jordan: jordanFixture as unknown as Fixture,
  // research-mode shape (2026-07-19): a relink cycle in the strategy
  // hierarchy (goals 6370→6375→6380→6370) — no tree root reaches the
  // ring, the x pass averaged over nothing, and the sky rendered
  // blank (owner report). The layout must survive ANY db state.
  a5_cmp: a5CmpFixture as unknown as Fixture,
}

function run(f: Fixture): ConstellationLayout {
  return layoutConstellation(
    f.goals, f.strategies, f.strategy_edges, f.anchor_edges, f.citation_edges)
}

function checkLaws(v: ConstellationLayout, f: Fixture) {
  // dimensions are finite and positive
  expect(Number.isFinite(v.width) && v.width > 0).toBe(true)
  expect(Number.isFinite(v.height) && v.height > 0).toBe(true)

  // every coordinate is a real number — NaN poisons silently downstream
  for (const n of v.nodes) {
    expect(Number.isFinite(n.x), `node ${n.goal.id} x`).toBe(true)
    expect(Number.isFinite(n.y), `node ${n.goal.id} y`).toBe(true)
  }
  for (const b of v.bundles) {
    expect(Number.isFinite(b.junction.x), `bundle s${b.strategyId} jx`).toBe(true)
    expect(Number.isFinite(b.junction.y), `bundle s${b.strategyId} jy`).toBe(true)
  }

  // plate bounds law: the engine must never move a node outside the
  // padded plate (jordan beached at x=-3208 before the tryMove guard)
  for (const n of v.nodes) {
    expect(n.x, `node ${n.goal.id} beached left`).toBeGreaterThanOrEqual(PAD - 1)
    expect(n.x, `node ${n.goal.id} beached right`).toBeLessThanOrEqual(v.width - PAD + 1)
    expect(n.y).toBeGreaterThanOrEqual(0)
    expect(n.y).toBeLessThanOrEqual(v.height)
  }

  // node identity: unique goals, each drawn once, all from the input
  const inputIds = new Set(f.goals.map((g) => g.id))
  const seen = new Set<number>()
  for (const n of v.nodes) {
    expect(inputIds.has(n.goal.id), `node ${n.goal.id} not in input`).toBe(true)
    expect(seen.has(n.goal.id), `goal ${n.goal.id} drawn twice`).toBe(false)
    seen.add(n.goal.id)
  }

  // row discipline: two stars on the same row never share a slot
  // (identical coordinates = one star hides another)
  const byY = new Map<number, number[]>()
  for (const n of v.nodes) {
    const xs = byY.get(n.y) ?? []
    xs.push(n.x)
    byY.set(n.y, xs)
  }
  for (const [y, xs] of byY) {
    xs.sort((a, b) => a - b)
    for (let i = 1; i < xs.length; i++) {
      expect(xs[i] - xs[i - 1], `row y=${y} stars overlap`)
        .toBeGreaterThanOrEqual(X_GAP / 2 - 1)
    }
  }

  // referential integrity: edges and bundles only point at drawn stars
  for (const e of v.edges) {
    expect(seen.has(e.from), `edge from ${e.from} undrawn`).toBe(true)
    expect(seen.has(e.to), `edge to ${e.to} undrawn`).toBe(true)
  }
  for (const b of v.bundles) {
    expect(seen.has(b.parentId), `bundle s${b.strategyId} parent undrawn`).toBe(true)
    for (const c of b.children) {
      expect(seen.has(c), `bundle s${b.strategyId} child ${c} undrawn`).toBe(true)
    }
  }
}

describe('layout laws on real problem states', () => {
  // EVERY fixture — a hardcoded pair here meant the a5 fixtures never
  // ran and the suite said "passed" while the live sky was NaN
  for (const name of Object.keys(FIXTURES)) {
    it(`${name}: holds every law`, () => {
      const f = FIXTURES[name]
      const v = run(f)
      expect(v.nodes.length).toBeGreaterThan(0)
      checkLaws(v, f)
    })

    it(`${name}: is deterministic`, () => {
      const f = FIXTURES[name]
      const a = run(f)
      const b = run(f)
      expect(b.nodes.map((n) => [n.goal.id, n.x, n.y]))
        .toEqual(a.nodes.map((n) => [n.goal.id, n.x, n.y]))
      expect(b.width).toBe(a.width)
      expect(b.height).toBe(a.height)
    })
  }
})

describe('layout edge cases', () => {
  const goal = (id: number, over: Partial<Goal> = {}): Goal =>
    ({
      id,
      slug: `g${id}`,
      status: 'open',
      kind: 'Prop',
      origin: 'backward',
      depth: 0,
      detached: false,
      alias_target_id: null,
      is_deliverable: false,
      statement: '',
      lean_path: '',
      created_at: '',
      attempts: 0,
      dead_attempts: 0,
      in_flight: false,
      ...over,
    }) as Goal

  it('empty input does not crash and yields finite dims', () => {
    const v = layoutConstellation([], [], [])
    expect(Number.isFinite(v.width)).toBe(true)
    expect(Number.isFinite(v.height)).toBe(true)
    expect(v.nodes).toEqual([])
  })

  it('a single root renders one star inside the plate', () => {
    const v = layoutConstellation([goal(1, { origin: 'root' })], [], [])
    expect(v.nodes.length).toBe(1)
    checkLaws(v, {
      goals: [goal(1, { origin: 'root' })],
      strategies: [], strategy_edges: [], anchor_edges: [], citation_edges: [],
    })
  })

  it('an AND-group becomes one bundle with a junction between the rows', () => {
    const goals = [goal(1, { origin: 'root' }), goal(2), goal(3)]
    const strategies = [{ id: 10, goal_id: 1, status: 'proposed' }] as Strategy[]
    const edges = [
      { strategy_id: 10, subgoal_id: 2 },
      { strategy_id: 10, subgoal_id: 3 },
    ] as StrategyEdge[]
    const v = layoutConstellation(goals, strategies, edges)
    expect(v.bundles.length).toBe(1)
    const b = v.bundles[0]
    expect(b.parentId).toBe(1)
    expect(new Set(b.children)).toEqual(new Set([2, 3]))
    const parent = v.nodes.find((n) => n.goal.id === 1)!
    const kid = v.nodes.find((n) => n.goal.id === 2)!
    expect(b.junction.y).toBeGreaterThan(parent.y)
    expect(b.junction.y).toBeLessThan(kid.y)
  })

  it('alias twins both render (one pair of stars, one line)', () => {
    const goals = [goal(1, { origin: 'root' }), goal(2, { origin: 'forward', alias_target_id: 1 })]
    const v = layoutConstellation(goals, [], [])
    expect(v.nodes.length).toBe(2)
  })
})
