/*
 * The shape of every block of Lean, markdown or plain text in this app
 * (owner, 2026-08-27: "all .lean / .md / text frames should come out of
 * one template"). Tokens live here, with no imports at all, so the
 * renderers that draw INTO a frame (`lib/prose`) can dress themselves
 * without a cycle back through the component.
 *
 * What this replaced: 24 hand-written <pre> blocks across 14 files had
 * drifted into FOUR backgrounds (bg-wash / bg-surface / bg-bg /
 * border-edge-strong), three paddings (px-3 py-2 / p-2.5 / px-3.5
 * py-2.5), five type sizes (11 / 11.5 / 12 / 12.5 / xs) and four ink
 * levels — for ONE object. And every framed code block sat at
 * `rounded-lg`, the radius ladder's CONTROL rung, while DESIGN.md puts
 * "code blocks, editors" on the 12px container rung: the law was
 * written, and universally broken, because nothing owned the shape.
 *
 * `bg-wash` is the only host-agnostic ground — a 2% white overlay
 * (index.css), so a slab recedes from whatever is behind it. `bg-bg`
 * and `bg-surface` are opaque and assume a particular host, which is
 * how the drift started.
 */

/** Stacked-textarea editors (LeanEditor, MarkdownEditor): the painted
 * <pre> and the transparent textarea must agree to the pixel. Both
 * files carried their own copy of this string. */
export const EDITOR_METRICS =
  'p-3 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap'

/** The container rung of DESIGN.md's radius ladder — code blocks,
 * editors and panels all sit here, not on the control rung. */
export const FRAME_CHROME = 'rounded-xl border border-edge bg-wash px-3 py-2'

/** Brightness, not hue: the settled recedes, the live carries ink. */
export const TONE = {
  ink: 'text-ink',
  dim: 'text-ink-dim',
  faint: 'text-ink-faint',
} as const

/** Reading room. `none` grows with the content; the rest scroll. */
export const CAP = {
  none: '',
  sm: 'max-h-56 overflow-y-auto',
  md: 'max-h-72 overflow-y-auto',
  lg: 'max-h-96 overflow-y-auto',
} as const

export const SIZE = {
  sm: 'text-[11px]',
  md: 'text-[12.5px]',
} as const

/** The one axis the survey found worth keeping: a block QUOTED into a
 * side panel is packed (a goal statement under a row), a block you
 * READ is not (a file tail, a log, a signature). Everything else the
 * call sites had invented — four grounds, three paddings, five sizes,
 * four inks — was drift, and is gone. */
export const LEAD = { quote: 'leading-snug', read: 'leading-relaxed' } as const

export interface FrameOpts {
  tone?: keyof typeof TONE
  size?: keyof typeof SIZE
  lead?: keyof typeof LEAD
  cap?: keyof typeof CAP
  /** false = a quotation INSIDE another frame: metrics only, no
   * chrome. Two frames around one block draws the same fact twice. */
  frame?: boolean
  /** off for text whose columns carry meaning (a file read verbatim) */
  wrap?: boolean
  mono?: boolean
  className?: string
}

export function frameClass({
  tone = 'dim',
  size = 'sm',
  lead = 'read',
  cap = 'none',
  frame = true,
  wrap = true,
  mono = true,
  className = '',
}: FrameOpts = {}): string {
  return [
    frame ? FRAME_CHROME : '',
    'overflow-x-auto',
    CAP[cap],
    mono ? 'font-mono' : '',
    SIZE[size],
    LEAD[lead],
    wrap ? 'break-words whitespace-pre-wrap' : 'whitespace-pre',
    TONE[tone],
    className,
  ]
    .filter((s) => s !== '')
    .join(' ')
}
