import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, apiGet, apiPost } from '../lib/api'
import {
  RECEIPT_POLL_MS,
  affectedSummary,
  commandTitle,
  fieldFromDetail,
  newIdempotencyKey,
  receiptLine,
  receiptStart,
  receiptStep,
} from '../lib/commands'
import type { CommandKind, CommandPreview, CommandRow, Receipt } from '../lib/commands'
import { groupCode, relTime } from '../lib/format'
import { goalStatusLabel } from '../lib/vocab'
import { ConfirmWindow } from './ConfirmWindow'
import { Button } from './ui'

/*
 * THE confirmation window (human_interface_design.md §1.3, §1.4-2:
 * "執行命令的確認用現場彈窗，與手動命令共用同一確認元件").
 *
 * One component, every surface: a star's command sheet, a group's, the
 * engine room's kill, and the Assistant's prepared command all end
 * here. It is a live floating window and never an inbox item — the
 * owner's ruling — because a command is a decision taken WHILE looking
 * at the thing it acts on, and the preview it shows is only true of the
 * revision it was read at.
 *
 * It floats by DESIGN.md's own carve-out: this is a task of its own
 * (read a cascade, then decide), and the page behind it is what the
 * cascade is about. The chrome — the shape, the portal, Escape and
 * backdrop, where the focus lands — is `ConfirmWindow`'s, shared with
 * every other floating surface. This file is the command half only.
 *
 * What it does NOT do: validate. The engine's own validator answers
 * that, and a 422 goes back to the form that drew the box — two
 * validators for one command is how a console starts telling a person
 * something the engine does not believe.
 */

/* ------------------------------------------------------------------ */
/* starting a run over a list of tasks                                 */
/* ------------------------------------------------------------------ */

/** One ticked name, and what pressing Run would do to it. */
export interface RunPreviewRow {
  name: string
  found: boolean
  status: string | null
  benched: boolean
  effect: 'start' | 'running' | 'benched' | 'unknown'
}

export interface RunPreview {
  problems: RunPreviewRow[]
  start: string[]
  blocked: boolean
  daemon: { running: boolean; scope: string | null }
}

/** The engine's four answers, in the reader's words. */
const RUN_EFFECT: Record<RunPreviewRow['effect'], string> = {
  start: 'would be started',
  running: 'already running',
  benched: 'benched — the run would skip it',
  unknown: 'not a task on this shelf',
}

/** Starting a run, confirmed the way every other consequential act is.
 *
 * The shelf's Run button used to name the ticked tasks as a joined
 * string beside itself, which says who was ticked and nothing about
 * what would happen to them: a typo, a benched task and a task the
 * engine is already on all read the same. This asks the engine first
 * (§1.3's preview) and lists the answer one row per name.
 */
