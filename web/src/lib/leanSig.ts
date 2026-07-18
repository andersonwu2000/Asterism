/*
 * Split a one-line Lean declaration signature into binder groups and
 * conclusion — the InfoView shape (hypotheses, then ⊢ goal) that
 * mathematicians already read. The input is the engine's display
 * signature (context.goal_display_signature via serve): attributes/
 * keyword/name prefix, top-level bracket binders, ` : `, conclusion.
 * Returns null when the text doesn't parse as that shape — callers
 * fall back to rendering it verbatim.
 */

export interface SplitSig {
  binders: string[]
  conclusion: string
}

const OPENS = '({[⦃⟨'
const CLOSES = ')}]⦄⟩'

export function splitSignature(sig: string): SplitSig | null {
  // first top-level ` : ` = the declaration's type ascription (binder
  // colons live inside their brackets)
  let depth = 0
  let colon = -1
  for (let i = 0; i < sig.length; i++) {
    const ch = sig[i]
    if (OPENS.includes(ch)) depth++
    else if (CLOSES.includes(ch)) depth = Math.max(0, depth - 1)
    else if (depth === 0 && ch === ':' && sig[i - 1] === ' ' && sig[i + 1] === ' ') {
      colon = i
      break
    }
  }
  if (colon < 0) return null
  const head = sig.slice(0, colon)
  const conclusion = sig.slice(colon + 1).trim()
  if (conclusion === '') return null
  const binders: string[] = []
  depth = 0
  let start = -1
  for (let i = 0; i < head.length; i++) {
    const ch = head[i]
    if (OPENS.includes(ch)) {
      if (depth === 0) start = i
      depth++
    } else if (CLOSES.includes(ch)) {
      depth = Math.max(0, depth - 1)
      if (depth === 0 && start >= 0) {
        binders.push(head.slice(start, i + 1))
        start = -1
      }
    }
  }
  return { binders, conclusion }
}
