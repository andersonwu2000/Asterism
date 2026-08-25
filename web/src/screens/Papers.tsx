import { Fragment, useEffect, useRef, useState } from 'react'
import { ApiError, apiDelete, apiPost, apiUpload, usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { shelfGroups } from '../lib/papers'
import { Button, EmptyState, ErrorState } from '../components/ui'
import type { PaperShelfItem } from '../lib/types'

/*
 * The paper shelf: every source the engine can ground its citations in.
 * One flat table (Board vocabulary) — a shelf of tens, not thousands.
 * Opening a paper shows the ORIGINAL document (browser-native PDF
 * rendering) beside a slim rail for switching papers; the extracted
 * text is the machines' copy, not a human reading surface.
 */

/** "21 pp · 87k chars" — pages first (how a mathematician sizes a
 * paper), characters as the honest extraction figure. */
function sizeLabel(p: PaperShelfItem): string {
  const chars = p.chars >= 1000 ? `${Math.round(p.chars / 1000)}k` : String(p.chars)
  return `${p.pages > 0 ? `${p.pages} pp` : 'unpaged'} · ${chars} chars`
}

function errText(e: unknown): string {
  return e instanceof ApiError ? e.detail : String((e as Error).message)
}

/** Two-step delete, same pattern as Telemetry's force stop: first press
 * arms it, 3s of silence disarms. */
function ShelfRow({ p, onChanged }: { p: PaperShelfItem; onChanged: () => void }) {
  const [armed, setArmed] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const rename = async (title: string) => {
    setRenaming(false)
    setErr(null)
    try {
      await apiPost(`/api/papers/${encodeURIComponent(p.id)}/rename`, { title })
      onChanged()
    } catch (e) {
      setErr(errText(e))
    }
  }
  const timer = useRef<number | null>(null)
  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )
  const del = async () => {
    if (!armed) {
      setArmed(true)
      if (timer.current !== null) window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => setArmed(false), 3000)
      return
    }
    if (timer.current !== null) window.clearTimeout(timer.current)
    setArmed(false)
    setErr(null)
    try {
      await apiDelete(`/api/papers/${encodeURIComponent(p.id)}`)
      onChanged()
    } catch (e) {
      setErr(errText(e))
    }
  }
  return (
    <>
      <tr className="group/row h-9 border-b border-edge/60 transition-colors duration-150 hover:bg-surface">
        <td className="pr-4 pl-3">
          {renaming ? (
            <input
              className="w-full rounded-md border border-edge bg-bg px-1.5 py-0.5 text-[13px] text-ink focus:border-ink-faint focus:outline-none"
              defaultValue={p.title ?? ''}
              placeholder={p.source_name}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') void rename(e.currentTarget.value)
                if (e.key === 'Escape') setRenaming(false)
              }}
              onBlur={() => setRenaming(false)}
            />
          ) : (
            <span className="flex min-w-0 items-baseline gap-2">
              <Link
                to={`/papers/${encodeURIComponent(p.id)}`}
                className={`block truncate text-[13px] text-ink transition-colors hover:text-starlight ${p.title ? '' : 'font-mono'}`}
                title={`read it — ${p.source_name} · ${sizeLabel(p)}`}
              >
                {p.title ?? p.source_name}
              </Link>
              {/* provenance: the default case (user upload) stays
                  unmarked; only the exception — the engine fetching
                  mid-run — wears a tag (the strategist fetches with
                  its own tools since the Scholar retired, 020ebf85) */}
              {p.added_by === 'fetched' && (
                <span
                  className="shrink-0 rounded-md border border-edge px-1 py-px text-[10px] text-ink-faint"
                  title="fetched by the engine during a run"
                >
                  fetched
                </span>
              )}
              {/* a human name for "paper.pdf" (owner, 2026-07-13) —
                  display only; identity stays the content hash */}
              <button
                className="shrink-0 text-[11px] text-ink-faint opacity-0 transition-opacity hover:text-ink group-hover/row:opacity-100"
                onClick={() => setRenaming(true)}
                title="rename (display only — the file keeps its name)"
              >
                rename
              </button>
            </span>
          )}
        </td>
        <td className="pr-4">
          {p.bound.length === 0 ? (
            <span className="text-xs text-ink-faint">—</span>
          ) : (
            /* block, or truncate is inert on an inline span and the
               names overprint the neighbouring columns (cold-eye) */
            <span className="block truncate text-xs" title={p.bound.map((b) => b.problem).join(', ')}>
              {p.bound.map((b, i) => (
                <span key={b.problem}>
                  {i > 0 && <span className="text-ink-faint">, </span>}
                  <Link
                    to={`/problems/${encodeURIComponent(b.problem)}`}
                    className="font-mono text-[12px] text-ink-dim transition-colors hover:text-ink"
                  >
                    {b.problem}
                  </Link>
                </span>
              ))}
            </span>
          )}
        </td>
        <td className="pr-4">
          {p.has_map && !p.map_stale && (
            <span
              className="text-[11px] text-ink-faint"
              title="a page-level index lets agents jump straight to the relevant pages"
            >
              indexed
            </span>
          )}
          {p.has_map && p.map_stale && (
            <span
              className="text-[11px] text-warn"
              title="re-extracted since the index was built — rebuild via CLI paper-index"
            >
              index stale
            </span>
          )}
        </td>
        <td className="pr-3 text-right whitespace-nowrap">
          <a
            href={`/api/papers/${encodeURIComponent(p.id)}/file`}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-ink-dim transition-colors hover:text-ink"
            title="open the original file"
          >
            original
          </a>
          <button
            className="ml-4 text-xs text-ink-dim transition-colors hover:text-ink"
            onClick={() => void del()}
          >
            {armed ? 'Confirm delete' : 'Delete'}
          </button>
        </td>
      </tr>
      {err && (
        <tr className="border-b border-edge/60">
          <td colSpan={6} className="py-1.5 pr-3 pl-3 text-right text-[11px] text-danger">
            {err}
          </td>
        </tr>
      )}
    </>
  )
}

