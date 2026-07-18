import { useMemo, useState } from 'react'
import { apiGet, apiPost, usePoll } from '../lib/api'
import { Lean } from '../lib/lean'
import { SectionLabel } from './ui'
import type {
  Goal,
  ProblemDetail,
  ReviewDeliverable,
  ReviewEntry,
  ReviewResponse,
} from '../lib/types'
import { relTime } from '../lib/format'

/** Ingest sign-off review: the anchor closure of each deliverable,
 * rendered as an expandable tree (charter §3.2). Data = the Ingest-time
 * snapshot; GET never touches the gateway. */

const PAPER_RE = /^paper: (.*?)\s+\(Papers\/(.+?)\/text\.md\)$/

/** snapshot anchor/claim entries: bare names or {name, kind, module}
 * records (the recompute path emits records — live-run catch) */
function entryName(e: ReviewEntry): string {
  return typeof e === 'string' ? e : String(e?.name ?? '')
}

function entrySignature(e: ReviewEntry): string | null {
  return typeof e === 'string' ? null : (e?.signature ?? null)
}

function PaperPane({ pid, anchor }: { pid: string; anchor: string }) {
  const { data, error } = usePoll<{ found: boolean; content: string }>(
    `/api/papers/${encodeURIComponent(pid)}/section?anchor=${encodeURIComponent(anchor)}`,
    60000,
  )
  if (error) return <div className="text-xs text-ink-faint">Paper text unavailable: {error.message}</div>
  if (!data) return <div className="text-xs text-ink-faint">Loading paper…</div>
  return (
    <div className="rounded-lg border border-edge bg-bg p-3">
      {!data.found && (
        <div className="mb-1 text-[11px] text-warn">
          anchor not found — showing the document head for orientation
        </div>
      )}
      <pre className="max-h-72 overflow-auto text-[11px] leading-relaxed whitespace-pre-wrap text-ink-dim">
        {data.content}
      </pre>
    </div>
  )
}

/** One vouchable decl with its actual mathematics — signing off means
 * reading the statement, not recognizing a name (anchor+claim §1).
 * `signature` (the declaration header, server-extracted) is the
 * readable truth; goal.statement is the fallback (for defs it's just
 * the target sort — worthless to a reader). */
function VouchRow({
  name,
  goal,
  signature,
  claim,
}: {
  name: string
  goal: Goal | null
  signature?: string | null
  claim?: boolean
}) {
  const text = signature ?? goal?.statement ?? null
  return (
    <div className="mb-1.5">
      <div className="flex items-baseline gap-2">
        <span
          className={`rounded-md px-1.5 py-0.5 font-mono text-[11px] ${
            claim ? 'bg-star/10 text-star' : 'bg-surface-2 text-ink-dim'
          }`}
        >
          {name}
        </span>
        {goal && <span className="text-[10px] text-ink-faint">{goal.kind}</span>}
      </div>
      {text && (
        <pre className="mt-1 ml-1 border-l border-edge pl-2 font-mono text-[11px] leading-snug break-words whitespace-pre-wrap text-ink-dim">
          <Lean code={text} />
        </pre>
      )}
    </div>
  )
}

