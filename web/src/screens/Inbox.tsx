import { useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { relTime } from '../lib/format'
import { EmptyState, ErrorState, SectionLabel } from '../components/ui'
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

  return (
    <div className="rounded-lg border border-danger/30 bg-surface p-4">
      <div className="mb-1 flex items-center justify-between">
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
        <span className="text-[11px] text-ink-faint">{relTime(a.created_at)}</span>
      </div>
      <p className="mb-1 text-sm text-ink">{a.question}</p>
      {a.reason && <p className="mb-3 text-xs text-ink-dim">{a.reason}</p>}

      {editing ? (
        <textarea
          className="mb-3 h-72 w-full resize-y rounded-md border border-edge bg-bg p-3 font-mono text-xs text-ink focus:border-accent focus:outline-none"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          spellCheck={false}
        />
      ) : (
        <div className="mb-3">
          <DiffView left={a.current_body} right={a.proposed_body} />
        </div>
      )}

      {error && <div className="mb-2 text-xs text-danger">{error}</div>}

      <div className="flex items-center gap-2">
        <button
          className="rounded-md bg-ok/20 px-3 py-1.5 text-xs font-medium text-ok hover:bg-ok/30 disabled:opacity-50"
          disabled={busy}
          onClick={() => void resolve('accept')}
        >
          {editing ? 'Accept with edits' : 'Accept proposed'}
        </button>
        <button
          className="rounded-md border border-edge px-3 py-1.5 text-xs text-ink-dim hover:text-ink disabled:opacity-50"
          disabled={busy}
          onClick={() => {
            setEditing((v) => !v)
            setBody(a.proposed_body)
          }}
        >
          {editing ? 'Back to diff' : 'Edit before accepting'}
        </button>
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
          <button
            className="rounded-md border border-danger/40 px-3 py-1.5 text-xs text-danger hover:bg-danger/10 disabled:opacity-50"
            disabled={busy}
            onClick={() => (rejecting ? void resolve('reject') : setRejecting(true))}
          >
            {rejecting ? 'Confirm reject' : 'Reject'}
          </button>
        </div>
      </div>
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
        <button
          className="rounded-md bg-star/20 px-3 py-1.5 text-xs font-medium text-star hover:bg-star/30 disabled:opacity-50"
          disabled={busy}
          onClick={() => void act('approve')}
        >
          Approve — harvest to Library
        </button>
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
          <button
            className="rounded-md border border-danger/40 px-3 py-1.5 text-xs text-danger hover:bg-danger/10 disabled:opacity-50"
            disabled={busy}
            onClick={() => (rejecting ? void act('reject') : setRejecting(true))}
          >
            {rejecting ? 'Confirm reject' : 'Reject — keep proving'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Inbox() {
  const { data, error, loading, refresh } = usePoll<InboxResponse>('/api/inbox', 3000)

  if (loading) return <div className="p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  if (!data) return null

  const empty = data.amends.length === 0 && data.signoffs.length === 0

  return (
    <div className="mx-auto max-w-4xl px-6 py-6">
      <h1 className="mb-4 text-lg font-semibold">Inbox</h1>
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
