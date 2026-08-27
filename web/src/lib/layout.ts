import type { Goal, Strategy, StrategyEdge } from './types'

/*
 * Constellation layout — a two-region sky (owner's sketch, 2026-07-07):
 *
 *   region 0  what grew from the ROOT, plus anything marked a
 *             top-level claim — the proof's main body
 *   ── horizon ──
 *   region 1  other forward work. Components a CITATION edge ties to
 *             the main sky rise first (they have real structure — a
 *             lemma cited by two nodes is the DAG's true shape, drawn
 *             as cross-links); only the truly unlinked sit apart.
 *
 * Deterministic tidy-tree per component (layering by longest path,
 * children grouped under parents). Positions may change between polls
 * when the structure changes — readability outranks stillness (owner
 * call); the renderer animates the transition so stars keep identity.
 *
 * Graph shape: goal → strategy (a decomposition attempt, an AND-group
 * of subgoals) → subgoal; competing strategies of one goal are the OR
 * fan. Citation/alias edges are cross-links, never hierarchy.
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
  kind: 'strategy' | 'alias' | 'anchor' | 'citation'
}

export interface AnchorEdge {
  from: number
  to: number
}

export interface CitationEdge {
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
  /** y (px) of the top of each band after the first — bands stack
   * independent trees, so a cross-band y comparison means nothing;
   * hairlines make that legible. */
  bandTops: number[]
  /** y (px) of the horizon rule between the root-grown sky and the
   * other forward work; null when everything grew from the root */
  horizonY: number | null
}

export const X_GAP = 110
export const Y_GAP = 120
const PAD = 60

/**
 * Lay the sky out to fit the page it is drawn on.
 *
 * TWO PHASES, and the split is the whole point (owner, 2026-08-27).
 * Measured on the fixtures: everything that decides the plate's SHAPE
 * — the tidy tree, the band packing, the alignment sweeps — costs 2-6
 * ms at 500 stars. The crossing polish that follows costs ~370 ms. The
 * shape is therefore free to search and the polish is not, so the
 * shape is searched and the polish is paid once, at the end, on the
 * shape that won.
 *
 * Why search at all: `targetBand` is derived from cell AREA as though
 * bands packed solid, and FFDH leaves real gaps, so a single pass
 * lands well short of what it aimed at (asking 2.75 returned 1.96 on
 * residue_thm, 1.58 on jordan). Aiming, measuring and re-aiming twice
 * more closes most of that — at a cost of ~12 ms.
 */
export function layoutConstellation(
  goals: Goal[],
  strategies: Strategy[],
  strategyEdges: StrategyEdge[],
  anchorEdges: AnchorEdge[] = [],
  citationEdges: CitationEdge[] = [],
  aspect = 16 / 9,
): ConstellationLayout {
  const shape = (a: number) =>
    packOnce(goals, strategies, strategyEdges, anchorEdges, citationEdges, a, false)
  const miss = (v: ConstellationLayout) => {
    const got = v.width / v.height
    return Number.isFinite(got) && got > 0 ? Math.abs(Math.log(got / aspect)) : Infinity
  }
  let target = aspect
  let bestTarget = aspect
  let bestMiss = Infinity
  // three aims is where the returns stop: a sky whose widest tree is
  // wider than the whole band CANNOT reach the page's ratio, and the
  // loop must land on the best reachable shape rather than chase one
  for (let i = 0; i < 3; i++) {
    const v = shape(target)
    const m = miss(v)
    if (m < bestMiss) {
      bestMiss = m
      bestTarget = target
    }
    const got = v.width / v.height
    if (!Number.isFinite(got) || got <= 0 || m < 0.08) break
    target = Math.min(24, Math.max(0.5, target * (aspect / got)))
  }
  return packOnce(
    goals, strategies, strategyEdges, anchorEdges, citationEdges, bestTarget, true)
}

/**
 * The stars a blink belongs on: work DISPATCHED right now, plus every
 * star it hangs under.
 *
 * `attempting` is NOT that signal (owner, 2026-08-27). It means the
 * goal has been decomposed and is waiting on its subtree — a goal sits
 * `attempting` while nothing at all is happening beneath it. The
 * engine learned this about its own reader as `status-SHALLOW`
 * (putnam_2025_b6 silent idle, 2026-07-09: a produced goal sat
 * `attempting` with every strategy under it dead and nothing queued)
 * and fixed it by recursing; the sky went on reading the bare status.
 * `in_flight` is the honest signal — a queue row leased by the LIVE
 * daemon, which is why it also needs `engineWorking` at the call site.
 *
 * The climb follows the SAME edges that make this picture a tree:
 * minted strategy edges and anchors. A cited lemma is a cross-link —
 * work inside it says nothing about the goals reaching for it, and
 * climbing citations would blink half a sky over one busy lemma. That
 * is `link_kind` again, one axis over, so `agreesWithHierarchy` in the
 * tests holds the two definitions together.
 */
export function liveWorkIds(
  goals: Goal[],
  strategies: Strategy[],
  strategyEdges: StrategyEdge[],
  anchorEdges: AnchorEdge[] = [],
): Set<number> {
  const hot = new Set<number>()
  for (const g of goals) if (g.in_flight) hot.add(g.id)
  if (hot.size === 0) return hot
  const known = new Set(goals.map((g) => g.id))
  const stratById = new Map(strategies.map((s) => [s.id, s]))
  const up = new Map<number, number[]>()
  const link = (child: number, parent: number) => {
    if (child === parent || !known.has(child) || !known.has(parent)) return
    const at = up.get(child)
    if (at) at.push(parent)
    else up.set(child, [parent])
  }
  const claimed = new Set<string>()
  for (const e of strategyEdges) {
    if (e.link_kind === 'cited') continue
    const s = stratById.get(e.strategy_id)
    if (!s) continue
    claimed.add(`${s.goal_id}>${e.subgoal_id}`)
    link(e.subgoal_id, s.goal_id)
  }
  // anchors hang BENEATH the claim they support — layout flips them
  // for hierarchy, so the parent is `to`. Its precedence too: a pair a
  // route already owns keeps the route's direction, and taking the
  // anchor as well would hand the pair a parent EACH way.
  for (const e of anchorEdges) {
    if (claimed.has(`${e.from}>${e.to}`) || claimed.has(`${e.to}>${e.from}`))
      continue
    link(e.from, e.to)
  }
  // `hot` doubles as the visited set, so a cycle cannot spin here
  const stack = [...hot]
  while (stack.length > 0) {
    for (const p of up.get(stack.pop()!) ?? []) {
      if (hot.has(p)) continue
      hot.add(p)
      stack.push(p)
    }
  }
  return hot
}

