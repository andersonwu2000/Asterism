import { useEffect, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { Lean } from '../lib/lean'
import { goalStatusLabel } from '../lib/vocab'
import { Button, ErrorState, StatusBadge } from '../components/ui'
import Constellation from '../components/Constellation'
import GoalPanel from '../components/GoalPanel'
import StrategyPanel from '../components/StrategyPanel'
import DecisionTimeline from '../components/DecisionTimeline'
import FileViewer from '../components/FileViewer'
import ManifestEditor from '../components/ManifestEditor'
import RunControl from '../components/RunControl'
import type { DaemonStatus, Goal, ProblemDetail } from '../lib/types'

type Tab = 'stars' | 'manifest' | 'goals' | 'timeline' | 'files'

/* proved is the settled majority — it reads quiet; color is spent on
 * the live minority (open/attempting) and exceptions. */
const GOAL_STATUS_CLS: Record<string, string> = {
  proved: 'text-ink-faint',
  attempting: 'text-accent',
  open: 'text-accent',
  shelved: 'text-ink-faint',
  pending_strategist_review: 'text-warn',
  disproved: 'text-danger',
  dead: 'text-ink-faint',
  frozen: 'text-ink-faint',
}

/* live work first, settled bulk after */
const GOAL_SORT: Record<string, number> = {
  attempting: 0,
  open: 1,
  pending_strategist_review: 2,
  disproved: 3,
  frozen: 4,
  proved: 5,
  shelved: 6,
  dead: 7,
}

/** Fold a statement's leading `letI …;` / `let …;` / `haveI …;` binder
 * chain (`;`-separated) into a count prefix — a truncating table cell
 * would otherwise show only the first binder and none of the actual
 * proposition. No `;`-separated binder prefix → returned unchanged. */
function stripBinders(statement: string): string {
  if (!/^(letI|haveI|let)\b/.test(statement)) return statement
  const parts = statement.split(';')
  let n = 0
  while (n < parts.length - 1 && /^\s*(letI|haveI|let)\b/.test(parts[n])) n++
  if (n === 0) return statement
  const rest = parts.slice(n).join(';').trim()
  if (rest === '') return statement
  return `${n} let${n === 1 ? '' : 's'} · ${rest}`
}

function GoalsList({
  goals,
  onSelect,
  engineWorking,
}: {
  goals: Goal[]
  onSelect: (id: number) => void
  engineWorking: boolean
}) {
  if (goals.length === 0)
    return <div className="px-4 py-8 text-center text-xs text-ink-faint">No goals yet.</div>
  // live work first (status), then within each group: root, then the
  // claims you sign, then ALPHABETICAL — slug prefixes are the de
  // facto topic taxonomy, so alpha order clusters the torus_*/int_*
  // families that creation order scattered (owner, 2026-07-13)
  const sorted = [...goals].sort(
    (a, b) =>
      (GOAL_SORT[a.status] ?? 9) - (GOAL_SORT[b.status] ?? 9) ||
      Number(b.origin === 'root') - Number(a.origin === 'root') ||
      Number(b.is_deliverable) - Number(a.is_deliverable) ||
      a.slug.localeCompare(b.slug) ||
      a.id - b.id,
  )
  return (
    <table className="w-full border-collapse text-left">
      <thead>
        <tr className="border-b border-edge text-xs text-ink-faint">
          <th className="py-2 pr-4 pl-4 font-medium">goal</th>
          <th className="py-2 pr-4 font-medium">status</th>
          <th className="py-2 pr-4 font-medium">statement</th>
          <th className="py-2 pr-4 text-right font-medium">attempts</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((g) => (
          <tr
            key={g.id}
            className="cursor-pointer border-b border-edge/60 hover:bg-surface"
            onClick={() => onSelect(g.id)}
          >
            <td className="py-2 pr-4 pl-4 font-mono text-xs whitespace-nowrap text-ink">
              <button
                className="font-mono"
                onClick={(e) => {
                  e.stopPropagation()
                  onSelect(g.id)
                }}
              >
                {g.slug}
              </button>
              {g.is_deliverable && <span className="ml-1.5 text-star" title="claim — you sign off on this">◈</span>}
              {g.disproof_of && (
                <span
                  className="ml-1.5 text-[11px] text-warn"
                  title={`this theorem is the negation of ${g.disproof_of.slug} — the kernel settled the original claim as false`}
                >
                  disproof
                </span>
              )}
            </td>
            <td
              className={`py-2 pr-4 text-xs ${
                g.status === 'attempting' && !engineWorking
                  ? 'text-ink-dim'
                  : (GOAL_STATUS_CLS[g.status] ?? 'text-ink-dim')
              }`}
              title={
                g.status === 'attempting' && !engineWorking
                  ? 'the run stopped mid-attempt — picked up again on the next run'
                  : undefined
              }
            >
              {/* "attempting" is a liveness claim — a stopped run's
                  leftover reads as interrupted, not live work; and
                  'proved' is the settled norm — it earns no ink */}
              {g.status === 'attempting' && !engineWorking
                ? 'interrupted'
                : g.status === 'proved'
                  ? null
                  : goalStatusLabel(g.status)}
            </td>
            <td
              className="max-w-md truncate py-2 pr-4 text-[12px] text-ink-dim"
              title={g.statement}
            >
              {/* the birth annotation reads; the full type is one
                  click away (and on hover) — a binder wall truncated
                  at 60 chars said nothing */}
              {g.doc ? (
                g.doc
              ) : (
                <span className="font-mono text-[11px]">
                  <Lean code={stripBinders(g.statement)} />
                </span>
              )}
            </td>
            <td className="py-2 pr-4 text-right text-xs text-ink-faint">
              {g.attempts > 0 ? g.attempts : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** The run strip — one line while the engine works this problem (its
 * presence IS the truthful "running" signal): phase + wall clock +
 * goal tallies. The machinery (agent lanes, live writes, burn) lives
 * on the Run console — one link, not a second copy. */
function RunStrip({
  workers,
  goals,
  startedAt,
  gateway,
  stopping,
}: {
  workers: ProblemDetail['workers']
  goals: Goal[]
  startedAt: string | null
  gateway: DaemonStatus['gateway']
  stopping: boolean
}) {
  const [, tick] = useState(0)
  useEffect(() => {
    const t = window.setInterval(() => tick((n) => n + 1), 1000)
    return () => window.clearInterval(t)
  }, [])

  let wall: string | null = null
  if (startedAt) {
    const sec = Math.max(0, Math.floor((Date.now() - Date.parse(startedAt)) / 1000))
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = sec % 60
    wall = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  // Phase, derived — a name for what the user would otherwise read
  // logs to learn. Order matters: stopping > warming > roster shape.
  const phase = stopping
    ? 'stopping — finishing in-flight work'
    : gateway === 'warming'
      ? 'warming the Lean toolchain'
      : workers.length === 0 || workers.every((w) => w.kind === 'Strategist')
        ? 'planning'
        : workers.every((w) => w.kind === 'Librarian')
          ? 'harvesting'
          : 'proving'
  const phaseHint: Record<string, string> = {
    planning: 'the Strategist is reading the state and deciding the next moves',
    proving: 'agents are attempting goals right now',
    harvesting: 'finished work is being curated into the Library',
    'warming the Lean toolchain':
      'first start takes a few minutes — proving begins once the toolchain is hot',
  }

  const count = (s: string) => goals.filter((g) => g.status === s).length
  const tallies: [number, string][] = [
    [count('proved'), 'proved'],
    [count('attempting'), 'attempting'],
    [count('open'), 'open'],
    [count('shelved') + count('pending_shelve_confirm'), 'shelved'],
  ]

  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      <span className="flex items-center gap-1.5 text-ink" title={phaseHint[phase]}>
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ok" />
        {phase}
      </span>
      {wall && <span className="tnum font-mono text-[12px] text-ink-dim">{wall}</span>}
      {goals.length > 0 && (
        <span className="tnum text-ink-faint">
          {tallies
            .filter(([n], i) => n > 0 || i === 0)
            .map(([n, label]) => `${n} ${label}`)
            .join(' · ')}
        </span>
      )}
      {workers.length > 0 && (
        <span className="tnum text-ink-faint">
          {workers.length} agent{workers.length === 1 ? '' : 's'}
        </span>
      )}
      <Link
        to="/run"
        className="text-ink-faint underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink"
        title="the run console: agent lanes, live writes, burn"
      >
        run console →
      </Link>
    </div>
  )
}

/** Destruction tier (owner, 2026-07-09): deleting a problem erases
 * its folder, proofs and history — heavier ceremony than the in-place
 * two-step: a floating confirm whose red button (the achromatic law's
 * one owner-sanctioned exception for irreversible loss) unlocks only
 * when the problem's name is typed back. The REAL guards — bridged
 * problems refuse, engine-busy refuses — live in the chokepoint. */
function DeleteProblem({ problem }: { problem: string }) {
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const match = typed === problem
  const doDelete = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiPost(`/api/problems/${encodeURIComponent(problem)}/delete`, {})
      navigate('/')
    } catch (e) {
      setError(String((e as Error).message))
      setBusy(false)
    }
  }
  return (
    <div className="mx-auto max-w-3xl px-4 pt-1 pb-8">
      <button
        className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink-dim"
        onClick={() => {
          setTyped('')
          setError(null)
          setOpen(true)
        }}
      >
        delete this problem…
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-bg/70"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-[26rem] rounded-lg border border-edge bg-surface p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-sm font-medium text-ink">Delete {problem}?</div>
            <p className="mt-2 text-xs leading-relaxed text-ink-dim">
              Erases this problem's folder, proofs and history. It cannot be undone.
            </p>
            <input
              className="mt-3 w-full rounded border border-edge bg-bg px-2 py-1.5 font-mono text-xs text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
              placeholder={`type ${problem} to confirm`}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoFocus
            />
            {error && <div className="text-danger mt-2 text-xs">{error}</div>}
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <button
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  match && !busy
                    ? 'bg-destruct cursor-pointer text-starlight hover:opacity-90'
                    : 'cursor-default border border-edge text-ink-faint'
                }`}
                disabled={!match || busy}
                onClick={() => void doDelete()}
              >
                {busy ? 'Deleting…' : 'Delete forever'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Problem({ name }: { name: string }) {
  const { data, error, loading } = usePoll<ProblemDetail>(
    `/api/problems/${encodeURIComponent(name)}`,
  )
  const { data: daemon } = usePoll<DaemonStatus>('/api/daemon', 3000)
  const [tab, setTab] = useState<Tab>('stars')
  const [manifestDirty, setManifestDirty] = useState(false)
  const [selectedGoal, setSelectedGoal] = useState<number | null>(null)
  // stars lit by hovering a route in the goal panel (owner: the text
  // and the map must point at each other)
  const [routeHover, setRouteHover] = useState<number[] | null>(null)
  const [selectedStrategy, setSelectedStrategy] = useState<number | null>(null)
  const [fileToOpen, setFileToOpen] = useState<string | null>(null)

  if (loading) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  if (!data) return null

  const proved = data.goals.filter((g) => g.status === 'proved').length

  const tabs: { id: Tab; label: string }[] = [
    { id: 'stars', label: 'Constellation' },
    { id: 'manifest', label: 'Manifest' },
    { id: 'goals', label: `Goals (${data.goals.length})` },
    { id: 'timeline', label: 'Timeline' },
    { id: 'files', label: 'Files' },
  ]

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-edge px-6 pt-3">
        <Link
          to="/"
          className="text-[11px] text-ink-faint transition-colors hover:text-ink"
        >
          ‹ problems
        </Link>
        <div className="mt-1 flex items-baseline justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-base font-semibold">{data.name}</h1>
            {data.status === 'awaiting_human' || data.status === 'signoff_pending' ? (
              <Link to="/inbox" title="paused on you — open the inbox">
                <StatusBadge status={data.status} />
              </Link>
            ) : (
              <StatusBadge status={data.status} />
            )}
          </div>
          <div className="flex items-center gap-4">
            <RunControl problem={data.name} />
            {data.goals.length > 0 && (
              <div
                className="flex h-[3px] w-28 overflow-hidden rounded-full bg-surface-3"
                title={`${proved} proved of ${data.goals.length} goals (bright = proved, mid = in progress)`}
              >
                <div
                  className="h-full bg-starlight/80 transition-[width] duration-700"
                  style={{ width: `${(proved / data.goals.length) * 100}%` }}
                />
                <div
                  className="h-full bg-accent/50 transition-[width] duration-700"
                  style={{
                    width: `${(data.goals.filter((g) => g.status === 'open' || g.status === 'attempting').length / data.goals.length) * 100}%`,
                  }}
                />
              </div>
            )}
            <div
              className="tnum text-xs text-ink-faint"
              title={[
                data.ingested_at && `ingested ${relTime(data.ingested_at)}`,
                data.library_bridged_at && `bridged ${relTime(data.library_bridged_at)}`,
              ]
                .filter(Boolean)
                .join(' · ')}
            >
              {proved}/{data.goals.length} proved
            </div>
          </div>
        </div>
        {data.engine_working && (
          <RunStrip
            workers={data.workers}
            goals={data.goals}
            startedAt={daemon?.started_at ?? null}
            gateway={daemon?.gateway ?? null}
            stopping={daemon?.stopping ?? false}
          />
        )}
        {(() => {
          // health line for live problems: when did the engine last make
          // progress, and where is it burning attempts (client-side from
          // data already on hand — the "is it stuck?" answer)
          const live =
            data.status === 'proving' ||
            data.status === 'awaiting_human' ||
            data.status === 'stalled' ||
            data.goals.some((g) => g.status === 'open' || g.status === 'attempting')
          if (!live) return null
          const OK = new Set([
            'success',
            'accepted',
            'live_subgoal',
            'closed_subgoal',
            'proved',
            'paper_fetched',
          ])
          const lastOk = data.decisions.find((d) => d.outcome !== null && OK.has(d.outcome))
          // a blocker must still be IN the way: the old not-proved
          // filter crowned dead goals — the header named a "top
          // blocker" the panel then called dead (cold-eye)
          const blocker = [...data.goals]
            .filter(
              (g) =>
                (g.status === 'open' ||
                  g.status === 'attempting' ||
                  g.status === 'pending_strategist_review') &&
                g.dead_attempts > 0,
            )
            .sort((a, b) => b.dead_attempts - a.dead_attempts)[0]
          const paused = data.status === 'awaiting_human' || data.status === 'signoff_pending'
          if (!lastOk && !blocker && !paused) return null
          const staleDays = lastOk
            ? Math.floor((Date.now() - Date.parse(lastOk.created_at)) / 86400_000)
            : null
          return (
            <div className="mt-1.5 text-xs">
              {lastOk && (
                <span className={staleDays !== null && staleDays >= 3 ? 'text-warn' : 'text-ink-faint'}>
                  last progress {relTime(lastOk.created_at)}
                </span>
              )}
              {blocker && (
                <span className="text-ink-faint">
                  {lastOk && ' · '}top blocker{' '}
                  {/* the words and the map must know each other: the
                      named blocker is a link that lights its star */}
                  <button
                    className="cursor-pointer font-mono text-ink-dim underline decoration-ink-faint/50 underline-offset-2 transition-colors hover:text-ink"
                    title="show this star on the constellation"
                    onClick={() => {
                      setTab('stars')
                      setSelectedStrategy(null)
                      setSelectedGoal(blocker.id)
                    }}
                  >
                    {blocker.slug}
                  </button>{' '}
                  ({blocker.dead_attempts} failed attempt
                  {blocker.dead_attempts === 1 ? '' : 's'})
                </span>
              )}
            </div>
          )
        })()}
        {/* NO standing-directive line: it is the strategist's memo to
            its own agents — engine vocabulary a mathematician can
            neither parse nor act on (owner, 2026-07-12). Its history
            lives where history lives: the Timeline's EmitDirective
            rows. */}
        <nav className="mt-3 flex gap-5">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={`relative pb-2 text-xs transition-colors duration-150 ${
                tab === t.id ? 'text-ink' : 'text-ink-dim hover:text-ink'
              }`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {t.id === 'manifest' && manifestDirty && (
                <span className="ml-1 text-star" title="unsaved changes">
                  ·
                </span>
              )}
              {tab === t.id && (
                <span className="absolute inset-x-0 bottom-0 h-[2px] rounded-full bg-star" />
              )}
            </button>
          ))}
        </nav>
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto">
          {tab === 'stars' && data.goals.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-ink-faint">
              {daemon?.running && daemon.scope === data.name ? (
                <>
                  <span className="flex items-center gap-2 text-ink-dim">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
                    the engine is working
                  </span>
                  <div className="text-xs text-ink-faint">
                    the first stars appear when the Strategist plants its first goals —
                    usually within a couple of minutes
                  </div>
                </>
              ) : (
                <>
                  <div>No goals yet — the Strategist bootstraps from the Manifest once the engine runs.</div>
                  <div className="text-xs text-ink-faint">
                    press <span className="font-semibold text-ink-dim">Run</span> in the header —
                    the engine works this problem only
                  </div>
                </>
              )}
            </div>
          ) : tab === 'stars' && (
            <div className="h-full">
              <Constellation
                goals={data.goals}
                strategies={data.strategies}
                strategyEdges={data.strategy_edges}
                anchorEdges={data.anchor_edges}
                citationEdges={data.citation_edges}
                highlightIds={routeHover}
                selectedId={selectedGoal}
                onSelect={(id) => {
                  setSelectedGoal(id)
                  if (id !== null) setSelectedStrategy(null)
                }}
                onSelectStrategy={(id) => {
                  setSelectedStrategy(id)
                  setSelectedGoal(null)
                }}
                shelveThreshold={data.shelve_threshold}
                engineWorking={data.engine_working}
              />
            </div>
          )}
          {/* the manifest editor stays mounted (hidden, not unmounted) so
              an unsaved draft survives a tab switch */}
          <div className={tab === 'manifest' ? undefined : 'hidden'}>
            <ManifestEditor
              problem={data.name}
              onDirtyChange={setManifestDirty}
              bridged={data.status === 'bridged'}
            />
            <DeleteProblem problem={data.name} />
          </div>
          {tab === 'goals' && (
            <GoalsList
              goals={data.goals}
              onSelect={setSelectedGoal}
              engineWorking={data.engine_working}
            />
          )}
          {tab === 'timeline' && (
            <div className="mx-auto max-w-4xl px-4 py-3">
              <DecisionTimeline decisions={data.decisions} />
            </div>
          )}
          {tab === 'files' && (
            <div className="flex h-full">
              <FileViewer
                problem={data.name}
                proofFiles={data.proof_files}
                initialFile={fileToOpen}
              />
            </div>
          )}
        </div>
        {selectedGoal !== null && tab !== 'files' && tab !== 'timeline' && tab !== 'manifest' && (
          <GoalPanel
            problem={data.name}
            goalId={selectedGoal}
            onClose={() => {
              setSelectedGoal(null)
              setRouteHover(null)
            }}
            onSelectStrategy={(id) => {
              setSelectedStrategy(id)
              setSelectedGoal(null)
            }}
            onSelectGoal={setSelectedGoal}
            onHoverGoals={setRouteHover}
            onOpenFile={(rel) => {
              setFileToOpen(rel)
              setTab('files')
            }}
          />
        )}
        {selectedGoal === null &&
          selectedStrategy !== null &&
          tab !== 'files' &&
          tab !== 'timeline' &&
          tab !== 'manifest' && (
            <StrategyPanel
              problem={data.name}
              strategyId={selectedStrategy}
              onClose={() => setSelectedStrategy(null)}
              onSelectGoal={(id) => {
                setSelectedGoal(id)
                setSelectedStrategy(null)
              }}
            />
          )}
      </div>
    </div>
  )
}
