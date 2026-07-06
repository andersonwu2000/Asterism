import { useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { relTime } from '../lib/format'
import { Button, EmptyState, ErrorState, SectionLabel } from '../components/ui'
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

  // Decision-first anatomy (design review): headline = the short ask
  // (reason when present — it's the strategist's TL;DR), actions above
  // the fold, the long reasoning wall collapsed, diff = changed hunks.
  const longQuestion = a.question.length > 280
  const headline = a.reason || (longQuestion ? `Amend ${a.file} — decision needed` : a.question)
  const [showReasoning, setShowReasoning] = useState(!longQuestion && !a.reason)

  return (
    <div className="rounded-lg border border-warn/40 bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link
            to={`/problems/${encodeURIComponent(a.problem)}`}
            className="font-mono text-sm text-ink hover:underline"
          >
            {a.problem}
          </Link>
          <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-dim">
            {a.file}
          </span>
        </div>
        {(() => {
          const days = Math.floor((Date.now() - Date.parse(a.created_at)) / 86400_000)
          return days >= 2 ? (
            <span className="rounded-full bg-warn/15 px-2 py-0.5 text-[11px] font-semibold text-warn">
              waiting {days} days
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
              className="w-64 rounded-md border border-edge bg-bg px-2 py-1.5 text-xs text-ink focus:border-danger focus:outline-none"
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
      {/* the highest-stakes click states its consequence — one line */}
      <div className="mb-3 truncate text-[11px] text-ink-faint">
        Either choice unpauses the problem — Accept writes the file, Reject keeps it and your
        reason guides the re-plan.
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
        <div className="mb-3 max-w-[75ch] rounded-md border border-edge bg-bg px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap text-ink-dim">
          {a.question}
        </div>
      )}

      {editing ? (
        <textarea
          className="h-72 w-full resize-y rounded-md border border-edge bg-bg p-3 font-mono text-xs text-ink focus:border-accent focus:outline-none"
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
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const act = async (action: 'approve' | 'reject') => {
    setBusy(true)
    setError(null)
    try {
      if (action === 'approve') {
        await apiPost(`/api/problems/${encodeURIComponent(s.problem)}/approve-ingest`)
      } else {
        await apiPost(`/api/problems/${encodeURIComponent(s.problem)}/reject-ingest`, {
          reason: reason || undefined,
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
    <div className="rounded-lg border border-warn/30 bg-surface p-4">
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
      <div className="flex items-center gap-2">
        <Button variant="star" disabled={busy} onClick={() => void act('approve')}>
          Approve — harvest to Library
        </Button>
        <div className="ml-auto flex items-center gap-2">
          {rejecting && (
            <input
              className="w-64 rounded-md border border-edge bg-bg px-2 py-1.5 text-xs text-ink focus:border-danger focus:outline-none"
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

export default function Inbox() {
  const { data, error, loading, refresh } = usePoll<InboxResponse>('/api/inbox', 3000)

  if (loading) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  if (!data) return null

  const empty = data.amends.length === 0 && data.signoffs.length === 0

  return (
    <div className="mx-auto max-w-4xl px-6 py-6">
      <div className="mb-4 flex items-baseline gap-3">
        <h1 className="font-display text-[22px] font-medium text-ink">Inbox</h1>
        {!empty && (
          <span className="tnum text-xs text-ink-faint">
            {data.amends.length + data.signoffs.length} waiting on you
          </span>
        )}
      </div>
      {empty ? (
        <EmptyState title="Nothing needs you right now">
          Amend requests and ingest sign-offs land here when the engine needs a human decision.
        </EmptyState>
      ) : (
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
      )}
    </div>
  )
}
