export type ProblemStatus =
  | 'proving'
  | 'paused'
  | 'awaiting_human'
  | 'stalled'
  | 'idle'
  | 'signoff_pending'
  | 'ingested'
  | 'bridged'

export interface BoardProblem {
  name: string
  status: ProblemStatus
  goals: { open: number; proved: number; shelved: number; total: number }
  in_flight: number
  queued: number
  last_event: string | null
  created_at: string
}

export interface BoardResponse {
  problems: BoardProblem[]
}

export type GoalStatus =
  | 'open'
  | 'attempting'
  | 'proved'
  | 'shelved'
  | 'pending_strategist_review'
  | 'disproved'
  | 'frozen'
  | 'dead'

export interface Goal {
  id: number
  /** the goal's birth annotation — the decomposer's sub-goal comment
   * or the strategist brief's first paragraph; prose, display-only */
  doc?: string | null
  slug: string
  status: GoalStatus
  kind: string
  origin: 'root' | 'backward' | 'forward'
  depth: number
  detached: boolean
  alias_target_id: number | null
  is_deliverable: boolean
  statement: string
  /** binders+conclusion display form read from the stub (the DB
   * statement is often the bare conclusion); null = statement stands */
  signature?: string | null
  lean_path: string
  created_at: string
  attempts: number
  dead_attempts: number
  in_flight: boolean
  /** set when this goal IS the mechanical negation of another goal
   * (AttemptDisproof linkage) — a proved disproof must not dress as
   * ordinary success */
  disproof_of?: { id: number; slug: string } | null
}

export interface Strategy {
  id: number
  goal_id: number
  status: 'proposed' | 'succeeded' | 'dead' | 'superseded' | 'stalled'
  created_by: string
  created_at: string
}

export interface StrategyEdge {
  strategy_id: number
  subgoal_id: number
  position: number
}

export interface Decision {
  id: number
  batch_id: string | null
  trigger_kind: string
  decision_kind: string
  target_id: number | null
  brief: string | null
  reason: string | null
  payload: Record<string, unknown>
  outcome: string | null
  outcome_detail: string | null
  produced_goal_id: number | null
  produced_strategy_id: number | null
  created_at: string
  updated_at: string
  /** which discussion group decided this (v35; null pre-migration) */
  group_id?: number | null
  /** the group a Delegate opened */
  produced_group_id?: number | null
}

export interface ProblemDetail {
  name: string
  status: ProblemStatus
  /** a live daemon is on this problem right now — liveness displays
   * (attempting tint, pulses) must gate on it, not on DB residue */
  engine_working: boolean
  /** the running daemon's leased units here: what each agent is doing */
  workers: { kind: string; slug: string; leased_at: string | null }[]
  shelve_threshold: number
  created_at: string
  ingested_at: string | null
  library_bridged_at: string | null
  strategist_directive: string | null
  goals: Goal[]
  strategies: Strategy[]
  strategy_edges: StrategyEdge[]
  anchor_edges: { from: number; to: number }[]
  /** proof-file import citations (from: cited, to: citer) — the DAG's
   * cross-links; what makes 'linked forward' work visibly linked */
  citation_edges: { from: number; to: number }[]
  decisions: Decision[]
  proof_files: string[]
  /** current Programme rev (research mode); null before bootstrap —
   * the Programme tab only exists when this is set */
  programme_rev: number | null
  /** revision events for the timeline — a proposal cycle leaves no
   * decision row, so the argument was invisible there */
  programme_events: ProgrammeEvent[]
  /** the discussion-group tree (v35); one entry (the top group) is the
   * ordinary case and reads exactly as it did before groups existed */
  groups?: Group[]
}

/** A discussion group (v35): one charter, one Programme, one
 * strategist/adversary loop, and the subtree it grows. Every problem
 * has a TOP group — itself, facing you — and may delegate burdens to
 * sub-groups, which argue their own charter in parallel. */
export interface Group {
  id: number
  problem: string
  parent_id: number | null
  /** the top group IS the problem; its charter is the Manifest */
  is_top: boolean
  /** the claim this group was handed (empty for the top group) */
  charter: string
  status: 'active' | 'delivered' | 'returned' | 'closed' | string
  anchor_goal_id: number | null
  created_at: string
}

export interface ProgrammeEvent {
  rev: number
  status: string
  rounds: number
  created_at: string
}

export interface Programme {
  current: {
    rev: number
    body: string
    rounds: number
    created_at: string
    reservations: string[]
  } | null
  history: { rev: number; status: string; rounds: number; created_at: string }[]
  /** which group's chain this is (null before any group exists) */
  group_id?: number | null
  /** every group in the problem — the others argue their own charters */
  groups?: Group[]
}

