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
  /** caption anchor for the unlinked forward block */
  singlesBlock: { x: number; y: number; count: number } | null
}

export const X_GAP = 110
export const Y_GAP = 120
const PAD = 60

export function layoutConstellation(
  goals: Goal[],
  strategies: Strategy[],
  strategyEdges: StrategyEdge[],
  anchorEdges: AnchorEdge[] = [],
  citationEdges: CitationEdge[] = [],
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
  // FLIPPED for hierarchy: the top-level claim is the parent and its
  // anchors hang beneath it (the sketch's mental model — claims on
  // top, vocabulary supporting from below).
  const seenPairs = new Set(edges.map((e) => `${e.from}>${e.to}`))
  for (const e of anchorEdges) {
    if (!byId.has(e.from) || !byId.has(e.to)) continue
    if (seenPairs.has(`${e.to}>${e.from}`)) continue
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
      edges.push({
        from: g.id,
        to: g.alias_target_id,
        strategyId: -1,
        strategyStatus: 'succeeded',
        kind: 'alias',
      })
    }
  }
  // Proof-file citations: the DAG's cross-links (a lemma two nodes
  // cite is drawn once, with two lines). Never hierarchy — a heavily
  // cited def would otherwise drag half the sky under itself.
  for (const e of citationEdges) {
    if (!byId.has(e.from) || !byId.has(e.to)) continue
    const k = `${e.from}>${e.to}`
    if (seenPairs.has(k)) continue
    seenPairs.add(k)
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
      items.push({
        kind: 'leaves',
        leaves: leafKs,
        w: perRow,
        d: Math.ceil(leafKs.length / perRow),
        ord: ordIdx.get(leafKs[0]) ?? 0,
      })
    } else {
      for (const k of leafKs) {
        items.push({ kind: 'branch', k, w: 1, d: 1, ord: ordIdx.get(k) ?? 0 })
      }
    }
    // Shelve depth-descending (FFDH — a shelf costs the height of its
    // deepest member, so mixed depths waste rows); ties keep the
    // sibling order (id on pass 1, partner barycenter on pass 2).
    // On a SINGLE shelf the order is free space-wise, so it obeys the
    // LEAN instead: a subtree on its parent's left flank packs its
    // deep spine rightmost (and vice versa), so fork branches run
    // inward — the owner's circled near-horizontal pair was two
    // branches crossing 800px to reach spines hugging the OUTER flanks.
    const totalW = items.reduce((a, it) => a + it.w, 0)
    const ascend = lean === 1 && totalW <= SHELF_CAP
    items.sort((a, b) => (ascend ? a.d - b.d : b.d - a.d) || a.ord - b.ord)
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
    for (const shelf of shelves) {
      slot = start0
      let shelfDepth = 1
      const shelfW = shelf.reduce((a, it) => a + it.w, 0)
      let off = 0
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
  const partner = new Map<number, number[]>()
  const addPartner = (a: number, b: number) => {
    partner.set(a, [...(partner.get(a) ?? []), b])
    partner.set(b, [...(partner.get(b) ?? []), a])
  }
  for (const e of edges) {
    if (e.kind === 'citation' || e.kind === 'alias') addPartner(e.from, e.to)
    else if (primaryParent.get(e.to) !== e.from) addPartner(e.from, e.to)
  }
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
  // Singleton beds: a run of lone stars in one row reads as a
  // clothesline — grid them into compact beds instead. Main-ish ones
  // (detached seeds, bare claims) bed in region 0; citation-linked
  // ones bed in region 1 ordered under their citers.
  const gridComp = (ids: number[]) => {
    if (ids.length === 0) return
    const perRow = Math.max(3, Math.ceil(Math.sqrt(ids.length * 2.2)))
    const start = slot
    ids.forEach((id, i) => {
      xSlot.set(id, start + (i % perRow))
      layer.set(id, Math.floor(i / perRow))
    })
    slot = start + Math.min(ids.length, perRow)
    treeInfos.push({
      members: ids,
      start,
      end: slot - 1,
      depth: Math.floor((ids.length - 1) / perRow),
    })
    slot += 0.6
  }
  const mainSingles = singletonIds.filter(mainish)
  const linkedSingles = singletonIds.filter(
    (id) => !mainish(id) && citPartner.has(id),
  )
  const partnerMean = (id: number) => {
    const xs = (citPartner.get(id) ?? [])
      .map((p) => xSlot.get(p))
      .filter((v): v is number => v !== undefined)
    return xs.length > 0 ? xs.reduce((a, b) => a + b, 0) / xs.length : Infinity
  }
  linkedSingles.sort((a, b) => partnerMean(a) - partnerMean(b) || a - b)
  gridComp(mainSingles)
  gridComp(linkedSingles)
  const unlinkedSingles = singletonIds.filter(
    (id) => !citPartner.has(id) && !mainish(id),
  )

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
    return (
      ra - rb ||
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
  // (residue_thm). Aim ≈16:9: W² = (16/9)·(Y/X)·area.
  const cellArea = treeInfos.reduce(
    (a, t) => a + (t.end - t.start + 1) * (t.depth + 1.7),
    0,
  )
  const targetBand = Math.max(
    16,
    Math.ceil(Math.sqrt(cellArea * (16 / 9) * (Y_GAP / X_GAP))),
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

  // Truly unlinked forward work: a compact grid block, last.
  const singles = unlinkedSingles
  if (singles.length > 0) {
    const perRow = Math.max(4, Math.ceil(Math.sqrt(singles.length * 2.6)))
    const sBand = bandUsed > 0 ? band + 1 : band
    if (horizonBand === null) horizonBand = sBand
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
  for (const ids of rows.values()) {
    ids.sort((a, b) => (localSlot.get(a)! - localSlot.get(b)!) || a - b)
    // Least-squares de-overlap (pool adjacent violators): in u_i =
    // desired_i − i the min-gap-1 constraint reads "nondecreasing", and
    // pooling violating neighbours at their mean is the optimal fit.
    // The old sweep resolved every collision by pushing RIGHT, so a
    // dense row slid off the parents centered above it.
    const blocks: { sum: number; n: number }[] = []
    ids.forEach((id, i) => {
      let b = { sum: localSlot.get(id)! - i, n: 1 }
      while (
        blocks.length > 0 &&
        blocks[blocks.length - 1].sum / blocks[blocks.length - 1].n >=
          b.sum / b.n
      ) {
        const prev = blocks.pop()!
        b = { sum: prev.sum + b.sum, n: prev.n + b.n }
      }
      blocks.push(b)
    })
    let i = 0
    for (const b of blocks) {
      for (let j = 0; j < b.n; j++, i++) {
        localSlot.set(ids[i], b.sum / b.n + i)
        colOf.set(ids[i], i)
      }
    }
  }
  // centering may push a row's left edge past zero — renormalise so the
  // sky still starts at the padding
  let minSlot = 0
  for (const v of localSlot.values()) minSlot = Math.min(minSlot, v)
  if (minSlot < 0) {
    for (const [id, v] of localSlot) localSlot.set(id, v - minSlot)
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
  const singlesBlock =
    singles.length > 0
      ? {
          x: PAD,
          y: PAD + (bandYBase[bandOfNode.get(singles[0]) ?? 0] ?? 0) * Y_GAP,
          count: singles.length,
        }
      : null

  return {
    nodes,
    edges: plainEdges,
    bundles,
    width,
    height,
    bandTops,
    horizonY,
    singlesBlock,
  }
}
