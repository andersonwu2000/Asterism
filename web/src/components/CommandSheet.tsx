import { useMemo, useState } from 'react'
import {
  COMMAND_NOTE,
  GOAL_COMMANDS,
  SIGNALS,
  commandTitle,
  payloadFor,
} from '../lib/commands'
import type { CommandFields, CommandKind, SignalKind } from '../lib/commands'
import { goalLabel } from '../lib/format'
import BenchConfirm from './BenchConfirm'
import CommandConfirm from './CommandConfirm'
import { Button } from './ui'

/*
 * The command sheet (human_interface_design.md §1.3): where a person
 * writes what a command needs, before the window that confirms it.
 *
 * It is INLINE — a form is not a task of its own, and DESIGN.md floats
 * only what the page cannot simply say. What floats is the next step:
 * the preview and its cascade, which is a thing to read and decide.
 *
 * The sheet never validates. It builds the payload, hands it to the
 * window, and takes back whatever the engine refused — under the input
 * the engine named. A second validator here would be a second opinion
 * about what a command owes, and only one of the two would be the one
 * that actually applies.
 */

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string
  hint?: string
  error?: string | null
  children: React.ReactNode
}) {
  return (
    <label className="mt-2.5 block">
      <span className="mb-1 flex items-baseline gap-2">
        <span className="text-[11px] tracking-wider text-ink-faint uppercase">{label}</span>
        {hint && <span className="text-[11px] text-ink-faint/80">{hint}</span>}
      </span>
      {children}
      {error && <span className="mt-1 block text-[11px] text-warn">{error}</span>}
    </label>
  )
}

const INPUT =
  'w-full rounded-lg border border-edge bg-bg px-2 py-1.5 text-[12px] text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none'

/** The four commands a star offers (§1.3-4/5/6 and the Delegate of
 * §1.3-1). One picker, one form, one review button. */
export function GoalCommandSheet({
  problem,
  goalId,
  slug,
  onClose,
}: {
  problem: string
  goalId: number
  slug: string
  onClose: () => void
}) {
  const [kind, setKind] = useState<CommandKind>('ConfirmShelve')
  const [fields, setFields] = useState<CommandFields>({})
  const [open, setOpen] = useState(false)
  const [refusal, setRefusal] = useState<{ field: string | null; detail: string } | null>(null)
  const set = (patch: Partial<CommandFields>) => {
    setFields((f) => ({ ...f, ...patch }))
    setRefusal(null)
  }
  const payload = useMemo(
    () => payloadFor(kind, { ...fields, targetGoalId: goalId }),
    [kind, fields, goalId],
  )
  const err = (name: string) =>
    refusal !== null && refusal.field === name ? refusal.detail : null

  return (
    <div className="shrink-0 border-t border-edge px-4 py-3">
      <div className="flex flex-wrap items-center gap-1">
        {GOAL_COMMANDS.map((k) => (
          <button
            key={k}
            className={`cursor-pointer rounded-md px-2 py-0.5 text-[11px] transition-colors ${
              kind === k ? 'bg-surface-2 text-ink' : 'text-ink-faint hover:text-ink-dim'
            }`}
            aria-pressed={kind === k}
            title={k}
            onClick={() => {
              setKind(k)
              setRefusal(null)
            }}
          >
            {commandTitle(k)}
          </button>
        ))}
        <button
          className="ml-auto cursor-pointer rounded-md px-1.5 text-[13px] text-ink-faint transition-colors hover:text-ink"
          onClick={onClose}
          title="close"
          aria-label="close the command sheet"
        >
          ×
        </button>
      </div>

      <p className="mt-2 text-[11px] leading-relaxed text-ink-faint">{COMMAND_NOTE[kind]}</p>

      {kind === 'Inject' ? (
        <Field
          label="proof"
          hint="as you would write it for a colleague — the engine formalizes it"
          error={err('proof')}
        >
          <textarea
            className={`${INPUT} h-40 resize-y font-mono`}
            placeholder={'## Proof\n\nBy induction on n…'}
            value={fields.proof ?? ''}
            onChange={(e) => set({ proof: e.target.value })}
            spellCheck={false}
          />
        </Field>
      ) : kind === 'Delegate' ? (
        <Field
          label="charter"
          hint="optional — with this goal named, its statement is the charter"
          error={err('charter')}
        >
          <textarea
            className={`${INPUT} h-20 resize-y`}
            placeholder="the claim the new group must settle"
            value={fields.charter ?? ''}
            onChange={(e) => set({ charter: e.target.value })}
          />
        </Field>
      ) : (
        <Field
          label="reason"
          hint={kind === 'ConfirmShelve' ? 'required' : 'optional'}
          error={err('reason')}
        >
          <textarea
            className={`${INPUT} h-16 resize-y`}
            placeholder={
              kind === 'ConfirmShelve'
                ? 'why this line stops here'
                : 'a note on the record'
            }
            value={fields.reason ?? ''}
            onChange={(e) => set({ reason: e.target.value })}
          />
        </Field>
      )}

      {refusal !== null && refusal.field === null && (
        <div className="mt-2 text-[11px] text-warn">{refusal.detail}</div>
      )}

      <div className="mt-3 flex items-center gap-2">
        <Button variant="outline" onClick={() => setOpen(true)}>
          Review…
        </Button>
        <span className="text-[11px] text-ink-faint">
          you see what it closes before anything is queued
        </span>
      </div>

      {open && (
        <CommandConfirm
          problem={problem}
          kind={kind}
          payload={payload}
          label={goalLabel(goalId, slug)}
          onClose={() => setOpen(false)}
          onFieldError={(field, detail) => setRefusal({ field, detail })}
        />
      )}
    </div>
  )
}

