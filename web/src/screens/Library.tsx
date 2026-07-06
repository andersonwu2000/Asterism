import { useMemo, useState } from 'react'
import { usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { EmptyState, ErrorState } from '../components/ui'
import type { LibraryDecl, LibraryProblem } from '../lib/types'

/*
 * Library Atlas — the harvested corpus as one sky. Each bridged problem
 * is a small constellation of its declarations; hovering a star reads
 * the actual mathematics (blueprint spirit: the machine's work,
 * re-told legibly). Data degrades gracefully: older harvests carry no
 * kind/signature and render as plain stars.
 */

function hash32(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function mulberry32(seed: number): () => number {
  let a = seed
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const DEF_KINDS = new Set(['def', 'induct', 'structure', 'class', 'instance', 'abbrev'])

interface StarPt {
  x: number
  y: number
  r: number
  decl: LibraryDecl
}

/** Cluster canvas grows with the constellation: sqrt-scaled so
 * banach_tarski (155 decls) is grand but not a wall. */
function clusterSize(n: number): { w: number; h: number } {
  const w = Math.min(150 + Math.sqrt(n) * 26, 480)
  return { w, h: w * 0.52 }
}

function Cluster({ p, query }: { p: LibraryProblem; query: string }) {
  const [hover, setHover] = useState<StarPt | null>(null)
  const { w, h } = clusterSize(p.decls.length)
  const match = (d: LibraryDecl) =>
    query !== '' && (d.name ?? d.slug).toLowerCase().includes(query)
  const stars = useMemo<StarPt[]>(() => {
    // Position is honestly non-quantitative (seeded sky aesthetic);
    // size/brightness must not fake importance, so they stay within a
    // narrow texture band, and no line-art pretends structure the data
    // doesn't carry. (Real usage/dependency weights are an engine-API
    // item — when they land, size/brightness get meaning.)
    const rand = mulberry32(hash32(p.problem))
    return p.decls.map((decl) => ({
      x: 10 + rand() * (w - 20),
      y: 8 + rand() * (h - 30),
      r: 1.4 + rand() * 0.5,
      decl,
    }))
  }, [p, w, h])

  const ns = p.problem.includes('.') ? p.problem.slice(0, p.problem.indexOf('.')) : null
  const leaf = ns ? p.problem.slice(ns.length + 1) : p.problem

  return (
    <div className="relative" style={{ width: w }}>
      <svg width={w} height={h} className="block">
        {/* generous invisible hit areas — 1.5px stars are not targets */}
        {stars.map((s, i) => (
          <circle
            key={`hit${i}`}
            cx={s.x}
            cy={s.y}
            r={Math.max(s.r + 4, 5)}
            fill="transparent"
            onMouseEnter={() => setHover(s)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
        {stars.map((s, i) => {
          const hit = match(s.decl)
          const fill = hit ? 'var(--color-star)' : 'var(--color-starlight)'
          const dim = query !== '' && !hit
          return DEF_KINDS.has(s.decl.decl_kind ?? '') ? (
            <rect
              key={i}
              x={s.x - s.r * 1.2}
              y={s.y - s.r * 1.2}
              width={s.r * 2.4}
              height={s.r * 2.4}
              transform={`rotate(45 ${s.x} ${s.y})`}
              fill={fill}
              opacity={dim ? 0.15 : hit ? 1 : 0.8}
              onMouseEnter={() => setHover(s)}
              onMouseLeave={() => setHover(null)}
            />
          ) : (
            <circle
              key={i}
              cx={s.x}
              cy={s.y}
              r={hit ? s.r + 0.8 : s.r}
              fill={fill}
              opacity={dim ? 0.12 : hit ? 1 : 0.62}
              onMouseEnter={() => setHover(s)}
              onMouseLeave={() => setHover(null)}
            />
          )
        })}
      </svg>
      {/* the section header carries the namespace — the card shows the leaf */}
      <Link
        to={`/problems/${encodeURIComponent(p.problem)}`}
        className="group block pb-1"
        title={`open ${p.problem}`}
      >
        <span className="block truncate font-mono text-xs text-ink-dim transition-colors group-hover:text-ink">
          {leaf}
          <span className="tnum ml-2 text-[10px] text-ink-faint">{p.decls.length}</span>
        </span>
      </Link>
      {hover && (
        <div
          className="pointer-events-none absolute z-10 max-w-xs rounded-md border border-edge-strong bg-surface-3 px-2.5 py-1.5"
          style={{
            left: Math.max(0, Math.min(hover.x + 10, w - 180)),
            top: Math.max(0, Math.min(hover.y + 10, h - 20)),
          }}
        >
          <div className="font-mono text-[11px] break-all text-ink">
            {(hover.decl.name ?? hover.decl.slug).split('.').pop()}
          </div>
          {hover.decl.signature && (
            <div className="mt-0.5 line-clamp-3 font-mono text-[10px] leading-snug break-words text-ink-dim">
              {hover.decl.signature}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Library() {
  const { data, error, loading } = usePoll<{ problems: LibraryProblem[] }>('/api/library', 30000)
  const [query, setQuery] = useState('')

  if (loading) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  const all = [...(data?.problems ?? [])].sort((a, b) => b.decls.length - a.decls.length)
  const declCount = all.reduce((s, p) => s + p.decls.length, 0)
  const q = query.trim().toLowerCase()
  // a constellation stays visible if its name or any star matches
  const problems =
    q === ''
      ? all
      : all.filter(
          (p) =>
            p.problem.toLowerCase().includes(q) ||
            p.decls.some((d) => (d.name ?? d.slug).toLowerCase().includes(q)),
        )
  const hitCount =
    q === ''
      ? 0
      : all.reduce(
          (s, p) => s + p.decls.filter((d) => (d.name ?? d.slug).toLowerCase().includes(q)).length,
          0,
        )

  if (all.length === 0) {
    return (
      <EmptyState title="The Library is empty">
        Approved harvests land here — finish a problem and sign off its ingest.
      </EmptyState>
    )
  }

  return (
    <div className="relative min-h-full">
      {/* one sky behind every constellation */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 60% 45% at 28% 18%, color-mix(in srgb, var(--color-accent) 5%, transparent), transparent), radial-gradient(ellipse 50% 40% at 75% 70%, color-mix(in srgb, var(--color-star) 4%, transparent), transparent)',
        }}
      />
      <div className="relative mx-auto max-w-6xl px-6 py-6">
        <div className="mb-6 flex items-baseline gap-4">
          <h1 className="font-display text-[22px] font-medium text-ink">Library</h1>
          <span className="tnum text-xs text-ink-faint">
            <span className="font-display text-[15px] text-ink-dim">{all.length}</span>{' '}
            constellations ·{' '}
            <span className="font-display text-[15px] text-ink-dim">{declCount}</span>{' '}
            declarations
          </span>
          <span className="ml-auto flex items-center gap-2">
            {q !== '' && (
              <span className="tnum text-[11px] text-star">{hitCount} stars lit</span>
            )}
            <input
              className="w-56 rounded-md border border-edge bg-surface py-1.5 px-2.5 font-mono text-xs text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-accent focus:outline-none"
              placeholder="find a declaration…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') {
                  setQuery('')
                  e.currentTarget.blur()
                }
              }}
            />
          </span>
        </div>
        {problems.length === 0 ? (
          <div className="py-16 text-center text-xs text-ink-faint">
            No declaration matches “{query}”.
          </div>
        ) : (
          (() => {
            // domain sections give the sky an index — 44 unsectioned
            // panels have no information scent
            const groups = new Map<string, LibraryProblem[]>()
            for (const p of problems) {
              const ns = p.problem.includes('.') ? p.problem.split('.')[0] : 'ungrouped'
              groups.set(ns, [...(groups.get(ns) ?? []), p])
            }
            const ordered = [...groups.entries()].sort(
              (a, b) =>
                b[1].reduce((s, p) => s + p.decls.length, 0) -
                a[1].reduce((s, p) => s + p.decls.length, 0),
            )
            return ordered.map(([ns, ps]) => (
              <section key={ns} className="mb-10">
                <div className="mb-3 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
                  {ns}
                  <span className="tnum ml-2 normal-case tracking-normal text-ink-faint/70">
                    {ps.reduce((s, p) => s + p.decls.length, 0)} decls
                  </span>
                </div>
                <div className="flex flex-wrap items-end gap-x-10 gap-y-8">
                  {ps.map((p) => (
                    <Cluster key={p.problem} p={p} query={q} />
                  ))}
                </div>
              </section>
            ))
          })()
        )}
      </div>
    </div>
  )
}
