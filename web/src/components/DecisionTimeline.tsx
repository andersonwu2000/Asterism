import { useState } from 'react'
import { decisionKindLabel, decisionKindTitle } from '../lib/vocab'
import type { Decision } from '../lib/types'

/* rows sit under day rules — a clock time reads better than thirty
 * copies of "37d ago". Locale is PINNED: `undefined` followed the
 * browser and dropped 下午07:14 / 2026年7月11日 into an English-voiced
 * page (audit, 2026-07-11); a 24h clock is also just denser. */
const TIME_FMT = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})

/** Strategist decision timeline (charter §3.3): newest first, one row
 * per decision, batch siblings visually grouped by a shared left rail. */

/* amber is reserved app-wide for "the human's move" — routine machine
 * events speak in neutral hues */
const KIND_CLS: Record<string, string> = {
  Inject: 'text-accent',
  Ingest: 'text-star',
  MarkDeliverable: 'text-star',
  ConfirmShelve: 'text-ink-dim',
  RequestUserAmend: 'text-warn',
  EmitDirective: 'text-ink-dim',
  FetchPaper: 'text-ink-dim',
  Noop: 'text-ink-faint',
}

/* positive outcomes are the norm — they collapse to a quiet check so
 * the timeline's color budget goes to failures and pauses */
const OK_OUTCOMES = new Set([
  'success',
  'accepted',
  'live_subgoal',
  'closed_subgoal',
  'proved',
  'paper_fetched',
])

/* failure is a CLOSED set of explicit shapes; an outcome this build
 * hasn't met renders neutrally instead of being branded a failure
 * ("not in the OK list" once counted the brand-new paper_fetched as
 * the run's only failure) */
const isFailureOutcome = (o: string) =>
  o === 'aborted' || o.startsWith('failed') || o.startsWith('exhausted') || o === 'rejected'

/* outcome enums get human labels */
const OUTCOME_LABEL: Record<string, string> = {
  awaiting_human: 'awaiting you',
  verify_failed: 'verify failed',
  forward_no_new_goal: 'no new goal',
  shelved_produced: 'shelved',
}

const OUTCOME_CLS: Record<string, string> = {
  awaiting_human: 'text-danger',
  rejected: 'text-danger',
  verify_failed: 'text-danger',
  cyclic: 'text-danger',
  forward_no_new_goal: 'text-warn',
  shelved_produced: 'text-ink-dim',
  stalled: 'text-warn',
}

function Row({ d, grouped }: { d: Decision; grouped: boolean }) {
  const [open, setOpen] = useState(false)
  // briefs are working markdown — the one-line summary strips the
  // notation ("## Need ONE Forward brick…" leaked literal hashes;
  // cold-eye). The expanded view keeps the raw text.
  const summary = (d.brief || d.reason || '')
    .replace(/^#{1,6}\s+/, '')
    .replace(/\*\*/g, '')
  const pipeline = typeof d.payload?.pipeline === 'string' ? (d.payload.pipeline as string) : null
  return (
    <div className={`relative pl-4 ${grouped ? 'border-l border-edge-strong/60' : ''}`}>
      <button
        className="group grid w-full grid-cols-[9.5rem_1fr_auto] items-baseline gap-2 rounded px-2 py-1.5 text-left hover:bg-surface"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span
          className={`text-xs font-medium ${KIND_CLS[d.decision_kind] ?? 'text-ink-dim'}`}
          title={decisionKindTitle(d.decision_kind)}
        >
          <span
            className={`mr-1.5 inline-block text-[9px] text-ink-faint transition-transform duration-150 ${open ? 'rotate-90' : ''} opacity-0 group-hover:opacity-100 ${open ? 'opacity-100' : ''}`}
            aria-hidden
          >
            ▸
          </span>
          {decisionKindLabel(d.decision_kind)}
          {pipeline && <span className="text-ink-faint"> · {pipeline}</span>}
        </span>
        <span className="truncate text-xs text-ink-dim">{summary}</span>
        <span className="flex items-baseline justify-end gap-2 text-right text-[11px] whitespace-nowrap text-ink-faint">
          {d.outcome &&
            (OK_OUTCOMES.has(d.outcome) ? null : (
              /* a quiet TAG, not loose words — the raw engine compound
                 ('failed:stalled') read as debris glued to the summary
                 (owner, audit 2026-07-11) */
              <span
                className={`rounded border border-edge px-1.5 py-px text-[10px] ${OUTCOME_CLS[d.outcome] ?? 'text-ink-dim'}`}
              >
                {OUTCOME_LABEL[d.outcome] ??
                  d.outcome.replace(':', ' · ').replace(/_/g, ' ')}
              </span>
            ))}
          {TIME_FMT.format(new Date(d.created_at))}
        </span>
      </button>
      {open && (
        <div className="mx-2 mb-2 rounded-md border border-edge bg-surface px-3 py-2">
          {d.brief && (
            <pre className="mb-2 font-mono text-[11px] whitespace-pre-wrap text-ink-dim">
              {d.brief}
            </pre>
          )}
          {d.reason && <div className="mb-1 text-xs text-ink-dim">{d.reason}</div>}
          {d.outcome_detail && (
            <pre className="font-mono text-[11px] whitespace-pre-wrap text-ink-faint">
              {d.outcome_detail}
            </pre>
          )}
          <div className="mt-1 text-[11px] text-ink-faint">
            trigger {d.trigger_kind}
            {d.batch_id && ` · batch ${d.batch_id.slice(0, 8)}`}
            {d.produced_goal_id !== null && ` · produced goal #${d.produced_goal_id}`}
          </div>
        </div>
      )}
    </div>
  )
}

const DAY_FMT = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
})

