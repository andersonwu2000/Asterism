import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, apiPost } from '../lib/api'
import { frameClass } from '../lib/textFrame'
import { Button } from './ui'

/*
 * A `.tex` document on the Project's shelf, Overleaf's way
 * (human_interface_design.md §1.2-2): the source on the left, the
 * compiled pdf on the right.
 *
 * The compile is the server's — `POST /api/projects/{p}/tex`, which
 * finds an engine at call time and answers with the render's address —
 * so the panel is an `<object>` pointed at a URL and nothing more. That
 * is also why the address is a sha1: pressing Render on an unchanged
 * document costs a directory listing.
 *
 * Three answers, all of them said plainly (DESIGN.md: engine states
 * speak inside the panel they affect, in human words): there is no TeX
 * on this machine, the engine refused the document (with the tail of
 * its own log), or here it is.
 */

type TexResult = {
  status: 'ok' | 'failed' | 'no_engine'
  engine: string | null
  sha1?: string
  pdf?: string
  detail?: string
  log_tail?: string
}

/** A save settles into one render. Several quick saves are one edit. */
const SAVE_DEBOUNCE_MS = 700

export default function TexDoc({
  project,
  path,
  value,
  onChange,
  /** bumped by the shelf when the document lands on disk — the render
   * follows the file, not every keystroke */
  savedAt,
}: {
  project: string
  path: string
  value: string
  onChange: (v: string) => void
  savedAt: number
}) {
  const [result, setResult] = useState<TexResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const valueRef = useRef(value)
  valueRef.current = value

  const render = useCallback(
    async (force: boolean) => {
      setBusy(true)
      setError(null)
      try {
        setResult(
          await apiPost<TexResult>(`/api/projects/${encodeURIComponent(project)}/tex`, {
            path,
            // what is in the box, so the panel follows the writing even
            // before the document lands on disk
            content: valueRef.current,
            force,
          }),
        )
      } catch (e) {
        setResult(null)
        setError(e instanceof ApiError ? e.detail : String((e as Error).message))
      } finally {
        setBusy(false)
      }
    },
    [project, path],
  )

  // on open, and again once each save has settled
  useEffect(() => {
    const t = window.setTimeout(() => void render(false), SAVE_DEBOUNCE_MS)
    return () => window.clearTimeout(t)
  }, [render, savedAt])

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
      <div className="min-w-0 flex-1 overflow-auto p-4">
        <textarea
          className="h-full min-h-[24rem] w-full resize-none rounded-xl border border-edge bg-wash p-3 font-mono text-[12px] leading-relaxed text-ink focus:border-ink-faint focus:outline-none"
          value={value}
          spellCheck={false}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
      <div className="flex w-[30rem] min-w-0 shrink-0 flex-col border-l border-edge">
        <div className="flex shrink-0 items-center gap-3 border-b border-edge px-3 py-1.5">
          <Button size="xs" disabled={busy} onClick={() => void render(true)}>
            {busy ? 'Rendering…' : 'Render'}
          </Button>
          <span className="min-w-0 flex-1 truncate text-[11px] text-ink-faint">
            {busy
              ? 'the engine is compiling it'
              : result?.status === 'ok'
                ? `compiled by ${result.engine}`
                : result?.status === 'no_engine'
                  ? 'no TeX engine here'
                  : result?.status === 'failed'
                    ? `${result.engine} refused it`
                    : ''}
          </span>
        </div>
        <div className="min-h-0 min-w-0 flex-1 overflow-auto">
          {error && <div className="p-3 text-[11px] text-warn">{error}</div>}
          {result?.status === 'no_engine' && (
            <p className="p-3 text-[11px] leading-relaxed text-ink-faint">
              {result.detail}
            </p>
          )}
          {result?.status === 'failed' && (
            <div className="p-3">
              <div className="mb-1 text-[11px] text-warn">{result.detail}</div>
              <pre className={frameClass({ tone: 'faint' })}>{result.log_tail}</pre>
            </div>
          )}
          {result?.status === 'ok' && result.pdf && (
            // keyed on the sha1: a new render is a new document, and a
            // reused <object> keeps showing the old one
            <object
              key={result.sha1}
              data={result.pdf}
              type="application/pdf"
              className="h-full min-h-[24rem] w-full"
              aria-label={`${path} — compiled`}
            >
              <p className="p-3 text-[11px] text-ink-faint">
                this browser will not display a pdf inline —{' '}
                <a
                  href={result.pdf}
                  className="underline decoration-edge-strong underline-offset-2 hover:text-ink"
                >
                  open the render
                </a>
                .
              </p>
            </object>
          )}
        </div>
      </div>
    </div>
  )
}
