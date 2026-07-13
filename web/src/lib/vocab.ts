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
  forward: 'built forward',
}

export function originLabel(origin: string): string {
  return ORIGIN_LABEL[origin] ?? origin.replace(/_/g, ' ')
}

/** tooltip companion to originLabel — the label is the human words,
 * the title keeps the engine term greppable */
const ORIGIN_TITLE: Record<string, string> = {
  root: "engine term: root — the problem's main statement",
  backward: 'engine term: backward — cut out of a larger goal by a decomposition',
  forward:
    'engine term: forward — a standalone step built from what is already known, not cut out of a larger goal',
}

export function originTitle(origin: string): string {
  return ORIGIN_TITLE[origin] ?? `engine term: ${origin}`
}

/** goal.detached — alive but not hanging under any decomposition */
export const DETACHED_LABEL = 'free-standing'
export const DETACHED_TITLE =
  'engine term: detached — not part of any decomposition; it stands on its own until other work cites it'

/** Strategist decision kinds (decision_kind) — the timeline's row
 * kinds and filter chips. The label is the human words; the engine
 * term stays reachable via decisionKindTitle (operators grep by it). */
const DECISION_KIND_LABEL: Record<string, string> = {
  Inject: 'new moves',
  ConfirmShelve: 'set aside',
  EmitDirective: 'steering note',
  RequestUserAmend: 'asked you',
  Noop: 'no change',
  MarkDeliverable: 'marked a claim',
  Ingest: 'closed the problem',
  FetchPaper: 'fetched a paper',
  AttemptDisproof: 'tried a disproof',
}

export function decisionKindLabel(kind: string): string {
  return DECISION_KIND_LABEL[kind] ?? kind.replace(/_/g, ' ')
}

const DECISION_KIND_TITLE: Record<string, string> = {
  Inject: 'engine term: Inject — the strategist dispatched new proof attempts',
  ConfirmShelve:
    'engine term: ConfirmShelve — a goal was set aside (not failed; it can be picked up again)',
  EmitDirective: 'engine term: EmitDirective — a standing note steering its own agents',
  RequestUserAmend:
    'engine term: RequestUserAmend — the run paused to ask you to amend the Manifest',
  Noop: 'engine term: Noop — looked at the state and changed nothing',
  MarkDeliverable: 'engine term: MarkDeliverable — flagged a result as a deliverable claim',
  Ingest: "engine term: Ingest — accepted the finished work as the problem's final state",
  FetchPaper: "engine term: FetchPaper — pulled a paper into the problem's sources",
  AttemptDisproof:
    'engine term: AttemptDisproof — dispatched an attempt to prove the negation instead',
}

export function decisionKindTitle(kind: string): string {
  return DECISION_KIND_TITLE[kind] ?? `engine term: ${kind}`
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
