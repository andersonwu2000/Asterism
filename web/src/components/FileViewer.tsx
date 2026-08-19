import { useEffect, useState } from 'react'
import { usePoll } from '../lib/api'
import { Lean } from '../lib/lean'
import { renderProse } from '../lib/prose'

/** Read-only proofs/ + input-file viewer. Lean highlighting comes
 * from the shared tokenizer in lib/lean; .md files render through the
 * ONE prose engine (lib/prose.tsx document mode — the hand-rolled
 * HTML-string renderer that lived here missed math, ordered lists and
 * soft-wrap joining, and was the third private markdown dialect). */

export default function FileViewer({
  problem,
  proofFiles,
  initialFile,
}: {
  problem: string
  proofFiles: string[]
  initialFile?: string | null
}) {
  // the problem's hand-authored files (v40 USER_INTENT_FILES — the
  // goal itself is no longer a file; it lives on the Intent tab)
  const files = ['Root.lean', 'Defs.lean', ...proofFiles.map((f) => `proofs/${f}`)]
  const [selected, setSelected] = useState(
    initialFile && files.includes(initialFile) ? initialFile : files[0],
  )
  useEffect(() => {
    if (initialFile && files.includes(initialFile)) setSelected(initialFile)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialFile])
  const { data, error } = usePoll<{ path: string; content: string }>(
    `/api/problems/${encodeURIComponent(problem)}/file?path=${encodeURIComponent(selected)}`,
    10000,
  )

  return (
    <div className="flex min-h-0 flex-1">
      <div className="w-72 shrink-0 overflow-y-auto border-r border-edge py-2">
        {files.map((f, i) => (
          <div key={f}>
            {/* one "proofs/" group header instead of a 130-row prefix wall */}
            {f.startsWith('proofs/') && !files[i - 1]?.startsWith('proofs/') && (
              <div className="mt-2 px-4 pb-1 text-[10px] font-medium tracking-widest text-ink-faint/70 uppercase">
                proofs · {files.length - i}
              </div>
            )}
            <button
              className={`block w-full truncate px-4 py-1.5 text-left font-mono text-xs ${
                f === selected ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:text-ink'
              }`}
              onClick={() => setSelected(f)}
              title={f}
            >
              {f.startsWith('proofs/L_') ? f.slice('proofs/L_'.length) : f.startsWith('proofs/') ? f.slice('proofs/'.length) : f}
            </button>
          </div>
        ))}
      </div>
      <div className="min-w-0 flex-1 overflow-auto p-4">
        {error && !data && (
          <div className="text-xs text-ink-faint">
            {selected} — not found (file may not exist for this problem).
          </div>
        )}
        {data &&
          data.path === selected &&
          (selected.endsWith('.lean') ? (
            <pre className="font-mono text-xs leading-relaxed whitespace-pre text-ink-dim">
              <Lean code={data.content} />
            </pre>
          ) : selected.endsWith('.md') ? (
            <div className="max-w-[78ch] text-[13px] leading-relaxed text-ink-dim">
              {renderProse(data.content, { mode: 'document', frontmatter: true })}
            </div>
          ) : (
            <pre className="font-mono text-xs leading-relaxed whitespace-pre text-ink-dim">
              {data.content}
            </pre>
          ))}
      </div>
    </div>
  )
}
