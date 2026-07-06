import { useEffect, useRef, useState } from 'react'
import { usePoll } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { EmptyState, ErrorState, StatusBadge } from '../components/ui'
import type { BoardProblem, BoardResponse, Meta } from '../lib/types'

/*
 * Board = the observatory's survey sheet. The eye should land on, in
 * order: what needs the human, what the engine is doing right now,
 * what settled recently — and only then the archive, which folds into
 * namespace clusters so 250 finished benchmarks read as one quiet row
 * instead of 250 identical pills.
 */

function GoalCounts({ p }: { p: BoardProblem }) {
  if (p.goals.total === 0 || (p.goals.open === 0 && p.goals.proved === 0))
    return <span className="text-xs text-ink-faint">—</span>
  // one nowrap line that truncates — a mid-word wrap inside a table
  // cell is worse than losing the (tertiary) shelved count
  return (
    <span className="tnum block truncate text-xs whitespace-nowrap">
      {p.goals.open > 0 && <span className="text-accent">{p.goals.open} open · </span>}
      <span className={p.goals.proved > 0 ? 'text-ink-dim' : 'text-ink-faint'}>
        {p.goals.proved} proved
      </span>
      {p.goals.shelved > 0 && (
        <span className="text-ink-faint"> · {p.goals.shelved} shelved</span>
      )}
    </span>
  )
}

/** Two honest channels: width ∝ √total (a 240-goal campaign should not
 * look like a 3-goal toy) and fill = composition, with the settled-but-
 * unproved remainder (shelved/dead) drawn as labeled grey ink instead
 * of masquerading as "unfinished". */
function ProgressBar({
  proved,
  open,
  total,
}: {
  proved: number
  open: number
  total: number
}) {
  if (total === 0 || (proved === 0 && open === 0)) return null
  const w = Math.round(Math.min(128, Math.max(36, Math.sqrt(total) * 10)))
  const rest = Math.max(0, total - proved - open)
  return (
    <div
      className="flex h-1 overflow-hidden rounded-full bg-surface-3"
      style={{ width: w }}
      title={`${proved} proved · ${open} open${rest > 0 ? ` · ${rest} shelved/dead` : ''} of ${total}`}
    >
      <div
        className="h-full bg-starlight/80 transition-[width] duration-700"
        style={{ width: `${(proved / total) * 100}%` }}
      />
      <div
        className="h-full bg-accent/50 transition-[width] duration-700"
        style={{ width: `${(open / total) * 100}%` }}
      />
      <div className="h-full bg-ink-faint/30" style={{ width: `${(rest / total) * 100}%` }} />
    </div>
  )
}

/** Quiet text status for settled rows — the pill treatment is reserved
 * for states that ask something of the reader. */
const SETTLED_LABEL: Record<string, string> = {
  ingested: 'ingested',
  bridged: 'bridged ◆',
  idle: 'not started',
}

function Row({ p, dense, stripPrefix }: { p: BoardProblem; dense?: boolean; stripPrefix?: string }) {
  const needsAction = p.status === 'awaiting_human' || p.status === 'signoff_pending'
  const settled = p.status === 'ingested' || p.status === 'bridged' || p.status === 'idle'
  // inside an expanded cluster the group header already carries the
  // namespace — repeating it every dense row is noise
  const shown =
    stripPrefix && p.name.startsWith(`${stripPrefix}.`)
      ? p.name.slice(stripPrefix.length + 1)
      : p.name
  return (
    <tr
      data-kind="problem"
      className={`cursor-pointer border-b border-edge/60 transition-colors duration-150 hover:bg-surface ${
        dense ? 'h-8' : 'h-9'
      }`}
      onClick={() => navigate(`/problems/${encodeURIComponent(p.name)}`)}
    >
      <td className={dense ? 'pr-4 pl-7' : 'pr-4 pl-3'}>
        {/* a real link: keyboard reachable (the row onClick is mouse sugar) */}
        <span className="flex min-w-0 items-center gap-2">
          <Link
            to={`/problems/${encodeURIComponent(p.name)}`}
            className={`truncate font-mono text-[13px] ${dense ? 'text-ink-dim' : 'text-ink'}`}
            title={p.name}
            onClick={(e) => e.stopPropagation()}
          >
            {shown}
          </Link>
          {p.in_flight > 0 && (
            <span
              className="tnum flex shrink-0 items-center gap-1.5 text-[11px] text-accent"
              title={`${p.in_flight} agent(s) running now`}
            >
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
              {p.in_flight}
            </span>
          )}
        </span>
      </td>
      <td className="pr-4">
        {needsAction ? (
          <Link to="/inbox" onClick={(e) => e.stopPropagation()} title="Open in inbox">
            <StatusBadge status={p.status} />
          </Link>
        ) : settled ? (
          <span className={`text-[11px] ${p.status === 'bridged' ? 'text-star/70' : 'text-ink-faint'}`}>
            {SETTLED_LABEL[p.status]}
          </span>
        ) : (
          <StatusBadge status={p.status} />
        )}
      </td>
      <td className="pr-4">
        <GoalCounts p={p} />
      </td>
      <td className="pr-4">
        <ProgressBar proved={p.goals.proved} open={p.goals.open} total={p.goals.total} />
      </td>
      <td className="tnum pr-3 text-right text-xs whitespace-nowrap text-ink-faint">
        {/* a blocking request's age is the product's most important
            number — escalate it instead of whispering it */}
        {needsAction && ageDays(p.last_event) >= 2 ? (
          <span className="font-medium text-warn">waiting {ageDays(p.last_event)}d</span>
        ) : (
          relTime(p.last_event)
        )}
      </td>
    </tr>
  )
}

