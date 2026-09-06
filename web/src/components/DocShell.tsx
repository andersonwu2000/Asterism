import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { claimLeanSlot, releaseLeanSlot } from '../lib/leanSlot'
import type { LeanCursor } from '../lib/leanSession'
import { editable, modeFor, ownerOf, syncedScrollTop } from '../lib/docShell'
import type { DocPane, DocRef, DocView } from '../lib/docShell'
import type { TheoryMeta } from '../lib/docShelf'
import { requestAssistant } from '../lib/focus'
import { EDITOR_METRICS, frameClass } from '../lib/textFrame'
import { ImagePanel, LeanInfoPanel, PdfPanel, ProsePanel, TexPanel } from './DocPanels'
import { MarkdownEditor } from '../lib/markdown'
import { LeanEditor } from './LeanEditor'
import { Button } from './ui'

/*
 * The open document (docs_tab_spec.md §C1-C3): one header line saying
 * what it is and what may be done to it, and a body of one or two
 * panes.
 *
 * The shell owns the VIEW, which is why the panels beside it are plain
 * components rather than the two whole-split screens they used to be
 * (`LeanDoc` / `TexDoc`): a reader who wants the source alone, or the
 * render alone, is asking the same document a different question.
 *
 * It owns no acts on the FILE. Renaming, moving and deleting live on
 * the rail's selected row and nowhere else (§D6) — the header used to
 * carry them too, which is two places for one thing.
 */

/** What the screen has fetched for the open ref. */
export interface OpenDoc {
  /** what the reader sees: the draft when one exists, else the disk */
  text?: string
  /** an image or a pdf payload */
  base64?: string
  /** the API's own sentence about why this could not be read */
  error: string | null
}

/** A 409 from the PUT: someone else's bytes are on disk under this
 * name. Shown IN the header rather than in a window — it is a field's
 * own refusal, and DESIGN.md floats only what is a task of its own. */
export interface Conflict {
  detail: string
}

const lastSegment = (path: string): string => path.split('/').pop() ?? path

/** The mode table's pane widths, spelt in the one place that draws
 * them. `even` splits the room between writing and reading; the other
 * two hold content with a width of its own (a compiled page, a column
 * of diagnostics) that would only dilute the writing by taking half. */
const PANE_WIDTH: Record<DocPane, string> = {
  even: 'flex-1',
  narrow: 'w-[30rem] shrink-0',
  side: 'w-96 shrink-0',
}

/** Where the document sits, said once. The rail already highlights the
 * row, so this is the only place the path is spelt out. */
function place(ref: DocRef): string {
  const parent = ref.path.split('/').slice(0, -1).join('/')
  if (ref.kind === 'doc') return parent === '' ? '' : `${parent}/`
  return [ref.task, parent].filter((s) => s).join('/') + '/'
}

