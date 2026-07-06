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
  slug: string
  status: GoalStatus
  kind: string
  origin: 'root' | 'backward' | 'forward'
  depth: number
  detached: boolean
  alias_target_id: number | null
  is_deliverable: boolean
  statement: string
  lean_path: string
  created_at: string
  attempts: number
  dead_attempts: number
  in_flight: boolean
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
  decisions: Decision[]
  proof_files: string[]
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
  dead_attempts: DeadAttempt[]
  strategies: {
    id: number
    status: string
    created_by: string
    subgoal_count: number
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

export interface ReviewDeliverable {
  fq: string
  problem: string
  slug: string
  ok: boolean
  error: string | null
  kind: string
  module: string | null
  paper: string
  anchors: string[]
  claims: string[]
  folded: number
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

/** A problem citing a shelf paper, as reported by GET /api/papers. */
export interface PaperBoundRef {
  problem: string
  origin: string
}

/** One entry on the paper shelf (GET /api/papers). */
export interface PaperShelfItem {
  id: string
  source_name: string
  pages: number
  chars: number
  original: string
  has_map: boolean
  map_stale: boolean
  bound: PaperBoundRef[]
}

/** GET /api/papers/{pid}/text — extracted markdown with `## p.N` page anchors. */
export interface PaperText {
  id: string
  source_name: string
  pages: number
  text: string
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
    lemma_hints: string[]
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
}
