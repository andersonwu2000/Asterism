// Constellation crossing metric — the layout's regression instrument.
//
//   node web/scripts/sky-crossings.mjs [problem ...]
//
// Requires a running serve (http://127.0.0.1:8642). Bundles the live
// layout.ts via esbuild, runs it against real problem data, and counts
// pairwise edge crossings in four buckets:
//
//   bb   SOLID x SOLID  — the score. One route crossing another.
//   bf   solid x dotted  — reported, NOT scored
//   ff   dotted x dotted — reported, NOT scored
//
// The weights were 1 / 0.2 / 0.05, and on a real sky the two dotted
// buckets WERE the score: stokes measured bb 1, bf 287, ff 1681, so
// 99% of what the engine optimised was a crossing involving a citation
// arc. Those arcs became dotted (`CITE_DASH`) and the eye separates
// them by texture rather than by position — the ruler was measuring a
// problem the ink had already solved, at ~370ms of the layout's ~380
// (owner, 2026-08-27: "stop using that ruler"). What dashes do NOT
// disambiguate is one solid route crossing another, and that is what
// is scored now. bf/ff stay VISIBLE because a number nobody scores is
// still evidence — but they buy nothing and cost nothing.
//
// Compare before/after a layout change; bb is the number that must
// not grow.
import { execSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const out = join(mkdtempSync(join(tmpdir(), 'sky-metric-')), 'layout.cjs')
execSync(`npx esbuild "${join(here, '../src/lib/layout.ts')}" --bundle --format=cjs --outfile="${out}"`, {
  cwd: join(here, '..'),
  stdio: 'pipe',
})
const { layoutConstellation } = createRequire(import.meta.url)(out)

const SERVE = process.env.ASTERISM_SERVE ?? 'http://127.0.0.1:8642'
const DEFAULT_PROBLEMS = [
  'Geometry.stokes_theorem',
  'Geometry.banach_tarski',
  'Topology.sphere_homology',
  'LinearAlgebra.jordan_normal_form',
  'residue_thm',
  'Geometry.green_theorem',
]

function metric(d, lay) {
  const pos = new Map(lay.nodes.map((n) => [n.goal.id, n]))
  const segs = []
  const push = (a, b, bright) =>
    segs.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, bright })
  for (const e of lay.edges) {
    const a = pos.get(e.from)
    const b = pos.get(e.to)
    if (!a || !b) continue
    const span = Math.hypot(b.x - a.x, b.y - a.y)
    push(a, b, e.kind !== 'citation' && span <= 480)
  }
  for (const bu of lay.bundles) {
    const p = pos.get(bu.parentId)
    if (p) {
      push(p, bu.junction, Math.hypot(bu.junction.x - p.x, bu.junction.y - p.y) <= 480)
    }
    for (const cid of bu.children) {
      const c = pos.get(cid)
      if (c) {
        push(bu.junction, c, Math.hypot(c.x - bu.junction.x, c.y - bu.junction.y) <= 480)
      }
    }
  }
  // unnecessary line length (owner: a co-objective, 2026-07-09) —
  // bright structural ink beyond a 150px allowance per segment, in
  // units of 1000px ("kilopixels of excess bright rope")
  let len = 0
  for (const s of segs) {
    if (!s.bright) continue
    len += Math.max(0, Math.hypot(s.x2 - s.x1, s.y2 - s.y1) - 150)
  }
  len = Math.round(len / 100) / 10
  let bb = 0
  let bf = 0
  let ff = 0
  const inter = (s, t) => {
    const dd = (ax, ay, bx, by, cx, cy) => (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    const eq = (x1, y1, x2, y2) => Math.abs(x1 - x2) < 1e-6 && Math.abs(y1 - y2) < 1e-6
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
  for (let i = 0; i < segs.length; i++) {
    for (let j = i + 1; j < segs.length; j++) {
      if (!inter(segs[i], segs[j])) continue
      if (segs[i].bright && segs[j].bright) bb++
      else if (segs[i].bright || segs[j].bright) bf++
      else ff++
    }
  }
  return { bb, bf, ff, len, score: bb }
}

// PLACEMENT, which is what the sky is judged on now that the arcs are
// dotted: how big the plate is, whether it takes the page's shape, and
// how much of it one block of unlinked singletons is eating. `blk` is
// that block's share of the plate area — a slab is the shape a reader
// notices first and the one carrying the least information.
function plate(lay) {
  const w = Math.round(lay.width)
  const h = Math.round(lay.height)
  // A LONE STAR is one no route reaches: no hierarchy edge, no bundle.
  // `spread` is the share of the plate their bounding box covers, and
  // HIGH is the good direction: they are scattered into the sky's gaps
  // now, so covering the page means covering it evenly, while a low
  // number means they have pooled back into a bed. (The first version
  // of this read `singlesBlock`, which was only the unlinked handful,
  // and reported 0 on the very sky whose beds filled a tenth of it.)
  const tied = new Set()
  for (const e of lay.edges) {
    if (e.kind === 'citation' || e.kind === 'alias') continue
    tied.add(e.from)
    tied.add(e.to)
  }
  for (const b of lay.bundles) {
    tied.add(b.parentId)
    for (const c of b.children) tied.add(c)
  }
  const lone = lay.nodes.filter((n) => !tied.has(n.goal.id))
  let spread = 0
  if (lone.length > 1) {
    const xs = lone.map((n) => n.x)
    const ys = lone.map((n) => n.y)
    const a = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys))
    spread = Math.round((a / (w * h)) * 100)
  }
  return { w, h, ratio: Math.round((w / h) * 100) / 100, lone: lone.length, spreadPct: spread }
}

const problems = process.argv.slice(2).length > 0 ? process.argv.slice(2) : DEFAULT_PROBLEMS
for (const p of problems) {
  const d = await fetch(`${SERVE}/api/problems/${encodeURIComponent(p)}`).then((r) => r.json())
  const aspect = Number(process.env.SKY_ASPECT ?? 16 / 9)
  const lay = layoutConstellation(d.goals, d.strategies, d.strategy_edges, d.anchor_edges, d.citation_edges, aspect)
  console.log(p.padEnd(42), JSON.stringify({ ...metric(d, lay), ...plate(lay) }))
}
