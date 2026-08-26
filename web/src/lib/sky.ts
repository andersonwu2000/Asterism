/*
 * Shared sky drawing helpers — the geometry AND the ink both sky
 * surfaces (the problem constellation and the Library module map)
 * must speak identically. The map carried its own bow formula (cap
 * 60, 0.16) beside the constellation's (cap 150, 0.18) — the same
 * two-implementations disease the layout engine and the camera were
 * cured of (owner, 2026-07-10). The star marks moved here on
 * 2026-08-26 for the same reason plus one more: a law nobody can
 * import is a law nobody can test (`sky.test.ts`).
 */

import type { Goal, Strategy } from './types'
import { DEF_KINDS } from './vocab'

/** Citation bow — single source for the initial render AND the
 * animator's per-frame rewrites. Bow grows with span (a fixed cap
 * flattened long horizontals back into wires); endpoint-id parity
 * mixes directions so parallel threads separate. */
export function citePath(
  a: { x: number; y: number },
  b: { x: number; y: number },
  from: number,
  to: number,
  trimEnd = 0,
): { d: string; len: number } {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  const bow = Math.min(150, len * 0.18) * ((from + to) % 2 === 0 ? 1 : -1)
  const mx = (a.x + b.x) / 2 + (-dy / len) * bow
  const my = (a.y + b.y) / 2 + (dx / len) * bow
  let bx = b.x
  let by = b.y
  if (trimEnd > 0) {
    // pull the endpoint back along the arrival tangent so a marker's
    // tip touches the star's RIM instead of drowning under the dot;
    // cap so a short arc can never invert
    const tx = b.x - mx
    const ty = b.y - my
    const tl = Math.hypot(tx, ty) || 1
    const t = Math.min(trimEnd, len * 0.4)
    bx = b.x - (tx / tl) * t
    by = b.y - (ty / tl) * t
  }
  return { d: `M ${a.x} ${a.y} Q ${mx} ${my} ${bx} ${by}`, len }
}

/* ---- star marks ----------------------------------------------------
 *
 * BODY vs SHELL is the sky's second state axis. A filled star is a
 * place light is coming or came home — live (on its way) or proved
 * (arrived). A shell is a place the light is NOT coming: parked
 * (shelved / frozen), refuted (disproved), abandoned (dead). One
 * exception, and it earns its keep: a goal waiting on the strategist
 * is a GLOWING shell — the light stopped, and the decision to relight
 * it is the only thing missing.
 *
 * Until 2026-08-26 shelved and proved differed by BRIGHTNESS ALONE,
 * and the owner read them as the same dot twice. Measured on
 * union_closed: proved L* 53.0, shelved L* 33.8 — two same-size grey
 * discs about five pixels across, sitting beside a live frontier at
 * L* 96 that flattens everything under it. Brightness had no headroom
 * left in either direction: proved may not brighten (the ink
 * inversion hands the light to the unproved while work is live) and
 * shelved may not dim (parked, not buried). A third pass at the same
 * knob would have been the fix that keeps not fixing it, so the
 * second axis is a different KIND of mark — and the Programme's
 * discussion tree had already been speaking exactly this one
 * ("delivered = filled, nothing came home = hollow", groupTree.ts).
 * One law on two surfaces now, instead of two laws.
 */

export interface StarMark {
  fill: string
  stroke: string
  glow: boolean
  opacity: number
}

/** Residual struggle heat: a proved star that burned failed attempts
 * keeps a duller cast — "where the machine fought" stays on the map
 * for the reviewer hunting fragile spots. */
export function provedFill(dead: number): string {
  if (dead <= 0) return 'var(--color-starlight)'
  // achromatic struggle residue: fought-over stars are duller, not warm
  const dull = dead <= 2 ? 22 : dead <= 5 ? 40 : 55
  return `color-mix(in srgb, var(--color-starlight) ${100 - dull}%, var(--color-ink-faint))`
}

/** status → the star's mark.
 *
 * INK INVERSION (cold-eye review): a status instrument must answer
 * "where is it stuck" in one glance. While ANYTHING is still live,
 * the unproved few are the brightest objects in the sky and the
 * proved mass recedes to memory; only a FINISHED problem lets the
 * proved stars shine (the sky becomes the trophy it earned). */
