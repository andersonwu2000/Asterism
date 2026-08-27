import { describe, expect, it } from 'vitest'
import { layoutConstellation, liveWorkIds, X_GAP } from './layout'
import type { ConstellationLayout } from './layout'
import type { Goal, Strategy, StrategyEdge } from './types'
import residueFixture from './__fixtures__/residue_thm.json'
import jordanFixture from './__fixtures__/jordan.json'
import a5CmpFixture from './__fixtures__/a5_cmp.json'
import stokesFixture from './__fixtures__/stokes.json'

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
  // the hub shape (2026-08-26): stokes' `smul_form` is a SINGLETON
  // that 100 of the 370 proof files import. It is why the engine used
  // to carry two hub tiers; the tiers are gone and the shape is not,
  // so it stays as a fixture — the laws below must hold for a star a
  // quarter of the sky reaches for, with no rule cut to its measure.
  // Frozen AFTER v44 link_kind reached the payload, so it also pins
  // the reuse-vs-decomposition split the other three predate.
  stokes: stokesFixture as unknown as Fixture,
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

describe('layout edge cases', () => {
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

  /*
   * v44 `link_kind`. On union_closed's fin4_..._d_trace_type_catalog,
   * SEVEN routes cite one lemma (#8781) and mint nothing: drawn as
   * decomposition, that lemma grew seven solid limbs fanning across
   * the sky AND got shoved below every citer by the layering pass —
   * exactly the failure the citation loop's own comment forbids ("a
   * heavily cited def would otherwise drag half the sky under
   * itself"). The engine has filtered on link_kind since v44; only the
   * read side was flattening it.
   */
  it('a reused lemma is a cross-link, not a branch of the route that cites it', () => {
    const goals = [goal(1, { origin: 'root' }), goal(2), goal(3)]
    const strategies = [
      { id: 10, goal_id: 1, status: 'proposed' },
      { id: 11, goal_id: 2, status: 'proposed' },
    ] as Strategy[]
    const edges = [
      { strategy_id: 10, subgoal_id: 2, link_kind: 'minted' },
      { strategy_id: 10, subgoal_id: 3, link_kind: 'minted' },
      // route 11 hangs off goal 2 and only REUSES goal 3
      { strategy_id: 11, subgoal_id: 3, link_kind: 'cited' },
    ] as StrategyEdge[]
    const v = layoutConstellation(goals, strategies, edges)
    const reuse = v.edges.filter((e) => e.from === 3 && e.to === 2)
    expect(reuse.length).toBe(1)
    expect(reuse[0].kind).toBe('citation')
    // ...and it keeps the route's own id, so the thread is openable
    expect(reuse[0].strategyId).toBe(11)
    // the citing route contributes no bundle: it minted nothing
    expect(v.bundles.map((b) => b.strategyId)).toEqual([10])
  })

  it('does not push a reused lemma below the routes that reach for it', () => {
    // the layering pass walks hierarchy only; a cited link must not
    // add a parent, or one lemma sinks under every citer
    const goals = [goal(1, { origin: 'root' }), goal(2), goal(3), goal(4)]
    const strategies = [
      { id: 10, goal_id: 1, status: 'proposed' },
      { id: 11, goal_id: 2, status: 'proposed' },
      { id: 12, goal_id: 4, status: 'proposed' },
    ] as Strategy[]
    const cited = layoutConstellation(goals, strategies, [
      { strategy_id: 10, subgoal_id: 2, link_kind: 'minted' },
      { strategy_id: 10, subgoal_id: 3, link_kind: 'minted' },
      { strategy_id: 10, subgoal_id: 4, link_kind: 'minted' },
      { strategy_id: 11, subgoal_id: 3, link_kind: 'cited' },
      { strategy_id: 12, subgoal_id: 3, link_kind: 'cited' },
    ] as StrategyEdge[])
    const bare = layoutConstellation(goals, strategies, [
      { strategy_id: 10, subgoal_id: 2, link_kind: 'minted' },
      { strategy_id: 10, subgoal_id: 3, link_kind: 'minted' },
      { strategy_id: 10, subgoal_id: 4, link_kind: 'minted' },
    ] as StrategyEdge[])
    const y = (v: ConstellationLayout, id: number) =>
      v.nodes.find((n) => n.goal.id === id)!.y
    expect(y(cited, 3)).toBe(y(bare, 3))
    expect(y(cited, 3)).toBe(y(cited, 2))
  })

  /*
   * The retired hub tiers (owner, 2026-08-26: "no more ultra-hub
   * distinction — return it to a normal node"). A singleton a quarter
   * of the sky cites used to leave the shared beds for a component of
   * its own, then get a band spliced in for itself alone, plate-
   * centred, with its starburst exempted from the crossing objective.
   * Two tiers, one witness, and the reason they existed was that its
   * 100 threads used to be drawn as solid starlight — indistinguishable
   * from structure, so a sun in a shelf read as a tangle. Cross-links
   * dot now. What must still hold is only what holds for everyone.
   */
  it('gives a star a quarter of the sky cites no rule of its own', () => {
    const f = FIXTURES.stokes
    const v = run(f)
    const deg = new Map<number, number>()
    for (const e of v.edges) {
      if (e.kind !== 'citation' && e.kind !== 'alias') continue
      deg.set(e.from, (deg.get(e.from) ?? 0) + 1)
      deg.set(e.to, (deg.get(e.to) ?? 0) + 1)
    }
    const [hubId, hubDeg] = [...deg].sort((a, b) => b[1] - a[1])[0]
    expect(hubDeg).toBeGreaterThanOrEqual(f.goals.length * 0.25)
    const hub = v.nodes.find((n) => n.goal.id === hubId)!
    // it shares a row like anything else — no band reserved for it
    expect(
      v.nodes.filter((n) => Math.abs(n.y - hub.y) < 1).length,
    ).toBeGreaterThan(1)
    // and it is still ON the plate, which is the law that DID matter
    checkLaws(v, f)
  })

  it('reads a pre-v44 edge (no link_kind) as minted', () => {
    const goals = [goal(1, { origin: 'root' }), goal(2), goal(3)]
    const strategies = [{ id: 10, goal_id: 1, status: 'proposed' }] as Strategy[]
    const v = layoutConstellation(goals, strategies, [
      { strategy_id: 10, subgoal_id: 2 },
      { strategy_id: 10, subgoal_id: 3 },
    ] as StrategyEdge[])
    expect(v.bundles.length).toBe(1)
    expect(v.edges.every((e) => e.kind === 'strategy')).toBe(true)
  })
})

