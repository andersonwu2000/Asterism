/*
 * One vocabulary for the machine's enums — a raw engine term never
 * reaches a label. Chips stay short; the long story lives in
 * tooltips. Unknown values degrade to underscore-free words, not to
 * identifiers.
 */

import { duration } from './format'
import type { RunWorker } from './types'

const GOAL_STATUS_LABEL: Record<string, string> = {
  open: 'open',
  attempting: 'attempting',
  proved: 'proved',
  shelved: 'shelved',
  pending_strategist_review: 'awaiting review',
  disproved: 'disproved',
  frozen: 'frozen (pre-launch)',
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
  // v35 — the discussion-group verbs. A delegation is a handover of a
  // claim, not a dispatch of work: the words say who now owns it.
  Delegate: 'handed off a claim',
  ReturnToParent: 'handed the claim back',
  CloseGroup: 'retired a group',
  // the theory layer. Not a dispatch of proof work: what comes back is
  // prose about the wall, so the words say what was ASKED FOR, not who
  // was sent.
  Theorize: 'asked for theory',
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
    'engine term: RequestUserAmend — the run paused to ask you to amend the goal or a' +
    ' pinned Lean file',
  Noop: 'engine term: Noop — looked at the state and changed nothing',
  MarkDeliverable: 'engine term: MarkDeliverable — flagged a result as a deliverable claim',
  Ingest: "engine term: Ingest — accepted the finished work as the problem's final state",
  FetchPaper: "engine term: FetchPaper — pulled a paper into the problem's sources",
  AttemptDisproof:
    'engine term: AttemptDisproof — dispatched an attempt to prove the negation instead',
  Delegate:
    'engine term: Delegate — handed a claim to a new discussion group, which argues its own' +
    ' programme until it can deliver it back',
  ReturnToParent:
    'engine term: ReturnToParent — a group handed its charter back: refuted, needing an' +
    ' amendment, or exhausted',
  CloseGroup:
    'engine term: CloseGroup — retired a group whose claim the route no longer needs' +
    ' (difficulty is never the reason)',
  Theorize:
    'engine term: Theorize — handed one wall to the theory layer; a theorist answers with' +
    ' a document (theorems, attempts on the wall, leads), reviewed before it lands under' +
    ' documents › agent',
}

export function decisionKindTitle(kind: string): string {
  return DECISION_KIND_TITLE[kind] ?? `engine term: ${kind}`
}

/* ---------------------------------------------------------------
 * Timeline events. The log's row is `at | what happened | to whom`,
 * so the verb must survive in ONE short word — the object next to it
 * carries the identity. (The old timeline spent its widest column on
 * the same word 47 times over and its second on 1.3KB of roadmap
 * markdown; owner, 2026-08-07.)
 * --------------------------------------------------------------- */
const EVENT_LABEL: Record<string, string> = {
  // 'asked' left the reader asking what was asked. The row is a
  // REQUEST for the thing named beside it (owner, 2026-08-14).
  asked: 'asked for',
  opened: 'opened',
  reopened: 'reopened',
  failed: 'failed',
  hiccup: 'hiccup',
  proved: 'proved',
  // the same word the goal panel and the sky use for this
  // state — one fact must not have two names across two
  // surfaces (owner, 2026-08-12)
  shelved: 'shelved',
  disproved: 'disproved',
  // HISTORY ONLY — the goal status `dead` retired 2026-09-04, but the
  // `goal_events` rows written before then still say it, and a log
  // entry with no word is worse than an old word.
  dead: 'dead',
  frozen: 'frozen',
  for_review: 'for review',
  // "claimed" read as somebody claiming something — the reader's first
  // question was what it meant (owner, 2026-08-07). `deliverable` is
  // the word the sign-off surfaces and the sky's ◈ already use.
  deliverable: 'deliverable',
  ingested: 'closed',
  rev: 'rev',
  proposal: 'proposal',
  // the object column shows the CLAIM, so 'handed off' never said to
  // whom. 'delegated' carries the direction in the word, and it is
  // the engine's own verb.
  handed_off: 'delegated',
  handed_back: 'returned',
  closed_group: 'retired',
  asked_you: 'asked you',
  directive: 'note',
  held: 'held',
  paper: 'paper',
  disproof: 'disproof',
  // the theory layer's whole life, six rows of it (serve `602c6614`):
  // the request, the wake at both ends, and the answer in its three
  // shapes. The verb says what was asked for and what came back; the
  // PAGE mark beside it says a DOCUMENT is the product, which is
  // neither a star nor a brick.
  asked_theory: 'asked for theory',
  theorizing: 'theorist at work',
  theorized: 'theorist came back',
  theory: 'theory landed',
  theory_refused: 'theory refused',
  theory_died: 'theorist died',
}

