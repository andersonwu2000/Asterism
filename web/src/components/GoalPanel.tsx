import { useState } from 'react'
import { usePoll } from '../lib/api'
import { relTime } from '../lib/format'
import { Lean } from '../lib/lean'
import { goalStatusLabel, originLabel, strategyStatusLabel } from '../lib/vocab'
import { SectionLabel } from './ui'
import type { DeadAttempt, GoalDetail } from '../lib/types'

/** Right-hand drill-down for a selected goal: statement, lifecycle
 * facts, dead-attempt forensics (failure reason + detail + the agent's
 * postmortem proposal). */

const GOAL_STATUS_CLS: Record<string, string> = {
  proved: 'text-starlight',
  attempting: 'text-accent',
  open: 'text-accent',
  shelved: 'text-ink-faint',
  pending_strategist_review: 'text-warn',
  disproved: 'text-danger',
  dead: 'text-ink-faint',
  frozen: 'text-ink-faint',
}

function Attempt({ a }: { a: DeadAttempt }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-md border border-edge">
      <button
        className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-surface-2"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="font-mono text-xs text-danger/90">{a.failure_reason}</span>
        <span className="text-[11px] text-ink-faint">{relTime(a.ts)}</span>
      </button>
      {open && (
        <div className="border-t border-edge px-3 py-2">
          {a.failure_detail && (
            <pre className="mb-2 font-mono text-[11px] leading-snug whitespace-pre-wrap text-ink-dim">
              {a.failure_detail}
            </pre>
          )}
          {a.proposal_md && (
            <>
              <SectionLabel>postmortem</SectionLabel>
              <pre className="font-mono text-[11px] leading-snug whitespace-pre-wrap text-ink-dim">
                {a.proposal_md}
              </pre>
            </>
          )}
          {!a.failure_detail && !a.proposal_md && (
            <div className="text-xs text-ink-faint">No details recorded.</div>
          )}
        </div>
      )}
    </div>
  )
}

export default function GoalPanel({
  problem,
  goalId,
  onClose,
  onSelectStrategy,
  onOpenFile,
}: {
  problem: string
  goalId: number
  onClose: () => void
  onSelectStrategy?: (id: number) => void
  onOpenFile?: (relPath: string) => void
}) {
  const { data, error, loading } = usePoll<GoalDetail>(
    `/api/problems/${encodeURIComponent(problem)}/goals/${goalId}`,
    5000,
  )

  return (
    <div className="rise-in flex h-full w-96 shrink-0 flex-col border-l border-edge bg-surface">
      <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
        <span className="truncate font-mono text-sm text-ink" title={data?.slug}>{data?.slug ?? `#${goalId}`}</span>
        <button
          className="ml-2 rounded px-1.5 text-ink-faint hover:text-ink"
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
            <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              <span className={GOAL_STATUS_CLS[data.status] ?? 'text-ink-dim'}>
                {goalStatusLabel(data.status)}
              </span>
              <span className="text-ink-faint">{data.kind}</span>
              <span className="text-ink-faint">{originLabel(data.origin)}</span>
              {data.is_deliverable && <span className="text-star">deliverable</span>}
              {data.detached && <span className="text-ink-faint">detached</span>}
            </div>
            <SectionLabel>statement</SectionLabel>
            <pre className="mb-4 font-mono text-xs leading-snug break-words whitespace-pre-wrap text-ink">
              <Lean code={data.statement} />
            </pre>
            <div className="mb-4 text-[11px] break-all text-ink-faint">
              {onOpenFile && data.lean_path.includes('proofs/') ? (
                <button
                  className="text-left break-all underline decoration-edge-strong hover:text-ink"
                  onClick={() =>
                    onOpenFile(`proofs/${data.lean_path.split('proofs/').pop()}`)
                  }
                  title="Open in the Files tab"
                >
                  {data.lean_path}
                </button>
              ) : (
                data.lean_path
              )}{' '}
              · created {relTime(data.created_at)}
            </div>
            {data.strategies.length > 0 && (
              <>
                <SectionLabel>decompositions ({data.strategies.length})</SectionLabel>
                <div className="mb-4 flex flex-col gap-0.5">
                  {data.strategies.map((s) => (
                    <button
                      key={s.id}
                      className="flex items-baseline justify-between rounded px-2 py-1 text-left hover:bg-surface-2 disabled:cursor-default"
                      disabled={!onSelectStrategy}
                      onClick={() => onSelectStrategy?.(s.id)}
                    >
                      <span className="font-mono text-xs text-ink">
                        s{s.id}
                        <span className="ml-2 text-ink-faint">
                          {s.subgoal_count} subgoal{s.subgoal_count === 1 ? '' : 's'}
                        </span>
                      </span>
                      <span
                        className={`text-[11px] ${
                          s.status === 'succeeded'
                            ? 'text-starlight'
                            : s.status === 'proposed'
                              ? 'text-accent'
                              : s.status === 'dead'
                                ? 'text-danger'
                                : 'text-ink-faint'
                        }`}
                      >
                        {strategyStatusLabel(s.status)}
                      </span>
                    </button>
                  ))}
                </div>
              </>
            )}
            <SectionLabel>
              failed attempts {data.dead_attempts.length > 0 && `(${data.dead_attempts.length})`}
            </SectionLabel>
            {data.dead_attempts.length === 0 ? (
              <div className="text-xs text-ink-faint">None.</div>
            ) : (
              <div className="flex flex-col gap-1.5">
                {data.dead_attempts.map((a) => (
                  <Attempt key={a.id} a={a} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
