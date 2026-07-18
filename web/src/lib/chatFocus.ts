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

/* Click-to-open. A mounted screen showing that problem's sky handles
 * the open IN PLACE (returns true → the citation skips navigation:
 * the engine console keeps you in the console). Unhandled, the
 * citation navigates and the target screen consumes the pending open
 * when its data arrives. Short TTL — a stale pending open must not
 * select a star minutes later. */

export type OpenListener = (ref: GoalRef) => boolean | void

let pendingOpen: { ref: GoalRef; at: number } | null = null
const OPEN_TTL_MS = 4000

/** Returns true when a live listener claimed the open. */
export function emitChatGoalOpen(ref: GoalRef): boolean {
  let handled = false
  for (const cb of openListeners) handled = cb(ref) === true || handled
  if (!handled) pendingOpen = { ref, at: Date.now() }
  return handled
}

const openListeners = new Set<OpenListener>()

export function onChatGoalOpen(cb: OpenListener): () => void {
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
