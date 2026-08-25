import type { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import type { ProblemStatus } from '../lib/types'
import { ApiError } from '../lib/api'
import { Link } from '../lib/router'

/* ------------------------------------------------------------------ */
/* Button — one component, five intents; every action in the app goes
 * through this so hover/focus/disabled behavior stays uniform.        */
/* ------------------------------------------------------------------ */

type ButtonVariant = 'primary' | 'star' | 'ok' | 'danger' | 'ghost' | 'outline'

/* achromatic CTA ladder: the primary action inverts (white on black is
 * the loudest achromatic signal); destructive stays a quiet outline —
 * the confirm step and the wording carry the gravity */
const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-ink text-bg font-semibold hover:bg-starlight',
  star: 'bg-ink text-bg font-semibold hover:bg-starlight',
  ok: 'bg-ink text-bg font-semibold hover:bg-starlight',
  danger: 'border border-edge-strong text-ink-dim hover:border-ink-faint hover:text-ink',
  ghost: 'text-ink-dim hover:text-ink hover:bg-surface-2',
  outline: 'border border-edge text-ink-dim hover:border-edge-strong hover:text-ink',
}

export function Button({
  variant = 'outline',
  size = 'sm',
  className = '',
  ...rest
}: {
  variant?: ButtonVariant
  size?: 'sm' | 'xs'
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`rounded-lg font-medium transition-colors duration-150 disabled:pointer-events-none disabled:opacity-45 ${
        size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-2 py-1 text-[11px]'
      } ${BUTTON_VARIANT[variant]} ${className}`}
      {...rest}
    />
  )
}

/* ------------------------------------------------------------------ */
/* TabNav — THE tab bar (Problem, Library chapter, Engine): one form,
 * the star underline as the active mark. Items with href render as
 * links (routed tabs); items without use onSelect (state tabs).       */
/* ------------------------------------------------------------------ */

export function TabNav<T extends string>({
  tabs,
  active,
  onSelect,
  className = '',
}: {
  tabs: { id: T; label: ReactNode; href?: string; title?: string }[]
  active: T
  onSelect?: (id: T) => void
  className?: string
}) {
  const cls = (id: T) =>
    `relative cursor-pointer pb-2 text-xs transition-colors duration-150 ${
      active === id ? 'text-ink' : 'text-ink-dim hover:text-ink'
    }`
  const mark = (id: T) =>
    active === id && (
      <span className="absolute inset-x-0 bottom-0 h-[2px] rounded-full bg-star" />
    )
  return (
    <nav className={`flex gap-5 ${className}`}>
      {tabs.map((t) =>
        t.href ? (
          <Link key={t.id} to={t.href} title={t.title} className={cls(t.id)}>
            {t.label}
            {mark(t.id)}
          </Link>
        ) : (
          <button
            key={t.id}
            title={t.title}
            className={cls(t.id)}
            onClick={() => onSelect?.(t.id)}
          >
            {t.label}
            {mark(t.id)}
          </button>
        ),
      )}
    </nav>
  )
}

/* ------------------------------------------------------------------ */
/* Select — the native box was a bare rectangle (owner): quiet border,
 * surface fill, a small chevron the platform styling never gave us.   */
/* ------------------------------------------------------------------ */

export function Select({
  className = '',
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className={`relative inline-block ${className}`}>
      <select
        {...rest}
        className="w-full cursor-pointer appearance-none rounded-lg border border-edge bg-surface py-1 pr-7 pl-2 font-mono text-xs text-ink transition-colors hover:border-edge-strong focus:border-ink-faint focus:outline-none"
      />
      <span
        className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-[8px] text-ink-faint"
        aria-hidden
      >
        ▼
      </span>
    </span>
  )
}

/** Problem status → one mark: a state dot + a word, at one size, on
 * one baseline. Brightness and motion carry the state; SHAPE carries
 * exactly one thing — the filled pill means "this row is your move",
 * and nothing else may wear it. Every other status is a plain word, so
 * a board of settled rows reads as one quiet column.
 *
 * The rule used to be written down ("pills reserved for states that
 * ask something") and contradicted in the same file: paused, proving,
 * complete and in-Library all wore chips too, and the Board answered
 * by inventing a SECOND vocabulary of bare text for the settled three.
 * Three treatments in one column is what the reader actually saw
 * (owner, 2026-08-26). One rule, applied here, is the fix — the Board
 * no longer overrides anything. */
