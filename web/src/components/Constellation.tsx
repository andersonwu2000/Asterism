import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { Goal, Strategy, StrategyEdge } from '../lib/types'
import { frontierView, layoutConstellation } from '../lib/layout'
import { Lean } from '../lib/lean'
import { goalStatusLabel } from '../lib/vocab'
import type { ConstellationLayout, LayoutNode } from '../lib/layout'

/*
 * The constellation view (charter §3.3 + appendix): goals as stars in a
 * layered DAG. Far = pure dots, near = slugs, hover = statement popover,
 * click = side-panel drill-down handled by the parent. Layout is
 * deterministic for a given graph; when the graph changes between polls
 * the stars GLIDE to their new places (and the camera re-frames an
 * untouched view), so a re-layout reads as motion, not as a new map.
 *
 * Rendering is budgeted for 400-star skies (charter §7): the heavy
 * layers (edges / routes / stars) are memoized JSX, so a pan re-renders
 * nothing and a zoom re-renders only on ~8% scale buckets; the glide is
 * applied imperatively (attribute writes per rAF frame, zero React
 * work); star glow is a radial-gradient halo, not a Gaussian filter —
 * a finished sky glows on ~300 stars at once and filters made every
 * repaint pay for that.
 */

/** poll-to-poll position tween: ~half a second, fast-out. Long enough
 * to read as motion, short enough to be over before the next poll. */
const ANIM_MS = 550
/** above this a sky stops animating and just jumps — even attribute
 * sweeps have a budget */
const ANIM_MAX = 400
const easeOut = (a: number) => 1 - (1 - a) ** 3

interface View {
  k: number
  tx: number
  ty: number
}

/** where the stars were LAST DRAWN (mid-tween capture makes an
 * interrupted glide continue smoothly instead of snapping back) */
interface Tween {
  t0: number
  fromPos: Map<number, { x: number; y: number }>
  fromJunc: Map<number, { x: number; y: number }>
  /** camera glide — only when the user hasn't zoomed or panned */
  fromView: View | null
  toView: View | null
}

/** Citation bow — single source for the initial render AND the
 * animator's per-frame rewrites. Bow grows with span (a fixed cap
 * flattened long horizontals back into wires); endpoint-id parity mixes
 * directions so parallel threads separate. */
function citePath(
  a: { x: number; y: number },
  b: { x: number; y: number },
  from: number,
  to: number,
): { d: string; len: number } {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  const bow = Math.min(150, len * 0.18) * ((from + to) % 2 === 0 ? 1 : -1)
  const mx = (a.x + b.x) / 2 + (-dy / len) * bow
  const my = (a.y + b.y) / 2 + (dx / len) * bow
  return { d: `M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`, len }
}

