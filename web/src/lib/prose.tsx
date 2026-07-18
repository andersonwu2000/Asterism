import type { ReactNode } from 'react'
import { navigate } from './router'
import { Lean } from './lean'
import { withMath } from './tex'
import { emitChatGoalHover, emitChatGoalOpen } from './chatFocus'

/*
 * Markdown-lite for MACHINE-AUTHORED prose the human reads: chat
 * answers, the Programme. Block engine shaped by QPaper's field-tested
 * renderer (chat-utils.js renderMarkdown): fences and $math$ tokenized
 * out before inline styling, TeX \(..\)/\[..\] normalized to dollar
 * form (models drift off the prompt's delimiter instruction), ordered/
 * mixed lists, quotes, rules and tables as real blocks. One deliberate
 * departure: single newlines inside a paragraph JOIN AS SPACES
 * (CommonMark soft break) — our authors write 72-column hard-wrapped
 * prose (the Programme, plan notes), and QPaper's <br> treatment
 * renders that as a ragged column. Citation links come from bracket
 * tokens the model emits while the CLIENT owns every route.
 *
 * NOT for the Manifest editor overlay (lib/markdown.tsx is metric-
 * faithful colouring, a different job).
 */

const CITE_RE = /\[(problem|goal|library|paper):([^[\]\n]+)\]/g

