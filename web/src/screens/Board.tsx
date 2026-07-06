import { useEffect, useRef, useState } from 'react'
import { usePoll } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { EmptyState, ErrorState, StatusBadge } from '../components/ui'
import GalaxyCard from '../components/GalaxyCard'
import type { BoardProblem, BoardResponse } from '../lib/types'

function GoalCounts({ p }: { p: BoardProblem }) {
  // Zero-progress rows render as quiet dashes — nine "0 open 0 proved"
  // rows in a row is pure noise (design review). Numbers are UI, not
  // code: sans + tabular numerals, aligned sub-columns.
  if (p.goals.total === 0 || (p.goals.open === 0 && p.goals.proved === 0))
    return <span className="text-xs text-ink-faint">—</span>
  return (
    <span className="tnum flex items-center text-xs">
      <span className={`w-14 ${p.goals.open > 0 ? 'text-accent' : 'text-ink-faint'}`}>
        {p.goals.open} open
      </span>
      <span className={`w-18 ${p.goals.proved > 0 ? 'text-ink-dim' : 'text-ink-faint'}`}>
        {p.goals.proved} proved
      </span>
      {p.goals.shelved > 0 && <span className="text-ink-faint">{p.goals.shelved} shelved</span>}
    </span>
  )
}

/** Progress: proved fill on a visible track, with the open fraction as
 * a second (accent) segment — complete vs in-progress reads at a
 * glance instead of two identical full bars. */
function Progress({ p }: { p: BoardProblem }) {
  if (p.goals.total === 0 || (p.goals.proved === 0 && p.goals.open === 0)) return null
  const proved = (p.goals.proved / p.goals.total) * 100
  const open = (p.goals.open / p.goals.total) * 100
  return (
    <div className="flex h-[3px] w-24 overflow-hidden rounded-full bg-surface-3">
      <div
        className="h-full bg-star/80 transition-[width] duration-700"
        style={{ width: `${proved}%` }}
      />
      <div
        className="h-full bg-accent/50 transition-[width] duration-700"
        style={{ width: `${open}%` }}
      />
    </div>
  )
}

function Row({ p }: { p: BoardProblem }) {
  const needsAction = p.status === 'awaiting_human' || p.status === 'signoff_pending'
  return (
    <tr
      className="h-9 cursor-pointer border-b border-edge/60 transition-colors duration-150 hover:bg-surface"
      onClick={() => navigate(`/problems/${encodeURIComponent(p.name)}`)}
    >
      <td className="pr-4 pl-3">
        <span className="font-mono text-[13px] text-ink">{p.name}</span>
      </td>
      <td className="pr-4">
        {needsAction ? (
          <Link to="/inbox" onClick={(e) => e.stopPropagation()} title="Open in inbox">
            <StatusBadge status={p.status} />
          </Link>
        ) : (
          <StatusBadge status={p.status} />
        )}
      </td>
      <td className="pr-4">
        <GoalCounts p={p} />
      </td>
      <td className="pr-4">
        <Progress p={p} />
      </td>
      <td className="pr-4 text-xs whitespace-nowrap text-ink-dim">
        {p.in_flight > 0 && (
          <span className="flex items-center gap-1.5 text-accent">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            <span className="tnum">{p.in_flight} running</span>
          </span>
        )}
      </td>
      <td className="tnum pr-3 text-right text-xs whitespace-nowrap text-ink-faint">
        {relTime(p.last_event)}
      </td>
    </tr>
  )
}

const STATUS_ORDER = [
  'awaiting_human',
  'signoff_pending',
  'stalled',
  'proving',
  'idle',
  'ingested',
  'bridged',
]

