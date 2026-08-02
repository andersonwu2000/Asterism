/*
 * The goal-focus bus: "point at this node", from anywhere to whichever
 * surface can show it. Hovering lights the star; clicking opens its
 * panel where you already are, and only navigates when nowhere on
 * screen can claim it.
 *
 * Three callers, one law: a chat answer citing [goal:problem:slug], a
 * run console lane naming the goal its agent is on, and a landed
 * receipt. (It began as the chat→sky channel; the lanes then wanted
 * the same behaviour, and two mechanisms for one act is how surfaces
 * drift apart.) A tiny module-level pub/sub instead of context — the
 * drawer, the console and the problem screen live in different
 * subtrees, and the hash router owns everything else.
 */

export interface GoalRef {
  problem: string
  slug: string
}

type Listener = (ref: GoalRef | null) => void

const hoverListeners = new Set<Listener>()

export function onGoalHover(cb: Listener): () => void {
  hoverListeners.add(cb)
  return () => hoverListeners.delete(cb)
}

export function emitGoalHover(ref: GoalRef | null): void {
  for (const cb of hoverListeners) cb(ref)
}

/* Click-to-open. A mounted screen showing that problem's sky handles
 * the open IN PLACE (returns true → the caller skips navigation: the
 * engine console keeps you in the console). Unhandled, the caller
 * navigates and the target screen consumes the pending open when its
 * data arrives. Short TTL — a stale pending open must not select a
 * star minutes later. */

export type OpenListener = (ref: GoalRef) => boolean | void

let pendingOpen: { ref: GoalRef; at: number } | null = null
const OPEN_TTL_MS = 4000

/** Returns true when a live listener claimed the open. */
export function emitGoalOpen(ref: GoalRef): boolean {
  let handled = false
  for (const cb of openListeners) handled = cb(ref) === true || handled
  if (!handled) pendingOpen = { ref, at: Date.now() }
  return handled
}

const openListeners = new Set<OpenListener>()

export function onGoalOpen(cb: OpenListener): () => void {
  openListeners.add(cb)
  return () => openListeners.delete(cb)
}

/** One-shot: the problem screen asks "was an open for me just
 * requested?" after navigation/data load. Consumes the pending ref. */
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