function packOnce(
  goals: Goal[],
  strategies: Strategy[],
  strategyEdges: StrategyEdge[],
  anchorEdges: AnchorEdge[] = [],
  citationEdges: CitationEdge[] = [],
  /** The plate's target width:height. It used to be a hard-coded 16:9,
   * which is why the sky sat in a fixed-aspect block with dead page on
   * either side of it (owner, 2026-08-27) — the band packer aims at
   * this, so on a wide window it should be told the window's shape.
   * Callers pass a QUANTIZED value: this run costs ~0.5s at 500 stars
   * and must not re-run per pixel of a drag. */
  aspect = 16 / 9,
  refine = true,
): ConstellationLayout {
  const byId = new Map(goals.map((g) => [g.id, g]))
  const stratById = new Map(strategies.map((s) => [s.id, s]))

  const edges: LayoutEdge[] = []
  // A route's REUSE of an existing lemma is not a decomposition branch
  // (v44 `link_kind`): it is exactly the cross-link the citation pass
  // below already knows how to draw, so it waits and goes through
  // there — after hierarchy and aliases have claimed their pairs.
  const reused: { from: number; to: number; sid: number; status: Strategy['status'] }[] = []
  for (const e of strategyEdges) {
    const s = stratById.get(e.strategy_id)
    if (!s || !byId.has(s.goal_id) || !byId.has(e.subgoal_id)) continue
    if (e.link_kind === 'cited') {
      // citation direction, same as a file import: FROM the lemma being
      // reused TO the goal reaching for it, so the focus arrow points
      // where knowledge flows in
      reused.push({ from: e.subgoal_id, to: s.goal_id, sid: s.id, status: s.status })
      continue
    }
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
  // FLIPPED for hierarchy: the top-level claim is the parent and its
  // anchors hang beneath it (the sketch's mental model — claims on
  // top, vocabulary supporting from below).
  // One pair of stars, one line. Precedence follows specificity:
  // hierarchy > alias > citation — an alias pair that also cites reads
  // as ONE dashed identity link, not two parallel curves (bt drew
  // both: the alias loop never registered its pair and the citation
  // dedupe only checked its own direction).
  const seenPairs = new Set(edges.map((e) => `${e.from}>${e.to}`))
  const pairSeen = (a: number, b: number) =>
    seenPairs.has(`${a}>${b}`) || seenPairs.has(`${b}>${a}`)
  for (const e of anchorEdges) {
    if (!byId.has(e.from) || !byId.has(e.to)) continue
    if (pairSeen(e.from, e.to)) continue
    seenPairs.add(`${e.to}>${e.from}`)
    edges.push({
      from: e.to,
      to: e.from,
      strategyId: -2,
      strategyStatus: 'succeeded',
      kind: 'anchor',
    })
  }
  for (const g of goals) {
    if (g.alias_target_id !== null && byId.has(g.alias_target_id)) {
      if (pairSeen(g.id, g.alias_target_id)) continue
      seenPairs.add(`${g.id}>${g.alias_target_id}`)
      edges.push({
        from: g.id,
        to: g.alias_target_id,
        strategyId: -1,
        strategyStatus: 'succeeded',
        kind: 'alias',
      })
    }
  }
  // Cross-links: proof-file citations, and the routes that reuse a
  // lemma rather than mint one (a lemma two nodes reach for is drawn
  // once per reacher). Never hierarchy — a heavily cited def would
  // otherwise drag half the sky under itself, which is precisely what
  // the reuse links were doing before v44's `link_kind` reached here.
  // Reuse keeps its real strategy id: the thread belongs to a route
  // the reader can open, unlike a bare file import (-3).
  for (const e of reused) {
    if (pairSeen(e.from, e.to)) continue
    seenPairs.add(`${e.from}>${e.to}`)
    edges.push({
      from: e.from,
      to: e.to,
      strategyId: e.sid,
      strategyStatus: e.status,
      kind: 'citation',
    })
  }
  for (const e of citationEdges) {
    if (!byId.has(e.from) || !byId.has(e.to)) continue
    if (pairSeen(e.from, e.to)) continue
    seenPairs.add(`${e.from}>${e.to}`)
    edges.push({
      from: e.from,
      to: e.to,
      strategyId: -3,
      strategyStatus: 'succeeded',
      kind: 'citation',
    })
  }

  // Longest-path layering over strategy + anchor edges (alias and
  // citation edges are cross-links, not hierarchy). Cycles can't occur
  // (the engine's circularity gate; anchor closures are kernel-
  // acyclic), but guard with a visit cap anyway.
  const children = new Map<number, number[]>()
  const parents = new Map<number, number[]>()
  for (const e of edges) {
    if (e.kind === 'alias' || e.kind === 'citation') continue
    children.set(e.from, [...(children.get(e.from) ?? []), e.to])
    parents.set(e.to, [...(parents.get(e.to) ?? []), e.from])
  }
  // Deep-chain compression: an unbranching pass-through link (its
  // parent has one child, it has one parent) costs 0.6 rows instead
  // of a full one — a 12-link spine no longer owns 12 rows of sky.
  // Cost-based longest path keeps the invariant that every child
  // still sits strictly below all of its parents.
  const linkCost = (p: number, c: number): number =>
    (children.get(p)?.length ?? 0) === 1 && (parents.get(c)?.length ?? 0) === 1
      ? 0.6
      : 1
  const layer = new Map<number, number>()
  const computeLayer = (id: number, guard: number): number => {
    const memo = layer.get(id)
    if (memo !== undefined) return memo
    if (guard > goals.length + 1) return 0
    const ps = parents.get(id)
    const l = !ps || ps.length === 0
      ? 0
      : Math.max(...ps.map((p) => computeLayer(p, guard + 1) + linkCost(p, id)))
    layer.set(id, l)
    return l
  }
  for (const g of goals) computeLayer(g.id, 0)

  // ---- Tidy-tree x-assignment -------------------------------------
  // The old approach (per-layer index * gap, rows centered globally,
  // weak barycenter) let a parent land half a canvas away from its
  // children — 217-goal graphs became sweeping-edge spaghetti. Instead:
  // build a primary-parent forest, assign x bottom-up (leaf = next
  // slot, parent = centered over its children), so families group and
  // edges stay local. Secondary DAG edges remain as the few genuine
  // cross-links. Deterministic throughout.
  //
  // Primary parent = the DEEPEST parent (ties → min id). A multi-parent
  // node sits one row under its deepest parent, so hanging it THERE
  // makes the tree edge the short vertical one; hanging it under an
  // early shallow parent (the old min-id rule) drew a near-parallel fan
  // of cross-sky diagonals out of every hub (residue's root fan).
  const primaryParent = new Map<number, number>()
  for (const [child, ps] of parents) {
    let best = ps[0]
    for (const p of ps) {
      const lp = layer.get(p) ?? 0
      const lb = layer.get(best) ?? 0
      if (lp > lb || (lp === lb && p < best)) best = p
    }
    primaryParent.set(child, best)
  }
  // Cycle guard: a research-mode relink can wire a strategy's declared
  // sub-goal back to an ancestor (live case 2026-07-19: goals
  // 6370→6375→6380→6370 — three 'proposed' strategies in a ring). In
  // the child→parent map a cycle has no root, so no tree walk ever
  // reaches its members, the bottom-up x pass averages over nothing,
  // and the alignment sweeps smear that NaN across the whole sky (the
  // a5 constellation rendered blank). Cut each cycle at its
  // smallest-id member (deterministic); the severed link re-renders
  // as a secondary cross-link, so the relation stays visible.
  {
    const color = new Map<number, 1 | 2>()
    for (const start of [...primaryParent.keys()]) {
      if (color.has(start)) continue
      const path: number[] = []
      let cur: number | undefined = start
      while (cur !== undefined && !color.has(cur)) {
        color.set(cur, 1)
        path.push(cur)
        cur = primaryParent.get(cur)
      }
      if (cur !== undefined && color.get(cur) === 1) {
        const cycle = path.slice(path.indexOf(cur))
        primaryParent.delete(Math.min(...cycle))
      }
      for (const n of path) color.set(n, 2)
    }
  }
  const treeKids = new Map<number, number[]>()
  for (const [c, p] of primaryParent) {
    treeKids.set(p, [...(treeKids.get(p) ?? []), c])
  }
  for (const ks of treeKids.values()) ks.sort((a, b) => a - b)

  // Child → the strategy of its primary hierarchy edge, kept only when
  // that strategy bundles (≥2 children): these are the junction fans
  // whose arms the shelf order can tangle.
  const stratSize = new Map<number, number>()
  for (const e of edges) {
    if (e.kind !== 'strategy') continue
    stratSize.set(e.strategyId, (stratSize.get(e.strategyId) ?? 0) + 1)
  }
  const stratOfChild = new Map<number, number>()
  for (const e of edges) {
    if (e.kind !== 'strategy') continue
    if (primaryParent.get(e.to) !== e.from) continue
    if ((stratSize.get(e.strategyId) ?? 0) < 2) continue
    const prev = stratOfChild.get(e.to)
    if (prev === undefined || e.strategyId < prev) stratOfChild.set(e.to, e.strategyId)
  }

  const isSingleton = (id: number) =>
    !primaryParent.has(id) && (treeKids.get(id)?.length ?? 0) === 0
  const treeRoots = goals
    .filter((g) => !primaryParent.has(g.id) && (treeKids.get(g.id)?.length ?? 0) > 0)
    .map((g) => g.id)
    .sort((a, b) => a - b)

  const xSlot = new Map<number, number>()
  let slot = 0
  interface Comp {
    members: number[]
    start: number
    end: number
    depth: number
  }
  const treeInfos: Comp[] = []
  // Subtree measurements (leaf-grid semantics included) feed the
  // shelf decision below.
  const subW = new Map<number, number>()
  const subD = new Map<number, number>()
  const measure = (id: number, guard: number): void => {
    if (guard > goals.length + 1 || subW.has(id)) return
    const ks = treeKids.get(id) ?? []
    const leafKs = ks.filter((k) => (treeKids.get(k)?.length ?? 0) === 0)
    const branchKs = ks.filter((k) => (treeKids.get(k)?.length ?? 0) > 0)
    if (ks.length === 0) {
      subW.set(id, 1)
      subD.set(id, 0)
      return
    }
    for (const k of branchKs) measure(k, guard + 1)
    let w = branchKs.reduce((a, k) => a + (subW.get(k) ?? 1), 0)
    let dep = branchKs.reduce((a, k) => Math.max(a, (subD.get(k) ?? 0) + 1), 0)
    if (leafKs.length > 8) {
      const perRow = Math.ceil(Math.sqrt(leafKs.length * 2.2))
      w += perRow
      dep = Math.max(dep, Math.ceil(leafKs.length / perRow))
    } else if (leafKs.length > 0) {
      w += leafKs.length
      dep = Math.max(dep, 1)
    }
    subW.set(id, Math.max(w, 1))
    subD.set(id, dep)
  }

  // Intra-tree shelf wrap: one mega-tree (residue: 189 slots wide,
  // 18 deep) locks the whole sky into a ribbon no band packing can
  // fix. When a node's children exceed the cap, they wrap into
  // shelves stacked beneath it — the tree folds toward a square.
  // ×2.2: trees fill their bounding box at roughly half density, so
  // the ideal-area width underestimates — compensate toward 16:9
  const SHELF_CAP = Math.max(14, Math.ceil(Math.sqrt(goals.length) * 2.2))

  const assign = (
    id: number,
    guard: number,
    members: number[],
    shift: number,
    lean: -1 | 0 | 1,
  ): void => {
    if (guard > goals.length + 1 || xSlot.has(id)) return
    members.push(id)
    layer.set(id, (layer.get(id) ?? 0) + shift)
    const ks = treeKids.get(id) ?? []
    if (ks.length === 0) {
      xSlot.set(id, slot)
      slot += 1
      return
    }
    const leafKs = ks.filter((k) => (treeKids.get(k)?.length ?? 0) === 0)
    const branchKs = ks.filter((k) => (treeKids.get(k)?.length ?? 0) > 0)
    const ordIdx = new Map(ks.map((c, i) => [c, i]))
    // child items: each branch subtree, plus (maybe) one leaf block
    interface Item {
      kind: 'branch' | 'leaves'
      k?: number
      leaves?: number[]
      w: number
      d: number
      ord: number
    }
    const items: Item[] = branchKs.map((k) => ({
      kind: 'branch' as const,
      k,
      w: subW.get(k) ?? 1,
      d: (subD.get(k) ?? 0) + 1,
      ord: ordIdx.get(k) ?? 0,
    }))
    if (leafKs.length > 8) {
      const perRow = Math.ceil(Math.sqrt(leafKs.length * 2.2))
      // inside the grid, leaves of one strategy cluster (row-major):
      // each junction's arms fan toward a compact block, not a stripe
      const gridLeaves = [...leafKs].sort(
        (a, b) =>
          (stratOfChild.get(a) ?? -1) - (stratOfChild.get(b) ?? -1) || a - b,
      )
      items.push({
        kind: 'leaves',
        leaves: gridLeaves,
        w: perRow,
        d: Math.ceil(leafKs.length / perRow),
        ord: ordIdx.get(leafKs[0]) ?? 0,
      })
    } else {
      for (const k of leafKs) {
        items.push({ kind: 'branch', k, w: 1, d: 1, ord: ordIdx.get(k) ?? 0 })
      }
    }
    // Shelve depth-descending when WRAPPING (FFDH — a shelf costs the
    // height of its deepest member). On a SINGLE shelf the order is
    // free space-wise, so it serves geometry instead: the deepest
    // subtree (the spine the parent will follow) sits at the lean end,
    // partner-LESS subtrees pack beside it (their only placement cost
    // is the parent edge — the halfspace chain sat 1800px out for
    // nothing), and partnered subtrees keep their barycenter order.
    const totalW = items.reduce((a, it) => a + it.w, 0)
    if (totalW > SHELF_CAP) {
      items.sort((a, b) => b.d - a.d || a.ord - b.ord)
    } else if (lean === 0) {
      items.sort((a, b) => b.d - a.d || a.ord - b.ord)
    } else {
      let spine = items[0]
      for (const it of items) if (it.d > spine.d) spine = it
      const tier = (it: (typeof items)[number]): number => {
        if (it === spine) return 2
        const anchored =
          it.k !== undefined
            ? hasPartnerDeep(it.k, 0)
            : (it.leaves ?? []).some((l) => partner.has(l))
        return anchored ? 0 : 1
      }
      items.sort((a, b) => {
        const ta = tier(a)
        const tb = tier(b)
        if (ta !== tb) return lean === 1 ? ta - tb : tb - ta
        if (ta === 1) return lean === 1 ? a.d - b.d : b.d - a.d
        return a.ord - b.ord
      })
    }
    const shelves: Item[][] = []
    let cur: Item[] = []
    let curW = 0
    for (const it of items) {
      if (curW > 0 && curW + it.w > SHELF_CAP) {
        shelves.push(cur)
        cur = []
        curW = 0
      }
      cur.push(it)
      curW += it.w
    }
    if (cur.length > 0) shelves.push(cur)

    const start0 = slot
    let maxEnd = slot
    let yOff = 0
    const myLayer = layer.get(id) ?? 0
    const wrapped: { members: number[]; left: number; right: number }[] = []
    for (const shelf of shelves) {
      slot = start0
      let shelfDepth = 1
      const shelfW = shelf.reduce((a, it) => a + it.w, 0)
      let off = 0
      const mStart = members.length
      for (const it of shelf) {
        if (it.kind === 'leaves' && it.leaves) {
          const perRow = it.w
          const gStart = slot
          it.leaves.forEach((k, i) => {
            if (xSlot.has(k)) return
            members.push(k)
            xSlot.set(k, gStart + (i % perRow))
            layer.set(k, myLayer + 1 + yOff + Math.floor(i / perRow))
          })
          slot = gStart + Math.min(it.leaves.length, perRow)
        } else if (it.k !== undefined) {
          // a lone branch is a chain link — it inherits the lean so
          // the whole chain hugs one side; fork children lean toward
          // the fork's centre (left half leans right, right half left)
          const childLean: -1 | 0 | 1 =
            branchKs.length === 1
              ? lean
              : off + it.w / 2 < shelfW / 2
                ? 1
                : -1
          assign(it.k, guard + 1, members, shift + yOff, childLean)
        }
        off += it.w
        shelfDepth = Math.max(shelfDepth, it.d)
      }
      if (yOff > 0) {
        wrapped.push({ members: members.slice(mStart), left: start0, right: slot })
      }
      maxEnd = Math.max(maxEnd, slot)
      yOff += shelfDepth
    }
    slot = maxEnd
    // Parent placement (owner: tree interiors meandered): span-centre
    // let side leaves drag every chain link 0.5+ slots sideways — a
    // staircase. Follow the SPINE when there is exactly one branch
    // child (chains run plumb, leaves hang beside). A LEANING fork
    // follows its INNER branch root instead of the midpoint — the node
    // presents itself on the flank its own parent reaches for, so the
    // parent's bundle branches span the inter-subtree gap instead of
    // overflying both bodies (owner's circled near-horizontal pair).
    // Only a lean-free fork (tree tops) takes the classic symmetric
    // midpoint of its child roots. Row de-overlap guards collisions.
    const placedBranches = branchKs.filter((c) => xSlot.has(c))
    if (placedBranches.length === 1) {
      xSlot.set(id, xSlot.get(placedBranches[0])!)
    } else if (lean !== 0 && placedBranches.length > 1) {
      let best = xSlot.get(placedBranches[0])!
      for (const c of placedBranches) {
        const x = xSlot.get(c)!
        if (lean === 1 ? x > best : x < best) best = x
      }
      xSlot.set(id, best)
    } else {
      let lo = Infinity
      let hi = -Infinity
      for (const c of ks) {
        const x = xSlot.get(c)
        if (x !== undefined) {
          lo = Math.min(lo, x)
          hi = Math.max(hi, x)
        }
      }
      xSlot.set(id, lo <= hi ? (lo + hi) / 2 : (start0 + maxEnd - 1) / 2)
    }
    // Wrapped shelves re-anchor under the PARENT: they start at the
    // subtree's left edge while the parent rides its spine — the
    // halfspace chain sat 1800px from its only parent because its
    // shelf stayed at start0. Rigid shift, clamped inside the span
    // (the span is reserved for this subtree, so no tree-level
    // collisions; the row pass guards the rest).
    {
      const px = xSlot.get(id)!
      for (const sh of wrapped) {
        const centre = (sh.left + sh.right - 1) / 2
        let dx = px - centre
        dx = Math.max(start0 - sh.left, Math.min(dx, maxEnd - sh.right))
        if (dx !== 0) {
          for (const m of sh.members) {
            const x = xSlot.get(m)
            if (x !== undefined) xSlot.set(m, x + dx)
          }
        }
      }
    }
    // Loose leaves hug the parent (owner: needless spans). The shelf
    // packed them at its cursor — a whole subtree away from where the
    // parent just landed (spine/inner-branch following). Re-seat them
    // beside the parent on its free side; the row de-overlap pass
    // keeps neighbours honest. Pure leaf fans (no branch children)
    // already sit under their parent, and >8 leaves live in a grid.
    if (branchKs.length > 0 && leafKs.length > 0 && leafKs.length <= 8) {
      // alternate sides — one-sided hugging cocked the parent's head
      // to the fan's end (owner); the spine child holds the centre
      // slot, leaves flank it symmetrically
      const px = xSlot.get(id)!
      leafKs.forEach((k, i) => {
        const step = Math.floor(i / 2) + 1
        const side = i % 2 === 0 ? 1 : -1
        xSlot.set(k, px + side * step)
      })
    }
  }
  // Cross-link partners (citations, aliases, secondary parents) —
  // needed during assign() too: a subtree with NO partners has exactly
  // one placement cost, its parent edge, so it belongs beside the
  // spine the parent will follow.
  const partner = new Map<number, number[]>()
  const addPartner = (a: number, b: number) => {
    partner.set(a, [...(partner.get(a) ?? []), b])
    partner.set(b, [...(partner.get(b) ?? []), a])
  }
  for (const e of edges) {
    if (e.kind === 'citation' || e.kind === 'alias') addPartner(e.from, e.to)
    else if (primaryParent.get(e.to) !== e.from) {
      // a SECONDARY hierarchy edge is a drawn bright(ish) limb — it
      // pulls three times as hard as a citation whisper, so co-parents
      // of a shared child drift together instead of 4400px apart
      addPartner(e.from, e.to)
      addPartner(e.from, e.to)
      addPartner(e.from, e.to)
      addPartner(e.from, e.to)
      addPartner(e.from, e.to)
    }
  }
  const subtreeHasPartner = new Map<number, boolean>()
  const hasPartnerDeep = (id: number, guard: number): boolean => {
    const memo = subtreeHasPartner.get(id)
    if (memo !== undefined) return memo
    if (guard > goals.length + 1) return false
    let v = partner.has(id)
    if (!v) {
      for (const c of treeKids.get(id) ?? []) {
        if (hasPartnerDeep(c, guard + 1)) {
          v = true
          break
        }
      }
    }
    subtreeHasPartner.set(id, v)
    return v
  }
  for (const r of treeRoots) measure(r, 0)
  const baseLayer = new Map(layer) // assign() adds shelf shifts — snapshot for pass 2
  const runForest = () => {
    slot = 0
    xSlot.clear()
    treeInfos.length = 0
    for (const r of treeRoots) {
      const start = slot
      const members: number[] = []
      assign(r, 0, members, 0, 0)
      treeInfos.push({
        members,
        start,
        end: slot - 1,
        depth: Math.max(...members.map((m) => layer.get(m) ?? 0), 0),
      })
      slot += 0.6 // breathing room between families
    }
  }
  runForest()

  // ---- pass 2: partner-barycenter sibling order ---------------------
  // Cross-links (citations, aliases, secondary parents) are drawn as
  // long threads wherever the id-ordered pass happens to put their
  // endpoints. Re-order equal-depth siblings by the mean pass-1 x of
  // each subtree's partners and lay the forest out again — threads pull
  // toward their far ends. Partner-less subtrees rank by their own
  // pass-1 centre, so they keep their relative order. Deterministic.
  if (partner.size > 0) {
    const collect = (id: number, acc: number[], guard: number): void => {
      if (guard > goals.length + 1) return
      for (const p of partner.get(id) ?? []) {
        const x = xSlot.get(p)
        if (x !== undefined) acc.push(x)
      }
      for (const c of treeKids.get(id) ?? []) collect(c, acc, guard + 1)
    }
    const rank = new Map<number, number>()
    const rankOf = (id: number): number => {
      const acc: number[] = []
      collect(id, acc, 0)
      return acc.length > 0
        ? acc.reduce((a, b) => a + b, 0) / acc.length
        : (xSlot.get(id) ?? 0)
    }
    for (const ks of treeKids.values()) {
      for (const c of ks) rank.set(c, rankOf(c))
      ks.sort((a, b) => (rank.get(a)! - rank.get(b)!) || a - b)
    }
    layer.clear()
    for (const [id, l] of baseLayer) layer.set(id, l)
    runForest()
  }

  // A singleton a citation ties to something is a 1-node component in
  // the normal flow (it HAS structure); only the truly unlinked
  // grid-pack into the final block.
  const citPartner = new Map<number, number[]>()
  for (const e of edges) {
    if (e.kind !== 'citation') continue
    citPartner.set(e.from, [...(citPartner.get(e.from) ?? []), e.to])
    citPartner.set(e.to, [...(citPartner.get(e.to) ?? []), e.from])
  }
  // Main-ness mirrors the engine's alive CTE (root ∪ detached ∪ …):
  // the root, top-level claims, and strategist-injected spines
  // (detached) are the proof's main body even before they connect.
  const mainish = (id: number) => {
    const g = byId.get(id)
    return g !== undefined && (g.origin === 'root' || g.is_deliverable || g.detached)
  }
  const singletonIds = goals.filter((g) => isSingleton(g.id)).map((g) => g.id)
  // Lone stars are NOT bedded. They used to be gridded into blocks —
  // and on union_closed the 698 of them made a rectangle covering 9%
  // of the plate while forcing the plate 23% bigger. Packing the bed
  // tighter only made it worse: the renderer boosts star radius at
  // fit-zoom (`0.78 / kq`, capped at 4x) so stars stay visible when
  // the sky is small on screen, and that boost assumes a full cell, so
  // at half-pitch the discs touched and 698 stars became one solid
  // grey brick (owner: "uglier — worse than scattering them across the
  // sky"). Density and legibility are one axis here, so a bed cannot
  // be shrunk by packing; only by not being a bed. They are scattered
  // into the sky's own gaps instead — `scatterLone`, after the sweeps,
  // once the tree geometry is final.
  // ---- Two-region sky ------------------------------------------------
  // Region 0: components holding the root, a top-level claim, or an
  // injected spine. Region 1 (below the horizon): other forward work —
  // citation-linked components first, ordered under their citers.
  const isMain = (c: Comp) => c.members.some(mainish)
  const memberComp = new Map<number, Comp>()
  for (const c of treeInfos) for (const m of c.members) memberComp.set(m, c)
  const mains = treeInfos.filter(isMain)
  /** mean pass-1 x of a tree's cross-link partners in OTHER trees —
   * fallback = its own centre (keeps the current order) */
  const treePartnerMean = (c: Comp): number => {
    const xs: number[] = []
    for (const m of c.members) {
      for (const p of partner.get(m) ?? []) {
        if (memberComp.get(p) !== c) {
          const x = xSlot.get(p)
          if (x !== undefined) xs.push(x)
        }
      }
    }
    return xs.length > 0
      ? xs.reduce((a, b) => a + b, 0) / xs.length
      : (c.start + c.end) / 2
  }
  // Shelf packing (FFDH): depth-descending order makes each band
  // depth-homogeneous — mixed bands waste the full height of their
  // deepest tree under every shallow one (residue_thm ballooned to a
  // 189-slot ribbon). The root's component still leads the sky; among
  // equal depths, connected trees queue together so the greedy packer
  // tends to drop them into the SAME band.
  mains.sort((a, b) => {
    const ra = a.members.some((id) => byId.get(id)?.origin === 'root') ? 0 : 1
    const rb = b.members.some((id) => byId.get(id)?.origin === 'root') ? 0 : 1
    // claims are the signed surface — their families take the crown
    // rows right under the root (owner), before depth economy speaks
    const ca = a.members.some((id) => byId.get(id)?.is_deliverable) ? 0 : 1
    const cb = b.members.some((id) => byId.get(id)?.is_deliverable) ? 0 : 1
    return (
      ra - rb ||
      ca - cb ||
      b.depth - a.depth ||
      treePartnerMean(a) - treePartnerMean(b) ||
      a.start - b.start
    )
  })
  const mainSet = new Set(mains)
  const rest = treeInfos.filter((c) => !mainSet.has(c))
  const touchesMain = (c: Comp) =>
    c.members.some((id) =>
      (citPartner.get(id) ?? []).some((p) => {
        const pc = memberComp.get(p)
        return pc !== undefined && mainSet.has(pc)
      }),
    )
  const linked = rest.filter(touchesMain)
  const linkedSet = new Set(linked)
  const unlinkedTrees = rest.filter((c) => !linkedSet.has(c))
  const meanPartnerSlot = (c: Comp) => {
    const xs: number[] = []
    for (const id of c.members)
      for (const p of citPartner.get(id) ?? []) {
        const pc = memberComp.get(p)
        if (pc && mainSet.has(pc)) xs.push(xSlot.get(p) ?? 0)
      }
    return xs.length > 0 ? xs.reduce((a, b) => a + b, 0) / xs.length : Infinity
  }
  // depth first (shelf packing), citer position as the tiebreak
  linked.sort(
    (a, b) =>
      b.depth - a.depth ||
      meanPartnerSlot(a) - meanPartnerSlot(b) ||
      a.start - b.start,
  )
  unlinkedTrees.sort((a, b) => b.depth - a.depth || a.start - b.start)

  // ---- Band packing (the region break forces a new band) -------------
  // Band width from ACTUAL cell area, not worst-case depth: a shallow
  // 300-tree forest sized by its one deep tree became a 5:1 ribbon
  // (residue_thm). Aim at `aspect`: W² = aspect·(Y/X)·area.
  const cellArea = treeInfos.reduce(
    (a, t) => a + (t.end - t.start + 1) * (t.depth + 1.7),
    0,
  )
  const targetBand = Math.max(
    16,
    Math.ceil(Math.sqrt(cellArea * aspect * (Y_GAP / X_GAP))),
  )
  const bandOfNode = new Map<number, number>()
  const localSlot = new Map<number, number>()
  const bandDepth: number[] = []
  let band = 0
  let bandUsed = 0
  let horizonBand: number | null = null
  const pack = (list: Comp[]) => {
    for (const t of list) {
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
  }
  pack(mains)
  if (linked.length > 0 || unlinkedTrees.length > 0) {
    if (bandUsed > 0) {
      band += 1
      bandUsed = 0
    }
    horizonBand = band
    pack(linked)
    pack(unlinkedTrees)
  }
  // ---- band composition -----------------------------------------------
  // Band MEMBERSHIP stays FFDH's (depth homogeneity = vertical
  // economy); every horizontal decision inside a band belongs to one
  // optimiser below. Bands share the x-origin, so localSlot compares
  // across bands directly.
  {
    const bandTrees = new Map<number, Comp[]>()
    for (const t of treeInfos) {
      const b = bandOfNode.get(t.members[0])
      if (b === undefined) continue
      bandTrees.set(b, [...(bandTrees.get(b) ?? []), t])
    }
    // ONE optimiser replaces the old slide + justify + centring trio
    // (owner: repeated patching bred edge cases — the three were
    // partial answers to the same question and fought each other:
    // justify tore apart what the slide pulled together). Objective:
    // per band, place rigid trees to minimise Σ(squared tether length)
    // subject to a minimum gap and the plate bounds — which is exactly
    // WEIGHTED interval isotonic regression, the same PAVA law the
    // node rows already obey. Unlinked trees hold their (pre-centred)
    // place at low weight, so a linkless neighbour cannot shove a
    // heavily-linked tree; order follows desired centres. Two sweeps
    // let both ends of a thread move.
    const GAP = 0.6
    const natural = (trees: Comp[]) =>
      trees.reduce((a, t) => a + (t.end - t.start + 1), 0) +
      GAP * (trees.length - 1)
    let targetW = 0
    for (const trees of bandTrees.values()) {
      targetW = Math.max(targetW, natural(trees))
    }
    // pre-centre every band: the no-information default is balance
    for (const trees of bandTrees.values()) {
      let cursor = Math.max(0, (targetW - natural(trees)) / 2)
      for (const t of trees) {
        for (const m of t.members) {
          localSlot.set(m, (xSlot.get(m) ?? 0) - t.start + cursor)
        }
        cursor += t.end - t.start + 1 + GAP
      }
    }
    for (let sweep = 0; sweep < 2; sweep++) {
      for (const trees of bandTrees.values()) {
        if (trees.length === 0) continue
        // desired shift per tree = the mean signed offset of its
        // cross-link partners (the least-squares optimum for a rigid
        // move); weight = link count
        interface Placed {
          t: Comp
          w: number
          desired: number // desired LEFT edge
          wt: number
        }
        const items: Placed[] = trees.map((t) => {
          const w = t.end - t.start + 1
          const m0 = t.members[0]
          const off = (localSlot.get(m0) ?? 0) - ((xSlot.get(m0) ?? 0) - t.start)
          let sum = 0
          let n = 0
          for (const m of t.members) {
            const mx = localSlot.get(m)
            if (mx === undefined) continue
            for (const p of partner.get(m) ?? []) {
              if (memberComp.get(p) === t) continue
              const px = localSlot.get(p)
              if (px !== undefined) {
                sum += px - mx
                n++
              }
            }
          }
          return {
            t,
            w,
            desired: off + (n > 0 ? sum / n : 0),
            wt: n > 0 ? n : 0.25,
          }
        })
        // order by desired CENTRE — comparing left edges biased wide
        // trees leftward and stranded stubs on the wrong side of the
        // tree they feed (owner: "swap those two and the crossings go")
        items.sort(
          (a, b) =>
            a.desired + a.w / 2 - (b.desired + b.w / 2) || a.t.start - b.t.start,
        )
        // weighted PAVA in gap-cumulated space (u = left − prefix)
        let prefix = 0
        const u: number[] = []
        for (const it of items) {
          u.push(it.desired - prefix)
          prefix += it.w + GAP
        }
        const blocks: { sum: number; wt: number; n: number }[] = []
        items.forEach((it, i) => {
          let b = { sum: u[i] * it.wt, wt: it.wt, n: 1 }
          while (
            blocks.length > 0 &&
            blocks[blocks.length - 1].sum / blocks[blocks.length - 1].wt >=
              b.sum / b.wt
          ) {
            const prev = blocks.pop()!
            b = { sum: prev.sum + b.sum, wt: prev.wt + b.wt, n: prev.n + b.n }
          }
          blocks.push(b)
        })
        const lefts: number[] = []
        {
          let i = 0
          let acc = 0
          for (const b of blocks) {
            const base = b.sum / b.wt
            for (let j = 0; j < b.n; j++, i++) {
              lefts.push(base + acc)
              acc += items[i].w + GAP
            }
          }
        }
        // project into the plate: two clamp passes preserve order+gaps
        for (let i = 0; i < items.length; i++) {
          const lo = i === 0 ? 0 : lefts[i - 1] + items[i - 1].w + GAP
          lefts[i] = Math.max(lefts[i], lo)
        }
        for (let i = items.length - 1; i >= 0; i--) {
          const hi =
            i === items.length - 1
              ? targetW - items[i].w
              : lefts[i + 1] - GAP - items[i].w
          lefts[i] = Math.min(lefts[i], hi)
        }
        items.forEach((it, i) => {
          for (const m of it.t.members) {
            localSlot.set(m, (xSlot.get(m) ?? 0) - it.t.start + lefts[i])
          }
        })
      }
    }

    // ---- vertical adjacency: connected bands become neighbours -------
    // Band ORDER was pure depth bookkeeping, so how many rows a
    // cross-band edge spans was luck. Re-order bands (within their
    // region — the root's band stays first, the horizon still splits
    // the regions) by the mean position of the bands they link to; a
    // band every tree depends on rises to sit beside its dependents.
    {
      const nBands = bandDepth.length
      const hb = horizonBand ?? nBands
      const links = new Map<number, number[]>()
      for (const t of treeInfos) {
        const b = bandOfNode.get(t.members[0])
        if (b === undefined) continue
        for (const m of t.members) {
          for (const p of partner.get(m) ?? []) {
            const c = bandOfNode.get(p)
            if (c !== undefined && c !== b) {
              links.set(b, [...(links.get(b) ?? []), c])
            }
          }
        }
      }
      const mainsB: number[] = []
      const belowB: number[] = []
      for (let b = 0; b < nBands; b++) (b < hb ? mainsB : belowB).push(b)
      const posOf = new Map<number, number>()
      const refresh = () => {
        let i = 0
        for (const b of mainsB) posOf.set(b, i++)
        for (const b of belowB) posOf.set(b, i++)
      }
      refresh()
      for (let sweep = 0; sweep < 2; sweep++) {
        const sc = new Map<number, number>()
        for (let b = 0; b < nBands; b++) {
          const ls = links.get(b)
          sc.set(
            b,
            ls && ls.length > 0
              ? ls.reduce((a, c) => a + posOf.get(c)!, 0) / ls.length
              : posOf.get(b)!,
          )
        }
        mainsB.sort((a, b) => {
          const sa = a === 0 ? -1 : sc.get(a)!
          const sb = b === 0 ? -1 : sc.get(b)!
          return sa - sb || a - b
        })
        belowB.sort((a, b) => sc.get(a)! - sc.get(b)! || a - b)
        refresh()
      }
      let identity = true
      for (let b = 0; b < nBands; b++) {
        if (posOf.get(b) !== b) {
          identity = false
          break
        }
      }
      if (!identity) {
        for (const [id, b] of bandOfNode) bandOfNode.set(id, posOf.get(b) ?? b)
        const newDepth: number[] = []
        for (let b = 0; b < nBands; b++) newDepth[posOf.get(b)!] = bandDepth[b]
        bandDepth.length = 0
        bandDepth.push(...newDepth)
      }
    }
  }

  // Vertical base of each band = cumulative depth of the bands above;
  // the horizon band gets extra air so the rule reads as a boundary.
  const bandYBase: number[] = []
  {
    let y = 0
    for (let b = 0; b < bandDepth.length; b++) {
      if (horizonBand !== null && b === horizonBand) y += 0.6
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
  // weighted least-squares de-overlap (pool adjacent violators): in
  // u_i = desired_i − i the min-gap-1 constraint reads "nondecreasing",
  // and pooling violating neighbours at their WEIGHTED mean is the
  // optimal fit. The old sweep resolved every collision by pushing
  // RIGHT, so a dense row slid off the parents centered above it.
  const solveRow = (
    ids: number[],
    desired: (id: number) => number,
    weight: (id: number) => number,
  ): void => {
    ids.sort((a, b) => (localSlot.get(a)! - localSlot.get(b)!) || a - b)
    const blocks: { sum: number; w: number; n: number }[] = []
    ids.forEach((id, i) => {
      const wi = weight(id)
      let b = { sum: (desired(id) - i) * wi, w: wi, n: 1 }
      while (
        blocks.length > 0 &&
        blocks[blocks.length - 1].sum / blocks[blocks.length - 1].w >=
          b.sum / b.w
      ) {
        const prev = blocks.pop()!
        b = { sum: prev.sum + b.sum, w: prev.w + b.w, n: prev.n + b.n }
      }
      blocks.push(b)
    })
    let i = 0
    for (const b of blocks) {
      for (let j = 0; j < b.n; j++, i++) {
        localSlot.set(ids[i], b.sum / b.w + i)
        colOf.set(ids[i], i)
      }
    }
  }
  // snapshot the DESIGNED geometry before the crowd starts shoving:
  // assign/pass-2/band-optimiser moves are rigid or deliberate, so the
  // relative offsets here are the intended family shapes
  const designSlot = new Map(localSlot)
  // A lone star sits the sweeps out: they exist to align a node with
  // its parent and its children, and it has neither — the only thing
  // the unit de-overlap would do to a bed is push it back to full
  // pitch, undoing the packing above.
  const loneSet = new Set(singletonIds)
  for (const ids of rows.values()) {
    solveRow(ids.filter((id) => !loneSet.has(id)), (id) => localSlot.get(id)!, () => 1)
  }
  // ---- alignment sweeps (owner: optimise the ARRANGEMENT, not the
  // aftermath). The one-shot de-overlap displaces each row's nodes by
  // whatever its own crowd demands, so a chain zigzags and a small
  // tree tilts off its parent. Classic Sugiyama coordinate refinement:
  // alternate down/up sweeps where a node's desire is its PRIMARY
  // parent's slot (down) or its children's spine/mean (up), each row
  // re-solved by the same weighted isotonic law — order within a row
  // NEVER changes (crossing decisions stay), families just compress
  // toward alignment where the crowd allows. Target-less nodes tether
  // to their current slot at low weight so the band optimiser's
  // placement is respected, not re-litigated.
  {
    const rowsOrdered = [...rows.entries()]
      .map(([k, ids]) => {
        const [b, l] = k.split(':').map(Number)
        return { y: (bandYBase[b] ?? 0) + l, ids: ids.filter((id) => !loneSet.has(id)) }
      })
      .filter((r) => r.ids.length > 0)
      .sort((a, b) => a.y - b.y)
    const TETHER = 0.15
    // desire = follow the relative offset the ARRANGEMENT designed,
    // from where the relative anchor actually IS now. Collapsing
    // children onto the parent's x (v1 of this sweep) destroyed the
    // designed fan spreads and bb exploded 3-20x — the sweep's job is
    // translating families back into their designed SHAPE, never
    // reshaping them.
    const off = (id: number, other: number): number =>
      (designSlot.get(id) ?? 0) - (designSlot.get(other) ?? 0)
    const downDesire = (id: number): { d: number; w: number } => {
      const p = primaryParent.get(id)
      if (p !== undefined && localSlot.has(p)) {
        return { d: localSlot.get(p)! + off(id, p), w: 1 }
      }
      return { d: localSlot.get(id)!, w: TETHER }
    }
    const upDesire = (id: number): { d: number; w: number } => {
      const ks = (treeKids.get(id) ?? []).filter((c) => localSlot.has(c))
      if (ks.length === 0) return { d: localSlot.get(id)!, w: TETHER }
      let sum = 0
      for (const c of ks) sum += localSlot.get(c)! + off(id, c)
      return { d: sum / ks.length, w: 1 }
    }
    // the band composition (justify, sun-band centring, vertical
    // adjacency) is a COMPOSITION decision the sweeps must not
    // re-litigate: a root sitting off-centre would otherwise drag its
    // whole cascade sideways and beach the sky against one edge
    // (jordan lost its right half to exactly this — the metric can't
    // see spatial balance, only the eye caught it). Snapshot each
    // band's span centre, sweep, then translate every band rigidly
    // back onto its own centre.
    const bandCenter = (): Map<number, number> => {
      const lo = new Map<number, number>()
      const hi = new Map<number, number>()
      for (const g of goals) {
        const b = bandOfNode.get(g.id) ?? 0
        const x = localSlot.get(g.id)
        if (x === undefined) continue
        lo.set(b, Math.min(lo.get(b) ?? Infinity, x))
        hi.set(b, Math.max(hi.get(b) ?? -Infinity, x))
      }
      const c = new Map<number, number>()
      for (const [b, l] of lo) c.set(b, (l + hi.get(b)!) / 2)
      return c
    }
    const preCenters = bandCenter()
    for (const dir of ['down', 'up', 'down'] as const) {
      const seq = dir === 'down' ? rowsOrdered : [...rowsOrdered].reverse()
      const desire = dir === 'down' ? downDesire : upDesire
      for (const { ids } of seq) {
        solveRow(
          ids,
          (id) => desire(id).d,
          (id) => desire(id).w,
        )
      }
    }
    const postCenters = bandCenter()
    for (const g of goals) {
      const b = bandOfNode.get(g.id) ?? 0
      const pre = preCenters.get(b)
      const post = postCenters.get(b)
      const x = localSlot.get(g.id)
      if (pre === undefined || post === undefined || x === undefined) continue
      localSlot.set(g.id, x + pre - post)
    }
  }
  // centering may push a row's left edge past zero — renormalise so the
  // sky still starts at the padding
  let minSlot = 0
  for (const v of localSlot.values()) minSlot = Math.min(minSlot, v)
  if (minSlot < 0) {
    for (const [id, v] of localSlot) localSlot.set(id, v - minSlot)
  }

  // ---- lone stars: scattered into the sky's own emptiness ------------
  // A star no route reaches used to be bedded in a grid — 698 of them
  // on union_closed made a rectangle covering 9% of the plate and
  // forced the plate 23% bigger. Packing the bed tighter only made it
  // a solid brick (the renderer boosts star radius at fit-zoom, so
  // density and legibility are one axis). The bed itself was the
  // error: a lone star needs a POSITION, not a neighbourhood, and the
  // sky is already full of gaps — measured on that same sky, 2880
  // cells stand empty with a one-cell moat around every tree, against
  // 698 stars to place. So they go in the gaps, the bed disappears,
  // and the plate does not grow by a single slot.
  //
  // Deterministic: candidate cells are ordered by a fixed hash, and
  // the stars by id. A cited lone star prefers a gap near its citer;
  // the rest spread evenly through the scrambled order.
  {
    const lone = singletonIds.filter((id) => localSlot.get(id) === undefined)
    if (lone.length > 0) {
      const held = new Set<string>()
      const key = (b: number, l: number, x: number) => `${b}:${l}:${x}`
      for (const [id, v] of localSlot) {
        const b = bandOfNode.get(id) ?? 0
        held.add(key(b, Math.round(layer.get(id) ?? 0), Math.round(v)))
      }
      let treeMax = 0
      for (const v of localSlot.values()) treeMax = Math.max(treeMax, v)
      const wide = Math.max(4, Math.ceil(treeMax))
      const overWide = Math.max(
        wide,
        Math.ceil(Math.sqrt(lone.length * aspect * (Y_GAP / X_GAP))),
      )
      const free: { b: number; l: number; x: number; h: number }[] = []
      for (let b = 0; b < bandDepth.length; b++) {
        for (let l = 0; l <= Math.round(bandDepth[b] ?? 0); l++) {
          for (let x = 0; x <= wide; x++) {
            if (held.has(key(b, l, x))) continue
            let near = false
            for (let dl = -1; dl <= 1 && !near; dl++)
              for (let dx = -1; dx <= 1 && !near; dx++)
                if (held.has(key(b, l + dl, x + dx))) near = true
            if (near) continue
            // a cheap fixed scramble so the field reads as sky rather
            // than as rows filling left to right
            const h = ((b * 73856093) ^ (l * 19349663) ^ (x * 83492791)) >>> 0
            free.push({ b, l, x, h })
          }
        }
      }
      free.sort((a, b2) => a.h - b2.h || a.b - b2.b || a.l - b2.l || a.x - b2.x)
      const order = [...lone].sort((a, b2) => a - b2)
      // a cited lone star is not really alone: seat it in the nearest
      // free gap to whoever cites it, and let the rest take the
      // scrambled order
      const taken = new Set<number>()
      const nearestFor = (id: number): number => {
        const xs = (citPartner.get(id) ?? [])
          .map((q) => localSlot.get(q))
          .filter((v): v is number => v !== undefined)
        if (xs.length === 0) return -1
        const want = xs.reduce((m, v) => m + v, 0) / xs.length
        let bestIdx = -1
        let bestD = Infinity
        for (let k = 0; k < free.length; k++) {
          if (taken.has(k)) continue
          const d = Math.abs(free[k].x - want)
          if (d < bestD) {
            bestD = d
            bestIdx = k
          }
          if (bestD === 0) break
        }
        return bestIdx
      }
      let i = 0
      for (const id of order) {
        const pick = nearestFor(id)
        if (pick >= 0) {
          taken.add(pick)
          const c = free[pick]
          bandOfNode.set(id, c.b)
          layer.set(id, c.l)
          localSlot.set(id, c.x)
          continue
        }
        while (i < free.length && taken.has(i)) i++
        if (i < free.length) {
          const c = free[i++]
          bandOfNode.set(id, c.b)
          layer.set(id, c.l)
          localSlot.set(id, c.x)
        } else {
          // More lone stars than gaps — a small sky, mostly. The
          // overflow gets fresh rows UNDER the sky at full pitch, as
          // wide as the page wants rather than as wide as the trees
          // happen to be: a four-node tree would otherwise dictate a
          // five-column column of stars.
          const over = i - free.length
          i++
          const b = bandDepth.length
          bandOfNode.set(id, b)
          layer.set(id, Math.floor(over / overWide))
          localSlot.set(id, over % overWide)
          bandDepth[b] = Math.max(bandDepth[b] ?? 0, Math.floor(over / overWide))
          // bandYBase was settled before this pass; a band invented
          // here needs its own base or the overflow lands back on top
          // of band 0 (which is exactly what it did)
          if (bandYBase[b] === undefined) {
            const prev = b - 1
            bandYBase[b] =
              (bandYBase[prev] ?? 0) + (bandDepth[prev] ?? 0) + 1.7
          }
        }
      }
    }
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

  // ---- crossing-driven refinement -----------------------------------
  // Everything above optimises a PROXY (tether length, barycenter,
  // contiguity) and the proxies fight at the margins: enforcing
  // junction contiguity blindly traded 4 same-parent crossings for 28
  // cross-tree ones on residue. So the final pass optimises the real
  // objective — the weighted crossing count the sky is judged by
  // (bright×bright 1, bright×faint 0.2, faint×faint 0.05), the same
  // law as scripts/sky-crossings.mjs.
  // Bounded discrete moves on the final geometry — mirror a tree, swap
  // two band-adjacent trees — accepted only on strict improvement,
  // evaluated incrementally (only segments touching moved nodes are
  // retested). Deterministic: fixed proposal order, exact arithmetic.
  if (refine && goals.length <= 600) {
    const px = new Map<number, number>()
    const pyOf = new Map<number, number>()
    for (const n of nodes) {
      px.set(n.goal.id, n.x)
      pyOf.set(n.goal.id, n.y)
    }
    // bundle groups (≥2 children); OR offsets are recomputed from the
    // CURRENT geometry on every evaluation — the engine's junction law
    // must be byte-identical to the builder's, or accepted moves stop
    // being improvements once the real bundles are built
    interface EngineGroup {
      sid: number
      parent: number
      children: number[]
    }
    const groups: EngineGroup[] = []
    const groupsByParent = new Map<number, EngineGroup[]>()
    {
      const byStrat = new Map<number, LayoutEdge[]>()
      for (const e of edges) {
        if (e.kind !== 'strategy') continue
        byStrat.set(e.strategyId, [...(byStrat.get(e.strategyId) ?? []), e])
      }
      for (const [sid, es] of [...byStrat].sort((a, b) => a[0] - b[0])) {
        if (es.length < 2) continue
        const children = es.map((e) => e.to).filter((c) => px.has(c))
        if (children.length < 2 || !px.has(es[0].from)) continue
        const g: EngineGroup = { sid, parent: es[0].from, children }
        groups.push(g)
        groupsByParent.set(g.parent, [...(groupsByParent.get(g.parent) ?? []), g])
      }
    }
    interface Seg {
      x1: number
      y1: number
      x2: number
      y2: number
      bxLo: number
      bxHi: number
      byLo: number
      byHi: number
      bright: boolean
      cite: boolean
      mark: number
      len: number // excess bright length (px beyond the allowance)
      grp?: EngineGroup
      end?: number // arm child / stem parent, junction is the other end
    }
    const segs: Seg[] = []
    const byDep = new Map<number, Seg[]>()
    const dep = (id: number, s: Seg) => byDep.set(id, [...(byDep.get(id) ?? []), s])
    const finish = (s: Seg): void => {
      s.bxLo = Math.min(s.x1, s.x2)
      s.bxHi = Math.max(s.x1, s.x2)
      s.byLo = Math.min(s.y1, s.y2)
      s.byHi = Math.max(s.y1, s.y2)
      const span = Math.hypot(s.x2 - s.x1, s.y2 - s.y1)
      s.bright = !s.cite && span <= 480
      // unnecessary length is a co-objective (owner, 2026-07-09):
      // bright structural rope beyond a 150px allowance costs weight —
      // 500px of excess ≈ one bright crossing, so length breaks ties
      // and kills long hauls but never outbids a bb fix
      s.len = s.bright ? Math.max(0, span - 150) / 500 : 0
    }
    const junctionOf = (g: EngineGroup): { x: number; y: number } => {
      const pxx = px.get(g.parent)!
      const pyy = pyOf.get(g.parent)!
      const meanCx = (gg: EngineGroup): number =>
        gg.children.reduce((a, c) => a + px.get(c)!, 0) / gg.children.length
      const cx = meanCx(g)
      const cyMin = Math.min(...g.children.map((c) => pyOf.get(c)!))
      const sibs = groupsByParent.get(g.parent) ?? [g]
      let orOff = 0
      if (sibs.length > 1) {
        const ranked = [...sibs].sort((a, b) => meanCx(a) - meanCx(b) || a.sid - b.sid)
        orOff = (ranked.indexOf(g) - (sibs.length - 1) / 2) * 18
      }
      return { x: pxx + (cx - pxx) * 0.35 + orOff, y: pyy + (cyMin - pyy) * 0.45 }
    }
    const reSeg = (s: Seg): void => {
      if (s.grp !== undefined) {
        const j = junctionOf(s.grp)
        const other = s.end!
        s.x1 = j.x
        s.y1 = j.y
        s.x2 = px.get(other)!
        s.y2 = pyOf.get(other)!
      }
      finish(s)
    }
    const bundled = new Set<number>()
    for (const g of groups) {
      const gSegs: Seg[] = [{
        x1: 0, y1: 0,
        x2: px.get(g.parent)!, y2: pyOf.get(g.parent)!,
        bxLo: 0, bxHi: 0, byLo: 0, byHi: 0,
        bright: false, cite: false, mark: 0, len: 0, grp: g, end: g.parent,
      }]
      for (const c of g.children) {
        gSegs.push({
          x1: 0, y1: 0,
          x2: px.get(c)!, y2: pyOf.get(c)!,
          bxLo: 0, bxHi: 0, byLo: 0, byHi: 0,
          bright: false, cite: false, mark: 0, len: 0, grp: g, end: c,
        })
      }
      if (gSegs.length === 0) continue
      segs.push(...gSegs)
      // every group seg moves when ANY sibling group's member moves —
      // the OR rank (and so the junction) is a function of them all
      const depIds = new Set<number>([g.parent])
      for (const sib of groupsByParent.get(g.parent) ?? [g]) {
        for (const c of sib.children) depIds.add(c)
      }
      for (const id of depIds) for (const s of gSegs) dep(id, s)
    }
    // strategy edges that belong to a bundle are drawn as arms, not
    // plain edges — mirror the builder's split
    {
      const cnt = new Map<number, number>()
      for (const e of edges) {
        if (e.kind === 'strategy') cnt.set(e.strategyId, (cnt.get(e.strategyId) ?? 0) + 1)
      }
      for (const e of edges) {
        if (e.kind === 'strategy' && (cnt.get(e.strategyId) ?? 0) >= 2) bundled.add(e.strategyId)
      }
    }
    for (const e of edges) {
      if (e.kind === 'strategy' && bundled.has(e.strategyId)) continue
      const a = px.get(e.from)
      const b = px.get(e.to)
      if (a === undefined || b === undefined) continue
      const s: Seg = {
        x1: a, y1: pyOf.get(e.from)!,
        x2: b, y2: pyOf.get(e.to)!,
        bxLo: 0, bxHi: 0, byLo: 0, byHi: 0,
        bright: false, cite: e.kind === 'citation', mark: 0, len: 0,
      }
      finish(s)
      segs.push(s)
      dep(e.from, s)
      dep(e.to, s)
    }
    for (const s of segs) if (s.grp !== undefined) reSeg(s)
    // plain segs need endpoint refresh on move too
    const plainEnds = new Map<Seg, [number, number]>()
    for (const [id, list] of byDep) {
      for (const s of list) {
        if (s.grp !== undefined) continue
        const ends = plainEnds.get(s) ?? ([-1, -1] as [number, number])
        if (ends[0] === -1) ends[0] = id
        else if (ends[0] !== id && ends[1] === -1) ends[1] = id
        plainEnds.set(s, ends)
      }
    }
    const refresh = (s: Seg): void => {
      if (s.grp !== undefined) {
        reSeg(s)
        return
      }
      const ends = plainEnds.get(s)
      if (!ends) return
      s.x1 = px.get(ends[0])!
      s.y1 = pyOf.get(ends[0])!
      if (ends[1] !== -1) {
        s.x2 = px.get(ends[1])!
        s.y2 = pyOf.get(ends[1])!
      }
      finish(s)
    }
    const inter = (s: Seg, t: Seg): boolean => {
      const dd = (ax: number, ay: number, bx: number, by: number, cx: number, cy: number) =>
        (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
      const eq = (x1: number, y1: number, x2: number, y2: number) =>
        Math.abs(x1 - x2) < 1e-6 && Math.abs(y1 - y2) < 1e-6
      if (
        eq(s.x1, s.y1, t.x1, t.y1) ||
        eq(s.x1, s.y1, t.x2, t.y2) ||
        eq(s.x2, s.y2, t.x1, t.y1) ||
        eq(s.x2, s.y2, t.x2, t.y2)
      ) {
        return false
      }
      const d1 = dd(t.x1, t.y1, t.x2, t.y2, s.x1, s.y1)
      const d2 = dd(t.x1, t.y1, t.x2, t.y2, s.x2, s.y2)
      const d3 = dd(s.x1, s.y1, s.x2, s.y2, t.x1, t.y1)
      const d4 = dd(s.x1, s.y1, s.x2, s.y2, t.x2, t.y2)
      return (
        ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
        ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
      )
    }
    const pairW = (s: Seg, t: Seg): number => {
      if (s.bxHi < t.bxLo || t.bxHi < s.bxLo || s.byHi < t.byLo || t.byHi < s.byLo) return 0
      if (!inter(s, t)) return 0
      // SOLID x SOLID only (owner, 2026-08-27). The old ruler charged
      // 0.2 for bright x faint and 0.05 for faint x faint, and on a
      // real sky those two buckets ARE the score — stokes measured
      // bb 1, bf 287, ff 1681, so 99% of what the engine optimised was
      // crossings involving a citation arc. Those arcs became DOTTED
      // (`CITE_DASH`), and the eye now separates them by texture, not
      // by position: the ruler was measuring a problem the ink had
      // already solved. What dashes do NOT disambiguate is one solid
      // route crossing another, which is what is left here.
      return s.bright && t.bright ? 1 : 0
    }
    const affectedOf = (ids: number[]): Seg[] => {
      const set = new Set<Seg>()
      for (const id of ids) for (const s of byDep.get(id) ?? []) set.add(s)
      return [...set]
    }
    let markGen = 0
    // three-component objective, LEXICOGRAPHIC: bright-bright count
    // first (the owner's "bb never grows" is the engine's OWN law, not
    // just the metric script's verdict — a scalar let +1 bb be bought
    // with -6 bf), weighted crossings second, length third (a single
    // scalar traded stokes bb 3->6 for length in calibration).
    interface W3 {
      bb: number
      c: number
      l: number
    }
    const better = (a: W3, b: W3): boolean =>
      a.bb < b.bb - 1e-9 ||
      (Math.abs(a.bb - b.bb) < 1e-9 &&
        (a.c < b.c - 1e-9 ||
          (Math.abs(a.c - b.c) < 1e-9 && a.l < b.l - 1e-9)))
    const localW = (aff: Seg[]): W3 => {
      markGen += 1
      for (const s of aff) s.mark = markGen
      let bb = 0
      let c = 0
      let l = 0
      const add = (w: number): void => {
        c += w
        if (w === 1) bb += 1
      }
      for (let i = 0; i < aff.length; i++) {
        const s = aff[i]
        l += s.len // per-segment additive — incremental for free
        for (let j = i + 1; j < aff.length; j++) add(pairW(s, aff[j]))
        for (const t of segs) {
          if (t.mark !== markGen) add(pairW(s, t))
        }
      }
      return { bb, c, l }
    }
    // a move = new xs for a set of nodes; accept iff strictly better.
    // Brightness guard: a move may not push a structural segment past
    // the fade threshold — dimming an edge "wins" crossing weight but
    // loses the structure it was drawn for (structure outranks the
    // count, owner), and without the guard the optimiser learns to
    // hide its problems in the faint layer.
    let modern = true
    // plate bounds: the band-composition layer projects every tree
    // into [0, targetW], but the engine had NO such law — a tree
    // FLUNG off the plate meets fewer segments, crossings drop, and
    // the move is "an improvement" (jordan lost a tree to x=-3208
    // exactly this way; same cheat class the brightness ratchet
    // exists for: hiding the problem outside the frame)
    const plateLo = PAD - 1e-6
    const plateHi = width - PAD + 1e-6
    // occupancy law: same-row stars keep half a slot of air. The
    // pass-level disjointness tests see only the mover's own family —
    // a leaf hugged inside a branch's span or a foreign tree's node
    // on the same row is invisible to them, and the objective doesn't
    // punish overlap, so a crossing-improving block permutation
    // stacked residue stars pairwise at gap 0 (invisible goals,
    // 2026-07-09). Same cheat class as the plate flight: a law in
    // tryMove, not a term in the metric.
    const OCC_GAP = X_GAP / 2
    const rowMates = new Map<number, number[]>()
    for (const id of px.keys()) {
      const y = pyOf.get(id)
      if (y === undefined) continue
      rowMates.set(y, [...(rowMates.get(y) ?? []), id])
    }
    const occupancyOk = (moves: [number, number][]): boolean => {
      const newX = new Map(moves)
      for (const [id, x] of moves) {
        const cur = px.get(id)
        if (cur !== undefined && Math.abs(cur - x) < 1e-9) continue
        const y = pyOf.get(id)
        if (y === undefined) continue
        for (const o of rowMates.get(y) ?? []) {
          if (o === id) continue
          const ox = newX.get(o) ?? px.get(o)
          if (ox !== undefined && Math.abs(ox - x) < OCC_GAP) return false
        }
      }
      return true
    }
    const tryMove = (moves: [number, number][]): boolean => {
      for (const [, x] of moves) {
        if (x < plateLo || x > plateHi) return false
      }
      if (!occupancyOk(moves)) return false
      const ids = moves.map(([id]) => id)
      const aff = affectedOf(ids)
      const before = localW(aff)
      const wasBright = aff.map((s) => s.bright)
      const prev = moves.map(([id]) => [id, px.get(id)!] as [number, number])
      for (const [id, x] of moves) px.set(id, x)
      for (const s of aff) refresh(s)
      let dimmed = false
      for (let i = 0; i < aff.length; i++) {
        if (wasBright[i] && !aff[i].bright) {
          dimmed = true
          break
        }
      }
      if (!dimmed) {
        const after = localW(aff)
        // legacy mode is BYTE-faithful to the pre-length engine (c
        // only): greedy is path-dependent, so the old recipe stays in
        // the schedule portfolio as the no-regression floor
        const ok = modern ? better(after, before) : after.c < before.c - 1e-9
        if (ok) return true
      }
      for (const [id, x] of prev) px.set(id, x)
      for (const s of aff) refresh(s)
      return false
    }
    // sibling blocks: a parent's child subtrees, each a rigid x-block.
    // Only pairwise-disjoint blocks (= shelf-mates) may permute; a
    // wrapped shelf or leaf grid overlaps in x and stays fixed.
    // Grouping key = the engine's OWN bundle groups (what is actually
    // drawn), not the hierarchy-derived proxy — a child hanging by an
    // anchor edge still belongs to the strategy fan that draws its arm.
    const sidOfChild = new Map<number, Map<number, number>>()
    for (const g of groups) {
      let m = sidOfChild.get(g.parent)
      if (!m) {
        m = new Map()
        sidOfChild.set(g.parent, m)
      }
      for (const c of g.children) {
        const prev = m.get(c)
        if (prev === undefined || g.sid < prev) m.set(c, g.sid)
      }
    }
    const subMembers = new Map<number, number[]>()
    const membersOf = (k: number): number[] => {
      const memo = subMembers.get(k)
      if (memo) return memo
      const acc: number[] = []
      const stack = [k]
      while (stack.length > 0) {
        const id = stack.pop()!
        if (acc.length > goals.length) break
        acc.push(id)
        for (const c of treeKids.get(id) ?? []) stack.push(c)
      }
      subMembers.set(k, acc)
      return acc
    }
    interface Block {
      k: number
      grp: number
      lo: number
      hi: number
    }
    // maximal runs of consecutive pairwise-disjoint blocks: an
    // all-or-nothing disjointness test skipped exactly the parents
    // that needed help (a leaf hugged inside a branch's span voided
    // the whole family). Within a run, rigid permutation stays sound —
    // nothing else lives between run members.
    const blocksOf = (p: number): Block[][] => {
      const ks = (treeKids.get(p) ?? []).filter((k) => px.has(k))
      if (ks.length < 2) return []
      const blocks: Block[] = []
      for (const k of ks) {
        let lo = Infinity
        let hi = -Infinity
        for (const m of membersOf(k)) {
          const x = px.get(m)
          if (x === undefined) continue
          lo = Math.min(lo, x)
          hi = Math.max(hi, x)
        }
        if (!isFinite(lo)) continue
        blocks.push({ k, grp: sidOfChild.get(p)?.get(k) ?? -(k + 2), lo, hi })
      }
      blocks.sort((a, b) => a.lo - b.lo)
      // a block touched by ANY overlap is immovable (running max-hi
      // catches a long block swallowing a non-adjacent later one)
      const poisoned = new Set<number>()
      let maxHi = -Infinity
      let maxIdx = -1
      for (let i = 0; i < blocks.length; i++) {
        if (blocks[i].lo <= maxHi) {
          poisoned.add(i)
          poisoned.add(maxIdx)
        }
        if (blocks[i].hi > maxHi) {
          maxHi = blocks[i].hi
          maxIdx = i
        }
      }
      const runs: Block[][] = []
      let run: Block[] = []
      for (let i = 0; i < blocks.length; i++) {
        if (poisoned.has(i)) {
          if (run.length >= 2) runs.push(run)
          run = []
          continue
        }
        run.push(blocks[i])
      }
      if (run.length >= 2) runs.push(run)
      return runs
    }
    // lay blocks into the same span in a new order: widths ride along,
    // the original gap sequence stays
    const arrangeMoves = (blocks: Block[], order: Block[]): [number, number][] => {
      const gaps: number[] = []
      for (let i = 0; i + 1 < blocks.length; i++) gaps.push(blocks[i + 1].lo - blocks[i].hi)
      const moves: [number, number][] = []
      let cursor = blocks[0].lo
      order.forEach((b, i) => {
        const d = cursor - b.lo
        if (Math.abs(d) > 1e-9) {
          for (const m of membersOf(b.k)) {
            const x = px.get(m)
            if (x !== undefined) moves.push([m, x + d])
          }
        }
        cursor += b.hi - b.lo + (i < gaps.length ? gaps[i] : 0)
      })
      return moves
    }
    const runPass = (run: Block[]): void => {
      // (a) compound proposal: same-strategy blocks contiguous, groups
      // ordered by mean x — the jump adjacent swaps can't make
      const byGrp = new Map<number, Block[]>()
      for (const b of run) byGrp.set(b.grp, [...(byGrp.get(b.grp) ?? []), b])
      if (byGrp.size < run.length) {
        const gMean = (bs: Block[]): number =>
          bs.reduce((a, b) => a + (b.lo + b.hi) / 2, 0) / bs.length
        const grouped = [...byGrp.values()]
          .sort((a, b) => gMean(a) - gMean(b))
          .flat()
        const same = grouped.every((b, i) => b === run[i])
        if (!same && tryMove(arrangeMoves(run, grouped))) {
          run.length = 0
          run.push(...grouped)
          // extents moved: refresh from px
          for (const b of run) {
            let lo = Infinity
            let hi = -Infinity
            for (const m of membersOf(b.k)) {
              const x = px.get(m)
              if (x === undefined) continue
              lo = Math.min(lo, x)
              hi = Math.max(hi, x)
            }
            b.lo = lo
            b.hi = hi
          }
        }
      }
      // (b) adjacent block swaps, one bubble sweep
      for (let i = 0; i + 1 < run.length; i++) {
        const order = [...run]
        const t = order[i]
        order[i] = order[i + 1]
        order[i + 1] = t
        if (tryMove(arrangeMoves(run, order))) {
          const shifted = order.map((b) => {
            let lo = Infinity
            let hi = -Infinity
            for (const m of membersOf(b.k)) {
              const x = px.get(m)
              if (x === undefined) continue
              lo = Math.min(lo, x)
              hi = Math.max(hi, x)
            }
            return { ...b, lo, hi }
          })
          run.length = 0
          run.push(...shifted)
        }
      }
      // (c) mirror a child block in place
      for (const b of run) {
        if (b.hi - b.lo < 1e-9) continue
        const moves: [number, number][] = []
        for (const m of membersOf(b.k)) {
          const x = px.get(m)
          if (x !== undefined) moves.push([m, b.lo + b.hi - x])
        }
        tryMove(moves)
      }
    }
    const siblingPass = (): void => {
      const parentsWithKids = [...treeKids.keys()].sort((a, b) => a - b)
      for (const p of parentsWithKids) {
        for (const run of blocksOf(p)) runPass(run)
        // leaf-row moves: leaves of one parent on one row are
        // interchangeable slots — no disjointness precondition (the
        // hug tucks them INSIDE a branch's span, which is exactly why
        // block moves can't reach them). Compound regroup by strategy,
        // then adjacent swaps.
        const leaves = (treeKids.get(p) ?? []).filter(
          (k) => (treeKids.get(k)?.length ?? 0) === 0 && px.has(k),
        )
        if (leaves.length < 2) continue
        const byRow = new Map<number, number[]>()
        for (const k of leaves) {
          const y = pyOf.get(k)!
          byRow.set(y, [...(byRow.get(y) ?? []), k])
        }
        for (const row of byRow.values()) {
          if (row.length < 2) continue
          row.sort((a, b) => px.get(a)! - px.get(b)!)
          const slots = row.map((k) => px.get(k)!)
          const grpOf = (k: number): number => sidOfChild.get(p)?.get(k) ?? -(k + 2)
          // (a) regroup: leaves ordered by (group mean x, x) onto slots
          const gs = new Map<number, number[]>()
          for (const k of row) gs.set(grpOf(k), [...(gs.get(grpOf(k)) ?? []), k])
          if (gs.size < row.length) {
            const gMean = (ks: number[]): number =>
              ks.reduce((a, k) => a + px.get(k)!, 0) / ks.length
            const target = [...gs.values()]
              .sort((a, b) => gMean(a) - gMean(b))
              .flat()
            if (!target.every((k, i) => k === row[i])) {
              if (tryMove(target.map((k, i) => [k, slots[i]]))) {
                row.length = 0
                row.push(...target)
              }
            }
          }
          // (b) adjacent leaf swaps
          for (let i = 0; i + 1 < row.length; i++) {
            const a = row[i]
            const b = row[i + 1]
            if (
              tryMove([
                [a, px.get(b)!],
                [b, px.get(a)!],
              ])
            ) {
              row[i] = b
              row[i + 1] = a
            }
          }
        }
      }
    }
    // row-level leaf pass: leaves of DIFFERENT parents sharing a row
    // are interchangeable slots too — a dense row's de-overlap sweep
    // strands leaves seven slots from their parent (residue: primary
    // arms 455px long crossing three trees). Reassigning slots across
    // parents pulls each fan back together; the brightness guard keeps
    // a leaf from being traded past the fade line.
    const rowPass = (): void => {
      const rows2 = new Map<number, number[]>()
      for (const g of goals) {
        if ((treeKids.get(g.id)?.length ?? 0) > 0) continue
        if (!primaryParent.has(g.id)) continue
        if (!px.has(g.id) || (byDep.get(g.id)?.length ?? 0) === 0) continue
        const y = pyOf.get(g.id)!
        rows2.set(y, [...(rows2.get(y) ?? []), g.id])
      }
      for (const row of rows2.values()) {
        if (row.length < 2 || row.length > 80) continue
        row.sort((a, b) => px.get(a)! - px.get(b)!)
        // compound: same-parent leaves contiguous, families ordered by
        // their current mean x
        const slots = row.map((k) => px.get(k)!)
        const fams = new Map<number, number[]>()
        for (const k of row) {
          const p = primaryParent.get(k)!
          fams.set(p, [...(fams.get(p) ?? []), k])
        }
        if (fams.size < row.length) {
          const fMean = (ks: number[]): number =>
            ks.reduce((a, k) => a + px.get(k)!, 0) / ks.length
          const target = [...fams.values()]
            .sort((a, b) => fMean(a) - fMean(b))
            .flat()
          if (!target.every((k, i) => k === row[i])) {
            if (tryMove(target.map((k, i) => [k, slots[i]]))) {
              row.length = 0
              row.push(...target)
            }
          }
        }
        // adjacent swaps across the whole row
        for (let i = 0; i + 1 < row.length; i++) {
          const a = row[i]
          const b = row[i + 1]
          if (primaryParent.get(a) === primaryParent.get(b)) continue
          if (
            tryMove([
              [a, px.get(b)!],
              [b, px.get(a)!],
            ])
          ) {
            row[i] = b
            row[i + 1] = a
          }
        }
      }
    }
    // long-haul rescue: a node stranded far from where its bright ink
    // pulls (an arm spanning three families, a 430px cross-fan haul)
    // is both a length offender and a crossing farm — adjacent swaps
    // never reach it because the destination is slots away. Compute
    // each row-node's PULL (mean x of its bright segments' far ends),
    // and for the badly displaced, try swapping with the row members
    // nearest the pull point. Bounded: ≤3 candidates per node, rows
    // reused from the row pass discipline (same-y = interchangeable).
    const rescuePass = (): void => {
      const rows3 = new Map<number, number[]>()
      for (const n of nodes) {
        if (!px.has(n.goal.id)) continue
        if ((byDep.get(n.goal.id)?.length ?? 0) === 0) continue
        if ((treeKids.get(n.goal.id)?.length ?? 0) > 0) continue // leaves only: rigid subtrees stay whole
        const y = pyOf.get(n.goal.id)!
        rows3.set(y, [...(rows3.get(y) ?? []), n.goal.id])
      }
      for (const row of rows3.values()) {
        if (row.length < 2 || row.length > 80) continue
        for (const k of row) {
          const x = px.get(k)!
          const y = pyOf.get(k)!
          let pull = 0
          let m = 0
          for (const s of byDep.get(k) ?? []) {
            if (!s.bright) continue
            // the far end = whichever endpoint is not this node's
            const farX = Math.abs(s.x1 - x) < 1e-6 && Math.abs(s.y1 - y) < 1e-6 ? s.x2 : s.x1
            pull += farX
            m += 1
          }
          if (m === 0) continue
          pull /= m
          if (Math.abs(x - pull) < 250) continue
          const cands = row
            .filter((o) => o !== k)
            .sort((a, b) => Math.abs(px.get(a)! - pull) - Math.abs(px.get(b)! - pull))
            .slice(0, 3)
          for (const o of cands) {
            if (
              tryMove([
                [k, px.get(o)!],
                [o, px.get(k)!],
              ])
            ) {
              break
            }
          }
        }
      }
    }
    // fan untangle: two strategies of ONE parent whose fans interleave
    // (a child of A standing on B's side and vice versa) — the
    // junction is a DERIVED function of the children's positions, so
    // no single-fan move can uncross them; the fix is exchanging the
    // two children. Cheap pre-filter (the swap must shorten both
    // children's distance to their own junction in sum); tryMove's
    // lexicographic objective is still the judge, and junctions
    // recompute through the group dependency wiring.
    const fanUntangle = (): void => {
      const dbg = (globalThis as { __skyDbg?: Record<string, number> }).__skyDbg
      for (const [, gs] of [...groupsByParent].sort((a, b) => a[0] - b[0])) {
        if (gs.length < 2) continue
        if (dbg) dbg.parents = (dbg.parents ?? 0) + 1
        for (let i = 0; i < gs.length; i++) {
          for (let j = i + 1; j < gs.length; j++) {
            const A = gs[i]
            const B = gs[j]
            for (const a of A.children) {
              if ((treeKids.get(a)?.length ?? 0) > 0) continue
              for (const b of B.children) {
                if (a === b) continue
                if ((treeKids.get(b)?.length ?? 0) > 0) continue
                if (dbg) dbg.pairs = (dbg.pairs ?? 0) + 1
                if (pyOf.get(a) !== pyOf.get(b)) continue
                if (dbg) dbg.sameRow = (dbg.sameRow ?? 0) + 1
                // no distance pre-filter: the junction CHASES its
                // children (it is their mean), so static distance
                // arithmetic self-defeats — the objective is the only
                // honest judge, and same-row cross-fan pairs are few
                const xa = px.get(a)!
                const xb = px.get(b)!
                if (
                  tryMove([
                    [a, xb],
                    [b, xa],
                  ])
                ) {
                  if (dbg) dbg.accepted = (dbg.accepted ?? 0) + 1
                }
              }
            }
          }
        }
      }
    }
    // row order pass: the residue autopsy's dominant remaining shape
    // is same-row children whose SLOT order disagrees with their
    // attachment points' x order — pairwise swaps get vetoed (the
    // junction chases its children, side crossings appear), a local
    // optimum. The classic fact: for straight fans onto fixed
    // attachment points, the non-crossing assignment is the ORDER-
    // PRESERVING one. So per row, reassign the interchangeable leaves
    // onto their own slot multiset sorted by attachment x — ONE
    // compound proposal per row, judged whole by the objective.
    const rowOrderPass = (): void => {
      const rows4 = new Map<number, number[]>()
      for (const n of nodes) {
        const id = n.goal.id
        if (!px.has(id)) continue
        if ((treeKids.get(id)?.length ?? 0) > 0) continue
        if ((byDep.get(id)?.length ?? 0) === 0) continue
        const y = pyOf.get(id)!
        rows4.set(y, [...(rows4.get(y) ?? []), id])
      }
      for (const row of rows4.values()) {
        if (row.length < 2 || row.length > 80) continue
        row.sort((a, b) => px.get(a)! - px.get(b)!)
        const slots = row.map((k) => px.get(k)!)
        const attach = (k: number): number => {
          const x = px.get(k)!
          const y = pyOf.get(k)!
          let pull = 0
          let m = 0
          for (const s of byDep.get(k) ?? []) {
            const farX =
              Math.abs(s.x1 - x) < 1e-6 && Math.abs(s.y1 - y) < 1e-6 ? s.x2 : s.x1
            pull += farX
            m += 1
          }
          return m > 0 ? pull / m : x
        }
        const target = [...row].sort((a, b) => attach(a) - attach(b) || px.get(a)! - px.get(b)!)
        if (!target.every((k, i) => k === row[i])) {
          tryMove(target.map((k, i) => [k, slots[i]] as [number, number]))
        }
        // second proposal: FAN CONTIGUITY — group the row by its
        // strategy fan (parent, min sid), fans ordered by junction x,
        // members by attachment inside. Blind contiguity enforcement
        // was falsified once (-4 bought +28 cross-tree); as a JUDGED
        // proposal the objective simply rejects it where that happens.
        const fanKey = (k: number): number => {
          const p = primaryParent.get(k)
          if (p === undefined) return -(k + 2)
          const sid = sidOfChild.get(p)?.get(k)
          return sid === undefined ? -(k + 2) : p * 100000 + sid
        }
        const fans = new Map<number, number[]>()
        for (const k of row) fans.set(fanKey(k), [...(fans.get(fanKey(k)) ?? []), k])
        if (fans.size < row.length) {
          const fMean = (ks: number[]): number =>
            ks.reduce((a, k) => a + attach(k), 0) / ks.length
          const target2 = [...fans.values()]
            .sort((a, b) => fMean(a) - fMean(b))
            .map((ks) => [...ks].sort((a, b) => attach(a) - attach(b) || px.get(a)! - px.get(b)!))
            .flat()
          const cur = [...row].sort((a, b) => px.get(a)! - px.get(b)!)
          if (!target2.every((k, i) => k === cur[i])) {
            tryMove(target2.map((k, i) => [k, slots[i]] as [number, number]))
          }
        }
      }
    }
    // chain straighten: a spine node with ONE continuing subtree child
    // plus side leaves sits at the tidy MIDPOINT of its children — as
    // the leaves alternate sides the midpoints alternate too, and the
    // spine renders as a staircase (owner circled one wandering 871px
    // over six links). No existing move touches internal nodes at all,
    // which is why the staircase survived every pass. Propose sliding
    // the parent onto its spine child's x (or the child under the
    // parent), occupancy-guarded so stars never stack, judged whole —
    // the length term rewards the straightening, crossings veto abuse.
    const rowXs = (): Map<number, number[]> => {
      const m = new Map<number, number[]>()
      for (const n of nodes) {
        if (!px.has(n.goal.id)) continue
        const y = pyOf.get(n.goal.id)!
        m.set(y, [...(m.get(y) ?? []), n.goal.id])
      }
      return m
    }
    const chainStraighten = (): void => {
      const dbg = (globalThis as { __skyDbg?: Record<string, number> }).__skyDbg
      const bump = (key: string): void => {
        if (dbg) dbg[key] = (dbg[key] ?? 0) + 1
      }
      const rows = rowXs()
      const occupied = (y: number, x: number, exclude: Set<number>): boolean => {
        for (const o of rows.get(y) ?? []) {
          if (!exclude.has(o) && Math.abs(px.get(o)! - x) < 60) return true
        }
        return false
      }
      // this is the first move family that mints NEW x positions (all
      // others exchange existing slots), so EVERY moved member needs
      // an occupancy check — stars must never stack
      const clearForAll = (moves: [number, number][]): boolean => {
        const moving = new Set(moves.map(([id]) => id))
        for (const [id, x] of moves) {
          if (occupied(pyOf.get(id)!, x, moving)) return false
        }
        return true
      }
      for (const n of nodes) {
        const k = n.goal.id
        const ks = (treeKids.get(k) ?? []).filter((c) => px.has(c))
        if (ks.length === 0) continue
        const spines = ks.filter((c) => (treeKids.get(c)?.length ?? 0) > 0)
        if (spines.length !== 1) continue
        const c = spines[0]
        const xk = px.get(k)!
        const xc = px.get(c)!
        if (Math.abs(xk - xc) < 20) continue
        bump('chainCand')
        // parent slides over the spine child — WITH its side leaves
        // (they are what dragged it off the spine; left behind, their
        // longer arms make the honest judge veto the straightening)
        const d0 = xc - xk
        const pMove: [number, number][] = [[k, xc]]
        for (const leaf of ks) {
          if (leaf === c) continue
          if ((treeKids.get(leaf)?.length ?? 0) > 0) continue
          const lx = px.get(leaf)
          if (lx !== undefined) pMove.push([leaf, lx + d0])
        }
        if (clearForAll(pMove)) {
          bump('chainPClear')
          if (tryMove(pMove)) {
            bump('chainPAcc')
            continue
          }
        } else if (clearForAll([[k, xc]]) && tryMove([[k, xc]])) {
          // leaves blocked: the bare slide still gets its day in court
          bump('chainPAcc')
          continue
        }
        const d = xk - xc
        const cMoves: [number, number][] = []
        for (const m of membersOf(c)) {
          const x = px.get(m)
          if (x !== undefined) cMoves.push([m, x + d])
        }
        if (clearForAll(cMoves)) {
          bump('chainCClear')
          if (tryMove(cMoves)) bump('chainCAcc')
        }
      }
    }
    // proposal set: per band, left-to-right adjacent tree swaps, then a
    // mirror per tree; two sweeps let a swap unlock a mirror and back
    const compsByBand = new Map<number, Comp[]>()
    for (const t of treeInfos) {
      const b = bandOfNode.get(t.members[0])
      if (b === undefined) continue
      compsByBand.set(b, [...(compsByBand.get(b) ?? []), t])
    }
    const extent = (t: Comp): [number, number] => {
      let lo = Infinity
      let hi = -Infinity
      for (const m of t.members) {
        const x = px.get(m)
        if (x === undefined) continue
        lo = Math.min(lo, x)
        hi = Math.max(hi, x)
      }
      return [lo, hi]
    }
    const treePass = (): void => {
      for (const [, comps] of [...compsByBand].sort((a, b) => a[0] - b[0])) {
        comps.sort((a, b) => extent(a)[0] - extent(b)[0])
        for (let i = 0; i + 1 < comps.length; i++) {
          const [aLo, aHi] = extent(comps[i])
          const [bLo, bHi] = extent(comps[i + 1])
          if (!isFinite(aLo) || !isFinite(bLo)) continue
          const gap = bLo - aHi
          const dB = aLo - bLo
          const dA = bHi - bLo + gap
          const moves: [number, number][] = []
          for (const m of comps[i].members) {
            const x = px.get(m)
            if (x !== undefined) moves.push([m, x + dA])
          }
          for (const m of comps[i + 1].members) {
            const x = px.get(m)
            if (x !== undefined) moves.push([m, x + dB])
          }
          if (tryMove(moves)) {
            const t = comps[i]
            comps[i] = comps[i + 1]
            comps[i + 1] = t
          }
        }
        for (const t of comps) {
          if (t.members.length < 2) continue
          const [lo, hi] = extent(t)
          if (!isFinite(lo)) continue
          const moves: [number, number][] = []
          for (const m of t.members) {
            const x = px.get(m)
            if (x !== undefined) moves.push([m, lo + hi - x])
          }
          tryMove(moves)
        }
      }
    }
    // Greedy is path-dependent and neither schedule dominates (coarse
    // first won stokes/residue, fine first won sphere/green): run BOTH
    // from the same seed and keep whichever final sky scores better on
    // the full objective. Deterministic, and the schedule choice stops
    // being a tuning knob.
    const totalW = (): W3 => {
      let bb = 0
      let c = 0
      let l = 0
      for (let i = 0; i < segs.length; i++) {
        l += segs[i].len
        for (let j = i + 1; j < segs.length; j++) {
          const w = pairW(segs[i], segs[j])
          c += w
          if (w === 1) bb += 1
        }
      }
      return { bb, c, l }
    }
    const seed = new Map(px)
    const restore = (state: Map<number, number>): void => {
      for (const [id, x] of state) px.set(id, x)
      for (const s of segs) refresh(s)
    }
    let best: Map<number, number> | null = null
    let bestW: W3 = { bb: Infinity, c: Infinity, l: Infinity }
    // schedule PORTFOLIO: {coarse-first, fine-first} × {modern, legacy}.
    // Modern = bb-first lexicographic acceptance + length tie-breaks +
    // the long-haul rescue pass; legacy = the pre-length engine
    // verbatim. Greedy is path-dependent — modern found residue
    // bb 22→21 but wandered stokes 3→4 — so the old recipe stays in
    // the pool as a mechanical no-regression floor, and the final
    // (bb, c, len) lexicographic pick keeps whichever sky is best.
    for (const [coarse, modernMode] of [
      [true, true],
      [false, true],
      [true, false],
      [false, false],
    ] as [boolean, boolean][]) {
      restore(seed)
      modern = modernMode
      // two sweeps: the third buys ~2 crossings on residue for +65%
      // engine time — the layout runs on every data refresh, so the
      // main thread wins that trade
      const tap = (name: string): void => {
        const dbg = (globalThis as { __skyDbg?: Record<string, number> }).__skyDbg
        if (!dbg) return
        let lo = Infinity
        for (const v of px.values()) lo = Math.min(lo, v)
        const key = `min:${name}`
        if (dbg[key] === undefined || lo < dbg[key]) dbg[key] = Math.round(lo)
      }
      for (let sweep = 0; sweep < 2; sweep++) {
        if (coarse) {
          treePass()
          tap('tree')
          siblingPass()
          tap('sibling')
        } else {
          siblingPass()
          tap('sibling')
          treePass()
          tap('tree')
        }
        rowPass()
        tap('row')
        if (modernMode) {
          rowOrderPass()
          tap('rowOrder')
          chainStraighten()
          tap('chain')
          rescuePass()
          tap('rescue')
          fanUntangle()
          tap('fan')
        }
      }
      const w = totalW()
      if (better(w, bestW)) {
        bestW = w
        best = new Map(px)
      }
    }
    if (best) restore(best)
    for (const n of nodes) n.x = px.get(n.goal.id) ?? n.x
  }

  // Hyperedge bundles: group strategy edges by strategy; ≥2 children
  // form an AND-bundle with a junction point, single-child strategies
  // stay plain edges. OR alternatives (several strategies on one goal)
  // get deterministic side-by-side junction offsets — ordered by their
  // children's mean x (id order let sibling junctions sit on the wrong
  // sides and their branches crossed for no reason).
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
  const stratMeanX = (sid: number): number => {
    let s = 0
    let n = 0
    for (const e of byStrategy.get(sid) ?? []) {
      const p = nodePos.get(e.to)
      if (p) {
        s += p.x
        n++
      }
    }
    return n > 0 ? s / n : 0
  }
  for (const sids of perParent.values()) {
    sids.sort((a, b) => stratMeanX(a) - stratMeanX(b) || a - b)
  }

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
  const bandTops: number[] = []
  for (let b = 1; b < bandDepth.length; b++) {
    if (b === horizonBand) continue // the horizon rule replaces this hairline
    bandTops.push(PAD + ((bandYBase[b] ?? 0) - 0.85) * Y_GAP)
  }
  const horizonY =
    horizonBand !== null && horizonBand < bandDepth.length
      ? PAD + ((bandYBase[horizonBand] ?? 0) - 0.95) * Y_GAP
      : null

  return {
    nodes,
    edges: plainEdges,
    bundles,
    width,
    height,
    bandTops,
    horizonY,
  }
}
