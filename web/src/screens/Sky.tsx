import { useEffect, useState } from 'react'
import { usePoll } from '../lib/api'
import { currentSegments, navigate, replace } from '../lib/router'
import { goalCode, goalLabel } from '../lib/format'
import { Lean } from '../lib/lean'
import { splitSignature } from '../lib/leanSig'
import { onGoalHover, onGoalOpen, takePendingGoalOpen } from '../lib/goalFocus'
import { usePublishFocus } from '../lib/focus'
import { goalStatusLabel } from '../lib/vocab'
import { scopeCovers } from '../lib/programmeFocus'
import { parseProjectRoute, projectPath } from '../lib/projectRoute'
import { docAddress } from '../lib/docShell'
import { ErrorState } from '../components/ui'
import Constellation from '../components/Constellation'
import GoalPanel from '../components/GoalPanel'
import StrategyPanel from '../components/StrategyPanel'
import type { DaemonStatus, Goal, ProblemDetail } from '../lib/types'

/*
 * Sky — one task's constellation (human_interface_design.md §1.4-2).
 *
 * The map and the table are ONE view of one data layer, switched: the
 * sky is how the work is read, the table is how it is swept (the
 * frontend charter's own appendix ruling, 2026-07-06). Neither is a
 * different page, so neither is a different address.
 *
 * Everything below the toggle is the problem page's sky, unchanged:
 * this package re-homed it, it did not redesign it. What left is the
 * chrome the shell now owns — the title, the tabs, the run control.
 */

/* proved is the settled majority — it reads quiet; color is spent on
 * the live minority (open/attempting) and exceptions. */
