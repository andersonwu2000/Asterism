import type { TimelineEvent } from './types'

/*
 * Where a Timeline row's NAME sends the reader.
 *
 * DESIGN.md's log grammar: a row reads `when | what happened | to
 * whom`, the third field is a NAME the reader can act on, and its click
 * OPENS that object — a star on the map, a revision, a document. Which
 * of the three a row has is a decision with a right answer, so it lives
 * here rather than as a ternary chain in the component: it is the one
 * part of the row a test can hold.
 */

export type RowTarget =
  | { kind: 'goal'; id: number; problem: string | null }
  | { kind: 'revision'; problem: string; revId: number }
  | { kind: 'document'; path: string }

/**
 * What this row opens, or null when it names nothing openable — the
 * click then falls back to following the object through the log.
 *
 * The order is the order a row's identity is decided in: a goal row IS
 * its star, a Programme row IS the revision it is about, and everything
 * else that landed a FILE opens the file.
 *
 * `scope` is the task the log is being read under. A per-task feed's
 * rows carry no problem of their own; the shelf-wide feed's do, and
 * theirs wins — a revision on another task must not open this one's.
 */
export function rowTarget(
  e: TimelineEvent,
  scope?: string | null,
): RowTarget | null {
  if (e.goal_id !== null)
    return { kind: 'goal', id: e.goal_id, problem: e.problem ?? null }
  const problem = e.problem ?? scope ?? null
  if (e.object_kind === 'programme' && typeof e.rev_id === 'number' && problem)
    return { kind: 'revision', problem, revId: e.rev_id }
  /* Every theory row that produced a document opens it — the landing
   * (`theory`), the refusal (`theory_refused`, which lands its record
   * too) and the WAKE's own return (`theorized`). The last of those was
   * the hole: serve filled no path on it, so the row a reader reaches
   * for — "the theorist came back, show me what it wrote" — fell
   * through to following the request and answered with its own history
   * (owner, 2026-09-06). A wake that died before any ruling still
   * carries no path, and still opens nothing: a link into a 404 is
   * worse than no link. */
  if (e.path) return { kind: 'document', path: e.path }
  return null
}
