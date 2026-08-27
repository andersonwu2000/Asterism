import { useEffect, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { Lean } from '../lib/lean'
import { splitSignature } from '../lib/leanSig'
import { onGoalHover, onGoalOpen, takePendingGoalOpen } from '../lib/goalFocus'
import { goalStatusLabel } from '../lib/vocab'
import { scopeCovers } from '../lib/programmeFocus'
import { Button, ErrorState, StatusBadge, TabNav } from '../components/ui'
import Constellation from '../components/Constellation'
import GoalPanel from '../components/GoalPanel'
import StrategyPanel from '../components/StrategyPanel'
import Timeline from '../components/Timeline'
import ProgrammeView from '../components/ProgrammeView'
import FileViewer from '../components/FileViewer'
import IntentEditor from '../components/IntentEditor'
import RunControl from '../components/RunControl'
import type { DaemonStatus, Goal, ProblemDetail, Programme } from '../lib/types'

type Tab = 'stars' | 'intent' | 'programme' | 'goals' | 'timeline' | 'files'

/** The Programme (research mode): the machine's standing argument —
 * what it believes, the route, the whole story — adversarially
 * reviewed before every revision. The Intent tab is what the HUMAN
 * asked; this is what the ENGINE currently argues. Read-only by
 * construction (the only writer is a passed proposal commit). */
function ProgrammePanel({ problem }: { problem: string }) {
  // a delegated claim is argued by its own group, with its own
  // revision chain numbered from 1 (v35) — null = the problem's own
  const [group, setGroup] = useState<number | null>(null)
  // 30s poll: revisions land once per strategist wake at most
  const { data, error, stale } = usePoll<Programme>(
    `/api/problems/${encodeURIComponent(problem)}/programme` +
      (group !== null ? `?group=${group}` : ''),
    30000,
    { keepPrevious: true },
  )
  if (error) return <ErrorState error={error} />
  if (!data) return null
  return (
    <ProgrammeView data={data} group={group} onPickGroup={setGroup} stale={stale} />
  )
}

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
  // facet + name filter (design round: "just the 3 open goals" was
  // impossible on a 171-row table). Facet pills only for statuses
  // that exist here — a chip for an absent state is homework.
  const [facet, setFacet] = useState<string | null>(null)
  const [q, setQ] = useState('')
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
  const facets = [...new Set(sorted.map((g) => g.status))]
  const shown = sorted.filter(
    (g) =>
      (facet === null || g.status === facet) &&
      (q === '' || g.slug.toLowerCase().includes(q.toLowerCase())),
  )
  return (
    <>
    <div className="flex flex-wrap items-center gap-1.5 px-4 pt-1 pb-2">
      {facets.map((s) => (
        <button
          key={s}
          className={`rounded-full border px-2 py-0.5 text-[11px] ${
            facet === s
              ? 'border-star/60 bg-star/10 text-star'
              : 'border-edge text-ink-faint hover:text-ink'
          }`}
          onClick={() => setFacet(facet === s ? null : s)}
        >
          {goalStatusLabel(s)} {goals.filter((g) => g.status === s).length}
        </button>
      ))}
      <input
        className="ml-2 w-48 rounded-lg border border-edge bg-surface px-2 py-0.5 text-[11px] text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
        placeholder="filter by name…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {(facet !== null || q !== '') && (
        <span className="text-[11px] text-ink-faint">{shown.length} shown</span>
      )}
    </div>
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
        {shown.map((g) => (
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
              {/* ◈ is the sign-off mark; a sub-group's delivery is not
                  one, so it gets the quiet word instead of the glyph */}
              {g.human_facing_claim ? (
                <span className="ml-1.5 text-star" title="claim — you sign off on this">
                  ◈
                </span>
              ) : (
                g.is_deliverable && (
                  <span
                    className="ml-1.5 text-[10px] text-ink-faint"
                    title="delivered by a discussion group to the group above it — not something you sign off on"
                  >
                    delivered
                  </span>
                )
              )}
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
                  leftover reads as interrupted, not live work. The
                  settled norm gets the FAINTEST word, not blankness:
                  two cold-eye reviewers read the empty cell as
                  missing data — ambiguity is noise too */}
              {g.status === 'attempting' && !engineWorking ? (
                'interrupted'
              ) : g.status === 'proved' ? (
                <span className="text-ink-faint/60">proved</span>
              ) : (
                goalStatusLabel(g.status)
              )}
            </td>
            <td
              className="max-w-md truncate py-2 pr-4 text-[12px] text-ink-dim"
              title={(g.signature ?? g.statement) + (g.doc ? `\n\n${g.doc}` : '')}
            >
              {/* a column named "statement" must show the statement
                  (first-time QA: the old doc-first rule filled it with
                  duplicated plan prose and mid-sentence fragments).
                  Conclusion-first keeps it readable at any width — the
                  binder wall and the birth annotation live in the
                  tooltip and one click away */}
              <span className="font-mono text-[11px]">
                <Lean
                  code={(() => {
                    const src = g.signature ?? g.statement
                    const sig = splitSignature(src)
                    return sig !== null ? '⊢ ' + sig.conclusion : stripBinders(g.statement)
                  })()}
                />
              </span>
            </td>
            <td className="py-2 pr-4 text-right text-xs text-ink-faint">
              {g.attempts > 0 ? g.attempts : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </>
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
      {wall && (
        <span
          className="tnum font-mono text-[12px] text-ink-dim"
          title="how long this run has been going (wall clock)"
        >
          {wall}
        </span>
      )}
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
        to="/engine"
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
  // Escape closes any floating surface (DESIGN.md). Safe here BECAUSE
  // it is the destructive one: the key cancels, it can never confirm.
  useEffect(() => {
    if (!open || busy) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, busy])
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
            className="w-[26rem] rounded-xl border border-edge bg-surface p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-sm font-medium text-ink">Delete {problem}?</div>
            <p className="mt-2 text-xs leading-relaxed text-ink-dim">
              Erases this problem's folder, proofs and history. It cannot be undone.
            </p>
            <input
              className="mt-3 w-full rounded-md border border-edge bg-bg px-2 py-1.5 font-mono text-xs text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
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
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
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

export default function Problem({
  name,
  initialGoal = null,
}: {
  name: string
  /** deep link: a goal id to select on the stars tab (run timeline
   * name clicks land here) */
  initialGoal?: number | null
}) {
  const { data, error, loading } = usePoll<ProblemDetail>(
    `/api/problems/${encodeURIComponent(name)}`,
  )
  const { data: daemon } = usePoll<DaemonStatus>('/api/daemon', 3000)
  const [tab, setTab] = useState<Tab>('stars')
  const [intentDirty, setIntentDirty] = useState(false)
  const [selectedGoal, setSelectedGoal] = useState<number | null>(initialGoal)
  // stars lit by hovering a route in the goal panel (owner: the text
  // and the map must point at each other)
  const [routeHover, setRouteHover] = useState<number[] | null>(null)
  const [selectedStrategy, setSelectedStrategy] = useState<number | null>(null)
  const [fileToOpen, setFileToOpen] = useState<string | null>(null)
  // stars lit from elsewhere — a chat answer's [goal:…] citation, a
  // run console lane: hovering lights the star (same text↔map law as
  // route hover), clicking selects it. takePendingGoalOpen survives
  // the navigation when the caller pointed at a sky not on screen.
  const [chatHoverSlug, setChatHoverSlug] = useState<string | null>(null)
  useEffect(
    () =>
      onGoalHover((ref) =>
        setChatHoverSlug(ref !== null && ref.problem === name ? ref.slug : null),
      ),
    [name],
  )
  useEffect(() => {
    if (!data) return
    const consume = (ref: { problem: string; slug: string } | null): boolean => {
      if (ref === null || ref.problem !== name) return false
      const g = data.goals.find((x) => x.slug === ref.slug)
      if (g === undefined) return false
      setSelectedGoal(g.id)
      setSelectedStrategy(null)
      setTab('stars')
      return true
    }
    consume(takePendingGoalOpen(name))
    return onGoalOpen(consume)
  }, [data, name])

  if (loading) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  if (!data) return null

  const proved = data.goals.filter((g) => g.status === 'proved').length
  const chatHoverIds =
    chatHoverSlug !== null
      ? (data.goals.filter((g) => g.slug === chatHoverSlug).map((g) => g.id) ?? null)
      : null

  const tabs: { id: Tab; label: string }[] = [
    { id: 'stars', label: 'Constellation' },
    { id: 'intent', label: 'Intent' },
    // the tab exists only once a Programme exists — pre-research-mode
    // problems keep their old anatomy
    ...(data.programme_rev !== null
      ? [{ id: 'programme' as Tab, label: 'Programme' }]
      : []),
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
            {/* the meter that used to sit here drew the fraction beside
                it a second time — same two numbers, less precisely, and
                the reader had to be told which grey meant what. Its one
                distinct fact (the live/settled split) is in the tooltip
                (owner, 2026-08-26: "光條不好懂"). */}
            <div
              className="tnum text-xs text-ink-faint"
              title={[
                `${proved} proved · ${
                  data.goals.filter((g) => g.status === 'open' || g.status === 'attempting').length
                } still open of ${data.goals.length} goals`,
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
        {/* "top blocker" used to sit here, above the map. It moved
            into the Timeline (owner, 2026-08-09): the header says what
            this problem IS and how it stands; where the machine is
            burning attempts is something happening TO it, and it reads
            next to the evidence rather than a tab away from it. */}
        {/* NO standing-directive line: it is the strategist's memo to
            its own agents — engine vocabulary a mathematician can
            neither parse nor act on (owner, 2026-07-12). Its history
            lives where history lives: the Timeline's EmitDirective
            rows. */}
        <TabNav
          className="mt-3"
          tabs={tabs.map((t) => ({
            id: t.id,
            label: (
              <>
                {t.label}
                {t.id === 'intent' && intentDirty && (
                  <span className="ml-1 text-star" title="unsaved changes">
                    ·
                  </span>
                )}
              </>
            ),
          }))}
          active={tab}
          onSelect={setTab}
        />
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto">
          {tab === 'stars' && data.goals.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-ink-faint">
              {daemon?.running && scopeCovers(daemon.scope, data.name) ? (
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
                  <div>No goals yet — the Strategist bootstraps from the goal once the engine runs.</div>
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
                highlightIds={routeHover ?? (chatHoverIds?.length ? chatHoverIds : null)}
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
          {/* the intent editor stays mounted (hidden, not unmounted) so
              an unsaved draft survives a tab switch */}
          <div className={tab === 'intent' ? undefined : 'hidden'}>
            <IntentEditor
              problem={data.name}
              onDirtyChange={setIntentDirty}
              bridged={data.status === 'bridged'}
            />
            <DeleteProblem problem={data.name} />
          </div>
          {tab === 'programme' && <ProgrammePanel problem={data.name} />}
          {tab === 'goals' && (
            <GoalsList
              goals={data.goals}
              onSelect={setSelectedGoal}
              engineWorking={data.engine_working}
            />
          )}
          {tab === 'timeline' && (
            <div className="mx-auto max-w-4xl px-4 py-3">
              <Timeline
                path={`/api/problems/${encodeURIComponent(data.name)}/events`}
                onSelectGoal={(id) => {
                  setSelectedGoal(id)
                  setSelectedStrategy(null)
                  setTab('stars')
                }}
                onOpenProgramme={
                  data.programme_rev !== null ? () => setTab('programme') : undefined
                }
              />
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
        {selectedGoal !== null &&
          tab !== 'files' &&
          tab !== 'timeline' &&
          tab !== 'intent' &&
          tab !== 'programme' && (
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
          tab !== 'intent' &&
          tab !== 'programme' && (
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
