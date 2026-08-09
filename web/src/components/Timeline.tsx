import { useMemo, useState } from 'react'
import { usePoll } from '../lib/api'
import { EVENT_CLS, eventLabel, eventTitle, failureLabel } from '../lib/vocab'
import type { TimelineEvent, TimelineGroup } from '../lib/types'

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
 *     object: one click and you read a single brick's whole life
 *     (asked → attempt 2 → proved), which is the reading the old
 *     decision-only timeline could not do at all.
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

/** Lenses, not per-verb chips: eleven verbs would be eleven chips, and
 * the questions a reader actually arrives with are three. */
const LENSES: { key: string; label: string; kinds: string[]; title: string }[] = [
  {
    key: 'landed',
    label: 'landings',
    kinds: ['proved', 'disproved', 'deliverable', 'ingested'],
    title: 'what the machine finished',
  },
  {
    key: 'stuck',
    label: 'setbacks',
    kinds: ['attempt', 'hiccup', 'set_aside', 'dead', 'asked_you'],
    title: 'where it lost time',
  },
  {
    key: 'argument',
    label: 'argument',
    kinds: [
      'rev', 'proposal', 'handed_off', 'handed_back', 'closed_group',
      'directive', 'held', 'paper',
    ],
    title: 'the Programme, the discussion groups, and the sources',
  },
]

/* An infra death cost no attempt, and a rejected proposal is a round
 * of editing rather than a change to the record — both are true
 * history and neither is news, so they stay off the default read and
 * come back with one click. */
const QUIET_KINDS = new Set(['hiccup', 'proposal'])

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
  | { kind: 'goal'; label: string }
  | { kind: 'programme' }
  | { kind: 'group'; id: number | null; label: string }

function followFor(e: TimelineEvent): Follow {
  if (e.object_kind === 'programme') return { kind: 'programme' }
  if (e.object_kind === 'group')
    return { kind: 'group', id: e.object_group_id, label: e.label }
  return { kind: 'goal', label: e.label }
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
  return f.kind === 'programme' ? 'the Programme' : f.label
}

