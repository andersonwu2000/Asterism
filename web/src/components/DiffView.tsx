import { useMemo } from 'react'
import { lineDiff } from '../lib/diff'

/** Side-by-side line diff (current | proposed) for amend review. */
export default function DiffView({ left, right }: { left: string; right: string }) {
  const rows = useMemo(() => lineDiff(left, right), [left, right])
  const changed = rows.filter((r) => r.type !== 'same').length
  return (
    <div className="overflow-hidden rounded-md border border-edge">
      <div className="grid grid-cols-2 border-b border-edge bg-surface-2 text-[11px] text-ink-faint">
        <div className="px-3 py-1">current</div>
        <div className="border-l border-edge px-3 py-1">
          proposed {changed > 0 && <span className="text-warn">· {changed} changed lines</span>}
        </div>
      </div>
      <div className="max-h-96 overflow-auto font-mono text-[11px] leading-relaxed">
        {rows.map((r, i) => (
          <div key={i} className="grid grid-cols-2">
            <div
              className={`flex min-w-0 border-r border-edge px-2 whitespace-pre-wrap ${
                r.type === 'del' || r.type === 'change'
                  ? 'bg-danger/10 text-ink'
                  : r.type === 'add'
                    ? 'bg-surface'
                    : 'text-ink-dim'
              }`}
            >
              <span className="mr-2 w-7 shrink-0 text-right text-ink-faint select-none">
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
              <span className="mr-2 w-7 shrink-0 text-right text-ink-faint select-none">
                {r.rightNo ?? ''}
              </span>
              <span className="min-w-0 break-words">{r.right ?? ''}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