export function eventLabel(kind: string): string {
  return EVENT_LABEL[kind] ?? kind.replace(/_/g, ' ')
}

const EVENT_TITLE: Record<string, string> = {
  asked:
    'engine term: Inject \u2014 the strategist asked a worker for this brick:'
    + ' state it, prove it, land it as a file. The name beside the verb is'
    + ' what it asked for',
  opened: 'cut out of a larger goal by a decomposition — nobody dispatched it',
  reopened: 'put back in play after having been settled',
  failed:
    'engine term: dead_attempt — a failure the engine filed, with the reason it filed.'
    + ' Not the same as the goal’s attempt count: one spawn can file two records,'
    + ' and some attempts burn the counter without filing any',
  hiccup:
    'an infrastructure death — provider, spawn or framework. It cost no attempt,' +
    ' which is why it is not numbered',
  proved: 'the goal reached proved',
  shelved: 'set aside — not failed; it can be picked up again',
  disproved: 'its negation was proved instead',
  dead: 'a retired status — the decomposition that minted this goal was' +
    ' wrong. Today the same event parks the goal instead',
  frozen: 'held out of play — the root after you amended its statement',
  for_review: 'handed to the strategist to judge',
  deliverable:
    'engine term: MarkDeliverable — a result was marked as delivered. Only the' +
    ' TOP group marks things you sign off on; a sub-group is handing a brick to' +
    ' the group above it, which is bookkeeping between machines',
  ingested: "the finished work was accepted as the problem's final state",
  rev: 'a Programme revision was adopted — the standing argument changed',
  proposal: 'a revision the adversarial reviewer rejected — editing, not a change of record',
  handed_off:
    'engine term: Delegate \u2014 this claim went to a NEW discussion group,'
    + ' which argues its own programme in parallel until it can deliver the'
    + ' claim back. The name beside the verb is that group',
  handed_back:
    'engine term: ReturnToParent \u2014 a group gave its claim back to the group'
    + ' above it: refuted, needing an amendment, or exhausted',
  closed_group: 'a group was retired — the route no longer needs its claim',
  asked_you:
    'engine term: RequestUserAmend — the run paused because something you own reads'
    + ' wrong: the goal, or a pinned Lean file. It waits in the Inbox.',
  directive: 'a standing note steering its own agents',
  held: 'looked at the state and changed nothing',
  paper: "a paper was pulled into the problem's sources",
  disproof: 'an attempt to prove the negation instead',
  asked_theory:
    'engine term: Theorize — one wall was handed to the theory layer. A theorist'
    + ' answers with a document (theorems, attempts on the wall, leads), reviewed before'
    + ' it lands under documents › agent. The name beside the verb is the question it'
    + ' was handed; a refused run lands nothing',
  theorizing:
    'engine term: Theorist — the wake that answers this question started. The name'
    + ' beside the verb is the question it was handed',
  theorized:
    'engine term: Theorist — the wake came back, and the note is its outcome. A run'
    + ' that died in the infrastructure never reaches a document, and this row is then'
    + ' the only trace it left',
  theory:
    'engine term: theory_documents — a document landed under documents › agent after'
    + ' the review rounds counted beside the verb. Open it from this row',
  theory_refused:
    'engine term: theory_documents — the reviewer refused the document after the rounds'
    + ' counted beside the verb. It lands under documents › agent all the same, as the'
    + ' record of what was tried; open it from this row. Not a failure of the question:'
    + ' the request can be filed again',
  theory_died:
    'engine term: Theorist — the wake died before anything was reviewed: no document,'
    + ' no ruling, nothing landed. Not a refusal — nobody read it. The note is the'
    + ' outcome the engine filed, and the request stands as asked',
}