function computeFit(el: HTMLElement, l: ConstellationLayout): View {
  const { width: cw, height: ch } = el.getBoundingClientRect()
  // Fill the canvas: fit the content bounding box, allowing generous
  // magnification for small graphs (10 stars in a void read as a
  // failed page load — design review). Extra vertical air keeps the
  // floating legend row off the top band's stars.
  const kMax = l.nodes.length <= 10 ? 2.6 : 2.0
  const k = Math.min((cw - 48) / l.width, (ch - 88) / l.height, kMax)
  return {
    k,
    tx: (cw - l.width * k) / 2,
    ty: (ch - l.height * k) / 2 + 14,
  }
}

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
  // a "scene" = one problem in one focus mode; tweens never cross
  // scenes (goal ids from another problem may collide)
  const problemKey = goals.length > 0 ? goals[0].lean_path.split('/')[1] : ''
  const sceneKey = `${problemKey}:${focused}`

  const layout = useMemo(
    () =>
      layoutConstellation(shownGoals, strategies, strategyEdges, anchorEdges, citationEdges),
    [shownGoals, strategies, strategyEdges, anchorEdges, citationEdges],
  )
  // Label stagger is collision-avoidance for dense rows; in sparse rows
  // it reads as jitter, so apply it only where needed. Counted per
  // ACTUAL row (y) — counting per layer number pooled every band's
  // layer 0 into one figure and staggered sparse bands for nothing.
  const rowCounts = useMemo(() => {
    const m = new Map<number, number>()
    for (const n of layout.nodes) m.set(n.y, (m.get(n.y) ?? 0) + 1)
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
      const staggered = (rowCounts.get(n.y) ?? 0) > 8 && n.col % 2 === 1
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
  }, [layout, rowCounts])

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
  }, [problemKey, focused])
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
    const fit = computeFit(el, layout)
    fitKRef.current = fit.k
    setView(fit)
  }, [view, layout])

  // ---- poll-to-poll transition (imperative) --------------------------
  // A structure change re-layouts the whole sky (readability outranks
  // stillness — owner call); the tween keeps every star's IDENTITY
  // through the move. React always renders the TARGET sky; the animator
  // below interpolates by writing DOM attributes directly through the
  // element registries — at 370 nodes one React render costs ~10ms
  // (measured on stokes), an attribute sweep doesn't. Unrelated
  // re-renders (hover, selection) diff target-vs-target and so never
  // disturb a glide in flight.
  const viewRef = useRef<View | null>(view) // the DISPLAYED camera
  const camDriven = useRef(false) // animator owns the camera right now
  /** the current fit-to-view scale — big skies fit far below the old
   * hard 0.25 wheel floor (stokes fits at 0.17), which trapped anyone
   * who zoomed in: the wheel could never get back out to the fit */
  const fitKRef = useRef<number | null>(null)
  const shownPosRef = useRef(new Map<number, { x: number; y: number }>())
  const shownJuncRef = useRef(new Map<number, { x: number; y: number }>())
  const sceneRef = useRef<string | null>(null)
  const outerGRef = useRef<SVGGElement | null>(null)
  const nodeEls = useRef(new Map<number, SVGGElement>())
  const juncEls = useRef(new Map<number, SVGGElement>())
  const edgeEls = useRef(
    new Map<SVGElement, { from: number; to: number; cite: boolean }>(),
  )
  const stemEls = useRef(new Map<SVGLineElement, { parent: number; sid: number }>())
  const branchEls = useRef(new Map<SVGLineElement, { sid: number; child: number }>())
  const animRef = useRef({ raf: 0, timer: 0 })

  const k = view?.k ?? 1
  const tx = view?.tx ?? 0
  const ty = view?.ty ?? 0
  // wheel/buttons/drag compound from the DISPLAYED camera, so grabbing
  // the controls mid-glide continues from what the eye sees
  if (!camDriven.current) {
    viewRef.current = view === null ? null : { k, tx, ty }
  }
  const showLabels = k >= 1.05
  // Quantized zoom for the memoized layers: panning is k-free, and a
  // wheel burst re-renders content only when it crosses an ~8% bucket —
  // in between, the outer transform scales everything smoothly and the
  // compensated sizes ride within ±8% of ideal.
  const kq = useMemo(() => {
    const step = Math.log(1.08)
    return Math.exp(Math.round(Math.log(Math.max(k, 0.05)) / step) * step)
  }, [k])

  useLayoutEffect(() => {
    const sameScene = sceneRef.current === sceneKey
    sceneRef.current = sceneKey
    const anim = animRef.current
    const stop = () => {
      if (anim.raf) cancelAnimationFrame(anim.raf)
      if (anim.timer) window.clearTimeout(anim.timer)
      anim.raf = 0
      anim.timer = 0
      camDriven.current = false
    }
    const targets = new Map(layout.nodes.map((n) => [n.goal.id, { x: n.x, y: n.y }]))
    const juncTargets = new Map(
      layout.bundles.map((b) => [b.strategyId, { x: b.junction.x, y: b.junction.y }]),
    )
    if (containerRef.current) {
      fitKRef.current = computeFit(containerRef.current, layout).k
    }
    let moved = false
    if (sameScene && shownPosRef.current.size > 0 && layout.nodes.length <= ANIM_MAX) {
      for (const [id, t] of targets) {
        const q = shownPosRef.current.get(id)
        if (q && Math.hypot(q.x - t.x, q.y - t.y) > 0.5) {
          moved = true
          break
        }
      }
    }
    if (!moved) {
      // new scene, oversized sky, or nothing moved: the freshly rendered
      // targets ARE the picture
      stop()
      shownPosRef.current = targets
      shownJuncRef.current = juncTargets
      return
    }
    stop()
    const glide =
      !userAdjusted.current && containerRef.current !== null && viewRef.current !== null
    const tween: Tween = {
      t0: performance.now(),
      fromPos: new Map(shownPosRef.current),
      fromJunc: new Map(shownJuncRef.current),
      fromView: glide ? { ...viewRef.current! } : null,
      toView: glide ? computeFit(containerRef.current!, layout) : null,
    }
    camDriven.current = tween.toView !== null

    const apply = (alpha: number) => {
      const shown = new Map<number, { x: number; y: number }>()
      for (const [id, t] of targets) {
        const f = tween.fromPos.get(id)
        const x = f ? f.x + (t.x - f.x) * alpha : t.x
        const y = f ? f.y + (t.y - f.y) * alpha : t.y
        shown.set(id, { x, y })
        nodeEls.current.get(id)?.setAttribute('transform', `translate(${x},${y})`)
      }
      shownPosRef.current = shown
      const shownJ = new Map<number, { x: number; y: number }>()
      for (const [sid, t] of juncTargets) {
        const f = tween.fromJunc.get(sid)
        const x = f ? f.x + (t.x - f.x) * alpha : t.x
        const y = f ? f.y + (t.y - f.y) * alpha : t.y
        shownJ.set(sid, { x, y })
        juncEls.current.get(sid)?.setAttribute('transform', `translate(${x},${y})`)
      }
      shownJuncRef.current = shownJ
      for (const [el, m] of edgeEls.current) {
        const a = shown.get(m.from)
        const b = shown.get(m.to)
        if (!a || !b) continue
        if (m.cite) {
          el.setAttribute('d', citePath(a, b, m.from, m.to).d)
        } else {
          el.setAttribute('x1', String(a.x))
          el.setAttribute('y1', String(a.y))
          el.setAttribute('x2', String(b.x))
          el.setAttribute('y2', String(b.y))
        }
      }
      for (const [el, m] of stemEls.current) {
        const a = shown.get(m.parent)
        const j = shownJ.get(m.sid)
        if (!a || !j) continue
        el.setAttribute('x1', String(a.x))
        el.setAttribute('y1', String(a.y))
        el.setAttribute('x2', String(j.x))
        el.setAttribute('y2', String(j.y))
      }
      for (const [el, m] of branchEls.current) {
        const j = shownJ.get(m.sid)
        const c = shown.get(m.child)
        if (!j || !c) continue
        el.setAttribute('x1', String(j.x))
        el.setAttribute('y1', String(j.y))
        el.setAttribute('x2', String(c.x))
        el.setAttribute('y2', String(c.y))
      }
      if (tween.fromView && tween.toView && !userAdjusted.current) {
        const f = tween.fromView
        const g = tween.toView
        const cam = {
          k: f.k + (g.k - f.k) * alpha,
          tx: f.tx + (g.tx - f.tx) * alpha,
          ty: f.ty + (g.ty - f.ty) * alpha,
        }
        viewRef.current = cam
        outerGRef.current?.setAttribute(
          'transform',
          `translate(${cam.tx},${cam.ty}) scale(${cam.k})`,
        )
      }
    }
    let done = false
    const finish = () => {
      if (done) return
      done = true
      apply(1)
      stop()
      // commit the camera through React with a FRESH fit — the derive-
      // time toView goes stale if the container resized mid-glide
      if (tween.toView && !userAdjusted.current && containerRef.current) {
        setView(computeFit(containerRef.current, layout))
      }
    }
    const step = () => {
      if (done) return
      const a = (performance.now() - tween.t0) / ANIM_MS
      if (a >= 1) {
        finish()
        return
      }
      apply(easeOut(a))
      anim.raf = requestAnimationFrame(step)
    }
    apply(0) // before paint: the freshly rendered targets must not flash
    anim.raf = requestAnimationFrame(step)
    // rAF starves in occluded/hidden tabs — the timer guarantees the
    // tween still ENDS there (a frozen half-glide reads as breakage)
    anim.timer = window.setTimeout(finish, ANIM_MS + 50)
    return () => {
      done = true
      stop()
    }
  }, [layout, sceneKey])

  // Wheel zoom must preventDefault (page would scroll); React's
  // delegated wheel handlers are passive, so attach natively.
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
      // the floor must sit BELOW the fit, or zooming in becomes a trap
      const kLo = Math.min(0.25, (fitKRef.current ?? 1) * 0.5)
      const nk = Math.min(4, Math.max(kLo, v.k * factor))
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
    const v = viewRef.current
    if (v === null) return
    // base the drag on the DISPLAYED camera (a glide may be driving it)
    drag.current = { x: e.clientX, y: e.clientY, tx: v.tx, ty: v.ty, moved: false }
    ;(e.target as Element).setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current
    const v = viewRef.current
    if (!d || v === null) return
    const dx = e.clientX - d.x
    const dy = e.clientY - d.y
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true
    if (d.moved) {
      userAdjusted.current = true
      setView({ k: v.k, tx: d.tx + dx, ty: d.ty + dy })
    }
  }
  const onPointerUp = (e: React.PointerEvent) => {
    const d = drag.current
    drag.current = null
    if (d && !d.moved && (e.target as Element).tagName === 'svg') onSelect(null)
  }

  // the incoming callbacks may be fresh lambdas every parent render —
  // route them through refs so the memoized layers can hold still
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect
  const selectCb = useCallback((id: number) => onSelectRef.current(id), [])
  const onSelectStrategyRef = useRef(onSelectStrategy)
  onSelectStrategyRef.current = onSelectStrategy
  const selectStrategyCb = useCallback(
    (id: number) => onSelectStrategyRef.current?.(id),
    [],
  )
  const hasStrategyClick = onSelectStrategy !== undefined

  const isDead = (s: string) => s === 'dead' || s === 'superseded'
  const visibleEdges = useMemo(
    () =>
      layout.edges.filter(
        (e) => showDead || e.kind === 'alias' || !isDead(e.strategyStatus),
      ),
    [layout, showDead],
  )
  const visibleBundles = useMemo(
    () => layout.bundles.filter((b) => showDead || !isDead(b.status)),
    [layout, showDead],
  )
  // density-stepped: a handful of citations read at 0.22; a hundred
  // would wash the sky at that weight
  const citeCount = useMemo(
    () => visibleEdges.filter((e) => e.kind === 'citation').length,
    [visibleEdges],
  )
  const citeOpacity = citeCount > 80 ? 0.08 : citeCount > 30 ? 0.13 : 0.22
  // hover/selection focus: point at a star with citation threads and
  // its threads carry the light while the rest of the web recedes —
  // "where is this actually used" answered in place (cold-eye backlog).
  // Null unless the focus target HAS citations, so hovering ordinary
  // stars leaves the memoized edge layer untouched.
  const focusId = hovered?.goal.id ?? selectedId
  const citeFocusId =
    focusId !== null &&
    visibleEdges.some(
      (e) => e.kind === 'citation' && (e.from === focusId || e.to === focusId),
    )
      ? focusId
      : null
  const deadEdgeCount =
    layout.edges.length -
    visibleEdges.length +
    layout.bundles.filter((b) => isDead(b.status)).length

  const byId = useMemo(
    () => new Map(layout.nodes.map((n) => [n.goal.id, n])),
    [layout],
  )

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

  // ---- memoized layers ----------------------------------------------
  // Each layer's JSX is cached until ITS inputs change: panning touches
  // none of them (one transform write), zooming only crosses kq buckets,
  // hovering re-renders the edge layer only when the target has
  // citation threads. All positions are layout targets — the animator
  // moves them between renders.
  const dustEl = useMemo(
    () => (
      <>
        {dust.map((d, i) => (
          <circle
            key={`d${i}`}
            cx={d.x}
            cy={d.y}
            r={(d.r * 0.8) / Math.max(kq, 0.5)}
            fill="var(--color-ink)"
            opacity={d.o * 0.45}
          />
        ))}
      </>
    ),
    [dust, kq],
  )

  const edgesEl = useMemo(
    () => (
      <>
        {visibleEdges.map((e, i) => {
          const a = byId.get(e.from)
          const b = byId.get(e.to)
          if (!a || !b) return null
          const dead = isDead(e.strategyStatus)
          const reg = (el: SVGElement | null) => {
            if (!el) return
            edgeEls.current.set(el, {
              from: e.from,
              to: e.to,
              cite: e.kind === 'citation',
            })
            return () => {
              edgeEls.current.delete(el)
            }
          }
          if (e.kind === 'citation') {
            // Citations bow sideways as quiet threads: parallel long
            // straights merge into fog on cite-heavy skies (sphere:
            // 100+ edges); a bow separates neighbours, and opacity
            // steps down with density so the trees stay in front.
            const { d, len } = citePath(a, b, e.from, e.to)
            // long hauls fade further: a cross-sky thread is context,
            // not content — nearby citations stay readable
            const fade = Math.min(1, Math.max(0.35, 320 / len))
            const touched =
              citeFocusId !== null && (e.from === citeFocusId || e.to === citeFocusId)
            return (
              <path
                key={i}
                ref={reg}
                d={d}
                fill="none"
                stroke={edgeStroke(e.strategyStatus, e.kind)}
                strokeWidth={touched ? 1.4 : 1}
                strokeOpacity={
                  touched
                    ? Math.max(0.55, citeOpacity * fade)
                    : citeFocusId !== null
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
              ref={reg}
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
      </>
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleEdges, byId, citeFocusId, citeOpacity],
  )

  const bundlesEl = useMemo(
    () => (
      <>
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
                ref={(el) => {
                  if (!el) return
                  stemEls.current.set(el, { parent: b.parentId, sid: b.strategyId })
                  return () => {
                    stemEls.current.delete(el)
                  }
                }}
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
                    ref={(el) => {
                      if (!el) return
                      branchEls.current.set(el, { sid: b.strategyId, child: cid })
                      return () => {
                        branchEls.current.delete(el)
                      }
                    }}
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
              <g
                ref={(el) => {
                  if (!el) return
                  juncEls.current.set(b.strategyId, el)
                  return () => {
                    juncEls.current.delete(b.strategyId)
                  }
                }}
                transform={`translate(${b.junction.x},${b.junction.y})`}
              >
                <circle r={2.1} fill={stroke} opacity={opacity} />
                {hasStrategyClick && (
                  <>
                    {/* a faint ring says "this fork is a thing you can
                        open" — the bare hit area was undiscoverable */}
                    <circle
                      r={5}
                      fill="none"
                      stroke={stroke}
                      strokeWidth={0.8}
                      opacity={opacity * 0.35}
                      vectorEffect="non-scaling-stroke"
                    />
                    <circle
                      r={9}
                      fill="transparent"
                      className="cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation()
                        selectStrategyCb(b.strategyId)
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
            </g>
          )
        })}
      </>
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleBundles, byId, hasStrategyClick, selectStrategyCb],
  )

  const nodesEl = useMemo(() => {
    // Zoom-honest sizing that PRESERVES the hierarchy: the old absolute
    // floor bottomed root, claim and step out at the same ~7px dot, so
    // a survey view erased exactly the marks it exists to show (owner:
    // anchor + claim are the only nodes the user NEEDS). One shared
    // boost scales every class — and the ring offsets — together; the
    // cap keeps the biggest stars inside their slot on 500-star skies.
    const boost = Math.min(Math.max(1, 0.78 / kq), 4)
    return (
      <>
        {layout.nodes.map((n) => {
          const s = nodeStyle(n.goal, hasLive)
          const live =
            n.goal.status === 'open' ||
            n.goal.status === 'attempting' ||
            n.goal.status === 'pending_strategist_review'
          const r = (radius(n.goal) + (live ? 1.5 : 0)) * boost
          const lod = kq < 0.8
          const fill = lod && live ? s.stroke : s.fill
          const selected = n.goal.id === selectedId
          // Attempts heat ring: arc fraction of the shelve threshold,
          // only meaningful while the goal is still being worked.
          const heatFrac =
            live && n.goal.attempts > 0
              ? Math.min(n.goal.attempts / shelveThreshold, 1)
              : 0
          const heatR = r + 3 * boost
          const heatC = 2 * Math.PI * heatR
          return (
            <g
              key={n.goal.id}
              ref={(el) => {
                if (!el) return
                nodeEls.current.set(n.goal.id, el)
                return () => {
                  nodeEls.current.delete(n.goal.id)
                }
              }}
              transform={`translate(${n.x},${n.y})`}
              className="cursor-pointer"
              onMouseEnter={() => setHovered(n)}
              onMouseLeave={() => setHovered(null)}
              onClick={(e) => {
                e.stopPropagation()
                selectCb(n.goal.id)
              }}
            >
              {/* glow = a radial-gradient halo UNDER the star; the old
                  per-star Gaussian filter made a finished sky (300
                  glowing stars) pay filter cost on every repaint */}
              {s.glow && (
                <circle
                  r={r * 2.5}
                  fill="url(#star-halo)"
                  opacity={s.opacity}
                  pointerEvents="none"
                />
              )}
              {/* Two orthogonal axes, two channels (owner): IDENTITY
                  speaks in ring + shape + size — THE permanent ring is
                  a single ring = the signed surface (root, claim,
                  anchor); STATUS speaks in brightness + blink and never
                  borrows a ring. Activity marks keep disjoint slots:
                  heat arc r+3, signed ring r+5.5, selection r+9,
                  birth halo r+12. */}
              {(n.goal.origin === 'root' ||
                n.goal.is_deliverable ||
                DEF_KINDS.has(n.goal.kind)) && (
                <circle
                  r={r + 5.5 * boost}
                  fill="none"
                  stroke={s.stroke}
                  strokeWidth={1.2}
                  opacity={s.opacity * 0.75}
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {selected && (
                <circle
                  r={r + 9 * boost}
                  fill="none"
                  stroke="var(--color-ink)"
                  strokeWidth={1}
                  strokeOpacity={0.8}
                  strokeDasharray="2 3"
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {/* defs are the meaning-bearers (the anchor surface a
                  human vouches for) — diamonds above the shape-
                  perception threshold (~5px), circles below it;
                  Props are the light and stay round */}
              {DEF_KINDS.has(n.goal.kind) && r * kq >= 4.2 ? (
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
                  vectorEffect="non-scaling-stroke"
                >
                  {/* working = the star itself BLINKS (owner: no ring
                      for activity) — gated on daemon liveness */}
                  {engineWorking &&
                    (n.goal.status === 'attempting' || n.goal.in_flight) && (
                      <animate
                        attributeName="opacity"
                        values="1;0.35;1"
                        dur="1.4s"
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
                  vectorEffect="non-scaling-stroke"
                >
                  {/* working = the star itself BLINKS (owner: no ring
                      for activity) — gated on daemon liveness */}
                  {engineWorking &&
                    (n.goal.status === 'attempting' || n.goal.in_flight) && (
                      <animate
                        attributeName="opacity"
                        values="1;0.35;1"
                        dur="1.4s"
                        repeatCount="indefinite"
                      />
                    )}
                </circle>
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
                  r={r + 12 * boost}
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
              {focused && (frontier.folded.get(n.goal.id) ?? 0) > 0 && (
                <text
                  x={r + 4 / kq}
                  y={-r}
                  className="pointer-events-none select-none"
                  fill="var(--color-ink-faint)"
                  fontSize={9.5 / kq}
                  fontFamily="var(--font-mono)"
                >
                  +{frontier.folded.get(n.goal.id)}
                </text>
              )}
              {(showLabels ||
                n.goal.origin === 'root' ||
                n.goal.is_deliverable) && (
                <text
                  // Stagger label rows by in-row parity so long slugs
                  // on adjacent stars don't collide; offsets are
                  // screen-constant like the font. Truncation is
                  // width-aware: never truncate into empty space.
                  // Root + claims stay labelled at ANY zoom — the
                  // survey view needs its landmarks named.
                  y={
                    r * (n.goal.is_deliverable || n.goal.origin === 'root' ? 1.6 : 1) +
                    ((rowCounts.get(n.y) ?? 0) > 8 && n.col % 2 === 1 ? 26 : 15) / kq
                  }
                  textAnchor="middle"
                  className="pointer-events-none select-none"
                  fill={selected ? 'var(--color-ink)' : 'var(--color-ink-dim)'}
                  fontSize={10.5 / kq}
                  fontFamily="var(--font-mono)"
                >
                  {(() => {
                    // budget from ACTUAL neighbour room: fair split
                    // of each gap, plus whatever a short neighbour
                    // doesn't need (mono ≈6.4px/char on screen)
                    const rm = labelRoom.get(n.goal.id)
                    const side = (gap: number, nbrLen: number) => {
                      if (!Number.isFinite(gap)) return Infinity
                      const gapPx = gap * kq
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
      </>
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
      layout,
      kq,
      showLabels,
      selectedId,
      hasLive,
      engineWorking,
      shelveThreshold,
      focused,
      frontier,
      labelRoom,
      rowCounts,
      selectCb,
    ])

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
          {/* star glow as a gradient halo — one shared paint server,
              instead of a Gaussian filter evaluated per glowing star */}
          <radialGradient id="star-halo">
            <stop offset="0%" stopColor="var(--color-starlight)" stopOpacity="0.5" />
            <stop offset="40%" stopColor="var(--color-starlight)" stopOpacity="0.16" />
            <stop offset="100%" stopColor="var(--color-starlight)" stopOpacity="0" />
          </radialGradient>
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
        <g ref={outerGRef} transform={`translate(${tx},${ty}) scale(${k})`}>
          {dustEl}
          {edgesEl}
          {bundlesEl}
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
          {nodesEl}
        </g>
      </svg>

      {/* the selected node's facts live in the side panel — no echo */}
      {hovered && hovered.goal.id !== selectedId && view !== null && (
        <div
          className="pointer-events-none absolute z-10 max-w-sm rounded-md border border-edge-strong bg-surface-3 px-3 py-2"
          style={{
            left: Math.min(
              tx + (shownPosRef.current.get(hovered.goal.id) ?? hovered).x * k + 14,
              (containerRef.current?.clientWidth ?? 800) - 340,
            ),
            top: Math.min(
              ty + (shownPosRef.current.get(hovered.goal.id) ?? hovered).y * k + 14,
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
            <Lean code={hovered.goal.statement} />
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
        {/* grouped: star status | landmark marks | line kinds — and the
            status icons must MATCH the sky (the old "open" swatch drew a
            hollow accent ring that exists nowhere) */}
        <div
          className={`pointer-events-none mt-1 ${legendOpen ? 'flex' : 'hidden'} flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-surface/90 px-2.5 py-1 text-[11px] text-ink-faint`}
        >
        {/* STATUS group — swatches carry the TRUE inking (brightness,
            blink); the shape is fixed so only the status axis varies */}
        <span className="flex items-center gap-1" title="not yet proved — the engine still owes this star">
          <svg width="13" height="13" viewBox="-5 -5 10 10">
            <circle r="3.4" fill="var(--color-star)" stroke="var(--color-starlight)" strokeWidth="0.9" />
          </svg>
          open
        </span>
        <span
          className="flex items-center gap-1"
          title="the engine is writing this star right now — it blinks"
        >
          <svg width="13" height="13" viewBox="-5 -5 10 10">
            <circle r="3.2" fill="var(--color-starlight)">
              <animate
                attributeName="opacity"
                values="1;0.3;1"
                dur="1.4s"
                repeatCount="indefinite"
              />
            </circle>
          </svg>
          working
        </span>
        <span
          className="flex items-center gap-1"
          title={
            hasLive
              ? 'proved — recedes to the background while work continues'
              : 'proved — a finished sky lets them shine'
          }
        >
          <svg width="13" height="13" viewBox="-5 -5 10 10">
            <circle r="3" fill="var(--color-starlight)" opacity={hasLive ? 0.5 : 1} />
          </svg>
          proved
        </span>
        <span className="flex items-center gap-1" title="set aside after repeated failed attempts">
          <svg width="13" height="13" viewBox="-5 -5 10 10">
            <circle r="3" fill="var(--color-ink-faint)" opacity="0.6" />
          </svg>
          shelved
        </span>
        <span className="flex items-center gap-1" title="an abandoned path (edges hidden behind “show dead paths”)">
          <svg width="13" height="13" viewBox="-5 -5 10 10">
            <circle r="2.6" fill="var(--color-edge-strong)" opacity="0.55" />
          </svg>
          dead
        </span>
        <span
          className="flex items-center gap-1"
          title="failed attempts burned on a live star — the arc fills toward the shelving threshold"
        >
          <svg width="15" height="15" viewBox="-6 -6 12 12">
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
        <span className="h-3 w-px bg-edge" />
        {/* IDENTITY group — neutral tone on purpose: here only ring,
            shape and size speak; brightness belongs to the status axis */}
        <span
          className="flex items-center gap-1"
          title="the problem's own statement — the largest ringed star"
        >
          <svg width="19" height="19" viewBox="-9 -9 18 18">
            <circle r="6.6" fill="none" stroke="var(--color-ink-dim)" strokeWidth="1" opacity="0.8" />
            <circle r="3.6" fill="var(--color-ink-dim)" />
          </svg>
          root
        </span>
        <span
          className="flex items-center gap-1"
          title="a top-level result you sign off on — the ring marks everything the human vouches for"
        >
          <svg width="17" height="17" viewBox="-8 -8 16 16">
            <circle r="5.6" fill="none" stroke="var(--color-ink-dim)" strokeWidth="1" opacity="0.8" />
            <circle r="2.7" fill="var(--color-ink-dim)" />
          </svg>
          claim
        </span>
        <span
          className="flex items-center gap-1"
          title="a definition the claims are made of — vouching a claim vouches its anchors (the diamond marks a def)"
        >
          <svg width="17" height="17" viewBox="-8 -8 16 16">
            <circle r="5.6" fill="none" stroke="var(--color-ink-dim)" strokeWidth="1" opacity="0.8" />
            <rect x="-2" y="-2" width="4" height="4" transform="rotate(45)" fill="var(--color-ink-dim)" />
          </svg>
          anchor
        </span>
        <span
          className="flex items-center gap-1"
          title="an unringed star is an intermediate step — its brightness is its status; the ring is what you sign"
        >
          <svg width="13" height="13" viewBox="-5 -5 10 10">
            <circle r="2" fill="var(--color-ink-dim)" opacity="0.8" />
          </svg>
          step
        </span>
        <span className="h-3 w-px bg-edge" />
        <span
          className="flex items-center gap-1"
          title="a fork needs ALL its branches (one route); two forks on one star are competing routes — click a fork for details"
        >
          <svg width="15" height="15" viewBox="0 0 12 12">
            <line x1="6" y1="1" x2="6" y2="5" stroke="var(--color-starlight)" strokeWidth="1" opacity="0.6" />
            <line x1="6" y1="5" x2="2" y2="11" stroke="var(--color-starlight)" strokeWidth="1" opacity="0.6" />
            <line x1="6" y1="5" x2="10" y2="11" stroke="var(--color-starlight)" strokeWidth="1" opacity="0.6" />
            <circle cx="6" cy="5" r="1.6" fill="var(--color-starlight)" opacity="0.8" />
          </svg>
          route
        </span>
        <span className="flex items-center gap-1" title="one proof imports another — the lemma is used there">
          <svg width="18" height="13" viewBox="0 0 14 10">
            <line x1="1" y1="8" x2="13" y2="2" stroke="var(--color-starlight)" strokeWidth="1" opacity="0.45" />
          </svg>
          cites
        </span>
        <span className="flex items-center gap-1">
          <svg width="18" height="13" viewBox="0 0 14 10">
            <line x1="1" y1="5" x2="13" y2="5" stroke="var(--color-accent)" strokeWidth="1" strokeDasharray="3 2.5" opacity="0.7" />
          </svg>
          alias
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
              const kLo = Math.min(0.25, (fitKRef.current ?? 1) * 0.5)
              const nk = Math.min(4, Math.max(kLo, v.k * factor))
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
