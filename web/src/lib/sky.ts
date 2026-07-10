/*
 * Shared sky drawing helpers — geometry both sky surfaces (the
 * problem constellation and the Library module map) must speak
 * identically. The map carried its own bow formula (cap 60, 0.16)
 * beside the constellation's (cap 150, 0.18) — the same
 * two-implementations disease the layout engine and the camera were
 * cured of (owner, 2026-07-10).
 */

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
