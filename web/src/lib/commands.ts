/*
 * The human command path (human_interface_design.md §1.3, §3.3).
 *
 * A person's command does not act: it is QUEUED. Serve inserts the row
 * and hands back an id; the daemon applies it on its next tick through
 * the same appliers the Strategist's own decisions go through. Three
 * consequences shape everything here:
 *
 *   · the payload speaks the strategist decision's own field names, so
 *     the console never teaches a second vocabulary;
 *   · every submission carries a FRESH idempotency key and the
 *     `expected_revision` the preview reported, so a retried POST is
 *     the same command and a command issued against a page that has
 *     moved is refused rather than applied to a state nobody read;
 *   · the answer arrives later, so a receipt has three honest states
 *     and "queued" is one of them — nothing here may show a command as
 *     done because the POST returned 202.
 *
 * The engine owns what a command MEANS and what each kind requires
 * (`state/commands.validate_fields`); this module owns what the CONSOLE
 * owes. Duplicating the requirements here would give the reader two
 * validators that can disagree — so a missing field is discovered by
 * asking, and `fieldFromDetail` puts the engine's own sentence under
 * the input it names.
 */

import type { RunWorker } from './types'

export const GOAL_COMMANDS = ['ConfirmShelve', 'MarkDeliverable', 'Inject', 'Delegate'] as const

/** What the task's own argument offers, where there is no node to aim
 * at. A `Theory` names no target (`state/commands.target_of` returns
 * None for it): it is a question about the whole record, filed on the
 * problem's TOP group whatever the reader is looking at. */
export const PROBLEM_COMMANDS = ['Theory'] as const

export const COMMAND_KINDS = [
  ...GOAL_COMMANDS,
  ...PROBLEM_COMMANDS,
  'ReturnToParent',
  'Signal',
] as const

export type CommandKind = (typeof COMMAND_KINDS)[number]

/** §3.7's three kill signals, in the engine's spelling. */
export const SIGNALS = ['return_to_nl', 'shelve', 'return_to_parent'] as const
export type SignalKind = (typeof SIGNALS)[number]

/** The reader's words for each command. Engine vocabulary belongs in
 * the tooltip (DESIGN.md: human words in the UI). */
const TITLE: Record<CommandKind, string> = {
  ConfirmShelve: 'park this goal',
  MarkDeliverable: 'mark it delivered',
  Inject: 'hand it a proof',
  Delegate: 'hand it to a new group',
  ReturnToParent: 'return this group to its parent',
  Signal: 'stop this worker',
  Theory: 'ask for theory',
}

export function commandTitle(kind: CommandKind): string {
  return TITLE[kind]
}

/** What each one does, in one sentence, on the sheet itself. */
export const COMMAND_NOTE: Record<CommandKind, string> = {
  ConfirmShelve:
    'parks this line of work. A person’s park is final — nothing revives it, and the reason is the only record of why it stopped.',
  MarkDeliverable:
    'records this goal as a result its group delivers. The reason is a note on the record, not a requirement.',
  Inject:
    'queues a formalizer to settle the argument you write. It joins the back of the queue — nothing in flight is disturbed.',
  Delegate:
    'hands this goal to a new discussion group, which argues it under its own charter. With a goal named, its statement IS the charter.',
  ReturnToParent:
    'closes this group and hands its charter back up. Every line still open under it is retired with it.',
  Signal: 'stops one worker that is running right now.',
  Theory:
    'hands one wall to the theory layer. A theorist reads the record, writes a document — theorems, attempts on the wall, leads — and it lands under documents › agent once its reviewer accepts it.',
}

// ---------------------------------------------------------------------
// which lane may be signalled

/** What the engine room offers on one worker lane.
 *
 * A kill is aimed at ONE `pipelines.id` — never at a kind and never at
 * a name (CLAUDE.md's broad-filter rule, in the engine). `/api/run`
 * carries that id since `f84f1828`: the lane is built from the queue
 * LEASE, which has no pipeline column, so serve joins it to the
 * running `pipelines` row by the dispatcher's own in-flight identity.
 *
 * The id is null when no running row matches — a lease claimed before
 * its dispatch opened a row, or after it closed one. That is a lane
 * whose worker this console cannot see, and it must say so rather than
 * aim at a neighbour's id, so the three answers stay separate:
 * `stop` (aim here), `unaddressable` (a Formalizer with no id), `none`
 * (a kind the applier refuses, or a lane belonging to no problem).
 */