export function eventTitle(kind: string): string {
  return EVENT_TITLE[kind] ?? kind.replace(/_/g, ' ')
}

/** Colour is a budget: the norm (a brick asked for, a brick landed) is
 * quiet, and amber stays reserved app-wide for the human's move. */
export const EVENT_CLS: Record<string, string> = {
  proved: 'text-starlight',
  disproved: 'text-danger',
  dead: 'text-ink-faint',
  shelved: 'text-ink-faint',
  frozen: 'text-ink-faint',
  for_review: 'text-ink-dim',
  hiccup: 'text-ink-faint',
  failed: 'text-ink-dim',
  opened: 'text-ink-dim',
  asked: 'text-ink-dim',
  deliverable: 'text-star',
  ingested: 'text-star',
  rev: 'text-star',
  proposal: 'text-ink-faint',
  handed_off: 'text-accent',
  handed_back: 'text-accent',
  closed_group: 'text-ink-dim',
  asked_you: 'text-warn',
  directive: 'text-ink-dim',
  held: 'text-ink-faint',
  paper: 'text-ink-dim',
  // asking for theory, and the wake answering, are the norm, so they
  // earn no accent — the page mark beside the verb identifies the row.
  // A landed document is a LANDING and takes the same ink as the other
  // landings; a refusal is residue.
  asked_theory: 'text-ink-dim',
  theorizing: 'text-ink-dim',
  theorized: 'text-ink-dim',
  theory: 'text-star',
  theory_refused: 'text-ink-faint',
  theory_died: 'text-ink-faint',
}

/** The theory layer's event kinds — the six rows serve writes for one
 * request (`object_kind: 'theory'`). */
const THEORY_EVENTS = new Set([
  'asked_theory', 'theorizing', 'theorized', 'theory', 'theory_refused',
  'theory_died',
])

/** Does this wear the PAGE mark — the theory layer's one glyph? Two
 * dialects for one thing: the rows the layer's life writes on the
 * Timeline, and the worker it seats (`Theorist`, on an engine lane).
 * NOT the decision kind `Theorize`: a decision is not a row, and serve
 * mints `asked_theory` for the row it does write. The mark is identity,
 * so the rule that decides it lives in one place rather than as a
 * string literal at each render site. */
export function isTheory(kind: string): boolean {
  return THEORY_EVENTS.has(kind) || kind === 'Theorist'
}

/** The count beside the verb, in the unit that row counts in.
 *
 * It is an attempt number nearly everywhere and reads as one bare. A
 * theory row counts what the REVIEW cost instead, and a bare `2` beside
 * "theory landed" reads as the second document. */
export function countWord(kind: string, n: number): string {
  if (kind !== 'theory' && kind !== 'theory_refused') return String(n)
  return n === 1 ? '1 round' : `${n} rounds`
}

/** What a worker argues past its reviewer: the Strategist a Programme
 * proposal, the Theorist a document. */
export type CycleSubject = 'programme' | 'document'

/** The review cycle in one sentence — round, ruling, what happens
 * next. One rhythm for both subjects (a reader learns it once), the
 * nouns each subject's own: a Theorist card must never say it is
 * drafting a programme, and the two land in different places (the
 * Programme is committed; a document lands under Documents). The
 * Strategist's phase vocabulary opens on `proposing`, the Theorist's on
 * `drafting`; either word means "no round yet". */
