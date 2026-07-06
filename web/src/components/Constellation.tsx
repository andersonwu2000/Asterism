import { useEffect, useMemo, useRef, useState } from 'react'
import type { Goal, Strategy, StrategyEdge } from '../lib/types'
import { frontierView, layoutConstellation, X_GAP } from '../lib/layout'
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
}

/** Residual struggle heat: a proved star that burned failed attempts
 * keeps a warm cast — "where the machine fought" stays on the map for
 * the reviewer hunting fragile spots. */
function provedFill(dead: number): string {
  if (dead <= 0) return 'var(--color-starlight)'
  const warm = dead <= 2 ? 18 : dead <= 5 ? 34 : 50
  return `color-mix(in srgb, var(--color-starlight) ${100 - warm}%, var(--color-warn))`
}

/** status → { fill, stroke, glow } for the star dot */
function nodeStyle(g: Goal): { fill: string; stroke: string; glow: boolean; opacity: number } {
  switch (g.status) {
    case 'proved':
      return {
        fill: provedFill(g.dead_attempts),
        stroke: provedFill(g.dead_attempts),
        glow: true,
        opacity: 1,
      }
    case 'attempting':
      return { fill: 'var(--color-accent)', stroke: 'var(--color-accent)', glow: true, opacity: 1 }
    case 'open':
      // The live frontier is the interesting 7% — accent, no glow
      // (glow shared with proved made brightness meaningless).
      return { fill: 'transparent', stroke: 'var(--color-accent)', glow: false, opacity: 1 }
    case 'frozen':
      return { fill: 'transparent', stroke: 'var(--color-ink-faint)', glow: false, opacity: 0.8 }
    case 'pending_strategist_review':
      return { fill: 'transparent', stroke: 'var(--color-warn)', glow: false, opacity: 1 }
    case 'shelved':
      return { fill: 'var(--color-ink-faint)', stroke: 'var(--color-ink-faint)', glow: false, opacity: 0.45 }
    case 'disproved':
      return { fill: 'var(--color-danger)', stroke: 'var(--color-danger)', glow: false, opacity: 0.8 }
    case 'dead':
    default:
      return { fill: 'var(--color-edge-strong)', stroke: 'var(--color-edge-strong)', glow: false, opacity: 0.35 }
  }
}

function radius(g: Goal): number {
  if (g.origin === 'root') return 9
  if (g.is_deliverable) return 7
  return 5
}

/** def-like kinds — the vouchable meaning-bearers (anchor+claim §4) */
const DEF_KINDS = new Set(['def', 'structure', 'class', 'instance', 'abbrev', 'inductive'])

/* Root goals are just the brightest star: larger radius + a soft halo
 * ring. No glyph shapes (owner's call — spikes and sparks both out). */

const STATUS_LABEL: Record<string, string> = {
  open: 'open',
  attempting: 'attempting',
  proved: 'proved',
  shelved: 'shelved',
  pending_strategist_review: 'awaiting strategist review',
  disproved: 'disproved',
  frozen: 'frozen (pre-launch)',
  dead: 'dead',
}

function edgeStroke(status: Strategy['status'], kind: 'strategy' | 'alias' | 'anchor'): string {
  if (kind === 'alias') return 'var(--color-accent)'
  if (kind === 'anchor' || status === 'succeeded') return 'var(--color-starlight)'
  if (status === 'dead' || status === 'superseded') return 'var(--color-edge)'
  return 'var(--color-edge-strong)'
}

