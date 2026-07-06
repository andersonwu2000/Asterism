import { useEffect, useRef, useState } from 'react'
import { usePoll } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { EmptyState, ErrorState, StatusBadge } from '../components/ui'
import GalaxyCard from '../components/GalaxyCard'
import type { BoardProblem, BoardResponse } from '../lib/types'

function GoalCounts({ p }: { p: BoardProblem }) {
  if (p.goals.total === 0) return <span className="text-xs text-ink-faint">—</span>
  return (
    <span className="tnum flex items-center gap-3 font-mono text-xs">
      <span className={p.goals.open > 0 ? 'text-accent' : 'text-ink-faint'}>
        {p.goals.open} open
      </span>
      <span className={p.goals.proved > 0 ? 'text-star' : 'text-ink-faint'}>
        {p.goals.proved} proved
      </span>
      {p.goals.shelved > 0 && <span className="text-ink-faint">{p.goals.shelved} shelved</span>}
    </span>
  )
}

/** Tiny progress bar: proved fraction of all goals, lit like a
 * constellation filling in. Hidden until there is any progress to show. */
function Progress({ p }: { p: BoardProblem }) {
  if (p.goals.total === 0 || (p.goals.proved === 0 && p.goals.open === 0)) return null
  const frac = p.goals.proved / p.goals.total
  return (
    <div className="h-[3px] w-24 overflow-hidden rounded-full bg-surface-3">
      <div
        className="h-full rounded-full bg-star/80 transition-[width] duration-700"
        style={{ width: `${frac * 100}%` }}
      />
    </div>
  )
}

function Row({ p }: { p: BoardProblem }) {
  const needsAction = p.status === 'awaiting_human' || p.status === 'signoff_pending'
  return (
    <tr
      className="h-11 cursor-pointer border-b border-edge/60 transition-colors duration-150 hover:bg-surface"
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
        <input
          ref={filterRef}
          className="w-64 rounded-md border border-edge bg-surface px-2.5 py-1.5 font-mono text-xs text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          placeholder="filter problems…  ( / )"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setQuery('')
              e.currentTarget.blur()
            }
          }}
        />
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
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {sorted.map((p) => (
            <GalaxyCard key={p.name} p={p} />
          ))}
        </div>
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