function ageDays(iso: string | null): number {
  if (!iso) return 0
  return Math.floor((Date.now() - Date.parse(iso)) / 86400_000)
}

function SectionRow({ label, count }: { label: string; count?: number }) {
  return (
    <tr>
      <td colSpan={5} className="pt-5 pb-1.5 pl-3">
        <span className="text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
          {label}
        </span>
        {count !== undefined && (
          <span className="tnum ml-2 text-[11px] text-ink-faint/70">{count}</span>
        )}
      </td>
    </tr>
  )
}

interface Cluster {
  prefix: string
  items: BoardProblem[]
  proved: number
  total: number
  open: number
  bridged: number
  lastEvent: string | null
}

function clusterize(items: BoardProblem[]): Cluster[] {
  const map = new Map<string, BoardProblem[]>()
  for (const p of items) {
    const prefix = p.name.includes('.') ? p.name.split('.')[0] : 'ungrouped'
    const arr = map.get(prefix)
    if (arr) arr.push(p)
    else map.set(prefix, [p])
  }
  const clusters: Cluster[] = []
  for (const [prefix, arr] of map) {
    arr.sort((a, b) => a.name.localeCompare(b.name))
    clusters.push({
      prefix,
      items: arr,
      proved: arr.reduce((s, p) => s + p.goals.proved, 0),
      total: arr.reduce((s, p) => s + p.goals.total, 0),
      open: arr.reduce((s, p) => s + p.goals.open, 0),
      bridged: arr.filter((p) => p.status === 'bridged').length,
      lastEvent: arr.reduce<string | null>(
        (m, p) => (p.last_event && (!m || p.last_event > m) ? p.last_event : m),
        null,
      ),
    })
  }
  clusters.sort((a, b) => b.items.length - a.items.length || a.prefix.localeCompare(b.prefix))
  return clusters
}

function ClusterRow({
  c,
  expanded,
  onToggle,
}: {
  c: Cluster
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <tr
      className="h-9 cursor-pointer border-b border-edge/60 transition-colors duration-150 hover:bg-surface"
      onClick={onToggle}
    >
      <td className="pr-4 pl-3">
        <button
          className="flex items-center gap-2"
          onClick={(e) => {
            e.stopPropagation()
            onToggle()
          }}
          aria-expanded={expanded}
        >
          <svg
            width="9"
            height="9"
            viewBox="0 0 10 10"
            className={`shrink-0 text-ink-faint transition-transform duration-150 ${expanded ? 'rotate-90' : ''}`}
            aria-hidden
          >
            <path d="M3 1.5L7.5 5 3 8.5" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" />
          </svg>
          <span className="font-mono text-[13px] text-ink">{c.prefix}</span>
          <span className="tnum text-[11px] text-ink-faint">{c.items.length} problems</span>
        </button>
      </td>
      <td className="pr-4">
        {c.bridged > 0 && (
          <span className="tnum text-[11px] text-star/70">{c.bridged} bridged ◆</span>
        )}
      </td>
      <td className="pr-4">
        <span className="tnum text-xs text-ink-faint">
          {c.proved > 0 && `${c.proved} proved`}
        </span>
      </td>
      <td className="pr-4">
        <ProgressBar proved={c.proved} open={c.open} total={c.total} />
      </td>
      <td className="tnum pr-3 text-right text-xs whitespace-nowrap text-ink-faint">
        {relTime(c.lastEvent)}
      </td>
    </tr>
  )
}

/* attention → live → settled → dormant */
const STATUS_ORDER = [
  'awaiting_human',
  'signoff_pending',
  'stalled',
  'proving',
  'ingested',
  'bridged',
  'idle',
]

const STATUS_FILTER_LABEL: Record<string, string> = {
  awaiting_human: 'needs input',
  signoff_pending: 'sign-off',
  stalled: 'stalled',
  proving: 'proving',
  ingested: 'ingested',
  bridged: 'bridged',
  idle: 'not started',
}

const WEEK_MS = 7 * 86400_000

