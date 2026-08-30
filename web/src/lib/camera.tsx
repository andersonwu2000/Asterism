import { useEffect, useLayoutEffect, useRef, useState } from 'react'

/*
 * The sky camera, shared. The problem sky (Constellation.tsx) set the
 * behaviour: fit-to-container on mount, re-fit on resize only while
 * the user hasn't touched the view, wheel zoom about the cursor, drag
 * pan, and a −/+/fit control bar. The Library module map grew its own
 * static shrink-and-scroll instead (owner, 2026-07-09: the two skies
 * scaled differently) — this hook is the one camera every non-problem
 * sky mounts. Constants mirror Constellation.tsx exactly (kMax 4,
 * wheel 0.0012, buttons 0.7/1.45, floor at half the fit).
 *
 * The problem sky's glide animator drives the camera BETWEEN React
 * renders (per-frame viewRef writes, a committed fresh fit at the
 * end) — the hook exposes its refs (viewRef / fitKRef /
 * userAdjustedRef) and commitView/computeFitNow for exactly that
 * handshake, plus a custom `fit` (label-overhang budgeting) and a
 * `resetKey` (refit per PROBLEM, never per poll — the layout shifts
 * on every poll and refitting would fight the user's camera).
 */

export interface CamView {
  k: number
  tx: number
  ty: number
}

export interface SkyCameraOpts {
  kMax?: number
  /** custom fit — receives the container element, returns the fitted
   * camera (null: nothing to fit yet) */
  fit?: (el: HTMLElement) => CamView | null
  /** refit trigger. Default: content dimensions (right for static
   * maps); pass a problem key when the content re-layouts per poll. */
  resetKey?: unknown
  /** the view's focal point in CONTENT coordinates (the selected
   * star), or null. When a panel/drawer resizes the container and a
   * focus exists, the camera keeps its zoom and pans the focus to the
   * new centre instead of re-fitting — a side panel opening used to
   * shrink the whole sky (owner, 2026-07-18). */
  focus?: () => { x: number; y: number } | null
}

