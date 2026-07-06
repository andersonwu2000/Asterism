import { useState } from 'react'
import type { Decision } from '../lib/types'

/* rows sit under day rules — a clock time reads better than thirty
 * copies of "37d ago" */
const TIME_FMT = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })

/** Strategist decision timeline (charter §3.3): newest first, one row
 * per decision, batch siblings visually grouped by a shared left rail. */

const KIND_CLS: Record<string, string> = {
  Inject: 'text-accent',
  Ingest: 'text-star',
  MarkDeliverable: 'text-star',
  ConfirmShelve: 'text-ink-dim',
  RequestUserAmend: 'text-danger',
  EmitDirective: 'text-warn',
  Noop: 'text-ink-faint',
}

/* positive outcomes are the norm — they collapse to a quiet check so
 * the timeline's color budget goes to failures and pauses */
const OK_OUTCOMES = new Set(['success', 'accepted', 'live_subgoal', 'closed_subgoal'])

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
  const summary = d.brief || d.reason || ''
  const pipeline = typeof d.payload?.pipeline === 'string' ? (d.payload.pipeline as string) : null
  return (
    <div className={`relative pl-4 ${grouped ? 'border-l border-edge-strong/60' : ''}`}>
      <button
        className="grid w-full grid-cols-[8rem_1fr_auto] items-baseline gap-2 rounded px-2 py-1.5 text-left hover:bg-surface"
        onClick={() => setOpen((v) => !v)}
      >
        <span className={`text-xs font-medium ${KIND_CLS[d.decision_kind] ?? 'text-ink-dim'}`}>
          {d.decision_kind}
          {pipeline && <span className="text-ink-faint"> · {pipeline}</span>}
        </span>
        <span className="truncate text-xs text-ink-dim">{summary}</span>
        <span className="text-right text-[11px] whitespace-nowrap text-ink-faint">
          {d.outcome &&
            (OK_OUTCOMES.has(d.outcome) ? (
              <span className="mr-2 text-ink-faint" title={d.outcome}>
                ✓
              </span>
            ) : (
              <span className={`mr-2 ${OUTCOME_CLS[d.outcome] ?? 'text-ink-dim'}`}>
                {d.outcome}
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

const DAY_FMT = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
})

export default function DecisionTimeline({ decisions }: { decisions: Decision[] }) {
  if (decisions.length === 0) {
    return <div className="px-4 py-8 text-center text-xs text-ink-faint">No decisions yet.</div>
  }
  const dayOf = (iso: string) => DAY_FMT.format(new Date(iso))
  return (
    <div className="flex flex-col">
      {decisions.map((d, i) => (
        <div key={d.id}>
          {/* day rules give a 44-day history its chapters */}
          {(i === 0 || dayOf(decisions[i - 1].created_at) !== dayOf(d.created_at)) && (
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
              (decisions[i - 1]?.batch_id === d.batch_id ||
                decisions[i + 1]?.batch_id === d.batch_id)
            }
          />
        </div>
      ))}
    </div>
  )
}
