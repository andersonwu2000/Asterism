"""DB schema + connection. Single source of truth.

Tables (see docs/architecture.md §3):
  problems, goals, strategies, strategy_subgoals,
  pipelines, dead_attempts, queue, strategist_decisions (Phase 2)

Schema version tracked via `PRAGMA user_version`:
  0 = pre-Phase 2 (everything before strategist_decisions)
  2 = Phase 2 (new tables/columns/CHECK extensions; see docs/archive/design/phase2/)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path("asterism.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    name           TEXT PRIMARY KEY,
    created_at     TEXT NOT NULL,
    -- v40 (Manifest retirement) — the user's WORD: standing directives,
    -- verbatim NL. Rendered into every agent surface at every depth and
    -- never replaced by any group's charter; the machine reads it and
    -- never writes it (writer = state/intent.set_word, driven by the
    -- serve UI / `asterism word` only; history rides user_file_history
    -- under the pseudo-key 'word'). The problem's GOAL is the top
    -- group's `groups.charter` row, not a problems column.
    user_word      TEXT NOT NULL DEFAULT '',
    -- Phase 2 — Strategist first-launch tracking.
    -- `bootstrap_done=0` → T0 trigger fires on next dispatcher tick.
    -- Set to 1 by Strategist's first commit (EmitDirective / Inject / Noop)
    -- so subsequent ticks fall through to T1 (wall-clock routine).
    bootstrap_done INTEGER NOT NULL DEFAULT 0
                    CHECK(bootstrap_done IN (0,1)),
    -- Phase 2 — standing directive set by Strategist EmitDirective /
    -- Reopen-with-directive. Injected into Context.md `## Strategist
    -- directive` section by `compile_context` for Backward / Builder /
    -- Forward cold-start. Overwrite-on-write (single text slot, no history).
    strategist_directive TEXT NULL DEFAULT NULL,
    -- Phase 2 — wall-clock timestamp of last Strategist commit (ANY trigger).
    last_strategist_at TEXT NULL DEFAULT NULL,
    -- Timestamp of the last ROUTINE Strategist commit specifically. Drives
    -- T1 independently of event-driven triggers (pending_review /
    -- inject_batch_done / first_launch): those bump last_strategist_at but
    -- NOT this, so the routine audit fires on its own fixed cadence instead
    -- of being starved by a busy event stream (stokes 2026-06-12: 0 routine
    -- over 5h because 18 event commits kept resetting the shared clock).
    last_routine_at TEXT NULL DEFAULT NULL,
    -- anchor+claim (v14) — set to 1 by a Strategist `Ingest` decision when
    -- `library.require_signoff` is on: harvest PAUSES here until the human
    -- runs `asterism approve-ingest` (→ enqueue Librarian) or
    -- `asterism reject-ingest` (→ back to proving). Default 0.
    ingest_signoff_pending INTEGER NOT NULL DEFAULT 0
                    CHECK(ingest_signoff_pending IN (0,1)),
    -- Phase 6 (v16) — the problem's TERMINAL state: ISO timestamp of the
    -- Strategist `Ingest` commit (the ONLY exit trigger; Done was fused
    -- into it). NULL = still live. Drives T1 liveness, the T4 stall
    -- predicate's cond-1 ("Ingest not yet emitted"), `_strategist_row_is_
    -- stale`, and the daemon exit check. Cleared by the rollback
    -- auto-revoke when a post-Ingest un-prove invalidates the terminal
    -- judgment. Backfilled once for legacy root-proved problems (v16
    -- migration) so they are not re-triggered as stalled.
    ingested_at    TEXT NULL DEFAULT NULL,
    -- Operator bench (2026-08-31): a benched problem takes no refill
    -- dispatch and no Strategist seat, state untouched — the owner's
    -- "hopeless for now, keep the assets" lever (`asterism bench`).
    benched        INTEGER NOT NULL DEFAULT 0 CHECK(benched IN (0,1)),
    -- Problem FSM (v29, problem_fsm_design.md §2): the explicit
    -- lifecycle state; single sanctioned mutator =
    -- transitions.apply_problem_transition. 'revoked' = post-Ingest
    -- un-prove quarantine (seal torn automatically; re-entry is the
    -- operator's `asterism revive`). 'stalled' is a derived guard on
    -- 'active', never a state.
    state          TEXT NOT NULL DEFAULT 'active'
                    CHECK(state IN ('active', 'awaiting_human',
                                    'ingest_signoff', 'ingested',
                                    'revoked', 'refuted'))
);

-- v35 (discussion_group_design.md) — a DISCUSSION GROUP: one charter, one
-- Programme, one strategist/adversary loop, and the subtree it grows. The
-- tree of groups lives inside ONE problem: a parent must cite its child's
-- bricks and cross-problem citation is forbidden (`_cite_gate.py:123`), so
-- groups are a partition of a problem, never recursive problems.
--
-- The TOP group of each problem is a real row with `parent_group_id IS
-- NULL` — not a special case in the code. Its charter is the problem's
-- GOAL, written at init and amended only through state/intent.set_charter
-- (v40, Manifest retirement). Every pre-v35 row in the problem belongs
-- to it.
CREATE TABLE IF NOT EXISTS groups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    problem         TEXT NOT NULL REFERENCES problems(name),
    -- NULL = the problem's top group, the only one that faces a human.
    -- ON DELETE CASCADE: a group cannot outlive its parent, and it makes
    -- `asterism reset`'s blanket per-problem DELETE order-independent —
    -- without it the self-FK trips mid-statement when a parent goes first.
    parent_group_id INTEGER NULL DEFAULT NULL
                        REFERENCES groups(id) ON DELETE CASCADE,
    -- The charter: the claim/task this group was asked to settle —
    -- verbatim from the parent's `Delegate` brief, or, for the top group,
    -- the problem's goal as the user authored it. One column, one meaning
    -- at every depth: that uniformity is what lets a sub-group reuse
    -- every problem-level mechanism down to Ingest.
    charter         TEXT NOT NULL DEFAULT '',
    -- OPTIONAL anchor. The main shape (a proactively delegated burden) has
    -- none: the group starts from prose and mints its own bricks, exactly
    -- like a pure-NL problem (`cli.py:355`). Only the rescue shape — an
    -- existing goal promoted to a group — carries one.
    anchor_goal_id  INTEGER NULL DEFAULT NULL
                        REFERENCES goals(id) ON DELETE SET NULL,
    -- The parent's `Delegate` row. NULL for the top group. Both this and
    -- `strategist_decisions.group_id` are SET NULL on delete: the two
    -- tables point at each other, so any delete order would otherwise be
    -- wrong in one direction (the reset path hits exactly this).
    opened_by       INTEGER NULL DEFAULT NULL
                        REFERENCES strategist_decisions(id)
                        ON DELETE SET NULL,
    -- 'active'    — working.
    -- 'delivered' — Ingested upward; its bricks are the parent's to cite.
    -- 'returned'  — handed the charter back (refuted / amend / exhausted).
    -- 'closed'    — the parent retired it.
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'delivered',
                                         'returned', 'closed')),
    -- Per-group wake clocks. DUAL-WRITE WINDOW (Stage A→D): the readers
    -- (`problems_needing_t1`, `_strategist_inflight`) still consult the
    -- `problems` columns; these are backfilled and maintained so the flip
    -- is a reader change, not a data migration. Stage D drops the problems
    -- columns — until then, a divergence between the two is a bug.
    last_routine_at    TEXT NULL DEFAULT NULL,
    last_strategist_at TEXT NULL DEFAULT NULL,
    -- Copy-on-open (v39): the parent's `## Conventions` AT THE MOMENT this
    -- group was opened. Workers resolve conventions from their OWN group
    -- only — no ancestor walk — so this snapshot is the one channel by
    -- which a parent's footguns reach a child that would otherwise never
    -- know they existed. It is a seed, not a link: it stops being read the
    -- moment this group ships its own `## Conventions`, and the group is
    -- free to drop any of it in its first revision.
    conventions_seed   TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem     TEXT    NOT NULL REFERENCES problems(name),
    slug        TEXT    NOT NULL,
    lean_path   TEXT    NOT NULL UNIQUE,
    statement   TEXT    NOT NULL,
    -- kind / origin enums kept minimal; extend when implementing
    -- generalizer / refuter / construction (architecture.md §13).
    -- Phase 2 added 'forward' to origin (Forward pipeline-produced lemmas).
    kind        TEXT    NOT NULL DEFAULT 'theorem'
                    -- Phase 4 — non-theorem kinds bypass the prove
                    -- loop: Forward writes them, framework type-checks
                    -- once, status='proved' immediately, BFS never
                    -- dispatches Backward / Builder on them. See
                    -- `NON_THEOREM_KINDS` in pipeline/forward.py for
                    -- the single source of truth on which kinds skip
                    -- dispatch / axiom probe / Library promotion gate.
                    -- v19 adds 'inductive' (Forward may mint new
                    -- inductive types; sorry-free-only at commit).
                    -- v20 adds 'instance' (named data instances; the
                    -- parse gate rejects anonymous ones).
                    CHECK(kind IN ('theorem','def','structure','class',
                                   'inductive','instance')),
    origin      TEXT    NOT NULL
                    CHECK(origin IN ('root','backward','forward')),
    -- Phase 2 status additions:
    --   'pending_strategist_review' (transitional) — agent declined with
    --     `shelve` directive; Strategist judges (ConfirmShelve/Reopen/Inject).
    --   'disproved' — agent declined with `unprovable`; dedupe blocks
    --     same-shape proposals. 2026-08-18: a claimed-counterexample
    --     PARK, no longer irreversibly terminal — a strategist Inject
    --     revives it (GOAL_EDGES ("disproved","open")); a kernel
    --     witness requirement is the deliberately unscheduled sequel.
    -- Existing 'shelved' semantic shifted to soft terminal (reopenable; dedupe
    -- doesn't block) covering: parent_needs_fix decline, ConfirmShelve from
    -- Strategist, and cascade descendants of ConfirmShelve.
    -- Phase 5 — 'frozen' is the pre-launch state for root goals. cli init
    -- creates roots as frozen; BFS `open_goals` filters status='open' so
    -- frozen roots are invisible to dispatch. Strategist `first_launch`
    -- trigger fires while root is frozen (may fire multiple times during
    -- initial Inject batches); Strategist `Reopen(root)` flips frozen→open
    -- to release BFS once vocabulary / lemmas are in place. Replaces the
    -- earlier `problems.bootstrap_done` gate.
    -- Split rule (2026-09-04 update — the goal status 'dead' retired
    -- at v51; a goal is a STATEMENT and only the kernel settles one):
    --   failure_reason='agent_infeasible' → 'disproved' (the disproof
    --     gate certified a counterexample; dedupe blocks same-shape
    --     proposals).
    --   failure_reason='agent_shelved' → 'pending_strategist_review'
    --     (transitional; Strategist judges).
    --   failure_reason='parent_needs_fix' → 'shelved', event
    --     'wrong_context_park' (the DECOMPOSITION was wrong, the
    --     statement was never judged). Every strategy hanging on the
    --     goal dies — inward and upward — so the parent retries with a
    --     new decomposition; the goal itself stays revivable.
    -- Terminal soft/hard semantics:
    --   'shelved' — a PARK, not a verdict; Strategist may Reopen,
    --     dedupe does NOT block, a citation may revive it. Which park
    --     it is lives in `goal_events.event`, not in the status.
    --   'proved' / 'disproved' — the two KERNEL-checked terminals, and
    --     the whole of GOAL_HARD_TERMINALS: citing a disproved goal is
    --     an error, dedupe blocks its twins, upward strategies die, and
    --     a strategist Inject may not overturn it (the way out of a
    --     refutation is a different statement). The ('disproved','open')
    --     FSM edge exists for OPERATOR repair only.
    status      TEXT    NOT NULL
                    CHECK(status IN ('open','attempting','proved','shelved',
                                     'pending_strategist_review','disproved',
                                     'frozen')),
    depth       INTEGER NOT NULL DEFAULT 0,
    attempts    INTEGER NOT NULL DEFAULT 0,
    -- (`entry_kind` routing column removed in v33 — the Formalizer
    -- merge, update_plan_2026_07 #1: the worker decides prove-vs-split
    -- itself, so pre-dispatch routing no longer exists. Predecessor
    -- `difficulty` died the same death.)
    -- Set to 1 by `verify.root_integrity_gate` after a root goal's
    -- axiom_probe passes; reset to 0 by `update_goal_status` whenever
    -- the goal leaves 'proved' (cascade rollback, manual reset). The
    -- dispatcher gate query consults this so a once-verified root is
    -- not re-probed every tick — without this marker the gate runs an
    -- axiom_probe per proved root per loop iteration, scaling O(N) over
    -- proved problems (244 miniF2F + 1 → ~115min stall before any
    -- dispatch on a benchmark-loaded workspace). Column is meaningful
    -- only for origin='root' rows; sub-goals carry the default 0 and
    -- it is never read for them.
    integrity_verified INTEGER NOT NULL DEFAULT 0
                    CHECK(integrity_verified IN (0,1)),
    -- Phase 2 — Strategist Reopen on a goal whose upward strategy chain
    -- is broken (any ancestor strategy ∈ {dead, superseded}) sets this
    -- flag. BFS `open_goals` walk treats `detached=1` rows as if they
    -- have an alive parent strategy, so the goal can be dispatched
    -- standalone. Proof becomes a usable library lemma even though no
    -- ancestor strategy threads it back to root. NULL/0 for goals with
    -- live ancestor chains.
    detached    INTEGER NOT NULL DEFAULT 0
                    CHECK(detached IN (0,1)),
    -- (Phase 7-D removed `builder_session_id` and `backward_session_id`
    -- columns. The cross-pipeline session passing they served is now
    -- handled by `Tooling/pipeline/_retry.py` with sid as a local
    -- pipeline-scope var. The migration in init_schema below drops
    -- these columns from older DBs.)
    -- When this goal is an alias (its lean file's proof body
    -- delegates to another goal via `apply <canonical_slug> <;>
    -- assumption`), `alias_target_id` points at that canonical goal.
    -- prune.is_retained treats a goal as retained if any alive goal
    -- aliases to it, so an orphan (status='proved' under a dead/
    -- superseded strategy) survives long enough for the eventual root
    -- lake build to find its file. NULL for non-alias goals.
    alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
    -- anchor+claim architecture (docs/internal/archive/anchor_claim_design.md):
    -- set to 1 when the Strategist marks this node a top-level
    -- *deliverable* (a claim or a delivered def). `asterism review`
    -- computes each deliverable's kernel anchor closure and presents
    -- anchor+claim for human opt-out review; `asterism reject` kills a
    -- rejected node. Independent of origin/detached (a deliverable can
    -- be a Forward lemma, a Backward sub-goal, or the root). Default 0.
    is_deliverable INTEGER NOT NULL DEFAULT 0
                    CHECK(is_deliverable IN (0,1)),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(problem, slug)
);

-- strategies.lean_path = parent goal's lean_path (the eventual write
--   target when this strategy wins Verify). NOT UNIQUE: multiple
--   strategies for the same goal share the same target.
-- strategies.scratch_path = this strategy's standalone patch lean module
--   (Problems/<p>/proofs/_strategy_s<sid>.lean). UNIQUE per strategy.
-- 'superseded' = another strategy for the same goal won Verify; this
--   one's work is moot and its sub-goals can be filtered out.
CREATE TABLE IF NOT EXISTS strategies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id      INTEGER NOT NULL REFERENCES goals(id),
    lean_path    TEXT    NOT NULL,
    scratch_path TEXT    NOT NULL DEFAULT '',
    status       TEXT    NOT NULL
    -- 'stalled' (Phase 11): all subgoals settled, >=1 soft-shelved, zero
    -- alive — the strategy is PARKED but reopenable (mirrors a goal's
    -- 'frozen'). Terminal-for-propagation (fills the producing Inject's
    -- outcome) yet NOT alive-conducting (excluded from the alive-DAG
    -- `IN('proposed','succeeded')` walk), so T4 sees the collapse. A
    -- subgoal Reopen flips it back to 'proposed'. Replaces the
    -- reconcile band-aid that filled the inject outcome out-of-band.
                     CHECK(status IN ('proposed','succeeded','dead',
                                      'superseded','stalled')),
    proposal_md  TEXT    NOT NULL DEFAULT '',
    created_by   TEXT    NOT NULL,
    created_at   TEXT NOT NULL
);

-- link_kind (v44): edge provenance. 'minted' = the strategy CREATED this
-- sub-goal (authorship — the sub-goal exists to serve that strategy's
-- argument); 'cited' = the strategy REUSES a pre-existing sibling (a
-- dependency/wait edge — the sub-goal has its own life). Readers that
-- reason about creation context (brief inheritance, hard-terminal Reopen
-- walks) must traverse 'minted' edges only; readers that reason about
-- dependency (verify-wait, prune retention, cycle detection, shelve
-- cascade) traverse both. Conflating the two leaked a redispatch brief
-- into a cited sibling's whole subtree (2026-08-25, six intake declines
-- in three minutes).
CREATE TABLE IF NOT EXISTS strategy_subgoals (
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    subgoal_id  INTEGER NOT NULL REFERENCES goals(id),
    position    INTEGER NOT NULL,
    link_kind   TEXT NOT NULL DEFAULT 'minted'
                    CHECK(link_kind IN ('minted','cited')),
    PRIMARY KEY (strategy_id, subgoal_id)
);

-- pipelines: one row per DISPATCHED pipeline, for its whole lifetime (v38).
-- INSERTed status='running' at dispatch (`record_pipeline_start`), UPDATEd
-- to succeeded/failed at completion (`finish_pipeline`). The row existing
-- from dispatch is what lets `dead_attempts` (FK → pipelines.id) be written
-- EAGERLY, 1:1 with each `goals.attempts` increment — before v38 the rows
-- were buffered until a normal worker return, and a worker thread dying by
-- exception banked the increments while the forensic rows died with the
-- stack frame (goal 7486, 2026-08-08: attempts=10 vs 7 dead_attempts).
-- A daemon crash leaves 'running' rows behind; `recovery.recover_at_startup`
-- finalizes them as failed/daemon_crashed (scope-filtered).
-- Phase 2 — `kind` adds 'Strategist' / 'Forward'; `target_kind` adds 'Problem'.
-- Forward target_id = problem_name (TEXT NOT NULL preserved; see
-- migration_plan §C option 1). Strategist target = problem.root.id (Goal).
-- v23 — `kind` adds 'Scholar' (paper pipeline v2: citation resolution +
-- fetch worker; docs/internal/archive/paper_pipeline_design.md D11).
-- v33 — `kind` adds 'Formalizer' (merged worker, update_plan_2026_07 #1).
-- v52 — `kind` adds 'Theorist' (theory_wake_design.md §3): the theory
-- layer's own pipeline, dispatched from a `Theorize` decision the way a
-- Formalizer is dispatched from an Inject. Group-targeted, NL-only.
-- 'Builder'/'Backward'/'Forward' stay VALID for historical rows — never
-- rewrite history; archaeology keys on these strings.
CREATE TABLE IF NOT EXISTS pipelines (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL
                    CHECK(kind IN ('Builder','Backward','Verify',
                                   'Strategist','Forward','Librarian',
                                   'Scholar','Formalizer','Theorist')),
    target_id   TEXT NOT NULL,
    -- 'Group' (v35): a Strategist wake belongs to ONE discussion group, so
    -- the seat is per group, not per problem. Pre-v35 Strategist rows are
    -- 'Problem' and stay valid.
    target_kind TEXT NOT NULL
                    CHECK(target_kind IN ('Goal','Strategy','Problem',
                                          'Group')),
    status      TEXT NOT NULL CHECK(status IN ('running','succeeded',
                                               'failed')),
    -- NULL while running; set by finish_pipeline / recovery.
    outcome     TEXT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT NULL
);

-- dead_attempts.artifacts: JSON dict of all agent output files for forensic
-- review. .attempts/<pid>/ filesystem dir is purely ephemeral, deleted at
-- pipeline end (success or failure); DB is single source of truth.
CREATE TABLE IF NOT EXISTS dead_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id       INTEGER NOT NULL,
    target_kind     TEXT NOT NULL,
    pipeline_id     TEXT NOT NULL REFERENCES pipelines(id),
    failure_reason  TEXT NOT NULL,
    failure_detail  TEXT,
    proposal_md     TEXT,
    artifacts       TEXT,                    -- JSON {filename: text}
    ts              TEXT NOT NULL
);

-- queue: dispatch backlog. Phase 2 adds 'Strategist'/'Forward' kinds,
-- explicit `target_kind` (was inferred from `kind` historically; with
-- Forward using a Problem target the inference breaks), and `decision_id`
-- (FK to strategist_decisions; non-null means this queue entry was
-- emitted by a Strategist Inject decision — its brief flows to the
-- spawned pipeline via Context.md `## The argument for this brick`).
CREATE TABLE IF NOT EXISTS queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL
                    CHECK(kind IN ('Builder','Backward','Verify',
                                   'Strategist','Forward','Librarian',
                                   'Scholar','Formalizer','Theorist')),
    target_id   TEXT NOT NULL,
    -- 'Group' (v35): see the pipelines note — one Strategist seat per
    -- discussion group is what lets sibling groups run concurrently.
    target_kind TEXT NOT NULL DEFAULT 'Goal'
                    CHECK(target_kind IN ('Goal','Strategy','Problem',
                                          'Group')),
    priority    INTEGER NOT NULL DEFAULT 0,
    decision_id INTEGER NULL DEFAULT NULL REFERENCES strategist_decisions(id),
    -- v17 queue contract (task #3): `problem` scopes every row (scope-safe
    -- pop/flush/recovery — the #74 class); `payload` carries structured
    -- per-row data as JSON (librarian per-file units: {"file": ...} — the
    -- \x1f target_id smuggle is retired from the PERSISTED contract; the
    -- encoding survives only as the in-process dispatch identity + the
    -- librarian_fail_counts key, composed at pop). `owner_pid`+`leased_at`
    -- are the lease: pop CLAIMS a row (visible to concurrent dispatchers
    -- as in-flight), completion deletes it; expired leases (dead owner OR
    -- TTL — Windows reuses PIDs, so liveness alone is not enough) are
    -- released for re-claim.
    problem     TEXT NOT NULL DEFAULT '',
    payload     TEXT,
    owner_pid   INTEGER,
    leased_at   TEXT,
    created_at  TEXT NOT NULL
);

-- Paper pipeline v2 (D13): problem ↔ shelved-paper bindings — the
-- backend of the frontend's checkbox model. origin: 'manifest' =
-- migrated from the retired Manifest.md's legacy `paper:` pointer
-- (historical rows only); 'scholar' = fetched by a Scholar pipeline
-- (reason records why); 'user' = bound via CLI/UI. CREATE TABLE IF
-- NOT EXISTS suffices for fresh + existing DBs (no user_version bump
-- needed).
CREATE TABLE IF NOT EXISTS problem_papers (
    problem    TEXT NOT NULL REFERENCES problems(name),
    paper_id   TEXT NOT NULL,
    -- v42 (owner ruling 2026-08-22): origin = the calling seat.
    -- 'scholar' stays for historical rows; 'agent' is the
    -- in-process (shim) path where no ASTERISM_SEAT env exists.
    origin     TEXT NOT NULL CHECK(origin IN ('manifest','scholar','user','agent',
        'strategist','adversary','formalizer','librarian',
        'presearch','theorist')),
    reason     TEXT NULL DEFAULT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (problem, paper_id)
);

-- Per-problem machine settings (frontmatter dissolve, 2026-07-07;
-- sole source since the v40 Manifest retirement): value is JSON. ALL
-- access via state/settings.py; an absent key means the framework
-- default (effective_axioms semantics untouched — an empty whitelist
-- never weakens a gate).
CREATE TABLE IF NOT EXISTS problem_settings (
    problem    TEXT NOT NULL REFERENCES problems(name),
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (problem, key)
);

-- User-intent content history (self-audit 2026-07-12 §3-1b + §3-3,
-- v28; v40 re-scope): first-load baseline + every change on the two
-- hand-authored files (Root.lean / Defs.lean — swept by IntentCache,
-- catching any write channel incl. a Bash bypass of the spawn
-- write-deny) and on the two DB-resident intent values (pseudo-keys
-- 'charter' / 'word', recorded by their state/intent writers — audit
-- trail only: mid-run charter/word edits are a legal, live channel).
-- root_integrity_gate requires the two FILES to still match their
-- baseline before a proved root verifies (benchmark comparability =
-- adapter pins upstream == init, this pins init == proved; Root.lean's
-- pin is statement-level — the framework's own proof-landing rewrites
-- the proof body, task #120). source='repin' rows are the sanctioned
-- change acks: operator re-baselines (`asterism repin`), accepted
-- amendments, and charter/word writes.
CREATE TABLE IF NOT EXISTS user_file_history (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    problem TEXT NOT NULL REFERENCES problems(name),
    file    TEXT NOT NULL,
    sha     TEXT NOT NULL,
    body    TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    source  TEXT NOT NULL DEFAULT 'observed'
            CHECK (source IN ('observed', 'repin'))
);

-- Phase 2 — Strategist decision audit log + awaiting_human gate.
-- One row per Strategist commit. `payload` JSON stores non-text-content
-- structured params (pipeline name for Inject, scope/body for
-- EmitDirective, file/proposed_body for RequestUserAmend, directive for
-- Reopen). `outcome` is cascade-filled (e.g. 'forward_no_new_goal',
-- 'awaiting_human', 'accepted', 'rejected', 'consumed'). `outcome_detail`
-- (Phase, #4) carries the agent's rich terminal-decline reasoning (e.g. a
-- Forward decline's `## Why` prose) so the Strategist's next wake sees WHY
-- its brief was rejected, not just the coarse `outcome` enum.
CREATE TABLE IF NOT EXISTS strategist_decisions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    problem             TEXT NOT NULL REFERENCES problems(name),
    triggered_at_tick   INTEGER NOT NULL,
    trigger_kind        TEXT NOT NULL
                            -- 'first_launch' + 'audit': retired at runtime
                            -- (audit merged into routine 2026-07-25); kept in
                            -- the CHECK for old rows.
                            -- 'stall' (v43): T4 structural-stall rescue,
                            -- first-class since 2026-08-24 (was conflated
                            -- with inject_batch_done, leaving the rescue
                            -- rate grep-only).
                            -- 'human' (v48, human_interface_design §3.2): a
                            -- person's command, not a clock or a cascade. Its
                            -- `actor` column is APPENDED by `_migrate_to_v48`.
                            CHECK(trigger_kind IN
                                  ('first_launch','pending_review','routine',
                                   'inject_batch_done','audit','stall',
                                   'routine_fired','human')),
    decision_kind       TEXT NOT NULL
                            -- 'Reopen'/'InitializeDefs': LEGACY, never emitted now
                            -- (see strategist.DECISION_KINDS); retained so pre-
                            -- 2026-05-28 rows stay valid — dropping needs a table
                            -- rebuild (16 'Reopen' rows would violate), low ROI.
                            -- 'MarkDeliverable' (v13, anchor+claim): Strategist
                            -- flags a Forward node top-level; sets goals.is_deliverable.
                            -- 'Ingest' (v14, anchor+claim): Strategist judges the
                            -- problem terminal → harvest deliverables to Library.
                            -- 'FetchPaper' (v23, paper pipeline v2): Strategist
                            -- requests a cited paper; a Scholar pipeline
                            -- resolves + fetches it (D11).
                            -- 'AttemptDisproof' (v25, feature D): Strategist
                            -- suspects a user-requested claim is FALSE →
                            -- framework mechanically mints the ¬P goal
                            -- (target_id=P, produced_goal_id=¬P). Belief is
                            -- never trusted — settling either way needs the
                            -- kernel.
                            -- 'Delegate' (v35, discussion groups): hand a
                            -- claim to a sub-group. Its own kind rather
                            -- than a third Inject shape because the batch
                            -- closure law is waived PER KIND, its produced
                            -- artifact is a group (not a goal or strategy),
                            -- its verify asks different questions, and it
                            -- alone can end in a return.
                            -- 'ReturnToParent' (v35): a sub-group hands the
                            -- charter back — refuted / amend / exhausted.
                            -- 'CloseGroup' (v35): the reverse direction — a
                            -- parent retires a child whose line its own route
                            -- no longer needs. Not an experiment, so it can
                            -- never be a batch's whole content: retiring work
                            -- is not progress.
                            -- Structurally unavailable to the top group,
                            -- which has no parent to return to; that is the
                            -- wall keeping the difficulty escape hatch away
                            -- from the human channel.
                            -- 'Theorize' (v52, theory_wake_design.md §2):
                            -- hand ONE load-bearing unknown to the theory
                            -- layer. Its own kind for the Delegate reasons
                            -- one level over: its produced artifact is a
                            -- DOCUMENT (`theory_documents`), its verify asks
                            -- different questions (objective / situation,
                            -- one in flight per group), and its executor is
                            -- a pipeline, not a group's seat.
                            CHECK(decision_kind IN
                                  ('Inject','ConfirmShelve','Reopen',
                                   'EmitDirective','InitializeDefs',
                                   'RequestUserAmend','Noop','MarkDeliverable',
                                   'Ingest','FetchPaper','AttemptDisproof',
                                   'Delegate','ReturnToParent',
                                   'CloseGroup','Theorize')),
    -- v35 — which group AUTHORED this decision. Backfilled to the problem's
    -- top group for every pre-v35 row. SET NULL on delete: see the note on
    -- `groups.opened_by` — the two tables reference each other.
    group_id            INTEGER NULL DEFAULT NULL
                            REFERENCES groups(id) ON DELETE SET NULL,
    target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
    brief               TEXT NULL DEFAULT NULL,
    reason              TEXT NULL DEFAULT NULL,
    payload             TEXT NOT NULL DEFAULT '{}',
    -- batch_id: groups the N Inject rows committed in one Strategist
    -- decision (briefs list path; every Inject under unified Phase 2.5
    -- is a batch, N=1 is degenerate). All rows in the same batch share
    -- the UUID; framework fires Strategist with trigger_kind='inject_
    -- batch_done' once every Forward spawned by the batch has reached
    -- a terminal outcome. NULL only for non-Inject decision kinds
    -- (and any legacy / manually-inserted Inject row).
    batch_id            TEXT NULL DEFAULT NULL,
    -- produced_goal_id: Inject decisions that successfully spawn a
    -- Forward lemma store its goal id here. The `outcome` column is
    -- then filled when that goal reaches a terminal status (proved /
    -- shelved / disproved), NOT when the Forward agent finishes
    -- writing — so `inject_batch_done` fires on real-completion
    -- semantics rather than agent-finished semantics. Inject
    -- decisions that fail to produce a lemma (forward_no_new_goal /
    -- agent_declined / etc.) fill `outcome` immediately with NULL
    -- here. Non-Inject decision kinds are always NULL.
    produced_goal_id    INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                            ON DELETE SET NULL,
    -- produced_strategy_id: Inject(Backward/Builder) decisions store
    -- the strategy_id their dispatched worker created here. The
    -- decision's `outcome` is filled when that strategy reaches a
    -- terminal status (succeeded / dead / superseded), mirroring the
    -- `produced_goal_id` mechanism for Forward. Lets `inject_batch_
    -- done` fire for Backward/Builder injects too — previously the
    -- per-kind asymmetry meant Strategist was only woken on Forward
    -- batch completion. ON DELETE SET NULL covers the
    -- placeholder-cleanup case (worker BaseException deletes the
    -- empty strategy row).
    produced_strategy_id INTEGER NULL DEFAULT NULL
                            REFERENCES strategies(id) ON DELETE SET NULL,
    -- produced_group_id (v35): a `Delegate` decision stores the group it
    -- opened here — the THIRD form of produced work, alongside goal and
    -- strategy. The parent's right to stay quiet is read off this column
    -- (`has_active_inflight_inject`): a delegated burden with no anchor
    -- goal has neither of the other two, so without this arm T4 would wake
    -- the parent while its child is still working. The `outcome` fills
    -- when the group reaches a terminal status (delivered / returned /
    -- closed) — the same real-completion semantics the other two use.
    produced_group_id   INTEGER NULL DEFAULT NULL
                            REFERENCES groups(id) ON DELETE SET NULL,
    outcome             TEXT NULL DEFAULT NULL,
    outcome_detail      TEXT NULL DEFAULT NULL,
    -- report_carried_at (2026-09-03): this batch finished mid-debate and
    -- the wake in flight neither received nor acted on it, so its REPORT
    -- has reached no Strategist. The clock ratchet (`last_strategist_at`)
    -- cannot say that — bumped at commit, it swallows every batch older
    -- than itself — so this mark carries the batch past it to the next
    -- wake. Written per batch, cleared on acknowledgement, by
    -- `strategist.batch_ack`; NULL = "the ratchet decides" (legacy rows,
    -- and every batch a wake received normally).
    report_carried_at   TEXT NULL DEFAULT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- Librarian (docs/archive/design/librarian_plan.md) — per-declaration state
-- for turning a proved problem into a mathlib-shaped Library. One row
-- per original Problems declaration. Pure new table (no FK widening on
-- existing tables), so a plain CREATE TABLE IF NOT EXISTS suffices for
-- both fresh and existing DBs — no user_version bump needed.
--
-- Columns fill across the three Librarian work kinds:
--   dedup    → verdict, citation
--   classify → target_file, target_name, file_order
--   migrate  → lifecycle advances to 'migrated'
--   cleanup  → lifecycle advances to 'cleaned'; a P4 rename records the
--              new name in target_name + the ORIGINAL fqn in renamed_from
--              (so consumer files self-apply the rename via deferred-rewire)
-- `lifecycle` is the per-decl state machine (plan §7). Flow:
-- candidate→deduped→classified→migrated→cleaned. Terminal states:
-- 'cleaned' (migrated + PR-ready: unused hyps removed, variables factored,
-- docstrings — Step 4), 'migrated' (kept + reshaped, pre-cleanup),
-- 'dropped' (reinvents mathlib OR merged into a canonical sibling),
-- 'cited' (mathlib/Library already states it; call sites cite).
CREATE TABLE IF NOT EXISTS library_decls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    problem         TEXT NOT NULL REFERENCES problems(name),
    slug            TEXT NOT NULL,
    source_goal_id  INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                        ON DELETE SET NULL,
    verdict         TEXT NULL DEFAULT NULL,
    citation        TEXT NULL DEFAULT NULL,
    target_file     TEXT NULL DEFAULT NULL,
    target_name     TEXT NULL DEFAULT NULL,
    file_order      INTEGER NULL DEFAULT NULL,
    lifecycle       TEXT NOT NULL DEFAULT 'candidate'
                        CHECK(lifecycle IN (
                          'candidate','deduped','classified',
                          'migrated','cleaned','dropped','cited')),
    reopen_note     TEXT NULL DEFAULT NULL,
    renamed_from    TEXT NULL DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(problem, slug)
);

-- librarian_fail_counts — persistent per-unit failure tally for the Librarian
-- chain (#92 cap). The dispatcher keeps an in-memory dict for the hot read path
-- but loads it from here at startup + writes through on every mutation, so a
-- genuinely-stuck unit's count survives a daemon restart and STALLs at the cap
-- instead of looping forever. `target_id` = a `problem` (serial phase step) or
-- `problem\x1ffile` (per-file migrate/cleanup unit). Pure new table → a plain
-- CREATE TABLE IF NOT EXISTS suffices for fresh + existing DBs (no user_version
-- bump; init_schema re-runs SCHEMA each start).
-- theory_documents (v52, theory_wake_design.md §4) — what the theory
-- layer produced, one row per Theorist pipeline that reached a verdict.
-- The Theorist's product is a DOCUMENT, the one artifact the decision
-- log had no table for: a goal has `goals`, a group has `groups`, and a
-- theory document had only a path in a payload nobody could query.
--
-- A REJECTED run keeps its row AND lands its document (owner ruling
-- 2026-09-06): what was tried on that wall and why it failed is the
-- post-mortem material the next `Theorize` there is written against,
-- and a record reachable only through a `dead_attempts` blob is a
-- record nobody reads. `status` is the review's verdict, never a
-- workflow state, and it does NOT decide citability — the reviewer's
-- criterion 2 (Rigour) does, which is why `verdict_json` is kept.
-- `path` is NULL only where no document was ever reviewed (a wake that
-- died mid-flight) or on a refusal filed before that rule.
CREATE TABLE IF NOT EXISTS theory_documents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    problem      TEXT NOT NULL REFERENCES problems(name),
    -- The group whose charter the document was written for. SET NULL on
    -- delete, the `strategist_decisions.group_id` rule: the two tables
    -- reference each other through the decision row.
    group_id     INTEGER NULL DEFAULT NULL
                     REFERENCES groups(id) ON DELETE SET NULL,
    pipeline_id  TEXT NULL DEFAULT NULL,
    decision_id  INTEGER NULL DEFAULT NULL
                     REFERENCES strategist_decisions(id),
    objective    TEXT NOT NULL,
    situation    TEXT NOT NULL,
    -- Workspace-relative, under `Problems/<project>/_docs/agent/`. Set
    -- on both roads; a refused document's NAME carries `_rejected` and
    -- its header opens `status: rejected`.
    path         TEXT NULL DEFAULT NULL,
    status       TEXT NOT NULL CHECK(status IN ('accepted','rejected')),
    -- Author turns spent: 1 = accepted on the cold wake, N = N-1
    -- revisions bought by a fired verdict.
    rounds       INTEGER NOT NULL DEFAULT 0,
    -- The LAST verdict, verbatim JSON. On a rejection it is the ruling
    -- the Strategist is told to re-read its request against.
    verdict_json TEXT NULL DEFAULT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_theory_docs_problem
    ON theory_documents(problem, created_at);

-- routine_verdicts — the routine wake as an AUDIT (owner design
-- 2026-08-30). One row per routine wake: the verdict.json it handed in,
-- its fired findings, and the roots it never ruled on. A fired row
-- with acted_at NULL is the persistent state that seats the action wake
-- (`trigger_kind='routine_fired'`), the way an unacknowledged Inject
-- batch seats a batch-done wake; the action wake's commit stamps
-- acted_at.
CREATE TABLE IF NOT EXISTS routine_verdicts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    problem        TEXT NOT NULL REFERENCES problems(name),
    group_id       INTEGER NOT NULL,
    pipeline_id    TEXT NOT NULL,
    verdict_json   TEXT NOT NULL,
    fired_json     TEXT NOT NULL DEFAULT '[]',
    unaudited_json TEXT NOT NULL DEFAULT '[]',
    fired          INTEGER NOT NULL DEFAULT 0 CHECK(fired IN (0,1)),
    acted_at       TEXT NULL DEFAULT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rv_group_pending
    ON routine_verdicts(group_id, fired, acted_at);

CREATE TABLE IF NOT EXISTS librarian_fail_counts (
    target_id   TEXT PRIMARY KEY,
    n           INTEGER NOT NULL,
    updated_at  TEXT NOT NULL
);

-- kb_entries — Phase 12 informal knowledge base (the LESSON revamp). One row
-- per title+body knowledge entry. Breadth reads off `node_id` alone: NULL =
-- problem-wide / global (type-2, promotable), set = bound to that goal node
-- (type-1, discarded when the node vanishes at promotion). `type` splits
-- confirmed-positive experience ('lesson') from confirmed-negative walls
-- ('antipattern'); unverified guesses are NOT stored (they stay in the
-- prior_partial carry-over). ON DELETE SET NULL keeps a vanished node's entry
-- as problem-wide rather than dropping it. The `scope` column was dropped in
-- Phase 12 (v12 migration) — it was 100% determined by node_id presence and the
-- structural-depth model it encoded was abandoned (lesson retrieval is semantic,
-- not subtree-walk). The type enum lives in `Tooling/state/kb.py`.
CREATE TABLE IF NOT EXISTS kb_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL CHECK(type IN ('lesson','antipattern')),
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    problem     TEXT NULL DEFAULT NULL REFERENCES problems(name),
    node_id     INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                    ON DELETE SET NULL,
    provenance  TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

-- v36 — every goal status transition, append-only, with the forensic
-- label of the event that drove it. `goals.updated_at` cannot serve as
-- an event clock: attempts+1, is_deliverable and integrity_verified all
-- bump it (measured p90 18min, worst 43min away from the real
-- transition), so a timeline built on it reads a goal as moving when
-- nothing moved. Written from `update_goal_status` — the WRITE
-- chokepoint, so both the validating path (`apply_goal_transition`) and
-- the operator-amend escape hatch land here, and any future caller does
-- too without a second wiring decision.
--
-- ON DELETE CASCADE is what keeps `asterism reset` honest: reset drops
-- the problem's goals by id, and the events go with them instead of
-- becoming a cross-run leak (the class #167 records for `.groups/`).
CREATE TABLE IF NOT EXISTS goal_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id     INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    problem     TEXT NOT NULL REFERENCES problems(name),
    -- NULL only when the row vanished under us mid-transition.
    from_status TEXT NULL DEFAULT NULL,
    to_status   TEXT NOT NULL,
    -- Short forensic label for the driving event ('builder_proved',
    -- 'strategist_reopen', 'operator_amend'); '' when the caller had
    -- none to give.
    event       TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT '',
    at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
-- v35 — one top group per problem, pinned in the schema rather than
-- trusted to the code that creates it (CLAUDE.md rule 6): a second
-- parentless row for the same problem would fork the whole tree's notion
-- of "who faces the human", silently.
CREATE UNIQUE INDEX IF NOT EXISTS ux_groups_top ON groups(problem)
    WHERE parent_group_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_groups_problem ON groups(problem);
CREATE INDEX IF NOT EXISTS idx_groups_parent ON groups(parent_group_id);
-- `idx_sd_group` is deliberately NOT here: SCHEMA runs BEFORE the
-- migration chain, and on an existing DB `CREATE TABLE IF NOT EXISTS
-- strategist_decisions` is a no-op — so the column this index needs does
-- not exist yet and the whole script dies. The v35 step creates it,
-- where the column is guaranteed. The three indexes above are safe only
-- because SCHEMA itself creates `groups`.
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC, id ASC);
CREATE INDEX IF NOT EXISTS idx_sd_problem ON strategist_decisions(problem);
CREATE INDEX IF NOT EXISTS idx_sd_outcome ON strategist_decisions(outcome);
CREATE INDEX IF NOT EXISTS idx_libdecls_problem ON library_decls(problem);
-- Hot path: tree.render's `_walk_goal` and db.open_goals both filter
-- strategies by goal_id. Without this index the (10k-row and growing)
-- table is full-scanned once per goal, making the dispatcher's periodic
-- TREE.md refresh O(goals × strategies) — measured 8.6s/tick across 281
-- problems (EXPLAIN showed `SCAN strategies`). idx_dead_attempts_target
-- backs `_strategy_dead_cause`'s per-dead-strategy verify-fault lookup.
CREATE INDEX IF NOT EXISTS idx_strategies_goal_id ON strategies(goal_id);
-- Upward cascade walks (_kill_upward_chain / _maybe_stall_parent_strategies /
-- _has_hard_terminal_ancestor) all filter strategy_subgoals.subgoal_id; the
-- PK is (strategy_id, subgoal_id) so each step was a full link-table scan —
-- the exact latent-O(N) class idx_strategies_goal_id fixed for tree.render
-- (8.6s/tick across 281 problems). Task #10(a).
CREATE INDEX IF NOT EXISTS idx_ssg_subgoal ON strategy_subgoals(subgoal_id);
CREATE INDEX IF NOT EXISTS idx_dead_attempts_target
    ON dead_attempts(target_kind, target_id);
CREATE INDEX IF NOT EXISTS idx_kb_problem ON kb_entries(problem);
CREATE INDEX IF NOT EXISTS idx_kb_node ON kb_entries(node_id);
CREATE INDEX IF NOT EXISTS idx_goal_events_goal ON goal_events(goal_id, at);
CREATE INDEX IF NOT EXISTS idx_goal_events_problem
    ON goal_events(problem, at);
-- idx_sd_batch_id: created after the batch_id ALTER TABLE migration
-- in init_schema, not here. Inlining it in SCHEMA would fail on pre-
-- Phase 2.5 DBs (executescript runs CREATE INDEX before the ALTER
-- TABLE block that adds the column).
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------
# dispatch scope
# ---------------------------------------------------------------------

#: What joins the names of an EXPLICIT-LIST scope. A problem name is
#: dot-separated identifiers (`state/projects.PROBLEM_NAME_RE`), so a
#: comma can never occur in one and the two scope forms cannot collide.
SCOPE_SEP = ","


def scope_names(scope: "str | None") -> "list[str] | None":
    """The exact problem names an explicit-list scope selects, or None
    when the scope is the historical single LIKE pattern.

    A scope has said one thing since the beginning — "restrict dispatch
    to what this SQL LIKE matches" — and a pattern cannot say "these
    three". `/api/daemon/start-many` (human_interface_design.md §1.4,
    §3.3) must take an explicit list and no patterns, so the scope
    language grows the one form it was missing: `a,b,c` = exactly those.
    """
    if scope is None or SCOPE_SEP not in scope:
        return None
    return [s for s in (part.strip() for part in scope.split(SCOPE_SEP)) if s]


def scope_sql(scope: "str | None",
              column: str = "problem") -> "tuple[str, tuple]":
    """(predicate, params) for a dispatch scope — `('', ())` when the
    scope is None (workspace-wide).

    The ONE translation from a scope to SQL. Every filter used to write
    `<col> LIKE ?` by hand, which is exactly why a second scope FORM
    could not be added without a hole: whichever site was missed would
    quietly run out-of-scope problems, the accident `/api/daemon/start`
    exists to prevent. `column` is a caller-supplied SQL identifier, not
    user input; the values always travel as parameters.
    """
    if scope is None:
        return "", ()
    names = scope_names(scope)
    if names is None:
        return f"{column} LIKE ?", (scope,)
    if not names:
        # `,` alone names nothing; match nothing rather than everything.
        return "0", ()
    marks = ",".join("?" for _ in names)
    return f"{column} IN ({marks})", tuple(names)


def scope_matches(conn: sqlite3.Connection, scope: "str | None",
                  name: str) -> bool:
    """Python-side mirror of `scope_sql` for the row-at-a-time readers.
    Patterns go through SQLite so LIKE semantics stay SQLite's."""
    if not scope:
        return True
    names = scope_names(scope)
    if names is not None:
        return name in names
    row = conn.execute("SELECT ? LIKE ?", (name, scope)).fetchone()
    return bool(row and row[0])


