import { useState } from 'react'
import { Lean } from '../lib/lean'
import { LeanEditor } from './LeanEditor'
import { useLeanSession, type LeanCursor } from '../lib/leanSession'

/*
 * Runnable Lean blocks, ONE mechanism everywhere: the interactive
 * engine session (same as the New page's Defs/Root editors). A probe
 * is just a live block seeded with `#print axioms <decl>` in its
 * declaration's module scope — pause typing and it elaborates, `#`
 * command output reads as results, the caret's goal shows when it
 * sits inside a `by` proof. No run button.
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
          <pre
            key={i}
            className="overflow-x-auto rounded-md border border-edge bg-white/[0.02] px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink"
          >
            <Lean code={d.message} />
          </pre>
        ),
      )}
    </div>
  )
}

/** One live probe block under a chapter declaration. */
export function LeanProbe({
  fq,
  module,
  seed,
  onClose,
}: {
  fq: string
  module?: string
  seed?: string
  onClose?: () => void
}) {
  const [code, setCode] = useState(seed ?? `#print axioms ${fq}`)
  const [cursor, setCursor] = useState<LeanCursor | null>(null)
  const s = useLeanSession({
    enabled: true,
    parts: [{ id: 'probe', code }],
    imports: module ? [module] : [],
    cursor,
  })
  const diags = [...s.preamble, ...(s.parts.probe ?? [])]
  const status =
    s.phase === 'warming'
      ? 'engine warming — resumes on its own (a cold start can take a minute)'
      : s.phase === 'busy'
        ? 'the engine editor slot is busy elsewhere — retrying'
        : s.phase === 'connecting'
          ? 'connecting…'
          : s.phase === 'checking'
            ? 'checking…'
            : s.detail
              ? `engine error: ${s.detail}`
              : ''
  const goalText =
    cursor && s.goal && s.goal !== 'no goals' && !s.goal.startsWith('<no goals')
      ? s.goal.replace(/^```lean\n?/, '').replace(/\n?```\s*$/, '')
      : null
  // two frames, like Defs/Root: the editor, and ONE InfoView below
  // (goal at cursor on top, messages/output under it)
  const hasInfo = status !== '' || goalText != null || diags.length > 0
  return (
    <div className="mt-2 ml-[22px] max-w-4xl">
      <div className="rounded-md border border-edge bg-white/[0.02]">
        <LeanEditor
          value={code}
          onChange={setCode}
          onCaret={(pos) => setCursor({ part: 'probe', ...pos })}
          heightClass="min-h-16 h-auto field-sizing-content"
          frameless
        />
        {onClose && (
          <div className="flex items-center border-t border-edge px-3 py-1">
            <button
              className="cursor-pointer font-mono text-[10px] text-ink-faint transition-colors hover:text-ink"
              onClick={onClose}
            >
              close
            </button>
          </div>
        )}
      </div>
      {hasInfo && (
        <div className="mt-1.5 rounded-md border border-edge px-3 py-2">
          {status !== '' && <div className="text-[11px] text-ink-faint">{status}</div>}
          {goalText && (
            <pre className="overflow-x-auto font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink">
              <span className="mr-2 text-[10px] tracking-widest text-ink-faint uppercase">
                goal
              </span>
              {goalText}
            </pre>
          )}
          <DiagList diags={diags} />
        </div>
      )}
    </div>
  )
}