export interface DeadAttempt {
  id: number
  pipeline_id: string
  failure_reason: string
  failure_detail: string | null
  proposal_md: string | null
  ts: string
}

export interface GoalDetail extends Omit<Goal, 'dead_attempts'> {
  /** declaration source — the proof file minus its import prelude */
  proof_text: string | null
  /** the file proof_text was read from */
  source_path: string
  /** what that text IS — a node's own file is a sorry stub for its
   * whole working life, so the panel must say whether it is showing a
   * finished proof, a live decomposition, or an attempt mid-write */
  source_state?: 'winning_route' | 'open_route' | 'in_flight' | 'own_file'
  /** the route the shown text belongs to (route states only) */
  source_strategy_id?: number | null
  dead_attempts: DeadAttempt[]
  strategies: {
    id: number
    status: string
    created_by: string
    subgoal_count: number
    /** the route's children, named — absent on a pre-upgrade serve */
    subgoals?: { id: number; slug: string }[]
  }[]
}

export interface Amend {
  id: number
  problem: string
  file: string
  proposed_body: string
  current_body: string
  question: string
  reason: string
  created_at: string
}

export interface Signoff {
  problem: string
  ingested_at: string | null
  snapshot: {
    stored_at: string
    deliverable_count: number
    ok_count: number
  } | null
}

export interface InboxResponse {
  amends: Amend[]
  signoffs: Signoff[]
}

/** Anchor/claim entries in the review snapshot arrive as bare names
 * OR as {kind, module, name} records (the recompute path emits the
 * latter — live-run catch, 2026-07-08). */
export type ReviewEntry =
  | string
  | { kind?: string; module?: string | null; name: string; signature?: string | null }

export interface ReviewDeliverable {
  fq: string
  problem: string
  slug: string
  ok: boolean
  error: string | null
  kind: string
  module: string | null
  paper: string
  anchors: ReviewEntry[]
  claims: ReviewEntry[]
  folded: number
  /** the declaration header, server-extracted from the proof file —
   * what the human actually reads before vouching */
  signature?: string | null
}

export interface ReviewResponse {
  stored_at: string
  deliverables: ReviewDeliverable[]
  union_count: number
}

export interface UsageKind {
  kind: string
  spawns: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_new_tokens: number
  turns: number
  wall_sec: number
}

export interface UsageProblem {
  problem: string
  spawns: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_new_tokens: number
  turns: number
  wall_sec: number
  kinds: UsageKind[]
}

/** One live worker lane on the run console (GET /api/run). */
export interface RunWorker {
  kind: string
  slug: string
  /** which problem this agent is on — a pattern scope runs several */
  problem?: string | null
  /** the discussion group this agent speaks for (Strategist seats are
   * per group since v35); null = not a group seat */
  group?: Group | null
  statement: string | null
  leased_at: string | null
  /** Strategist only: why it woke (trigger_kind) — names the mode of
   * this think: reviewing results, batch follow-up, audit, routine */
  mode: string | null
  path: string | null
  /** tail of the file it is writing — spawn writes go through to the
   * real path, so this is the live view; null = nothing on disk yet */
  file: { tail: string; size: number; quiet_sec: number } | null
  /** Strategist only (research mode): the live proposal↔reviewer
   * cycle read from its working files — the argument would otherwise
   * be half an hour of silence */
  cycle?: {
    phase: 'proposing' | 'judging' | 'revising' | 'passed'
    round: number
    objections: string[]
    since_sec: number | null
  } | null
}

/** One subscription window (from the account's own OAuth usage read). */
export interface QuotaWindow {
  utilization: number
  resets_at: string | null
}

export interface RunStatus {
  daemon: DaemonStatus
  problem: string | null
  /** every problem under the run's lens — more than one when the
   * scope is a pattern; `problem` is the resolved pick */
  problems?: string[]
  goals: { open: number; attempting: number; proved: number; total: number } | null
  workers: RunWorker[]
  burn_run: { problems: UsageProblem[] } | null
  burn_5h: { problems: UsageProblem[] } | null
  /** null = not knowable right now (no login file, offline) — omitted, never faked */
  quota: {
    five_hour: QuotaWindow | null
    seven_day: QuotaWindow | null
    scoped: { name: string; percent: number; resets_at: string | null; is_active: boolean }[]
  } | null
  recent: { kind: string; outcome: string; at: string }[]
}

export interface LibraryDecl {
  slug: string
  name: string | null
  file: string | null
  signature: string | null
  decl_kind: string | null
  lifecycle: string
}

export interface LibraryProblem {
  problem: string
  decls: LibraryDecl[]
}