# The schema version the current code expects. Every `init_schema` migration
# phase bumps PRAGMA user_version up to this; `connect` uses it to detect a
# stale on-disk DB. Keep in lockstep with the final `PRAGMA user_version = N`
# in init_schema (an invariant test asserts they match).
_CURRENT_USER_VERSION = 52


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    # Lift busy-timeout from sqlite3's 5s default to 30s.
    # With pool=12 workers each holding their own conn and issuing
    # short bursts of UPDATEs / INSERTs through cascade_one, the 5s
    # ceiling is uncomfortably close to real bursts; 30s absorbs
    # transient WAL writer contention without ever surfacing as
    # OperationalError to callers (who don't retry).
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL: readers don't block writers; reduces contention with 12
    # workers concurrently INSERTing into pipelines + dead_attempts.
    conn.execute("PRAGMA journal_mode = WAL")
    # Auto-migrate a STALE but POPULATED on-disk DB so no caller silently
    # operates on an old schema (the v6→v9 incident: a standalone driver used
    # `connect` without `init_schema` and crashed on the missing reopen_note
    # column). Only act when the DB already has tables AND its user_version is
    # behind — a FRESH DB (no `goals` table, e.g. a `:memory:` test fixture)
    # is left untouched for the caller's explicit `init_schema`, and a current
    # DB pays only one PRAGMA read. init_schema is idempotent; the daemon's own
    # startup init_schema then becomes a no-op.
    ver = conn.execute("PRAGMA user_version").fetchone()[0]
    if ver < _CURRENT_USER_VERSION and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone():
        print(f"[db] auto-migrating stale schema {ver} -> "
              f"{_CURRENT_USER_VERSION} at {path}", flush=True)
        init_schema(conn)
    return conn


