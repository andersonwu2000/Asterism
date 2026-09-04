import { useEffect, useMemo, useState } from 'react'
import { apiGet, usePoll } from '../lib/api'
import { goalCode, goalLabel, groupCode, groupLabel } from '../lib/format'
import { EVENT_CLS, eventLabel, eventTitle, failureLabel } from '../lib/vocab'
import type { TimelineEvent, TimelineGroup } from '../lib/types'
import { frameClass } from '../lib/textFrame'
import JudgeVerdict from './JudgeVerdict'

/*
 * The Timeline is a LOG, not a narrative: every row reads
 *
 *     17:15 | proved | supirred_to_biunion_join_irred
 *
 * — when, what happened, and to whom. Three consequences, all of them
 * the point (owner design, 2026-08-07):
 *
 *   · Prose never reaches a row. A strategist brief is 1.3KB of
 *     roadmap markdown; as a row headline it drowned the one token
 *     that identifies the event, and the identifying token is the
 *     brick's name.
 *   · Because every row NAMES an object, the log can be followed by
 *     object: the name click opens the star on the map (the side
 *     panel reads the goal's history there), and one click further —
 *     the row's expansion — filters the log to that brick's whole
 *     life (asked → attempt 2 → proved).
 *   · Outcomes are events. 52 of union_closed's 54 goals reached
 *     proved and not one of those landings used to appear here.
 */

/* rows sit under day rules — a clock time reads better than thirty
 * copies of "37d ago". Locale is PINNED: `undefined` followed the
 * browser and dropped 下午07:14 into an English-voiced page (audit,
 * 2026-07-11); a 24h clock is also just denser. */
const TIME_FMT = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})
const DAY_FMT = new Intl.DateTimeFormat('en-US', {
  month: 'short', day: 'numeric', year: 'numeric',
})

/* Infra deaths and rejected proposals used to be held back behind a
 * "+N quiet" link. The link went with the chips (owner, 2026-08-26) —
 * and holding rows back with no way to ask for them is the one thing a
 * log may not do, so they simply render. They already recede on their
 * own: both verbs are residue ink in EVENT_CLS, which is how a log is
 * supposed to quiet something. */

/** What "follow this object" follows. Usually the label IS the object,
 * but a revision row is labelled with that revision's own title, so
 * following by label would match a single row — the object is the
 * Programme; the title is what it said that day.
 *
 * A discriminated value, not a string with a reserved prefix: the
 * first cut used a sentinel-prefixed key, the "prefix" that reached
 * disk was a NUL byte, and git read the whole .tsx as binary
 * (2026-08-07). A namespace belongs in the type, not in the bytes.
 */
type Follow =
  | { kind: 'goal'; id: number | null; label: string }
  | { kind: 'programme' }
  | { kind: 'group'; id: number | null; label: string }

function followFor(e: TimelineEvent): Follow {
  if (e.object_kind === 'programme') return { kind: 'programme' }
  if (e.object_kind === 'group')
    return { kind: 'group', id: e.object_group_id, label: e.label }
  return { kind: 'goal', id: e.goal_id, label: e.label }
}

function followMatches(f: Follow, e: TimelineEvent): boolean {
  if (f.kind === 'programme') return e.object_kind === 'programme'
  if (f.kind === 'group')
    return e.object_kind === 'group' && e.object_group_id === f.id
  return (
    e.object_kind !== 'programme' &&
    e.object_kind !== 'group' &&
    e.label === f.label
  )
}

function followName(f: Follow): string {
  if (f.kind === 'programme') return 'the Programme'
  if (f.kind === 'group' && f.id !== null) return groupLabel(f.id, f.label)
  if (f.kind === 'goal' && f.id !== null) return goalLabel(f.id, f.label)
  return f.label
}

