import { useEffect, useMemo, useRef, useState } from 'react'
import { lineDiff, wordDiff } from '../lib/diff'
import type { DiffRow, Seg } from '../lib/diff'

/*
 * Side-by-side line diff (current | proposed) for amend review.
 * Defaults to changed hunks ± context; unchanged runs collapse into
 * expandable "⋯ N unchanged lines" separators (a 28-line change in a
 * 200-line file should not open on 19 identical lines).
 */

const CONTEXT = 2

type Chunk = { kind: 'rows'; rows: DiffRow[] } | { kind: 'fold'; rows: DiffRow[] }

function chunkRows(rows: DiffRow[]): Chunk[] {
  const keep = new Array<boolean>(rows.length).fill(false)
  rows.forEach((r, i) => {
    if (r.type !== 'same') {
      for (let j = Math.max(0, i - CONTEXT); j <= Math.min(rows.length - 1, i + CONTEXT); j++) {
        keep[j] = true
      }
    }
  })
  const chunks: Chunk[] = []
  rows.forEach((r, i) => {
    const kind: Chunk['kind'] = keep[i] ? 'rows' : 'fold'
    const last = chunks[chunks.length - 1]
    if (!last || last.kind !== kind) {
      chunks.push({ kind, rows: [r] })
    } else {
      last.rows.push(r)
    }
  })
  return chunks
}

/* Unified rendering: full-measure lines survive Lean statements; the
 * old side-by-side gave each pane ~400px and wrapped every math line
 * 2–4 times (design review). change → del line + add line stacked. */
function Line({
  no,
  text,
  segs,
  tone,
  sign,
}: {
  no: number | null
  text?: string
  segs?: Seg[]
  tone: 'same' | 'del' | 'add'
  sign: string
}) {
  return (
    <div
      className={`flex min-w-0 px-2 whitespace-pre-wrap ${
        tone === 'del'
          ? 'bg-white/[0.025] text-ink-dim'
          : tone === 'add'
            ? 'bg-white/[0.07] text-ink'
            : 'text-ink-dim'
      }`}
    >
      <span className="tnum mr-1 w-8 shrink-0 text-right text-ink-faint select-none">
        {no ?? ''}
      </span>
      <span className="mr-2 w-3 shrink-0 text-ink-faint select-none">{sign}</span>
      <span className="min-w-0 break-words">
        {/* achromatic word-diff: removed words are struck, added words
            sit on a light plate. Removed content stays READABLE (dim,
            not faint) — it is exactly what the reviewer must weigh
            before giving it up (cold-eye) */}
        {segs
          ? segs.map((s, i) =>
              s.changed ? (
                <span
                  key={i}
                  className={`rounded-[2px] ${
                    tone === 'del'
                      ? 'text-ink-dim line-through decoration-ink-faint/70'
                      : 'bg-white/15 text-ink'
                  }`}
                >
                  {s.text}
                </span>
              ) : (
                <span key={i}>{s.text}</span>
              ),
            )
          : text}
      </span>
    </div>
  )
}

function Row({ r }: { r: DiffRow }) {
  if (r.type === 'same') return <Line no={r.rightNo} text={r.right ?? ''} tone="same" sign=" " />
  if (r.type === 'change') {
    // paired edit: highlight the words that moved, not the whole line
    const { left, right } = wordDiff(r.left ?? '', r.right ?? '')
    return (
      <>
        <Line no={r.leftNo} segs={left} tone="del" sign="−" />
        <Line no={r.rightNo} segs={right} tone="add" sign="+" />
      </>
    )
  }
  return (
    <>
      {r.type === 'del' && <Line no={r.leftNo} text={r.left ?? ''} tone="del" sign="−" />}
      {r.type === 'add' && <Line no={r.rightNo} text={r.right ?? ''} tone="add" sign="+" />}
    </>
  )
}

function Fold({ rows }: { rows: DiffRow[] }) {
  const [open, setOpen] = useState(false)
  if (open) {
    return (
      <>
        {rows.map((r, i) => (
          <Row key={i} r={r} />
        ))}
      </>
    )
  }
  return (
    <button
      className="block w-full border-y border-edge/60 bg-surface py-0.5 text-center font-sans text-[11px] text-ink-faint transition-colors hover:text-ink"
      onClick={() => setOpen(true)}
    >
      ⋯ {rows.length} unchanged line{rows.length === 1 ? '' : 's'}
    </button>
  )
}

export default function DiffView({
  left,
  right,
  label = 'current → proposed',
}: {
  left: string
  right: string
  /** what the two sides ARE — the amend review's default is one case;
   * a Programme diff is one revision against the next, and reusing
   * the amend wording there said the wrong thing about both */
  label?: string
}) {
  const rows = useMemo(() => lineDiff(left, right), [left, right])
  const chunks = useMemo(() => chunkRows(rows), [rows])
  const changed = rows.filter((r) => r.type !== 'same').length
  // The bottom edge must SAY there is more, not merely fade: an
  // unconditional gradient ended mid-sentence and read as truncation
  // (cold-eye). Shown only while scrollable-and-not-at-bottom.
  const scrollRef = useRef<HTMLDivElement>(null)
  const [more, setMore] = useState(false)
  const check = () => {
    const el = scrollRef.current
    if (el) setMore(el.scrollHeight - el.scrollTop - el.clientHeight > 8)
  }
  useEffect(check, [chunks])
  return (
    <div className="overflow-hidden rounded-lg border border-edge">
      <div className="flex items-center gap-2 border-b border-edge bg-surface-2 px-3 py-1 text-[11px] text-ink-faint">
        <span>{label}</span>
        {changed > 0 && <span className="tnum">· {changed} changed lines</span>}
      </div>
      {/* re-check on fold clicks: opening one grows scrollHeight */}
      <div className="relative" onClickCapture={() => window.setTimeout(check, 0)}>
        <div
          ref={scrollRef}
          onScroll={check}
          className="max-h-96 overflow-auto font-mono text-[11px] leading-relaxed"
        >
          {chunks.map((c, i) =>
            c.kind === 'fold' && c.rows.length > 3 ? (
              <Fold key={i} rows={c.rows} />
            ) : (
              c.rows.map((r, j) => <Row key={`${i}-${j}`} r={r} />)
            ),
          )}
        </div>
        {more && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex h-8 items-end justify-center bg-gradient-to-t from-surface to-transparent">
            <span className="mb-0.5 rounded-full bg-surface-2 px-2 text-[10px] text-ink-dim">
              ↓ scroll for the rest
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