export function nodeStyle(g: Goal, hasLive: boolean): StarMark {
  switch (g.status) {
    case 'proved':
      return hasLive
        ? {
            // 55% mix: the settled mass stays clearly ABOVE the shelved
            // mid ink — at 45% the two collided (owner, 2026-08-24)
            fill: 'color-mix(in srgb, var(--color-starlight) 55%, var(--color-bg))',
            stroke: 'color-mix(in srgb, var(--color-starlight) 55%, var(--color-bg))',
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
    case 'pending_strategist_review':
      // the glowing shell: nothing stands here, and a decision is what
      // it is waiting for
      return { fill: 'transparent', stroke: 'var(--color-warn)', glow: true, opacity: 1 }
    case 'frozen':
    case 'shelved':
      // parked, not buried (owner, 2026-08-24) — a SHELL at mid ink.
      // 0.65 (was 0.45 when it was a disc) pays back the ink an
      // outline loses to its hole, so a far-zoom shelved star is
      // exactly as present as it was while a near one is unmistakable.
      // frozen parks identically (owner, same day): same story in the
      // engine, same mark on the sky.
      return { fill: 'transparent', stroke: 'var(--color-ink-dim)', glow: false, opacity: 0.65 }
    case 'disproved':
      // refuted (owner, 2026-08-24): a shell at residue weight — the
      // question closed without light coming home, so it never glows
      // in any sky. Faint ink keeps its outline from masquerading as a
      // sign-off ring.
      return { fill: 'transparent', stroke: 'var(--color-ink-faint)', glow: false, opacity: 0.55 }
    case 'dead':
    default:
      // abandoned: the faintest shell, residue but never hidden. Ink
      // token, not the rgba `--color-edge-strong` it used to carry:
      // that one stacks its own alpha under opacity, and a 5% outline
      // is nothing at all.
      return { fill: 'transparent', stroke: 'var(--color-ink-faint)', glow: false, opacity: 0.3 }
  }
}

/** Size hierarchy = what the human must know (owner: anchor + claim
 * are the only nodes the user NEEDS): root and claims largest, def
 * anchors next, supporting Props recede. */
export function radius(g: Goal): number {
  if (g.origin === 'root') return 9
  // "bigger = more important", applied to the two kinds of promise: a
  // claim YOU sign outranks a brick a sub-group delivered to the group
  // above it. Both are landmarks; only one is yours.
  if (g.human_facing_claim) return 8.5
  if (g.is_deliverable) return 7
  if (DEF_KINDS.has(g.kind)) return 6.5
  return 4.5
}

/* ---- lines ---------------------------------------------------------
 *
 * SOLID vs BROKEN is the line law (2026-08-26). Solid means the
 * machine's own decomposition — the tree it chose: routes, and the
 * anchor edges that hang a claim off the defs it is made of. Broken
 * means a cross-link that is NOT part of that tree: a citation dots,
 * an alias dashes. `layout.ts` has always sorted them exactly this
 * way (hierarchy is walked, `alias`/`citation` are skipped); the ink
 * just never said so.
 *
 * Before: citations, anchor edges and succeeded routes were all
 * `--color-starlight`, all 1–1.4px, and a route longer than 480 bowed
 * through the SAME `citePath` a citation does — so on putnam_b6_1 (25
 * route edges, 38 citations) the only thing telling a decomposition
 * from an import was an opacity that was simultaneously encoding
 * density and span. Three facts, one channel; the owner read the
 * result as one tangle, correctly.
 */

/** screen-constant under `vector-effect: non-scaling-stroke` — a bare
 * dasharray is measured in USER units and a zoomed-out sky wraps the
 * first dash around the whole path (the heat gauge learned this the
 * hard way, putnam sky) */
export const CITE_DASH = '1.6 3.4'
export const ALIAS_DASH = '4 4'

/** Base ink for the citation weave, stepped by how many threads the
 * sky carries. A dotted line spends ~32% of a solid one's ink, so
 * these sit ~1.6x above the solid values they replace: HALF the total
 * fog, twice the peak — one thread is traceable where a hundred used
 * to be a single wash. */
export function citeInk(count: number): number {
  return count > 80 ? 0.13 : count > 30 ? 0.21 : 0.35
}

export function edgeStroke(
  status: Strategy['status'],
  kind: 'strategy' | 'alias' | 'anchor' | 'citation',
): string {
  if (kind === 'alias') return 'var(--color-accent)'
  if (kind === 'citation') return 'var(--color-starlight)'
  if (kind === 'anchor' || status === 'succeeded') return 'var(--color-starlight)'
  // routes speak in THREE voices (owner, 2026-08-24): active ink-dim /
  // succeeded starlight / everything else ink-faint. The old edge
  // tokens are rgba whites (7-15% alpha) — stacked under strokeOpacity
  // they netted ~2% and the dependency tree vanished
  if (status === 'dead' || status === 'superseded') return 'var(--color-ink-faint)'
  return 'var(--color-ink-dim)'
}
