import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { ProblemStatus } from '../lib/types'
import { ApiError } from '../lib/api'

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
      className={`rounded-md font-medium transition-colors duration-150 disabled:pointer-events-none disabled:opacity-45 ${
        size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-2 py-1 text-[11px]'
      } ${BUTTON_VARIANT[variant]} ${className}`}
      {...rest}
    />
  )
}

/** Problem status → dot + label chip. One visual language for every
 * state; awaiting_human is the single loud exception (it's the one
 * state that is strictly the human's move). */
/* One attention system (design review): amber = the human's move
 * (needs input / sign-off), red = broken or destructive only. */
const STATUS_CHIP: Record<ProblemStatus, { label: string; cls: string; dot: string }> = {
  proving: { label: 'proving', cls: 'text-accent bg-accent/10', dot: 'bg-accent' },
  awaiting_human: { label: 'needs input', cls: 'bg-warn text-bg font-semibold', dot: 'bg-bg' },
  stalled: { label: 'stalled', cls: 'text-danger bg-danger/10', dot: 'bg-danger' },
  idle: { label: 'idle', cls: 'text-ink-faint', dot: 'bg-ink-faint/60' },
  signoff_pending: { label: 'sign-off', cls: 'text-warn bg-warn/15', dot: 'bg-warn' },
  ingested: { label: 'ingested', cls: 'text-ok bg-ok/10', dot: 'bg-ok' },
  bridged: {
    label: 'bridged',
    cls: 'text-ink-dim border border-edge-strong',
    dot: 'bg-starlight',
  },
}

export function StatusBadge({ status }: { status: ProblemStatus }) {
  const c = STATUS_CHIP[status] ?? STATUS_CHIP.proving
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap ${c.cls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
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
        Run the engine once (start the daemon from the header, or{' '}
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
