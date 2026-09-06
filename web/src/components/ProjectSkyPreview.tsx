import { useEffect, useMemo, useRef, useState } from 'react'
import { usePoll } from '../lib/api'
import { previewCandidates } from '../lib/projectShelf'
import { layoutConstellation } from '../lib/layout'
import { ALIAS_DASH, CITE_DASH, citeInk, citePath, edgeStroke, nodeStyle, radius } from '../lib/sky'
import { DEF_KINDS } from '../lib/vocab'
import type { BoardResponse, ProblemDetail } from '../lib/types'

/** A still of a REAL complete sky. Shares the full map's layout, ink,
 * shapes and edge vocabulary; no controls, invented stars or live pulses.
 * The snapshot is explicitly labelled, since it is not a polling monitor. */
function Miniature({ data }: { data: ProblemDetail }) {
  const layout = useMemo(() => layoutConstellation(data.goals, data.strategies,
    data.strategy_edges, data.anchor_edges, data.citation_edges, 2.1), [data])
  // Fit the actual marks, not the full map's reserved reading space.
  // A four-node horizontal sky should sit in the middle of its tile.
  const xs = layout.nodes.map(n => n.x), ys = layout.nodes.map(n => n.y)
  const left = Math.min(...xs) - 60, top = Math.min(...ys) - 60
  const width = Math.max(...xs) - left + 60, height = Math.max(...ys) - top + 60
  const scale = Math.min(552 / width, 220 / height, 1)
  const point = (p: { x: number; y: number }) => ({
    x: (600 - width * scale) / 2 + (p.x - left) * scale,
    y: (260 - height * scale) / 2 + (p.y - top) * scale,
  })
  const nodes = new Map(layout.nodes.map(n => [n.goal.id, { ...point(n), goal: n.goal, source: n }]))
  const origin = point({ x: 0, y: 0 })
  const hasLive = data.goals.some(g => ['open', 'attempting', 'pending_strategist_review'].includes(g.status))
  const anchors = new Set(data.anchor_edges.flatMap(e => [e.from, e.to]))
  return (
    <svg viewBox="0 0 600 260" className="h-full w-full [mask-image:linear-gradient(to_bottom,transparent,var(--color-ink)_22%,var(--color-ink)_72%,transparent)]" role="img" aria-label={`Proof map snapshot of ${data.name}`}>
      <g fill="none" strokeWidth="0.75">
        {layout.edges.map((e, i) => {
          const a = nodes.get(e.from), b = nodes.get(e.to)
          if (!a || !b) return null
          const curved = e.kind === 'citation' || e.kind === 'alias' || Math.hypot(b.source.x - a.source.x, b.source.y - a.source.y) > 480
          return <path key={i} d={curved ? citePath(a.source, b.source, e.from, e.to).d : `M${a.source.x},${a.source.y} L${b.source.x},${b.source.y}`}
            transform={`translate(${origin.x} ${origin.y}) scale(${scale})`} vectorEffect="non-scaling-stroke"
            stroke={edgeStroke(e.strategyStatus, e.kind)}
            strokeDasharray={e.kind === 'citation' ? CITE_DASH : e.kind === 'alias' ? ALIAS_DASH : undefined}
            opacity={e.kind === 'citation' ? citeInk(layout.edges.length) : 0.45} />
        })}
        {layout.bundles.map(bundle => {
          const parent = nodes.get(bundle.parentId), junction = point(bundle.junction)
          if (!parent) return null
          return <g key={bundle.strategyId} stroke={edgeStroke(bundle.status, 'strategy')} opacity="0.5">
            <path d={`M${parent.x},${parent.y} L${junction.x},${junction.y}`} />
            {bundle.children.map(id => {
              const child = nodes.get(id)
              return child ? <path key={id} d={`M${junction.x},${junction.y} L${child.x},${child.y}`} /> : null
            })}
          </g>
        })}
      </g>
      {[...nodes.values()].map(({ goal: g, x, y }) => {
        const mark = nodeStyle(g, hasLive)
        const r = radius(g) / 4.5 * Math.max(1.15, Math.min(2.5, 4.5 * scale))
        const definition = DEF_KINDS.has(g.kind)
        return <g key={g.id} data-preview-goal={g.id} transform={`translate(${x} ${y})`} opacity={mark.opacity}>
          {(g.origin === 'root' || g.human_facing_claim || (definition && anchors.has(g.id))) &&
            <circle r={r + 2.3} fill="none" stroke={mark.stroke} strokeWidth="0.6" opacity="0.75" />}
          {definition
            ? <rect x={-r * 0.85} y={-r * 0.85} width={r * 1.7} height={r * 1.7} transform="rotate(45)" fill={mark.fill} stroke={mark.stroke} strokeWidth="0.65" />
            : <circle r={r} fill={mark.fill} stroke={mark.stroke} strokeWidth="0.65" />}
        </g>
      })}
    </svg>
  )
}

function Candidate({ name, onEmpty }: { name: string; onEmpty: () => void }) {
  const { data, error } = usePoll<ProblemDetail>(`/api/problems/${encodeURIComponent(name)}`, 0)
  const empty = data?.goals.length === 0
  useEffect(() => { if (empty) onEmpty() }, [empty, onEmpty])
  if (error) return <span className="text-xs text-ink-faint">Preview unavailable — open the project to continue.</span>
  if (!data || empty) return <span className="text-xs text-ink-faint">Reading a proof map…</span>
  return <>
    <Miniature data={data} />
    <span className="absolute inset-x-6 bottom-14 truncate text-[10px] text-ink-faint" title={name}>
      <span className="font-mono">{name.split('.').pop()}</span> · snapshot
    </span>
  </>
}

function PreviewSource({ project }: { project: string }) {
  const { data, error } = usePoll<BoardResponse>(`/api/problems?project=${encodeURIComponent(project)}`, 0)
  const [sample] = useState(Math.random)
  const [index, setIndex] = useState(0)
  const candidates = useMemo(() => previewCandidates(data?.problems ?? [], project, sample), [data, project, sample])
  if (error) return <span className="text-xs text-ink-faint">Preview unavailable — open the project to continue.</span>
  if (!data) return <span className="text-xs text-ink-faint">Finding a proof map…</span>
  const name = candidates[index]
  return name ? <Candidate key={name} name={name} onEmpty={() => setIndex(i => i + 1)} />
    : <span className="text-xs text-ink-faint">A proof map will appear when a task has goals.</span>
}

/** Only cards near the viewport fetch a task list and ONE detail. A
 * large project never downloads all its proof graphs for a thumbnail. */
export default function ProjectSkyPreview({ project, empty }: { project: string; empty: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) { setVisible(true); observer.disconnect() }
    }, { rootMargin: '120px' })
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return <div ref={ref} className="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center overflow-hidden px-3 pt-16 pb-12">
    <div className="flex h-full w-full items-center justify-center">
      {empty ? null : visible ? <PreviewSource project={project} /> : null}
    </div>
    {empty && <span className="absolute inset-x-6 bottom-14 text-xs text-ink-faint">Your first question starts a new sky.</span>}
  </div>
}