export default function Board() {
  const { data, error, loading } = usePoll<BoardResponse>('/api/problems')
  const { data: meta } = usePoll<Meta>('/api/meta', 5000)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const filterRef = useRef<HTMLInputElement>(null)

  // "/" focuses the filter from anywhere on the board
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.key === '/' &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault()
        filterRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (loading)
    return (
      <div className="mx-auto max-w-6xl px-6 py-10">
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
  const filtering = q !== '' || statusFilter !== null
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

  // ---- attention / motion / recent / archive partition (list view) ----
  const now = Date.now()
  const isRecent = (p: BoardProblem) =>
    p.last_event !== null && now - Date.parse(p.last_event) < WEEK_MS
  const needsYou = sorted.filter(
    (p) => p.status === 'awaiting_human' || p.status === 'signoff_pending' || p.status === 'stalled',
  )
  const inMotion = sorted.filter(
    (p) => !needsYou.includes(p) && (p.status === 'proving' || p.in_flight > 0 || p.queued > 0),
  )
  const hot = new Set([...needsYou, ...inMotion].map((p) => p.name))
  const recent = sorted.filter((p) => !hot.has(p.name) && isRecent(p))
  for (const p of recent) hot.add(p.name)
  const archive = sorted.filter((p) => !hot.has(p.name))
  const clusters = clusterize(archive)

  const toggleCluster = (prefix: string) =>
    setExpanded((old) => {
      const next = new Set(old)
      if (next.has(prefix)) next.delete(prefix)
      else next.add(prefix)
      return next
    })

  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <div className="mb-4 flex items-end justify-between">
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-[22px] font-medium text-ink">Problems</h1>
          <span className="tnum text-xs text-ink-faint">
            {problems.length}
            {attention > 0 && (
              <span className="ml-2 font-medium text-warn">{attention} need input</span>
            )}
          </span>
        </div>
      </div>
      {error && (
        <div className="mb-3 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
          Live update failed ({error.message}) — showing last known state.
        </div>
      )}
      {/* the board must not imply motion the engine isn't making */}
      {meta && !meta.daemon.running && !meta.daemon.stopping && inMotion.length > 0 && (
        <div className="mb-3 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
          The daemon is idle — {inMotion.length} problem{inMotion.length === 1 ? '' : 's'} in
          motion {inMotion.length === 1 ? 'is' : 'are'} not being worked.{' '}
          <Link to="/telemetry" className="underline">
            Start it from the Engine page
          </Link>
          .
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
                  ? 'border-star/60 bg-star/10 text-star'
                  : 'border-edge text-ink-faint hover:text-ink'
              }`}
              onClick={() => setStatusFilter(statusFilter === s ? null : s)}
            >
              {STATUS_FILTER_LABEL[s] ?? s} {statusCounts.get(s)}
            </button>
          ))}
        </div>
        {filtering && <span className="text-xs text-ink-faint">{sorted.length} shown</span>}
      </div>
      {/* table-fixed + truncating name cell: long mono names must not
          push "last event" off a laptop screen (main clips overflow) */}
      {(
        <table className="w-full table-fixed border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-bg">
            <tr className="border-b border-edge text-xs text-ink-faint">
              <th className="py-2 pr-4 pl-3 font-medium">problem</th>
              <th className="w-[120px] py-2 pr-4 font-medium">status</th>
              <th className="w-[170px] py-2 pr-4 font-medium">goals</th>
              <th className="w-[130px] py-2 pr-4 font-medium">progress</th>
              <th className="w-[80px] py-2 pr-3 text-right font-medium whitespace-nowrap">
                last event
              </th>
            </tr>
          </thead>
          {filtering ? (
            /* Filtering flattens the survey — results are what you asked
               for, not the attention hierarchy. */
            <tbody>
              {sorted.map((p) => (
                <Row key={p.name} p={p} />
              ))}
            </tbody>
          ) : (
            <tbody>
              {needsYou.length > 0 && (
                <>
                  <SectionRow label="Needs you" count={needsYou.length} />
                  {needsYou.map((p) => (
                    <Row key={p.name} p={p} />
                  ))}
                </>
              )}
              {inMotion.length > 0 && (
                <>
                  <SectionRow label="In motion" count={inMotion.length} />
                  {inMotion.map((p) => (
                    <Row key={p.name} p={p} />
                  ))}
                </>
              )}
              {recent.length > 0 && (
                <>
                  <SectionRow label="Recent" count={recent.length} />
                  {recent.map((p) => (
                    <Row key={p.name} p={p} />
                  ))}
                </>
              )}
              {clusters.length > 0 && (
                <>
                  <SectionRow
                    label="Archive"
                    count={archive.length}
                  />
                  {clusters.map((c) =>
                    c.items.length === 1 ? (
                      <Row key={c.items[0].name} p={c.items[0]} />
                    ) : (
                      <PerCluster
                        key={c.prefix}
                        c={c}
                        expanded={expanded.has(c.prefix)}
                        onToggle={() => toggleCluster(c.prefix)}
                      />
                    ),
                  )}
                </>
              )}
            </tbody>
          )}
        </table>
      )}
    </div>
  )
}

function PerCluster({
  c,
  expanded,
  onToggle,
}: {
  c: Cluster
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <>
      <ClusterRow c={c} expanded={expanded} onToggle={onToggle} />
      {expanded && c.items.map((p) => <Row key={p.name} p={p} dense stripPrefix={c.prefix} />)}
    </>
  )
}
