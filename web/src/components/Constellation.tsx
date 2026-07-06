import { useEffect, useMemo, useRef, useState } from 'react'
import type { Goal, Strategy, StrategyEdge } from '../lib/types'
import { layoutConstellation } from '../lib/layout'
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
  selectedId: number | null
  onSelect: (id: number | null) => void
}

/** status → { fill, stroke, glow } for the star dot */
function nodeStyle(g: Goal): { fill: string; stroke: string; glow: boolean; opacity: number } {
  switch (g.status) {
    case 'proved':
      return { fill: 'var(--color-star)', stroke: 'var(--color-star)', glow: true, opacity: 1 }
    case 'attempting':
      return { fill: 'var(--color-accent)', stroke: 'var(--color-accent)', glow: true, opacity: 1 }
    case 'open':
      return { fill: 'transparent', stroke: 'var(--color-accent)', glow: false, opacity: 0.9 }
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

export default function Constellation({
  goals,
  strategies,
  strategyEdges,
  selectedId,
  onSelect,
}: Props) {
  const layout = useMemo(
    () => layoutConstellation(goals, strategies, strategyEdges),
    [goals, strategies, strategyEdges],
  )
  const byId = useMemo(
    () => new Map(layout.nodes.map((n) => [n.goal.id, n])),
    [layout],
  )

  const containerRef = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<{ k: number; tx: number; ty: number } | null>(null)
  const [hovered, setHovered] = useState<LayoutNode | null>(null)
  const [showDead, setShowDead] = useState(false)
  const drag = useRef<{ x: number; y: number; tx: number; ty: number; moved: boolean } | null>(null)

  // Initial fit — once per problem (not per poll: the layout is stable,
  // and refitting under the user's zoom would fight them).
  useEffect(() => {
    setView(null)
  }, [goals.length > 0 && goals[0].lean_path.split('/')[1]])
  useEffect(() => {
    if (view !== null) return
    const el = containerRef.current
    if (!el || layout.nodes.length === 0) return
    const { width: cw, height: ch } = el.getBoundingClientRect()
    const k = Math.min(cw / layout.width, ch / layout.height, 1.3)
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

  const visibleEdges = layout.edges.filter(
    (e) =>
      showDead ||
      e.kind === 'alias' ||
      (e.strategyStatus !== 'dead' && e.strategyStatus !== 'superseded'),
  )
  const deadEdgeCount = layout.edges.length - visibleEdges.length

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
        className="h-full w-full"
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
        </defs>
        <g transform={`translate(${tx},${ty}) scale(${k})`}>
          {visibleEdges.map((e, i) => {
            const a = byId.get(e.from)
            const b = byId.get(e.to)
            if (!a || !b) return null
            const dead = e.strategyStatus === 'dead' || e.strategyStatus === 'superseded'
            const stroke =
              e.kind === 'alias'
                ? 'var(--color-accent)'
                : e.strategyStatus === 'succeeded'
                  ? 'var(--color-star)'
                  : dead
                    ? 'var(--color-edge)'
                    : 'var(--color-edge-strong)'
            return (
              <line
                key={i}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={stroke}
                strokeWidth={e.strategyStatus === 'succeeded' ? 1.4 : 1}
                strokeOpacity={dead ? 0.35 : e.kind === 'alias' ? 0.5 : 0.55}
                strokeDasharray={e.kind === 'alias' ? '4 4' : undefined}
                vectorEffect="non-scaling-stroke"
              />
            )
          })}
          {layout.nodes.map((n) => {
            const s = nodeStyle(n.goal)
            const r = radius(n.goal)
            const selected = n.goal.id === selectedId
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
                {selected && (
                  <circle
                    r={r + 6}
                    fill="none"
                    stroke="var(--color-ink)"
                    strokeWidth={1}
                    strokeOpacity={0.8}
                    strokeDasharray="2 3"
                  />
                )}
                <circle
                  r={r}
                  fill={s.fill}
                  stroke={s.stroke}
                  strokeWidth={1.4}
                  opacity={s.opacity}
                  filter={s.glow ? 'url(#star-glow)' : undefined}
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
                {n.goal.is_deliverable && (
                  <circle r={r + 3} fill="none" stroke={s.stroke} strokeWidth={0.7} opacity={0.6} />
                )}
                {showLabels && (
                  <text
                    // Stagger label rows by in-layer parity so long
                    // slugs on adjacent stars don't collide; offsets are
                    // screen-constant like the font.
                    y={r + (n.col % 2 === 0 ? 14 : 26) / k}
                    textAnchor="middle"
                    className="pointer-events-none select-none"
                    fill={selected ? 'var(--color-ink)' : 'var(--color-ink-dim)'}
                    fontSize={10.5 / k}
                    fontFamily="var(--font-mono)"
                  >
                    {k >= 2 || n.goal.slug.length <= 16
                      ? n.goal.slug
                      : `${n.goal.slug.slice(0, 7)}…${n.goal.slug.slice(-7)}`}
                  </text>
                )}
              </g>
            )
          })}
        </g>
      </svg>

      {hovered && view !== null && (
        <div
          className="pointer-events-none absolute z-10 max-w-sm rounded-md border border-edge-strong bg-surface-2 px-3 py-2 shadow-lg"
          style={{
            left: tx + hovered.x * k + 14,
            top: ty + hovered.y * k + 14,
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

      {deadEdgeCount > 0 && (
        <button
          className="absolute right-3 bottom-3 rounded-md border border-edge bg-surface px-2.5 py-1 text-xs text-ink-dim hover:border-edge-strong hover:text-ink"
          onClick={() => setShowDead((v) => !v)}
        >
          {showDead ? 'hide' : 'show'} dead paths ({deadEdgeCount})
        </button>
      )}
    </div>
  )
}
