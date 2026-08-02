import type { Group, RunWorker } from './types'

/*
 * Which argument the run-scoped Programme opens on, and whose live
 * cycle belongs above it. Pure so the law can be tested without a
 * browser — the multi-group case is rare (a delegated burden is a
 * heavyweight move) and rare paths are exactly the ones that rot
 * unwatched.
 */

/** Strategist lanes that speak for a group, newest-agnostic. */
export function seatedGroups(workers: RunWorker[]): { group: Group; worker: RunWorker }[] {
  return workers
    .filter((w) => w.kind === 'Strategist' && w.group)
    .map((w) => ({ group: w.group as Group, worker: w }))
}

/**
 * The default selection (null = the problem's own argument, i.e. the
 * top group).
 *
 * Exactly ONE delegated claim being argued right now → open it: the
 * watcher's question is "what is happening", and that is where it is
 * happening. None, or several at once → the problem's own argument,
 * because picking one of several would be arbitrary and the picker's
 * live dots already say where the others are.
 */
export function defaultGroup(workers: RunWorker[]): number | null {
  const subs = seatedGroups(workers).filter((s) => !s.group.is_top)
  return subs.length === 1 ? subs[0].group.id : null
}

/**
 * The cycle to narrate above a body — the one belonging to the chain
 * actually on screen (`resolvedGroupId` is the server's answer to
 * "which chain did I return"). A sibling's round narrated over this
 * argument is the same class of lie as reading a verdict through the
 * wrong contract.
 */
export function cycleForGroup(
  workers: RunWorker[],
  resolvedGroupId: number | null | undefined,
): RunWorker['cycle'] {
  if (resolvedGroupId === null || resolvedGroupId === undefined) return null
  const seat = seatedGroups(workers).find((s) => s.group.id === resolvedGroupId)
  return seat?.worker.cycle ?? null
}