export default function DecisionTimeline({ decisions }: { decisions: Decision[] }) {
  const [filter, setFilter] = useState<string | null>(null)
  if (decisions.length === 0) {
    return <div className="px-4 py-8 text-center text-xs text-ink-faint">No decisions yet.</div>
  }
  const dayOf = (iso: string) => DAY_FMT.format(new Date(iso))
  const isFailure = (d: Decision) => d.outcome !== null && isFailureOutcome(d.outcome)
  const kinds = [...new Set(decisions.map((d) => d.decision_kind))].sort()
  const filtered =
    filter === null
      ? decisions
      : filter === '__failures'
        ? decisions.filter(isFailure)
        : decisions.filter((d) => d.decision_kind === filter)
  const chip = (key: string | null, label: string, count: number, title?: string) => (
    <button
      key={key ?? 'all'}
      className={`rounded-full border px-2 py-0.5 text-[11px] ${
        filter === key
          ? 'border-star/60 bg-star/10 text-star'
          : 'border-edge text-ink-faint hover:text-ink'
      }`}
      onClick={() => setFilter(filter === key ? null : key)}
      title={title}
    >
      {label} {count}
    </button>
  )
  return (
    <div className="flex flex-col">
      <div className="mb-2 flex flex-wrap gap-1.5 px-2">
        {chip(null, 'all', decisions.length)}
        {kinds.map((k) =>
          chip(
            k,
            decisionKindLabel(k),
            decisions.filter((d) => d.decision_kind === k).length,
            decisionKindTitle(k),
          ),
        )}
        {decisions.some(isFailure) &&
          chip('__failures', 'failures', decisions.filter(isFailure).length)}
      </div>
      {filtered.length === 0 && (
        <div className="px-4 py-6 text-center text-xs text-ink-faint">
          No events match this filter.
        </div>
      )}
      {filtered.map((d, i) => {
        const newDay = i === 0 || dayOf(filtered[i - 1].created_at) !== dayOf(d.created_at)
        // burst-vs-stall rhythm: a same-day gap over an hour gets
        // whitespace ∝ log(Δt), so a 6-hour stall looks different
        // from a 40-second burst (newest-first: gap to the row above)
        const dt = newDay
          ? 0
          : Math.abs(Date.parse(filtered[i - 1].created_at) - Date.parse(d.created_at))
        const gap =
          dt > 3600_000 ? Math.min(26, 6 + Math.round(Math.log10(dt / 3600_000) * 16)) : 0
        return (
          <div key={d.id} style={gap > 0 ? { marginTop: gap } : undefined}>
            {/* day rules give a 44-day history its chapters */}
            {newDay && (
              <div className="mt-4 mb-1 flex items-center gap-3 px-2 first:mt-1">
                <span className="text-[11px] font-medium tracking-widest text-ink-faint uppercase">
                  {dayOf(d.created_at)}
                </span>
                <span className="h-px flex-1 bg-edge" />
              </div>
            )}
            <Row
              d={d}
              grouped={
                d.batch_id !== null &&
                (filtered[i - 1]?.batch_id === d.batch_id ||
                  filtered[i + 1]?.batch_id === d.batch_id)
              }
            />
          </div>
        )
      })}
    </div>
  )
}
