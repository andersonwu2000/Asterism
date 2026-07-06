import { useMemo, useState } from 'react'
import { lineDiff } from '../lib/diff'
import type { DiffRow } from '../lib/diff'

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

function Row({ r }: { r: DiffRow }) {
  return (
    <div className="grid grid-cols-2">
      <div
        className={`flex min-w-0 border-r border-edge px-2 whitespace-pre-wrap ${
          r.type === 'del' || r.type === 'change'
            ? 'bg-danger/10 text-ink'
            : r.type === 'add'
              ? 'bg-surface'
              : 'text-ink-dim'
        }`}
      >
        <span className="tnum mr-2 w-7 shrink-0 text-right text-ink-faint select-none">
          {r.leftNo ?? ''}
        </span>
        <span className="min-w-0 break-words">{r.left ?? ''}</span>
      </div>
      <div
        className={`flex min-w-0 px-2 whitespace-pre-wrap ${
          r.type === 'add' || r.type === 'change'
            ? 'bg-ok/10 text-ink'
            : r.type === 'del'
              ? 'bg-surface'
              : 'text-ink-dim'
        }`}
      >
        <span className="tnum mr-2 w-7 shrink-0 text-right text-ink-faint select-none">
          {r.rightNo ?? ''}
        </span>
        <span className="min-w-0 break-words">{r.right ?? ''}</span>
      </div>
    </div>
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

export default function DiffView({ left, right }: { left: string; right: string }) {
  const rows = useMemo(() => lineDiff(left, right), [left, right])
  const chunks = useMemo(() => chunkRows(rows), [rows])
  const changed = rows.filter((r) => r.type !== 'same').length
  return (
    <div className="overflow-hidden rounded-md border border-edge">
      <div className="grid grid-cols-2 border-b border-edge bg-surface-2 text-[11px] text-ink-faint">
        <div className="px-3 py-1">current</div>
        <div className="border-l border-edge px-3 py-1">
          proposed{' '}
          {changed > 0 && <span className="tnum text-warn">· {changed} changed lines</span>}
        </div>
      </div>
      <div className="max-h-96 overflow-auto font-mono text-[11px] leading-relaxed">
        {chunks.map((c, i) =>
          c.kind === 'fold' && c.rows.length > 3 ? (
            <Fold key={i} rows={c.rows} />
          ) : (
            c.rows.map((r, j) => <Row key={`${i}-${j}`} r={r} />)
          ),
        )}
      </div>
    </div>
  )
}
