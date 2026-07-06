import { useState } from 'react'
import { usePoll } from '../lib/api'
import { SectionLabel } from './ui'
import type { ReviewDeliverable, ReviewResponse } from '../lib/types'
import { relTime } from '../lib/format'

/** Ingest sign-off review: the anchor closure of each deliverable,
 * rendered as an expandable tree (charter §3.2). Data = the Ingest-time
 * snapshot; GET never touches the gateway. */

const PAPER_RE = /^paper: (.*?)\s+\(Papers\/(.+?)\/text\.md\)$/

function PaperPane({ pid, anchor }: { pid: string; anchor: string }) {
  const { data, error } = usePoll<{ found: boolean; content: string }>(
    `/api/papers/${encodeURIComponent(pid)}/section?anchor=${encodeURIComponent(anchor)}`,
    60000,
  )
  if (error) return <div className="text-xs text-ink-faint">Paper text unavailable: {error.message}</div>
  if (!data) return <div className="text-xs text-ink-faint">Loading paper…</div>
  return (
    <div className="rounded-md border border-edge bg-bg p-3">
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

function Deliverable({ d }: { d: ReviewDeliverable }) {
  const [open, setOpen] = useState(false)
  const [showPaper, setShowPaper] = useState(false)
  const paper = d.paper ? PAPER_RE.exec(d.paper) : null
  return (
    <div className="rounded-md border border-edge">
      <button
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-surface-2"
        onClick={() => setOpen((v) => !v)}
      >
        <span className={d.ok ? 'text-ok' : 'text-danger'}>{d.ok ? '✓' : '✗'}</span>
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-ink">{d.fq}</span>
        <span className="text-[11px] whitespace-nowrap text-ink-faint">
          {d.kind}
          {d.anchors.length > 0 && ` · ${d.anchors.length} anchors`}
          {d.folded > 0 && ` · ${d.folded} folded`}
        </span>
      </button>
      {open && (
        <div className="border-t border-edge px-3 py-2">
          {d.error && <div className="mb-2 text-xs text-danger">{d.error}</div>}
          {d.paper && (
            <div className="mb-2">
              <div className="flex items-center gap-2 text-[11px] text-ink-dim">
                <span className="text-star">◈</span>
                {d.paper}
                {paper && (
                  <button
                    className="rounded border border-edge px-1.5 py-0.5 text-[11px] text-ink-dim hover:text-ink"
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
          {d.anchors.length > 0 && (
            <>
              <SectionLabel>anchors vouched for</SectionLabel>
              <div className="mb-2 flex flex-wrap gap-1.5">
                {d.anchors.map((a) => (
                  <span key={a} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-dim">
                    {a}
                  </span>
                ))}
              </div>
            </>
          )}
          {d.claims.length > 0 && (
            <>
              <SectionLabel>claims</SectionLabel>
              <div className="flex flex-wrap gap-1.5">
                {d.claims.map((c) => (
                  <span key={c} className="rounded bg-star/10 px-1.5 py-0.5 font-mono text-[11px] text-star">
                    {c}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function ReviewTree({ problem }: { problem: string }) {
  const { data, error, loading } = usePoll<ReviewResponse>(
    `/api/problems/${encodeURIComponent(problem)}/review`,
    30000,
  )
  if (loading) return <div className="text-xs text-ink-faint">Loading review…</div>
  if (error && !data)
    return (
      <div className="text-xs text-warn">
        No stored review snapshot ({error.message}) — run <code>asterism review {problem}</code>{' '}
        in a terminal for a live closure.
      </div>
    )
  if (!data) return null
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[11px] text-ink-faint">
        snapshot {relTime(data.stored_at)} · {data.union_count} distinct anchor names
      </div>
      {data.deliverables.map((d) => (
        <Deliverable key={d.fq} d={d} />
      ))}
    </div>
  )
}