export default function Constellation({
  goals,
  strategies,
  strategyEdges,
  anchorEdges = [],
  selectedId,
  onSelect,
  onSelectStrategy,
  shelveThreshold = 8,
}: Props) {
  // Frontier focus: on for big live graphs by default (attention +
  // charter §7 perf bar); terminal problems always show everything.
  const [focusFrontier, setFocusFrontier] = useState<boolean | null>(null)
  const frontier = useMemo(
    () => frontierView(goals, strategies, strategyEdges),
    [goals, strategies, strategyEdges],
  )
  const focusable = frontier.hiddenCount > 0
  const focused = focusable && (focusFrontier ?? goals.length > 60)
  const shownGoals = focused ? frontier.goals : goals

  const layout = useMemo(
    () => layoutConstellation(shownGoals, strategies, strategyEdges, anchorEdges),
    [shownGoals, strategies, strategyEdges, anchorEdges],
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

  const containerRef = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<{ k: number; tx: number; ty: number } | null>(null)
  const [hovered, setHovered] = useState<LayoutNode | null>(null)
  const [showDead, setShowDead] = useState(false)
  const drag = useRef<{ x: number; y: number; tx: number; ty: number; moved: boolean } | null>(null)

  // Initial fit — once per problem and on frontier-focus toggles (not
  // per poll: the layout is stable, and refitting under the user's
  // zoom would fight them).
  useEffect(() => {
    setView(null)
  }, [goals.length > 0 && goals[0].lean_path.split('/')[1], focused])
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
    const k = Math.min((cw - 48) / layout.width, (ch - 48) / layout.height, kMax)
    setView({
      k,
      tx: (cw - layout.width * k) / 2,
      ty: (ch - layout.height * k) / 2,
    })
  }, [view, layout])

  const k = view?.k ?? 1
  const tx = view?.tx ?? 0
  const ty = view?.ty ?? 0
  const showLabels = k >= 1.05
  const labelBudgetPx = X_GAP

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
    if (d.moved) setView({ k: view.k, tx: d.tx + dx, ty: d.ty + dy })
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
            <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.05" />
            <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="nebula-b" cx="76%" cy="72%" r="50%">
            <stop offset="0%" stopColor="var(--color-star)" stopOpacity="0.035" />
            <stop offset="100%" stopColor="var(--color-star)" stopOpacity="0" />
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
              r={d.r / Math.max(k, 0.5)}
              fill="var(--color-ink)"
              opacity={d.o}
            />
          ))}
          {visibleEdges.map((e, i) => {
            const a = byId.get(e.from)
            const b = byId.get(e.to)
            if (!a || !b) return null
            const dead = isDead(e.strategyStatus)
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
                  r={1.6}
                  fill={stroke}
                  opacity={opacity}
                />
                {onSelectStrategy && (
                  <circle
                    cx={b.junction.x}
                    cy={b.junction.y}
                    r={6}
                    fill="transparent"
                    className="cursor-pointer"
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelectStrategy(b.strategyId)
                    }}
                  >
                    <title>strategy s{b.strategyId} — {b.status}</title>
                  </circle>
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
          {layout.singlesBlock && (
            <text
              x={layout.singlesBlock.x}
              y={layout.singlesBlock.y - 22 / k}
              fill="var(--color-ink-faint)"
              fontSize={10 / k}
              fontFamily="var(--font-sans)"
              className="pointer-events-none select-none"
            >
              unlinked bricks · {layout.singlesBlock.count}
            </text>
          )}
          {layout.nodes.map((n) => {
            const s = nodeStyle(n.goal)
            const live =
              n.goal.status === 'open' ||
              n.goal.status === 'attempting' ||
              n.goal.status === 'pending_strategist_review'
            // scale honesty: marks never drop below ~7px on screen, and
            // at survey zoom the live frontier switches to filled
            // accent dots — hollow 0.5px strokes are sub-perceptual
            const r = Math.max(radius(n.goal), 3.5 / k)
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
                    {n.goal.status === 'attempting' && (
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
                    {n.goal.status === 'attempting' && (
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
                    stroke={heatFrac >= 0.99 ? 'var(--color-danger)' : 'var(--color-warn)'}
                    strokeWidth={1.2}
                    strokeOpacity={0.4 + heatFrac * 0.5}
                    strokeDasharray={`${heatC * heatFrac} ${heatC}`}
                    transform="rotate(-90)"
                    vectorEffect="non-scaling-stroke"
                  />
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
                {showLabels && (
                  <text
                    // Stagger label rows by in-layer parity so long
                    // slugs on adjacent stars don't collide; offsets are
                    // screen-constant like the font. Truncation is
                    // width-aware: never truncate into empty space.
                    y={
                      r +
                      ((layerCounts.get(n.layer) ?? 0) > 8 && n.col % 2 === 1 ? 26 : 14) / k
                    }
                    textAnchor="middle"
                    className="pointer-events-none select-none"
                    fill={selected ? 'var(--color-ink)' : 'var(--color-ink-dim)'}
                    fontSize={10.5 / k}
                    fontFamily="var(--font-mono)"
                  >
                    {(() => {
                      const budget = Math.max(12, Math.floor((labelBudgetPx * k) / 6.4))
                      return k >= 2 || n.goal.slug.length <= budget
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
              {STATUS_LABEL[hovered.goal.status] ?? hovered.goal.status}
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

      {/* persistent mini-legend — the encodings must be self-describing */}
      <div className="pointer-events-none absolute top-3 left-3 flex items-center gap-3 rounded-md bg-surface/80 px-2.5 py-1 text-[11px] text-ink-faint">
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
          onClick={() => setView(null)}
        >
          fit
        </button>
      </div>
      <div className="absolute right-3 bottom-3 flex gap-2">
        {focusable && (
          <button
            className="rounded-md border border-edge bg-surface px-2.5 py-1 text-xs text-ink-dim hover:border-edge-strong hover:text-ink"
            onClick={() => setFocusFrontier(!focused)}
            title="Fold settled subtrees into their nearest visible ancestor (+N badges)"
          >
            {focused
              ? `frontier focus — show all (${goals.length})`
              : `focus frontier (fold ${frontier.hiddenCount})`}
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