export default function Board() {
  const { data, error, loading } = usePoll<BoardResponse>('/api/problems')
  const [view, setView] = useState<'list' | 'galaxy'>(
    () => (localStorage.getItem('board_view') as 'list' | 'galaxy') || 'list',
  )
  const switchView = (v: 'list' | 'galaxy') => {
    setView(v)
    localStorage.setItem('board_view', v)
  }
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const filterRef = useRef<HTMLInputElement>(null)

  // "/" focuses the filter from anywhere on the board
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === '/' && !(e.target instanceof HTMLInputElement) &&
          !(e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault()
        filterRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (loading)
    return (
      <div className="mx-auto max-w-5xl px-6 py-10">
        {Array.from({ length: 7 }, (_, i) => (
          <div
            key={i}
            className="mb-3 h-9 animate-pulse rounded-md bg-surface"
            style={{ animationDelay: `${i * 80}ms`, opacity: 1 - i * 0.11 }}
          />
        ))}
      </div>
    )
  if (error && !data) return <ErrorState error={error} />
  const problems = data?.problems ?? []

  if (problems.length === 0) {
    return (
      <EmptyState title="No problems yet">
        Add a problem under <code className="font-mono">Problems/</code> (Manifest.md + Defs.lean)
        and start the daemon — it will appear here.
      </EmptyState>
    )
  }

  const q = query.trim().toLowerCase()
  const filtered = problems.filter(
    (p) =>
      (q === '' || p.name.toLowerCase().includes(q)) &&
      (statusFilter === null || p.status === statusFilter),
  )
  const sorted = [...filtered].sort(
    (a, b) =>
      STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) ||
      (b.last_event ?? '').localeCompare(a.last_event ?? ''),
  )
  const attention = problems.filter(
    (p) => p.status === 'awaiting_human' || p.status === 'signoff_pending',
  ).length
  const statusCounts = new Map<string, number>()
  for (const p of problems) statusCounts.set(p.status, (statusCounts.get(p.status) ?? 0) + 1)

  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <div className="mb-3 flex items-center justify-between">
        <div className="tnum text-xs text-ink-dim">
          {problems.length} problems
          {attention > 0 && <span className="ml-2 text-danger">{attention} need attention</span>}
        </div>
        <div className="flex overflow-hidden rounded-md border border-edge text-xs">
          {(['list', 'galaxy'] as const).map((v) => (
            <button
              key={v}
              className={`px-2.5 py-1 transition-colors duration-150 ${
                view === v ? 'bg-surface-2 text-ink' : 'text-ink-faint hover:text-ink'
              }`}
              onClick={() => switchView(v)}
            >
              {v}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <div className="mb-3 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
          Live update failed ({error.message}) — showing last known state.
        </div>
      )}
      <div className="mb-3 flex items-center gap-2">
        <div className="relative">
          <input
            ref={filterRef}
            className="w-64 rounded-md border border-edge bg-surface py-1.5 pr-8 pl-2.5 text-xs text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
            placeholder="filter problems…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                setQuery('')
                e.currentTarget.blur()
              }
            }}
          />
          <kbd className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 rounded border border-edge bg-surface-2 px-1.5 text-[10px] text-ink-faint">
            /
          </kbd>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {STATUS_ORDER.filter((s) => (statusCounts.get(s) ?? 0) > 0).map((s) => (
            <button
              key={s}
              className={`rounded-full border px-2 py-0.5 text-[11px] ${
                statusFilter === s
                  ? 'border-accent/60 bg-accent/10 text-accent'
                  : 'border-edge text-ink-faint hover:text-ink'
              }`}
              onClick={() => setStatusFilter(statusFilter === s ? null : s)}
            >
              {s.replace('_', ' ')} {statusCounts.get(s)}
            </button>
          ))}
        </div>
        {(q !== '' || statusFilter !== null) && (
          <span className="text-xs text-ink-faint">{sorted.length} shown</span>
        )}
      </div>
      {view === 'galaxy' ? (
        (() => {
          // Dormant problems (idle, zero progress) demote to a compact
          // strip — a wall of dark stub cards drowned the live sky.
          const active = sorted.filter((p) => p.status !== 'idle')
          const dormant = sorted.filter((p) => p.status === 'idle')
          return (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                {active.map((p) => (
                  <GalaxyCard key={p.name} p={p} />
                ))}
              </div>
              {dormant.length > 0 && (
                <div className="mt-6">
                  <div className="mb-2 text-xs font-medium tracking-widest text-ink-faint uppercase">
                    not started ({dormant.length})
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {dormant.map((p) => (
                      <button
                        key={p.name}
                        className="rounded-md border border-edge px-2 py-1 font-mono text-[11px] text-ink-faint transition-colors hover:border-edge-strong hover:text-ink"
                        onClick={() => navigate(`/problems/${encodeURIComponent(p.name)}`)}
                        title={p.name}
                      >
                        {p.name.length > 30 ? `…${p.name.slice(-29)}` : p.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )
        })()
      ) : (
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-bg">
            <tr className="border-b border-edge text-xs text-ink-faint">
              <th className="py-2 pr-4 pl-4 font-medium">problem</th>
              <th className="py-2 pr-4 font-medium">status</th>
              <th className="py-2 pr-4 font-medium">goals</th>
              <th className="py-2 pr-4 font-medium">progress</th>
              <th className="py-2 pr-4 font-medium">activity</th>
              <th className="py-2 pr-4 text-right font-medium whitespace-nowrap">last event</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <Row key={p.name} p={p} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
