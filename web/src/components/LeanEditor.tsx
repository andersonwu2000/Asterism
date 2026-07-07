import { useRef } from 'react'
import { Lean } from '../lib/lean'
import { caretLineCol } from '../lib/leanSession'

/*
 * A colored Lean editor without an editor dependency: a transparent
 * textarea (input, caret, selection, scrolling) stacked on a
 * tokenizer-painted <pre> showing the same text. The two share one
 * metrics class string verbatim — same font, padding, line height,
 * wrapping — so glyphs align exactly; the textarea's own text is
 * transparent and only its caret ink shows.
 */

const METRICS =
  'p-3 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap'

export function LeanEditor({
  value,
  onChange,
  onCaret,
  onKeyDown,
  placeholder,
  heightClass = 'h-40',
  frameless = false,
}: {
  value: string
  onChange: (v: string) => void
  onCaret?: (pos: { line: number; col: number }) => void
  onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
  placeholder?: string
  /** textarea height utility — the textarea drives the box size */
  heightClass?: string
  /** skip border/background chrome (host provides its own frame) */
  frameless?: boolean
}) {
  const preRef = useRef<HTMLPreElement>(null)
  const caret = (e: { currentTarget: HTMLTextAreaElement }) =>
    onCaret?.(caretLineCol(e.currentTarget))
  return (
    <div
      className={
        'relative ' +
        (frameless
          ? ''
          : 'rounded-md border border-edge bg-surface focus-within:border-ink-faint')
      }
    >
      <pre
        ref={preRef}
        aria-hidden
        className={
          'pointer-events-none absolute inset-0 overflow-hidden text-ink ' +
          METRICS
        }
      >
        <Lean code={value + '\n'} />
      </pre>
      <textarea
        className={
          'relative block w-full resize-y bg-transparent text-transparent placeholder:text-ink-faint focus:outline-none ' +
          heightClass +
          ' ' +
          METRICS
        }
        style={{ caretColor: 'var(--color-ink)' }}
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          caret(e)
        }}
        onSelect={caret}
        onKeyDown={onKeyDown}
        onScroll={(e) => {
          const p = preRef.current
          if (p) {
            p.scrollTop = e.currentTarget.scrollTop
            p.scrollLeft = e.currentTarget.scrollLeft
          }
        }}
        placeholder={placeholder}
        spellCheck={false}
      />
    </div>
  )
}