function Row({
  e,
  following,
  prefix,
  argument,
  showProblem,
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
  onFollow: (f: Follow) => void
  onOpenGoal?: (id: number) => void
  onOpenProgramme?: () => void
}) {
  const [open, setOpen] = useState(false)
  const expandable = Boolean(e.body || e.note || argument)
  const note = e.kind === 'attempt' || e.kind === 'hiccup'
    ? failureLabel(e.note ?? '')
    : e.note
  return (
    <div>
      <div
        className={`grid grid-cols-[3.1rem_6.2rem_1fr] items-baseline gap-2 rounded-md px-2 py-[3px] ${
          expandable ? 'cursor-pointer hover:bg-surface' : ''
        }`}
        onClick={expandable ? () => setOpen((v) => !v) : undefined}
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
                : `${e.label} — click to follow it through the log`
            }
            onClick={(ev) => {
              ev.stopPropagation()
              onFollow(followFor(e))
            }}
            onKeyDown={(ev) => {
              if (ev.key === 'Enter') {
                ev.stopPropagation()
                onFollow(followFor(e))
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
          {argument && (
            /* which argument this brick serves. A column would cost
               width on every problem to answer a question only
               multi-group problems raise (owner, 2026-08-07) */
            <div
              className="mb-1.5 text-[11px] text-ink-faint"
              title="the discussion group whose programme commissioned this — a problem under load argues several at once"
            >
              for <span className="text-ink-dim">{argument}</span>
            </div>
          )}
          {note && <div className="mb-1.5 text-xs text-ink-dim">{note}</div>}
          {e.body && (
            <pre className="font-mono text-[11px] whitespace-pre-wrap text-ink-faint">
              {e.body}
            </pre>
          )}
          <div className="mt-1.5 flex items-center gap-3 text-[11px]">
            {e.goal_id !== null && onOpenGoal && (
              <button
                className="text-ink-faint underline decoration-edge-strong underline-offset-2 hover:text-ink"
                onClick={() => onOpenGoal(e.goal_id as number)}
              >
                open on the map
              </button>
            )}
            {e.object_kind === 'programme' && onOpenProgramme && (
              <button
                className="text-ink-faint underline decoration-edge-strong underline-offset-2 hover:text-ink"
                onClick={onOpenProgramme}
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
  followGoal = null,
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
  /** open already following this goal — another surface can make a
   * claim ("5 failed attempts") and hand the reader its evidence */
  followGoal?: string | null
  onSelectGoal?: (id: number) => void
  onOpenProgramme?: () => void
}) {
  const { data, error, loading } = usePoll<{
    events: TimelineEvent[]
    log_since: string | null
    groups: TimelineGroup[]
    problems?: string[]
    truncated?: number
  }>(path, pollMs, { keepPrevious: true })
  const [lens, setLens] = useState<string | null>(null)
  const [quiet, setQuiet] = useState(false)
  const [follow, setFollow] = useState<Follow | null>(
    followGoal ? { kind: 'goal', label: followGoal } : null)

  const all = useMemo(() => data?.events ?? [], [data])
  const since = data?.log_since ?? null
  // one group is the ordinary case and reads exactly as it did before
  // groups existed — the argument is named only where there is a
  // choice of arguments to name (v35's standing law)
  const argOf = useMemo(() => {
    const gs = data?.groups ?? []
    if (gs.length < 2) return () => null
    const by = new Map(gs.map((g) => [g.id, g.label]))
    return (id: number | null) => (id === null ? null : (by.get(id) ?? null))
  }, [data])

  if (loading && all.length === 0)
    return <div className="late-fade px-4 py-8 text-center text-xs text-ink-faint">Loading…</div>
  if (error && all.length === 0)
    return <div className="px-4 py-8 text-center text-xs text-ink-dim">{error.message}</div>
  if (all.length === 0)
    return <div className="px-4 py-8 text-center text-xs text-ink-faint">Nothing has happened yet.</div>

  const lensKinds = LENSES.find((l) => l.key === lens)?.kinds
  const shown = all.filter((e) => {
    if (follow !== null) return followMatches(follow, e)
    if (lensKinds) return lensKinds.includes(e.kind)
    return quiet || !QUIET_KINDS.has(e.kind)
  })
  const quietHidden = follow === null && !lensKinds && !quiet
    ? all.filter((e) => QUIET_KINDS.has(e.kind)).length
    : 0

  const chip = (key: string | null, label: string, count: number, title?: string) => (
    <button
      key={key ?? 'all'}
      className={`rounded-full border px-2 py-0.5 text-[11px] ${
        lens === key
          ? 'border-star/60 bg-star/10 text-star'
          : 'border-edge text-ink-faint hover:text-ink'
      }`}
      onClick={() => setLens(lens === key ? null : key)}
      title={title}
    >
      {label} <span className="tnum">{count}</span>
    </button>
  )

  return (
    <div className="flex flex-col">
      {follow !== null ? (
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
      ) : (
        <div className="mb-2 flex flex-wrap items-center gap-1.5 px-2">
          {chip(null, 'all', all.length - quietHidden)}
          {LENSES.map((l) => {
            const n = all.filter((e) => l.kinds.includes(e.kind)).length
            return n > 0 ? chip(l.key, l.label, n, l.title) : null
          })}
          {quietHidden > 0 && (
            <button
              className="text-[11px] text-ink-faint underline decoration-edge-strong underline-offset-2 hover:text-ink"
              onClick={() => setQuiet(true)}
              title="infrastructure deaths that cost no attempt, and revision proposals the reviewer rejected"
            >
              +{quietHidden} quiet
            </button>
          )}
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
              onFollow={setFollow}
              onOpenGoal={onSelectGoal}
              onOpenProgramme={onOpenProgramme}
            />
          </div>
        )
      })}
    </div>
  )
}
