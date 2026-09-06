import { useState } from 'react'
import { usePoll } from '../lib/api'
import { relTime } from '../lib/format'
import { renderProse } from '../lib/prose'
import { frameClass } from '../lib/textFrame'
import { VerdictBody } from './JudgeVerdict'
import type { DebateRound, RevisionDetail, RevisionRow } from '../lib/types'

/*
 * A group's decided history, and how each decision was argued
 * (human_interface_design.md §1.4-2: "提供 Programme 定案歷史和各定案
 * 下的辯論歷史").
 *
 * COLLAPSED by default, at every level, and read on demand at every
 * level. The standing argument is what the Groups screen is for — the
 * owner cleared a revision's provenance off that reading in 2026-08-07
 * — so history opens only when a reader asks for it, and a debate
 * carries every round's draft, which is kilobytes per round.
 *
 * Settled things RECEDE, they are never struck through (DESIGN.md): a
 * discarded proposal is faint, not crossed out. Calling a rejection a
 * retraction is what `line-through` would say.
 */

/** Both halves of one round: what the author put on the table, and what
 * the judge fired back at that body. The engine stores them paired
 * because they ARE a pair; the page draws them the same way. */
function Round({ r }: { r: DebateRound }) {
  const [open, setOpen] = useState(false)
  const fired = r.criteria.filter((c) => c.state === 'fired')
  return (
    <div className="border-t border-edge py-2 first:border-t-0">
      <div className="flex items-baseline gap-2">
        <span className="tnum shrink-0 text-[11px] text-ink-faint">
          round {r.round ?? '?'}
        </span>
        <span className="min-w-0 flex-1 truncate text-[11px] text-ink-dim">
          {r.criticisms[0] ?? (r.ruling ? `adversary — ${r.ruling}` : 'adversary')}
        </span>
        {r.proposal !== null && (
          <button
            className="shrink-0 cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
            onClick={() => setOpen((v) => !v)}
            title="the draft this round argued about"
          >
            {open ? 'hide the draft' : 'the draft'}
          </button>
        )}
      </div>
      {/* the strategist's half */}
      {open && r.proposal !== null && (
        <div className="mt-1.5 max-h-72 overflow-y-auto text-[12px] leading-relaxed text-ink-dim">
          {renderProse(r.proposal, { mode: 'document' })}
        </div>
      )}
      {/* …and the adversary's */}
      {r.criticisms.length > 0 && (
        <ul className="mt-1 space-y-0.5 pl-4 text-[12px] text-ink-dim">
          {r.criticisms.map((c, i) => (
            <li key={i} className="list-disc marker:text-ink-faint">
              {c}
            </li>
          ))}
        </ul>
      )}
      {fired.length > 0 && (
        <div className="mt-1 text-[11px] text-ink-faint">
          fired on {fired.map((c) => c.key).join(', ')}
        </div>
      )}
    </div>
  )
}

/**
 * ONE revision, read: what the judge said, and then what it said it
 * about.
 *
 * The criticism sits ABOVE the Programme text (owner, 2026-09-06). A
 * revision is opened to answer "why does the argument say this", and
 * the ruling is the answer; underneath a body that runs to a screen and
 * a half it was a footnote nobody reached. It is the same drawing
 * wherever a revision is read — inside the history list, and as the
 * Groups page's own reading when the address names one — because two
 * drawings of one object is exactly the drift this file's own header
 * warns about.
 *
 * `cap` bounds the body inside the LIST (a row that grows to a screen
 * and a half buries the rows under it) and is off where the revision IS
 * the reading.
 */
export function RevisionReading({
  problem,
  id,
  cap = false,
}: {
  problem: string
  id: number
  /** inside the list: hold the body to a readable window */
  cap?: boolean
}) {
  const [debate, setDebate] = useState(false)
  const { data, error } = usePoll<RevisionDetail>(
    `/api/problems/${encodeURIComponent(problem)}/programme/revisions/${id}`,
    0,
  )
  if (error) return <div className="py-2 text-[11px] text-warn">{error.message}</div>
  if (!data) return <div className="late-fade py-2 text-[11px] text-ink-faint">…</div>
  return (
    <>
      {data.discard_reason && (
        <div className="mb-2 text-[11px] text-ink-dim">
          discarded — {data.discard_reason}
        </div>
      )}
      {/* the ruling first — already in hand, so no second request for
          the same JSON */}
      <VerdictBody v={data.verdict} />
      <div
        className={`mt-3 text-[12.5px] leading-relaxed text-ink-dim ${
          cap ? 'max-h-[28rem] overflow-y-auto' : ''
        }`}
      >
        {renderProse(data.body, { mode: 'document' })}
      </div>
      {data.last_words && (
        <div className="mt-3">
          <div className="mb-1 text-[11px] tracking-wider text-ink-faint uppercase">
            the author's last words — its own record, unverified
          </div>
          <pre className={frameClass({ tone: 'faint' })}>{data.last_words}</pre>
        </div>
      )}
      {data.dialogue.length > 0 && (
        <div className="mt-3">
          <button
            className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
            onClick={() => setDebate((v) => !v)}
          >
            <span
              className={`mr-1 inline-block text-[9px] transition-transform duration-150 ${
                debate ? 'rotate-90' : ''
              }`}
              aria-hidden
            >
              ▸
            </span>
            the debate · {data.dialogue.length} round
            {data.dialogue.length === 1 ? '' : 's'}
          </button>
          {debate && (
            <div className="mt-1 rounded-xl border border-edge bg-wash px-3 py-1">
              {data.dialogue.map((r, i) => (
                <Round key={i} r={r} />
              ))}
            </div>
          )}
        </div>
      )}
    </>
  )
}

