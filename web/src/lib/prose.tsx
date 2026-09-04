import type { ReactNode } from 'react'
import { apiGet } from './api'
import { currentSegments, navigate } from './router'
import { Lean } from './lean'
import { withMath } from './tex'
import { emitGoalHover, emitGoalOpen } from './goalFocus'
import { parseProjectRoute, projectPath } from './projectRoute'
import { frameClass } from './textFrame'

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
 * NOT for the intent editor overlay (lib/markdown.tsx is metric-
 * faithful colouring, a different job).
 */

/* One scanner, two shapes of citation.
 *
 * `[goal:problem:slug]` is a token a model emitted on purpose. `g4021`
 * is how EVERY author — the Programme, a plan note, a rebuttal, the
 * Assistant — actually names a star in running prose, and until now
 * that was dead text (HID §1.5-1). Both alternatives live in one
 * regex so a bare id inside a bracket token cannot be carved out a
 * second time: the bracket matches first at its own `[`, and the
 * scanner resumes past it.
 */
const CITE_RE =
  /\[(problem|goal|library|paper):([^[\]\n]+)\]|\bg(\d+)\b/g

export interface GoalMention {
  /** where the mention starts in the segment it was found in */
  index: number
  /** the mention as written — `g4021` */
  text: string
  id: number
}

/** Every bare `g<id>` a segment names, in order.
 *
 * A mention is a WORD: `log123`, `img12`, the slug `g12_trace` and the
 * label `gg12` all contain the characters and name no star. Exported
 * for its own test — the boundary rule is the whole of this function,
 * and it is not observable through the rendered markup.
 */
export function goalMentions(seg: string): GoalMention[] {
  const out: GoalMention[] = []
  let m: RegExpExecArray | null
  CITE_RE.lastIndex = 0
  while ((m = CITE_RE.exec(seg)) !== null) {
    if (m[3] !== undefined)
      out.push({ index: m.index, text: m[0], id: Number(m[3]) })
  }
  return out
}

/** Where a bare mention points when the engine cannot place it.
 *
 * The text carries the id alone, so the task is not in it — but the
 * ADDRESS is: prose is read inside a Project, on a page that already
 * names a task, and the overwhelming majority of mentions are that
 * task's own stars. `null` outside a Project (the picker page), where
 * there is nothing to point at. Read at CLICK time, not at render
 * time: the reader may have walked somewhere else in between, and a
 * renderer that touches `window` cannot be tested off a browser.
 */
function mentionHere(id: number): string | null {
  const here = parseProjectRoute(currentSegments())
  if (here === null || !here.problem) return null
  return projectPath(here.project, 'sky', here.problem, id)
}

/** …and where it points once the engine has answered. `locate` knows
 * the shelf and the task, so the click lands on the real star even
 * when the mention was written about another task. */
function openMention(id: number): void {
  apiGet<{
    problem: string
    project: string | null
    slug: string
  }>(`/api/goals/${id}/locate`)
    .then((loc) => {
      // a mounted sky claims the open in place, exactly as a bracket
      // citation does — no navigation, no camera reset
      if (emitGoalOpen({ problem: loc.problem, slug: loc.slug })) return
      navigate(
        loc.project
          ? projectPath(loc.project, 'sky', loc.problem, id)
          : // filed nowhere: the legacy resolver finds the shelf
            `/problems/${encodeURIComponent(loc.problem)}/g/${id}`,
      )
    })
    .catch(() => {
      // the engine could not place it (a stale id in old prose) — the
      // reader still goes somewhere real, which is where they are
      const here = mentionHere(id)
      if (here !== null) navigate(here)
    })
}

/* `to: null` = the citation names something real and there is nowhere
 * to send the reader. The Library surface left the shell (HID §1.4-3)
 * and the papers page retired (§3.9), so `/library/X` and `/papers/ID`
 * resolve to nothing and drop the reader on the project picker with no
 * explanation. The label still names the thing; only the offer to open
 * it is gone. */