export type LaneSignal =
  | { move: 'stop'; pipelineId: string; problem: string }
  | { move: 'unaddressable' }
  | { move: 'none' }

export function laneSignal(
  w: Pick<RunWorker, 'kind' | 'problem' | 'pipeline_id'>,
  lens: string | null,
): LaneSignal {
  // the lane's OWN problem outranks the console's lens — a pattern
  // scope runs agents across several problems at once
  const problem = w.problem ?? lens
  if (w.kind !== 'Formalizer' || !problem) return { move: 'none' }
  const pipelineId = (w.pipeline_id ?? '').trim()
  if (pipelineId === '') return { move: 'unaddressable' }
  return { move: 'stop', pipelineId, problem }
}

// ---------------------------------------------------------------------
// the payload

export interface CommandFields {
  targetGoalId?: number | null
  groupId?: number | null
  reason?: string
  proof?: string
  charter?: string
  brief?: string
  pipelineId?: string
  signal?: SignalKind | ''
  /** Theory: what would suffice — the statement to settle, or the wall */
  objective?: string
  /** Theory: where the record stands, so the theorist does not re-derive it */
  situation?: string
}

/** Build the payload the appliers already consume.
 *
 * A field the person left blank is OMITTED. The engine reads
 * present-but-empty as missing (`str(payload.get(f) or '').strip()`),
 * so sending `''` would make the console and the validator disagree
 * about what is still owed — and the console would be the one lying,
 * because it is the one that drew the empty box.
 */
export function payloadFor(kind: CommandKind, f: CommandFields): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  const text = (v: string | undefined): string | null => {
    const s = (v ?? '').trim()
    return s === '' ? null : s
  }
  if (kind === 'Theory') {
    // no target and no reason: the question is about the whole record,
    // and the two boxes below are the whole of what it owes
    const objective = text(f.objective)
    if (objective !== null) out.objective = objective
    const situation = text(f.situation)
    if (situation !== null) out.situation = situation
    return out
  }
  if (kind === 'ReturnToParent') {
    if (f.groupId !== undefined && f.groupId !== null) out.group_id = f.groupId
  } else if (kind === 'Signal') {
    const p = text(f.pipelineId)
    if (p !== null) out.pipeline_id = p
    if (f.signal) out.signal = f.signal
  } else if (f.targetGoalId !== undefined && f.targetGoalId !== null) {
    out.target_goal_id = f.targetGoalId
  }
  const reason = text(f.reason)
  if (reason !== null && kind !== 'Delegate') out.reason = reason
  if (kind === 'Inject') {
    const proof = text(f.proof)
    if (proof !== null) out.proof = proof
  }
  if (kind === 'Delegate') {
    const charter = text(f.charter)
    if (charter !== null) out.charter = charter
    const brief = text(f.brief)
    if (brief !== null) out.brief = brief
  }
  return out
}

/** A fresh key for every submission.
 *
 * The key is what makes a RETRY the same command: a dropped response
 * or a double click re-POSTs the same key and gets the same id back.
 * It must therefore be minted once per intent and never reused across
 * two intents — a re-issue after a `stale` refusal is a new command
 * against a state that has moved, and reusing the key would return the
 * refused row's id forever.
 */