/*
 * The blink law (owner, 2026-08-27): a star blinks when work is
 * DISPATCHED on it or anywhere beneath it — never for wearing
 * `attempting`, which only says the goal was decomposed and is
 * waiting. These are the cases the sky got wrong.
 */
describe('the blink follows the work, not the status', () => {
  const strat = (id: number, goal_id: number): Strategy =>
    ({ id, goal_id, status: 'proposed' }) as Strategy
  const minted = (sid: number, ...subs: number[]): StrategyEdge[] =>
    subs.map((s) => ({ strategy_id: sid, subgoal_id: s, link_kind: 'minted' })) as StrategyEdge[]

  it('leaves a bare `attempting` dark when nothing is dispatched', () => {
    // the whole complaint: `attempting` rode up as liveness, and a
    // goal wears it while its entire subtree sits parked
    const goals = [goal(1, { status: 'attempting' }), goal(2, { status: 'open' })]
    const hot = liveWorkIds(goals, [strat(10, 1)], minted(10, 2))
    expect([...hot]).toEqual([])
  })

  it('blinks the star an agent is actually on', () => {
    const goals = [goal(1, { status: 'attempting' }), goal(2, { in_flight: true })]
    const hot = liveWorkIds(goals, [strat(10, 1)], minted(10, 2))
    expect(hot.has(2)).toBe(true)
  })

  it('carries the blink up every star the work hangs under', () => {
    // 1 → 2 → 3, an agent on 3: the whole spine leads the eye down
    const goals = [goal(1, { origin: 'root' }), goal(2), goal(3, { in_flight: true })]
    const hot = liveWorkIds(
      goals, [strat(10, 1), strat(11, 2)], [...minted(10, 2), ...minted(11, 3)])
    expect([...hot].sort((a, b) => a - b)).toEqual([1, 2, 3])
  })

  it('leaves the sibling branch dark', () => {
    // 1 decomposes into 2 and 3; the agent is on 2 — 3 has no work
    const goals = [goal(1, { origin: 'root' }), goal(2, { in_flight: true }), goal(3)]
    const hot = liveWorkIds(goals, [strat(10, 1)], minted(10, 2, 3))
    expect(hot.has(3)).toBe(false)
    expect([...hot].sort((a, b) => a - b)).toEqual([1, 2])
  })

  it('does not climb a citation — one busy lemma must not blink its citers', () => {
    // goal 3 is a lemma route 11 REUSES. Work inside it belongs to
    // whoever minted it, not to everyone reaching for it (this is
    // `link_kind` again, so the two rules cannot drift apart).
    const goals = [goal(1, { origin: 'root' }), goal(2), goal(3, { in_flight: true })]
    const edges = [
      ...minted(10, 2, 3),
      { strategy_id: 11, subgoal_id: 3, link_kind: 'cited' },
    ] as StrategyEdge[]
    const hot = liveWorkIds(goals, [strat(10, 1), strat(11, 2)], edges)
    expect(hot.has(2)).toBe(false)
    expect([...hot].sort((a, b) => a - b)).toEqual([1, 3])
  })

  it('climbs an anchor to the claim it holds up', () => {
    // anchors hang beneath their claim — layout flips them, and so
    // must this, or the blink runs the wrong way down the picture
    const goals = [goal(1, { origin: 'root' }), goal(2, { in_flight: true })]
    const hot = liveWorkIds(goals, [], [], [{ from: 2, to: 1 }])
    expect([...hot].sort((a, b) => a - b)).toEqual([1, 2])
  })

  it('survives a hierarchy cycle', () => {
    // research mode really produces these (the a5_cmp fixture's
    // 6370→6375→6380→6370); a blink must not spin on one
    const goals = [goal(1, { in_flight: true }), goal(2), goal(3)]
    const hot = liveWorkIds(
      goals, [strat(10, 1), strat(11, 2), strat(12, 3)],
      [...minted(10, 2), ...minted(11, 3), ...minted(12, 1)])
    expect([...hot].sort((a, b) => a - b)).toEqual([1, 2, 3])
  })

  it('climbs only edges the reader can see it climb', () => {
    // Anti-drift lock. "Beneath" must mean what the PICTURE means by
    // it: every star the blink carries to is one layout actually drew
    // a parent line from, on real problem shapes.
    for (const [name, f] of Object.entries(FIXTURES)) {
      const v = run(f)
      const parents = new Map<number, Set<number>>()
      const add = (child: number, parent: number) => {
        const at = parents.get(child)
        if (at) at.add(parent)
        else parents.set(child, new Set([parent]))
      }
      for (const e of v.edges)
        if (e.kind === 'strategy' || e.kind === 'anchor') add(e.to, e.from)
      for (const b of v.bundles) for (const c of b.children) add(c, b.parentId)

      const drawn = new Set(v.nodes.map((n) => n.goal.id))
      // ~a dozen seeds spread through the node order whatever the
      // fixture's size, so the walk crosses several real trees (a
      // fixed stride gave the 36-goal a5_cmp exactly one seed, and it
      // was a root — the non-vacuity guard below caught that)
      const stride = Math.max(1, Math.floor(v.nodes.length / 12))
      const seeds = v.nodes.filter((_, i) => i % stride === 0).map((n) => n.goal.id)
      let climbed = 0
      for (const seed of seeds) {
        const hot = liveWorkIds(
          f.goals.map((g) => (g.id === seed ? { ...g, in_flight: true } : { ...g, in_flight: false })),
          f.strategies, f.strategy_edges, f.anchor_edges)
        for (const id of hot) {
          if (id === seed || !drawn.has(id)) continue
          climbed++
          // it is hot because something under it is: SOME child of it
          // is hot too, along a line layout drew
          const viaDrawnChild = [...hot].some((c) => parents.get(c)?.has(id))
          expect(viaDrawnChild, `${name}: star ${id} blinks with no drawn child under it`).toBe(true)
        }
      }
      // the seeds must actually have ancestors, or this proves nothing
      expect(climbed, `${name}: no seed climbed — the lock is vacuous`)
        .toBeGreaterThan(0)
    }
  })
})
