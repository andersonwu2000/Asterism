import type { ReactNode } from 'react'
import { Lean } from './lean'

/*
 * Markdown display colouring for Manifest prose — the same achromatic
 * axes as the rest of the chrome (brightness carries structure), and
 * the one licensed exception carries over: ALL code — fenced blocks
 * and inline `spans` alike — runs through the shared Lean tokenizer
 * (DESIGN.md: every Lean fragment on every screen goes through it; a
 * flat amber for inline spans read as one undifferentiated wash on a
 * ref-dense Manifest, owner 2026-07-09). Display only.
 */

const CODE_SPAN_RE = /(`[^`\n]+`)/
const BOLD_RE = /(\*\*[^*\n]+\*\*)/

function inline(text: string, key: number): ReactNode {
  return text.split(CODE_SPAN_RE).map((seg, i) => {
    if (seg.startsWith('`') && seg.endsWith('`') && seg.length > 2) {
      return (
        <span key={`${key}-c${i}`}>
          <span className="text-ink-faint">`</span>
          <Lean code={seg.slice(1, -1)} />
          <span className="text-ink-faint">`</span>
        </span>
      )
    }
    return seg.split(BOLD_RE).map((b, j) =>
      b.startsWith('**') && b.endsWith('**') && b.length > 4 ? (
        <span key={`${key}-b${i}-${j}`} className="text-starlight">
          {b}
        </span>
      ) : (
        b
      ),
    )
  })
}

export function Markdown({ text }: { text: string }): ReactNode {
  const lines = text.split('\n')
  const out: ReactNode[] = []
  let fence: string[] | null = null
  lines.forEach((ln, i) => {
    const nl = i < lines.length - 1 ? '\n' : ''
    if (/^\s*```/.test(ln)) {
      if (fence !== null) {
        // closing — paint the buffered block as Lean in one pass so
        // multi-line comments tokenize correctly
        out.push(<Lean key={`f${i}`} code={fence.join('\n')} />)
        out.push('\n')
        fence = null
      } else {
        fence = []
      }
      out.push(
        <span key={i} className="text-ink-faint">
          {ln}
        </span>,
        nl,
      )
      return
    }
    if (fence !== null) {
      fence.push(ln)
      return
    }
    const h = ln.match(/^(\s{0,3}#{1,6}\s+)(.*)$/)
    if (h) {
      out.push(
        <span key={i}>
          <span className="text-ink-faint">{h[1]}</span>
          <span className="text-starlight">{h[2]}</span>
        </span>,
        nl,
      )
      return
    }
    const b = ln.match(/^(\s*(?:[-*+]|\d+\.)\s+)(.*)$/)
    if (b) {
      out.push(
        <span key={i}>
          <span className="text-ink-faint">{b[1]}</span>
          {inline(b[2], i)}
        </span>,
        nl,
      )
      return
    }
    out.push(<span key={i}>{inline(ln, i)}</span>, nl)
  })
  if (fence !== null) {
    // unclosed fence at EOF — still paint what's there
    out.push(<Lean key="ftail" code={(fence as string[]).join('\n')} />)
  }
  return out
}

const METRICS = 'p-3 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap'

/** A coloured markdown editor, LeanEditor's trick verbatim: a
 * transparent textarea (input, caret, selection) stacked on a painted
 * <pre> of the same text with identical metrics. */
export function MarkdownEditor({
  value,
  onChange,
  heightClass = 'h-96',
}: {
  value: string
  onChange: (v: string) => void
  heightClass?: string
}) {
  return (
    <div className="relative rounded-xl border border-edge bg-surface focus-within:border-ink-faint has-[textarea:disabled]:opacity-60">
      <pre
        aria-hidden
        className={'pointer-events-none absolute inset-0 overflow-hidden text-ink ' + METRICS}
      >
        <Markdown text={value + '\n'} />
      </pre>
      <textarea
        className={
          'relative block w-full resize-y bg-transparent text-transparent focus:outline-none ' +
          heightClass +
          ' ' +
          METRICS
        }
        style={{ caretColor: 'var(--color-ink)' }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={(e) => {
          const p = e.currentTarget.previousElementSibling as HTMLElement | null
          if (p) {
            p.scrollTop = e.currentTarget.scrollTop
            p.scrollLeft = e.currentTarget.scrollLeft
          }
        }}
        spellCheck={false}
      />
    </div>
  )
}