function Row({
  e,
  following,
  prefix,
  argument,
  showProblem,
  problem,
  onFollow,
  onOpenGoal,
  onOpenProgramme,
}: {
  e: TimelineEvent
  /** the log is filtered to this object — the header names it, so the
   * row must not say it a third and fourth time */
  following: boolean
  /** show the object's kind anchor ("Programme:") — an aid for finding
   * it in the mixed stream, redundant once the stream IS it */
  prefix: boolean
  /** which argument this event serves — null on a problem running a
   * single group, where naming it on every row would be noise */
  argument: string | null
  /** the run view merges several problems; say which */
  showProblem: boolean
  /** the problem this log is scoped to; the run-scoped read stamps
   * each row instead (it merges several) */
  problem?: string
  onFollow: (f: Follow) => void
  onOpenGoal?: (id: number, problem: string | null) => void
  /** the row's own task — a shelf-wide feed merges several, so the
   * Programme this row is about is not necessarily the one the reader
   * is scoped to (the same shape `onOpenGoal` already carries) */
  onOpenProgramme?: (problem: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  // a revision row opens onto the judge's ruling on it — criterion by
  // criterion, and for a killed proposal the reason it was killed
  // (readable only since 2026-08-29; see JudgeVerdict.tsx)
  const revProblem = e.problem ?? problem
  const verdictOf =
    e.object_kind === 'programme' && typeof e.rev_id === 'number' && revProblem
      ? { problem: revProblem, revId: e.rev_id }
      : null
  const expandable = Boolean(e.body || e.note || argument || verdictOf)
  const note = e.kind === 'failed' || e.kind === 'hiccup'
    ? failureLabel(e.note ?? '')
    : e.note
  return (
    <div>
      <div
        className={`grid grid-cols-[3.1rem_6.2rem_1fr] items-baseline gap-2 rounded-md px-2 py-[3px] ${
          expandable ? 'cursor-pointer hover:bg-surface' : ''
        }`}
        onClick={expandable ? () => setOpen((v) => !v) : undefined}
        data-verdict-row={verdictOf ? verdictOf.revId : undefined}
      >
        <span
          className="tnum text-[11px] text-ink-faint"
          title={
            e.approx
              ? `${new Date(e.at).toLocaleString()} — reconstructed. The engine records a` +
                " goal's status, not its history, so this landing is dated from the work" +
                ' that produced it; where even that is missing the row falls back to the' +
                " row's last write."
              : new Date(e.at).toLocaleString()
          }
        >
          {e.approx && <span className="text-ink-faint/60">~</span>}
          {TIME_FMT.format(new Date(e.at))}
        </span>
        <span
          className={`text-xs whitespace-nowrap ${EVENT_CLS[e.kind] ?? 'text-ink-dim'}`}
          title={eventTitle(e.kind)}
        >
          {eventLabel(e.kind)}
          {e.n !== null && <span className="tnum"> {e.n}</span>}
        </span>
        <span className="flex min-w-0 items-baseline gap-2">
          {!following && (
          <span
            role="button"
            tabIndex={0}
            /* the OBJECT never yields: a long note used to squeeze the
               name down to "msid…", which is the one token the row
               exists to carry (cold-eye, 2026-08-07) */
            className={`max-w-[70%] shrink-0 truncate ${
              e.object_kind === 'goal' || e.object_kind === 'unbuilt'
                ? 'font-mono text-[12px]'
                : 'text-xs'
            } ${
              e.object_kind === 'unbuilt' ? 'text-ink-faint' : 'text-ink-dim'
            } cursor-pointer underline decoration-transparent underline-offset-2 hover:text-ink hover:decoration-edge-strong`}
            title={
              e.object_kind === 'unbuilt'
                ? `${e.label} — asked for; no such brick exists yet. Click to follow it.`
                : e.object_kind === 'goal' && e.goal_id !== null && onOpenGoal
                  ? `${e.label} — click to open it on the map`
                  : `${e.label} — click to follow it through the log`
            }
            onClick={(ev) => {
              ev.stopPropagation()
              /* the map IS the goal's history now (the side panel reads
                 it out) — the name goes there; following the log moved
                 one click down, into the expansion (owner, 2026-08-24) */
              if (e.goal_id !== null && onOpenGoal) onOpenGoal(e.goal_id, e.problem ?? null)
              else onFollow(followFor(e))
            }}
            onKeyDown={(ev) => {
              if (ev.key === 'Enter') {
                ev.stopPropagation()
                if (e.goal_id !== null && onOpenGoal) onOpenGoal(e.goal_id, e.problem ?? null)
                else onFollow(followFor(e))
              }
            }}
          >
            {/* the object column is otherwise a wall of mono goal
                slugs; a lexical anchor makes the argument's own
                landmarks findable in one pass (owner, 2026-08-07).
                Dropped once the log is already filtered to it — the
                header says so, and saying it twice is the thing this
                page keeps deleting. */}
            {e.object_kind === 'programme' && prefix && (
              <span className="text-ink-faint">Programme: </span>
            )}
            {e.object_kind === 'goal' && e.goal_id !== null && (
              <span className="mr-1.5 text-ink-faint">{goalCode(e.goal_id)}</span>
            )}
            {e.object_kind === 'group' && e.object_group_id !== null && (
              <span className="mr-1.5 font-mono text-ink-faint">
                {groupCode(e.object_group_id)}
              </span>
            )}
            {e.label}
          </span>
          )}
          {showProblem && e.problem && (
            <span className="shrink-0 font-mono text-[10px] text-ink-faint">
              {e.problem.includes('.') ? e.problem.split('.').pop() : e.problem}
            </span>
          )}
          {note && !open && (
            <span className="truncate text-[11px] text-ink-faint">{note}</span>
          )}
        </span>
      </div>
      {open && (
        <div className="mx-2 mt-1 mb-2 ml-[9.4rem] rounded-lg border border-edge bg-surface px-3 py-2">
          {argument && argument !== e.label && (
            /* which argument this brick serves. A column would cost
               width on every problem to answer a question only
               multi-group problems raise (owner, 2026-08-07). Dropped
               when it IS the row's own name: a delegated group's
               revision often titles itself after the charter it was
               handed, and the line then said the row twice. */
            <div
              className="mb-1.5 text-[11px] text-ink-faint"
              title="the discussion group whose programme commissioned this — a problem under load argues several at once"
            >
              for <span className="text-ink-dim">{argument}</span>
            </div>
          )}
          {note && <div className="mb-1.5 text-xs text-ink-dim">{note}</div>}
          {e.body && (
            <pre className={frameClass({ frame: false, lead: 'quote', tone: 'faint' })}>
              {e.body}
            </pre>
          )}
          {verdictOf && (
            <JudgeVerdict problem={verdictOf.problem} revId={verdictOf.revId} />
          )}
          <div className="mt-1.5 flex items-center gap-3 text-[11px]">
            {e.goal_id !== null && onOpenGoal && (
              <button
                className="text-ink-faint underline decoration-edge-strong underline-offset-2 hover:text-ink"
                title="one click and you read this brick's whole life right here"
                onClick={() => onFollow(followFor(e))}
              >
                follow through the log
              </button>
            )}
            {e.object_kind === 'programme' && onOpenProgramme && (
              <button
                className="text-ink-faint underline decoration-edge-strong underline-offset-2 hover:text-ink"
                onClick={() => onOpenProgramme(revProblem ?? null)}
              >
                read the Programme
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function Timeline({
  path,
  pollMs = 15000,
  showProblem = false,
  problem,
  onSelectGoal,
  onOpenProgramme,
}: {
  /** where the log comes from. Two framings of one renderer
   * (`419dcb31`): the problem page reads its own archive, the Engine
   * reads the run it is sitting on — which spans every problem under a
   * pattern scope and so can never be delegated to a problem page. */
  path: string
  pollMs?: number
  /** name the problem on each row — only the run view needs it, and
   * only when the run holds more than one */
  showProblem?: boolean
  /** the problem this log is scoped to. The run-scoped read merges
   * several and stamps each row, so it passes nothing. */
  problem?: string
  /** where clicking a goal's name lands: the star map (the side panel
   * carries the history). The run view navigates to the problem's own
   * page — the second argument says which. */
  onSelectGoal?: (id: number, problem: string | null) => void
  /** where "read the Programme" lands, told which task the row is
   * about — on the shelf-wide feed that is the row's own, not the
   * reader's scope */
  onOpenProgramme?: (problem: string | null) => void
}) {
  const { data, error, loading } = usePoll<{
    events: TimelineEvent[]
    /** the per-task feed's seam. The shelf-wide one carries a MAP under
     * its own key instead (`log_since_by_problem`) — one line across
     * several tasks would mislabel every task but one, so the seam is
     * simply not drawn there. */
    log_since?: string | null
    groups?: TimelineGroup[]
    problems?: string[]
    truncated?: number
    /** the shelf-wide feed pages; `null` at the end of the history */
    next_before?: string | null
  }>(path, pollMs, { keepPrevious: true })
  const [follow, setFollow] = useState<Follow | null>(null)
  /** pages fetched behind the first one, oldest-ward. History does not
   * change, so they are held rather than re-polled. */
  const [older, setOlder] = useState<TimelineEvent[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  // a new subject is a new history — never show one feed's tail under
  // another's head
  useEffect(() => {
    setOlder([])
    setCursor(null)
  }, [path])

  // dispatch rows for bricks that don't exist (kind 'asked', no goal):
  // the backend's label falls back to the problem name — identical on
  // every row — and there is no goal to open or follow. They fail the
  // log's one law, so they never render; asked rows for bricks that DO
  // exist carry a name and a goal id and stay (owner, 2026-08-24)
  const all = useMemo(
    () =>
      [...(data?.events ?? []), ...older].filter(
        (e) => !(e.kind === 'asked' && e.goal_id === null),
      ),
    [data, older],
  )
  const more = cursor ?? data?.next_before ?? null
  const loadEarlier = async () => {
    if (more === null || loadingMore) return
    setLoadingMore(true)
    try {
      const page = await apiGet<{ events: TimelineEvent[]; next_before?: string | null }>(
        `${path}${path.includes('?') ? '&' : '?'}before=${encodeURIComponent(more)}`,
      )
      setOlder((o) => [...o, ...page.events])
      setCursor(page.next_before ?? null)
    } catch {
      /* the button stays; the history is not going anywhere */
    } finally {
      setLoadingMore(false)
    }
  }
  const since = data?.log_since ?? null
  // one group is the ordinary case and reads exactly as it did before
  // groups existed — the argument is named only where there is a
  // choice of arguments to name (v35's standing law)
  const argOf = useMemo(() => {
    const gs = data?.groups ?? []
    if (gs.length < 2) return () => null
    const by = new Map(gs.map((g) => [g.id, groupLabel(g.id, g.label)]))
    return (id: number | null) => (id === null ? null : (by.get(id) ?? null))
  }, [data])

  if (loading && all.length === 0)
    return <div className="late-fade px-4 py-8 text-center text-xs text-ink-faint">Loading…</div>
  if (error && all.length === 0)
    return <div className="px-4 py-8 text-center text-xs text-ink-dim">{error.message}</div>
  if (all.length === 0)
    return <div className="px-4 py-8 text-center text-xs text-ink-faint">Nothing has happened yet.</div>

  const shown = all.filter((e) => {
    if (follow !== null) return followMatches(follow, e)
    // dispatch-start rows ('asked for') complete a brick's life when
    // you FOLLOW it, but in the stream they double every attempt —
    // the failed/proved rows already mark what happened (owner,
    // 2026-08-25). Reachable through the expansion's follow link.
    return e.kind !== 'asked'
  })

  return (
    <div className="flex flex-col">
      {/* nothing sits above the log any more — no lens chips, no held-
          back count. When you are following one object, that state has
          to be visible and reversible, so THAT line stays. */}
      {follow !== null && (
        <div className="mb-2 flex items-center gap-3 px-2">
          <span className="text-[11px] text-ink-faint">following</span>
          <span
            className={`text-[12px] text-ink ${
              follow.kind === 'goal' ? 'font-mono' : ''
            }`}
          >
            {followName(follow)}
          </span>
          <span className="tnum text-[11px] text-ink-faint">{shown.length} events</span>
          <button
            className="text-[11px] text-ink-faint underline decoration-edge-strong underline-offset-2 hover:text-ink"
            onClick={() => setFollow(null)}
          >
            clear
          </button>
        </div>
      )}
      {shown.length === 0 && (
        <div className="px-4 py-6 text-center text-xs text-ink-faint">
          No events match this filter.
        </div>
      )}
      {shown.map((e, i) => {
        const day = DAY_FMT.format(new Date(e.at))
        const newDay = i === 0 || DAY_FMT.format(new Date(shown[i - 1].at)) !== day
        // where the engine's own record of state changes begins: above
        // it the transitions were written down, below they are inferred
        // from the work that produced them. Unmarked, the seam is
        // invisible and in three months nobody knows which half is
        // which (backend, 2026-08-07)
        const seam =
          since !== null && i > 0 && shown[i - 1].at >= since && e.at < since
        // burst-vs-stall rhythm: a same-day gap over an hour gets
        // whitespace ∝ log(Δt), so a 6-hour stall looks different from
        // a 40-second burst (newest-first: gap to the row above)
        const dt = newDay ? 0 : Math.abs(Date.parse(shown[i - 1].at) - Date.parse(e.at))
        const gap = dt > 3600_000 ? Math.min(26, 6 + Math.round(Math.log10(dt / 3600_000) * 16)) : 0
        return (
          <div key={e.id} style={gap > 0 ? { marginTop: gap } : undefined}>
            {seam && (
              <div
                className="mt-3 mb-2 flex items-center gap-3 px-2"
                title="goal_events — the engine began writing state changes down here. Older landings are dated by inference from the work that produced them, so they are close but not the engine's own word."
              >
                <span className="h-px flex-1 bg-edge" />
                <span className="text-[10px] tracking-wide text-ink-faint">
                  older landings are reconstructed
                </span>
                <span className="h-px flex-1 bg-edge" />
              </div>
            )}
            {newDay && (
              <div className="mt-4 mb-1 flex items-center gap-3 px-2 first:mt-1">
                <span className="text-[11px] font-medium tracking-widest text-ink-faint uppercase">
                  {day}
                </span>
                <span className="h-px flex-1 bg-edge" />
              </div>
            )}
            <Row
              e={e}
              /* hide the object only when the header already says
                 exactly it. A followed Programme's rows are labelled
                 with each revision's own title — different every row,
                 and the whole content of that reading */
              following={follow?.kind === 'goal'}
              prefix={follow === null}
              showProblem={showProblem && (data?.problems?.length ?? 0) > 1}
              argument={argOf(e.group_id)}
              problem={problem}
              onFollow={setFollow}
              onOpenGoal={onSelectGoal}
              onOpenProgramme={onOpenProgramme}
            />
          </div>
        )
      })}
      {/* a shelf's history is every task's at once, so it pages. One
          task's does not, and the button simply never appears. */}
      {more !== null && follow === null && (
        <button
          className="mt-4 cursor-pointer self-center text-[11px] text-ink-faint underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink"
          onClick={() => void loadEarlier()}
          disabled={loadingMore}
        >
          {loadingMore ? 'reading…' : 'load earlier'}
        </button>
      )}
    </div>
  )
}
