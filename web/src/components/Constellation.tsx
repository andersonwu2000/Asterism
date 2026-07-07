import { useEffect, useMemo, useRef, useState } from 'react'
import type { Goal, Strategy, StrategyEdge } from '../lib/types'
import { frontierView, layoutConstellation, X_GAP } from '../lib/layout'
import { goalStatusLabel } from '../lib/vocab'
import type { LayoutNode } from '../lib/layout'

/*
 * The constellation view (charter §3.3 + appendix): goals as stars in a
 * layered DAG. Far = pure dots, near = slugs, hover = statement popover,
 * click = side-panel drill-down handled by the parent. Layout is
 * deterministic — nodes never move between polls.
 */

interface Props {
  goals: Goal[]
  strategies: Strategy[]
  strategyEdges: StrategyEdge[]
  anchorEdges?: { from: number; to: number }[]
  selectedId: number | null
  onSelect: (id: number | null) => void
  /** junction click → strategy drill-down (optional) */
  onSelectStrategy?: (id: number) => void
  /** attempts heat-ring denominator (engine's shelve threshold) */
  shelveThreshold?: number
  /** proof-file import citations — the DAG's cross-links */
  citationEdges?: { from: number; to: number }[]
  /** liveness gate: pulses are claims that work is happening NOW —
   * without a live daemon on this problem they must not render */
  engineWorking?: boolean
}

/** Residual struggle heat: a proved star that burned failed attempts
 * keeps a warm cast — "where the machine fought" stays on the map for
 * the reviewer hunting fragile spots. */
function provedFill(dead: number): string {
  if (dead <= 0) return 'var(--color-starlight)'
  // achromatic struggle residue: fought-over stars are duller, not warm
  const dull = dead <= 2 ? 22 : dead <= 5 ? 40 : 55
  return `color-mix(in srgb, var(--color-starlight) ${100 - dull}%, var(--color-ink-faint))`
}

/** status → { fill, stroke, glow } for the star dot.
 *
 * INK INVERSION (cold-eye review): a status instrument must answer
 * "where is it stuck" in one glance. While ANYTHING is still live,
 * the unproved few are the brightest objects in the sky and the
 * proved mass recedes to memory; only a FINISHED problem lets the
 * proved stars shine (the sky becomes the trophy it earned). */
function nodeStyle(
  g: Goal,
  hasLive: boolean,
): { fill: string; stroke: string; glow: boolean; opacity: number } {
  switch (g.status) {
    case 'proved':
      return hasLive
        ? {
            fill: 'color-mix(in srgb, var(--color-starlight) 45%, var(--color-bg))',
            stroke: 'color-mix(in srgb, var(--color-starlight) 45%, var(--color-bg))',
            glow: false,
            opacity: 0.9,
          }
        : {
            fill: provedFill(g.dead_attempts),
            stroke: provedFill(g.dead_attempts),
            glow: true,
            opacity: 1,
          }
    case 'attempting':
      return { fill: 'var(--color-starlight)', stroke: 'var(--color-starlight)', glow: true, opacity: 1 }
    case 'open':
      // the live frontier owns the light: filled bright + glow, so the
      // seven unproved stars outshine the hundred proved ones
      return { fill: 'var(--color-star)', stroke: 'var(--color-starlight)', glow: true, opacity: 1 }
    case 'frozen':
      return { fill: 'transparent', stroke: 'var(--color-ink-faint)', glow: false, opacity: 0.8 }
    case 'pending_strategist_review':
      return { fill: 'transparent', stroke: 'var(--color-warn)', glow: true, opacity: 1 }
    case 'shelved':
      return { fill: 'var(--color-ink-faint)', stroke: 'var(--color-ink-faint)', glow: false, opacity: 0.45 }
    case 'disproved':
      return { fill: 'var(--color-danger)', stroke: 'var(--color-danger)', glow: false, opacity: 0.8 }
    case 'dead':
    default:
      return { fill: 'var(--color-edge-strong)', stroke: 'var(--color-edge-strong)', glow: false, opacity: 0.35 }
  }
}

/** Size hierarchy = what the human must know (owner: anchor + claim
 * are the only nodes the user NEEDS): root and claims largest, def
 * anchors next, supporting Props recede. */
function radius(g: Goal): number {
  if (g.origin === 'root') return 9
  if (g.is_deliverable) return 8.5
  if (DEF_KINDS.has(g.kind)) return 6.5
  return 4.5
}

/** def-like kinds — the vouchable meaning-bearers (anchor+claim §4) */
const DEF_KINDS = new Set(['def', 'structure', 'class', 'instance', 'abbrev', 'inductive'])

