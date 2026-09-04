import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from '../lib/router'
import { ConfirmWindow } from './ConfirmWindow'

/*
 * The marks the shell is allowed (human_interface_design.md §1.4-2:
 * "頂層選單之外只有兩個獨立按鈕（右上角）：齒輪、Assistant"). One home,
 * because both the Project picker and the Project header draw them and
 * two copies would drift.
 */

/** the wordmark's mark: three stars, one line of sky */
export const MARK = (
  <svg width="18" height="18" viewBox="0 0 20 20" className="text-star" aria-hidden>
    <path d="M4 14.5L10.5 5l5 6.5" stroke="currentColor" strokeWidth="0.9" opacity="0.5" fill="none" />
    <circle cx="4" cy="14.5" r="1.7" fill="currentColor" />
    <circle cx="10.5" cy="5" r="2.1" fill="currentColor" />
    <circle cx="15.5" cy="11.5" r="1.4" fill="currentColor" />
  </svg>
)

/** two sliders — the things you set. One mark for the one settings
 * page, kept from the retired sidebar. */
export const GEAR = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
    <path d="M2 5.5h12M2 10.5h12" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" opacity="0.55" />
    <circle cx="10" cy="5.5" r="1.7" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
    <circle cx="6" cy="10.5" r="1.7" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
  </svg>
)

export const HELP_GLYPH = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
    <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.1" opacity="0.6" />
    <path
      d="M6.3 6.2a1.75 1.75 0 013.4.6c0 1.2-1.7 1.4-1.7 2.6"
      stroke="currentColor"
      strokeWidth="1.1"
      strokeLinecap="round"
    />
    <circle cx="8" cy="11.6" r="0.75" fill="currentColor" />
  </svg>
)

/** a bubble with a star in it — the Assistant inherits the drawer's
 * mark, and loses the word "ask" */
export const ASSISTANT = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
    <path
      d="M2.5 3.5A1.5 1.5 0 014 2h8a1.5 1.5 0 011.5 1.5v6A1.5 1.5 0 0112 11H7.2L4.5 13.6V11H4a1.5 1.5 0 01-1.5-1.5v-6z"
      stroke="currentColor"
      strokeWidth="1.1"
      strokeLinejoin="round"
    />
    <circle cx="8" cy="6.5" r="1.3" fill="currentColor" opacity="0.85" />
  </svg>
)

/** A circular glyph button — the shape the two corner affordances
 * share. `live` is a state dot on the mark itself (identity is the
 * shape, state is the brightness: DESIGN.md's two channels), and
 * `pulse` is the same dot blinking — §1.4-2 asks the closed Assistant
 * glyph to carry two states, and brightness/blink is the axis that
 * carries them without touching the mark's identity. */
export function IconButton({
  children,
  title,
  onClick,
  to,
  active,
  live,
  pulse,
}: {
  children: ReactNode
  title: string
  onClick?: () => void
  /** a destination instead of an action — the gear is a page */
  to?: string
  active?: boolean
  /** something arrived while you were not looking */
  live?: boolean
  /** it is working right now */
  pulse?: boolean
}) {
  const cls = `relative inline-flex cursor-pointer rounded-full p-1.5 transition-colors ${
    active ? 'bg-surface-2 text-ink' : 'text-ink-faint hover:bg-surface-2 hover:text-ink'
  }`
  const dot =
    pulse || live ? (
      <span
        className={`absolute top-1 right-1 h-1.5 w-1.5 rounded-full ${
          pulse ? 'animate-pulse bg-ink-dim' : 'bg-starlight'
        }`}
      />
    ) : null
  if (to !== undefined)
    return (
      <Link to={to} title={title} className={cls}>
        {children}
        {dot}
      </Link>
    )
  return (
    <button title={title} onClick={onClick} className={cls}>
      {children}
      {dot}
    </button>
  )
}

/** The help affordance: three sentences about how the machine works,
 * floated because reading them is a task of its own and the page
 * behind is what they are about. Nothing here is a link out — the
 * console must answer for itself. */
export function HelpButton() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <IconButton title="how Asterism works" onClick={() => setOpen(true)} active={open}>
        {HELP_GLYPH}
      </IconButton>
      {open && (
        <ConfirmWindow title="How this works" width="sm" onClose={() => setOpen(false)}>
          <ol className="mt-3 flex flex-col gap-2 text-xs leading-relaxed text-ink-dim">
            <li>
              <span className="text-ink">A project</span> is a shelf of tasks. A{' '}
              <span className="text-ink">task</span> is one thing you want proved, written
              in plain language.
            </li>
            <li>
              Press <span className="text-ink">Run</span> on a task: the engine decomposes
              it, searches the library, writes Lean, and checks every step with the
              prover. The <span className="text-ink">sky</span> is that work — a star per
              goal, lighting up as proofs land.
            </li>
            <li>
              It never stops on its own. When it needs you — a decision, a sign-off — the
              task says so, and so does its project tile.
            </li>
          </ol>
          <div className="mt-4 flex justify-end">
            <button
              className="cursor-pointer rounded-lg border border-edge px-3 py-1.5 text-xs text-ink-dim transition-colors hover:border-edge-strong hover:text-ink"
              onClick={() => setOpen(false)}
            >
              Close
            </button>
          </div>
        </ConfirmWindow>
      )}
    </>
  )
}