export function useSkyCamera(
  contentW: number,
  contentH: number,
  opts?: SkyCameraOpts,
) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<CamView | null>(null)
  const [fitK, setFitK] = useState(1)
  const viewRef = useRef<CamView | null>(null)
  const fitKRef = useRef<number | null>(null)
  const userAdjusted = useRef(false)
  const drag = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null)
  /** true while the pointer sequence that just ended was a pan — click
   * handlers on content consult this to not fire after a drag */
  const dragMovedRef = useRef(false)
  // effects read options through a ref so the wheel listener and fit
  // logic always see the caller's LATEST fit closure (it captures the
  // current layout) without re-subscribing
  const optsRef = useRef(opts)
  optsRef.current = opts

  const computeFitNow = (): CamView | null => {
    const el = containerRef.current
    if (!el) return null
    const custom = optsRef.current?.fit
    if (custom) return custom(el)
    if (contentW <= 0 || contentH <= 0) return null
    const kMax = optsRef.current?.kMax ?? 2.0
    const { width: cw, height: ch } = el.getBoundingClientRect()
    const k = Math.min((cw - 48) / contentW, (ch - 48) / contentH, kMax)
    return { k, tx: (cw - contentW * k) / 2, ty: (ch - contentH * k) / 2 }
  }
  const computeFitRef = useRef(computeFitNow)
  computeFitRef.current = computeFitNow
  /** write a camera through BOTH channels (ref for the next gesture,
   * state for React) — the glide animator commits its final fit here */
  const commitView = (v: CamView) => {
    viewRef.current = v
    setView(v)
  }

  // reset → forget the user's camera and re-fit. The reset belongs to
  // the SAME layout effect as the fit: a passive mount effect used to
  // run after the first fit and publish `null`, so the first node hover
  // had no camera until a click caused another render.
  const resetKey =
    opts?.resetKey !== undefined ? opts.resetKey : `${contentW}x${contentH}`
  const fittedResetKey = useRef(resetKey)
  // ONE owner for the fit. A camera is fitted when there is no view to
  // show, and RE-fitted when the PLATE changed size under a camera the
  // reader has not touched: the engine console's sky is live, so its
  // plate is re-laid as goals land and a camera fitted to the plate of
  // ten seconds ago is not the fit any more (owner, 2026-08-27).
  //
  // Those were two effects for a day, and the second one PARKED the
  // camera. Both wrote `view` in one commit; `setView(null)` ran last;
  // React compared null to null, bailed out of the re-render, and the
  // fit effect — keyed on `view` — never ran again. `viewRef` still
  // held the right fit, which is exactly why a nudge of a drag "fixed"
  // it: the drag published the ref. On a 1900x1000 page union_closed
  // opened at scale(1) — an 11x zoom on a sky whose fit is 0.07 — and
  // stayed there. One effect cannot race itself.
  //
  // LAYOUT effect, not a passive one: `view === null` renders the sky
  // at k = 1, and on a big plate that fallback frame is a full paint of
  // every element at 1:1 before the fit lands. Fitting before paint
  // means the frame is never shown — the rule the aspect measurement in
  // Constellation.tsx already follows.
  const fittedFor = useRef<string | null>(null)
  useLayoutEffect(() => {
    const reset = !Object.is(fittedResetKey.current, resetKey)
    if (reset) {
      fittedResetKey.current = resetKey
      userAdjusted.current = false
      viewRef.current = null
      fittedFor.current = null
    }
    const size = `${contentW}x${contentH}`
    const plateChanged = fittedFor.current !== size && !userAdjusted.current
    if (view !== null && !plateChanged) return
    if (contentW <= 0 || contentH <= 0) {
      if (reset) setView(null)
      return
    }
    const fit = computeFitRef.current()
    if (!fit) {
      if (reset) setView(null)
      return
    }
    fittedFor.current = size
    fitKRef.current = fit.k
    viewRef.current = fit
    setFitK(fit.k)
    setView(fit)
  }, [view, contentW, contentH, resetKey])
  // The listener effects key on "a fit has landed": a component that
  // mounts in its EMPTY state (the problem sky's "no goals yet") has
  // no container div yet, and mount-only effects would never attach —
  // the wheel stayed dead for the whole session once goals arrived
  // (latent in the pre-hook copy; caught in review, 2026-07-09). The
  // first fit proves the container exists, so re-running on that
  // transition attaches exactly once per appearance.
  const attached = view !== null
  // window/panel resize re-fits ONLY untouched views (fighting an
  // explicit zoom is worse than letting it drift off-centre). With a
  // focal point on screen the resize keeps the SCALE and re-centres
  // on it — the goal panel / chat drawer taking width must not shrink
  // the sky the reader is inspecting.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    let initial = true // observe() always delivers one initial callback
    const ro = new ResizeObserver(() => {
      if (initial) {
        initial = false
        return
      }
      if (userAdjusted.current) return
      const f = optsRef.current?.focus?.()
      const v = viewRef.current
      if (f && v) {
        const { width: cw, height: ch } = el.getBoundingClientRect()
        const next = { k: v.k, tx: cw / 2 - f.x * v.k, ty: ch / 2 - f.y * v.k }
        viewRef.current = next
        setView(next)
        return
      }
      setView(null)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [attached])
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
  }, [attached])

  const onPointerDown = (e: React.PointerEvent) => {
    const v = viewRef.current
    if (v === null) return
    drag.current = { x: e.clientX, y: e.clientY, tx: v.tx, ty: v.ty }
    dragMovedRef.current = false
    ;(e.target as Element).setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current
    const v = viewRef.current
    if (!d || v === null) return
    const dx = e.clientX - d.x
    const dy = e.clientY - d.y
    if (Math.abs(dx) + Math.abs(dy) > 3) dragMovedRef.current = true
    if (dragMovedRef.current) {
      userAdjusted.current = true
      const next = { k: v.k, tx: d.tx + dx, ty: d.ty + dy }
      viewRef.current = next
      setView(next)
    }
  }
  const onPointerUp = () => {
    drag.current = null
  }
  const zoomBy = (factor: number) => {
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
  }
  const refit = () => {
    userAdjusted.current = false
    viewRef.current = null // gestures no-op until the fresh fit lands
    setView(null)
  }

  return {
    containerRef,
    view,
    fitK,
    viewRef,
    fitKRef,
    userAdjustedRef: userAdjusted,
    dragMovedRef,
    computeFitNow,
    commitView,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    zoomBy,
    refit,
  }
}

/** The −/+/fit bar, verbatim from the problem sky. */
export function CameraControls({
  zoomBy,
  refit,
}: {
  zoomBy: (factor: number) => void
  refit: () => void
}) {
  return (
    <div className="absolute bottom-3 left-3 flex overflow-hidden rounded-lg border border-edge bg-surface">
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
          onClick={() => zoomBy(factor)}
        >
          {label}
        </button>
      ))}
      <button
        className="border-l border-edge px-2.5 py-1 text-xs text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
        title="fit to view"
        onClick={refit}
      >
        fit
      </button>
    </div>
  )
}
