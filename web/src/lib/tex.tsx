import { useMemo } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'

/*
 * Typeset math for READ-ONLY prose surfaces (Library chapter
 * docstrings/keystones). Deliberately NOT wired into lib/markdown.tsx:
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
        throwOnError: false,
        output: 'html',
      })
    } catch {
      return null
    }
  }, [math, display])
  if (html === null) return <span className="font-mono text-[0.9em]">${math}$</span>
  return <span dangerouslySetInnerHTML={{ __html: html }} />
}

const MATH_SPLIT_RE = /(\$\$[^$]+\$\$|\$[^$\n]+\$)/

/** Split prose on $…$ / $$…$$ and typeset the math runs; `plain` is
 * called on everything else so callers keep their own emphasis/code
 * handling. */
export function withMath(s: string, plain: (seg: string, i: number) => React.ReactNode) {
  return s.split(MATH_SPLIT_RE).map((seg, i) => {
    if (seg.startsWith('$$') && seg.endsWith('$$') && seg.length > 4)
      return <TeX key={`m${i}`} math={seg.slice(2, -2)} display />
    if (seg.startsWith('$') && seg.endsWith('$') && seg.length > 2)
      return <TeX key={`m${i}`} math={seg.slice(1, -1)} />
    return plain(seg, i)
  })
}