/** One declaration in a Library chapter (GET /api/library/{problem}):
 * curated docstring + kernel-true signature, in source order. */
export interface LibraryChapterDecl {
  slug: string
  name: string | null
  signature: string | null
  decl_kind: string | null
  doc: string
  /** the decl's real source block (attributes + header + proof body,
   * docstring excluded) — the run state seeds a live editor with it */
  source: string | null
  /** the module preamble (open/open scoped/universe/variable lines)
   * that makes `source` elaborate standalone — the librarian hoists
   * instance hypotheses into `variable`, so a probe without this
   * loses them and the goal collapses into sorries */
  context: string | null
  is_deliverable: boolean
  /** how many OTHER modules of this problem reach for it — the
   * keystone weight (ingest weakens the claim flags; demonstrated
   * reuse is the honest importance signal) */
  used_by: number
}

export interface LibraryChapterFile {
  path: string
  module_doc: string
  decls: LibraryChapterDecl[]
  /** within-problem import edges (paths) — the file-level sky */
  imports_within: string[]
}

/** The sign-off signature (v27): the operator's claim (name), the
 * machine's observations (evidence, captured never typed), and the
 * content seal. seal_ok=false ⇒ the reviewed snapshot changed AFTER
 * signing — surfaces must say so, not display a stale vouch. */
export interface SignoffRecord {
  name: string | null
  at: string
  snapshot_sha: string | null
  evidence: { claude_email: string | null; os_user: string; host: string }
  seal_ok: boolean
}

export interface LibraryChapter {
  problem: string
  bridged_at: string | null
  /** the problem's root statement — what the bridge gate re-proves
   * from these modules alone; the chapter opens with it */
  root?: { slug: string; statement: string } | null
  files: LibraryChapterFile[]
  signoff?: SignoffRecord | null
  /** the gates' recorded guarantees — sorry-free, axioms whitelist */
  colophon?: { decls: number; axioms: string[] } | null
}

/** A problem citing a shelf paper, as reported by GET /api/papers. */
export interface PaperBoundRef {
  problem: string
  origin: string
}

/** One entry on the paper shelf (GET /api/papers). */
export interface PaperShelfItem {
  id: string
  source_name: string
  /** owner-editable display title; null = the filename stands in */
  title: string | null
  /** who shelved it: 'user' (upload/CLI) or 'fetched' (the Scholar
   * agent during a run); null = shelved before provenance existed */
  added_by: string | null
  pages: number
  chars: number
  original: string
  has_map: boolean
  map_stale: boolean
  bound: PaperBoundRef[]
}

/** One paper bound to a problem (GET /api/problems/{p}/papers). */
export interface ProblemPaperBinding {
  id: string
  /** who bound it: 'manifest' | 'user' | 'scholar' */
  origin: string
  reason: string | null
  source_name: string | null
  /** binding survives but the shelf entry is gone */
  missing: boolean
}

export interface DaemonStatus {
  running: boolean
  /** the boot window: Run was pressed but the engine hasn't claimed its
   * lock yet (seconds) — running is still false, idle it is NOT */
  starting: boolean
  pid: number | null
  /** exact problem name or LIKE pattern; null = workspace-wide */
  scope: string | null
  /** ISO start time of the running daemon; null when idle */
  started_at: string | null
  /** only ever true while running (a stale stop-file is not a state) */
  stopping: boolean
  in_flight_leases: number
  /** Lean toolchain phase: 'warming' (cold start, minutes), 'ready',
   * or null (no gateway) — names the dead-air minutes after Run */
  gateway: 'warming' | 'ready' | null
  /** how the LAST run ended; null while running or before any run.
   * rc=0 clean finish · rc>0 crash (error says why) · rc=null forced */
  last_exit: {
    at: string
    rc: number | null
    error: string | null
    scope: string | null
  } | null
}

export interface ManifestData {
  problem: string
  body: string
  settings: {
    axioms_whitelist: string[]
    forbidden_lemmas: string[]
    library: boolean
  }
  pending_amend: boolean
}

export interface ConfigSetting {
  key: string
  yaml: string | number | null
  resolved: string | number | null
  type: 'str' | 'int'
  description: string
  /** present on .model keys: the UI offers these (typo-proof select);
   * the resolved value is always included */
  choices?: string[]
}

export interface Meta {
  workspace: string
  db: 'ok' | 'missing' | 'behind'
  daemon: DaemonStatus
  inbox_count: number
  /** auth awareness (the login itself is Claude Code's own wizard) */
  claude: { installed: boolean; logged_in: boolean; subscription: string | null }
  /** the console's Lean-layer self-check (can break long after install) */
  lean_ready: { lake: boolean; mathlib: boolean }
}