const GOAL_STATUS_CLS: Record<string, string> = {
  proved: 'text-ink-faint',
  attempting: 'text-accent',
  open: 'text-accent',
  shelved: 'text-ink-faint',
  pending_strategist_review: 'text-warn',
  disproved: 'text-danger',
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
      (q === '' ||
        g.slug.toLowerCase().includes(q.toLowerCase()) ||
        goalCode(g.id).toLowerCase().includes(q.toLowerCase())),
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
        placeholder="filter by name or g…"
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
                <span className="mr-2 text-ink-faint">{goalCode(g.id)}</span>
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
                  title={`this theorem is the negation of ${goalLabel(g.disproof_of.id, g.disproof_of.slug)} — the kernel settled the original claim as false`}
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

export default function Sky({
  project,
  problem,
  initialGoal = null,
}: {
  project: string
  problem: string
  /** deep link: a timeline row's name click lands on its star */
  initialGoal?: number | null
}) {
  // the biggest read the console makes (~800KB on a 500-goal task).
  // It took the 2s default and moved the whole payload every time; the
  // request is conditional now (`pollGet` sends the ETag, the server
  // answers 304 with no body) and 5s is a constellation's cadence, not
  // a stopwatch's.
  const { data, error, loading } = usePoll<ProblemDetail>(
    `/api/problems/${encodeURIComponent(problem)}`,
    5000,
  )
  const { data: daemon } = usePoll<DaemonStatus>('/api/daemon', 3000)
  const [view, setView] = useState<'map' | 'list'>('map')
  const [selectedGoal, setSelectedGoal] = useState<number | null>(initialGoal)
  const [selectedStrategy, setSelectedStrategy] = useState<number | null>(null)
  // stars lit by hovering a route in the goal panel (owner: the text
  // and the map must point at each other)
  const [routeHover, setRouteHover] = useState<number[] | null>(null)
  // the Assistant is told which star is open (§1.4-2): the panel and
  // this screen are in different subtrees, so it goes through the bus
  usePublishFocus({ problem, goal_id: selectedGoal })
  // …and so is the ADDRESS. `…/sky/<task>/g/<id>` was already read on
  // arrival but never written back, so a reload or a mailed link showed
  // the star the reader had open three clicks ago, and a link followed
  // from the Timeline kept saying `/g/123` whatever was open after it.
  // `replace`, not `navigate`: a star click is not a move the back
  // button should have to undo one star at a time.
  useEffect(() => {
    const here = parseProjectRoute(currentSegments())
    // only ever rewrite THIS screen's own address — never one the shell
    // has already walked away from
    if (here === null || here.section !== 'sky') return
    if (here.project !== project || here.problem !== problem) return
    if (here.goal === selectedGoal) return
    replace(projectPath(project, 'sky', problem, selectedGoal))
  }, [project, problem, selectedGoal])
  // stars lit from elsewhere — a chat answer's citation, a lane in the
  // engine room: hovering lights the star, clicking selects it
  const [chatHoverSlug, setChatHoverSlug] = useState<string | null>(null)
  useEffect(
    () =>
      onGoalHover((ref) =>
        setChatHoverSlug(ref !== null && ref.problem === problem ? ref.slug : null),
      ),
    [problem],
  )
  useEffect(() => {
    if (!data) return
    const consume = (ref: { problem: string; slug: string } | null): boolean => {
      if (ref === null || ref.problem !== problem) return false
      const g = data.goals.find((x) => x.slug === ref.slug)
      if (g === undefined) return false
      setSelectedGoal(g.id)
      setSelectedStrategy(null)
      setView('map')
      return true
    }
    consume(takePendingGoalOpen(problem))
    return onGoalOpen(consume)
  }, [data, problem])

  if (loading) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  if (!data) return null

  const chatHoverIds =
    chatHoverSlug !== null
      ? (data.goals.filter((g) => g.slug === chatHoverSlug).map((g) => g.id) ?? null)
      : null

  if (data.goals.length === 0)
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-ink-faint">
        {daemon?.running && scopeCovers(daemon.scope, problem) ? (
          <>
            <span className="flex items-center gap-2 text-ink-dim">
              <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
              the engine is working
            </span>
            <div className="text-xs text-ink-faint">
              the first stars appear when the Strategist plants its first goals — usually
              within a couple of minutes
            </div>
          </>
        ) : (
          <>
            <div>
              No goals yet — the Strategist bootstraps from the goal once the engine runs.
            </div>
            <button
              className="cursor-pointer text-xs text-ink-faint underline decoration-edge-strong underline-offset-2 hover:text-ink"
              onClick={() => navigate(projectPath(project, 'tasks', problem))}
            >
              press Run on its task page
            </button>
          </>
        )}
      </div>
    )

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* the one control this section owns: the same goals, read as a
          map or swept as a table */}
      <div className="flex shrink-0 items-center gap-2 px-4 pt-3">
        {(['map', 'list'] as const).map((v) => (
          <button
            key={v}
            className={`cursor-pointer rounded-md px-2 py-0.5 text-[11px] transition-colors ${
              view === v ? 'bg-surface-2 text-ink' : 'text-ink-faint hover:text-ink-dim'
            }`}
            onClick={() => setView(v)}
            aria-pressed={view === v}
          >
            {v}
          </button>
        ))}
        <span className="tnum ml-2 text-[11px] text-ink-faint">
          {data.goals.filter((g) => g.status === 'proved').length}/{data.goals.length} proved
        </span>
      </div>
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto">
          {view === 'map' ? (
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
          ) : (
            <GoalsList
              goals={data.goals}
              onSelect={(id) => {
                setSelectedGoal(id)
                setSelectedStrategy(null)
              }}
              engineWorking={data.engine_working}
            />
          )}
        </div>
        {selectedGoal !== null && (
          <GoalPanel
            problem={problem}
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
            /* the file belongs to THIS sky's task, and the address now
               says so — the old link named no task and landed on
               whichever one the Documents tab defaulted to */
            onOpenFile={(rel) =>
              navigate(docAddress(project, { kind: 'task', task: problem, path: rel }))
            }
          />
        )}
        {selectedGoal === null && selectedStrategy !== null && (
          <StrategyPanel
            problem={problem}
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
