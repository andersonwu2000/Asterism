import { useMemo } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'

/*
 * Typeset math for READ-ONLY prose surfaces. Deliberately NOT wired into lib/markdown.tsx:
 * that renderer is the editor overlay's source-faithful colouriser —
 * its glyphs must keep textarea metrics, and typesetting would break
 * caret alignment. Failed parses degrade to the raw source, never
 * crash the page.
 */

export function TeX({ math, display = false }: { math: string; display?: boolean }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(math, {
        displayMode: display,
        throwOnError: true,
        output: 'htmlAndMathml',
      })
    } catch {
      return null
    }
  }, [math, display])
  // normal-case: math must survive an uppercase ancestor (eyebrow
  // headings) — case is semantic in math, g(n) ≠ G(N)
  if (html === null) return <span className="font-mono text-[0.9em] normal-case">{display ? '$$' : '$'}{math}{display ? '$$' : '$'}</span>
  return <span className="normal-case" dangerouslySetInnerHTML={{ __html: html }} />
}

/** Why the typesetter would refuse this math, or null if it takes it.
 *
 * Reading surfaces fall back to the source when typesetting fails.
 * Ask the same parser for the reason. Used by the
 * markdown pane's check, which is the console's answer to "does this
 * read?" for prose (`lib/prose::proseIssues`). */
export function mathError(math: string, display = false): string | null {
  try {
    katex.renderToString(math, { displayMode: display, throwOnError: true, output: 'html' })
    return null
  } catch (e) {
    return e instanceof Error ? e.message : 'the typesetter refused it'
  }
}

export const MATH_SPLIT_RE = /(\$\$[^$]+\$\$|\$[^$\n]+\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\))/

/** The renderer and its formatting report recognize the same delimiters. */
export function mathRun(seg: string): { math: string; display: boolean } | null {
  if (seg.startsWith('$$') && seg.endsWith('$$') && seg.length > 4)
    return { math: seg.slice(2, -2), display: true }
  if (seg.startsWith('$') && seg.endsWith('$') && seg.length > 2)
    return { math: seg.slice(1, -1), display: false }
  if (seg.startsWith('\\[') && seg.endsWith('\\]') && seg.length > 4)
    return { math: seg.slice(2, -2), display: true }
  if (seg.startsWith('\\(') && seg.endsWith('\\)') && seg.length > 4)
    return { math: seg.slice(2, -2), display: false }
  return null
}

/** Split prose on dollar or TeX delimiters and typeset the math runs; `plain` is
 * called on everything else so callers keep their own emphasis/code
 * handling. */
export function withMath(s: string, plain: (seg: string, i: number) => React.ReactNode) {
  return s.split(MATH_SPLIT_RE).map((seg, i) => {
    const run = mathRun(seg)
    if (run) return <TeX key={`m${i}`} {...run} />
    return plain(seg, i)
  })
}