const STATUS_MARK: Record<ProblemStatus, { label: string; ink: string; dot: string }> = {
  proving: { label: 'proving', ink: 'text-ink', dot: 'bg-accent animate-pulse' },
  paused: { label: 'paused', ink: 'text-ink-dim', dot: 'bg-ink-dim' },
  stalled: { label: 'stalled', ink: 'text-danger font-medium', dot: 'bg-danger' },
  // the two the human owns — both wear the pill, and their labels
  // rhyme so the class reads before the word does
  awaiting_human: { label: 'needs input', ink: '', dot: '' },
  signoff_pending: { label: 'needs sign-off', ink: '', dot: '' },
  ingested: { label: 'complete', ink: 'text-ink-faint', dot: 'bg-ink-faint/60' },
  bridged: { label: 'in Library', ink: 'text-ink-dim', dot: 'bg-starlight' },
  idle: { label: 'not started', ink: 'text-ink-faint', dot: 'bg-ink-faint/40' },
}

/** The states that are strictly the human's move — the pill's sole
 * owners. Brightness cannot separate them from live work in an
 * achromatic palette (warn and ink are two greys apart), so inversion
 * does it: DESIGN.md's fifth axis, spent once. */
const YOUR_MOVE: ProblemStatus[] = ['awaiting_human', 'signoff_pending']

const STATUS_HINT: Record<ProblemStatus, string> = {
  proving: 'the engine is working on it right now',
  paused: 'unfinished — the engine is not running it; press Run on its page to continue',
  awaiting_human: 'waiting for your decision — open the inbox',
  stalled: 'no path forward found — needs direction',
  idle: 'not started yet',
  signoff_pending: 'finished — waiting for your sign-off in the inbox',
  ingested: 'proof complete and accepted (engine term: ingested)',
  bridged: 'merged into the Library (engine term: bridged)',
}

export function StatusBadge({
  status,
  flush,
}: {
  status: ProblemStatus
  /** pull the pill's own padding back out, so its dot sits on the same
   * vertical line as every plain mark's dot — a status COLUMN wants one
   * dot grid, a header next to a title does not. */
  flush?: boolean
}) {
  // Unknown status must degrade to the quietest claim, never the
  // loudest — "proving" asserts live work the server didn't claim.
  const c = STATUS_MARK[status] ?? STATUS_MARK.idle
  if (YOUR_MOVE.includes(status))
    return (
      <span
        title={STATUS_HINT[status]}
        className={`inline-flex items-center gap-1.5 rounded-full bg-warn px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap text-bg ${
          flush ? '-ml-2' : ''
        }`}
      >
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-bg" />
        {c.label}
      </span>
    )
  return (
    <span
      title={STATUS_HINT[status]}
      className={`inline-flex items-center gap-1.5 text-[11px] whitespace-nowrap ${c.ink}`}
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <svg width="30" height="30" viewBox="0 0 20 20" className="mb-4 text-ink-faint" aria-hidden>
        <path
          d="M4 14.5L10.5 5l5 6.5"
          stroke="currentColor"
          strokeWidth="0.8"
          opacity="0.4"
          fill="none"
        />
        <circle cx="4" cy="14.5" r="1.5" fill="currentColor" opacity="0.6" />
        <circle cx="10.5" cy="5" r="1.9" fill="currentColor" opacity="0.6" />
        <circle cx="15.5" cy="11.5" r="1.2" fill="currentColor" opacity="0.6" />
      </svg>
      <div className="font-display text-[19px] text-ink-dim">{title}</div>
      {children && <div className="mt-2 max-w-md text-sm text-ink-faint">{children}</div>}
    </div>
  )
}

/** API error → user-facing state. Distinguishes the two structured
 * degraded modes (no DB yet / schema behind) from transport failures. */
export function ErrorState({ error }: { error: Error }) {
  if (error instanceof ApiError && error.detail === 'NO_DATABASE') {
    return (
      <EmptyState title="This workspace hasn't been initialized yet">
        Run the engine once (press Run in the header, or{' '}
        <code className="font-mono">asterism init</code> a problem) and the board will populate.
      </EmptyState>
    )
  }
  if (error instanceof ApiError && error.detail.startsWith('UPGRADE_REQUIRED')) {
    return (
      <EmptyState title="Database needs a migration">
        The engine's schema is newer than this database. Start the engine once to migrate, then
        reload.
      </EmptyState>
    )
  }
  if (error instanceof ApiError && error.status === 404) {
    return (
      <EmptyState title="Not found">
        {error.detail} — it may have been renamed or removed.
      </EmptyState>
    )
  }
  return (
    <EmptyState title="Can't reach the engine">
      {String(error.message)} — is <code className="font-mono">asterism serve</code> still running?
    </EmptyState>
  )
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="mb-2 text-[11px] font-medium tracking-widest text-ink-faint/70 uppercase">
      {children}
    </div>
  )
}
