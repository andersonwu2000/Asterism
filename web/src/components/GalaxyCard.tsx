import { useMemo } from 'react'
import { navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { StatusBadge } from './ui'
import type { BoardProblem } from '../lib/types'

/*
 * Galaxy view (charter appendix foreshadow): each problem is a small
 * constellation. Star positions are a deterministic hash of the problem
 * name (stable across polls — guardrail 1 applies here too); the lit
 * fraction mirrors proved/total. Decorative but honest about
 * proportions; the table view stays the forensic tool.
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

const HALO: Record<string, string> = {
  awaiting_human: 'border-warn/70',
  signoff_pending: 'border-warn/50',
  stalled: 'border-danger/40',
  bridged: 'border-star/40',
  ingested: 'border-ok/30',
  proving: 'border-accent/40',
  idle: 'border-edge',
}

/** Attention states carry the full badge on the card — a 1px halo is
 * not a signal (design review); dormant cards stay quiet. */
const BADGE_STATES = new Set(['awaiting_human', 'signoff_pending', 'stalled', 'proving'])

/** Truncate the namespace prefix, never the leaf — two adjacent
 * `Minif2f.mathd_algebr…` cards are indistinguishable. */
function displayName(name: string, budget = 26): string {
  if (name.length <= budget) return name
  return `…${name.slice(name.length - budget + 1)}`
}

export default function GalaxyCard({ p }: { p: BoardProblem }) {
  const stars = useMemo(() => {
    const rand = mulberry32(hash32(p.name))
    const n = Math.max(3, Math.min(p.goals.total || 5, 12))
    const pts: { x: number; y: number; r: number }[] = []
    for (let i = 0; i < n; i++) {
      pts.push({
        x: 12 + rand() * 116,
        y: 12 + rand() * 56,
        r: 1.6 + rand() * 1.6,
      })
    }
    // Connect left→right so the polyline reads as constellation
    // line-art instead of a scribble.
    pts.sort((a, b) => a.x - b.x)
    return pts
  }, [p.name, p.goals.total])

  const litCount =
    p.goals.total > 0 ? Math.round((p.goals.proved / p.goals.total) * stars.length) : 0

  return (
    <button
      className={`group relative flex flex-col rounded-lg border bg-surface text-left transition-all duration-150 hover:-translate-y-0.5 hover:bg-surface-2 ${
        HALO[p.status] ?? 'border-edge'
      }`}
      onClick={() => navigate(`/problems/${encodeURIComponent(p.name)}`)}
    >
      {BADGE_STATES.has(p.status) && (
        <div className="absolute top-2 right-2 z-10">
          <StatusBadge status={p.status} />
        </div>
      )}
      <svg viewBox="0 0 140 80" className="w-full">
        {stars.slice(0, -1).map((s, i) => {
          const t = stars[i + 1]
          return (
            <line
              key={i}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke={i < litCount - 1 ? 'var(--color-starlight)' : 'var(--color-edge-strong)'}
              strokeWidth={0.5}
              strokeOpacity={i < litCount - 1 ? 0.4 : 0.35}
            />
          )
        })}
        {stars.map((s, i) => {
          const lit = i < litCount
          return (
            <circle
              key={i}
              cx={s.x}
              cy={s.y}
              r={s.r}
              fill={lit ? 'var(--color-starlight)' : 'transparent'}
              stroke={lit ? 'var(--color-starlight)' : 'var(--color-ink-faint)'}
              strokeWidth={0.8}
              opacity={lit ? 0.9 : 0.5}
            />
          )
        })}
      </svg>
      <div className="border-t border-edge/60 px-3 py-2">
        {/* badge on its own row over the art keeps the name whole */}
        <div className="truncate font-mono text-xs text-ink" title={p.name}>
          {displayName(p.name)}
        </div>
        <div className="tnum mt-0.5 flex items-center justify-between text-[11px] text-ink-faint">
          <span>
            {p.goals.total === 0 ? 'no goals' : `${p.goals.proved}/${p.goals.total} proved`}
          </span>
          <span>{relTime(p.last_event)}</span>
        </div>
      </div>
    </button>
  )
}