export function cycleLine(
  cycle: NonNullable<RunWorker['cycle']>,
  subject: CycleSubject,
): string {
  const dur = cycle.since_sec !== null ? duration(cycle.since_sec) : null
  const held = dur ? ` (${dur})` : ''
  const n = cycle.objections.length
  const objections = `${n} objection${n === 1 ? '' : 's'}`
  if (subject === 'document') {
    switch (cycle.phase) {
      case 'proposing':
      case 'drafting':
        return 'writing the document — the reviewer reads it next'
      case 'judging':
        return `round ${cycle.round} — the reviewer is examining the document${held}`
      case 'revising':
        return `round ${cycle.round} — rejected with ${objections}; revising the document`
      default:
        return `round ${cycle.round} — passed review; landing the document under Documents`
    }
  }
  switch (cycle.phase) {
    case 'proposing':
    case 'drafting':
      return 'drafting a programme proposal — the adversarial reviewer reads it next'
    case 'judging':
      return `round ${cycle.round} — the reviewer is examining the proposal${held}`
    case 'revising':
      return `round ${cycle.round} — rejected with ${objections}; revising the proposal`
    default:
      return `round ${cycle.round} — passed review; committing the programme`
  }
}

/** dead_attempts.failure_reason — the engine's forensic enum. The words
 * say what happened; the enum stays greppable in the tooltip. */
const FAILURE_LABEL: Record<string, string> = {
  agent_timeout: 'ran out of time',
  agent_stuck_thinking: 'stopped making progress',
  agent_declined: 'the agent declined the task',
  agent_infeasible: 'reported it infeasible',
  agent_no_annotation: 'no usable proposal',
  agent_no_output: 'produced nothing',
  agent_shelved: 'the agent shelved it',
  agent_rc_nonzero: 'the agent exited badly',
  agent_error: 'the agent errored',
  lake_build_error: "the proof didn't build",
  axiom_violation: 'used a forbidden axiom',
  naming_violation: 'broke a naming rule',
  no_progress: 'no progress over the last attempt',
  cite_unproved_sibling: 'cited a sibling that is not proved',
  patch_signature_mismatch: 'changed the locked signature',
  patch_body_contains_sorry: 'left a sorry in the body',
  no_nl_correspondence: "the Lean didn't match the prose",
  forward_no_new_goal: 'produced no new brick',
  parent_needs_fix: 'blocked on its parent',
  parent_stub_not_decomposable: 'its parent cannot be split further',
  missing_parent_stub: 'its parent stub was missing',
  goal_no_longer_open: 'settled before this attempt finished',
  // the group-side twin (1d34f80d): the authoring group folded
  // while its strategist wake was mid-dialogue
  group_retired: 'its group retired before the wake finished',
  spawn_fast_fail: 'the agent never started',
  daemon_shutdown: 'the engine stopped mid-run',
  paper_unfetchable: 'the paper could not be fetched',
  strategist_noop: 'the strategist changed nothing',
  strategist_schema_invalid: 'the strategist wrote an invalid decision',
  strategist_proposal_rejected: 'the reviewer rejected the proposal',
  parse_proposal_fail: 'the proposal could not be parsed',
}

export function failureLabel(reason: string): string {
  return FAILURE_LABEL[reason] ?? reason.replace(/_/g, ' ')
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
  frozen: 'text-ink-faint',
}

/** Backend names as the reader knows them. One map — the accounts
 * panel and the run console's quota strip must not drift apart. */
export const PROVIDER_LABEL: Record<string, string> = {
  claude: 'Claude Code',
  antigravity: 'Antigravity CLI',
  codex: 'Codex CLI',
  gemini: 'Gemini CLI',
  openai: 'OpenAI-compatible API',
  zen: 'OpenCode',
}

export function providerLabel(name: string): string {
  return PROVIDER_LABEL[name] ?? name
}

/** A quota window named by its own length. The backends report minutes
 * and they do not report the same ones — claude: 5 hours + week; codex:
 * a week, or 5 hours + week depending on the account (both shapes
 * measured in one workspace, 2026-08-26). Naming by position is how a
 * weekly window ends up labelled "5-hour". */
export function windowLabel(minutes: number | null): string {
  if (minutes === null) return 'window'
  if (minutes % 10080 === 0)
    return minutes === 10080 ? 'week' : `${minutes / 10080} weeks`
  if (minutes % 1440 === 0)
    return minutes === 1440 ? 'day' : `${minutes / 1440}-day window`
  if (minutes % 60 === 0) return `${minutes / 60}-hour window`
  return `${minutes}-minute window`
}
