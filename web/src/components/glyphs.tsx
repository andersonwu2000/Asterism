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

/** A page — a DOCUMENT. The sky's two shapes are a diamond (data) and
 * a circle (proposition); the theory layer's product is neither, it is
 * prose about the wall, so it gets the third shape (DESIGN.md, 2026-09-04).
 * `currentColor` throughout: the mark is identity, the ink around it is
 * state, and the two channels stay separate. Sized for a text line. */
export const PAGE = (
  <svg
    width="10"
    height="11"
    viewBox="0 0 10 11"
    fill="none"
    className="inline-block shrink-0 align-[-1px]"
    aria-hidden
  >
    <rect x="1" y="1" width="8" height="9" rx="1" stroke="currentColor" strokeWidth="1" />
    <path d="M3 4.25h4M3 6.75h2.5" stroke="currentColor" strokeWidth="0.9" strokeLinecap="round" opacity="0.55" />
  </svg>
)

/** A glyph button — the shape the corner affordances share. `live` is
 * a state dot on the mark itself (identity is the shape, state is the
 * brightness: DESIGN.md's two channels), and `pulse` is the same dot
 * blinking — §1.4-2 asks the closed Assistant glyph to carry two
 * states, and brightness/blink is the axis that carries them without
 * touching the mark's identity.
 *
 * With a `label` the mark carries its word (2026-09-05). Two 15px
 * glyphs at residue ink were the whole of the corner, and a newcomer
 * could not tell that one of them was a core function or that the
 * other was where settings live — a pictogram asks to be decoded, a
 * word does not. `framed` draws the control rung's border around it:
 * the one ACT in a header of places, told apart by shape rather than
 * by colour. */
export function IconButton({
  children,
  title,
  onClick,
  to,
  active,
  live,
  pulse,
  label,
  framed,
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
  /** the word beside the mark — the button reads as a labelled control */
  label?: string
  /** a bordered control (rounded-lg, the control rung) — for an act,
   * never for a place; only meaningful with a label */
  framed?: boolean
}) {
  const cls =
    label === undefined
      ? `relative inline-flex cursor-pointer rounded-full p-1.5 transition-colors ${
          active ? 'bg-surface-2 text-ink' : 'text-ink-faint hover:bg-surface-2 hover:text-ink'
        }`
      : framed
        ? `relative inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
            active
              ? 'border-edge-strong bg-surface-2 text-ink'
              : 'border-edge bg-surface text-ink hover:border-edge-strong hover:bg-surface-2'
          }`
        : `relative inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1 text-xs transition-colors ${
            active ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:bg-surface-2 hover:text-ink'
          }`
  const dot =
    pulse || live ? (
      <span
        className={`absolute h-1.5 w-1.5 rounded-full ${
          label === undefined ? 'top-1 right-1' : '-top-0.5 -right-0.5'
        } ${pulse ? 'animate-pulse bg-ink-dim' : 'bg-starlight'}`}
      />
    ) : null
  const body = (
    <>
      {children}
      {label !== undefined && <span>{label}</span>}
      {dot}
    </>
  )
  if (to !== undefined)
    return (
      <Link to={to} title={title} className={cls}>
        {body}
      </Link>
    )
  return (
    <button title={title} onClick={onClick} className={cls}>
      {body}
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
