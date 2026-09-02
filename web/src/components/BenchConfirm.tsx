import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ApiError, apiPost } from '../lib/api'
import { benchPath } from '../lib/bench'
import { Button } from './ui'

/*
 * The bench window — "stop this task without stopping the run"
 * (owner's ruling; `POST /api/problems/{p}/bench` | `/unbench`).
 *
 * It floats by the same carve-out CommandConfirm floats under, and
 * wears the same shape (DESIGN.md: `fixed inset-0 z-50` over
 * `bg-bg/70`, one centred panel, Escape and backdrop close, focus
 * lands inside, rendered through a portal because the surfaces that
 * open it animate transforms).
 *
 * It is NOT a queued command, and must not pretend to be one: bench
 * flips a flag through an idempotent endpoint and answers immediately,
 * so there is no preview to read, no revision to carry and no receipt
 * to poll. What the reader is owed instead is what the flip does and
 * what it deliberately does NOT do — nothing in flight is killed.
 */
export default function BenchConfirm({
  problem,
  benched,
  onClose,
  onDone,
}: {
  problem: string
  /** the direction: true = take it off the live path */
  benched: boolean
  onClose: () => void
  /** the flip landed — the surface may refresh what it shows */
  onDone?: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const panelRef = useRef<HTMLDivElement | null>(null)

  const close = useCallback(() => {
    if (busy) return // a POST is in flight; let it answer
    onClose()
  }, [busy, onClose])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        close()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [close])

  useEffect(() => {
    panelRef.current?.focus()
  }, [])

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiPost(benchPath(problem, benched), {})
      setDone(true)
      onDone?.()
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg/70 p-6"
      onClick={close}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className="w-[32rem] max-w-full rounded-xl border border-edge bg-surface p-5 focus:outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-ink">
            {benched ? 'stop this task' : 'put this task back'}
          </span>
          <span className="min-w-0 truncate font-mono text-[11px] text-ink-faint" title={problem}>
            {problem}
          </span>
          <span
            className="ml-auto shrink-0 font-mono text-[10px] text-ink-faint/70"
            title="the engine's own name for this"
          >
            {benched ? 'bench' : 'unbench'}
          </span>
        </div>

        <p className="mt-3 max-w-[52ch] text-[12px] leading-relaxed text-ink-dim">
          {benched
            ? 'Dispatch skips this task until you put it back, and it takes no Strategist seat. Nothing in flight is killed — the agents on it now finish and land their work. Every goal, revision and your standing word stay exactly as they are.'
            : 'Dispatch picks this task up again from the engine’s next tick. Nothing else changes: the bench kept everything.'}
        </p>
        {benched && (
          <p className="mt-2 max-w-[52ch] text-[12px] leading-relaxed text-ink-faint">
            The rest of the run keeps going. To stop the engine itself, use Stop on the Tasks
            page.
          </p>
        )}

        {error && <div className="mt-3 text-[12px] text-danger">{error}</div>}
        {done && (
          <div className="mt-3 text-[12px] text-ink-dim">
            {benched
              ? 'benched — the next tick dispatches nothing here'
              : 'back on the live path — the next tick may dispatch here'}
          </div>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          {done ? (
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={close} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={busy}
                onClick={() => void submit()}
                title={
                  benched
                    ? 'takes this task off the live path; you can put it back at any time'
                    : 'puts this task back on the live path'
                }
              >
                {busy
                  ? 'Sending…'
                  : benched
                    ? 'Confirm — bench it'
                    : 'Confirm — put it back'}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
