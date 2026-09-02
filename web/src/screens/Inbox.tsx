import { useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { relTime } from '../lib/format'
import { renderProse } from '../lib/prose'
import { Button, SectionLabel } from '../components/ui'
import DiffView from '../components/DiffView'
import ReviewTree from '../components/ReviewTree'
import type { Amend, InboxResponse, Signoff } from '../lib/types'

/** The human decision inbox (charter §3.2): amend requests with a
 * side-by-side diff, and paused ingest sign-offs with the anchor
 * closure. Every action posts to a CLI/state chokepoint. */

function AmendCard({ a, onDone }: { a: Amend; onDone: () => void }) {
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(a.proposed_body)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const resolve = async (action: 'accept' | 'reject') => {
    setBusy(true)
    setError(null)
    try {
      await apiPost(`/api/inbox/amend/${a.id}/resolve`, {
        action,
        body: action === 'accept' && editing ? body : undefined,
        reason: action === 'reject' ? reason || undefined : undefined,
      })
      onDone()
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  // What is being amended. Two of the three targets are files; the
  // third is the problem's GOAL, which stopped being a file in v40 —
  // naming a DB value "Manifest.md" would send the reader to a path
  // that no longer exists.
  const isGoal = a.file === 'charter'
  const target = isGoal ? 'the goal' : a.file

  // Decision-first anatomy (design review): headline = the short ask
  // (reason when present — it's the strategist's TL;DR), actions above
  // the fold, the long reasoning wall collapsed, diff = changed hunks.
  const longQuestion = a.question.length > 280
  const headline = a.reason || (longQuestion ? `Amend ${target} — decision needed` : a.question)
  const [showReasoning, setShowReasoning] = useState(!longQuestion && !a.reason)

  return (
    <div className="rounded-xl border border-warn/40 bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link
            to={`/problems/${encodeURIComponent(a.problem)}`}
            className="font-mono text-sm text-ink hover:underline"
          >
            {a.problem}
          </Link>
          <span
            className={`rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] text-ink-dim ${
              isGoal ? '' : 'font-mono'
            }`}
            title={
              isGoal
                ? "engine term: charter — the problem's goal, which lives in the engine, not in a file"
                : undefined
            }
          >
            {target}
          </span>
        </div>
        {(() => {
          const days = Math.floor((Date.now() - Date.parse(a.created_at)) / 86400_000)
          return days >= 2 ? (
            <span className="rounded-full bg-warn/15 px-2 py-0.5 text-[11px] font-semibold text-warn">
              waiting {days}d
            </span>
          ) : (
            <span className="text-[11px] text-ink-faint">{relTime(a.created_at)}</span>
          )
        })()}
      </div>

      <p className="font-display mb-3 max-w-[62ch] text-[19px] leading-snug font-normal text-ink">
        {headline}
      </p>

      {error && <div className="mb-2 text-xs text-danger">{error}</div>}

      <div className="mb-3 flex items-center gap-2">
        <Button variant="ok" disabled={busy} onClick={() => void resolve('accept')}>
          {editing ? 'Accept with edits' : 'Accept proposed'}
        </Button>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => {
            setEditing((v) => !v)
            setBody(a.proposed_body)
          }}
        >
          {editing ? 'Back to diff' : 'Edit before accepting'}
        </Button>
        <div className="ml-auto flex items-center gap-2">
          {rejecting && (
            <input
              className="w-64 rounded-lg border border-edge bg-bg px-2 py-1.5 text-xs text-ink focus:border-danger focus:outline-none"
              placeholder="why? (guides the Strategist)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              autoFocus
            />
          )}
          <Button
            variant="danger"
            disabled={busy}
            onClick={() => (rejecting ? void resolve('reject') : setRejecting(true))}
          >
            {rejecting ? 'Confirm reject' : 'Reject'}
          </Button>
        </div>
      </div>
      {/* the highest-stakes click states its consequence — one line.
          "Either choice" misled next to THREE buttons (cold-eye): Edit
          is a mode toggle, not a resolution — name the two that are. */}
      <div className="mb-3 truncate text-[11px] text-ink-faint">
        Accept {isGoal ? 'replaces the goal' : 'writes the file'} (with your edits, if any);
        Reject keeps {isGoal ? 'the current one' : 'it'} and asks you why — either resolution
        unpauses the problem.
      </div>

      {(longQuestion || a.reason) && (
        <button
          className="mb-2 text-xs text-ink-dim transition-colors hover:text-ink"
          onClick={() => setShowReasoning((v) => !v)}
        >
          {showReasoning ? '▾ hide' : '▸ show'} the strategist's full reasoning
        </button>
      )}
      {showReasoning && (longQuestion || a.reason) && (
        <div className="mb-3 max-w-[75ch] rounded-lg border border-edge bg-bg px-3 py-2 text-[13px] leading-relaxed text-ink-dim">
          {/* strategist-authored markdown — the shared prose engine
              joins its hard-wrapped lines and renders lists/code */}
          {renderProse(a.question)}
        </div>
      )}

      {editing ? (
        <textarea
          className="h-72 w-full resize-y rounded-lg border border-edge bg-bg p-3 font-mono text-xs text-ink focus:border-accent focus:outline-none"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          spellCheck={false}
        />
      ) : (
        <DiffView left={a.current_body} right={a.proposed_body} />
      )}
    </div>
  )
}

function SignoffCard({ s, onDone }: { s: Signoff; onDone: () => void }) {
  const [rejecting, setRejecting] = useState(false)
  const [confirmingHarvest, setConfirmingHarvest] = useState(false)
  const [reason, setReason] = useState('')
  // the signature's displayed name — the operator's claim, remembered
  // per browser; the record's evidence half (Claude login, OS user,
  // host, content seal) is captured server-side and never typed
  const [signer, setSigner] = useState(
    () => localStorage.getItem('asterism.signer') ?? '',
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const signed = signer.trim().length > 0

  // the Library decision is made HERE, statements in hand — approving
  // carries it (owner: a human signs; nothing is harvested by default)
  const act = async (action: 'harvest' | 'archive' | 'reject') => {
    setBusy(true)
    setError(null)
    try {
      if (action === 'reject') {
        await apiPost(`/api/problems/${encodeURIComponent(s.problem)}/reject-ingest`, {
          reason: reason || undefined,
        })
      } else {
        localStorage.setItem('asterism.signer', signer.trim())
        await apiPost(`/api/problems/${encodeURIComponent(s.problem)}/approve-ingest`, {
          library: action === 'harvest',
          signer: signer.trim(),
        })
      }
      onDone()
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-xl border border-warn/30 bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <Link
          to={`/problems/${encodeURIComponent(s.problem)}`}
          className="font-mono text-sm text-ink hover:underline"
        >
          {s.problem}
        </Link>
        <span className="text-[11px] text-ink-faint">
          ingest judged {relTime(s.ingested_at)}
        </span>
      </div>
      <div className="mb-3">
        <ReviewTree problem={s.problem} />
      </div>
      {error && <div className="mb-2 text-xs text-danger">{error}</div>}
      {/* signing ceremony — the affirmative twin of delete's
          type-the-name: approving puts YOUR name on the record */}
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[11px] tracking-widest text-ink-faint uppercase">
          signed off by
        </span>
        <input
          className="w-56 rounded-lg border border-edge bg-bg px-2 py-1 text-xs text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
          placeholder="your name — signs the approval"
          value={signer}
          onChange={(e) => setSigner(e.target.value)}
          spellCheck={false}
        />
        <span
          className="text-[11px] text-ink-faint"
          title="recorded with the signature, captured by the machine (not typed): the Claude account logged in right now, OS user, host, and a hash sealing exactly what you reviewed"
        >
          + machine evidence
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="star"
          disabled={busy || !signed}
          onClick={() =>
            confirmingHarvest ? void act('harvest') : setConfirmingHarvest(true)
          }
          title={
            !signed
              ? 'type your name above — the approval is signed'
              : confirmingHarvest
                ? 'approves and starts the harvest run right away'
                : undefined
          }
        >
          {confirmingHarvest ? 'Confirm — engine runs now' : 'Approve — harvest to Library'}
        </Button>
        {confirmingHarvest && (
          <span className="text-[11px] text-ink-faint">
            the engine starts harvesting immediately
          </span>
        )}
        <Button
          variant="outline"
          disabled={busy || !signed}
          onClick={() => {
            setConfirmingHarvest(false)
            void act('archive')
          }}
          title={
            !signed
              ? 'type your name above — the approval is signed'
              : 'accept the results but keep them out of the Library — the proofs stay archived with the problem'
          }
        >
          Approve — archive only
        </Button>
        <div className="ml-auto flex items-center gap-2">
          {rejecting && (
            <input
              className="w-64 rounded-lg border border-edge bg-bg px-2 py-1.5 text-xs text-ink focus:border-danger focus:outline-none"
              placeholder="what's still missing?"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              autoFocus
            />
          )}
          <Button
            variant="danger"
            disabled={busy}
            onClick={() => (rejecting ? void act('reject') : setRejecting(true))}
          >
            {rejecting ? 'Confirm reject' : 'Reject — keep proving'}
          </Button>
        </div>
      </div>
    </div>
  )
}

/** The decisions waiting on the human, scoped to one Project (§1.4:
 * a Project owns one inbox). It is not a destination of its own any
 * more — it rides at the top of that Project's shelf, where the tasks
 * it is about are, and it draws NOTHING when there is nothing to
 * decide (an empty state on a page you did not open is furniture). */
export default function Inbox({ project }: { project: string }) {
  const { data, refresh } = usePoll<InboxResponse>(
    `/api/inbox?project=${encodeURIComponent(project)}`,
    3000,
  )

  if (!data) return null
  const empty = data.amends.length === 0 && data.signoffs.length === 0
  if (empty) return null

  return (
    <section className="mb-7">
      <div className="mb-2 flex items-baseline gap-3">
        <span className="text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
          needs you
        </span>
        <span className="tnum text-[11px] text-ink-faint">
          {data.amends.length + data.signoffs.length} waiting
        </span>
      </div>
      <div className="flex flex-col gap-6">
          {data.amends.length > 0 && (
            <section>
              <SectionLabel>amend requests ({data.amends.length})</SectionLabel>
              <div className="flex flex-col gap-3">
                {data.amends.map((a) => (
                  <AmendCard key={a.id} a={a} onDone={refresh} />
                ))}
              </div>
            </section>
          )}
          {data.signoffs.length > 0 && (
            <section>
              <SectionLabel>ingest sign-offs ({data.signoffs.length})</SectionLabel>
              <div className="flex flex-col gap-3">
                {data.signoffs.map((s) => (
                  <SignoffCard key={s.problem} s={s} onDone={refresh} />
                ))}
              </div>
            </section>
          )}
      </div>
    </section>
  )
}
