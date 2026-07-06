import type { Goal, Strategy, StrategyEdge } from './types'

/*
 * Constellation layout — layered (Sugiyama-style), never force-directed
 * (charter appendix guardrail 1: nodes must not move between polls).
 * Deterministic: longest-path layering from the DAG roots, then a few
 * barycenter ordering passes with goal-id tie-breaks, then even
 * horizontal spacing per layer.
 *
 * Graph shape: goal → strategy (a decomposition attempt, an AND-group
 * of subgoals) → subgoal. Strategies are collapsed into parent→child
 * edges carrying the strategy id + status; alternative strategies of
 * one goal are distinguishable by edge grouping.
 */

export interface LayoutNode {
  goal: Goal
  x: number
  y: number
  layer: number
  /** index within the layer (label-stagger parity) */
  col: number
}

export interface LayoutEdge {
  from: number // parent goal id
  to: number // subgoal id
  strategyId: number
  strategyStatus: Strategy['status']
  kind: 'strategy' | 'alias' | 'anchor'
}

export interface AnchorEdge {
  from: number
  to: number
}

/** A strategy's AND-group rendered as a hyperedge: one stem from the
 * parent to a junction, then one branch per subgoal. Competing
 * strategies of the same goal (OR) get side-by-side junctions. */
export interface LayoutBundle {
  strategyId: number
  status: Strategy['status']
  parentId: number
  junction: { x: number; y: number }
  children: number[]
}

export interface ConstellationLayout {
  nodes: LayoutNode[]
  edges: LayoutEdge[] // alias cross-links + single-child strategies
  bundles: LayoutBundle[] // multi-child strategies (AND-groups)
  width: number
  height: number
}

export const X_GAP = 110
export const Y_GAP = 120
const PAD = 60

const ACTIVE_STATUSES = new Set(['open', 'attempting', 'pending_strategist_review'])

export interface FrontierView {
  goals: Goal[]
  /** kept goal id → number of hidden descendants folded into it */
  folded: Map<number, number>
  hiddenCount: number
}

/**
 * Active-frontier focus (charter appendix): keep the live frontier +
 * its ancestor chains + roots + deliverables; everything else folds
 * into its nearest kept ancestor (badge count). For problems with no
 * frontier (terminal), returns everything unchanged.
 */
export function frontierView(
  goals: Goal[],
  strategies: Strategy[],
  strategyEdges: StrategyEdge[],
): FrontierView {
  const frontier = goals.filter((g) => ACTIVE_STATUSES.has(g.status) || g.in_flight)
  if (frontier.length === 0) {
    return { goals, folded: new Map(), hiddenCount: 0 }
  }
  const stratOwner = new Map(strategies.map((s) => [s.id, s.goal_id]))
  const parents = new Map<number, number[]>()
  for (const e of strategyEdges) {
    const p = stratOwner.get(e.strategy_id)
    if (p === undefined) continue
    parents.set(e.subgoal_id, [...(parents.get(e.subgoal_id) ?? []), p])
  }
  const keep = new Set<number>()
  const markWithAncestors = (id: number) => {
    if (keep.has(id)) return
    keep.add(id)
    for (const p of parents.get(id) ?? []) markWithAncestors(p)
  }
  for (const g of frontier) markWithAncestors(g.id)
  for (const g of goals) {
    if (g.origin === 'root' || g.is_deliverable) markWithAncestors(g.id)
  }

  const folded = new Map<number, number>()
  let hiddenCount = 0
  for (const g of goals) {
    if (keep.has(g.id)) continue
    hiddenCount++
    // attribute to the nearest kept ancestor (deterministic: sorted
    // parent walk, breadth-first)
    const queue = [...(parents.get(g.id) ?? [])].sort((a, b) => a - b)
    const seen = new Set<number>(queue)
    let owner: number | null = null
    while (queue.length > 0) {
      const p = queue.shift()!
      if (keep.has(p)) {
        owner = p
        break
      }
      for (const pp of (parents.get(p) ?? []).sort((a, b) => a - b)) {
        if (!seen.has(pp)) {
          seen.add(pp)
          queue.push(pp)
        }
      }
    }
    if (owner !== null) folded.set(owner, (folded.get(owner) ?? 0) + 1)
  }
  return {
    goals: goals.filter((g) => keep.has(g.id)),
    folded,
    hiddenCount,
  }
}

