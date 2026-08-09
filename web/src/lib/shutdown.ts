/*
 * The console outlives its own server by a few hundred milliseconds.
 *
 * When Settings quits Asterism, the process this page talks to exits on
 * purpose — so every poll in the app would start failing and the screen
 * would fill with "live update failed" as its parting words. That is a
 * lie about what happened: nothing failed.
 *
 * So the app is TOLD. One flag, read by usePoll (which stops rather
 * than reporting an error) and by App (which replaces the page with a
 * plain goodbye). Deliberately module state, not React state: the poll
 * loops are scattered across a dozen components and the fact is global.
 */

let stopped = false
const listeners = new Set<() => void>()

export function isStopped(): boolean {
  return stopped
}

export function markStopped(): void {
  if (stopped) return
  stopped = true
  for (const fn of listeners) fn()
}

export function onStopped(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
