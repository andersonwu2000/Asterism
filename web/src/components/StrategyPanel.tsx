import { useEffect } from 'react'
import { usePoll } from '../lib/api'
import { relTime } from '../lib/format'
import { renderProse } from '../lib/prose'
import { GOAL_STATUS_CLS, goalStatusLabel, strategyStatusLabel } from '../lib/vocab'
import { SectionLabel } from './ui'

/** Strategy (decomposition) drill-down: the agent's proposal reasoning,
 * subgoal roster, and why it died if it died. */

interface StrategyDetail {
  id: number
  goal_id: number
  goal_slug: string
  status: string
  proposal_md: string
  created_by: string
  created_at: string
  subgoals: { id: number; slug: string; status: string; position: number }[]
  dead_attempts: {
    id: number
    pipeline_id: string
    failure_reason: string
    failure_detail: string | null
    ts: string
  }[]
}

const STRAT_STATUS_CLS: Record<string, string> = {
  succeeded: 'text-starlight',
  proposed: 'text-accent',
  dead: 'text-danger',
  superseded: 'text-ink-faint',
  stalled: 'text-warn',
}

export default function StrategyPanel({
  problem,
  strategyId,
  onClose,
  onSelectGoal,
}: {
  problem: string
  strategyId: number
  onClose: () => void
  onSelectGoal: (id: number) => void
}) {
  const { data, error, loading } = usePoll<StrategyDetail>(
    `/api/problems/${encodeURIComponent(problem)}/strategies/${strategyId}`,
    5000,
  )
  // Esc closes — same law as GoalPanel (QA: the star panels were the
  // only surfaces that ignored it)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      const t = e.target as Element | null
      if (t?.closest('input, textarea, [contenteditable], aside[aria-label="explainer chat"]'))
        return
      onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="rise-in flex h-full w-96 shrink-0 flex-col border-l border-edge bg-surface">
      <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
        <span className="truncate font-mono text-sm text-ink">
          strategy s{strategyId}
          {data && <span className="text-ink-faint"> on {data.goal_slug}</span>}
        </span>
        <button
          className="ml-2 rounded-md px-1.5 text-ink-faint hover:text-ink"
          onClick={onClose}
          title="Close"
        >
          ✕
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {loading && <div className="late-fade text-xs text-ink-faint">Loading…</div>}
        {error && !data && <div className="text-xs text-danger">{String(error.message)}</div>}
        {data && (
          <>
            <div className="mb-3 flex items-center gap-3 text-xs">
              <span className={STRAT_STATUS_CLS[data.status] ?? 'text-ink-dim'}>
                {strategyStatusLabel(data.status)}
              </span>
              <span className="text-ink-faint">
                by {data.created_by} · {relTime(data.created_at)}
              </span>
            </div>
            <SectionLabel>subgoals ({data.subgoals.length})</SectionLabel>
            <div className="mb-4 flex flex-col gap-0.5">
              {data.subgoals.map((sg) => (
                <button
                  key={sg.id}
                  className="flex items-baseline justify-between rounded-md px-2 py-1 text-left hover:bg-surface-2"
                  onClick={() => onSelectGoal(sg.id)}
                >
                  <span className="font-mono text-xs text-ink">{sg.slug}</span>
                  <span className={`text-[11px] ${GOAL_STATUS_CLS[sg.status] ?? 'text-ink-dim'}`}>
                    {goalStatusLabel(sg.status)}
                  </span>
                </button>
              ))}
            </div>
            {data.dead_attempts.length > 0 && (
              <>
                <SectionLabel>failures</SectionLabel>
                <div className="mb-4 flex flex-col gap-1">
                  {data.dead_attempts.map((a) => (
                    <div key={a.id} className="rounded-md border border-edge px-2 py-1.5">
                      <div className="flex justify-between text-[11px]">
                        <span className="font-mono text-danger/90">{a.failure_reason}</span>
                        <span className="text-ink-faint">{relTime(a.ts)}</span>
                      </div>
                      {a.failure_detail && (
                        <pre className="mt-1 font-mono text-[11px] whitespace-pre-wrap text-ink-faint">
                          {a.failure_detail.slice(0, 600)}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
            <SectionLabel>proposal</SectionLabel>
            {data.proposal_md ? (
              // working markdown with $TeX$ and Lean fences — read it
              // as prose, not a mono dump (class fix, 2026-07-25)
              <div className="text-[12px] leading-relaxed text-ink-dim">
                {renderProse(data.proposal_md, { mode: 'document' })}
              </div>
            ) : (
              <div className="text-xs text-ink-faint">No proposal recorded.</div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