/** A group node's commands (§1.3-2). A sub-group returns its charter
 * upward with a reason. The problem's own argument has no parent to
 * return to, so what §1.3-2 asks for there — "stop this task" — is the
 * BENCH (owner's ruling): the reversible move that takes one task off
 * the live path while the run keeps going. It is not a queued command,
 * so it goes through its own window rather than the receipt one. */
export function GroupCommandSheet({
  problem,
  groupId,
  isTop,
  benched,
  label,
  onClose,
}: {
  problem: string
  groupId: number
  isTop: boolean
  /** top group only: whether the task is already off the live path */
  benched?: boolean
  label: string
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const [open, setOpen] = useState(false)
  // the top group's own move: bench, which is not a queued command
  const [benching, setBenching] = useState(false)
  const [refusal, setRefusal] = useState<{ field: string | null; detail: string } | null>(null)
  const payload = useMemo(
    () => payloadFor('ReturnToParent', { groupId, reason }),
    [groupId, reason],
  )
  return (
    <div className="mb-5 rounded-xl border border-edge bg-surface px-3.5 py-2.5">
      <div className="flex items-baseline gap-2">
        <span className="text-[11px] tracking-wider text-ink-faint uppercase">
          {isTop ? 'stopping this task' : commandTitle('ReturnToParent')}
        </span>
        <button
          className="ml-auto cursor-pointer rounded-md px-1.5 text-[13px] text-ink-faint transition-colors hover:text-ink"
          onClick={onClose}
          aria-label="close"
        >
          ×
        </button>
      </div>
      {isTop ? (
        <>
          <p className="mt-1.5 max-w-[62ch] text-[11px] leading-relaxed text-ink-faint">
            This is the task’s own argument — it has no parent to hand back to.{' '}
            {benched
              ? 'It is benched: dispatch skips it until you put it back, and everything it has is kept.'
              : 'Stopping work on it means benching the task — dispatch skips it until you put it back, and the rest of the run carries on.'}{' '}
            To park one line of work for good, open its star and park it there.
          </p>
          <div className="mt-2.5">
            <Button variant="outline" onClick={() => setBenching(true)}>
              {benched ? 'Put this task back…' : 'Stop this task…'}
            </Button>
          </div>
          {benching && (
            <BenchConfirm
              problem={problem}
              benched={benched !== true}
              onClose={() => setBenching(false)}
            />
          )}
        </>
      ) : (
        <>
          <p className="mt-1.5 max-w-[62ch] text-[11px] leading-relaxed text-ink-faint">
            {COMMAND_NOTE.ReturnToParent}
          </p>
          <label className="mt-2.5 block">
            <span className="mb-1 block text-[11px] tracking-wider text-ink-faint uppercase">
              reason <span className="normal-case text-ink-faint/80">— required</span>
            </span>
            <textarea
              className={`${INPUT} h-16 resize-y`}
              placeholder="what the parent is owed: why this charter comes back"
              value={reason}
              onChange={(e) => {
                setReason(e.target.value)
                setRefusal(null)
              }}
            />
            {refusal && <span className="mt-1 block text-[11px] text-warn">{refusal.detail}</span>}
          </label>
          <div className="mt-3">
            <Button variant="outline" onClick={() => setOpen(true)}>
              Review…
            </Button>
          </div>
          {open && (
            <CommandConfirm
              problem={problem}
              kind="ReturnToParent"
              payload={payload}
              label={label}
              onClose={() => setOpen(false)}
              onFieldError={(field, detail) => setRefusal({ field, detail })}
              onApplied={onClose}
            />
          )}
        </>
      )}
    </div>
  )
}

/** §3.7's three kill signals, for ONE in-flight Formalizer. */
const SIGNAL_WORD: Record<SignalKind, string> = {
  return_to_nl: 'send the goal back to the Strategist',
  shelve: 'park the goal — final',
  return_to_parent: 'return its group to the parent',
}

export function SignalSheet({
  problem,
  pipelineId,
  label,
  onClose,
}: {
  problem: string
  pipelineId: string
  label: string
  onClose: () => void
}) {
  const [signal, setSignal] = useState<SignalKind>('return_to_nl')
  const [reason, setReason] = useState('')
  const [open, setOpen] = useState(false)
  const [refusal, setRefusal] = useState<{ field: string | null; detail: string } | null>(null)
  const payload = useMemo(
    () => payloadFor('Signal', { pipelineId, signal, reason }),
    [pipelineId, signal, reason],
  )
  return (
    <div className="mt-2 rounded-xl border border-edge bg-wash px-3 py-2.5">
      <div className="flex items-baseline gap-2">
        <span className="text-[11px] tracking-wider text-ink-faint uppercase">
          stop this worker
        </span>
        <button
          className="ml-auto cursor-pointer rounded-md px-1.5 text-[13px] text-ink-faint transition-colors hover:text-ink"
          onClick={onClose}
          aria-label="close"
        >
          ×
        </button>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-ink-faint">
        the worker is killed either way — the choice is what becomes of its goal.
      </p>
      <div className="mt-2 flex flex-col gap-0.5">
        {SIGNALS.map((s) => (
          <button
            key={s}
            className={`cursor-pointer rounded-md px-2 py-1 text-left text-[11px] transition-colors ${
              signal === s ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:text-ink'
            }`}
            aria-pressed={signal === s}
            title={s}
            onClick={() => {
              setSignal(s)
              setRefusal(null)
            }}
          >
            {SIGNAL_WORD[s]}
          </button>
        ))}
      </div>
      <label className="mt-2 block">
        <span className="mb-1 block text-[11px] tracking-wider text-ink-faint uppercase">
          reason{' '}
          <span className="normal-case text-ink-faint/80">
            {signal === 'return_to_parent' ? '— required' : '— optional'}
          </span>
        </span>
        <textarea
          className={`${INPUT} h-14 resize-y`}
          placeholder="why you are stopping it"
          value={reason}
          onChange={(e) => {
            setReason(e.target.value)
            setRefusal(null)
          }}
        />
        {refusal && <span className="mt-1 block text-[11px] text-warn">{refusal.detail}</span>}
      </label>
      <div className="mt-2.5">
        <Button variant="outline" onClick={() => setOpen(true)}>
          Review…
        </Button>
      </div>
      {open && (
        <CommandConfirm
          problem={problem}
          kind="Signal"
          payload={payload}
          label={label}
          onClose={() => setOpen(false)}
          onFieldError={(field, detail) => setRefusal({ field, detail })}
          onApplied={onClose}
        />
      )}
    </div>
  )
}
