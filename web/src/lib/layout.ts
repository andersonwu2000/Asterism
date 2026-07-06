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
  kind: 'strategy' | 'alias'
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

  // Longest-path layering over strategy edges only (alias edges are
  // cross-links, not hierarchy). Cycles can't occur (the engine's
  // circularity gate), but guard with a visit cap anyway.
  const children = new Map<number, number[]>()
  const parents = new Map<number, number[]>()
  for (const e of edges) {
    if (e.kind !== 'strategy') continue
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

  // Group per layer, initial order by goal id (creation order).
  const layers = new Map<number, number[]>()
  for (const g of goals) {
    const l = layer.get(g.id) ?? 0
    layers.set(l, [...(layers.get(l) ?? []), g.id])
  }
  const layerKeys = [...layers.keys()].sort((a, b) => a - b)
  for (const k of layerKeys) layers.get(k)!.sort((a, b) => a - b)

  // Barycenter ordering: 3 top-down passes using parent positions.
  const pos = new Map<number, number>()
  const reindex = (ids: number[]) => ids.forEach((id, i) => pos.set(id, i))
  for (const k of layerKeys) reindex(layers.get(k)!)
  for (let pass = 0; pass < 3; pass++) {
    for (const k of layerKeys) {
      if (k === 0) continue
      const ids = layers.get(k)!
      ids.sort((a, b) => {
        const bary = (id: number): number => {
          const ps = parents.get(id)
          if (!ps || ps.length === 0) return pos.get(id) ?? 0
          return ps.reduce((acc, p) => acc + (pos.get(p) ?? 0), 0) / ps.length
        }
        return bary(a) - bary(b) || a - b
      })
      reindex(ids)
    }
  }

  // Edge-free graphs (all-forward problems) degenerate into one long
  // row; wrap them into a roughly 16:9 grid so the canvas fills
  // instead of rendering a single line in a void.
  if (layerKeys.length === 1 && (layers.get(0)?.length ?? 0) > 6) {
    const ids = layers.get(0)!
    const perRow = Math.max(3, Math.ceil(Math.sqrt(ids.length * 1.8)))
    layers.clear()
    layerKeys.length = 0
    ids.forEach((id, i) => {
      const row = Math.floor(i / perRow)
      if (!layers.has(row)) {
        layers.set(row, [])
        layerKeys.push(row)
      }
      layers.get(row)!.push(id)
    })
  }

  // Coordinates: layers stacked top-down, rows centered on the widest.
  const maxCount = Math.max(...layerKeys.map((k) => layers.get(k)!.length), 1)
  const width = PAD * 2 + Math.max(0, maxCount - 1) * X_GAP
  const nodes: LayoutNode[] = []
  for (const k of layerKeys) {
    const ids = layers.get(k)!
    const rowWidth = Math.max(0, ids.length - 1) * X_GAP
    const x0 = PAD + (width - PAD * 2 - rowWidth) / 2
    ids.forEach((id, i) => {
      nodes.push({
        goal: byId.get(id)!,
        x: x0 + i * X_GAP,
        y: PAD + k * Y_GAP,
        layer: k,
        col: i,
      })
    })
  }
  const height = PAD * 2 + Math.max(0, layerKeys.length - 1) * Y_GAP

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
