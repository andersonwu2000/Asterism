/*
 * Chat → sky channel. When an answer cites [goal:problem:slug] and
 * that problem's constellation is on screen, hovering the citation
 * lights the star and clicking it opens the star's panel — the text
 * and the map must point at each other (same law as the goal panel's
 * route hover). A tiny module-level pub/sub instead of context: the
 * drawer and the Problem screen live in different subtrees, and the
 * hash router owns everything else.
 */

export interface GoalRef {
  problem: string
  slug: string
}

type Listener = (ref: GoalRef | null) => void

const hoverListeners = new Set<Listener>()

export function onChatGoalHover(cb: Listener): () => void {
  hoverListeners.add(cb)
  return () => hoverListeners.delete(cb)
}

export function emitChatGoalHover(ref: GoalRef | null): void {
  for (const cb of hoverListeners) cb(ref)
}

/* Click-to-open: the citation ALSO navigates (its normal job), so a
 * cross-problem click lands on the right page first and the target
 * screen consumes the pending open when its data arrives. Short TTL —
 * a stale pending open must not select a star minutes later. */

let pendingOpen: { ref: GoalRef; at: number } | null = null
const OPEN_TTL_MS = 4000

export function emitChatGoalOpen(ref: GoalRef): void {
  pendingOpen = { ref, at: Date.now() }
  for (const cb of openListeners) cb(ref)
}

const openListeners = new Set<Listener>()

export function onChatGoalOpen(cb: Listener): () => void {
  openListeners.add(cb)
  return () => openListeners.delete(cb)
}

/** One-shot: the problem screen asks "was a citation for me just
 * clicked?" after navigation/data load. Consumes the pending ref. */
export function takePendingGoalOpen(problem: string): GoalRef | null {
  if (pendingOpen === null) return null
  if (Date.now() - pendingOpen.at > OPEN_TTL_MS || pendingOpen.ref.problem !== problem) {
    if (Date.now() - pendingOpen.at > OPEN_TTL_MS) pendingOpen = null
    return null
  }
  const ref = pendingOpen.ref
  pendingOpen = null
  return ref
}