function Deliverable({
  d,
  resolve,
  onRejected,
}: {
  d: ReviewDeliverable
  resolve: (name: string) => Goal | null
  onRejected?: () => void
}) {
  const [open, setOpen] = useState(false)
  const [showPaper, setShowPaper] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const paper = d.paper ? PAPER_RE.exec(d.paper) : null

  const reject = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiPost(`/api/problems/${encodeURIComponent(d.problem)}/reject-decl`, {
        decl: d.fq,
        reason: reason || undefined,
      })
      onRejected?.()
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="rounded-lg border border-edge">
      <button
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-surface-2"
        onClick={() => setOpen((v) => !v)}
      >
        <span className={d.ok ? 'text-ok' : 'text-danger'}>{d.ok ? '✓' : '✗'}</span>
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-ink">{d.fq}</span>
        {/* signing a negation must read as signing a negation — the
            requested claim was settled FALSE, this is its refutation */}
        {resolve(d.fq)?.disproof_of && (
          <span
            className="text-[11px] whitespace-nowrap text-warn"
            title={`the negation of ${resolve(d.fq)!.disproof_of!.slug} — the kernel settled the requested claim as false`}
          >
            disproof of {resolve(d.fq)!.disproof_of!.slug}
          </span>
        )}
        <span className="text-[11px] whitespace-nowrap text-ink-faint">
          {d.kind}
          {d.anchors.length > 0 && ` · ${d.anchors.length} anchors`}
          {d.folded > 0 && ` · ${d.folded} folded`}
        </span>
      </button>
      {/* the statement is the thing being vouched for — it reads
          WITHOUT a click (owner: put what must be read on the sheet) */}
      {(d.signature ?? resolve(d.fq)?.statement) && (
        <pre className="border-t border-edge/60 px-3 py-2 font-mono text-[11px] leading-snug break-words whitespace-pre-wrap text-ink-dim">
          <Lean code={(d.signature ?? resolve(d.fq)?.statement) as string} />
        </pre>
      )}
      {open && (
        <div className="border-t border-edge px-3 py-2">
          {d.error && <div className="mb-2 text-xs text-danger">{d.error}</div>}
          {error && <div className="mb-2 text-xs text-danger">{error}</div>}
          <div className="mb-2 flex items-center justify-end gap-2">
            {rejecting && (
              <input
                className="w-56 rounded-lg border border-edge bg-bg px-2 py-1 text-[11px] text-ink focus:border-danger focus:outline-none"
                placeholder="why is this wrong?"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                autoFocus
              />
            )}
            <button
              className="rounded-lg border border-danger/40 px-2 py-1 text-[11px] text-danger transition-colors hover:bg-danger/10 disabled:opacity-50"
              disabled={busy}
              title="Kill this claim + everything whose meaning depends on it (slow — recomputes closures)"
              onClick={() => (rejecting ? void reject() : setRejecting(true))}
            >
              {busy ? 'rejecting…' : rejecting ? 'confirm reject' : 'reject this claim'}
            </button>
          </div>
          {d.paper && (
            <div className="mb-2">
              <div className="flex items-center gap-2 text-[11px] text-ink-dim">
                <span className="text-star">◈</span>
                {d.paper}
                {paper && (
                  <button
                    className="rounded-md border border-edge px-1.5 py-0.5 text-[11px] text-ink-dim hover:text-ink"
                    onClick={() => setShowPaper((v) => !v)}
                  >
                    {showPaper ? 'hide paper' : 'view paper'}
                  </button>
                )}
              </div>
              {showPaper && paper && (
                <div className="mt-2">
                  <PaperPane pid={paper[2]} anchor={paper[1]} />
                </div>
              )}
            </div>
          )}
          {d.claims.length > 0 && (
            <>
              <SectionLabel>claims — what is asserted</SectionLabel>
              <div className="mb-2">
                {d.claims.map((c) => (
                  <VouchRow
                    key={entryName(c)}
                    name={entryName(c)}
                    goal={resolve(entryName(c))}
                    signature={entrySignature(c)}
                    claim
                  />
                ))}
              </div>
            </>
          )}
          {d.anchors.length > 0 && (
            <>
              <SectionLabel>anchors — what the statement stands on</SectionLabel>
              <div>
                {d.anchors.map((a) => (
                  <VouchRow
                    key={entryName(a)}
                    name={entryName(a)}
                    goal={resolve(entryName(a))}
                    signature={entrySignature(a)}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function RefreshButton({ problem, onDone }: { problem: string; onDone: () => void }) {
  const [state, setState] = useState<'idle' | 'running' | 'failed'>('idle')
  const start = async () => {
    setState('running')
    try {
      await apiPost(`/api/problems/${encodeURIComponent(problem)}/review/refresh`)
      const poll = async (): Promise<void> => {
        const j = await apiGet<{ state: string }>(
          `/api/problems/${encodeURIComponent(problem)}/review/refresh`,
        )
        if (j.state === 'running') {
          await new Promise((r) => setTimeout(r, 2000))
          return poll()
        }
        setState(j.state === 'done' ? 'idle' : 'failed')
        if (j.state === 'done') onDone()
      }
      await poll()
    } catch {
      setState('failed')
    }
  }
  return (
    <button
      className="rounded-md border border-edge px-1.5 py-0.5 text-[11px] text-ink-dim hover:text-ink disabled:opacity-50"
      disabled={state === 'running'}
      onClick={() => void start()}
      title="Recompute the closure live (warms the Lean gateway — slow)"
    >
      {state === 'running' ? 'recomputing…' : state === 'failed' ? 'recompute (failed — retry)' : 'recompute'}
    </button>
  )
}

export default function ReviewTree({ problem }: { problem: string }) {
  const { data, error, loading, refresh } = usePoll<ReviewResponse>(
    `/api/problems/${encodeURIComponent(problem)}/review`,
    30000,
  )
  // statements for the vouch sheet — anchors/claims are named in the
  // snapshot, but reading the mathematics is the whole point of review
  const { data: detail } = usePoll<ProblemDetail>(
    `/api/problems/${encodeURIComponent(problem)}`,
    30000,
  )
  const bySlug = useMemo(
    () => new Map((detail?.goals ?? []).map((g) => [g.slug, g])),
    [detail],
  )
  const resolve = (name: string) => bySlug.get(name.split('.').pop() ?? name) ?? null
  if (loading) return <div className="text-xs text-ink-faint">Loading review…</div>
  if (error && !data)
    return (
      <div className="flex items-center gap-2 text-xs text-warn">
        No stored review snapshot — recompute it live:
        <RefreshButton problem={problem} onDone={refresh} />
      </div>
    )
  if (!data) return null
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2 text-[11px] text-ink-faint">
        snapshot {relTime(data.stored_at)} · {data.union_count} distinct anchor names
        <RefreshButton problem={problem} onDone={refresh} />
      </div>
      {data.deliverables.map((d) => (
        <Deliverable key={d.fq} d={d} resolve={resolve} onRejected={refresh} />
      ))}
    </div>
  )
}
