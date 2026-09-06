import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode, Ref } from 'react'
import { ApiError, apiPost } from '../lib/api'
import { engineWord, useLeanSession, type LeanCursor } from '../lib/leanSession'
import { useLeanSlotActive } from '../lib/leanSlot'
import { proseIssues, renderProse } from '../lib/prose'
import { frameClass } from '../lib/textFrame'
import { DiagList } from './LeanBlock'
import { Button } from './ui'

/*
 * The Documents tab's right-hand panels (docs_tab_spec.md §C3): one per
 * kind of document, because "what sits beside the text while you write
 * it" is a different question for prose, TeX and Lean
 * (human_interface_design.md §1.2-2, 左編輯、右面板).
 *
 * They live together in one file because they are one slot on one
 * screen — the shell picks by `panelFor(path)` and never by an `if`
 * chain of its own. The TeX and Lean panels are the halves that used to
 * be `TexDoc.tsx` and `LeanDoc.tsx`, which owned the WHOLE split and so
 * could not be reused by a shell that owns the view control.
 */

/** The bar every render pane wears: the CHECK, and what it answered.
 *
 * One shape for prose and for TeX. The two formats must operate alike
 * (owner, 2026-09-06) and "does this read?" is the same question in
 * both — only the thing that answers it differs, so only that differs
 * here. Before this the markdown render had no bar at all, which said
 * markdown could not be wrong. */
function PanelBar({
  action,
  status,
  warn = false,
}: {
  action: ReactNode
  status: string
  /** the answer is bad news — the TeX pane's own idiom for it */
  warn?: boolean
}) {
  return (
    <div className="flex shrink-0 items-center gap-3 border-b border-edge px-3 py-1.5">
      {action}
      <span
        className={`min-w-0 flex-1 truncate text-[11px] ${warn ? 'text-warn' : 'text-ink-faint'}`}
      >
        {status}
      </span>
    </div>
  )
}

/** Markdown's render, of the DRAFT text — a document reads as it is
 * being written, not as it was last saved.
 *
 * The check is the painter itself (`lib/prose::proseIssues`): the
 * render below the bar is what the document says, and the bar says
 * whether anything in it fell out of that reading on the way. No
 * compile step, because there is none — the paint is already live, and
 * the button opens the report rather than starting work. */
export function ProsePanel({
  text,
  scrollRef,
}: {
  text: string
  /** the shell drives this pane from the source pane's scroll
   * (`docShell::syncedScrollTop`) */
  scrollRef?: Ref<HTMLDivElement>
}) {
  const [open, setOpen] = useState(false)
  const issues = useMemo(() => proseIssues(text), [text])
  const n = issues.length
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <PanelBar
        action={
          <Button size="xs" onClick={() => setOpen((v) => !v)}>
            {open ? 'Hide' : 'Check'}
          </Button>
        }
        warn={n > 0}
        status={
          n === 0
            ? 'painted by the console — it read every line'
            : `${n} line${n === 1 ? '' : 's'} the painter could not read`
        }
      />
      {open && (
        <pre className={frameClass({ tone: 'faint', className: 'mx-3 mt-2 shrink-0' })}>
          {n === 0
            ? 'Nothing fell out of the reading. Fences all close and every $formula$ typesets.'
            : issues.map((i) => `line ${i.line} — ${i.detail}`).join('\n')}
        </pre>
      )}
      <div ref={scrollRef} className="min-h-0 min-w-0 flex-1 overflow-auto p-4">
        <div className="max-w-[78ch] text-[13px] leading-relaxed text-ink-dim">
          {renderProse(text, { mode: 'document', frontmatter: true })}
        </div>
      </div>
    </div>
  )
}

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

/**
 * A `.tex` document's compiled pdf, Overleaf's way.
 *
 * The compile is the server's — `POST /api/projects/{p}/tex`, which
 * finds an engine at call time and answers with the render's address —
 * so the panel is an `<object>` pointed at a URL and nothing more. That
 * is also why the address is a sha1: pressing Render on an unchanged
 * document costs a directory listing.
 *
 * Three answers, all said plainly (DESIGN.md: engine states speak
 * inside the panel they affect, in human words): there is no TeX on
 * this machine, the engine refused the document (with the tail of its
 * own log), or here it is. Opening never blocks on any of them.
 */