export default function DocShell({
  project,
  open,
  isDir,
  theory,
  doc,
  view,
  onView,
  dirty,
  saving,
  note,
  conflict,
  savedAt,
  autoFocus,
  onChange,
  onSave,
  onTakeDisk,
  onKeepMine,
}: {
  project: string
  open: DocRef | null
  /** the open ref names a folder, not a file */
  isDir: boolean
  theory: TheoryMeta | null
  doc: OpenDoc | null
  view: DocView
  onView: (v: DocView) => void
  dirty: boolean
  saving: boolean
  /** `saved`, or the engine's refusal */
  note: string | null
  conflict: Conflict | null
  /** bumped when the document lands on disk — the TeX panel follows */
  savedAt: number
  /** the document was just created here (§D5) — the caret starts in it */
  autoFocus: boolean
  onChange: (text: string) => void
  onSave: () => void
  onTakeDisk: () => void
  onKeepMine: () => void
}) {
  const [cursor, setCursor] = useState<LeanCursor | null>(null)
  /* The render pane follows the writing. One direction only: a render
   * that scrolled the source back would fight the reader's wheel, and
   * the pane a person is IN is the one that decides where both are
   * (`docShell::syncedScrollTop` owns the mapping and is tested there). */
  const sourcePane = useRef<HTMLDivElement | null>(null)
  const renderPane = useRef<HTMLDivElement | null>(null)
  const followScroll = useCallback(() => {
    const from = sourcePane.current
    const to = renderPane.current
    if (from === null || to === null) return
    to.scrollTop = syncedScrollTop(from, to)
  }, [])
  // one reserved Lean slot, browser-wide: this surface holds it only
  // while the reader is actually typing in it
  const slotId = useId()
  useEffect(() => () => releaseLeanSlot(slotId), [slotId])
  // a new document is a new caret — a stale line number would ask the
  // engine for a goal in a file nobody is reading
  const key = open === null ? '' : `${open.kind}:${open.path}`
  useEffect(() => setCursor(null), [key])

  if (open === null)
    return (
      <div className="min-w-0 flex-1 overflow-auto p-6">
        <p className="max-w-md text-[11px] leading-relaxed text-ink-faint">
          Nothing open. Pick a document on the left, or start one with{' '}
          <span className="font-mono">+ file</span> under{' '}
          <span className="font-mono">yours</span>.
        </p>
      </div>
    )

  /* ONE table decides what the two panes do (`lib/docShell::modeFor`):
   * the tab set, which painter the source wears, how wide the render
   * sits, whether it follows the writing and what its check offers.
   * `.md` and `.tex` are two rows of it — until 2026-09-06 they were
   * four separate branches here, and had drifted apart in every one. */
  const mode = modeFor(open.path)
  const panel = mode.panel
  const writable = editable(open) && !isDir
  const owner = ownerOf(open, theory)
  const text = doc?.text ?? ''
  // the segmented control exists only where there are two halves to
  // choose between (§C2)
  const hasViews = !isDir && mode.third !== null
  const showLeft = view !== 'render'
  const showRight = view !== 'source'

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-edge px-4 py-1.5">
        <span className="font-mono text-[12px] text-ink" title={open.path}>
          {lastSegment(open.path)}
        </span>
        <span className="min-w-0 truncate font-mono text-[11px] text-ink-faint">
          {place(open)}
        </span>
        {owner !== null && <span className="text-[11px] text-ink-faint">{owner}</span>}
        {hasViews && (
          <span className="ml-2 flex items-center gap-1">
            {(['source', 'split', 'render'] as const).map((v) => (
              <button
                key={v}
                className={`cursor-pointer rounded-md px-2 py-0.5 text-[11px] transition-colors ${
                  view === v ? 'bg-surface-2 text-ink' : 'text-ink-faint hover:text-ink-dim'
                }`}
                aria-pressed={view === v}
                onClick={() => onView(v)}
              >
                {v === 'render' ? (mode.third ?? v) : v}
              </button>
            ))}
          </span>
        )}
        {writable && dirty && (
          <Button
            variant="ok"
            size="xs"
            disabled={saving}
            title="Ctrl+S"
            onClick={onSave}
          >
            {saving ? 'Saving…' : 'Save'}
          </Button>
        )}
        {note !== null && conflict === null && (
          <span
            className={`min-w-0 truncate text-[11px] ${
              note === 'saved' ? 'text-ink-faint' : 'text-warn'
            }`}
          >
            {note}
          </span>
        )}
        {conflict !== null && (
          <span className="flex min-w-0 items-center gap-2 text-[11px] text-warn">
            <span className="min-w-0 truncate">{conflict.detail}</span>
            <button
              className="cursor-pointer text-ink-faint underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink"
              onClick={onTakeDisk}
              title="drop what you wrote and reload the file"
            >
              take the disk's
            </button>
            <button
              className="cursor-pointer text-ink-faint underline decoration-edge-strong underline-offset-2 transition-colors hover:text-ink"
              onClick={onKeepMine}
              title="overwrite the disk with what you wrote"
            >
              keep mine
            </button>
          </span>
        )}
        <button
          className="ml-auto shrink-0 cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
          onClick={requestAssistant}
          title="open the Assistant on this document"
        >
          ask the Assistant
        </button>
      </div>

      {isDir ? (
        <div className="min-w-0 flex-1 overflow-auto p-4">
          <p className="text-[11px] text-ink-faint">a folder — new files start here.</p>
        </div>
      ) : doc?.error != null ? (
        <div className="min-w-0 flex-1 overflow-auto p-4">
          <div className="text-xs text-warn">{doc.error}</div>
        </div>
      ) : panel === 'viewer' ? (
        <PdfPanel src={rawDocUrl(project, open)} title={open.path} />
      ) : panel === 'image' ? (
        <div className="min-w-0 flex-1 overflow-auto p-4">
          {doc?.base64 === undefined && doc?.text === undefined ? (
            <div className="late-fade text-xs text-ink-faint">loading…</div>
          ) : (
            <ImagePanel path={open.path} base64={doc?.base64} text={doc?.text} />
          )}
        </div>
      ) : doc === null || doc.text === undefined ? (
        // loading is not empty (§C3): the read is in flight, or has not
        // been started yet in this frame — either way there is no
        // document to draw, and a blank editor would claim there is
        <div className="min-w-0 flex-1 overflow-auto p-4">
          <div className="late-fade text-xs text-ink-faint">loading…</div>
        </div>
      ) : (
        <div className="flex min-h-0 min-w-0 flex-1">
          {showLeft && (
            <div
              ref={sourcePane}
              onScroll={mode.scrollSync && showRight ? followScroll : undefined}
              className="flex min-w-0 flex-1 flex-col overflow-auto p-4"
            >
              {mode.editor === 'lean' ? (
                <LeanEditor
                  key={key}
                  value={text}
                  readOnly={!writable}
                  onChange={onChange}
                  onCaret={(pos) => setCursor({ part: 'doc', ...pos })}
                  onFocus={() => claimLeanSlot(slotId)}
                  autoFocus={autoFocus}
                  heightClass="min-h-[24rem] h-auto field-sizing-content"
                />
              ) : writable && mode.editor === 'markdown' ? (
                /* the console's own markdown painter, the one the task
                   page's goal and standing word have always worn
                   (`lib/markdown`). This tab used neither tokenizer:
                   every file a person could edit got a bare box while
                   the same prose was coloured one section over (owner,
                   2026-09-06). A language with no painter keeps the
                   plain box below — colouring TeX with a markdown
                   painter would paint it wrong. */
                <MarkdownEditor
                  key={key}
                  value={text}
                  onChange={onChange}
                  autoFocus={autoFocus}
                  label="document source"
                  className="bg-wash"
                  heightClass="min-h-[24rem] h-auto field-sizing-content"
                />
              ) : writable ? (
                <textarea
                  key={key}
                  className={`h-full min-h-[24rem] w-full resize-none rounded-xl border border-edge bg-wash text-ink focus:border-ink-faint focus:outline-none ${EDITOR_METRICS}`}
                  value={text}
                  autoFocus={autoFocus}
                  spellCheck={false}
                  onChange={(e) => onChange(e.target.value)}
                />
              ) : (
                <pre className={frameClass({ frame: false, size: 'md', wrap: true })}>
                  {text}
                </pre>
              )}
            </div>
          )}
          {showRight && (
            <div
              className={`flex min-h-0 min-w-0 flex-col ${
                showLeft ? 'border-l border-edge' : ''
              } ${PANE_WIDTH[mode.pane]}`}
            >
              {panel === 'render' ? (
                <ProsePanel text={text} scrollRef={renderPane} />
              ) : panel === 'pdf-render' ? (
                <TexPanel
                  key={key}
                  project={project}
                  path={open.path}
                  value={text}
                  savedAt={savedAt}
                />
              ) : (
                <LeanInfoPanel key={key} slotId={slotId} value={text} cursor={cursor} />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** The raw address a pdf viewer fetches for itself. Only a document ref
 * reaches this: the engine writes no pdfs. */
function rawDocUrl(project: string, ref: DocRef): string {
  const tail = ref.path.split('/').map(encodeURIComponent).join('/')
  return `/api/projects/${encodeURIComponent(project)}/docs/${tail}?raw=1`
}