function Row({
  problem,
  r,
  open,
  onToggle,
}: {
  problem: string
  r: RevisionRow
  open: boolean
  onToggle: () => void
}) {
  const passed = r.status === 'passed'
  return (
    <div>
      <button
        className="flex w-full items-baseline gap-2 px-3 py-1 text-left transition-colors hover:bg-surface/60"
        onClick={onToggle}
        title={r.judge ? `judged by ${[r.judge.provider, r.judge.model, r.judge.effort].filter(Boolean).join(' · ')}` : 'seat not recorded'}
      >
        <span
          className={`mr-0.5 shrink-0 text-[9px] transition-transform duration-150 ${
            open ? 'rotate-90' : ''
          }`}
          aria-hidden
        >
          ▸
        </span>
        {/* settled things recede — a discarded proposal is faint, never
            struck through (DESIGN.md) */}
        <span className={`tnum shrink-0 text-[11px] ${passed ? 'text-ink' : 'text-ink-faint'}`}>
          rev {r.rev}
        </span>
        <span className={`shrink-0 text-[11px] ${passed ? 'text-ink-dim' : 'text-ink-faint'}`}>
          {passed ? 'passed' : 'discarded'}
        </span>
        <span className="tnum shrink-0 text-[11px] text-ink-faint">
          {r.rounds} round{r.rounds === 1 ? '' : 's'}
        </span>
        <span className="min-w-0 flex-1 truncate text-[11px] text-ink-faint">
          {r.discard_reason ?? ''}
        </span>
        <span className="tnum shrink-0 text-[11px] text-ink-faint">
          {relTime(r.created_at)}
        </span>
      </button>
      {open && (
        <div className="border-t border-edge px-3 py-2">
          <RevisionReading problem={problem} id={r.id} cap />
        </div>
      )}
    </div>
  )
}

/**
 * The chain, folded. It sits UNDER the reading now and opens on
 * request: a revision the address names is read where the argument is
 * read (owner, 2026-09-06), so nothing arrives here needing to be
 * unfolded for the reader — the list is an index, and an index the
 * page opens for you is a page that starts by hiding what you came for.
 */
export default function RevisionHistory({
  problem,
  group,
}: {
  problem: string
  /** whose chain — the group the screen is standing on. Chains never
   * interleave (v35), so this is not optional information. */
  group: number | null
}) {
  const [open, setOpen] = useState(false)
  const [openRev, setOpenRev] = useState<number | null>(null)
  // read ONCE when it opens (`intervalMs <= 0`), never on a poll: this
  // is history, and it changes when something happens, not every 15s
  const { data, error } = usePoll<{ revisions: RevisionRow[] }>(
    open
      ? `/api/problems/${encodeURIComponent(problem)}/programme/revisions` +
          (group !== null ? `?group=${group}` : '')
      : null,
    0,
  )
  const rows = data?.revisions ?? []
  return (
    <div className="mb-5">
      <button
        className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
        onClick={() => setOpen((v) => !v)}
        title="every proposal this group decided, passed and discarded"
      >
        <span
          className={`mr-1 inline-block text-[9px] transition-transform duration-150 ${
            open ? 'rotate-90' : ''
          }`}
          aria-hidden
        >
          ▸
        </span>
        revision history
      </button>
      {open && (
        <div className="mt-1 rounded-xl border border-edge">
          {error && !data ? (
            <div className="px-3 py-2 text-[11px] text-warn">{error.message}</div>
          ) : data === null ? (
            <div className="late-fade px-3 py-2 text-[11px] text-ink-faint">…</div>
          ) : rows.length === 0 ? (
            <div className="px-3 py-2 text-[11px] text-ink-faint">
              nothing decided yet — the first passed proposal starts the chain.
            </div>
          ) : (
            rows.map((r) => (
              <Row
                key={r.id}
                problem={problem}
                r={r}
                open={openRev === r.id}
                onToggle={() => setOpenRev((cur) => (cur === r.id ? null : r.id))}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}
