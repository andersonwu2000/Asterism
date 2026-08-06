import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { Goal, Strategy, StrategyEdge } from '../lib/types'
import { CameraControls, useSkyCamera } from '../lib/camera'
import { splitSignature } from '../lib/leanSig'
import { layoutConstellation } from '../lib/layout'
import { Lean } from '../lib/lean'
import { citePath } from '../lib/sky'
import { DEF_KINDS, goalStatusLabel } from '../lib/vocab'
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

/** finished layouts, content-keyed, shared across mounts — a revisited
 * sky must not re-pay the engine (0.5s at 500 stars). Insertion order
 * doubles as recency (Map iterates oldest-first). */
const layoutLRU = new Map<string, ConstellationLayout>()
const LAYOUT_LRU_MAX = 8

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

function computeFit(el: HTMLElement, l: ConstellationLayout): View {
  const { width: cw, height: ch } = el.getBoundingClientRect()
  // Fill the canvas: fit the content bounding box, allowing generous
  // magnification for small graphs (10 stars in a void read as a
  // failed page load — design review). Extra vertical air keeps the
  // floating legend row off the top band's stars.
  const kMax = l.nodes.length <= 10 ? 2.6 : 2.0
  let k = Math.min((cw - 48) / l.width, (ch - 88) / l.height, kMax)
  if (k >= 1.05 && l.nodes.length > 0) {
    // labels render at this zoom, screen-constant (10.5px mono,
    // centred): an edge node's half-label hangs OUTSIDE the node
    // bounding box and got cropped (Run's trophy sky). Budget the
    // widest half-label; if that would push k below the label
    // threshold, sit just under it instead — no labels, no crop.
    const maxChars = Math.max(...l.nodes.map((n) => n.goal.slug.length))
    const halfLabel = Math.min((maxChars * 6.4) / 2, cw / 4)
    const k2 = Math.min(k, (cw - 48 - 2 * halfLabel) / l.width)
    k = k2 >= 1.05 ? k2 : Math.min(k, 1.049)
  }
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
  /** stars to light up transiently (the goal panel's route hover) —
   * a pointer echo, not a selection */
  highlightIds?: number[] | null
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
  highlightIds = null,
}: Props) {
  // The sky ALWAYS shows everything (owner: the stars that need you
  // are already the brightest). Frontier folding and the dead-paths
  // toggle are retired — hiding structure read as bugs, not focus.
  const [legendOpen, setLegendOpen] = useState<boolean>(() => {
    try {
      return localStorage.getItem('cst-legend') !== 'closed'
    } catch {
      return true
    }
  })
  // ink inversion gate: while anything is live the unproved few carry
  // the light; a finished sky lets the proved shine
  const hasLive = goals.some(
    (g) =>
      g.status === 'open' ||
      g.status === 'attempting' ||
      g.status === 'pending_strategist_review',
  )
  // a "scene" = one problem; tweens never cross scenes (goal ids from
  // another problem may collide)
  const problemKey = goals.length > 0 ? goals[0].lean_path.split('/')[1] : ''
  const sceneKey = problemKey

  // Layout is keyed on CONTENT, not poll identity: every 2s poll hands
  // back fresh arrays, and re-running the ~0.5s layout engine per tick
  // during a live run was pure waste (the sky rarely changes shape).
  // The signature covers exactly what geometry depends on — the node
  // set, statuses (dead paths draw differently), and the edge lists.
  // The signature must cover every MUTABLE field the render layer
  // reads through the cached layout's captured objects (n.goal.*,
  // edge.strategyStatus) — a field left out would render stale ink
  // until something else changed. Geometry itself only depends on the
  // node set and edge lists.
  const layoutSig = useMemo(() => {
    let a = 0
    const mix = (s: string): void => {
      for (let i = 0; i < s.length; i++) a = (a * 31 + s.charCodeAt(i)) | 0
    }
    for (const g of goals)
      mix(`${g.id}:${g.status}:${g.attempts}:${g.dead_attempts}:${g.in_flight ? 1 : 0}:${g.is_deliverable ? 1 : 0};`)
    for (const s of strategies) mix(`${s.id}:${s.status};`)
    for (const e of strategyEdges) mix(`${e.strategy_id}>${e.subgoal_id}:${e.position};`)
    for (const e of anchorEdges) mix(`${e.from}>${e.to};`)
    for (const e of citationEdges) mix(`${e.from}>${e.to};`)
    return `${goals.length}|${strategies.length}|${strategyEdges.length}|${anchorEdges.length}|${citationEdges.length}#${a}`
  }, [goals, strategies, strategyEdges, anchorEdges, citationEdges])
  const layout = useMemo(() => {
    // Module-level LRU, not a per-mount ref: navigating Board → Problem
    // → Board → Problem re-paid the full engine run (0.5s at 500 stars,
    // ON the main thread) for a sky that hadn't changed. The signature
    // already guarantees ink freshness, so a cross-mount hit is exactly
    // as safe as the old in-mount hit — revisiting a big sky is now
    // instant (owner asked for faster entry, 2026-07-12).
    const hit = layoutLRU.get(layoutSig)
    if (hit) {
      layoutLRU.delete(layoutSig)
      layoutLRU.set(layoutSig, hit) // refresh recency
      return hit
    }
    const v = layoutConstellation(goals, strategies, strategyEdges, anchorEdges, citationEdges)
    layoutLRU.set(layoutSig, v)
    if (layoutLRU.size > LAYOUT_LRU_MAX) {
      const oldest = layoutLRU.keys().next().value
      if (oldest !== undefined) layoutLRU.delete(oldest)
    }
    return v
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sig IS the content key
  }, [layoutSig])
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
  // halo so a live run reads as growth, not as a diff you must spot.
  // Expiry must DRIVE a re-render: the halo lives inside the memoized
  // node layer, and a map sweep nothing depends on left rings pulsing
  // until the next structural change — minutes on a quiet sky (owner:
  // "new nodes grow rings by themselves", 2026-07-12). Each birth
  // schedules its own curfew; birthTick invalidates the layer.
  const birthsRef = useRef<{ seen: Set<number>; born: Map<number, number>; primed: boolean }>({
    seen: new Set(),
    born: new Map(),
    primed: false,
  })
  const [birthTick, setBirthTick] = useState(0)
  const birthTimers = useRef<Set<number>>(new Set())
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
        const timer = window.setTimeout(() => {
          birthTimers.current.delete(timer)
          b.born.delete(g.id)
          setBirthTick((t) => t + 1)
        }, 12000)
        birthTimers.current.add(timer)
      }
    }
  }, [goals])
  useEffect(
    () => () => {
      for (const t of birthTimers.current) window.clearTimeout(t)
    },
    [],
  )

  // afterglow: a star that just turned PROVED keeps a hot halo that
  // cools over ~15 minutes — "what lit up while I was away" read
  // straight off the sky (design round, two reviewers independently).
  // Brightness-as-recency, grayscale-native. Decay steps schedule
  // their own re-renders (the node layer is memoized).
  const glowRef = useRef<{ status: Map<number, string>; lit: Map<number, number>; primed: boolean }>({
    status: new Map(),
    lit: new Map(),
    primed: false,
  })
  const [glowTick, setGlowTick] = useState(0)
  const glowTimers = useRef<Set<number>>(new Set())
  useEffect(() => {
    const g = glowRef.current
    if (!g.primed) {
      for (const x of goals) g.status.set(x.id, x.status)
      if (goals.length > 0) g.primed = true
      return
    }
    for (const x of goals) {
      const prev = g.status.get(x.id)
      if (prev === x.status) continue
      g.status.set(x.id, x.status)
      if (x.status === 'proved' && prev !== undefined) {
        g.lit.set(x.id, Date.now())
        for (const dt of [90_000, 5 * 60_000, 15 * 60_000]) {
          const t = window.setTimeout(() => {
            glowTimers.current.delete(t)
            setGlowTick((v) => v + 1)
          }, dt)
          glowTimers.current.add(t)
        }
      }
    }
  }, [goals])
  useEffect(
    () => () => {
      for (const t of glowTimers.current) window.clearTimeout(t)
    },
    [],
  )

  // The shared sky camera (lib/camera.tsx). Fit per PROBLEM and on
  // frontier-focus toggles, never per poll (resetKey: the layout
  // shifts on every poll and refitting would fight the user's zoom);
  // the custom fit budgets label overhang. The glide animator below
  // drives the camera BETWEEN renders through the exposed refs.
  const cam = useSkyCamera(
    layout.nodes.length === 0 ? 0 : layout.width,
    layout.height,
    {
      resetKey: problemKey,
      fit: (el) => computeFit(el, layout),
      // panel/drawer resizes keep the scale and re-centre on the
      // selected star (a side panel opening used to shrink the sky)
      focus: () => {
        if (selectedId === null) return null
        const n = layout.nodes.find((m) => m.goal.id === selectedId)
        return n ? { x: n.x, y: n.y } : null
      },
    },
  )
  const containerRef = cam.containerRef
  const [hovered, setHovered] = useState<LayoutNode | null>(null)
  // the glide animator (an effect) needs the CURRENT selection, not
  // the one its closure captured at layout-change time
  const selectedIdRef = useRef(selectedId)
  selectedIdRef.current = selectedId

  // ---- poll-to-poll transition (imperative) --------------------------
  // A structure change re-layouts the whole sky (readability outranks
  // stillness — owner call); the tween keeps every star's IDENTITY
  // through the move. React always renders the TARGET sky; the animator
  // below interpolates by writing DOM attributes directly through the
  // element registries — at 370 nodes one React render costs ~10ms
  // (measured on stokes), an attribute sweep doesn't. Unrelated
  // re-renders (hover, selection) diff target-vs-target and so never
  // disturb a glide in flight.
  const shownPosRef = useRef(new Map<number, { x: number; y: number }>())
  const shownJuncRef = useRef(new Map<number, { x: number; y: number }>())
  const sceneRef = useRef<string | null>(null)
  const outerGRef = useRef<SVGGElement | null>(null)
  const nodeEls = useRef(new Map<number, SVGGElement>())
  const juncEls = useRef(new Map<number, SVGGElement>())
  const edgeEls = useRef(
    new Map<SVGElement, { from: number; to: number; cite: boolean; rTo?: number }>(),
  )
  const stemEls = useRef(new Map<SVGLineElement, { parent: number; sid: number }>())
  const branchEls = useRef(
    new Map<SVGElement, { sid: number; child: number; curved: boolean }>(),
  )
  const animRef = useRef({ raf: 0, timer: 0 })

  const k = cam.view?.k ?? 1
  const tx = cam.view?.tx ?? 0
  const ty = cam.view?.ty ?? 0
  const showLabels = k >= 1.05
  // Quantized zoom for the memoized layers: panning is k-free, and a
  // wheel burst re-renders content only when it crosses an ~8% bucket —
  // in between, the outer transform scales everything smoothly and the
  // compensated sizes ride within ±8% of ideal.
  const kq = useMemo(() => {
    const step = Math.log(1.08)
    return Math.exp(Math.round(Math.log(Math.max(k, 0.05)) / step) * step)
  }, [k])
  // the stars' shared size boost, mirrored into a ref so the edge
  // layer and the rAF animator can trim arcs to the CURRENT rim
  // without taking a zoom-bucket dependency (a hover refresh corrects
  // any staleness within the same interaction)
  const boostRef = useRef(1)
  boostRef.current = Math.min(Math.max(1, 0.78 / kq), 4)

  // the animator must fire on [layout, sceneKey] ONLY — it reaches the
  // camera through this ref so the hook's per-render identity doesn't
  // join the dependency list
  const camRef = useRef(cam)
  camRef.current = cam

  useLayoutEffect(() => {
    const sameScene = sceneRef.current === sceneKey
    sceneRef.current = sceneKey
    const anim = animRef.current
    const stop = () => {
      if (anim.raf) cancelAnimationFrame(anim.raf)
      if (anim.timer) window.clearTimeout(anim.timer)
      anim.raf = 0
      anim.timer = 0
    }
    const targets = new Map(layout.nodes.map((n) => [n.goal.id, { x: n.x, y: n.y }]))
    const juncTargets = new Map(
      layout.bundles.map((b) => [b.strategyId, { x: b.junction.x, y: b.junction.y }]),
    )
    if (camRef.current.containerRef.current) {
      camRef.current.fitKRef.current = computeFit(camRef.current.containerRef.current, layout).k
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
      !camRef.current.userAdjustedRef.current &&
      camRef.current.containerRef.current !== null &&
      camRef.current.viewRef.current !== null
    // re-frame target: with a star selected the camera keeps its scale
    // and follows the star to its new place — a re-layout (or the
    // panel it opened) must not shrink the sky under the reader (the
    // resize path in lib/camera.tsx applies the same law)
    const cameraTarget = (el: HTMLElement): View => {
      const sel = selectedIdRef.current
      const v = camRef.current.viewRef.current
      if (sel !== null && v !== null) {
        const n = layout.nodes.find((m) => m.goal.id === sel)
        if (n) {
          const { width: cw, height: ch } = el.getBoundingClientRect()
          return { k: v.k, tx: cw / 2 - n.x * v.k, ty: ch / 2 - n.y * v.k }
        }
      }
      return computeFit(el, layout)
    }
    const tween: Tween = {
      t0: performance.now(),
      fromPos: new Map(shownPosRef.current),
      fromJunc: new Map(shownJuncRef.current),
      fromView: glide ? { ...camRef.current.viewRef.current! } : null,
      toView: glide ? cameraTarget(camRef.current.containerRef.current!) : null,
    }

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
          // an arc carrying a direction marker keeps its rim trim
          // through the glide (attribute presence IS the touched state)
          const trim = el.hasAttribute('marker-end')
            ? (m.rTo ?? 0) * boostRef.current + 2
            : 0
          el.setAttribute('d', citePath(a, b, m.from, m.to, trim).d)
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
        if (m.curved) {
          el.setAttribute('d', citePath(j, c, m.sid, m.child).d)
        } else {
          el.setAttribute('x1', String(j.x))
          el.setAttribute('y1', String(j.y))
          el.setAttribute('x2', String(c.x))
          el.setAttribute('y2', String(c.y))
        }
      }
      if (tween.fromView && tween.toView && !camRef.current.userAdjustedRef.current) {
        const f = tween.fromView
        const g = tween.toView
        const camNow = {
          k: f.k + (g.k - f.k) * alpha,
          tx: f.tx + (g.tx - f.tx) * alpha,
          ty: f.ty + (g.ty - f.ty) * alpha,
        }
        camRef.current.viewRef.current = camNow
        outerGRef.current?.setAttribute(
          'transform',
          `translate(${camNow.tx},${camNow.ty}) scale(${camNow.k})`,
        )
      }
    }
    let done = false
    const finish = () => {
      if (done) return
      done = true
      apply(1)
      stop()
      // commit the camera through React with a FRESH target — the
      // derive-time toView goes stale if the container resized mid-
      // glide (cameraTarget keeps a selected star centred at scale)
      if (tween.toView && !camRef.current.userAdjustedRef.current && camRef.current.containerRef.current) {
        camRef.current.commitView(cameraTarget(camRef.current.containerRef.current))
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

  // wheel zoom + drag pan live in the shared camera; the sky adds one
  // behaviour on top — a plain click on empty sky clears the selection
  const onPointerUp = (e: React.PointerEvent) => {
    cam.onPointerUp()
    if (!cam.dragMovedRef.current && (e.target as Element).tagName === 'svg') {
      onSelect(null)
    }
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

  // Dead routes stay on the map as whisper-faint residue (the toggle is
  // retired): a grey star with no edge read as floating dust — the
  // struggle keeps its shape, at an opacity that never competes.
  const isDead = (s: string) => s === 'dead' || s === 'superseded'
  const visibleEdges = layout.edges
  const visibleBundles = layout.bundles
  // density-stepped: a handful of citations read at 0.22; a hundred
  // would wash the sky at that weight
  const citeCount = useMemo(
    () => layout.edges.filter((e) => e.kind === 'citation').length,
    [layout],
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
    layout.edges.some(
      (e) => e.kind === 'citation' && (e.from === focusId || e.to === focusId),
    )
      ? focusId
      : null

  const byId = useMemo(
    () => new Map(layout.nodes.map((n) => [n.goal.id, n])),
    [layout],
  )

  // Anchor = a def in the KERNEL-DERIVED closure of a claim's
  // statement (anchor_claim_design §4) — membership comes from the
  // anchor edges the review snapshot recorded. "Every def wears the
  // ring" over-marked the sign-off surface (owner, 2026-07-14): a
  // scratch def nobody's claim depends on is vocabulary, not a
  // vouching obligation.
  const anchorIds = useMemo(() => {
    const s = new Set<number>()
    for (const e of anchorEdges) {
      s.add(e.from)
      s.add(e.to)
    }
    return s
  }, [anchorEdges])
  const isAnchor = useCallback(
    (g: Goal) => DEF_KINDS.has(g.kind) && anchorIds.has(g.id),
    [anchorIds],
  )

  // Hover family: the pointed-at star's OWN tree, one hop — parents
  // above, subgoals below. Citations already carry the hover light;
  // the hierarchy stayed at base ink and drowned next to them (owner,
  // 2026-07-11). Rendered as an overlay like the route-hover echo:
  // relit strokes + rings ON TOP of the memoized layers, so hovering
  // never re-renders the edge/bundle layers. Hierarchy = strategy +
  // anchor edges (from = parent); alias/citation are cross-links.
  const family = useMemo(() => {
    if (!hovered) return null
    const id = hovered.goal.id
    // rings follow the hovered star's OWN vitality (owner, 2026-07-11):
    // a living star's hover invites you to its living relatives — its
    // failed decompositions keep the faint strokes (never hidden) but
    // earn no ring; a dead/shelved star has only dead family, and
    // "where did this hang" still deserves an answer, so its rings stay
    const retiredStatus = (s: string) => s === 'dead' || s === 'shelved'
    const retired = retiredStatus(hovered.goal.status)
    // dim ink = the route is dead OR the relative itself is parked —
    // brightness is the state axis, and a shelved subgoal must not
    // wear living ink just because its route survived (owner)
    const segs: {
      key: string
      dead: boolean
      d?: string
      line?: [number, number, number, number]
    }[] = []
    // star id → dim-only? a neighbour reached by any living route
    // wears the live ring
    const stars = new Map<number, boolean>()
    const mark = (sid: number, routeDead: boolean) => {
      if (routeDead && !retired) return
      const n = byId.get(sid)
      const dim = routeDead || (n !== undefined && retiredStatus(n.goal.status))
      stars.set(sid, (stars.get(sid) ?? true) && dim)
    }
    const pt = (a: { x: number; y: number }, b: { x: number; y: number }, fromId: number, toId: number, dead: boolean, key: string) => {
      // same geometry law as the base layers: past 480 a straight
      // stroke reads as a stray wire — bow it exactly where they do
      if ((Math.hypot(b.x - a.x, b.y - a.y) || 1) > 480)
        segs.push({ key, dead, d: citePath(a, b, fromId, toId).d })
      else segs.push({ key, dead, line: [a.x, a.y, b.x, b.y] })
    }
    for (const e of layout.edges) {
      if (e.kind !== 'strategy' && e.kind !== 'anchor') continue
      const other = e.from === id ? e.to : e.to === id ? e.from : null
      if (other === null) continue
      const a = byId.get(e.from)
      const b = byId.get(e.to)
      if (!a || !b) continue
      const routeDead = isDead(e.strategyStatus)
      const otherNode = e.from === id ? b : a
      pt(a, b, e.from, e.to, routeDead || retiredStatus(otherNode.goal.status), `e${e.from}>${e.to}`)
      mark(other, routeDead)
    }
    for (const b of layout.bundles) {
      const parent = byId.get(b.parentId)
      if (!parent) continue
      const routeDead = isDead(b.status)
      if (b.parentId === id) {
        // my route: stem + EVERY branch — the fork needs all its
        // subgoals. A route is only as alive as its liveliest child:
        // all children parked/dead → the stem dims with them
        const kids = b.children.map((cid) => byId.get(cid)).filter((c) => c !== undefined)
        const allParked = kids.length > 0 && kids.every((c) => retiredStatus(c!.goal.status))
        segs.push({ key: `s${b.strategyId}`, dead: routeDead || allParked, line: [parent.x, parent.y, b.junction.x, b.junction.y] })
        for (const cid of b.children) {
          const c = byId.get(cid)
          if (!c) continue
          pt(b.junction, c, b.strategyId, cid, routeDead || retiredStatus(c.goal.status), `s${b.strategyId}>${cid}`)
          mark(cid, routeDead)
        }
      } else if (b.children.includes(id)) {
        // my parent's route: stem + only my branch — siblings stay quiet
        const c = byId.get(id)
        if (!c) continue
        segs.push({ key: `s${b.strategyId}`, dead: routeDead, line: [parent.x, parent.y, b.junction.x, b.junction.y] })
        pt(b.junction, c, b.strategyId, id, routeDead || retired, `s${b.strategyId}>${id}`)
        mark(b.parentId, routeDead)
      }
    }
    return segs.length > 0 ? { segs, stars: [...stars] } : null
  }, [hovered, layout, byId])

  // The legend shows only what THIS sky contains (owner) — a swatch
  // for a mark that never appears is homework.
  const present = useMemo(() => {
    let open = false
    let working = false
    let proved = false
    let shelved = false
    let dead = false
    let attempts = false
    let root = false
    let claim = false
    let anchor = false
    for (const g of goals) {
      const live =
        g.status === 'open' ||
        g.status === 'attempting' ||
        g.status === 'pending_strategist_review'
      if (live) open = true
      if (engineWorking && (g.status === 'attempting' || g.in_flight)) working = true
      if (g.status === 'proved') proved = true
      if (g.status === 'shelved') shelved = true
      if (g.status === 'dead') dead = true
      if (live && g.attempts > 0) attempts = true
      if (g.origin === 'root') root = true
      if (g.is_deliverable) claim = true
      if (isAnchor(g)) anchor = true
    }
    return {
      open,
      working,
      proved,
      shelved,
      dead,
      attempts,
      root,
      claim,
      anchor,
      route: layout.bundles.length > 0,
      cites: layout.edges.some((e) => e.kind === 'citation'),
      alias: layout.edges.some((e) => e.kind === 'alias'),
    }
  }, [goals, layout, engineWorking, isAnchor])
  const legendStatus =
    present.open ||
    present.working ||
    present.proved ||
    present.shelved ||
    present.dead ||
    present.attempts
  const legendMarks = present.root || present.claim || present.anchor
  const legendLines = present.route || present.cites || present.alias

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
          // curved elements animate via a `d` rewrite; straight ones by
          // endpoint attributes — the registry must know which
          const reg = (curved: boolean) => (el: SVGElement | null) => {
            if (!el) return
            edgeEls.current.set(el, {
              from: e.from,
              to: e.to,
              cite: curved,
              rTo: radius(b.goal),
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
            const touched =
              citeFocusId !== null && (e.from === citeFocusId || e.to === citeFocusId)
            // a marked arc stops at the star's rim so the chevron's
            // tip touches the dot instead of vanishing under it
            const trim = touched ? radius(b.goal) * boostRef.current + 2 : 0
            const { d, len } = citePath(a, b, e.from, e.to, trim)
            // long hauls fade further: a cross-sky thread is context,
            // not content — nearby citations stay readable
            const fade = Math.min(1, Math.max(0.35, 320 / len))
            return (
              <path
                key={i}
                ref={reg(true)}
                d={d}
                fill="none"
                // direction reads only under focus: the arrow points at
                // the path END (node b = e.to = the citer). Gated on the
                // same `touched` that brightens, so the settled sky and
                // every non-citation hover carry no marker at all.
                markerEnd={touched ? 'url(#cite-arrow)' : undefined}
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
          // The same ink law citations obey: a long haul is context,
          // not content. Hierarchy gets a GENTLER curve than citations
          // (480 vs 320): wide trees legitimately span 3–4 slots, and
          // fading those washed out the structural skeleton itself
          // (green_theorem went ghostly) — only true cross-sky rays
          // recede (stokes' hub fan, jordan's chain fan).
          const span = Math.hypot(b.x - a.x, b.y - a.y) || 1
          const lineFade = Math.min(1, Math.max(0.4, 480 / span))
          const baseOpacity =
            (dead
              ? 0.18
              : e.kind === 'alias'
                ? 0.5
                : e.kind === 'anchor'
                  ? 0.3
                  : e.strategyStatus === 'succeeded'
                    ? 0.38
                    : 0.55) * lineFade
          // past the long-haul boundary (same 480 as the fade — one
          // concept, one number) a straight hierarchy edge reads as a
          // stray WIRE (the owner circled one); a bow reads as a
          // relation
          if (span > 480) {
            return (
              <path
                key={i}
                ref={reg(true)}
                d={citePath(a, b, e.from, e.to).d}
                fill="none"
                stroke={edgeStroke(e.strategyStatus, e.kind)}
                strokeWidth={e.strategyStatus === 'succeeded' ? 1.2 : 1}
                strokeOpacity={baseOpacity}
                strokeDasharray={e.kind === 'alias' ? '4 4' : undefined}
                vectorEffect="non-scaling-stroke"
              />
            )
          }
          return (
            <line
              key={i}
              ref={reg(false)}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={edgeStroke(e.strategyStatus, e.kind)}
              strokeWidth={e.strategyStatus === 'succeeded' ? 1.2 : 1}
              strokeOpacity={baseOpacity}
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
          const opacity = dead ? 0.18 : b.status === 'succeeded' ? 0.38 : 0.55
          // the ink law applies to hyperedge limbs too: a branch whose
          // child lives under a DIFFERENT primary parent can span half
          // the sky (jordan's chain fan was all bundle branches);
          // hierarchy curve (480) — see the edge layer
          const fade = (ax: number, ay: number, bx: number, by: number) =>
            Math.min(1, Math.max(0.4, 480 / (Math.hypot(bx - ax, by - ay) || 1)))
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
                strokeOpacity={
                  opacity * fade(parent.x, parent.y, b.junction.x, b.junction.y)
                }
                vectorEffect="non-scaling-stroke"
              />
              {b.children.map((cid) => {
                const c = byId.get(cid)
                if (!c) return null
                const branchSpan = Math.hypot(c.x - b.junction.x, c.y - b.junction.y)
                const curved = branchSpan > 480
                const regBranch = (el: SVGElement | null) => {
                  if (!el) return
                  branchEls.current.set(el, { sid: b.strategyId, child: cid, curved })
                  return () => {
                    branchEls.current.delete(el)
                  }
                }
                // a straight limb past ~5 slots reads as a stray wire
                // (the owner circled one) — long limbs bow instead
                if (curved) {
                  return (
                    <path
                      key={cid}
                      ref={regBranch}
                      d={citePath(b.junction, c, b.strategyId, cid).d}
                      fill="none"
                      stroke={stroke}
                      strokeWidth={b.status === 'succeeded' ? 1.4 : 1}
                      strokeOpacity={
                        opacity * fade(b.junction.x, b.junction.y, c.x, c.y)
                      }
                      vectorEffect="non-scaling-stroke"
                    />
                  )
                }
                return (
                  <line
                    key={cid}
                    ref={regBranch}
                    x1={b.junction.x}
                    y1={b.junction.y}
                    x2={c.x}
                    y2={c.y}
                    stroke={stroke}
                    strokeWidth={b.status === 'succeeded' ? 1.4 : 1}
                    strokeOpacity={
                      opacity * fade(b.junction.x, b.junction.y, c.x, c.y)
                    }
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
          // the star's own SMIL blink — the class exempts it from the
          // status-flip opacity transition, which otherwise low-pass
          // filters the 1.4s wave to a ±0.03 flicker nobody can see
          // (the legend blinked, the sky didn't — owner, 2026-07-09)
          const working =
            engineWorking &&
            (n.goal.status === 'attempting' || n.goal.in_flight)
          // Attempts heat gauge: lives burned out of threshold+1, only
          // meaningful while the goal is still being worked. The +1
          // keeps the gauge visibly open right up to the shelving
          // attempt (at attempts/threshold, one-away-from-shelving
          // drew 4/5 ≈ a closed ring; 4/6 = 2/3 breathes — owner).
          const heatFrac =
            live && n.goal.attempts > 0
              ? Math.min(n.goal.attempts / (shelveThreshold + 1), 1)
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
              {/* afterglow — freshly proved runs hot, cools in steps */}
              {(() => {
                const litAt = glowRef.current.lit.get(n.goal.id)
                if (litAt === undefined) return null
                const age = Date.now() - litAt
                if (age > 15 * 60_000) {
                  glowRef.current.lit.delete(n.goal.id)
                  return null
                }
                const heat = age < 90_000 ? 0.55 : age < 5 * 60_000 ? 0.3 : 0.14
                return (
                  <circle
                    r={r * 4}
                    fill="url(#star-halo)"
                    opacity={heat}
                    pointerEvents="none"
                  />
                )
              })()}
              {/* Two orthogonal axes, two channels (owner): IDENTITY
                  speaks in ring + shape + size — THE permanent ring is
                  a single ring = the signed surface (root, claim,
                  anchor); STATUS speaks in brightness + blink and never
                  borrows a ring. Activity marks keep disjoint slots:
                  heat arc r+3, signed ring r+5.5, selection r+9,
                  birth halo r+12. */}
              {/* the ring is the SIGN-OFF surface: root, claims, and
                  anchors — defs in the kernel closure of a claim, NOT
                  every def (a scratch def nobody's claim depends on
                  carries no vouching obligation; owner, 2026-07-14) */}
              {(n.goal.origin === 'root' ||
                n.goal.is_deliverable ||
                isAnchor(n.goal)) && (
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
                  human vouches for) — ALWAYS diamonds (a zoom-dependent
                  fallback to circles read as two different marks);
                  smaller than the circle radius so the ring keeps a
                  clear margin from the corners. Props stay round. */}
              {DEF_KINDS.has(n.goal.kind) ? (
                <rect
                  className={working ? 'working' : undefined}
                  x={-r * 0.85}
                  y={-r * 0.85}
                  width={r * 1.7}
                  height={r * 1.7}
                  transform="rotate(45)"
                  fill={fill}
                  stroke={s.stroke}
                  strokeWidth={1.4}
                  opacity={s.opacity}
                  vectorEffect="non-scaling-stroke"
                >
                  {/* working = the star itself BLINKS (owner: no ring
                      for activity) — gated on daemon liveness */}
                  {working && (
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
                  className={working ? 'working' : undefined}
                  r={r}
                  fill={fill}
                  stroke={s.stroke}
                  strokeWidth={1.4}
                  opacity={s.opacity}
                  vectorEffect="non-scaling-stroke"
                >
                  {/* working = the star itself BLINKS (owner: no ring
                      for activity) — gated on daemon liveness */}
                  {working && (
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
                // The dash pattern IS the data (arc fraction = attempts
                // burned), so it must live in USER space: with
                // non-scaling-stroke the dashes were measured in screen
                // units and a zoomed-out sky wrapped the first dash all
                // the way around — a 4/5 gauge read as a CLOSED ring and
                // masqueraded as the root/claim identity mark (owner,
                // putnam sky). Stroke width compensates via the zoom
                // bucket instead; round caps keep the endpoints legible.
                <circle
                  r={heatR}
                  fill="none"
                  stroke="var(--color-starlight)"
                  strokeWidth={1.8 / kq}
                  strokeLinecap="round"
                  strokeOpacity={0.4 + heatFrac * 0.5}
                  strokeDasharray={`${heatC * heatFrac} ${heatC}`}
                  transform="rotate(-90)"
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
              {showLabels && (
                <text
                  // Stagger label rows by in-row parity so long slugs
                  // on adjacent stars don't collide; offsets are
                  // screen-constant like the font. Truncation is
                  // width-aware: never truncate into empty space.
                  // No labels in the survey view (owner): the ring IS
                  // the far-zoom identity — names arrive with zoom.
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
      labelRoom,
      rowCounts,
      selectCb,
      birthTick,
      glowTick,
      isAnchor,
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
        onPointerDown={cam.onPointerDown}
        onPointerMove={cam.onPointerMove}
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
          {/* the atmosphere is drawn in INK, not in white: on the light
              end of the scale a white nebula over white paper is
              nothing at all (2026-08-07) */}
          <radialGradient id="nebula-a" cx="30%" cy="24%" r="55%">
            <stop offset="0%" stopColor="var(--color-ink)" stopOpacity="0.028" />
            <stop offset="100%" stopColor="var(--color-ink)" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="nebula-b" cx="76%" cy="72%" r="50%">
            <stop offset="0%" stopColor="var(--color-ink)" stopOpacity="0.02" />
            <stop offset="100%" stopColor="var(--color-ink)" stopOpacity="0" />
          </radialGradient>
          {/* Citation direction, drawn ONLY on focused arcs (see the
              edge layer's `touched` gate): a slender chevron at the
              path's END — the citer, where knowledge flows in. Achromatic
              starlight, the exact ink focused citation arcs already carry
              (edgeStroke → starlight); markerUnits="strokeWidth" keeps it
              proportional to the thread. The settled sky attaches no
              marker, so it stays clean (ink is for exceptions). */}
          <marker
            id="cite-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            markerUnits="strokeWidth"
            orient="auto"
          >
            <path
              d="M 2 2 L 9 5 L 2 8"
              fill="none"
              stroke="var(--color-starlight)"
              strokeOpacity="0.6"
              strokeWidth="1.4"
            />
          </marker>
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
          {/* hover family echo: the hovered star's parents and subgoals
              relit over the base layers — dead routes at residue ink,
              never as bright as the living */}
          {family && (
            <g className="pointer-events-none">
              {family.segs.map((s) =>
                s.d ? (
                  <path
                    key={s.key}
                    d={s.d}
                    fill="none"
                    stroke="var(--color-starlight)"
                    strokeWidth={1.6}
                    strokeOpacity={s.dead ? 0.3 : 0.9}
                    vectorEffect="non-scaling-stroke"
                  />
                ) : (
                  <line
                    key={s.key}
                    x1={s.line![0]}
                    y1={s.line![1]}
                    x2={s.line![2]}
                    y2={s.line![3]}
                    stroke="var(--color-starlight)"
                    strokeWidth={1.6}
                    strokeOpacity={s.dead ? 0.3 : 0.9}
                    vectorEffect="non-scaling-stroke"
                  />
                ),
              )}
              {family.stars.map(([sid, dead]) => {
                const n = byId.get(sid)
                if (!n) return null
                const boost = Math.min(Math.max(1, 0.78 / kq), 4)
                return (
                  <circle
                    key={sid}
                    cx={n.x}
                    cy={n.y}
                    r={(radius(n.goal) + 9) * boost}
                    fill="none"
                    stroke="var(--color-starlight)"
                    strokeWidth={1.4}
                    strokeOpacity={dead ? 0.35 : 0.95}
                    vectorEffect="non-scaling-stroke"
                  />
                )
              })}
            </g>
          )}
          {/* route-hover echo (goal panel → sky): a transient bright
              ring OUTSIDE the memoized layers — hover must not pay a
              node-layer re-render. Solid, vs the selection's dashes. */}
          {highlightIds && highlightIds.length > 0 && (
            <g className="pointer-events-none">
              {highlightIds.map((id) => {
                const n = layout.nodes.find((m) => m.goal.id === id)
                if (!n) return null
                const boost = Math.min(Math.max(1, 0.78 / kq), 4)
                return (
                  <circle
                    key={id}
                    cx={n.x}
                    cy={n.y}
                    r={(radius(n.goal) + 9) * boost}
                    fill="none"
                    stroke="var(--color-starlight)"
                    strokeWidth={1.4}
                    strokeOpacity={0.95}
                    vectorEffect="non-scaling-stroke"
                  />
                )
              })}
            </g>
          )}
        </g>
      </svg>

      {/* the selected node's facts live in the side panel — no echo */}
      {hovered && hovered.goal.id !== selectedId && cam.view !== null && (
        <div
          className="pointer-events-none absolute z-10 max-w-sm rounded-lg border border-edge-strong bg-surface-3 px-3 py-2"
          style={{
            left: Math.min(
              tx + (shownPosRef.current.get(hovered.goal.id) ?? hovered).x * k + 14,
              // clamp ≥ the card's real max width (max-w-sm = 384px):
              // 340 let right-edge popovers run off-screen (cold-eye)
              (containerRef.current?.clientWidth ?? 800) - 400,
            ),
            top: Math.min(
              ty + (shownPosRef.current.get(hovered.goal.id) ?? hovered).y * k + 14,
              (containerRef.current?.clientHeight ?? 600) - 120,
            ),
          }}
        >
          {/* wrap, don't clip: a long slug was pushing the status
              label straight through the card's right border (owner:
              "proved 也超出框") — the name may break, every word stays
              inside the card */}
          <div className="mb-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <span className="min-w-0 font-mono text-xs break-all text-ink">
              {hovered.goal.slug}
            </span>
            <span className="text-xs text-ink-faint">
              {goalStatusLabel(hovered.goal.status)}
            </span>
            {hovered.goal.disproof_of && (
              <span className="text-[11px] text-warn">disproof of {hovered.goal.disproof_of.slug}</span>
            )}
          </div>
          {/* break-words: a fully-qualified name is one giant token —
              without break permission it overflows sideways and the
              clip SWALLOWS its middle ("…has_simple_l / f" read as the
              whole statement; owner, 2026-07-12).
              InfoView shape when the stub's signature is available
              (owner, 2026-07-18: the bare conclusion without its
              hypotheses "意義很低"): binder lines, then ⊢ goal. */}
          {(() => {
            const sig = hovered.goal.signature
              ? splitSignature(hovered.goal.signature)
              : null
            if (sig !== null && sig.binders.length > 0) {
              const shown = sig.binders.slice(0, 5)
              return (
                <div className="font-mono text-[11px] leading-snug break-words">
                  {shown.map((b, i) => (
                    <div key={i} className="text-ink-faint">
                      <Lean code={b} />
                    </div>
                  ))}
                  {sig.binders.length > shown.length && (
                    <div className="text-ink-faint">
                      … {sig.binders.length - shown.length} more
                    </div>
                  )}
                  <div className="line-clamp-3 text-ink-dim">
                    <Lean code={'⊢ ' + sig.conclusion} />
                  </div>
                </div>
              )
            }
            return (
              <div className="line-clamp-4 font-mono text-[11px] leading-snug break-words text-ink-dim">
                <Lean code={hovered.goal.signature ?? hovered.goal.statement} />
              </div>
            )
          })()}
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
          choice sticks. It opens RIGHTWARD on the toggle's own line
          (owner, 2026-07-11): the second line used to hang exactly
          over the root band at the sky's top-left */}
      {/* opaque: at high zoom the sky's strokes crossed straight
          through the 90%-alpha plate and garbled the labels (cold-eye) */}
      <div className="absolute top-3 left-3 flex flex-wrap items-center gap-x-2.5 gap-y-1 rounded-lg bg-surface px-2.5 py-1">
        <button
          className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink-dim"
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
          {/* the triangle tells the truth about the direction: closed
              opens RIGHTWARD (▸), open folds back left (◂) */}
          legend {legendOpen ? '◂' : '▸'}
        </button>
        {legendOpen && <span className="h-3 w-px bg-edge" aria-hidden />}
        {/* grouped: star status | landmark marks | line kinds — and the
            status icons must MATCH the sky (the old "open" swatch drew a
            hollow accent ring that exists nowhere) */}
        {/* NOT pointer-events-none: every swatch carries an explanatory
            title, and the old none made all of them unreachable — the
            legend explained nothing on hover (cold-eye) */}
        <div
          className={`${legendOpen ? 'flex' : 'hidden'} flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-faint`}
        >
        {/* STATUS group — swatches carry the TRUE inking (brightness,
            blink); the shape is fixed so only the status axis varies */}
        {present.open && (
<span className="flex items-center gap-1" title="not yet proved — the engine still owes this star">
          <svg width="13" height="13" viewBox="-5 -5 10 10">
            <circle r="3.4" fill="var(--color-star)" stroke="var(--color-starlight)" strokeWidth="0.9" />
          </svg>
          open
        </span>
        )}
        {present.working && (
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
        )}
        {present.proved && (
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
        )}
        {present.shelved && (
<span className="flex items-center gap-1" title="set aside after repeated failed attempts">
          <svg width="13" height="13" viewBox="-5 -5 10 10">
            <circle r="3" fill="var(--color-ink-faint)" opacity="0.6" />
          </svg>
          shelved
        </span>
        )}
        {present.dead && (
<span className="flex items-center gap-1" title="an abandoned path (edges hidden behind “show dead paths”)">
          <svg width="13" height="13" viewBox="-5 -5 10 10">
            <circle r="2.6" fill="var(--color-edge-strong)" opacity="0.55" />
          </svg>
          dead
        </span>
        )}
        {present.attempts && (
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
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeDasharray="20 28"
              transform="rotate(-90)"
            />
          </svg>
          attempts
        </span>
        )}
        {legendStatus && legendMarks && <span className="h-3 w-px bg-edge" />}
        {/* IDENTITY group — neutral tone on purpose: here only ring,
            shape and size speak; brightness belongs to the status axis */}
        {present.root && (
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
        )}
        {present.claim && (
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
        )}
        {present.anchor && (
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
        )}
        {(legendStatus || legendMarks) && legendLines && (
          <span className="h-3 w-px bg-edge" />
        )}
        {present.route && (
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
        )}
        {present.cites && (
<span className="flex items-center gap-1" title="one proof imports another — the lemma is used there">
          <svg width="18" height="13" viewBox="0 0 14 10">
            <line x1="1" y1="8" x2="13" y2="2" stroke="var(--color-starlight)" strokeWidth="1" opacity="0.45" />
          </svg>
          cites
        </span>
        )}
        {present.alias && (
<span
          className="flex items-center gap-1"
          title="two names, one theorem — the dashed link ties a goal to the star it turned out to equal"
>
          <svg width="18" height="13" viewBox="0 0 14 10">
            <line x1="1" y1="5" x2="13" y2="5" stroke="var(--color-accent)" strokeWidth="1" strokeDasharray="3 2.5" opacity="0.7" />
          </svg>
          alias
        </span>
        )}
        </div>
      </div>
      <CameraControls zoomBy={cam.zoomBy} refit={cam.refit} />
    </div>
  )
}
