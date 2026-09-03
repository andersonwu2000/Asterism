import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api'
import type { RevisionVerdict } from '../lib/types'

/*
 * The judge's ruling on ONE revision, opened from its Timeline row.
 *
 * Everything here became readable on 2026-08-29 (judge calibration
 * survey, knives 0+1). Before it, a killed proposal's verdict column
 * was hard-coded NULL — so the one row a reader most wants to open,
 * "why was this one thrown away", was the one row with nothing in it —
 * and four of the five criteria accepted the bare word `clear`, so
 * "why did this pass" had no answer on the record either. The survey
 * measured 70-94% bare clears on the unforced criteria.
 *
 * Why here and not on the Programme page: the owner cleared a
 * revision's own vital signs off the reading surface on 2026-08-07 —
 * "a reader of the STANDING argument does not read its provenance" —
 * and history lives where history lives. The Timeline already draws a
 * row per revision and already opens it; this fills an expansion that
 * had a link and a round count in it.
 *
 * Fetched when the row opens, never on the 15s poll: union_closed's
 * last hundred revisions carry 152 KB of verdict.
 */

/** Only a FIRED criterion says so. Clearing is the settled norm and
 * earns no ink (DESIGN.md — subtraction outranks addition, never draw
 * the same fact twice): on a verdict that passed, a column reading
 * "cleared" five times restates what the row's own verb already says.
 * `fired` lands exactly where the reader is going. A criterion the
 * judge left unmarked says THAT, because a silent criterion is the one
 * thing here nobody should have to guess about. */
const STATE_WORD: Record<string, string> = {
  clear: '',
  fired: 'fired',
  '': 'unmarked',
}

function Criterion({ c }: { c: RevisionVerdict['criteria'][number] }) {
  const fired = c.state === 'fired'
  return (
    <div
      className="grid grid-cols-[9.5rem_2.6rem_1fr] items-baseline gap-2 py-[3px]"
      data-criterion={c.key}
      data-state={c.state || 'unmarked'}
      data-bullets={c.bullets.length}
    >
      <span
        className={`min-w-0 truncate text-[11px] ${
          fired ? 'text-ink-dim' : 'text-ink-faint'
        }`}
        title={c.name ? `criterion ${c.key}` : undefined}
      >
        <span className="tnum text-ink-faint">{c.key}</span>{' '}
        {c.name ?? 'criterion'}
      </span>
      <span
        className={`text-[11px] ${fired ? 'text-ink' : 'text-ink-faint'}`}
      >
        {STATE_WORD[c.state] ?? c.state}
      </span>
      <span className={`text-[12px] ${fired ? 'text-ink-dim' : 'text-ink-faint'}`}>
        {c.bullets.length === 0 ? (
          // a bare `clear` is refused as of 2026-08-29; the ones already
          // on the record stay silent, and the page shows the silence
          // rather than inventing a reason
          <span className="text-ink-faint/60">— no reason recorded</span>
        ) : (
          /* one bullet per objection: a judge that sees three defects
             under one criterion fires all three in this round, and
             showing only the first is how the old one-string schema
             hid ~22% of objections for a round (owner, 2026-08-28) */
          c.bullets.map((b, i) => (
            <span key={i} className="block leading-snug" data-bullet={i}>
              {c.bullets.length > 1 && (
                <span className="mr-1 text-ink-faint" aria-hidden>
                  ·
                </span>
              )}
              {b}
            </span>
          ))
        )}
      </span>
    </div>
  )
}

function Seat({ judge }: { judge: RevisionVerdict['judge'] }) {
  // The seat comparison used to need yaml archaeology plus date-slicing
  // (survey P1/P2). It is the CONFIGURED seat — a rescue swap inside
  // the provider layer never reached this stamp.
  //
  // `rubric_sha` is deliberately not shown: it hashes the RENDERED
  // prompt, which carries a per-round dossier manifest (which files
  // exist, how many entries the proofs dir holds), so it changes every
  // round without the rubric changing. Measured 2026-08-29: five
  // consecutive verdicts under one unedited rubric, five different
  // hashes. A version stamp that never repeats identifies nothing.
  const bits = [judge?.provider, judge?.model, judge?.effort].filter(Boolean)
  return (
    <div className="mb-1.5 text-[11px] text-ink-faint">
      {bits.length > 0 ? (
        <>
          judged by <span className="text-ink-dim">{bits.join(' · ')}</span>
        </>
      ) : (
        // every verdict written before 2026-08-28 predates the stamp
        <span title="this verdict predates the seat stamp (2026-08-28)">
          seat not recorded
        </span>
      )}
    </div>
  )
}

/** The verdict itself, drawn — no fetching.
 *
 * The revision history (HID §1.4-2) already HOLDS the verdict it wants
 * to draw: the revision read carries it, and a second request for the
 * same JSON would be the console asking twice for one fact. Two
 * renderers for one object is the drift this extraction prevents. */
export function VerdictBody({ v }: { v: RevisionVerdict | null }) {
  if (v === null || (v.criteria.length === 0 && v.reservations.length === 0))
    return (
      <div className="mt-1.5 text-[11px] text-ink-faint" data-verdict="none">
        {/* pre-2026-08-29 rejections: the column was hard-coded NULL and
            the ruling is gone for good */}
        no verdict on record
      </div>
    )
  return (
    <div className="mt-2 border-t border-edge pt-2" data-verdict="read">
      <Seat judge={v.judge} />
      {v.criteria.map((c) => (
        <Criterion key={c.key} c={c} />
      ))}
      {v.reservations.length > 0 && (
        <div className="mt-2">
          <div className="mb-0.5 text-[11px] tracking-wider text-ink-faint uppercase">
            reservations — fired nothing, passed to the next wake
          </div>
          <ul className="space-y-0.5 pl-4 text-[12px] text-ink-faint">
            {v.reservations.map((r, i) => (
              <li key={i} className="list-disc marker:text-ink-faint">
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
      {/* the ruling explains an adversary kill; anything else killed it
          for a reason the criteria do not carry, and that IS the news */}
      {v.status === 'rejected' && v.ruling !== 'rebut' && v.discard_reason && (
        <div className="mt-2 text-[11px] text-ink-dim">
          discarded — {v.discard_reason}
        </div>
      )}
    </div>
  )
}

export default function JudgeVerdict({
  problem,
  revId,
}: {
  problem: string
  revId: number
}) {
  const [v, setV] = useState<RevisionVerdict | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    setV(null)
    setErr(null)
    apiGet<RevisionVerdict>(
      `/api/problems/${encodeURIComponent(problem)}/programme/verdict/${revId}`,
    )
      .then((r) => live && setV(r))
      .catch((e) => live && setErr(e instanceof Error ? e.message : 'unreadable'))
    return () => {
      live = false
    }
  }, [problem, revId])

  if (err !== null)
    return (
      <div className="mt-1.5 text-[11px] text-ink-faint" data-verdict="none">
        no verdict on record
      </div>
    )
  if (v === null)
    return (
      <div className="mt-1.5 text-[11px] text-ink-faint" data-verdict="loading">
        …
      </div>
    )
  return <VerdictBody v={v} />
}
