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

export interface ConstellationLayout {
  nodes: LayoutNode[]
  edges: LayoutEdge[]
  width: number
  height: number
}

export const X_GAP = 110
export const Y_GAP = 120
const PAD = 60

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
  return { nodes, edges, width, height }
}