export function layoutConstellation(
  goals: Goal[],
  strategies: Strategy[],
  strategyEdges: StrategyEdge[],
  anchorEdges: AnchorEdge[] = [],
): ConstellationLayout {
  const byId = new Map(goals.map((g) => [g.id, g]))
  const stratById = new Map(strategies.map((s) => [s.id, s]))

  const edges: LayoutEdge[] = []
  for (const e of strategyEdges) {
    const s = stratById.get(e.strategy_id)
    if (!s || !byId.has(s.goal_id) || !byId.has(e.subgoal_id)) continue
    edges.push({
      from: s.goal_id,
      to: e.subgoal_id,
      strategyId: s.id,
      strategyStatus: s.status,
      kind: 'strategy',
    })
  }
  // Kernel-dependency edges from the review snapshot — the structural
  // truth for Forward-built problems, which have no strategy edges.
  const seenPairs = new Set(edges.map((e) => `${e.from}>${e.to}`))
  for (const e of anchorEdges) {
    if (!byId.has(e.from) || !byId.has(e.to)) continue
    if (seenPairs.has(`${e.from}>${e.to}`)) continue
    seenPairs.add(`${e.from}>${e.to}`)
    edges.push({
      from: e.from,
      to: e.to,
      strategyId: -2,
      strategyStatus: 'succeeded',
      kind: 'anchor',
    })
  }
  for (const g of goals) {
    if (g.alias_target_id !== null && byId.has(g.alias_target_id)) {
      edges.push({
        from: g.id,
        to: g.alias_target_id,
        strategyId: -1,
        strategyStatus: 'succeeded',
        kind: 'alias',
      })
    }
  }

  // Longest-path layering over strategy + anchor edges (alias edges
  // are cross-links, not hierarchy). Cycles can't occur (the engine's
  // circularity gate; anchor closures are kernel-acyclic), but guard
  // with a visit cap anyway.
  const children = new Map<number, number[]>()
  const parents = new Map<number, number[]>()
  for (const e of edges) {
    if (e.kind === 'alias') continue
    children.set(e.from, [...(children.get(e.from) ?? []), e.to])
    parents.set(e.to, [...(parents.get(e.to) ?? []), e.from])
  }
  const layer = new Map<number, number>()
  const computeLayer = (id: number, guard: number): number => {
    const memo = layer.get(id)
    if (memo !== undefined) return memo
    if (guard > goals.length + 1) return 0
    const ps = parents.get(id)
    const l = !ps || ps.length === 0
      ? 0
      : Math.max(...ps.map((p) => computeLayer(p, guard + 1))) + 1
    layer.set(id, l)
    return l
  }
  for (const g of goals) computeLayer(g.id, 0)

  // ---- Tidy-tree x-assignment -------------------------------------
  // The old approach (per-layer index * gap, rows centered globally,
  // weak barycenter) let a parent land half a canvas away from its
  // children — 217-goal graphs became sweeping-edge spaghetti. Instead:
  // build a primary-parent forest (min parent id), assign x bottom-up
  // (leaf = next slot, parent = centered over its children), so
  // families group and edges stay local. Secondary DAG edges remain as
  // the few genuine cross-links. Deterministic throughout.
  const primaryParent = new Map<number, number>()
  for (const [child, ps] of parents) primaryParent.set(child, Math.min(...ps))
  const treeKids = new Map<number, number[]>()
  for (const [c, p] of primaryParent) {
    treeKids.set(p, [...(treeKids.get(p) ?? []), c])
  }
  for (const ks of treeKids.values()) ks.sort((a, b) => a - b)

  const isSingleton = (id: number) =>
    !primaryParent.has(id) && (treeKids.get(id)?.length ?? 0) === 0
  const treeRoots = goals
    .filter((g) => !primaryParent.has(g.id) && (treeKids.get(g.id)?.length ?? 0) > 0)
    .map((g) => g.id)
    .sort((a, b) => a - b)

  const xSlot = new Map<number, number>()
  let slot = 0
  const treeInfos: { members: number[]; start: number; end: number; depth: number }[] = []
  const assign = (id: number, guard: number, members: number[]): void => {
    if (guard > goals.length + 1 || xSlot.has(id)) return
    members.push(id)
    const ks = treeKids.get(id) ?? []
    if (ks.length === 0) {
      xSlot.set(id, slot)
      slot += 1
      return
    }
    for (const k of ks) assign(k, guard + 1, members)
    const first = xSlot.get(ks[0])
    const last = xSlot.get(ks[ks.length - 1])
    xSlot.set(id, first !== undefined && last !== undefined ? (first + last) / 2 : slot++)
  }
  for (const r of treeRoots) {
    const start = slot
    const members: number[] = []
    assign(r, 0, members)
    treeInfos.push({
      members,
      start,
      end: slot - 1,
      depth: Math.max(...members.map((m) => layer.get(m) ?? 0), 0),
    })
    slot += 0.6 // breathing room between families
  }

  // Band the independent families: a 200-goal shallow forest laid out
  // in one strip is a ribbon (aspect 20:1); fold trees into horizontal
  // bands sized for a roughly 16:9 canvas. Trees are independent, so
  // banding costs nothing but the few cross-tree DAG edges.
  const maxDepthAll = Math.max(...treeInfos.map((t) => t.depth), 0)
  const targetBand = Math.max(
    16,
    Math.ceil(Math.sqrt(Math.max(slot, 1) * (maxDepthAll + 2) * (Y_GAP / X_GAP) * 1.7)),
  )
  const bandOfNode = new Map<number, number>()
  const localSlot = new Map<number, number>()
  const bandDepth: number[] = []
  let band = 0
  let bandUsed = 0
  for (const t of treeInfos) {
    const w = t.end - t.start + 1
    if (bandUsed > 0 && bandUsed + w > targetBand) {
      band += 1
      bandUsed = 0
    }
    for (const m of t.members) {
      bandOfNode.set(m, band)
      localSlot.set(m, xSlot.get(m)! - t.start + bandUsed)
    }
    bandDepth[band] = Math.max(bandDepth[band] ?? 0, t.depth)
    bandUsed += w + 0.6
  }

  // Parentless, childless forward bricks: their own compact block band.
  const singles = goals.filter((g) => isSingleton(g.id)).map((g) => g.id)
  if (singles.length > 0) {
    const perRow = Math.max(4, Math.ceil(Math.sqrt(singles.length * 2.6)))
    const sBand = bandUsed > 0 || band > 0 ? band + 1 : band
    singles.forEach((id, i) => {
      bandOfNode.set(id, sBand)
      localSlot.set(id, i % perRow)
      layer.set(id, Math.floor(i / perRow))
    })
    bandDepth[sBand] = Math.max(
      bandDepth[sBand] ?? 0,
      Math.floor((singles.length - 1) / perRow),
    )
  }

  // Vertical base of each band = cumulative depth of the bands above.
  const bandYBase: number[] = []
  {
    let y = 0
    for (let b = 0; b < bandDepth.length; b++) {
      bandYBase[b] = y
      y += (bandDepth[b] ?? 0) + 1.7
    }
  }

  // Per-(band, layer) collision sweep: multi-parent pulls a node deeper
  // than its tree slot suggests; enforce min horizontal gap.
  const rows = new Map<string, number[]>()
  for (const g of goals) {
    const key = `${bandOfNode.get(g.id) ?? 0}:${layer.get(g.id) ?? 0}`
    rows.set(key, [...(rows.get(key) ?? []), g.id])
  }
  const colOf = new Map<number, number>()
  for (const ids of rows.values()) {
    ids.sort((a, b) => (localSlot.get(a)! - localSlot.get(b)!) || a - b)
    let prev = -Infinity
    ids.forEach((id, i) => {
      const x = Math.max(localSlot.get(id)!, prev + 1)
      localSlot.set(id, x)
      prev = x
      colOf.set(id, i)
    })
  }

  const maxSlot = Math.max(...[...localSlot.values()], 0)
  const lastBand = bandDepth.length - 1
  const totalLayers = (bandYBase[lastBand] ?? 0) + (bandDepth[lastBand] ?? 0)
  const width = PAD * 2 + maxSlot * X_GAP
  const height = PAD * 2 + totalLayers * Y_GAP

  const nodes: LayoutNode[] = goals.map((g) => ({
    goal: g,
    x: PAD + (localSlot.get(g.id) ?? 0) * X_GAP,
    y:
      PAD +
      ((bandYBase[bandOfNode.get(g.id) ?? 0] ?? 0) + (layer.get(g.id) ?? 0)) * Y_GAP,
    layer: layer.get(g.id) ?? 0,
    col: colOf.get(g.id) ?? 0,
  }))

  // Hyperedge bundles: group strategy edges by strategy; ≥2 children
  // form an AND-bundle with a junction point, single-child strategies
  // stay plain edges. OR alternatives (several strategies on one goal)
  // get deterministic side-by-side junction offsets, ordered by id.
  const nodePos = new Map(nodes.map((n) => [n.goal.id, n]))
  const byStrategy = new Map<number, LayoutEdge[]>()
  for (const e of edges) {
    if (e.kind !== 'strategy') continue
    byStrategy.set(e.strategyId, [...(byStrategy.get(e.strategyId) ?? []), e])
  }
  const perParent = new Map<number, number[]>() // parent goal → strategy ids (multi-child only)
  for (const [sid, es] of byStrategy) {
    if (es.length < 2) continue
    perParent.set(es[0].from, [...(perParent.get(es[0].from) ?? []), sid])
  }
  for (const sids of perParent.values()) sids.sort((a, b) => a - b)

  const bundles: LayoutBundle[] = []
  const plainEdges: LayoutEdge[] = []
  for (const e of edges) {
    if (e.kind !== 'strategy' || (byStrategy.get(e.strategyId)?.length ?? 0) < 2) {
      plainEdges.push(e)
    }
  }
  for (const [sid, es] of byStrategy) {
    if (es.length < 2) continue
    const parent = nodePos.get(es[0].from)
    const children = es
      .map((e) => nodePos.get(e.to))
      .filter((n): n is LayoutNode => n !== undefined)
    if (!parent || children.length < 2) {
      for (const e of es) plainEdges.push(e)
      continue
    }
    const sibs = perParent.get(es[0].from) ?? [sid]
    const orOffset = (sibs.indexOf(sid) - (sibs.length - 1) / 2) * 18
    const cx = children.reduce((a, n) => a + n.x, 0) / children.length
    const cyMin = Math.min(...children.map((n) => n.y))
    bundles.push({
      strategyId: sid,
      status: es[0].strategyStatus,
      parentId: parent.goal.id,
      junction: {
        x: parent.x + (cx - parent.x) * 0.35 + orOffset,
        y: parent.y + (cyMin - parent.y) * 0.45,
      },
      children: children.map((n) => n.goal.id),
    })
  }
  return { nodes, edges: plainEdges, bundles, width, height }
}
