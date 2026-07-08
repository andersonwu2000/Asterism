// Bright-crossing autopsy — enumerate every bb pair with enough context
// to classify its mechanism (same band? same tree? edge kinds? spans).
//   node web/scripts/bb-diag.mjs <problem>
import { execSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const out = join(mkdtempSync(join(tmpdir(), 'sky-diag-')), 'layout.cjs')
execSync(`npx esbuild "${join(here, '../src/lib/layout.ts')}" --bundle --format=cjs --outfile="${out}"`, {
  cwd: join(here, '..'), stdio: 'pipe',
})
const { layoutConstellation } = createRequire(import.meta.url)(out)
const SERVE = process.env.ASTERISM_SERVE ?? 'http://127.0.0.1:8642'
const prob = process.argv[2] ?? 'residue_thm'

const d = await fetch(`${SERVE}/api/problems/${encodeURIComponent(prob)}`).then((r) => r.json())
const lay = layoutConstellation(d.goals, d.strategies, d.strategy_edges, d.anchor_edges, d.citation_edges)
const pos = new Map(lay.nodes.map((n) => [n.goal.id, n]))
const slug = new Map(d.goals.map((g) => [g.id, g.slug]))
const deg = new Map()
for (const e of d.citation_edges) {
  deg.set(e.from, (deg.get(e.from) ?? 0) + 1)
  deg.set(e.to, (deg.get(e.to) ?? 0) + 1)
}
const ultra = new Set([...deg].filter(([, n]) => n >= d.goals.length * 0.25).map(([id]) => id))

// segments with provenance
const segs = []
const push = (a, b, bright, hub, tag, ends) =>
  segs.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, bright, hub, tag, ends })
for (const e of lay.edges) {
  const a = pos.get(e.from), b = pos.get(e.to)
  if (!a || !b) continue
  const span = Math.hypot(b.x - a.x, b.y - a.y)
  push(a, b, e.kind !== 'citation' && span <= 480, ultra.has(e.from) || ultra.has(e.to),
       e.kind, [e.from, e.to])
}
for (const bu of lay.bundles) {
  const p = pos.get(bu.parentId)
  const hubP = ultra.has(bu.parentId)
  if (p) push(p, bu.junction, Math.hypot(bu.junction.x - p.x, bu.junction.y - p.y) <= 480, hubP,
              'stem', [bu.parentId, -1])
  for (const cid of bu.children) {
    const c = pos.get(cid)
    if (c) push(bu.junction, c, Math.hypot(c.x - bu.junction.x, c.y - bu.junction.y) <= 480,
                hubP || ultra.has(cid), 'arm', [bu.parentId, cid])
  }
}
const inter = (s, t) => {
  const dd = (ax, ay, bx, by, cx, cy) => (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
  const eq = (x1, y1, x2, y2) => Math.abs(x1 - x2) < 1e-6 && Math.abs(y1 - y2) < 1e-6
  if (eq(s.x1, s.y1, t.x1, t.y1) || eq(s.x1, s.y1, t.x2, t.y2) ||
      eq(s.x2, s.y2, t.x1, t.y1) || eq(s.x2, s.y2, t.x2, t.y2)) return false
  const d1 = dd(t.x1, t.y1, t.x2, t.y2, s.x1, s.y1)
  const d2 = dd(t.x1, t.y1, t.x2, t.y2, s.x2, s.y2)
  const d3 = dd(s.x1, s.y1, s.x2, s.y2, t.x1, t.y1)
  const d4 = dd(s.x1, s.y1, s.x2, s.y2, t.x2, t.y2)
  return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
}
const name = (id) => (id === -1 ? 'junction' : (slug.get(id) ?? id))
const fmt = (s) => `${s.tag}[${name(s.ends[0])}->${name(s.ends[1])}] ` +
  `(${Math.round(s.x1)},${Math.round(s.y1)})->(${Math.round(s.x2)},${Math.round(s.y2)}) ` +
  `span=${Math.round(Math.hypot(s.x2 - s.x1, s.y2 - s.y1))}`
let n = 0
for (let i = 0; i < segs.length; i++) {
  for (let j = i + 1; j < segs.length; j++) {
    const s = segs[i], t = segs[j]
    if (s.hub || t.hub || !s.bright || !t.bright) continue
    if (!inter(s, t)) continue
    n++
    const dy = Math.abs(((s.y1 + s.y2) / 2) - ((t.y1 + t.y2) / 2))
    console.log(`#${n} dy=${Math.round(dy)}\n   A ${fmt(s)}\n   B ${fmt(t)}`)
  }
}
console.log(`total bb=${n}`)