def set_review_snapshot(conn: sqlite3.Connection, problem: str,
                        snapshot_json: str) -> None:
    """Store the problem's anchor+claim review snapshot (charter §5-4;
    written at Ingest commit while the gateway is warm, refreshed by an
    explicit recompute)."""
    conn.execute(
        "UPDATE problems SET review_snapshot = ?, review_snapshot_at = ?"
        " WHERE name = ?",
        (snapshot_json, now(), problem))
    conn.commit()


def get_review_snapshot(conn: sqlite3.Connection,
                        problem: str) -> "tuple[str, str] | None":
    """(snapshot_json, stored_at) or None when never stored."""
    row = conn.execute(
        "SELECT review_snapshot, review_snapshot_at FROM problems"
        " WHERE name = ?", (problem,)).fetchone()
    if row is None or row["review_snapshot"] is None:
        return None
    return str(row["review_snapshot"]), str(row["review_snapshot_at"] or "")


def set_ingest_signoff(conn: sqlite3.Connection, problem: str,
                       record: "dict | None") -> None:
    """Write (or revoke, with None) the sign-off signature record —
    {name, at, snapshot_sha, evidence} as JSON. Written at approve;
    cleared by reject-ingest and un-harvest (a revoked judgment must
    not keep wearing its seal)."""
    import json as _json
    conn.execute(
        "UPDATE problems SET ingest_signoff = ? WHERE name = ?",
        (None if record is None else _json.dumps(record), problem))
    conn.commit()


