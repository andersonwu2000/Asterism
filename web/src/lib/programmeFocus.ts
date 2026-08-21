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
 * The chain to show: the reader's choice when they have made one,
 * otherwise the run's own default.
 *
 * The three states are distinct and MUST stay so. `undefined` is "no
 * choice yet — follow the run"; `null` is "the problem's own
 * argument", which is a real choice and must not be re-resolved into
 * whatever sub-group happens to be seated. Collapsing the two with
 * `pick ?? defaultGroup(...)` made the "the problem" chip a no-op
 * whenever exactly one sub-group had a strategist seated — the reader
 * was locked out of the top group's Programme entirely (owner,
 * 2026-08-06: union_closed's top group held rev 2 while the screen
 * insisted the delegated group had none).
 */
export function resolveGroup(
  pick: number | null | undefined,
  workers: RunWorker[],
): number | null {
  return pick === undefined ? defaultGroup(workers) : pick
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

/**
 * WHICH PROBLEM the run-scoped faces open on. A pattern scope runs a
 * fleet, and the daemon's `scope` is then a LIKE pattern ("Erdos.%"),
 * not a problem name — using it as one 404'd both the Programme and
 * the Intent tab for every fleet run (2026-08-22). Same shape as
 * resolveGroup: the reader's pick wins; otherwise follow the run —
 * exactly one problem with a seated strategist means the action is
 * there, several (or none) fall back to the run's own focus pick.
 * A scope with no wildcard is a plain problem name and still serves
 * as the last resort (the engine idle, nothing else known).
 */
export function fleetProblem(
  pick: string | null,
  run: { problem?: string | null; workers?: RunWorker[] } | null | undefined,
  scope?: string | null,
): string | null {
  if (pick !== null) return pick
  const seated = [...new Set(
    seatedGroups(run?.workers ?? []).map((s) => s.group.problem),
  )]
  if (seated.length === 1) return seated[0]
  if (run?.problem) return run.problem
  // `_` is a LIKE wildcard too, but real problem names carry it
  // (union_closed) — only % and * mark a scope as a pattern here
  if (scope && !/[%*]/.test(scope)) return scope
  return null
}
