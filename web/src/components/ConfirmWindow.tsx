import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
// namespace import on purpose: the portal call below is then the ONLY
// occurrence of that name anywhere in `src`, so grepping for it is a
// ratchet — a second hand-written floating surface shows up as a
// second hit.
import * as ReactDOM from 'react-dom'

/*
 * THE floating window — the only one in this console.
 *
 * DESIGN.md ("Interaction") describes one shape and every floating
 * surface wears it: a full-viewport backdrop at `z-50` over `bg-bg/70`,
 * one centred `rounded-xl border border-edge bg-surface` panel,
 * backdrop click and Escape both close, focus lands inside on open.
 * That shape used to be hand-written at nine sites and had already
 * drifted — two backdrop paddings, two title voices, and only three of
 * the nine rendered through a portal.
 *
 * The portal is not optional. `fixed` is relative to the nearest
 * ancestor that animates a transform, and several surfaces that open a
 * window do exactly that (`rise-in` on the goal panel). Mounted in
 * place, a window came up the width of the panel it was launched from
 * with its title wrapped over three lines. Every caller is a candidate
 * for that trap, so the fix lives here rather than in each of them.
 *
 * It carries no idea of WHAT is being confirmed: the body — copy,
 * inputs, buttons — belongs to the caller, and so do the semantics
 * (a `busy` guard is a caller passing an `onClose` that no-ops while
 * its POST is in flight).
 */

/** The three widths the console uses. `sm` is a window that asks one
 * short question; `md` holds a list the reader has to read; `lg` is a
 * window that is a PLACE — Settings, whose body is a page's worth of
 * cards and scrolls inside the panel rather than off the screen. */
const WIDTH = {
  sm: 'w-[26rem]',
  md: 'w-[34rem]',
  lg: 'w-[44rem]',
} as const

export function ConfirmWindow({
  title,
  subject,
  badge,
  badgeTitle,
  width = 'md',
  autoFocus = true,
  onClose,
  children,
}: {
  title: string
  /** what this is about, in the reader's terms */
  subject?: string
  /** the engine's own name for it, quiet, top right */
  badge?: string
  badgeTitle?: string
  width?: 'sm' | 'md' | 'lg'
  /** Focus lands inside on open, and by default that is the panel.
   *
   * A window whose body opens ON an input (a name to type back, a
   * search box) focuses that input instead, and must say so: React
   * attaches a child's `autoFocus` during commit, while this focus
   * runs as a passive effect afterwards — the panel would take the
   * focus back every time. Passing `autoFocus={false}` says "the body
   * already lands the focus", which keeps the rule rather than
   * dropping it. */
  autoFocus?: boolean
  onClose: () => void
  children: ReactNode
}) {
  const panelRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [onClose])
  // focus lands inside the window on open (DESIGN.md's floating shape)
  useEffect(() => {
    if (autoFocus) panelRef.current?.focus()
  }, [autoFocus])
  return ReactDOM.createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg/70 p-6"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`${WIDTH[width]} max-h-[85vh] max-w-full overflow-y-auto rounded-xl border border-edge bg-surface p-5 focus:outline-none`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-ink">{title}</span>
          {subject !== undefined && (
            <span
              className="min-w-0 truncate font-mono text-[11px] text-ink-faint"
              title={subject}
            >
              {subject}
            </span>
          )}
          {badge !== undefined && (
            <span
              className="ml-auto shrink-0 font-mono text-[10px] text-ink-faint/70"
              title={badgeTitle}
            >
              {badge}
            </span>
          )}
        </div>
        {children}
      </div>
    </div>,
    document.body,
  )
}

export default ConfirmWindow