function citeTarget(
  kind: string,
  body: string,
): { to: string; label: string; goal?: { problem: string; slug: string } } | null {
  const parts = body.split(':')
  if (kind === 'problem') return { to: `/problems/${body}`, label: body }
  if (kind === 'goal') {
    if (parts.length < 2) return null
    const slug = parts.slice(1).join(':')
    return { to: `/problems/${parts[0]}`, label: slug, goal: { problem: parts[0], slug } }
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
      const { to, goal } = t
      const open = () => {
        // goal citations pin their star. A screen already showing that
        // sky claims the open in place (no navigation); otherwise the
        // pending-open survives the navigation and the problem screen
        // consumes it on arrival.
        if (goal && emitChatGoalOpen(goal)) return
        navigate(to)
      }
      out.push(
        <span
          key={`${keyBase}c${m.index}`}
          role="link"
          tabIndex={0}
          className="cursor-pointer font-mono text-[0.92em] text-ink underline decoration-ink-faint decoration-dotted underline-offset-2 hover:decoration-ink"
          onClick={open}
          onKeyDown={(e) => {
            if (e.key === 'Enter') open()
          }}
          onMouseEnter={goal ? () => emitChatGoalHover(goal) : undefined}
          onMouseLeave={goal ? () => emitChatGoalHover(null) : undefined}
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

/** Inline pipeline, exported for renderers that keep their own block
 * shell (the Library chapter's docstring cards). `code` spans go
 * through the Lean tokenizer — code is the one coloured thing on every
 * screen (DESIGN.md) — then $math$, then **bold** / *emphasis* /
 * citation tokens on the rest. */
export function renderInline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = []
  text.split(/(`[^`\n]+`)/).forEach((part, i) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      out.push(
        <code key={`${keyBase}i${i}`} className="rounded-md bg-surface-2 px-1 font-mono text-[0.92em] text-ink">
          <Lean code={part.slice(1, -1)} />
        </code>,
      )
      return
    }
    out.push(
      ...withMath(part, (seg, j) => (
        <span key={`${keyBase}i${i}m${j}`}>
          {seg.split(/(\*\*[^*\n]+\*\*|\*[^*\s][^*\n]*\*)/).map((b, k) =>
            b.startsWith('**') && b.endsWith('**') && b.length > 4 ? (
              <strong key={k} className="font-medium text-ink">
                {renderCites(b.slice(2, -2), `${keyBase}b${k}`)}
              </strong>
            ) : b.startsWith('*') && b.endsWith('*') && b.length > 2 ? (
              <em key={k}>{renderCites(b.slice(1, -1), `${keyBase}e${k}`)}</em>
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

// -- block engine ------------------------------------------------------------

const BULLET_RE = /^\s*[-*•]\s+/
const ORDERED_RE = /^\s*\d+[.)]\s+/
const QUOTE_RE = /^\s*>\s?/
// hard-wrap continuation: an indented line that is not itself a marker
const CONT_RE = /^\s{2,}\S/

type Run =
  | { type: 'p'; text: string }
  | { type: 'ul' | 'ol'; items: string[] }
  | { type: 'quote'; text: string }

/** One paragraph-block → runs of paragraphs / lists / quotes. Single
 * newlines join as spaces; indented continuations belong to the item
 * above them (72-column sources wrap list items too). */
function parseRuns(lines: string[]): Run[] {
  const runs: Run[] = []
  const last = () => runs[runs.length - 1]
  for (const line of lines) {
    if (line.trim() === '') continue
    if (QUOTE_RE.test(line)) {
      const text = line.replace(QUOTE_RE, '')
      const l = last()
      if (l?.type === 'quote') l.text += ' ' + text
      else runs.push({ type: 'quote', text })
    } else if (BULLET_RE.test(line)) {
      const item = line.replace(BULLET_RE, '')
      const l = last()
      if (l?.type === 'ul') l.items.push(item)
      else runs.push({ type: 'ul', items: [item] })
    } else if (ORDERED_RE.test(line)) {
      const item = line.replace(ORDERED_RE, '')
      const l = last()
      if (l?.type === 'ol') l.items.push(item)
      else runs.push({ type: 'ol', items: [item] })
    } else {
      const l = last()
      if ((l?.type === 'ul' || l?.type === 'ol') && CONT_RE.test(line)) {
        l.items[l.items.length - 1] += ' ' + line.trim()
      } else if (l?.type === 'p') {
        l.text += ' ' + line.trim()
      } else {
        runs.push({ type: 'p', text: line.trim() })
      }
    }
  }
  return runs
}

function renderRuns(runs: Run[], keyBase: string): ReactNode[] {
  return runs.map((r, i) => {
    if (r.type === 'p')
      return <p key={`${keyBase}r${i}`}>{renderInline(r.text, `${keyBase}r${i}`)}</p>
    if (r.type === 'quote')
      return (
        <blockquote
          key={`${keyBase}r${i}`}
          className="border-l-2 border-edge-strong pl-3 text-ink-faint italic"
        >
          {renderInline(r.text, `${keyBase}r${i}`)}
        </blockquote>
      )
    const Tag = r.type
    return (
      <Tag
        key={`${keyBase}r${i}`}
        className={`space-y-1 pl-4 ${r.type === 'ol' ? 'list-decimal' : 'list-disc'} marker:text-ink-faint`}
      >
        {r.items.map((it, li) => (
          <li key={li}>{renderInline(it, `${keyBase}r${i}.${li}`)}</li>
        ))}
      </Tag>
    )
  })
}

function renderTable(lines: string[], keyBase: string): ReactNode {
  const cells = (l: string) =>
    l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
  const head = cells(lines[0])
  const rows = lines.slice(2).filter((l) => l.trim().startsWith('|')).map(cells)
  return (
    <div key={keyBase} className="overflow-x-auto">
      <table className="text-[0.95em]">
        <thead>
          <tr>
            {head.map((c, i) => (
              <th key={i} className="border-b border-edge-strong px-2 py-1 text-left font-medium text-ink">
                {renderInline(c, `${keyBase}h${i}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((c, ci) => (
                <td key={ci} className="border-b border-edge px-2 py-1 align-top">
                  {renderInline(c, `${keyBase}${ri}.${ci}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Full prose body. `mode: 'chat'` = compact, heading marks stripped;
 * `mode: 'document'` = a reading page — real headings (the Programme's
 * title + sections, the Manifest in the Files tab), more air between
 * blocks. `frontmatter` renders a leading `---` block as a quiet mono
 * preamble instead of prose (Manifest.md settings). */
export function renderProse(
  text: string,
  {
    mode = 'chat',
    frontmatter = false,
  }: { mode?: 'chat' | 'document'; frontmatter?: boolean } = {},
): ReactNode {
  const doc = mode === 'document'
  let fmBlock: ReactNode = null
  if (frontmatter && text.startsWith('---\n')) {
    const end = text.indexOf('\n---', 4)
    if (end > 0) {
      fmBlock = (
        <pre className="rounded-lg border border-edge bg-surface px-3 py-2 font-mono text-[11px] leading-relaxed text-ink-faint">
          {text.slice(4, end)}
        </pre>
      )
      text = text.slice(end + 4).replace(/^\n+/, '')
    }
  }
  const blocks = text.split(/(```[\s\S]*?(?:```|$))/)
  return (
    <div className={doc ? 'space-y-3' : 'space-y-2'}>
      {fmBlock}
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
        // TeX delimiter drift (QPaper: models emit \(..\)/\[..\] no
        // matter what the prompt says) — normalized outside fences only
        const prose = block
          .replace(/\\\[([\s\S]*?)\\\]/g, (_, tex: string) => `$$${tex}$$`)
          .replace(/\\\(([^\n]*?)\\\)/g, (_, tex: string) => `$${tex}$`)
        const paras = prose.split(/\n{2,}/).filter((p) => p.trim() !== '')
        return paras.map((para, pi) => {
          const key = `${bi}.${pi}`
          const lines = para.split('\n')
          const first = lines.find((l) => l.trim() !== '') ?? ''
          if (/^(-{3,}|\*{3,}|_{3,})$/.test(first.trim()) && lines.length === 1)
            return <hr key={key} className="border-edge" />
          if (
            lines.length >= 2 &&
            /^\|(.+\|)+\s*$/.test(lines[0].trim()) &&
            /^\|[-\s|:]+\|$/.test(lines[1].trim())
          )
            return renderTable(lines, key)
          // a heading owns the paragraph's first line even without a
          // blank line after it (the Programme writes `## Argument`
          // flush against its text)
          const h = /^(#{1,6})\s+(.*)$/.exec(first)
          const rest = h ? lines.slice(lines.indexOf(first) + 1) : lines
          const restRuns = renderRuns(parseRuns(rest), key)
          if (h && doc) {
            // one heading ladder for every reading page: # = title
            // voice, ## = section voice (both Fraunces), ###+ = quiet
            // uppercase eyebrow — FileViewer / Programme / chapter had
            // three private dialects before
            const level = h[1].length
            return (
              <div key={key} className={level > 1 ? 'space-y-2' : 'space-y-3'}>
                {level === 1 ? (
                  <h3 className="font-display pt-1 text-[20px] leading-snug font-medium text-ink">
                    {renderInline(h[2], `${key}h`)}
                  </h3>
                ) : level === 2 ? (
                  <h4 className="font-display pt-2 text-[16px] leading-snug font-medium text-ink">
                    {renderInline(h[2], `${key}h`)}
                  </h4>
                ) : (
                  <h5 className="pt-3 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
                    {h[2]}
                  </h5>
                )}
                {restRuns}
              </div>
            )
          }
          if (h) {
            // chat: heading marks read as emphasis, not structure
            return (
              <div key={key} className="space-y-2">
                <p className="font-medium text-ink">{renderInline(h[2], `${key}h`)}</p>
                {restRuns}
              </div>
            )
          }
          return restRuns.length === 1 ? (
            <div key={key}>{restRuns}</div>
          ) : (
            <div key={key} className="space-y-2">
              {restRuns}
            </div>
          )
        })
      })}
    </div>
  )
}
