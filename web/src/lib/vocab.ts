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
