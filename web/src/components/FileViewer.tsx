import { useState } from 'react'
import { usePoll } from '../lib/api'

/** Read-only proofs/ + input-file viewer. Minimal hand-rolled Lean
 * highlighting (keywords / comments / strings) — dependency freeze
 * rules out a highlighter package. */

const LEAN_KEYWORDS =
  /\b(theorem|lemma|def|noncomputable|instance|inductive|structure|class|abbrev|example|by|exact|intro|intros|apply|simp|rw|rfl|calc|have|show|from|let|fun|match|with|do|then|else|if|open|import|namespace|end|section|variable|variables|universe|where|deriving|extends|mutual|sorry)\b/g

function highlightLean(src: string): string {
  const esc = src.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return esc
    .replace(/("(?:[^"\\]|\\.)*")/g, '<span class="text-ok">$1</span>')
    .replace(/(--[^\n]*)/g, '<span class="text-ink-faint italic">$1</span>')
    .replace(/(\/-[\s\S]*?-\/)/g, '<span class="text-ink-faint italic">$1</span>')
    .replace(LEAN_KEYWORDS, '<span class="text-accent">$1</span>')
}

export default function FileViewer({
  problem,
  proofFiles,
}: {
  problem: string
  proofFiles: string[]
}) {
  const files = ['Manifest.md', 'Defs.lean', ...proofFiles.map((f) => `proofs/${f}`)]
  const [selected, setSelected] = useState(files[0])
  const { data, error } = usePoll<{ path: string; content: string }>(
    `/api/problems/${encodeURIComponent(problem)}/file?path=${encodeURIComponent(selected)}`,
    10000,
  )

  return (
    <div className="flex min-h-0 flex-1">
      <div className="w-56 shrink-0 overflow-y-auto border-r border-edge py-2">
        {files.map((f) => (
          <button
            key={f}
            className={`block w-full truncate px-4 py-1.5 text-left font-mono text-xs ${
              f === selected ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:text-ink'
            }`}
            onClick={() => setSelected(f)}
            title={f}
          >
            {f}
          </button>
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
            <pre
              className="font-mono text-xs leading-relaxed whitespace-pre text-ink-dim"
              dangerouslySetInnerHTML={{ __html: highlightLean(data.content) }}
            />
          ) : (
            <pre className="font-mono text-xs leading-relaxed whitespace-pre text-ink-dim">
              {data.content}
            </pre>
          ))}
      </div>
    </div>
  )
}
