import type { ReactNode } from 'react'
import { Lean } from '../lib/lean'
import { LeanEditor } from './LeanEditor'
import { frameClass } from '../lib/textFrame'

/*
 * ONE shape for a live Lean surface, wherever it stands: a caption, a
 * framed editor (with an optional footer row), and ONE InfoView under
 * it carrying the engine's word, the goal at the caret, and the
 * diagnostics — in that order, rendering nothing when there is nothing
 * to say.
 *
 * Owner, 2026-08-27: the New page's Defs/Root boxes had grown their
 * own arrangement, and a first attempt to fix it (68a344a3) only
 * imitated this one — a second copy of the shape, which is the thing
 * being complained about. Defs/Root differ from the chapter and
 * console blocks in ONE way (they are authored, not read), and that
 * difference is not a reason to draw them differently. So the shape
 * lives here and every caller wears it.
 *
 * Deliberately presentational: the SESSION belongs to the caller. A
 * probe owns a one-part session of its own; the New page owns one
 * two-part session feeding two blocks. A block that owned its session
 * could not have served both.
 */

export type EvalDiag = {
  line: number | null
  col: number | null
  severity: string
  message: string
}

const isProblem = (d: EvalDiag) => d.severity === 'error' || d.severity === 'warning'

export function countErrors(diags: EvalDiag[] | undefined): number {
  return (diags ?? []).filter((d) => d.severity === 'error').length
}

/** Diagnostics under a code buffer: errors and warnings lead with a
 * glyph + line anchor; info output (the whole point of a probe) reads
 * as plain result text. Monochrome — severity is weight, not hue. */
export function DiagList({ diags }: { diags: EvalDiag[] }) {
  if (diags.length === 0) return null
  return (
    <div className="mt-1.5 flex flex-col gap-1">
      {diags.map((d, i) =>
        isProblem(d) ? (
          <div key={i} className="flex gap-2 font-mono text-[11px] leading-relaxed">
            <span
              className={d.severity === 'error' ? 'shrink-0 text-ink' : 'shrink-0 text-ink-faint'}
            >
              {d.severity === 'error' ? '✕' : '△'}
              {d.line != null ? ` L${d.line}` : ''}
            </span>
            <span
              className={
                'whitespace-pre-wrap ' + (d.severity === 'error' ? 'text-ink-dim' : 'text-ink-faint')
              }
            >
              {d.message}
            </span>
          </div>
        ) : (
          <pre key={i} className={frameClass({ tone: 'ink' })}>
            <Lean code={d.message} />
          </pre>
        ),
      )}
    </div>
  )
}

export function LeanBlock({
  value,
  onChange,
  onCaret,
  onFocus,
  status = '',
  goal = null,
  diags = [],
  caption,
  footer,
  placeholder,
  autoFocus = false,
  heightClass = 'min-h-16 h-auto field-sizing-content',
  className = '',
}: {
  value: string
  onChange: (v: string) => void
  onCaret?: (pos: { line: number; col: number }) => void
  onFocus?: () => void
  /** the engine's word — warming, busy, an error, or nothing */
  status?: string
  /** the goal at the caret, already unfenced; null = say nothing */
  goal?: string | null
  diags?: EvalDiag[]
  caption?: ReactNode
  /** a row inside the frame's foot (the probe puts `close` there) */
  footer?: ReactNode
  placeholder?: string
  autoFocus?: boolean
  /** grows to its content by default. A caller swapping this in FOR a
   * scrolling frame passes that frame's cap, so the swap costs the
   * page no height. */
  heightClass?: string
  /** the block's place on the page — margins belong to the caller's
   * layout, never to the block */
  className?: string
}) {
  const hasInfo = status !== '' || goal !== null || diags.length > 0
  return (
    <div className={className}>
      {caption !== undefined && (
        <div className="mb-1 text-[11px] text-ink-faint">{caption}</div>
      )}
      <div className="rounded-xl border border-edge bg-wash">
        <LeanEditor
          value={value}
          onChange={onChange}
          onCaret={onCaret}
          onFocus={onFocus}
          placeholder={placeholder}
          autoFocus={autoFocus}
          heightClass={heightClass}
          frameless
        />
        {footer !== undefined && footer !== null && footer !== false && (
          <div className="flex items-center border-t border-edge px-3 py-1">{footer}</div>
        )}
      </div>
      {hasInfo && (
        <div className="mt-1.5 rounded-xl border border-edge px-3 py-2">
          {status !== '' && <div className="text-[11px] text-ink-faint">{status}</div>}
          {goal !== null && (
            <pre className={frameClass({ frame: false, tone: 'ink' })}>
              <span className="mr-2 text-[10px] tracking-widest text-ink-faint uppercase">
                goal
              </span>
              {goal}
            </pre>
          )}
          <DiagList diags={diags} />
        </div>
      )}
    </div>
  )
}
