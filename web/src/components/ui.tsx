import type { ReactNode } from 'react'
import type { ProblemStatus } from '../lib/types'
import { ApiError } from '../lib/api'

/** Problem status → label + chip styling. awaiting_human / stalled are
 * the two "needs attention" reds: filled = human's move, outlined =
 * engine gave up. */
const STATUS_CHIP: Record<ProblemStatus, { label: string; cls: string }> = {
  proving: { label: 'proving', cls: 'text-accent bg-accent/10' },
  awaiting_human: { label: 'needs input', cls: 'text-white bg-danger/80' },
  stalled: { label: 'stalled', cls: 'text-danger border border-danger/60' },
  idle: { label: 'idle', cls: 'text-ink-faint border border-edge' },
  signoff_pending: { label: 'sign-off', cls: 'text-warn bg-warn/15' },
  ingested: { label: 'ingested', cls: 'text-ok bg-ok/10' },
  bridged: { label: 'bridged', cls: 'text-star bg-star/10' },
}

export function StatusBadge({ status }: { status: ProblemStatus }) {
  const c = STATUS_CHIP[status] ?? STATUS_CHIP.proving
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${c.cls}`}
    >
      {c.label}
    </span>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <svg width="28" height="28" viewBox="0 0 24 24" className="mb-4 text-ink-faint" aria-hidden>
        <path
          fill="currentColor"
          d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z"
          opacity="0.5"
        />
      </svg>
      <div className="text-base text-ink-dim">{title}</div>
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
  return (
    <EmptyState title="Can't reach the engine">
      {String(error.message)} — is <code className="font-mono">asterism serve</code> still running?
    </EmptyState>
  )
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="mb-2 text-xs font-medium tracking-widest text-ink-faint uppercase">
      {children}
    </div>
  )
}
