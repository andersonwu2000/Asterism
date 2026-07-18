import type { ReactNode } from 'react'
import { navigate } from './router'
import { Lean } from './lean'
import { withMath } from './tex'

/*
 * Markdown-lite for MACHINE-AUTHORED prose the human reads: chat
 * answers, the Programme. One renderer, two rules learned elsewhere:
 * fences and $math$ are tokenized out before any inline styling
 * (QPaper ordering lesson), and citation links come from bracket
 * tokens the model emits while the CLIENT owns every route — a
 * hallucinated citation can point at the wrong object, never invent
 * a destination. NOT for the Manifest editor overlay (lib/markdown
 * .tsx is metric-faithful colouring, a different job).
 */

const CITE_RE = /\[(problem|goal|library|paper):([^[\]\n]+)\]/g

function citeTarget(kind: string, body: string): { to: string; label: string } | null {
  const parts = body.split(':')
  if (kind === 'problem') return { to: `/problems/${body}`, label: body }
  if (kind === 'goal') {
    if (parts.length < 2) return null
    const slug = parts.slice(1).join(':')
    return { to: `/problems/${parts[0]}`, label: slug }
  }
  if (kind === 'library') return { to: `/library/${body}`, label: body }
  if (kind === 'paper') return { to: `/papers/${body}`, label: body }
  return null
}

function renderCites(seg: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let m: RegExpExecArray | null
  CITE_RE.lastIndex = 0
  while ((m = CITE_RE.exec(seg)) !== null) {
    if (m.index > last) out.push(seg.slice(last, m.index))
    const t = citeTarget(m[1], m[2])
    if (t === null) {
      out.push(m[0])
    } else {
      const to = t.to
      out.push(
        <span
          key={`${keyBase}c${m.index}`}
          role="link"
          tabIndex={0}
          className="cursor-pointer font-mono text-[0.92em] text-ink underline decoration-ink-faint decoration-dotted underline-offset-2 hover:decoration-ink"
          onClick={() => navigate(to)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') navigate(to)
          }}
        >
          {t.label}
        </span>,
      )
    }
    last = m.index + m[0].length
  }
  if (last < seg.length) out.push(seg.slice(last))
  return out
}

function renderInline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = []
  text.split(/(`[^`\n]+`)/).forEach((part, i) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      out.push(
        <code key={`${keyBase}i${i}`} className="rounded-md bg-surface-2 px-1 font-mono text-[0.92em]">
          {part.slice(1, -1)}
        </code>,
      )
      return
    }
    out.push(
      ...withMath(part, (seg, j) => (
        <span key={`${keyBase}i${i}m${j}`}>
          {seg.split(/(\*\*[^*\n]+\*\*)/).map((b, k) =>
            b.startsWith('**') && b.endsWith('**') && b.length > 4 ? (
              <strong key={k} className="font-medium text-ink">
                {renderCites(b.slice(2, -2), `${keyBase}b${k}`)}
              </strong>
            ) : (
              <span key={k}>{renderCites(b, `${keyBase}p${i}.${j}.${k}`)}</span>
            ),
          )}
        </span>
      )),
    )
  })
  return out
}

/** Full prose body: fenced code (lean-colored), paragraphs, lists,
 * headings. `headings: true` renders #/## lines as quiet headers
 * (the Programme's four sections); false strips the marks (chat). */
export function renderProse(text: string, { headings = false } = {}): ReactNode {
  const blocks = text.split(/(```[\s\S]*?(?:```|$))/)
  return (
    <div className="space-y-2">
      {blocks.map((block, bi) => {
        if (block.startsWith('```')) {
          const body = block.replace(/^```[^\n]*\n?/, '').replace(/```\s*$/, '')
          return (
            <pre
              key={bi}
              className="overflow-x-auto rounded-lg border border-edge bg-surface p-2.5 font-mono text-[12px] leading-relaxed"
            >
              <Lean code={body.replace(/\n$/, '')} />
            </pre>
          )
        }
        const paras = block.split(/\n{2,}/).filter((p) => p.trim() !== '')
        return paras.map((para, pi) => {
          const lines = para.split('\n')
          const isList = lines.every((l) => /^\s*[-*•]\s+/.test(l) || l.trim() === '')
          if (isList) {
            return (
              <ul key={`${bi}.${pi}`} className="space-y-1 pl-4">
                {lines
                  .filter((l) => l.trim() !== '')
                  .map((l, li) => (
                    <li key={li} className="list-disc marker:text-ink-faint">
                      {renderInline(l.replace(/^\s*[-*•]\s+/, ''), `${bi}.${pi}.${li}`)}
                    </li>
                  ))}
              </ul>
            )
          }
          // a heading owns the paragraph's first line even without a
          // blank line after it (the Programme writes `## Argument`
          // flush against its text)
          const h = headings ? /^(#{1,6})\s+(.*)$/.exec(lines[0]) : null
          if (h) {
            const rest = lines.slice(1).join('\n').trim()
            return (
              <div key={`${bi}.${pi}`}>
                {h[1].length === 1 ? (
                  <h3 className="pt-1 text-[15px] font-medium text-ink">
                    {renderInline(h[2], `${bi}.${pi}h`)}
                  </h3>
                ) : (
                  <h4 className="pt-2 text-[11px] font-medium tracking-wider text-ink-faint uppercase">
                    {h[2]}
                  </h4>
                )}
                {rest !== '' && (
                  <p className="mt-1.5 whitespace-pre-wrap">
                    {renderInline(rest, `${bi}.${pi}`)}
                  </p>
                )}
              </div>
            )
          }
          return (
            <p key={`${bi}.${pi}`} className="whitespace-pre-wrap">
              {renderInline(para.replace(/^#{1,6}\s+/, ''), `${bi}.${pi}`)}
            </p>
          )
        })
      })}
    </div>
  )
}
