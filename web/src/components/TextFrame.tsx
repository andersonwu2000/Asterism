import { Lean } from '../lib/lean'
import { renderProse } from '../lib/prose'
import { CAP, FRAME_CHROME, SIZE, TONE, frameClass } from '../lib/textFrame'
import type { FrameOpts } from '../lib/textFrame'

/*
 * One template for every block of Lean, markdown or plain text — the
 * component half; the class vocabulary is `lib/textFrame` (which
 * imports nothing, so `lib/prose` can dress its own code blocks
 * without a cycle back through here). The reasoning, and the drift
 * this ended, are written down there.
 */

export type TextKind = 'lean' | 'prose' | 'plain'

export function TextFrame({
  text,
  kind = 'plain',
  declHead = false,
  title,
  ...opts
}: FrameOpts & {
  text: string
  kind?: TextKind
  /** Lean only: colour a bare declaration head */
  declHead?: boolean
  title?: string
}) {
  if (kind === 'prose') {
    // prose builds its own blocks (headings, lists, $TeX$ typeset) and
    // must not be wrapped in a <pre> — it takes the chrome, not the
    // monospace metrics
    const { tone = 'dim', size = 'sm', cap = 'none', frame = true, className = '' } = opts
    return (
      <div
        className={[frame ? FRAME_CHROME : '', CAP[cap], SIZE[size], TONE[tone], className]
          .filter((s) => s !== '')
          .join(' ')}
        title={title}
      >
        {renderProse(text, { mode: 'document' })}
      </div>
    )
  }
  return (
    <pre className={frameClass(opts)} title={title}>
      {kind === 'lean' ? <Lean code={text} declHead={declHead} /> : text}
    </pre>
  )
}