def get_ingest_signoff(conn: sqlite3.Connection,
                       problem: str) -> "dict | None":
    """The sign-off signature record, or None (never signed / revoked /
    predates v27)."""
    import json as _json
    row = conn.execute(
        "SELECT ingest_signoff FROM problems WHERE name = ?",
        (problem,)).fetchone()
    if row is None or row["ingest_signoff"] is None:
        return None
    try:
        rec = _json.loads(row["ingest_signoff"])
        return rec if isinstance(rec, dict) else None
    except ValueError:
        return None


class SchemaBehind(RuntimeError):
    """The on-disk DB's user_version trails _CURRENT_USER_VERSION and the
    caller is read-only (must not migrate). Carries both versions so the
    surface can say 'run the daemon/CLI once to upgrade' precisely."""

    def __init__(self, found: int, expected: int) -> None:
        super().__init__(
            f"DB schema v{found} is behind v{expected}; a read-only "
            f"consumer must not migrate — run the daemon or any asterism "
            f"CLI command once to upgrade")
        self.found = found
        self.expected = expected


def connect_readonly(path: Path = DB_PATH) -> sqlite3.Connection:
    """TRUE read-only connection (frontend charter §5-5, the web layer's
    only legal DB entry). `connect()` auto-migrates a stale DB — a WRITE,
    which a 'read-only' web layer must never perform (it would silently
    upgrade the schema under a running daemon's feet). SQLite URI
    `mode=ro` makes writes impossible at the engine level; a behind
    schema raises SchemaBehind instead of upgrading."""
    uri = f"file:{Path(path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    ver = conn.execute("PRAGMA user_version").fetchone()[0]
    if ver < _CURRENT_USER_VERSION:
        conn.close()
        raise SchemaBehind(ver, _CURRENT_USER_VERSION)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # Additive migrations + user_version stepping live in db_migrations
    # (split 2026-07-07 at the v24 schema rework — the file-size
    # ratchet's documented natural cut; lazy import keeps load acyclic).
    from .. import db_migrations
    db_migrations.apply(conn)