export function RunConfirm({
  project,
  problems,
  once,
  onClose,
  onStarted,
}: {
  project: string
  problems: string[]
  once?: boolean
  onClose: () => void
  /** the run is up — the shelf clears its ticks */
  onStarted: () => void
}) {
  const [preview, setPreview] = useState<RunPreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const key = problems.join('\n')

  useEffect(() => {
    let gone = false
    setPreview(null)
    setError(null)
    apiPost<RunPreview>('/api/daemon/start-many/preview', {
      problems: key === '' ? [] : key.split('\n'),
      project,
    })
      .then((p) => !gone && setPreview(p))
      .catch((e) => !gone && setError(String((e as Error).message)))
    return () => {
      gone = true
    }
  }, [project, key])

  const close = useCallback(() => {
    if (busy) return
    onClose()
  }, [busy, onClose])

  const start = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiPost('/api/daemon/start-many', { problems, once: once ?? false })
      onStarted()
      onClose()
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  const goes = preview?.start.length ?? 0
  return (
    <ConfirmWindow
      title="run these tasks"
      /* one task has a NAME; only a list needs counting. The task
         page's Run opens this same window over a list of one, and
         "1 ticked" there says nothing the reader did not just do. */
      subject={problems.length === 1 ? problems[0] : `${problems.length} ticked`}
      badge="start-many"
      badgeTitle="the engine's own name for this endpoint — an explicit list, never a pattern"
      onClose={close}
    >
      {preview === null && error === null && (
        <div className="late-fade mt-4 text-xs text-ink-faint">
          asking the engine what this would start…
        </div>
      )}
      {preview && (
        <>
          {preview.blocked && (
            <p className="mt-3 flex items-baseline gap-2 text-[12px] text-warn">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-warn" />
              the engine is already running
              {preview.daemon.scope ? ` on ${preview.daemon.scope}` : ''} — stop it before
              starting another run.
            </p>
          )}
          <div className="mt-3 max-h-56 overflow-y-auto rounded-xl border border-edge bg-wash">
            {preview.problems.map((p) => (
              <div key={p.name} className="flex items-baseline gap-2 px-2.5 py-1 text-[11px]">
                <span
                  className={`min-w-0 flex-1 truncate font-mono ${
                    p.effect === 'start' ? 'text-ink' : 'text-ink-faint'
                  }`}
                  title={p.name}
                >
                  {p.name}
                </span>
                <span className="shrink-0 text-ink-faint">{p.status ?? '—'}</span>
                <span
                  className={`shrink-0 ${
                    p.effect === 'unknown' || p.effect === 'benched'
                      ? 'text-warn'
                      : 'text-ink'
                  }`}
                >
                  → {RUN_EFFECT[p.effect]}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[12px] text-ink-dim">
            {goes === 0
              ? 'nothing here would start.'
              : `${goes} task${goes === 1 ? '' : 's'} would be started, as one run over an explicit list.`}
          </p>
        </>
      )}
      {error && <div className="mt-3 text-[12px] text-danger">{error}</div>}
      <div className="mt-5 flex items-center justify-end gap-2">
        <Button variant="outline" onClick={close} disabled={busy}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={preview === null || busy || preview.blocked || goes === 0}
          onClick={() => void start()}
          title="starts the engine on exactly these tasks — the run begins now"
        >
          {busy ? 'Starting…' : goes === 1 ? 'Confirm — run it' : `Confirm — run ${goes}`}
        </Button>
      </div>
    </ConfirmWindow>
  )
}

function Affected({ preview }: { preview: CommandPreview }) {
  if (preview.affected.length === 0) return null
  return (
    <div className="mt-3">
      <div className="mb-1.5 flex items-baseline gap-2">
        <span className="text-[11px] tracking-wider text-ink-faint uppercase">
          what closes
        </span>
        <span className="tnum text-[11px] text-ink-dim">{affectedSummary(preview)}</span>
      </div>
      <div className="max-h-56 overflow-y-auto rounded-xl border border-edge bg-wash">
        {preview.affected.map((a) => (
          <div
            key={`${a.kind}${a.id}`}
            className="flex items-baseline gap-2 px-2.5 py-1 text-[11px]"
          >
            <span className="shrink-0 font-mono text-ink-faint">
              {a.kind === 'group' ? groupCode(a.id) : `g${a.id}`}
            </span>
            <span
              className={`min-w-0 flex-1 truncate ${
                a.kind === 'group' ? 'text-ink-dim' : 'font-mono text-ink-dim'
              }`}
              title={a.slug}
            >
              {a.slug}
            </span>
            <span className="shrink-0 text-ink-faint">
              {a.kind === 'goal' ? goalStatusLabel(a.status) : a.status}
            </span>
            <span className="shrink-0 text-ink" title="what this command makes of it">
              → {a.effect}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function CommandConfirm({
  problem,
  kind,
  payload,
  label,
  onClose,
  onFieldError,
  onApplied,
}: {
  problem: string
  kind: CommandKind
  payload: Record<string, unknown>
  /** what the command is about, in the reader's terms — a goal's name,
   * a group's charter line. Optional: the payload alone is ids. */
  label?: string
  onClose: () => void
  /** a 422 belongs under the input that drew it; the modal hands the
   * engine's own sentence back to the form and gets out of the way */
  onFieldError?: (field: string | null, detail: string) => void
  /** the command landed — the surface may drop its sheet */
  onApplied?: () => void
}) {
  const [preview, setPreview] = useState<CommandPreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const appliedRef = useRef(onApplied)
  appliedRef.current = onApplied

  // the payload arrives as a fresh object every render; the preview
  // must follow its CONTENT, or the read re-fires forever
  const payloadKey = JSON.stringify(payload)
  const payloadRef = useRef(payload)
  payloadRef.current = payload

  // the preview is a READ on the read-only connection: nothing is
  // queued and nothing moves until Confirm
  useEffect(() => {
    let gone = false
    setPreview(null)
    setError(null)
    apiPost<CommandPreview>('/api/commands/preview', {
      problem,
      kind,
      payload: JSON.parse(payloadKey),
    })
      .then((p) => !gone && setPreview(p))
      .catch((e) => !gone && setError(String((e as Error).message)))
    return () => {
      gone = true
    }
  }, [problem, kind, payloadKey])

  const close = useCallback(() => {
    if (submitting) return // a POST is in flight; let it answer
    onClose()
  }, [submitting, onClose])

  // the receipt: 202 is "queued", never "done" — poll until the
  // daemon's tick has answered
  useEffect(() => {
    if (receipt === null || receipt.phase !== 'waiting') {
      if (receipt?.phase === 'applied') appliedRef.current?.()
      return
    }
    const t = window.setTimeout(() => {
      apiGet<CommandRow>(`/api/commands/${receipt.id}`)
        .then((row) => setReceipt((r) => (r === null ? r : receiptStep(r, row))))
        .catch(() => setReceipt((r) => (r === null ? r : receiptStep(r, null))))
    }, RECEIPT_POLL_MS)
    return () => window.clearTimeout(t)
  }, [receipt])

  const submit = async () => {
    if (preview === null) return
    setSubmitting(true)
    setError(null)
    try {
      const r = await apiPost<{ id: number }>('/api/commands', {
        problem,
        kind,
        payload,
        // fresh per submission: a retried POST is the same command, a
        // re-issue after a refusal is a different one
        idempotency_key: newIdempotencyKey(),
        expected_revision: preview.revision,
      })
      setReceipt(receiptStart(r.id))
    } catch (e) {
      const detail = e instanceof ApiError ? e.detail : String((e as Error).message)
      if (e instanceof ApiError && e.status === 422 && onFieldError) {
        onFieldError(fieldFromDetail(detail), detail)
        onClose()
        return
      }
      setError(detail)
    } finally {
      setSubmitting(false)
    }
  }

  const settled = receipt !== null && receipt.phase !== 'waiting'
  const cascade = preview?.cascade ?? false

  return (
    <ConfirmWindow
      title={commandTitle(kind)}
      subject={label ?? problem}
      badge={kind}
      badgeTitle="the engine's own name for this command"
      onClose={close}
    >
        {preview === null && error === null && (
          <div className="late-fade mt-4 text-xs text-ink-faint">
            reading what this would close…
          </div>
        )}

        {preview && (
          <>
            {preview.effect && (
              <p className="mt-3 max-w-[52ch] text-[12px] leading-relaxed text-ink-dim">
                {preview.effect}
              </p>
            )}
            {preview.pipeline === null && (
              <p className="mt-3 text-[12px] text-warn">
                there is no such worker — nothing has ever run under that id.
              </p>
            )}
            {preview.pipeline && (
              <div className="mt-3 flex items-baseline gap-3 rounded-xl border border-edge bg-wash px-3 py-2 text-[11px]">
                <span className="text-ink">{preview.pipeline.kind.toLowerCase()}</span>
                <span className="font-mono text-ink-faint">{preview.pipeline.id}</span>
                <span className="text-ink-dim">{preview.pipeline.status}</span>
                <span
                  className="tnum ml-auto text-ink-faint"
                  title="how long this worker has been running — four minutes in and forty are not the same decision"
                >
                  {relTime(preview.pipeline.started_at)}
                </span>
              </div>
            )}
            {cascade && (
              <p className="mt-3 flex items-baseline gap-2 text-[12px] text-warn">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-warn" />
                this does not stop at the node you picked — everything below is listed.
              </p>
            )}
            <Affected preview={preview} />
            {preview.affected.length === 0 && !preview.pipeline && (
              <p className="mt-3 text-[12px] text-ink-faint">
                nothing else closes with it — the command acts on this one thing.
              </p>
            )}
          </>
        )}

        {error && <div className="mt-3 text-[12px] text-danger">{error}</div>}
        {receipt && (
          <div
            className={`mt-3 text-[12px] ${
              receipt.phase === 'rejected' ? 'text-warn' : 'text-ink-dim'
            }`}
          >
            {receiptLine(receipt)}
          </div>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          {receipt === null ? (
            <>
              <Button variant="outline" onClick={close} disabled={submitting}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={preview === null || submitting}
                onClick={() => void submit()}
                title="queues the command; the engine applies it on its next tick"
              >
                {submitting ? 'Sending…' : 'Confirm — queue it'}
              </Button>
            </>
          ) : (
            <Button variant="outline" onClick={onClose}>
              {settled ? 'Close' : 'Close — it stays queued'}
            </Button>
          )}
        </div>
      {receipt === null && preview !== null && (
        <div className="mt-2 text-right text-[11px] text-ink-faint">
          read at revision {preview.revision} — the command carries it, so a record that
          moves in between is refused rather than applied
        </div>
      )}
    </ConfirmWindow>
  )
}
