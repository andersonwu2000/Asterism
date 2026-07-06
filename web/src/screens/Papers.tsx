import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, apiDelete, apiGet, apiPost, usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { Button, EmptyState, ErrorState } from '../components/ui'
import type { PaperShelfItem, PaperText } from '../lib/types'

/*
 * The paper shelf: every source the engine can ground its citations in.
 * One flat table (Board vocabulary) — a shelf of tens, not thousands.
 * The reader below renders the extracted text as-is; the `original`
 * link opens the untouched PDF for anything extraction mangled.
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
  const [err, setErr] = useState<string | null>(null)
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
      <tr className="h-9 border-b border-edge/60 transition-colors duration-150 hover:bg-surface">
        <td className="pr-4 pl-3">
          <Link
            to={`/papers/${encodeURIComponent(p.id)}`}
            className="block truncate font-mono text-[13px] text-ink transition-colors hover:text-starlight"
            title={`read ${p.source_name}`}
          >
            {p.source_name}
          </Link>
        </td>
        <td className="pr-4 font-mono text-[11px] text-ink-faint">{p.id}</td>
        <td className="tnum pr-4 text-xs whitespace-nowrap text-ink-dim">{sizeLabel(p)}</td>
        <td className="pr-4">
          {p.bound.length === 0 ? (
            <span className="text-xs text-ink-faint">—</span>
          ) : (
            <span className="truncate text-xs">
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

export default function Papers() {
  const { data, error, loading, refresh } = usePoll<{ papers: PaperShelfItem[] }>(
    '/api/papers',
    15000,
  )
  const [path, setPath] = useState('')
  const [adding, setAdding] = useState(false)
  const [addErr, setAddErr] = useState<string | null>(null)

  const add = async () => {
    const p = path.trim()
    if (p === '' || adding) return
    setAdding(true)
    setAddErr(null)
    try {
      await apiPost('/api/papers/add', { path: p })
      setPath('')
      refresh()
    } catch (e) {
      setAddErr(errText(e))
    } finally {
      setAdding(false)
    }
  }

  const papers = data?.papers ?? []
  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      {/* the add box stays above whatever the list area shows — adding
          a first paper IS the empty state's call to action */}
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-[22px] font-medium text-ink">Papers</h1>
          {papers.length > 0 && (
            <span className="tnum text-xs text-ink-faint">{papers.length}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <input
            className="w-96 rounded-md border border-edge bg-surface px-2.5 py-1.5 font-mono text-xs text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
            placeholder={'C:\\path\\to\\paper.pdf — or .md/.txt/.tex'}
            value={path}
            onChange={(e) => setPath(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void add()
            }}
            spellCheck={false}
          />
          <Button
            variant="primary"
            disabled={adding || path.trim() === ''}
            onClick={() => void add()}
          >
            {adding ? 'Adding…' : 'Add'}
          </Button>
        </div>
      </div>
      {/* 404/422 details are written for humans — show them whole */}
      {addErr && (
        <div className="mb-3 text-[11px] whitespace-pre-wrap text-danger">{addErr}</div>
      )}
      {loading ? (
        <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
      ) : error && !data ? (
        <ErrorState error={error} />
      ) : papers.length === 0 ? (
        <EmptyState title="The shelf is empty">
          Papers ground the engine's citations — add a PDF (or .md/.tex) by its path above;
          the Scholar pipeline can also fetch cited papers on its own during a run.
        </EmptyState>
      ) : (
        <table className="w-full table-fixed border-collapse text-left">
          <thead>
            <tr className="border-b border-edge text-xs text-ink-faint">
              <th className="py-2 pr-4 pl-3 font-medium">paper</th>
              <th className="w-[110px] py-2 pr-4 font-medium">id</th>
              <th className="w-[140px] py-2 pr-4 font-medium">size</th>
              <th className="w-[220px] py-2 pr-4 font-medium">cited by</th>
              <th className="w-[90px] py-2 pr-4 font-medium">
                <span title="a page-level index lets agents jump straight to the relevant pages">
                  index
                </span>
              </th>
              <th className="w-[160px] py-2 pr-3 text-right font-medium"> </th>
            </tr>
          </thead>
          <tbody>
            {papers.map((p) => (
              <ShelfRow key={p.id} p={p} onChanged={refresh} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Reader — the extracted text, one page anchor per `## p.N` line.     */
/* ------------------------------------------------------------------ */

interface Segment {
  page: number | null
  text: string
}

function splitPages(text: string): Segment[] {
  const segs: Segment[] = [{ page: null, text: '' }]
  for (const line of text.split('\n')) {
    const m = /^## p\.(\d+)\s*$/.exec(line)
    if (m) segs.push({ page: Number(m[1]), text: '' })
    else {
      const s = segs[segs.length - 1]
      s.text = s.text === '' ? line : `${s.text}\n${line}`
    }
  }
  return segs.filter((s) => s.page !== null || s.text.trim() !== '')
}

export function PaperReader({ id }: { id: string }) {
  const [data, setData] = useState<PaperText | null>(null)
  const [error, setError] = useState<Error | null>(null)

  // one-shot fetch — extracted text is immutable per paper id (a
  // re-extraction goes through paper-add, which the shelf reflects)
  useEffect(() => {
    let cancelled = false
    setData(null)
    setError(null)
    apiGet<PaperText>(`/api/papers/${encodeURIComponent(id)}/text`)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e as Error))
    return () => {
      cancelled = true
    }
  }, [id])

  const segments = useMemo(() => (data ? splitPages(data.text) : []), [data])
  const pageNums = segments.filter((s) => s.page !== null).map((s) => s.page as number)

  if (error) return <ErrorState error={error} />
  if (!data) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>

  return (
    <div className="mx-auto max-w-[80ch] px-6 py-6">
      <Link to="/papers" className="text-xs text-ink-faint transition-colors hover:text-ink">
        ‹ papers
      </Link>
      <div className="mt-2 mb-6 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="font-display min-w-0 text-[22px] font-medium break-all text-ink">
          {data.source_name}
        </h1>
        <a
          href={`/api/papers/${encodeURIComponent(data.id)}/file`}
          target="_blank"
          rel="noreferrer"
          className="text-xs whitespace-nowrap text-ink-dim transition-colors hover:text-ink"
          title="open the original file"
        >
          original ↗
        </a>
        {pageNums.length > 1 && (
          <select
            className="rounded border border-edge bg-surface px-2 py-1 text-xs text-ink-dim focus:border-ink-faint focus:outline-none"
            value=""
            onChange={(e) => {
              if (e.target.value === '') return
              document
                .getElementById(`p-${e.target.value}`)
                ?.scrollIntoView({ block: 'start' })
              e.target.value = ''
            }}
          >
            <option value="">jump to page…</option>
            {pageNums.map((n) => (
              <option key={n} value={n}>
                p. {n}
              </option>
            ))}
          </select>
        )}
      </div>
      {segments.map((s, i) => (
        <section key={i}>
          {s.page !== null && (
            <div
              id={`p-${s.page}`}
              className="mt-8 mb-3 flex items-center gap-3 first:mt-0 scroll-mt-4"
            >
              <span className="text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
                p. {s.page}
              </span>
              <span className="h-px flex-1 bg-edge" />
            </div>
          )}
          {s.text.trim() !== '' && (
            <div className="text-sm leading-relaxed whitespace-pre-wrap text-ink-dim">
              {s.text}
            </div>
          )}
        </section>
      ))}
    </div>
  )
}