/* Root goals are just the brightest star: larger radius + a soft halo
 * ring. No glyph shapes (owner's call — spikes and sparks both out). */

function edgeStroke(
  status: Strategy['status'],
  kind: 'strategy' | 'alias' | 'anchor' | 'citation',
): string {
  if (kind === 'alias') return 'var(--color-accent)'
  if (kind === 'citation') return 'var(--color-starlight)'
  if (kind === 'anchor' || status === 'succeeded') return 'var(--color-starlight)'
  if (status === 'dead' || status === 'superseded') return 'var(--color-edge)'
  return 'var(--color-edge-strong)'
}

export default function Constellation({
  goals,
  strategies,
  strategyEdges,
  anchorEdges = [],
  citationEdges = [],
  selectedId,
  onSelect,
  onSelectStrategy,
  shelveThreshold = 8,
  engineWorking = false,
}: Props) {
  // Frontier focus: on for big live graphs by default (attention +
  // charter §7 perf bar); terminal problems always show everything.
  const [focusFrontier, setFocusFrontier] = useState<boolean | null>(null)
  const [legendOpen, setLegendOpen] = useState<boolean>(() => {
    try {
      return localStorage.getItem('cst-legend') !== 'closed'
    } catch {
      return true
    }
  })
  const frontier = useMemo(
    () => frontierView(goals, strategies, strategyEdges),
    [goals, strategies, strategyEdges],
  )
  const focusable = frontier.hiddenCount > 0
  const focused = focusable && (focusFrontier ?? goals.length > 60)
  const shownGoals = focused ? frontier.goals : goals
  // ink inversion gate: while anything is live the unproved few carry
  // the light; a finished sky lets the proved shine
  const hasLive = goals.some(
    (g) =>
      g.status === 'open' ||
      g.status === 'attempting' ||
      g.status === 'pending_strategist_review',
  )

  const layout = useMemo(
    () =>
      layoutConstellation(shownGoals, strategies, strategyEdges, anchorEdges, citationEdges),
    [shownGoals, strategies, strategyEdges, anchorEdges, citationEdges],
  )
  const byId = useMemo(
    () => new Map(layout.nodes.map((n) => [n.goal.id, n])),
    [layout],
  )
  // Label stagger is collision-avoidance for dense layers; in sparse
  // layers it reads as jitter, so apply it only where needed.
  const layerCounts = useMemo(() => {
    const m = new Map<number, number>()
    for (const n of layout.nodes) m.set(n.layer, (m.get(n.layer) ?? 0) + 1)
    return m
  }, [layout])

  // Per-node label room from the ACTUAL neighbours in the same label
  // row (same y + same stagger parity) — a lone star at the sky's
  // edge must never truncate into empty space, and a short neighbour
  // donates the room it doesn't need. Gaps in content units (× k at
  // render); neighbour slug lengths ride along for the fair split.
  const labelRoom = useMemo(() => {
    const rows = new Map<string, LayoutNode[]>()
    for (const n of layout.nodes) {
      const staggered = (layerCounts.get(n.layer) ?? 0) > 8 && n.col % 2 === 1
      const key = `${n.y}:${staggered ? 1 : 0}`
      rows.set(key, [...(rows.get(key) ?? []), n])
    }
    const room = new Map<
      number,
      { gapL: number; gapR: number; nbrL: number; nbrR: number }
    >()
    for (const ns of rows.values()) {
      ns.sort((a, b) => a.x - b.x)
      ns.forEach((n, i) => {
        room.set(n.goal.id, {
          gapL: i > 0 ? n.x - ns[i - 1].x : Infinity,
          gapR: i < ns.length - 1 ? ns[i + 1].x - n.x : Infinity,
          nbrL: i > 0 ? ns[i - 1].goal.slug.length : 0,
          nbrR: i < ns.length - 1 ? ns[i + 1].goal.slug.length : 0,
        })
      })
    }
    return room
  }, [layout, layerCounts])

  // newborn stars (ids that appear after the first load) get a brief
  // halo so a live run reads as growth, not as a diff you must spot
  const birthsRef = useRef<{ seen: Set<number>; born: Map<number, number>; primed: boolean }>({
    seen: new Set(),
    born: new Map(),
    primed: false,
  })
  useEffect(() => {
    const b = birthsRef.current
    const now = Date.now()
    if (!b.primed) {
      for (const g of goals) b.seen.add(g.id)
      if (goals.length > 0) b.primed = true
      return
    }
    for (const g of goals) {
      if (!b.seen.has(g.id)) {
        b.seen.add(g.id)
        b.born.set(g.id, now)
      }
    }
    for (const [id, t] of b.born) if (now - t > 12000) b.born.delete(id)
  }, [goals])

  const containerRef = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<{ k: number; tx: number; ty: number } | null>(null)
  const [hovered, setHovered] = useState<LayoutNode | null>(null)
  const [showDead, setShowDead] = useState(false)
  const drag = useRef<{ x: number; y: number; tx: number; ty: number; moved: boolean } | null>(null)

  // Initial fit — once per problem and on frontier-focus toggles (not
  // per poll: the layout is stable, and refitting under the user's
  // zoom would fight them). `userAdjusted` records a manual zoom/pan:
  // a window resize re-fits ONLY untouched views (fighting an explicit
  // zoom is worse than letting it drift off-center).
  const userAdjusted = useRef(false)
  useEffect(() => {
    userAdjusted.current = false
    setView(null)
  }, [goals.length > 0 && goals[0].lean_path.split('/')[1], focused])
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    // observe() always delivers one INITIAL callback (spec) — it is
    // not a resize, and letting it setView(null) batches against the
    // mount fit's setView(fitted): the queue collapses to null→null,
    // the [view] dep sees no change, and the fit effect starves until
    // the next poll (~2s of unfitted sky). Skip delivery #1.
    let initial = true
    const ro = new ResizeObserver(() => {
      if (initial) {
        initial = false
        return
      }
      if (!userAdjusted.current) setView(null)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  useEffect(() => {
    if (view !== null) return
    const el = containerRef.current
    if (!el || layout.nodes.length === 0) return
    const { width: cw, height: ch } = el.getBoundingClientRect()
    // Fill the canvas: fit the content bounding box, allowing generous
    // magnification for small graphs (10 stars in a void read as a
    // failed page load — design review). Tiny plates may magnify
    // further still: four stars at atlas scale is a composition,
    // at survey scale it's dust.
    const kMax = layout.nodes.length <= 10 ? 2.6 : 2.0
    // extra vertical air: the floating legend row must not sit on the
    // top band's stars (cold-eye finding)
    const k = Math.min((cw - 48) / layout.width, (ch - 88) / layout.height, kMax)
    setView({
      k,
      tx: (cw - layout.width * k) / 2,
      ty: (ch - layout.height * k) / 2 + 14,
    })
  }, [view, layout])

  const k = view?.k ?? 1
  const tx = view?.tx ?? 0
  const ty = view?.ty ?? 0
  const showLabels = k >= 1.05

  // Wheel zoom must preventDefault (page would scroll); React's
  // delegated wheel handlers are passive, so attach natively.
  const viewRef = useRef(view)
  viewRef.current = view
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      const v = viewRef.current
      if (v === null) return
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const factor = Math.exp(-e.deltaY * 0.0012)
      const nk = Math.min(4, Math.max(0.25, v.k * factor))
      // zoom about the cursor; update the ref immediately so rapid
      // wheel bursts compound instead of re-reading a stale view
      const next = {
        k: nk,
        tx: mx - ((mx - v.tx) / v.k) * nk,
        ty: my - ((my - v.ty) / v.k) * nk,
      }
      userAdjusted.current = true
      viewRef.current = next
      setView(next)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const onPointerDown = (e: React.PointerEvent) => {
    if (view === null) return
    drag.current = { x: e.clientX, y: e.clientY, tx: view.tx, ty: view.ty, moved: false }
    ;(e.target as Element).setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current
    if (!d || view === null) return
    const dx = e.clientX - d.x
    const dy = e.clientY - d.y
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true
    if (d.moved) {
      userAdjusted.current = true
      setView({ k: view.k, tx: d.tx + dx, ty: d.ty + dy })
    }
  }
  const onPointerUp = (e: React.PointerEvent) => {
    const d = drag.current
    drag.current = null
    if (d && !d.moved && (e.target as Element).tagName === 'svg') onSelect(null)
  }

  const isDead = (s: string) => s === 'dead' || s === 'superseded'
  const visibleEdges = layout.edges.filter(
    (e) => showDead || e.kind === 'alias' || !isDead(e.strategyStatus),
  )
  // density-stepped: a handful of citations read at 0.22; a hundred
  // would wash the sky at that weight
  const citeCount = visibleEdges.filter((e) => e.kind === 'citation').length
  const citeOpacity = citeCount > 80 ? 0.08 : citeCount > 30 ? 0.13 : 0.22
  // hover/selection focus: point at a star with citation threads and
  // its threads carry the light while the rest of the web recedes —
  // "where is this actually used" answered in place (cold-eye backlog)
  const focusId = hovered?.goal.id ?? selectedId
  const citeFocus =
    focusId !== null &&
    visibleEdges.some(
      (e) => e.kind === 'citation' && (e.from === focusId || e.to === focusId),
    )
  const visibleBundles = layout.bundles.filter((b) => showDead || !isDead(b.status))
  const deadEdgeCount =
    layout.edges.length -
    visibleEdges.length +
    layout.bundles.filter((b) => isDead(b.status)).length

  // Faint background stardust — deterministic per problem, pure
  // atmosphere (opacity kept below signal level).
  const dust = useMemo(() => {
    let h = 88172645
    const rand = () => {
      h ^= h << 13
      h ^= h >>> 17
      h ^= h << 5
      return ((h >>> 0) % 1000) / 1000
    }
    return Array.from({ length: 70 }, () => ({
      x: rand() * 1600 - 200,
      y: rand() * 1200 - 200,
      r: 0.5 + rand() * 0.9,
      o: 0.04 + rand() * 0.1,
    }))
  }, [])

  if (layout.nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-faint">
        No goals yet — the constellation appears once the Strategist starts working.
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full cursor-grab overflow-hidden active:cursor-grabbing"
    >
      <svg
        className="constellation h-full w-full"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        <defs>
          <filter id="star-glow" x="-150%" y="-150%" width="400%" height="400%">
            <feGaussianBlur stdDeviation="3.2" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* atmosphere: two faint nebulae + a vignette, screen-space so
              they sit behind the sky rather than inside it */}
          <radialGradient id="nebula-a" cx="30%" cy="24%" r="55%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.028" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="nebula-b" cx="76%" cy="72%" r="50%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.02" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="100%" height="100%" fill="url(#nebula-a)" />
        <rect width="100%" height="100%" fill="url(#nebula-b)" />
        <g transform={`translate(${tx},${ty}) scale(${k})`}>
          {dust.map((d, i) => (
            <circle
              key={`d${i}`}
              cx={d.x}
              cy={d.y}
              r={(d.r * 0.8) / Math.max(k, 0.5)}
              fill="var(--color-ink)"
              opacity={d.o * 0.45}
            />
          ))}
          {visibleEdges.map((e, i) => {
            const a = byId.get(e.from)
            const b = byId.get(e.to)
            if (!a || !b) return null
            const dead = isDead(e.strategyStatus)
            if (e.kind === 'citation') {
              // Citations bow sideways as quiet threads: parallel long
              // straights merge into fog on cite-heavy skies (sphere:
              // 100+ edges); a bow separates neighbours, and opacity
              // steps down with density so the trees stay in front.
              const dx = b.x - a.x
              const dy = b.y - a.y
              const len = Math.hypot(dx, dy) || 1
              // bow grows with span (a 46px cap flattened long
              // horizontals back into wires); parity mixes directions
              const bow =
                Math.min(150, len * 0.18) * ((e.from + e.to) % 2 === 0 ? 1 : -1)
              const mx = (a.x + b.x) / 2 + (-dy / len) * bow
              const my = (a.y + b.y) / 2 + (dx / len) * bow
              // long hauls fade further: a cross-sky thread is context,
              // not content — nearby citations stay readable
              const fade = Math.min(1, Math.max(0.35, 320 / len))
              const touched = citeFocus && (e.from === focusId || e.to === focusId)
              return (
                <path
                  key={i}
                  d={`M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`}
                  fill="none"
                  stroke={edgeStroke(e.strategyStatus, e.kind)}
                  strokeWidth={touched ? 1.4 : 1}
                  strokeOpacity={
                    touched
                      ? Math.max(0.55, citeOpacity * fade)
                      : citeFocus
                        ? 0.04
                        : citeOpacity * fade
                  }
                  vectorEffect="non-scaling-stroke"
                />
              )
            }
            return (
              <line
                key={i}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={edgeStroke(e.strategyStatus, e.kind)}
                strokeWidth={e.strategyStatus === 'succeeded' ? 1.2 : 1}
                strokeOpacity={
                  dead
                    ? 0.35
                    : e.kind === 'alias'
                      ? 0.5
                      : e.kind === 'anchor'
                        ? 0.3
                        : e.strategyStatus === 'succeeded'
                          ? 0.38
                          : 0.55
                }
                strokeDasharray={e.kind === 'alias' ? '4 4' : undefined}
                vectorEffect="non-scaling-stroke"
              />
            )
          })}
          {visibleBundles.map((b) => {
            // AND-group hyperedge: stem parent→junction, then branches.
            // Side-by-side junctions on one goal = competing strategies.
            const parent = byId.get(b.parentId)
            if (!parent) return null
            const dead = isDead(b.status)
            const stroke = edgeStroke(b.status, 'strategy')
            const opacity = dead ? 0.35 : b.status === 'succeeded' ? 0.38 : 0.55
            return (
              <g key={`s${b.strategyId}`}>
                <line
                  x1={parent.x}
                  y1={parent.y}
                  x2={b.junction.x}
                  y2={b.junction.y}
                  stroke={stroke}
                  strokeWidth={b.status === 'succeeded' ? 2 : 1.6}
                  strokeOpacity={opacity}
                  vectorEffect="non-scaling-stroke"
                />
                {b.children.map((cid) => {
                  const c = byId.get(cid)
                  if (!c) return null
                  return (
                    <line
                      key={cid}
                      x1={b.junction.x}
                      y1={b.junction.y}
                      x2={c.x}
                      y2={c.y}
                      stroke={stroke}
                      strokeWidth={b.status === 'succeeded' ? 1.4 : 1}
                      strokeOpacity={opacity}
                      vectorEffect="non-scaling-stroke"
                    />
                  )
                })}
                <circle
                  cx={b.junction.x}
                  cy={b.junction.y}
                  r={2.1}
                  fill={stroke}
                  opacity={opacity}
                />
                {onSelectStrategy && (
                  <>
                    {/* a faint ring says "this fork is a thing you can
                        open" — the bare hit area was undiscoverable */}
                    <circle
                      cx={b.junction.x}
                      cy={b.junction.y}
                      r={5}
                      fill="none"
                      stroke={stroke}
                      strokeWidth={0.8}
                      opacity={opacity * 0.35}
                      vectorEffect="non-scaling-stroke"
                    />
                    <circle
                      cx={b.junction.x}
                      cy={b.junction.y}
                      r={9}
                      fill="transparent"
                      className="cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation()
                        onSelectStrategy(b.strategyId)
                      }}
                    >
                      <title>
                        one route: this fork needs ALL its branches; a second
                        fork on the same star is a competing route — click for
                        details (s{b.strategyId}, {b.status})
                      </title>
                    </circle>
                  </>
                )}
              </g>
            )
          })}
          {/* band hairlines: bands stack independent trees — equal y
              across bands means nothing, so mark the seams */}
          {layout.bandTops.map((y, i) => (
            <line
              key={`b${i}`}
              x1={0}
              y1={y}
              x2={layout.width}
              y2={y}
              stroke="var(--color-edge)"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {/* the horizon: above it, what grew from the root (or was
              marked a claim); below, other forward work — citation
              threads cross it where that work is actually used */}
          {layout.horizonY !== null && (
            <g className="pointer-events-none select-none">
              <line
                x1={0}
                y1={layout.horizonY}
                x2={layout.width}
                y2={layout.horizonY}
                stroke="var(--color-edge-strong)"
                strokeWidth={1}
                strokeDasharray="1 6"
                vectorEffect="non-scaling-stroke"
              />
              <text
                x={layout.width}
                y={layout.horizonY + 16 / k}
                textAnchor="end"
                fill="var(--color-ink-faint)"
                fontSize={10 / k}
                fontFamily="var(--font-sans)"
                letterSpacing="0.12em"
              >
                OTHER FORWARD WORK
              </text>
            </g>
          )}
          {layout.singlesBlock && (
            <text
              x={layout.singlesBlock.x}
              y={layout.singlesBlock.y - 22 / k}
              fill="var(--color-ink-faint)"
              fontSize={10 / k}
              fontFamily="var(--font-sans)"
              className="pointer-events-none select-none"
            >
              unlinked · {layout.singlesBlock.count}
            </text>
          )}
          {layout.nodes.map((n) => {
            const s = nodeStyle(n.goal, hasLive)
            const live =
              n.goal.status === 'open' ||
              n.goal.status === 'attempting' ||
              n.goal.status === 'pending_strategist_review'
            // scale honesty: marks never drop below ~7px on screen (the
            // live frontier gets a size bonus + a larger floor) — but
            // the floor is capped in CONTENT units, or at extreme
            // zoom-out the floors exceed the slot gap and stars fuse
            // into blobs (residue_thm, 500 nodes)
            const r = Math.max(
              radius(n.goal) + (live ? 1.5 : 0),
              Math.min((live ? 5.5 : 3.5) / k, X_GAP * 0.28),
            )
            const lod = k < 0.8
            const fill = lod && live ? s.stroke : s.fill
            const selected = n.goal.id === selectedId
            // Attempts heat ring: arc fraction of the shelve threshold,
            // only meaningful while the goal is still being worked.
            const heatFrac =
              (n.goal.status === 'open' ||
                n.goal.status === 'attempting' ||
                n.goal.status === 'pending_strategist_review') &&
              n.goal.attempts > 0
                ? Math.min(n.goal.attempts / shelveThreshold, 1)
                : 0
            const heatR = r + 3
            const heatC = 2 * Math.PI * heatR
            return (
              <g
                key={n.goal.id}
                transform={`translate(${n.x},${n.y})`}
                className="cursor-pointer"
                onMouseEnter={() => setHovered(n)}
                onMouseLeave={() => setHovered(null)}
                onClick={(e) => {
                  e.stopPropagation()
                  onSelect(n.goal.id)
                }}
              >
                {/* ring slots are disjoint (heat r+3, deliverable r+5,
                    root r+7, in-flight r+8, selection r+10) — two
                    meanings on one radius merge into ambiguity */}
                {selected && (
                  <circle
                    r={r + 10}
                    fill="none"
                    stroke="var(--color-ink)"
                    strokeWidth={1}
                    strokeOpacity={0.8}
                    strokeDasharray="2 3"
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                {n.goal.origin === 'root' && (
                  <circle
                    r={r + 7}
                    fill="none"
                    stroke={s.stroke}
                    strokeWidth={0.8}
                    opacity={s.opacity * 0.5}
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                {/* defs are the meaning-bearers (the anchor surface a
                    human vouches for) — diamonds above the shape-
                    perception threshold (~5px), circles below it;
                    Props are the light and stay round */}
                {DEF_KINDS.has(n.goal.kind) && r * k >= 5 ? (
                  <rect
                    x={-r * 1.06}
                    y={-r * 1.06}
                    width={r * 2.12}
                    height={r * 2.12}
                    transform="rotate(45)"
                    fill={fill}
                    stroke={s.stroke}
                    strokeWidth={1.4}
                    opacity={s.opacity}
                    filter={s.glow ? 'url(#star-glow)' : undefined}
                    vectorEffect="non-scaling-stroke"
                  >
                    {engineWorking && n.goal.status === 'attempting' && (
                      <animate
                        attributeName="opacity"
                        values="1;0.45;1"
                        dur="1.6s"
                        repeatCount="indefinite"
                      />
                    )}
                  </rect>
                ) : (
                  <circle
                    r={r}
                    fill={fill}
                    stroke={s.stroke}
                    strokeWidth={1.4}
                    opacity={s.opacity}
                    filter={s.glow ? 'url(#star-glow)' : undefined}
                    vectorEffect="non-scaling-stroke"
                  >
                    {engineWorking && n.goal.status === 'attempting' && (
                      <animate
                        attributeName="opacity"
                        values="1;0.45;1"
                        dur="1.6s"
                        repeatCount="indefinite"
                      />
                    )}
                  </circle>
                )}
                {n.goal.is_deliverable && (
                  <circle
                    r={r + 5}
                    fill="none"
                    stroke="var(--color-star)"
                    strokeWidth={1.1}
                    opacity={0.9}
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                {heatFrac > 0 && (
                  <circle
                    r={heatR}
                    fill="none"
                    stroke="var(--color-starlight)"
                    strokeWidth={1.2}
                    strokeOpacity={0.4 + heatFrac * 0.5}
                    strokeDasharray={`${heatC * heatFrac} ${heatC}`}
                    transform="rotate(-90)"
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                {birthsRef.current.born.has(n.goal.id) && (
                  <circle
                    r={r + 12}
                    fill="none"
                    stroke="var(--color-starlight)"
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                  >
                    <animate
                      attributeName="stroke-opacity"
                      values="0.8;0.1;0.8"
                      dur="1.8s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                {n.goal.in_flight && (
                  <circle
                    r={r + 8}
                    fill="none"
                    stroke="var(--color-accent)"
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                  >
                    <animate
                      attributeName="stroke-opacity"
                      values="0.7;0.15;0.7"
                      dur="1.4s"
                      repeatCount="indefinite"
                    />
                    <animate
                      attributeName="r"
                      values={`${r + 7};${r + 9};${r + 7}`}
                      dur="1.4s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                {focused && (frontier.folded.get(n.goal.id) ?? 0) > 0 && (
                  <text
                    x={r + 4 / k}
                    y={-r}
                    className="pointer-events-none select-none"
                    fill="var(--color-ink-faint)"
                    fontSize={9.5 / k}
                    fontFamily="var(--font-mono)"
                  >
                    +{frontier.folded.get(n.goal.id)}
                  </text>
                )}
                {(showLabels ||
                  n.goal.origin === 'root' ||
                  n.goal.is_deliverable) && (
                  <text
                    // Stagger label rows by in-layer parity so long
                    // slugs on adjacent stars don't collide; offsets are
                    // screen-constant like the font. Truncation is
                    // width-aware: never truncate into empty space.
                    // Root + claims stay labelled at ANY zoom — the
                    // survey view needs its landmarks named.
                    y={
                      r * (n.goal.is_deliverable || n.goal.origin === 'root' ? 1.6 : 1) +
                      ((layerCounts.get(n.layer) ?? 0) > 8 && n.col % 2 === 1 ? 26 : 15) / k
                    }
                    textAnchor="middle"
                    className="pointer-events-none select-none"
                    fill={selected ? 'var(--color-ink)' : 'var(--color-ink-dim)'}
                    fontSize={10.5 / k}
                    fontFamily="var(--font-mono)"
                  >
                    {(() => {
                      // budget from ACTUAL neighbour room: fair split
                      // of each gap, plus whatever a short neighbour
                      // doesn't need (mono ≈6.4px/char on screen)
                      const rm = labelRoom.get(n.goal.id)
                      const side = (gap: number, nbrLen: number) => {
                        if (!Number.isFinite(gap)) return Infinity
                        const gapPx = gap * k
                        return gapPx - 6 - Math.min(nbrLen * 3.2, gapPx / 2)
                      }
                      const half = rm
                        ? Math.min(side(rm.gapL, rm.nbrL), side(rm.gapR, rm.nbrR))
                        : Infinity
                      const budget = Number.isFinite(half)
                        ? Math.min(44, Math.max(12, Math.floor((half * 2) / 6.4)))
                        : 44
                      return n.goal.slug.length <= budget
                        ? n.goal.slug
                        : `${n.goal.slug.slice(0, Math.floor(budget / 2) - 1)}…${n.goal.slug.slice(-(Math.floor(budget / 2) - 1))}`
                    })()}
                  </text>
                )}
              </g>
            )
          })}
        </g>
      </svg>

      {/* the selected node's facts live in the side panel — no echo */}
      {hovered && hovered.goal.id !== selectedId && view !== null && (
        <div
          className="pointer-events-none absolute z-10 max-w-sm rounded-md border border-edge-strong bg-surface-3 px-3 py-2"
          style={{
            left: Math.min(
              tx + hovered.x * k + 14,
              (containerRef.current?.clientWidth ?? 800) - 340,
            ),
            top: Math.min(
              ty + hovered.y * k + 14,
              (containerRef.current?.clientHeight ?? 600) - 120,
            ),
          }}
        >
          <div className="mb-1 flex items-center gap-2">
            <span className="font-mono text-xs text-ink">{hovered.goal.slug}</span>
            <span className="text-xs text-ink-faint">
              {goalStatusLabel(hovered.goal.status)}
            </span>
          </div>
          <div className="line-clamp-4 font-mono text-[11px] leading-snug text-ink-dim">
            {hovered.goal.statement}
          </div>
          {(hovered.goal.attempts > 0 || hovered.goal.dead_attempts > 0) && (
            <div className="mt-1 text-[11px] text-ink-faint">
              {hovered.goal.attempts} attempt{hovered.goal.attempts === 1 ? '' : 's'}
              {hovered.goal.dead_attempts > 0 && ` · ${hovered.goal.dead_attempts} dead`}
            </div>
          )}
        </div>
      )}

      {/* legend open by default (owner call — the encoding is for
          strangers, not the author); one click folds it away, and the
          choice sticks */}
      <div className="absolute top-3 left-3">
        <button
          className="cursor-pointer rounded-md bg-surface/80 px-2 py-1 text-[11px] text-ink-faint transition-colors hover:text-ink-dim"
          onClick={() =>
            setLegendOpen((v) => {
              try {
                localStorage.setItem('cst-legend', v ? 'closed' : 'open')
              } catch {
                /* private mode */
              }
              return !v
            })
          }
          title={legendOpen ? 'hide the legend' : 'show the legend'}
        >
          legend {legendOpen ? '▾' : '▸'}
        </button>
        <div
          className={`pointer-events-none mt-1 ${legendOpen ? 'flex' : 'hidden'} flex-wrap items-center gap-3 rounded-md bg-surface/90 px-2.5 py-1 text-[11px] text-ink-faint`}
        >
        <span className="flex items-center gap-1">
          <svg width="10" height="10" viewBox="-5 -5 10 10">
            <circle r="3" fill="var(--color-starlight)" />
          </svg>
          proved
        </span>
        <span className="flex items-center gap-1">
          <svg width="10" height="10" viewBox="-5 -5 10 10">
            <circle r="3" fill="none" stroke="var(--color-accent)" strokeWidth="1.2" />
          </svg>
          open
        </span>
        <span className="flex items-center gap-1">
          <svg width="12" height="12" viewBox="-6 -6 12 12">
            <circle r="5" fill="none" stroke="var(--color-starlight)" strokeWidth="0.6" opacity="0.5" />
            <circle r="2.8" fill="var(--color-starlight)" />
          </svg>
          root
        </span>
        <span className="flex items-center gap-1">
          <svg width="12" height="12" viewBox="-6 -6 12 12">
            <circle r="2.4" fill="var(--color-starlight)" />
            <circle r="4.6" fill="none" stroke="var(--color-star)" strokeWidth="0.9" opacity="0.9" />
          </svg>
          deliverable
        </span>
        <span className="flex items-center gap-1">
          <svg width="14" height="10" viewBox="0 0 14 10">
            <line x1="1" y1="5" x2="13" y2="5" stroke="var(--color-accent)" strokeWidth="1" strokeDasharray="3 2.5" opacity="0.7" />
          </svg>
          alias
        </span>
        <span className="flex items-center gap-1" title="one proof imports another — the lemma is used there">
          <svg width="14" height="10" viewBox="0 0 14 10">
            <line x1="1" y1="8" x2="13" y2="2" stroke="var(--color-starlight)" strokeWidth="1" opacity="0.45" />
          </svg>
          cites
        </span>
        <span
          className="flex items-center gap-1"
          title="a fork needs ALL its branches (one route); two forks on one star are competing routes — click a fork for details"
        >
          <svg width="12" height="12" viewBox="0 0 12 12">
            <line x1="6" y1="1" x2="6" y2="5" stroke="var(--color-starlight)" strokeWidth="1" opacity="0.6" />
            <line x1="6" y1="5" x2="2" y2="11" stroke="var(--color-starlight)" strokeWidth="1" opacity="0.6" />
            <line x1="6" y1="5" x2="10" y2="11" stroke="var(--color-starlight)" strokeWidth="1" opacity="0.6" />
            <circle cx="6" cy="5" r="1.6" fill="var(--color-starlight)" opacity="0.8" />
          </svg>
          route
        </span>
        <span className="flex items-center gap-1">
          <svg width="10" height="10" viewBox="-5 -5 10 10">
            <rect x="-2.6" y="-2.6" width="5.2" height="5.2" transform="rotate(45)" fill="var(--color-starlight)" />
          </svg>
          def
        </span>
        <span className="flex items-center gap-1">
          <svg width="12" height="12" viewBox="-6 -6 12 12">
            <circle r="2.4" fill="none" stroke="var(--color-ink-faint)" strokeWidth="1" />
            <circle
              r="4.4"
              fill="none"
              stroke="var(--color-warn)"
              strokeWidth="1.2"
              strokeDasharray="14 28"
              transform="rotate(-90)"
            />
          </svg>
          attempts
        </span>
        </div>
      </div>
      <div className="absolute bottom-3 left-3 flex overflow-hidden rounded-md border border-edge bg-surface">
        {(
          [
            ['−', 0.7],
            ['+', 1.45],
          ] as const
        ).map(([label, factor]) => (
          <button
            key={label}
            className="px-2.5 py-1 text-sm text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
            title={label === '+' ? 'zoom in' : 'zoom out'}
            onClick={() => {
              const v = viewRef.current
              const el = containerRef.current
              if (!v || !el) return
              const { width: cw, height: ch } = el.getBoundingClientRect()
              const nk = Math.min(4, Math.max(0.25, v.k * factor))
              const next = {
                k: nk,
                tx: cw / 2 - ((cw / 2 - v.tx) / v.k) * nk,
                ty: ch / 2 - ((ch / 2 - v.ty) / v.k) * nk,
              }
              userAdjusted.current = true
              viewRef.current = next
              setView(next)
            }}
          >
            {label}
          </button>
        ))}
        <button
          className="border-l border-edge px-2.5 py-1 text-xs text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
          title="fit to view"
          onClick={() => {
            userAdjusted.current = false
            setView(null)
          }}
        >
          fit
        </button>
      </div>
      <div className="absolute right-3 bottom-3 flex gap-2">
        {focusable && (
          <button
            className="rounded-md border border-edge bg-surface px-2.5 py-1 text-xs text-ink-dim hover:border-edge-strong hover:text-ink"
            onClick={() => setFocusFrontier(!focused)}
            title="Tuck finished branches behind their nearest visible star (+N badges); the stars still being worked stay out"
          >
            {focused
              ? `showing active work — show all (${goals.length})`
              : `hide finished work (${frontier.hiddenCount})`}
          </button>
        )}
        {deadEdgeCount > 0 && (
          <button
            className="rounded-md border border-edge bg-surface px-2.5 py-1 text-xs text-ink-dim hover:border-edge-strong hover:text-ink"
            onClick={() => setShowDead((v) => !v)}
          >
            {showDead ? 'hide' : 'show'} dead paths ({deadEdgeCount})
          </button>
        )}
      </div>
    </div>
  )
}
