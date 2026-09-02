import { useEffect, useState } from 'react'
import { usePoll } from '../lib/api'
import { goalCode, goalLabel, relTime } from '../lib/format'
import { Lean } from '../lib/lean'
import { renderProse } from '../lib/prose'
import {
  DETACHED_LABEL,
  DETACHED_TITLE,
  GOAL_STATUS_CLS,
  goalStatusLabel,
  originLabel,
  originTitle,
  strategyStatusLabel,
} from '../lib/vocab'
import { SectionLabel } from './ui'
import { GoalCommandSheet } from './CommandSheet'
import type { DeadAttempt, GoalDetail } from '../lib/types'
import { frameClass } from '../lib/textFrame'

/** Right-hand drill-down for a selected goal: the declaration source
 * as written (`name : statement := proof`, import prelude stripped),
 * routes, and — while the goal is still unproved — dead-attempt
 * forensics. A proved star's past failures are history, not signal. */

function Attempt({ a }: { a: DeadAttempt }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-lg border border-edge">
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
            <pre className={frameClass({ frame: false, lead: 'quote', className: 'mb-2' })}>
              {a.failure_detail}
            </pre>
          )}
          {a.proposal_md && (
            <>
              <SectionLabel>postmortem</SectionLabel>
              {/* working markdown with $TeX$ and Lean fences — read it
                  as prose, not a mono dump (class fix, 2026-07-25) */}
              <div className="text-[12px] leading-relaxed text-ink-dim">
                {renderProse(a.proposal_md, { mode: 'document' })}
              </div>
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

/** One quiet line naming what the source block below actually is.
 * Silent for a landed proof — that is the case the reader assumes. */
function SourceNote({
  data,
  onSelectStrategy,
}: {
  data: GoalDetail
  onSelectStrategy?: (id: number) => void
}) {
  const sid = data.source_strategy_id ?? null
  const route =
    sid !== null && onSelectStrategy ? (
      <button
        className="font-mono underline decoration-edge-strong decoration-dotted underline-offset-2 transition-colors hover:text-ink"
        onClick={() => onSelectStrategy(sid)}
        title="open this route — its reasoning and its subgoals"
      >
        s{sid}
      </button>
    ) : sid !== null ? (
      <span className="font-mono">s{sid}</span>
    ) : null

  if (data.source_state === 'open_route')
    return (
      <div className="mb-1.5 text-[11px] text-ink-faint">
        how it is split right now — the skeleton of route {route}, still open. Its{' '}
        <span title="engine term: sub-goal">pieces</span> are the stars below it.
      </div>
    )
  if (data.source_state === 'in_flight')
    return (
      <div className="mb-1.5 text-[11px] text-ink-faint">
        an agent is writing this right now — a draft in its scratch area, not yet
        part of the proof.
      </div>
    )
  if (data.source_state === 'own_file' && /\bsorry\b/.test(data.proof_text ?? ''))
    // "nothing attempted" would be a lie next to a list of failed
    // attempts — say only what the file shows: nothing LANDED
    return (
      <div className="mb-1.5 text-[11px] text-ink-faint">
        the bare statement — no work has landed in this node's own file.
      </div>
    )
  return null
}

export default function GoalPanel({
  problem,
  goalId,
  onClose,
  onSelectStrategy,
  onSelectGoal,
  onHoverGoals,
  onOpenFile,
}: {
  problem: string
  goalId: number
  onClose: () => void
  onSelectStrategy?: (id: number) => void
  /** jump the panel to a route's subgoal */
  onSelectGoal?: (id: number) => void
  /** light the hovered route's stars in the sky (null = release) */
  onHoverGoals?: (ids: number[] | null) => void
  onOpenFile?: (relPath: string) => void
}) {
  const { data, error, loading } = usePoll<GoalDetail>(
    `/api/problems/${encodeURIComponent(problem)}/goals/${goalId}`,
    5000,
  )
  /** routes whose subgoal name-list is unfolded */
  const [openRoutes, setOpenRoutes] = useState<Set<number>>(new Set())
  /** the command sheet (§1.3): a star is where a person acts on a goal */
  const [acting, setActing] = useState(false)
  // a lit star must not outlive the panel (or the hovered row)
  useEffect(() => () => onHoverGoals?.(null), [onHoverGoals])
  // Esc closes — every other panel honors it and QA tripped over the
  // one that didn't. Keystrokes inside inputs/the chat drawer are
  // theirs, not ours.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      const t = e.target as Element | null
      if (t?.closest('input, textarea, [contenteditable], aside[aria-label="assistant"]'))
        return
      // the sheet is the innermost thing open — Escape closes what is
      // in front of you, not the panel behind it
      if (acting) {
        setActing(false)
        return
      }
      onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, acting])

  return (
    <div className="rise-in flex h-full w-96 shrink-0 flex-col border-l border-edge bg-surface">
      <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
        <span
          className="flex min-w-0 items-baseline gap-2 font-mono text-sm"
          title={data ? goalLabel(data.id, data.slug) : goalCode(goalId)}
        >
          <span className="shrink-0 text-ink-faint">{goalCode(goalId)}</span>
          {data && <span className="truncate text-ink">{data.slug}</span>}
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
            <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              <span className={GOAL_STATUS_CLS[data.status] ?? 'text-ink-dim'}>
                {goalStatusLabel(data.status)}
              </span>
              <span className="text-ink-faint">{data.kind}</span>
              <span className="text-ink-faint" title={originTitle(data.origin)}>
                {originLabel(data.origin)}
              </span>
              {data.is_deliverable &&
                (data.human_facing_claim ? (
                  <span
                    className="text-star"
                    title="a result YOU vouch for at sign-off — the top group's promise (engine term: deliverable)"
                  >
                    claim
                  </span>
                ) : (
                  /* a sub-group's mark is a delivery to the group above
                     it, not a promise to the reader. Same flag in the
                     DB, different audience — and calling both "claim"
                     asked the human to vouch for 23 pieces of machine
                     bookkeeping (owner, 2026-08-12). */
                  <span
                    className="text-ink-faint"
                    title="a brick a discussion group delivered to the group above it — tracked between groups, not something you sign off on (engine term: deliverable, marked by a sub-group)"
                  >
                    delivered
                  </span>
                ))}
              {data.disproof_of && (
                <span
                  className="text-warn"
                  title={`this theorem is the negation of ${goalLabel(data.disproof_of.id, data.disproof_of.slug)} — the kernel settled the original claim as false`}
                >
                  disproof of {goalLabel(data.disproof_of.id, data.disproof_of.slug)}
                </span>
              )}
              {data.detached && (
                <span className="text-ink-faint" title={DETACHED_TITLE}>
                  {DETACHED_LABEL}
                </span>
              )}
            </div>
            <SectionLabel>{data.proof_text ? 'source' : 'statement'}</SectionLabel>
            {/* A node's own file is a `:= by sorry` stub for its whole
                working life — the decomposition lives in the ROUTE's
                file, a live attempt only in a workarea. The panel now
                shows that text, so it must say which one it is (owner,
                2026-08-01). */}
            {data.proof_text && <SourceNote data={data} onSelectStrategy={onSelectStrategy} />}
            {/* no inner scroll: the panel body is the ONE scroll
                context — a nested max-h pane read as double
                scrollbars (owner). The import/open/namespace preamble
                folds away so the first visible line is the THEOREM —
                a professor judging a claim wants the proposition, not
                eight lines of plumbing (design round, 2026-07-13) */}
            {(() => {
              const src = data.proof_text ?? data.statement
              const lines = src.split('\n')
              let cut = 0
              while (
                cut < lines.length &&
                (/^\s*(import|open|namespace|section|noncomputable section|set_option|universe|attribute|variable)\b/.test(
                  lines[cut],
                ) ||
                  lines[cut].trim() === '')
              )
                cut++
              const preamble = lines.slice(0, cut).join('\n').trimEnd()
              const body = lines.slice(cut).join('\n')
              return (
                <>
                  {preamble && (
                    <details className="group/pre mb-1">
                      <summary className="cursor-pointer list-none font-mono text-[10px] text-ink-faint transition-colors hover:text-ink-dim">
                        <span
                          className="mr-1 inline-block text-[9px] transition-transform duration-150 group-open/pre:rotate-90"
                          aria-hidden
                        >
                          ▸
                        </span>
                        context · {cut} line{cut === 1 ? '' : 's'}
                      </summary>
                      <pre className={frameClass({ frame: false, lead: 'quote', tone: 'faint', className: 'mt-1' })}>
                        <Lean code={preamble} />
                      </pre>
                    </details>
                  )}
                  <pre className={frameClass({ frame: false, lead: 'quote', tone: 'ink', size: 'md', className: 'mb-3' })}>
                    <Lean code={body} />
                  </pre>
                </>
              )
            })()}
            <div className="mb-4 text-[11px] break-all text-ink-faint">
              {onOpenFile && (data.source_path ?? data.lean_path).includes('proofs/') ? (
                <button
                  className="text-left break-all underline decoration-edge-strong hover:text-ink"
                  onClick={() =>
                    onOpenFile(
                      `proofs/${(data.source_path ?? data.lean_path).split('proofs/').pop()}`,
                    )
                  }
                  title="Open in the Files tab"
                >
                  {data.source_path ?? data.lean_path}
                </button>
              ) : (
                (data.source_path ?? data.lean_path)
              )}
            </div>
            {data.strategies.filter((s) => s.subgoal_count > 0).length > 0 && (
              <>
                <SectionLabel>routes</SectionLabel>
                <div className="mb-4 flex flex-col gap-0.5">
                  {data.strategies
                    .filter((s) => s.subgoal_count > 0)
                    .map((s) => {
                      const subs = s.subgoals ?? []
                      // a route's children and a route's INPUTS are not
                      // the same list: `reused` ones already existed and
                      // this route only reaches for them (v44 link_kind).
                      // Counting them as subgoals credited routes with
                      // decompositions they never made — s25803 read as
                      // "8 subgoals" having minted none of them.
                      const minted = subs.filter((x) => !x.reused).length
                      const cited = subs.length - minted
                      const multi = subs.length > 1
                      const unfolded = openRoutes.has(s.id)
                      const statusCls =
                        s.status === 'succeeded'
                          ? 'text-starlight'
                          : s.status === 'proposed'
                            ? 'text-accent'
                            : s.status === 'dead'
                              ? 'text-danger'
                              : 'text-ink-faint'
                      return (
                        <div key={s.id}>
                          {/* the route names its children (owner: seven
                              rows of '1 subgoal' were indistinguishable);
                              hover lights their stars, the s-number
                              matches the plan notes' vocabulary */}
                          <div
                            className="flex items-baseline gap-1.5 rounded-md px-2 py-1 hover:bg-surface-2"
                            onMouseEnter={() =>
                              subs.length > 0 &&
                              onHoverGoals?.(subs.map((x) => x.id))
                            }
                            onMouseLeave={() => onHoverGoals?.(null)}
                          >
                            {multi && (
                              <button
                                className="shrink-0 text-[9px] text-ink-faint hover:text-ink"
                                title={unfolded ? 'fold the subgoal list' : 'name the subgoals'}
                                onClick={() =>
                                  setOpenRoutes((prev) => {
                                    const next = new Set(prev)
                                    if (next.has(s.id)) next.delete(s.id)
                                    else next.add(s.id)
                                    return next
                                  })
                                }
                              >
                                <span
                                  className={`inline-block transition-transform duration-150 ${unfolded ? 'rotate-90' : ''}`}
                                >
                                  ▸
                                </span>
                              </button>
                            )}
                            <button
                              className="min-w-0 flex-1 truncate text-left font-mono text-xs disabled:cursor-default"
                              disabled={!onSelectStrategy}
                              onClick={() => onSelectStrategy?.(s.id)}
                              title="open the route's record"
                            >
                              <span className="text-ink-faint">s{s.id}</span>
                              {subs.length === 1 && (
                                <span className="text-ink">
                                  {' '}· {goalLabel(subs[0].id, subs[0].slug)}
                                  {subs[0].reused && (
                                    <span className="text-ink-faint"> · reused</span>
                                  )}
                                </span>
                              )}
                              {multi && (
                                <span className="text-ink-dim">
                                  {minted > 0 && (
                                    <>
                                      {' '}· {minted} subgoal{minted === 1 ? '' : 's'}
                                    </>
                                  )}
                                  {cited > 0 && (
                                    <span className="text-ink-faint"> · {cited} reused</span>
                                  )}
                                </span>
                              )}
                              {subs.length === 0 && (
                                <span className="text-ink-dim">
                                  {' '}· {s.subgoal_count} subgoal
                                  {s.subgoal_count === 1 ? '' : 's'}
                                </span>
                              )}
                            </button>
                            <span className={`shrink-0 text-[11px] ${statusCls}`}>
                              {strategyStatusLabel(s.status)}
                            </span>
                          </div>
                          {multi && unfolded && (
                            <div className="mb-1 ml-6 flex flex-col gap-0.5">
                              {subs.map((x) => (
                                <button
                                  key={x.id}
                                  className="truncate rounded-md px-2 py-0.5 text-left font-mono text-[11px] text-ink-dim hover:bg-surface-2 hover:text-ink"
                                  onMouseEnter={() => onHoverGoals?.([x.id])}
                                  onMouseLeave={() => onHoverGoals?.(null)}
                                  onClick={() => onSelectGoal?.(x.id)}
                                  title={
                                    x.reused
                                      ? 'this route reaches for a goal that already existed — it did not create it'
                                      : 'open this subgoal'
                                  }
                                >
                                  {goalLabel(x.id, x.slug)}
                                  {x.reused && (
                                    <span className="text-ink-faint"> · reused</span>
                                  )}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                </div>
              </>
            )}
            {data.status !== 'proved' && data.dead_attempts.length > 0 && (
              <>
                <SectionLabel>failed attempts ({data.dead_attempts.length})</SectionLabel>
                <div className="flex flex-col gap-1.5">
                  {data.dead_attempts.map((a) => (
                    <Attempt key={a.id} a={a} />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
      {/* the act (§1.4-2: "點擊星星後可下達相關命令"). It sits below the
          reading, in a strip of its own: acting on a goal must be
          reachable without scrolling past thirty dead attempts, and it
          must not compete with the statement for the first glance. */}
      {data &&
        (acting ? (
          <GoalCommandSheet
            problem={problem}
            goalId={data.id}
            slug={data.slug}
            onClose={() => setActing(false)}
          />
        ) : (
          <div className="shrink-0 border-t border-edge px-4 py-2">
            <button
              className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
              onClick={() => setActing(true)}
              title="park it, mark it delivered, hand it a proof, or hand it to a new group"
            >
              act on this goal…
            </button>
          </div>
        ))}
    </div>
  )
}