export function TexPanel({
  project,
  path,
  value,
  savedAt,
}: {
  project: string
  path: string
  value: string
  /** bumped by the shell when the document lands on disk — the render
   * follows the file, not every keystroke */
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
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <PanelBar
        action={
          <Button size="xs" disabled={busy} onClick={() => void render(true)}>
            {busy ? 'Rendering…' : 'Render'}
          </Button>
        }
        warn={!busy && result?.status === 'failed'}
        status={
          busy
            ? 'compiling…'
            : result?.status === 'ok'
              ? `compiled by ${result.engine}`
              : result?.status === 'no_engine'
                ? 'no TeX engine here'
                : result?.status === 'failed'
                  ? `${result.engine} refused it`
                  : ''
        }
      />
      <div className="min-h-0 min-w-0 flex-1 overflow-auto">
        {error && <div className="p-3 text-[11px] text-warn">{error}</div>}
        {result === null && !busy && error === null && (
          <div className="late-fade p-3 text-[11px] text-ink-faint">compiling…</div>
        )}
        {result?.status === 'no_engine' && (
          <p className="p-3 text-[11px] leading-relaxed text-ink-faint">{result.detail}</p>
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
  )
}

/**
 * A `.lean` document's Info panel: the goal at the caret plus the
 * engine's diagnostics.
 *
 * It runs on the SAME session every other live Lean surface runs on —
 * `useLeanSession` over `/api/lean/session`, holding the one reserved
 * gateway slot through `lib/leanSlot`. There is no second eval client
 * here and there must not be: the probe, the New page and this document
 * differ in where they sit, not in how they ask.
 *
 * The file carries its own `import` header, which is how it reaches the
 * engine's proofs (`Problems.<task>.proofs.…`); serve rebuilds those
 * modules incrementally before elaborating, so the panel reads the text
 * on disk rather than a stale olean.
 */
export function LeanInfoPanel({
  slotId,
  value,
  cursor,
}: {
  /** the shell's reserved-slot id — the editor beside this panel claims
   * it on focus, and the session runs only while this surface holds it */
  slotId: string
  value: string
  cursor: LeanCursor | null
}) {
  const active = useLeanSlotActive(slotId)
  const s = useLeanSession({
    enabled: true,
    active,
    parts: [{ id: 'doc', code: value }],
    // no `imports` list: the document's own header IS the list, and
    // serve reads the assembled text for what it must rebuild
    imports: [],
    cursor,
  })
  const diags = [...s.preamble, ...(s.parts.doc ?? [])]
  const status = engineWord(s)
  const goal =
    cursor && s.goal && s.goal !== 'no goals' && !s.goal.startsWith('<no goals')
      ? s.goal.replace(/^```lean\n?/, '').replace(/\n?```\s*$/, '')
      : null

  return (
    <div className="min-h-0 min-w-0 flex-1 overflow-y-auto px-4 py-3">
      {status !== '' && (
        <div className="mb-2 text-[11px] leading-relaxed text-ink-faint">{status}</div>
      )}
      {goal !== null && (
        <>
          <div className="mb-1 text-[10px] tracking-widest text-ink-faint uppercase">
            goal at the cursor
          </div>
          <pre className={frameClass({ frame: false, lead: 'quote', tone: 'ink' })}>
            {goal}
          </pre>
        </>
      )}
      {diags.length === 0 && goal === null && status === '' && (
        <div className="text-[11px] leading-relaxed text-ink-faint">
          no messages — the file elaborates clean. Put the caret inside a proof to see its
          goal.
        </div>
      )}
      <DiagList diags={diags} />
    </div>
  )
}

/** A pdf, shown by the browser's own viewer. It is pointed at the raw
 * document address rather than at a blob built from the base64 payload:
 * a paper runs to tens of megabytes, and a blob cannot answer the range
 * requests the viewer makes to open page one before the rest arrives. */
export function PdfPanel({ src, title }: { src: string; title: string }) {
  return <iframe src={src} title={title} className="h-full w-full bg-wash" />
}

const MIME: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
}

/** An image. A `.svg` arrives as text and the rest as base64 — one
 * `<img>` either way, so the panel does not care which door it came
 * through. */
export function ImagePanel({
  path,
  base64,
  text,
}: {
  path: string
  base64?: string
  text?: string
}) {
  const i = path.lastIndexOf('.')
  const e = i < 0 ? '' : path.slice(i).toLowerCase()
  const src =
    base64 !== undefined
      ? `data:${MIME[e] ?? 'application/octet-stream'};base64,${base64}`
      : text !== undefined
        ? `data:image/svg+xml;utf8,${encodeURIComponent(text)}`
        : null
  if (src === null) return null
  return (
    <img src={src} alt={path} className="max-w-full rounded-xl border border-edge" />
  )
}
