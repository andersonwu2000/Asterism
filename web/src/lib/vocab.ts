/*
 * One vocabulary for the machine's enums — a raw engine term never
 * reaches a label. Chips stay short; the long story lives in
 * tooltips. Unknown values degrade to underscore-free words, not to
 * identifiers.
 */

const GOAL_STATUS_LABEL: Record<string, string> = {
  open: 'open',
  attempting: 'attempting',
  proved: 'proved',
  shelved: 'shelved',
  pending_strategist_review: 'awaiting review',
  disproved: 'disproved',
  frozen: 'frozen (pre-launch)',
  dead: 'dead',
}

export function goalStatusLabel(status: string): string {
  return GOAL_STATUS_LABEL[status] ?? status.replace(/_/g, ' ')
}

const ORIGIN_LABEL: Record<string, string> = {
  root: 'root',
  backward: 'subgoal of a decomposition',
  forward: 'forward work',
}

export function originLabel(origin: string): string {
  return ORIGIN_LABEL[origin] ?? origin.replace(/_/g, ' ')
}

/** strategy statuses are already words (proposed / succeeded / dead /
 * superseded); this only guards future underscored values */
export function strategyStatusLabel(status: string): string {
  return status.replace(/_/g, ' ')
}

/** Definition-bearing kinds — what draws as a DIAMOND (the anchor
 * surface a human vouches for). ONE set for both dialects: goals
 * speak Lean's ('inductive'), the librarian's decl_kind speaks its
 * shorthand ('induct'). Three per-screen copies had drifted three
 * ways (2026-07-10) — the atlas missed 'inductive', the sky missed
 * 'induct'. */
export const DEF_KINDS = new Set([
  'def', 'abbrev', 'structure', 'class', 'instance', 'inductive', 'induct',
])

/** goal status → text class, shared by every status chip (GoalPanel
 * and StrategyPanel each carried an identical private copy — the
 * pre-drift stage of the same disease). */
export const GOAL_STATUS_CLS: Record<string, string> = {
  proved: 'text-starlight',
  attempting: 'text-accent',
  open: 'text-accent',
  shelved: 'text-ink-faint',
  pending_strategist_review: 'text-warn',
  disproved: 'text-danger',
  dead: 'text-ink-faint',
  frozen: 'text-ink-faint',
}
