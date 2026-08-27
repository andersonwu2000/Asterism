import { useEffect, useId, useState } from 'react'
import { LeanBlock } from './LeanBlock'
import { engineWord, useLeanSession, type LeanCursor } from '../lib/leanSession'
import { claimLeanSlot, releaseLeanSlot, useLeanSlotActive } from '../lib/leanSlot'

/*
 * A probe: a live Lean block seeded with `#print axioms <decl>` in its
 * declaration's module scope — pause typing and it elaborates, `#`
 * command output reads as results, the caret's goal shows when it sits
 * inside a `by` proof. No run button.
 *
 * The SHAPE is `LeanBlock`, shared with the New page's Defs/Root; what
 * lives here is the session that feeds it.
 */

export { DiagList, countErrors } from './LeanBlock'
export type { EvalDiag } from './LeanBlock'

/** One live probe block under a chapter declaration. */
export function LeanProbe({
  fq,
  module,
  imports,
  seed,
  onClose,
  className = 'mt-2 ml-[22px] max-w-4xl',
  heightClass = 'min-h-16 h-auto field-sizing-content',
}: {
  /** the declaration the probe defaults to when no `seed` is given */
  fq?: string
  module?: string
  /** what the snippet needs imported, when that is NOT "the module the
   * declaration lives in". The Library reads a decl in its own module
   * and `module` says it all; a scratch file an agent is writing has a
   * prelude of its own and must name it (Engine Console, 2026-08-27). */
  imports?: string[]
  seed?: string
  onClose?: () => void
  /** the block's own place on the page — the indent belongs to the
   * caller's layout, not to the probe (the Library hangs it under a
   * chapter decl; the Engine Console swaps it INTO a lane's frame) */
  className?: string
  /** grows to its content by default — a Library decl is a signature.
   * A caller swapping this in FOR a scrolling frame passes that
   * frame's cap, so the swap costs the page no height. */
  heightClass?: string
}) {
  const [code, setCode] = useState(seed ?? (fq ? `#print axioms ${fq}` : ''))
  const [cursor, setCursor] = useState<LeanCursor | null>(null)
  // the reader's Lean runs on ONE reserved slot; this block only holds
  // it while it's the surface the user is in (claimed on focus / open).
  const slotId = useId()
  const active = useLeanSlotActive(slotId)
  useEffect(() => () => releaseLeanSlot(slotId), [slotId])
  const s = useLeanSession({
    enabled: true,
    active,
    parts: [{ id: 'probe', code }],
    imports: imports ?? (module ? [module] : []),
    cursor,
  })
  const diags = [...s.preamble, ...(s.parts.probe ?? [])]
  const status = engineWord(s)
  const goalText =
    cursor && s.goal && s.goal !== 'no goals' && !s.goal.startsWith('<no goals')
      ? s.goal.replace(/^```lean\n?/, '').replace(/\n?```\s*$/, '')
      : null
  // two frames, like Defs/Root: the editor, and ONE InfoView below
  // (goal at cursor on top, messages/output under it)
  return (
    <LeanBlock
      className={className}
      value={code}
      onChange={setCode}
      onCaret={(pos) => setCursor({ part: 'probe', ...pos })}
      onFocus={() => claimLeanSlot(slotId)}
      autoFocus
      heightClass={heightClass}
      status={status}
      goal={goalText}
      diags={diags}
      footer={
        onClose ? (
          <button
            className="cursor-pointer font-mono text-[10px] text-ink-faint transition-colors hover:text-ink"
            onClick={onClose}
          >
            close
          </button>
        ) : undefined
      }
    />
  )
}
