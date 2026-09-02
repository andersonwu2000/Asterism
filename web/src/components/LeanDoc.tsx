import { useEffect, useId, useState } from 'react'
import { DiagList } from './LeanBlock'
import { LeanEditor } from './LeanEditor'
import { engineWord, useLeanSession, type LeanCursor } from '../lib/leanSession'
import { claimLeanSlot, releaseLeanSlot, useLeanSlotActive } from '../lib/leanSlot'
import { frameClass } from '../lib/textFrame'

/*
 * A `.lean` document on the Project's shelf: the file on the left, the
 * Info panel on the right (human_interface_design.md §1.2-2 — "左編輯、
 * 右面板", and for Lean the right panel is the goal at the caret plus
 * the engine's diagnostics).
 *
 * It runs on the SAME session every other live Lean surface runs on —
 * `useLeanSession` over `/api/lean/session`, holding the one reserved
 * gateway slot through `lib/leanSlot`. There is no second eval client
 * here and there must not be: the probe, the New page and this document
 * differ in where they sit, not in how they ask.
 *
 * The file carries its own `import` header, which is how it reaches the
 * engine's proofs (`Problems.<task>.proofs.…`); serve rebuilds those
 * modules incrementally before elaborating, so the panel reads the text
 * on disk rather than a stale olean.
 */

export default function LeanDoc({
  /** the document's text — the shelf owns it (drafts, save, dirty) */
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const [cursor, setCursor] = useState<LeanCursor | null>(null)
  // one reserved slot, browser-wide: this surface holds it only while
  // the reader is actually in it
  const slotId = useId()
  const active = useLeanSlotActive(slotId)
  useEffect(() => () => releaseLeanSlot(slotId), [slotId])
  const s = useLeanSession({
    enabled: true,
    active,
    parts: [{ id: 'doc', code: value }],
    // no `imports` list: the document's own header IS the list, and
    // serve reads the assembled text for what it must rebuild
    imports: [],
    cursor,
  })
  const diags = [...s.preamble, ...(s.parts.doc ?? [])]
  const status = engineWord(s)
  const goal =
    cursor && s.goal && s.goal !== 'no goals' && !s.goal.startsWith('<no goals')
      ? s.goal.replace(/^```lean\n?/, '').replace(/\n?```\s*$/, '')
      : null

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
      <div className="min-w-0 flex-1 overflow-auto p-4">
        <LeanEditor
          value={value}
          onChange={onChange}
          onCaret={(pos) => setCursor({ part: 'doc', ...pos })}
          onFocus={() => claimLeanSlot(slotId)}
          heightClass="min-h-[24rem] h-auto field-sizing-content"
        />
      </div>
      <div className="w-96 shrink-0 overflow-y-auto border-l border-edge px-4 py-3">
        {status !== '' && (
          <div className="mb-2 text-[11px] leading-relaxed text-ink-faint">{status}</div>
        )}
        {goal !== null && (
          <>
            <div className="mb-1 text-[10px] tracking-widest text-ink-faint uppercase">
              goal at the cursor
            </div>
            <pre className={frameClass({ frame: false, lead: 'quote', tone: 'ink' })}>
              {goal}
            </pre>
          </>
        )}
        {diags.length === 0 && goal === null && status === '' && (
          <div className="text-[11px] leading-relaxed text-ink-faint">
            no messages — the file elaborates clean. Put the caret inside a proof to see
            its goal.
          </div>
        )}
        <DiagList diags={diags} />
      </div>
    </div>
  )
}