function citeTarget(
  kind: string,
  body: string,
): { to: string | null; label: string; goal?: { problem: string; slug: string } } | null {
  const parts = body.split(':')
  if (kind === 'problem') return { to: `/problems/${body}`, label: body }
  if (kind === 'goal') {
    if (parts.length < 2) return null
    const slug = parts.slice(1).join(':')
    return { to: `/problems/${parts[0]}`, label: slug, goal: { problem: parts[0], slug } }
  }
  if (kind === 'library' || kind === 'paper') return { to: null, label: body }
  return null
}

/** The mono voice both citation shapes wear; a link adds the pointer
 * and the dotted rule to it. */
const CITE_TEXT = 'font-mono text-[0.92em] text-ink'
const CITE_LINK = `cursor-pointer ${CITE_TEXT} underline decoration-ink-faint decoration-dotted underline-offset-2 hover:decoration-ink`

function renderCites(seg: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let m: RegExpExecArray | null
  CITE_RE.lastIndex = 0
  while ((m = CITE_RE.exec(seg)) !== null) {
    if (m.index > last) out.push(seg.slice(last, m.index))
    if (m[3] !== undefined) {
      const id = Number(m[3])
      out.push(
        <span
          key={`${keyBase}g${m.index}`}
          role="link"
          tabIndex={0}
          className={CITE_LINK}
          title="open this star"
          onClick={() => openMention(id)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') openMention(id)
          }}
        >
          {m[0]}
        </span>,
      )
      last = m.index + m[0].length
      continue
    }
    const t = citeTarget(m[1], m[2])
    if (t === null) {
      out.push(m[0])
    } else if (t.to === null) {
      // named, but no longer reachable — the same mono voice, without
      // the pointer and the rule that promise somewhere to go
      out.push(
        <span key={`${keyBase}c${m.index}`} className={CITE_TEXT}>
          {t.label}
        </span>,
      )
    } else {
      const { to, goal } = t
      const open = () => {
        // goal citations pin their star. A screen already showing that
        // sky claims the open in place (no navigation); otherwise the
        // pending-open survives the navigation and the problem screen
        // consumes it on arrival.
        if (goal && emitGoalOpen(goal)) return
        navigate(to)
      }
      out.push(
        <span
          key={`${keyBase}c${m.index}`}
          role="link"
          tabIndex={0}
          className={CITE_LINK}
          onClick={open}
          onKeyDown={(e) => {
            if (e.key === 'Enter') open()
          }}
          onMouseEnter={goal ? () => emitGoalHover(goal) : undefined}
          onMouseLeave={goal ? () => emitGoalHover(null) : undefined}
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
      // normal-case: code must survive an uppercase ancestor —
      // identifier case is semantic
      out.push(
        <code key={`${keyBase}i${i}`} className="rounded-md bg-surface-2 px-1 font-mono text-[0.92em] normal-case text-ink">
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
// a heading is one LINE — leading whitespace disqualifies it, as in
// CommonMark's indented-code rule, and everything else about the
// paragraph it sits in is irrelevant
const HEADING_RE = /^(#{1,6})\s+(.*)$/

export interface ProseSegment {
  /** the heading this segment opens with, if it opens with one */
  heading: { level: number; text: string } | null
  /** everything under it, up to the next heading line */
  lines: string[]
}

/** A paragraph's lines, cut at every heading line.
 *
 * The renderer used to look for a heading in the paragraph's FIRST
 * line only, so `# Title` written flush against `## Argument` — no
 * blank line, which is how three of the 188 PROGRAMME.md bodies on
 * disk are written — rendered the second as the literal text
 * `## Argument`. A heading is a property of its own line; nothing
 * above it can take that away.
 */
export function headingSegments(lines: string[]): ProseSegment[] {
  const out: ProseSegment[] = []
  for (const line of lines) {
    const h = HEADING_RE.exec(line)
    if (h !== null) {
      out.push({ heading: { level: h[1].length, text: h[2] }, lines: [] })
      continue
    }
    if (out.length === 0) out.push({ heading: null, lines: [] })
    out[out.length - 1].lines.push(line)
  }
  return out.length > 0 ? out : [{ heading: null, lines: [] }]
}

type Run =
  | { type: 'p'; text: string }
  | { type: 'ul'; items: string[] }
  // start: the source's own first number — an HTML <ol> restarts at 1,
  // which silently renumbered "3. 4. 5." (and every list resumed after
  // a paragraph break) to "1. 2. 3." (owner catch, 2026-07-18)
  | { type: 'ol'; items: string[]; start: number }
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
      else
        runs.push({
          type: 'ol',
          items: [item],
          start: Number(/^\s*(\d+)/.exec(line)?.[1] ?? '1'),
        })
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
    const items = r.items.map((it, li) => (
      <li key={li}>{renderInline(it, `${keyBase}r${i}.${li}`)}</li>
    ))
    return r.type === 'ol' ? (
      <ol
        key={`${keyBase}r${i}`}
        start={r.start !== 1 ? r.start : undefined}
        className="list-decimal space-y-1 pl-4 marker:text-ink-faint"
      >
        {items}
      </ol>
    ) : (
      <ul key={`${keyBase}r${i}`} className="list-disc space-y-1 pl-4 marker:text-ink-faint">
        {items}
      </ul>
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
 * title + sections, a document in the Files tab), more air between
 * blocks. `frontmatter` renders a leading `---` block as a quiet mono
 * preamble instead of prose (a settings block). */
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
        <pre className={frameClass({ tone: 'faint' })}>
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
              className={frameClass({ tone: 'ink', size: 'md' })}
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
          // EVERY heading line is a heading — the Programme writes
          // `# Title` flush against `## Argument`, and matching only
          // the paragraph's first line rendered the second as text
          return headingSegments(lines).map((seg, si) => {
            const skey = `${key}.${si}`
            const h = seg.heading
            const restRuns = renderRuns(parseRuns(seg.lines), skey)
            if (h === null && seg.lines.every((l) => l.trim() === '')) return null
            if (h && doc) {
              // one heading ladder for every reading page: # = title
              // voice, ## = section voice (both Fraunces), ###+ = quiet
              // uppercase eyebrow — FileViewer / Programme / chapter had
              // three private dialects before
              return (
                <div key={skey} className={h.level > 1 ? 'space-y-2' : 'space-y-3'}>
                  {h.level === 1 ? (
                    <h3 className="font-display pt-1 text-[20px] leading-snug font-medium text-ink">
                      {renderInline(h.text, `${skey}h`)}
                    </h3>
                  ) : h.level === 2 ? (
                    <h4 className="font-display pt-2 text-[16px] leading-snug font-medium text-ink">
                      {renderInline(h.text, `${skey}h`)}
                    </h4>
                  ) : (
                    // renderInline, not the raw string: eyebrows carry
                    // $TeX$/`code` too — and those runs wear normal-case
                    // so the uppercase voice can't flip math letters
                    // (g(n) vs G(N) is a different statement)
                    <h5 className="pt-3 text-[11px] font-medium tracking-[0.14em] text-ink-faint uppercase">
                      {renderInline(h.text, `${skey}h`)}
                    </h5>
                  )}
                  {restRuns}
                </div>
              )
            }
            if (h) {
              // chat: heading marks read as emphasis, not structure
              return (
                <div key={skey} className="space-y-2">
                  <p className="font-medium text-ink">{renderInline(h.text, `${skey}h`)}</p>
                  {restRuns}
                </div>
              )
            }
            return restRuns.length === 1 ? (
              <div key={skey}>{restRuns}</div>
            ) : (
              <div key={skey} className="space-y-2">
                {restRuns}
              </div>
            )
          })
        })
      })}
    </div>
  )
}
