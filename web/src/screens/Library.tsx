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

function Cluster({ p }: { p: LibraryProblem }) {
  const [hover, setHover] = useState<StarPt | null>(null)
  const { w, h } = clusterSize(p.decls.length)
  const { stars, spine } = useMemo(() => {
    const rand = mulberry32(hash32(p.problem))
    const pts: StarPt[] = p.decls.map((decl) => ({
      x: 10 + rand() * (w - 20),
      y: 8 + rand() * (h - 30),
      r: 1.1 + rand() * 1.7,
      decl,
    }))
    // Atlas convention: line-art joins only the brightest few; the
    // rest are the star field. 258 connected stars read as static.
    const spine = [...pts]
      .sort((a, b) => b.r - a.r)
      .slice(0, Math.min(10, Math.max(3, Math.round(Math.sqrt(pts.length) * 1.5))))
      .sort((a, b) => a.x - b.x)
    return { stars: pts, spine }
  }, [p, w, h])

  const ns = p.problem.includes('.') ? p.problem.slice(0, p.problem.indexOf('.')) : null
  const leaf = ns ? p.problem.slice(ns.length + 1) : p.problem

  return (
    <div className="relative" style={{ width: w }}>
      <svg width={w} height={h} className="block">
        {spine.slice(0, -1).map((s, i) => (
          <line
            key={i}
            x1={s.x}
            y1={s.y}
            x2={spine[i + 1].x}
            y2={spine[i + 1].y}
            stroke="var(--color-starlight)"
            strokeWidth={0.5}
            strokeOpacity={0.28}
          />
        ))}
        {stars.map((s, i) =>
          DEF_KINDS.has(s.decl.decl_kind ?? '') ? (
            <rect
              key={i}
              x={s.x - s.r * 1.2}
              y={s.y - s.r * 1.2}
              width={s.r * 2.4}
              height={s.r * 2.4}
              transform={`rotate(45 ${s.x} ${s.y})`}
              fill="var(--color-starlight)"
              opacity={0.55 + s.r * 0.16}
              onMouseEnter={() => setHover(s)}
              onMouseLeave={() => setHover(null)}
            />
          ) : (
            <circle
              key={i}
              cx={s.x}
              cy={s.y}
              r={s.r}
              fill="var(--color-starlight)"
              opacity={0.3 + s.r * 0.22}
              onMouseEnter={() => setHover(s)}
              onMouseLeave={() => setHover(null)}
            />
          ),
        )}
      </svg>
      <Link
        to={`/problems/${encodeURIComponent(p.problem)}`}
        className="group block pb-1"
        title={`open ${p.problem}`}
      >
        {ns && (
          <span className="block truncate font-mono text-[10px] leading-tight text-ink-faint">
            {ns}
          </span>
        )}
        <span className="block truncate font-mono text-xs text-ink-dim transition-colors group-hover:text-ink">
          {leaf}
          <span className="tnum ml-2 text-[10px] text-ink-faint">{p.decls.length}</span>
        </span>
      </Link>
      {hover && (
        <div
          className="pointer-events-none absolute z-10 max-w-xs rounded-md border border-edge-strong bg-surface-3 px-2.5 py-1.5"
          style={{
            left: Math.min(hover.x + 10, w - 180),
            top: Math.min(hover.y + 10, h - 20),
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

  if (loading) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  const problems = [...(data?.problems ?? [])].sort((a, b) => b.decls.length - a.decls.length)
  const declCount = problems.reduce((s, p) => s + p.decls.length, 0)

  if (problems.length === 0) {
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
            <span className="font-display text-[15px] text-ink-dim">{problems.length}</span>{' '}
            constellations ·{' '}
            <span className="font-display text-[15px] text-ink-dim">{declCount}</span>{' '}
            declarations
          </span>
        </div>
        <div className="flex flex-wrap items-end gap-x-10 gap-y-8">
          {problems.map((p) => (
            <Cluster key={p.problem} p={p} />
          ))}
        </div>
      </div>
    </div>
  )
}