export function newIdempotencyKey(): string {
  const c = globalThis.crypto
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  // a browser without randomUUID still must not collide: time plus two
  // draws of randomness, in the same shape
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}-${Math.random()
    .toString(36)
    .slice(2, 12)}`
}

// ---------------------------------------------------------------------
// refusals

/** The form's own inputs. A refusal naming anything else is about the
 * command, not about a box on screen. */
const FORM_FIELDS = new Set([
  'target_goal_id',
  'group_id',
  'reason',
  'proof',
  'charter',
  'brief',
  'pipeline_id',
  'signal',
  'objective',
  'situation',
])

/** Which input a 422 is about, or null.
 *
 * The engine's message already names the field and says why it is
 * owed, so the console does not restate it — it puts that sentence
 * under the right box. Backticks first (the requirement messages quote
 * the field), then the bare `requires <field>` form.
 */
export function fieldFromDetail(detail: string): string | null {
  const ticked = detail.match(/`([a-z_]+)`/g)
  if (ticked) {
    for (const t of ticked) {
      const name = t.slice(1, -1)
      if (FORM_FIELDS.has(name)) return name
    }
  }
  const bare = /\brequires\s+([a-z_]+)/.exec(detail)
  if (bare && FORM_FIELDS.has(bare[1])) return bare[1]
  return null
}

// ---------------------------------------------------------------------
// the preview

export interface PreviewNode {
  id: number
  kind: 'goal' | 'group'
  slug: string
  status: string
  effect: string
}

export interface PreviewPipeline {
  id: string
  kind: string
  target_id: string
  target_kind: string
  status: string
  started_at: string
}

export interface CommandPreview {
  affected: PreviewNode[]
  cascade: boolean
  revision: number
  /** Signal only: what stopping this worker does, in the engine's own
   * words (`state/commands.SIGNAL_EFFECT`). */
  effect?: string
  /** Signal only: the worker the kill names, or null when no pipeline
   * ever ran under that id. */
  pipeline?: PreviewPipeline | null
}

/** The one line above the list: how much closes, and of what. */
export function affectedSummary(p: CommandPreview): string {
  const goals = p.affected.filter((a) => a.kind === 'goal').length
  const groups = p.affected.length - goals
  const n = (k: number, word: string) => `${k} ${word}${k === 1 ? '' : 's'}`
  if (p.affected.length === 0) return 'nothing would change'
  if (groups === 0) return n(goals, 'goal')
  if (goals === 0) return n(groups, 'group')
  return `${p.affected.length} nodes — ${n(goals, 'goal')} and ${n(groups, 'group')}`
}

/** What the confirm window is reading while the preview is in flight.
 *
 * Every other kind closes something, so the wait is about a cascade. A
 * theory request closes nothing by construction — saying it is reading
 * what this would close would promise a list that never comes. */
export function previewWaitLine(kind: CommandKind): string {
  return kind === 'Theory'
    ? 'reading the record this asks about…'
    : 'reading what this would close…'
}

/** The sentence under an empty cascade, or null when the list speaks
 * for itself.
 *
 * An empty `affected` means two different things. For a command that
 * acts on a node it means the node is alone — nothing else comes down
 * with it. For a `Theory` it is not about scope at all: the command
 * queues a worker and moves no row, so the same empty list read as
 * "nothing happens" would be the console flatly misreporting what
 * Confirm does. */
export function previewNote(kind: CommandKind, p: CommandPreview): string | null {
  if (kind === 'Theory')
    return 'nothing closes — a theorist is dispatched to answer; its document lands under documents › agent once its reviewer accepts it.'
  if (p.affected.length === 0 && !p.pipeline)
    return 'nothing else closes with it — the command acts on this one thing.'
  return null
}

// ---------------------------------------------------------------------
// the receipt

export interface CommandRow {
  id: number
  problem: string
  kind: string
  payload: Record<string, unknown>
  idempotency_key: string
  expected_revision: number | null
  status: 'queued' | 'applied' | 'rejected'
  outcome: string | null
  decision_id: number | null
  created_at: string
  applied_at: string | null
}

export type Receipt =
  | { phase: 'waiting'; id: number; polls: number; slow: boolean }
  | { phase: 'applied'; id: number; outcome: string | null }
  | { phase: 'rejected'; id: number; outcome: string; stale: boolean }

/** How long a queued row may sit before the wait itself is the news.
 * A command applies on the daemon's TICK, so on a stopped engine it
 * waits forever — and a spinner that never says so is the console
 * pretending something is happening. ~30s at the poll below. */
export const RECEIPT_SLOW_POLLS = 20
export const RECEIPT_POLL_MS = 1500

export function receiptStart(id: number): Receipt {
  return { phase: 'waiting', id, polls: 0, slow: false }
}

/** One poll's answer. `null` = the read did not arrive (transport, a
 * restarting serve); that is not an outcome, so the wait continues. */
export function receiptStep(prev: Receipt, row: CommandRow | null): Receipt {
  if (prev.phase !== 'waiting') return prev
  if (row === null || row.status === 'queued') {
    const polls = prev.polls + 1
    return { phase: 'waiting', id: prev.id, polls, slow: polls >= RECEIPT_SLOW_POLLS }
  }
  if (row.status === 'applied')
    return { phase: 'applied', id: prev.id, outcome: row.outcome }
  const outcome = row.outcome ?? ''
  return { phase: 'rejected', id: prev.id, outcome, stale: outcome === 'stale' }
}

/** The receipt in one sentence. Rejections are quoted verbatim — the
 * engine wrote a reason a person can act on, and paraphrasing it is
 * how a reader ends up guessing. `stale` is the exception: it is a
 * status word, not a sentence. */
export function receiptLine(r: Receipt): string {
  if (r.phase === 'waiting')
    return r.slow
      ? 'still queued — a command applies on the engine’s next tick, so nothing happens while the engine is stopped. It is not lost.'
      : 'queued — it applies on the engine’s next tick'
  if (r.phase === 'applied')
    return r.outcome === 'committed' || r.outcome === null
      ? 'done — the record has moved; the sky catches up on its next poll'
      : `done — ${r.outcome}`
  if (r.stale)
    return 'the record moved while you were reading it — preview again, then re-issue'
  return `refused — ${r.outcome}`
}


// ---------------------------------------------------------------------
// what the Assistant prepared (§3.8)

export interface PreparedCommand {
  kind: CommandKind
  problem: string
  payload: Record<string, unknown>
  /** what `prepare_command` already read — shown while the confirm
   * window fetches its own, which is the one that decides */
  preview?: CommandPreview
}

function asPrepared(raw: unknown): PreparedCommand | null {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return null
  const o = raw as Record<string, unknown>
  const kind = o.kind
  if (typeof kind !== 'string' || !(COMMAND_KINDS as readonly string[]).includes(kind))
    return null
  if (typeof o.problem !== 'string' || o.problem.trim() === '') return null
  if (o.payload === null || typeof o.payload !== 'object' || Array.isArray(o.payload))
    return null
  const preview =
    o.preview !== null && typeof o.preview === 'object' && !Array.isArray(o.preview)
      ? (o.preview as unknown as CommandPreview)
      : undefined
  return {
    kind: kind as CommandKind,
    problem: o.problem,
    payload: o.payload as Record<string, unknown>,
    preview,
  }
}

const FENCE_RE = /```[^\n]*\n([\s\S]*?)```/g

/** Pull the Assistant's prepared commands out of an answer, and hand
 * back the prose with those blocks removed.
 *
 * The tool returns JSON (`mcp_tools.prepare_command`) and the answer
 * carries it through; the console reads the STRUCTURED block and never
 * the prose around it — "the framework knows but flattens" runs the
 * other way here, and a console that inferred a command from a sentence
 * would be inventing one. A block that does not parse into a command
 * the queue takes is left exactly where it was: it is then ordinary
 * code, and the reader should see it.
 */
export function splitPrepared(text: string): {
  text: string
  commands: PreparedCommand[]
} {
  const commands: PreparedCommand[] = []
  const out = text.replace(FENCE_RE, (whole, body: string) => {
    let parsed: unknown
    try {
      parsed = JSON.parse(body)
    } catch {
      return whole
    }
    const cmd = asPrepared(parsed)
    if (cmd === null) return whole
    commands.push(cmd)
    return ''
  })
  if (commands.length > 0) return { text: out.replace(/\n{3,}/g, '\n\n'), commands }
  // some backends answer with the object and nothing else
  const bare = text.trim()
  if (bare.startsWith('{') && bare.endsWith('}')) {
    try {
      const cmd = asPrepared(JSON.parse(bare))
      if (cmd !== null) return { text: '', commands: [cmd] }
    } catch {
      /* not JSON — ordinary prose that happens to start with a brace */
    }
  }
  return { text, commands: [] }
}