/** One file's journey through the upload strip. Keyed by a sequence
 * number, not the filename — the same name can be dropped twice. */
interface UploadItem {
  key: number
  name: string
  status: 'uploading' | 'shelved' | 'already' | 'error'
  detail?: string
}

export default function Papers() {
  const { data, error, loading, refresh } = usePoll<{ papers: PaperShelfItem[] }>(
    '/api/papers',
    15000,
  )
  const [uploads, setUploads] = useState<UploadItem[]>([])
  const seq = useRef(0)
  const fileInput = useRef<HTMLInputElement>(null)
  // Counter, not boolean: dragging over child elements fires
  // leave/enter pairs that a boolean would read as "left the page".
  const [dragDepth, setDragDepth] = useState(0)

  const settle = (key: number, patch: Partial<UploadItem>) => {
    setUploads((u) => u.map((x) => (x.key === key ? { ...x, ...patch } : x)))
    // successes clear themselves after a beat; errors stay until dismissed
    if (patch.status !== 'error')
      window.setTimeout(
        () => setUploads((u) => u.filter((x) => x.key !== key)),
        4000,
      )
  }

  /** Sequential on purpose: PDF extraction is real server work, and a
   * strip that fills top-to-bottom reads as progress. Suffix checking
   * stays server-side — one validator, one wording. */
  const uploadFiles = async (files: File[]) => {
    for (const f of files) {
      const key = ++seq.current
      setUploads((u) => [...u, { key, name: f.name, status: 'uploading' }])
      try {
        const r = await apiUpload<{ id: string; already_shelved: boolean }>(
          `/api/papers/upload?filename=${encodeURIComponent(f.name)}`,
          f,
        )
        settle(key, { status: r.already_shelved ? 'already' : 'shelved' })
        refresh()
      } catch (e) {
        settle(key, { status: 'error', detail: errText(e) })
      }
    }
  }

  const hasFiles = (e: React.DragEvent) => e.dataTransfer.types.includes('Files')

  const papers = data?.papers ?? []
  // the shelf arranged by who each paper serves. The chip menu that
  // filtered these went out with the timeline's (owner, 2026-08-26):
  // the section headers already say which problem a paper is registered
  // under, and that was the question — a second control that answers it
  // again is furniture, and the browser's own find is a better filter
  // than a row of pills.
  const groups = shelfGroups(papers)
  return (
    <div
      className="relative min-h-full"
      onDragEnter={(e) => {
        if (!hasFiles(e)) return
        e.preventDefault()
        setDragDepth((d) => d + 1)
      }}
      onDragOver={(e) => {
        if (hasFiles(e)) e.preventDefault()
      }}
      onDragLeave={(e) => {
        if (hasFiles(e)) setDragDepth((d) => Math.max(0, d - 1))
      }}
      onDrop={(e) => {
        if (!hasFiles(e)) return
        e.preventDefault()
        setDragDepth(0)
        void uploadFiles([...e.dataTransfer.files])
      }}
    >
      {dragDepth > 0 && (
        <div className="pointer-events-none absolute inset-3 z-40 flex items-center justify-center rounded-xl border-2 border-dashed border-ink-faint bg-bg/85">
          <div className="text-center">
            <div className="font-display text-[18px] text-ink">Drop to shelve</div>
            <div className="mt-1 text-xs text-ink-faint">.pdf · .md · .txt · .tex</div>
          </div>
        </div>
      )}
      <div className="mx-auto max-w-6xl px-6 py-6">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-[22px] font-medium text-ink">Papers</h1>
          {papers.length > 0 && (
            <span className="tnum text-xs text-ink-faint">{papers.length}</span>
          )}
        </div>
        <div className="flex items-baseline gap-3">
          <span className="text-xs text-ink-faint">or drop files anywhere on this page</span>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept=".pdf,.md,.txt,.tex"
            className="hidden"
            onChange={(e) => {
              const files = [...(e.target.files ?? [])]
              e.target.value = '' // re-picking the same file must re-fire
              void uploadFiles(files)
            }}
          />
          <Button variant="primary" onClick={() => fileInput.current?.click()}>
            Add papers
          </Button>
        </div>
      </div>
      {/* upload strip: one line per in-flight/settled file; 422 details
          are written for humans — show them whole */}
      {uploads.length > 0 && (
        <div className="mb-3 space-y-1">
          {uploads.map((u) => (
            <div key={u.key} className="flex items-baseline gap-2 text-[12px]">
              <span className="shrink-0 font-mono text-ink-dim">{u.name}</span>
              {u.status === 'uploading' && (
                <span className="text-ink-faint">uploading…</span>
              )}
              {u.status === 'shelved' && <span className="text-ink-faint">shelved</span>}
              {u.status === 'already' && (
                <span className="text-ink-faint">
                  already on the shelf (same content)
                </span>
              )}
              {u.status === 'error' && (
                <>
                  <span className="min-w-0 whitespace-pre-wrap text-danger">
                    {u.detail}
                  </span>
                  <button
                    className="shrink-0 text-[11px] text-ink-faint transition-colors hover:text-ink"
                    onClick={() =>
                      setUploads((list) => list.filter((x) => x.key !== u.key))
                    }
                  >
                    dismiss
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      )}
      {loading ? (
        <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
      ) : error && !data ? (
        <ErrorState error={error} />
      ) : papers.length === 0 ? (
        <EmptyState title="The shelf is empty">
          Papers ground the engine's citations — drop a PDF (or .md/.tex) anywhere on this
          page; the engine can also fetch cited papers on its own during a run.
        </EmptyState>
      ) : (
        <>
        <table className="w-full table-fixed border-collapse text-left">
          <thead>
            <tr className="border-b border-edge text-xs text-ink-faint">
              <th className="py-2 pr-4 pl-3 font-medium">paper</th>
              {/* size dropped (owner: low-value column) — it lives in
                  the row's hover title now */}
              <th className="w-[220px] py-2 pr-4 font-medium">registered under</th>
              <th className="w-[90px] py-2 pr-4 font-medium">
                <span title="a page-level index lets agents jump straight to the relevant pages">
                  index
                </span>
              </th>
              <th className="w-[160px] py-2 pr-3 text-right font-medium"> </th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <Fragment key={g.problem ?? ''}>
                {/* section header only when there is a second section
                    to tell apart: a single-problem shelf reads as it
                    always did */}
                {groups.length > 1 && (
                  <tr>
                    <td
                      colSpan={4}
                      className="pt-4 pb-1 pl-3 text-[10px] font-medium tracking-widest text-ink-faint/70 uppercase"
                    >
                      {g.problem ? (
                        <Link
                          to={`/problems/${encodeURIComponent(g.problem)}`}
                          className="transition-colors hover:text-ink"
                          title="open the problem"
                        >
                          {g.problem}
                        </Link>
                      ) : (
                        <span title="uploaded and never bound, or its problem was reset and the binding went with it. Bind from a problem's Intent tab.">
                          registered under no problem
                        </span>
                      )}{' '}
                      · {g.papers.length}
                    </td>
                  </tr>
                )}
                {g.papers.map((p) => (
                  <ShelfRow key={`${g.problem ?? ''}#${p.id}`} p={p} onChanged={refresh} />
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
        </>
      )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Viewer — the ORIGINAL document, browser-native rendering, with a    */
/* slim rail for switching papers without losing your place on the    */
/* shelf. The extracted text is for agents; humans get the PDF.       */
/* ------------------------------------------------------------------ */

export function PaperReader({ id }: { id: string }) {
  const { data, error } = usePoll<{ papers: PaperShelfItem[] }>('/api/papers', 30000)
  const papers = data?.papers ?? []
  const current = papers.find((p) => p.id === id) ?? null
  const fileUrl = `/api/papers/${encodeURIComponent(id)}/file`

  if (error && !data) return <ErrorState error={error} />

  return (
    <div className="flex h-full">
      <aside className="flex w-60 shrink-0 flex-col border-r border-edge bg-surface/50">
        <Link
          to="/papers"
          className="px-4 pt-4 pb-2 text-xs text-ink-faint transition-colors hover:text-ink"
        >
          ‹ all papers
        </Link>
        <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
          {papers.map((p) => (
            <Link
              key={p.id}
              to={`/papers/${encodeURIComponent(p.id)}`}
              className={`block truncate rounded-lg px-2 py-1.5 font-mono text-[12px] transition-colors ${
                p.id === id
                  ? 'bg-surface-2 text-ink'
                  : 'text-ink-dim hover:bg-surface-2/60 hover:text-ink'
              }`}
              title={p.source_name}
            >
              {p.title ?? p.source_name}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex shrink-0 items-baseline gap-4 border-b border-edge px-4 py-2.5">
          <span className="min-w-0 truncate font-mono text-[13px] text-ink">
            {current ? (current.title ?? current.source_name) : id}
          </span>
          {current && (
            <span className="tnum text-[11px] whitespace-nowrap text-ink-faint">
              {sizeLabel(current)}
            </span>
          )}
          {current && current.bound.length > 0 && (
            <span className="min-w-0 truncate text-[11px] text-ink-faint">
              cited by{' '}
              {current.bound.map((b, i) => (
                <span key={b.problem}>
                  {i > 0 && ', '}
                  <Link
                    to={`/problems/${encodeURIComponent(b.problem)}`}
                    className="font-mono text-ink-dim transition-colors hover:text-ink"
                  >
                    {b.problem}
                  </Link>
                </span>
              ))}
            </span>
          )}
          <a
            href={fileUrl}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-xs whitespace-nowrap text-ink-dim transition-colors hover:text-ink"
            title="open in its own tab"
          >
            open in tab ↗
          </a>
        </div>
        {/* browser-native PDF viewer; text sources render as plain text */}
        <iframe src={fileUrl} title={current?.source_name ?? id} className="min-h-0 w-full flex-1 border-0" />
      </div>
    </div>
  )
}
