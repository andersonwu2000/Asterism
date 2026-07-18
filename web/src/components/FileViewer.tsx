import { useEffect, useState } from 'react'
import { usePoll } from '../lib/api'
import { Lean, leanHtml } from '../lib/lean'

/** Read-only proofs/ + input-file viewer. Lean highlighting comes
 * from the shared tokenizer in lib/lean (the old regex-replace chain
 * could match keywords inside its own emitted markup). */

function escapeHtml(src: string): string {
  return src.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/* ------------------------------------------------------------------ */
/* Markdown (hand-rolled, dependency freeze): headings, lists, fences,
 * frontmatter, inline code/bold. Manifest.md is the most-read document
 * in the product — it deserves typography, not raw mono.              */
/* ------------------------------------------------------------------ */

function mdInline(s: string): string {
  // `code` spans re-highlight from the RAW text (leanHtml escapes
  // itself); everything else escapes first
  const parts = s.split(/(`[^`]+`)/)
  return parts
    .map((p) =>
      p.startsWith('`') && p.endsWith('`') && p.length > 2
        ? `<code class="rounded-md bg-surface-2 px-1 py-px font-mono text-[12px] text-ink">${leanHtml(p.slice(1, -1))}</code>`
        : escapeHtml(p).replace(
            /\*\*([^*]+)\*\*/g,
            '<strong class="font-semibold text-ink">$1</strong>',
          ),
    )
    .join('')
}

function Markdown({ src }: { src: string }) {
  const out: string[] = []
  const lines = src.split('\n')
  let i = 0
  // frontmatter: render as a quiet mono preamble block
  if (lines[0]?.trim() === '---') {
    const end = lines.indexOf('---', 1)
    if (end > 0) {
      out.push(
        `<pre class="mb-4 rounded-lg border border-edge bg-surface px-3 py-2 font-mono text-[11px] leading-relaxed text-ink-faint">${escapeHtml(
          lines.slice(1, end).join('\n'),
        )}</pre>`,
      )
      i = end + 1
    }
  }
  let listOpen = false
  const closeList = () => {
    if (listOpen) {
      out.push('</ul>')
      listOpen = false
    }
  }
  while (i < lines.length) {
    const line = lines[i]
    if (line.startsWith('```')) {
      closeList()
      const end = lines.findIndex((l, j) => j > i && l.startsWith('```'))
      const body = lines.slice(i + 1, end === -1 ? undefined : end).join('\n')
      out.push(
        `<pre class="my-3 overflow-x-auto rounded-lg border border-edge bg-bg px-3 py-2 font-mono text-[12px] leading-relaxed text-ink-dim">${leanHtml(body)}</pre>`,
      )
      i = end === -1 ? lines.length : end + 1
      continue
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line)
    if (h) {
      closeList()
      const level = h[1].length
      const cls =
        level === 1
          ? 'font-display mt-5 mb-2 text-[21px] font-medium text-ink'
          : level === 2
            ? 'font-display mt-5 mb-1.5 text-[17px] font-medium text-ink'
            : 'mt-4 mb-1 text-[13px] font-semibold text-ink'
      out.push(`<h${level} class="${cls}">${mdInline(h[2])}</h${level}>`)
    } else if (/^\s*[-*]\s+/.test(line)) {
      if (!listOpen) {
        out.push('<ul class="my-2 flex flex-col gap-1">')
        listOpen = true
      }
      out.push(
        `<li class="relative pl-4 text-[13px] leading-relaxed text-ink-dim before:absolute before:left-0 before:text-ink-faint before:content-['·']">${mdInline(
          line.replace(/^\s*[-*]\s+/, ''),
        )}</li>`,
      )
    } else if (line.trim() === '') {
      closeList()
    } else {
      closeList()
      out.push(`<p class="my-1.5 text-[13px] leading-relaxed text-ink-dim">${mdInline(line)}</p>`)
    }
    i++
  }
  closeList()
  return (
    <div
      className="max-w-[78ch]"
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: out.join('') }}
    />
  )
}

export default function FileViewer({
  problem,
  proofFiles,
  initialFile,
}: {
  problem: string
  proofFiles: string[]
  initialFile?: string | null
}) {
  const files = ['Manifest.md', 'Defs.lean', ...proofFiles.map((f) => `proofs/${f}`)]
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
            <Markdown src={data.content} />
          ) : (
            <pre className="font-mono text-xs leading-relaxed whitespace-pre text-ink-dim">
              {data.content}
            </pre>
          ))}
      </div>
    </div>
  )
}
