"""DB schema + connection. Single source of truth.

Tables (see docs/architecture.md §4):
  problems, goals, strategies, strategy_subgoals,
  pipelines, dead_attempts, queue, strategist_decisions (Phase 2)

Schema version tracked via `PRAGMA user_version`:
  0 = pre-Phase 2 (everything before strategist_decisions)
  2 = Phase 2 (new tables/columns/CHECK extensions; see docs/phase2/)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path("asterism.db")


# ---------------------------------------------------------------------
# Problem name ↔ filesystem path mapping
# ---------------------------------------------------------------------
#
# A problem's "name" (= the `problem` column / Manifest frontmatter
# `problem:` field) is a dot-separated slug whose components map 1:1
# to filesystem directory components under `Problems/`.
#
# Top-level problem (legacy / hand-authored):
#   slug:        "sylvester_gallai"
#   on disk:     Problems/sylvester_gallai/
#   Lean ns:     Problems.sylvester_gallai
#
# Nested problem (benchmark imports, multi-category collections):
#   slug:        "Minif2f.mathd_algebra_10"
#   on disk:     Problems/Minif2f/mathd_algebra_10/
#   Lean ns:     Problems.Minif2f.mathd_algebra_10
#
# The `.` separator is a deliberate choice — Lean namespace syntax
# uses `.` natively, so `f"Problems.{problem}.Root"`-style string
# concatenation in module path / namespace generation needs ZERO
# changes for nested support. Only filesystem accesses need to
# convert dots to path separators via `problem_dir()`.

def problem_dir(workspace: Path, problem: str) -> Path:
    """Map a problem slug to its filesystem directory.

    `problem` is the dot-separated slug as stored in the `problems` /
    `goals` `problem` columns. For legacy single-component slugs
    (`"sylvester_gallai"`) this returns `workspace/Problems/sylvester_gallai/`.
    For nested slugs (`"Minif2f.algebra_1"`) it returns
    `workspace/Problems/Minif2f/algebra_1/`.
    """
    return workspace / "Problems" / Path(*problem.split("."))


def slug_from_problem_dir(workspace: Path, pdir: Path) -> str:
    """Inverse of `problem_dir`. Given a problem's filesystem
    directory, return the dot-separated slug. Raises ValueError if
    `pdir` is not under `workspace/Problems/`.
    """
    rel = pdir.resolve().relative_to((workspace / "Problems").resolve())
    if not rel.parts:
        raise ValueError(f"{pdir} resolves to Problems/ root, not a problem dir")
    return ".".join(rel.parts)


SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    name           TEXT PRIMARY KEY,
    manifest_path  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    -- Phase 2 — Strategist first-launch tracking.
    -- `bootstrap_done=0` → T0 trigger fires on next dispatcher tick.
    -- Set to 1 by Strategist's first commit (InitializeDefs / EmitDirective /
    -- Noop) so subsequent ticks fall through to T1 (wall-clock routine).
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
    last_routine_at TEXT NULL DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem     TEXT    NOT NULL REFERENCES problems(name),
    slug        TEXT    NOT NULL,
    lean_path   TEXT    NOT NULL UNIQUE,
    statement   TEXT    NOT NULL,
    -- kind / origin enums kept minimal; extend when implementing
    -- generalizer / refuter / construction (architecture.md §12).
    -- Phase 2 added 'forward' to origin (Forward pipeline-produced lemmas).
    kind        TEXT    NOT NULL DEFAULT 'theorem'
                    -- Phase 4 — non-theorem kinds bypass the prove
                    -- loop: Forward writes them, framework type-checks
                    -- once, status='proved' immediately, BFS never
                    -- dispatches Backward / Builder on them. See
                    -- `NON_THEOREM_KINDS` in dispatcher.py for the
                    -- single source of truth on which kinds skip
                    -- dispatch / axiom probe / Library promotion gate.
                    CHECK(kind IN ('theorem','def','structure','class')),
    origin      TEXT    NOT NULL
                    CHECK(origin IN ('root','backward','forward')),
    -- Phase 2 status additions:
    --   'pending_strategist_review' (transitional) — agent declined with
    --     `shelve` directive; Strategist judges (ConfirmShelve/Reopen/Inject).
    --   'disproved' (terminal hard) — agent declined with `unprovable`;
    --     dedupe blocks same-shape proposals.
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
    -- Split rule (Phase 6 update):
    --   failure_reason='agent_infeasible' → 'disproved' (counterexample;
    --     dedupe blocks same-shape proposals).
    --   failure_reason='agent_shelved' → 'pending_strategist_review'
    --     (transitional; Strategist judges).
    --   failure_reason='parent_needs_fix' → 'dead' (parent strategy
    --     was wrong, goal moot under that context; kills upward
    --     strategies so parent retries with new decomposition).
    -- Terminal soft/hard semantics:
    --   'shelved' — soft terminal; Strategist may Reopen, dedupe DOES
    --     NOT block, upward strategies stay 'proposed' (wait for Reopen).
    --   'disproved' — hard terminal; never Reopen, dedupe BLOCKS, kills
    --     upward strategies.
    --   'dead' — hard terminal in this strategy context; never Reopen,
    --     dedupe DOES NOT block (same statement may be valid under a
    --     different parent strategy), kills upward strategies so parent
    --     goal retries.
    status      TEXT    NOT NULL
                    CHECK(status IN ('open','attempting','proved','shelved',
                                     'pending_strategist_review','disproved',
                                     'frozen','dead')),
    depth       INTEGER NOT NULL DEFAULT 0,
    attempts    INTEGER NOT NULL DEFAULT 0,
    -- Routing directive: which worker dispatches on the first attempt.
    -- 'Builder' = tactic_try + one-shot LLM patch; 'Backward' = skip
    -- Builder, decompose immediately. Set at goal creation:
    --   - cli init: from Manifest's `## Entry kind` section.
    --   - Backward agent: per sub-goal, via `-- entry_kind:` annotation
    --     in `new_<slug>.lean`.
    -- next_worker_kind honors this while attempts < BUILDER_THRESHOLD;
    -- once the threshold is reached escalation to Backward is forced
    -- regardless (safety net for an entry_kind=Builder directive that
    -- turns out wrong).
    entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                    CHECK(entry_kind IN ('Builder','Backward')),
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

CREATE TABLE IF NOT EXISTS strategy_subgoals (
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    subgoal_id  INTEGER NOT NULL REFERENCES goals(id),
    position    INTEGER NOT NULL,
    PRIMARY KEY (strategy_id, subgoal_id)
);

-- pipelines: only finished rows. No 'running' status.
-- Live state ('this daemon has a worker on target X') is in-memory only.
-- → daemon crash leaves no zombie rows; restart sees clean DB.
-- Phase 2 — `kind` adds 'Strategist' / 'Forward'; `target_kind` adds 'Problem'.
-- Forward target_id = problem_name (TEXT NOT NULL preserved; see
-- migration_plan §C option 1). Strategist target = problem.root.id (Goal).
CREATE TABLE IF NOT EXISTS pipelines (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL
                    CHECK(kind IN ('Builder','Backward','Verify',
                                   'Strategist','Forward','Librarian')),
    target_id   TEXT NOT NULL,
    target_kind TEXT NOT NULL
                    CHECK(target_kind IN ('Goal','Strategy','Problem')),
    status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
    outcome     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT NOT NULL
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
-- spawned pipeline via Context.md `## Strategist brief`).
CREATE TABLE IF NOT EXISTS queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL
                    CHECK(kind IN ('Builder','Backward','Verify',
                                   'Strategist','Forward','Librarian')),
    target_id   TEXT NOT NULL,
    target_kind TEXT NOT NULL DEFAULT 'Goal'
                    CHECK(target_kind IN ('Goal','Strategy','Problem')),
    priority    INTEGER NOT NULL DEFAULT 0,
    decision_id INTEGER NULL DEFAULT NULL REFERENCES strategist_decisions(id),
    created_at  TEXT NOT NULL
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
                            CHECK(trigger_kind IN
                                  ('first_launch','pending_review','routine',
                                   'inject_batch_done')),
    decision_kind       TEXT NOT NULL
                            CHECK(decision_kind IN
                                  ('Inject','ConfirmShelve','Reopen',
                                   'EmitDirective','InitializeDefs',
                                   'RequestUserAmend','Noop')),
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
    outcome             TEXT NULL DEFAULT NULL,
    outcome_detail      TEXT NULL DEFAULT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- Librarian (docs/internal/librarian_plan.md) — per-declaration state
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
CREATE TABLE IF NOT EXISTS librarian_fail_counts (
    target_id   TEXT PRIMARY KEY,
    n           INTEGER NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
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
CREATE INDEX IF NOT EXISTS idx_dead_attempts_target
    ON dead_attempts(target_kind, target_id);
-- idx_sd_batch_id: created after the batch_id ALTER TABLE migration
-- in init_schema, not here. Inlining it in SCHEMA would fail on pre-
-- Phase 2.5 DBs (executescript runs CREATE INDEX before the ALTER
-- TABLE block that adds the column).
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# The schema version the current code expects. Every `init_schema` migration
# phase bumps PRAGMA user_version up to this; `connect` uses it to detect a
# stale on-disk DB. Keep in lockstep with the final `PRAGMA user_version = N`
# in init_schema (an invariant test asserts they match).
_CURRENT_USER_VERSION = 11


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


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # Additive migrations for older DBs (CREATE TABLE IF NOT EXISTS is
    # a no-op when the table already exists, so blind ALTER TABLE is
    # needed to backfill columns added in later versions). Idempotent
    # via "duplicate column name" detection.
    for col, ddl in (
        # Routine-only Strategist clock (T1 fires on its own cadence; see the
        # SCHEMA comment on problems.last_routine_at). Additive nullable
        # column — no user_version bump needed (same pattern as bootstrap_done
        # / strategist_directive).
        ("last_routine_at",
         "ALTER TABLE problems ADD COLUMN last_routine_at TEXT NULL"
         " DEFAULT NULL"),
        ("alias_target_id",
         "ALTER TABLE goals ADD COLUMN alias_target_id INTEGER NULL"
         " DEFAULT NULL REFERENCES goals(id)"),
        # Migration entry for older DBs created before entry_kind landed.
        # The CREATE TABLE above already declares this column with a
        # CHECK constraint; this ALTER picks up disk DBs created prior
        # and adds the column with the same NOT NULL default. SQLite
        # ALTER TABLE can't add CHECK after the fact; the CHECK is only
        # enforced for new DBs, but `insert_goal` is the only writer of
        # this column and it always passes a validated value.
        ("entry_kind",
         "ALTER TABLE goals ADD COLUMN entry_kind TEXT NOT NULL"
         " DEFAULT 'Builder'"),
        # See SCHEMA comment on `goals.integrity_verified` for rationale.
        # New rows default to 0; backfill below promotes pre-migration
        # proved roots to 1.
        ("integrity_verified",
         "ALTER TABLE goals ADD COLUMN integrity_verified INTEGER NOT NULL"
         " DEFAULT 0"),
        # Phase 2 — problems columns. Pure ADD COLUMN (no CHECK extension
        # on existing columns); idempotent. See `docs/phase2/pipelines.md`
        # §4.1 for semantics.
        ("bootstrap_done",
         "ALTER TABLE problems ADD COLUMN bootstrap_done INTEGER NOT NULL"
         " DEFAULT 0 CHECK(bootstrap_done IN (0,1))"),
        ("strategist_directive",
         "ALTER TABLE problems ADD COLUMN strategist_directive TEXT"
         " NULL DEFAULT NULL"),
        ("last_strategist_at",
         "ALTER TABLE problems ADD COLUMN last_strategist_at TEXT"
         " NULL DEFAULT NULL"),
        # Phase 2.5 — Strategist multi-Inject batch grouping. Same UUID
        # across all Inject rows committed in one briefs-list decision
        # (every Inject is a batch under the unified schema; N=1 is
        # degenerate). Cascade fires Strategist with
        # trigger_kind='inject_batch_done' when the last Forward in
        # the batch finishes. Pure ADD COLUMN (no CHECK on this column);
        # the CHECK widening for trigger_kind happens via
        # _migrate_to_phase3 below.
        ("batch_id",
         "ALTER TABLE strategist_decisions ADD COLUMN batch_id TEXT"
         " NULL DEFAULT NULL"),
        # Phase 2.5 evolution — Inject decision's "completion" was
        # originally filled when the Forward agent finished writing
        # (sorry-bearing or otherwise). That caused inject_batch_done
        # to fire while produced lemmas were still `:= by sorry`,
        # leading Strategist to Reopen parent goals whose new deps
        # were unproven and Backward to leaf-bypass-cite them →
        # sorryAx rollback (observed residue_thm 2026-05-19, goals
        # 1741 / 1768 / 1759 / 1753). The fix shifts "completion" to
        # "produced lemma reached a terminal status (proved /
        # shelved / disproved)" — the Inject decision tracks the
        # goal it produced via `produced_goal_id` and its `outcome`
        # is filled when that goal terminates, not when the agent
        # finishes. Pure ADD COLUMN, no CHECK to widen.
        ("produced_goal_id",
         "ALTER TABLE strategist_decisions ADD COLUMN produced_goal_id"
         " INTEGER NULL DEFAULT NULL"
         " REFERENCES goals(id) ON DELETE SET NULL"),
        # Inject(Backward/Builder) outcome-tracking — see the column
        # comment in SCHEMA above. Closes the Strategist wake-up
        # asymmetry where only Forward batches fired `inject_batch_
        # done`.
        ("produced_strategy_id",
         "ALTER TABLE strategist_decisions ADD COLUMN produced_strategy_id"
         " INTEGER NULL DEFAULT NULL"
         " REFERENCES strategies(id) ON DELETE SET NULL"),
        # #4 — rich terminal-decline reasoning (Forward `## Why` etc.) so
        # the Strategist sees WHY its brief was declined, not just the
        # coarse `outcome` enum. Additive nullable — no user_version bump.
        ("outcome_detail",
         "ALTER TABLE strategist_decisions ADD COLUMN outcome_detail TEXT"
         " NULL DEFAULT NULL"),
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    # Phase 2.5 — index on the freshly-added batch_id column. Lives
    # here (post-ALTER) rather than in SCHEMA because executescript
    # runs CREATE INDEX in declaration order, before the additive
    # ALTER block above ever runs — on pre-Phase 2.5 DBs that would
    # fail with "no such column: batch_id".
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sd_batch_id"
        " ON strategist_decisions(batch_id)"
    )
    # Backfill: mark every already-proved root as verified. Prior to
    # this column existing, `library.maybe_promote` (later
    # `verify.root_integrity_gate`) ran an axiom_probe on every proved
    # root every dispatcher tick — so any row currently sitting at
    # status='proved' has been kernel-axiom-validated under whatever
    # gate code was active at the time, just without a persistent
    # marker. The backfill turns that implicit history into explicit
    # DB state so the first post-migration dispatcher tick doesn't
    # re-pay ~30s × N proved roots (244 miniF2F + N stalls dispatch
    # ~110min on a benchmark-loaded workspace). Only meaningful on
    # the migration tick — on a fresh DB built from SCHEMA there are
    # no proved rows yet, so this is a no-op.
    conn.execute(
        "UPDATE goals SET integrity_verified = 1"
        " WHERE origin = 'root' AND status = 'proved'"
        "   AND integrity_verified = 0"
    )
    # Phase 7-D — drop the former cross-pipeline session_id columns.
    # The in-pipeline retry helper (Tooling/pipeline/_retry.py) keeps
    # sid as a local var for the pipeline's lifetime; the columns are
    # vestigial. Idempotent: a fresh DB built from the current SCHEMA
    # never had them, so DROP COLUMN raises "no such column" and we
    # swallow. Requires SQLite >= 3.35.0 (Python 3.12 ships ≥ 3.40).
    for col in ("builder_session_id", "backward_session_id"):
        try:
            conn.execute(f"ALTER TABLE goals DROP COLUMN {col}")
        except sqlite3.OperationalError as e:
            if "no such column" not in str(e).lower():
                raise
    conn.commit()

    # Phase 2 migration — CHECK-extension table-rebuild for
    # goals/pipelines/queue (SQLite cannot ALTER existing CHECK). Gated
    # by `PRAGMA user_version < 2`; fresh DBs (built directly from the
    # updated SCHEMA) skip the rebuild via the `'detached' in goals_cols`
    # detection. Idempotent.
    v = conn.execute("PRAGMA user_version").fetchone()[0]
    if v < 2:
        goals_cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
        if 'detached' not in goals_cols:
            _migrate_to_phase2(conn)
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
    if v < 3:
        # Phase 2.5 — strategist_decisions.trigger_kind CHECK adds
        # 'inject_batch_done'. SQLite cannot extend CHECK in place;
        # rebuild required. Fresh DBs built from the updated SCHEMA
        # already have the widened CHECK + idx_sd_batch_id; the rebuild
        # short-circuits via the duplicate-index probe inside.
        _migrate_to_phase3(conn)
        conn.execute("PRAGMA user_version = 3")
        conn.commit()
    if v < 4:
        # Phase 4 — goals.kind CHECK widens to accept 'def', 'structure',
        # 'class' (non-theorem toolkit kinds Forward can produce). Same
        # rebuild pattern as phase 3; idempotent via the in-DDL probe.
        _migrate_to_phase4(conn)
        conn.execute("PRAGMA user_version = 4")
        conn.commit()
    if v < 5:
        # Phase 5 — goals.status CHECK widens to accept 'frozen' (root
        # pre-launch state). Same rebuild pattern. Backfill: roots in
        # problems with bootstrap_done=0 flip to 'frozen' (matches the
        # legacy gate semantic — those roots were waiting for first_launch
        # anyway).
        _migrate_to_phase5(conn)
        conn.execute("PRAGMA user_version = 5")
        conn.commit()
    if v < 6:
        # Phase 6 — goals.status CHECK widens to accept 'dead' (terminal
        # for parent_needs_fix decline). Hard terminal like disproved
        # but doesn't block dedupe (same statement may be valid under a
        # different parent strategy). Same rebuild pattern as phase 5.
        # No backfill: pre-Phase-6 rows used 'shelved' for the
        # parent_needs_fix case; leaving them as 'shelved' is safe (just
        # means they're reopenable, which is harmless for already-completed
        # runs).
        _migrate_to_phase6(conn)
        conn.execute("PRAGMA user_version = 6")
        conn.commit()
    if v < 7:
        # Phase 7 — pipelines.kind + queue.kind CHECK widen to accept
        # 'Librarian' (the Library-ization pipeline). Same rebuild
        # pattern as earlier phases; idempotent via in-DDL CHECK probe.
        # No backfill: no pre-Phase-7 rows ever had kind='Librarian'.
        _migrate_to_phase7(conn)
        conn.execute("PRAGMA user_version = 7")
        conn.commit()
    if v < 8:
        # Phase 8 — library_decls.lifecycle CHECK widens to accept 'cleaned'
        # (Step 4 PR-ready state, after 'migrated'). Same rebuild pattern;
        # idempotent via the in-DDL CHECK probe. No backfill: pre-Phase-8
        # rows never had 'cleaned'.
        _migrate_to_phase8(conn)
        conn.execute("PRAGMA user_version = 8")
        conn.commit()
    if v < 9:
        # Phase 9 — library_decls gains `reopen_note` (the constraint a
        # downstream `needs-upstream` decline passes to a re-opened upstream's
        # re-cleanup). Plain ADD COLUMN (nullable) — no table rebuild. Guarded
        # so a fresh DB built from the updated SCHEMA (column already present)
        # doesn't double-add.
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(library_decls)")}
        if "reopen_note" not in cols:
            conn.execute(
                "ALTER TABLE library_decls ADD COLUMN reopen_note TEXT")
        conn.execute("PRAGMA user_version = 9")
        conn.commit()
    if v < 10:
        # Phase 10 — library_decls gains `renamed_from` (the ORIGINAL fqn of a
        # P4-renamed kept decl; target_name holds the new fqn). Consumer files
        # read {renamed_from → target_name} as deferred-rewire renames. Plain
        # ADD COLUMN (nullable) — no table rebuild. Guarded so a fresh DB built
        # from the updated SCHEMA (column already present) doesn't double-add.
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(library_decls)")}
        if "renamed_from" not in cols:
            conn.execute(
                "ALTER TABLE library_decls ADD COLUMN renamed_from TEXT")
        conn.execute("PRAGMA user_version = 10")
        conn.commit()
    if v < 11:
        # Phase 11 — widen `strategies.status` CHECK to accept 'stalled'
        # (a parked-but-reopenable strategy whose subgoals all settled with
        # >=1 soft-shelved). Same rebuild pattern as phase 5/7/8. No
        # backfill: pre-Phase-11 rows in this state lingered as 'proposed';
        # the reconcile backstop migrates them to 'stalled' at runtime.
        _migrate_to_phase11(conn)
        conn.execute("PRAGMA user_version = 11")
        conn.commit()


def _migrate_to_phase11(conn: sqlite3.Connection) -> None:
    """Phase 11 — widen `strategies.status` CHECK to accept 'stalled'.
    SQLite cannot ALTER a CHECK; rebuild the table with the new clause,
    copy rows, swap. Idempotent: skips when the CHECK is already wide.

    Pre-condition: PRAGMA user_version < 11.
    Post-condition (caller sets user_version = 11):
      - strategies.status CHECK accepts 'stalled'
      - All existing rows preserved unchanged
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='strategies'"
    ).fetchone()
    # Table absent (fresh DB) → init_schema's CREATE already built the wide
    # CHECK; nothing to rebuild. Wide already → skip.
    if not chk or "'stalled'" in (chk["sql"] or ""):
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_strategies (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id      INTEGER NOT NULL REFERENCES goals(id),
                lean_path    TEXT    NOT NULL,
                scratch_path TEXT    NOT NULL DEFAULT '',
                status       TEXT    NOT NULL
                                 CHECK(status IN ('proposed','succeeded',
                                                  'dead','superseded',
                                                  'stalled')),
                proposal_md  TEXT    NOT NULL DEFAULT '',
                created_by   TEXT    NOT NULL,
                created_at   TEXT NOT NULL
            );
            INSERT INTO _new_strategies SELECT * FROM strategies;
            DROP TABLE strategies;
            ALTER TABLE _new_strategies RENAME TO strategies;
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 11 migration left FK violations: {fk_violations[:5]}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase8(conn: sqlite3.Connection) -> None:
    """Phase 8 — widen `library_decls.lifecycle` CHECK to accept 'cleaned'.
    SQLite cannot ALTER a CHECK; rebuild the table with the new clause, copy
    rows, swap. Idempotent: skips when the CHECK is already wide.

    Pre-condition: PRAGMA user_version < 8.
    Post-condition (caller sets user_version = 8):
      - library_decls.lifecycle CHECK accepts 'cleaned'
      - All existing rows preserved unchanged
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='library_decls'"
    ).fetchone()
    # Table absent (pre-Librarian DB) → init_schema's CREATE already built the
    # wide CHECK; nothing to rebuild. Wide already → skip.
    if not chk or "'cleaned'" in (chk["sql"] or ""):
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_library_decls (
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
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_library_decls SELECT * FROM library_decls;
            DROP TABLE library_decls;
            ALTER TABLE _new_library_decls RENAME TO library_decls;
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 8 migration left FK violations: {fk_violations[:5]}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase7(conn: sqlite3.Connection) -> None:
    """Phase 7 — widen `pipelines.kind` and `queue.kind` CHECK to accept
    'Librarian'. SQLite cannot ALTER a CHECK constraint; rebuild each
    table with the new CHECK clause, copy rows, swap.

    Pre-condition: PRAGMA user_version < 7.

    Post-condition (caller sets user_version = 7):
      - pipelines.kind CHECK accepts 'Librarian'
      - queue.kind CHECK accepts 'Librarian'
      - All existing rows preserved unchanged
    """
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # --- pipelines rebuild (skip if CHECK already wide) ---
        chk = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
            " AND name='pipelines'"
        ).fetchone()
        if not (chk and "'Librarian'" in (chk["sql"] or "")):
            conn.executescript("""
                CREATE TABLE _new_pipelines (
                    id          TEXT PRIMARY KEY,
                    kind        TEXT NOT NULL
                                    CHECK(kind IN ('Builder','Backward','Verify',
                                                   'Strategist','Forward',
                                                   'Librarian')),
                    target_id   TEXT NOT NULL,
                    target_kind TEXT NOT NULL
                                    CHECK(target_kind IN ('Goal','Strategy','Problem')),
                    status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
                    outcome     TEXT NOT NULL,
                    started_at  TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                );
                INSERT INTO _new_pipelines SELECT * FROM pipelines;
                DROP TABLE pipelines;
                ALTER TABLE _new_pipelines RENAME TO pipelines;
                CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
            """)

        # --- queue rebuild (skip if CHECK already wide) ---
        chk = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
            " AND name='queue'"
        ).fetchone()
        if not (chk and "'Librarian'" in (chk["sql"] or "")):
            conn.executescript("""
                CREATE TABLE _new_queue (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind        TEXT NOT NULL
                                    CHECK(kind IN ('Builder','Backward','Verify',
                                                   'Strategist','Forward',
                                                   'Librarian')),
                    target_id   TEXT NOT NULL,
                    target_kind TEXT NOT NULL DEFAULT 'Goal'
                                    CHECK(target_kind IN ('Goal','Strategy','Problem')),
                    priority    INTEGER NOT NULL DEFAULT 0,
                    decision_id INTEGER NULL DEFAULT NULL REFERENCES strategist_decisions(id),
                    created_at  TEXT NOT NULL
                );
                INSERT INTO _new_queue (id, kind, target_id, target_kind,
                    priority, decision_id, created_at)
                SELECT id, kind, target_id, target_kind,
                    priority, decision_id, created_at FROM queue;
                DROP TABLE queue;
                ALTER TABLE _new_queue RENAME TO queue;
                CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC, id ASC);
            """)

        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 7 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase2(conn: sqlite3.Connection) -> None:
    """Phase 2 schema migration for pre-Phase 2 DBs.

    Rebuilds goals / pipelines / queue to widen CHECK constraints and
    add new columns. Backfills existing `shelved` rows into `disproved`
    based on dead_attempts.failure_reason = 'agent_infeasible'.

    Pre-condition: PRAGMA user_version < 2 AND goals table lacks the
    Phase 2 `detached` column (i.e. genuinely pre-Phase 2 schema).

    Post-condition (caller sets PRAGMA user_version = 2):
      - goals.origin CHECK accepts 'forward'
      - goals.status CHECK accepts 'pending_strategist_review', 'disproved'
      - goals has new `detached` column (default 0)
      - pipelines.kind CHECK accepts 'Strategist', 'Forward'
      - pipelines.target_kind CHECK accepts 'Problem'
      - queue.kind CHECK accepts 'Strategist', 'Forward'
      - queue has new `target_kind` column (default 'Goal') + `decision_id`
        column (NULL FK)

    Failure recovery: SQLite executescript implicit-commits between
    statements, so a mid-rebuild failure leaves the DB in an
    inconsistent state. Operator should `cp asterism.db
    asterism.db.pre_phase2_<UTC>` before first daemon start under
    Phase 2 code (per `docs/internal/archive/phase2_migration_plan.md §E`).
    """
    # PRAGMA foreign_keys cannot be set inside a transaction.
    # connect() leaves us at autocommit (isolation_level default).
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # --- goals rebuild: extend origin/status CHECK + add detached ---
        # INSERT SELECT lists columns explicitly (new `detached` not in
        # source); it gets the DEFAULT 0 from _new_goals schema.
        conn.executescript("""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ('theorem')),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_goals (id, problem, slug, lean_path, statement,
                kind, origin, status, depth, attempts, entry_kind,
                integrity_verified, alias_target_id, created_at, updated_at)
            SELECT id, problem, slug, lean_path, statement,
                kind, origin, status, depth, attempts, entry_kind,
                integrity_verified, alias_target_id, created_at, updated_at
            FROM goals;
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)

        # Backfill: existing 'shelved' rows whose latest decline gave a
        # counterexample (failure_reason='agent_infeasible') represent
        # the new 'disproved' semantic. Must run AFTER goals rebuild so
        # the new CHECK accepts 'disproved'. dead_attempts is intact
        # (no rebuild on it).
        conn.execute("""
            UPDATE goals SET status = 'disproved'
            WHERE status = 'shelved'
              AND id IN (
                SELECT DISTINCT target_id FROM dead_attempts
                WHERE target_kind = 'Goal'
                  AND failure_reason = 'agent_infeasible'
              )
        """)

        # --- pipelines rebuild: extend kind + target_kind CHECK ---
        conn.executescript("""
            CREATE TABLE _new_pipelines (
                id          TEXT PRIMARY KEY,
                kind        TEXT NOT NULL
                                CHECK(kind IN ('Builder','Backward','Verify',
                                               'Strategist','Forward')),
                target_id   TEXT NOT NULL,
                target_kind TEXT NOT NULL
                                CHECK(target_kind IN ('Goal','Strategy','Problem')),
                status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
                outcome     TEXT NOT NULL,
                started_at  TEXT NOT NULL,
                finished_at TEXT NOT NULL
            );
            INSERT INTO _new_pipelines SELECT * FROM pipelines;
            DROP TABLE pipelines;
            ALTER TABLE _new_pipelines RENAME TO pipelines;
            CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
        """)

        # --- queue rebuild: extend kind CHECK + add target_kind, decision_id ---
        conn.executescript("""
            CREATE TABLE _new_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                kind        TEXT NOT NULL
                                CHECK(kind IN ('Builder','Backward','Verify',
                                               'Strategist','Forward')),
                target_id   TEXT NOT NULL,
                target_kind TEXT NOT NULL DEFAULT 'Goal'
                                CHECK(target_kind IN ('Goal','Strategy','Problem')),
                priority    INTEGER NOT NULL DEFAULT 0,
                decision_id INTEGER NULL DEFAULT NULL REFERENCES strategist_decisions(id),
                created_at  TEXT NOT NULL
            );
            INSERT INTO _new_queue (id, kind, target_id, priority, created_at)
            SELECT id, kind, target_id, priority, created_at FROM queue;
            DROP TABLE queue;
            ALTER TABLE _new_queue RENAME TO queue;
            CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC, id ASC);
        """)

        # Validate FK integrity post-rebuild
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 2 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase4(conn: sqlite3.Connection) -> None:
    """Phase 4 — widen `goals.kind` CHECK to accept Forward non-theorem
    artifacts (`def`, `structure`, `class`). Rebuild required because
    SQLite cannot ALTER a CHECK constraint in place.

    Pre-condition: PRAGMA user_version < 4. Existing rows are preserved
    unchanged — pre-Phase 4 DBs only had `kind='theorem'` so the
    rebuild has no data-shape concerns.

    Post-condition (caller sets user_version = 4):
      - goals.kind CHECK accepts {'theorem','def','structure','class'}
      - All existing rows + indexes preserved
    """
    # Skip if widened CHECK already in place (fresh DB built from
    # current SCHEMA, or repeat migration).
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone()
    if chk and "'structure'" in (chk["sql"] or ""):
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ('theorem','def',
                                               'structure','class')),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_goals SELECT * FROM goals;
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 4 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase6(conn: sqlite3.Connection) -> None:
    """Phase 6 — widen `goals.status` CHECK to accept 'dead' (terminal
    for parent_needs_fix decline). Hard terminal but doesn't block dedupe
    (same statement may be valid under a different parent strategy).
    Same rebuild pattern as phase 5.

    Pre-condition: PRAGMA user_version < 6.

    Post-condition (caller sets user_version = 6):
      - goals.status CHECK accepts {'open','attempting','proved','shelved',
        'pending_strategist_review','disproved','frozen','dead'}
      - All existing rows preserved unchanged
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone()
    if chk and "'dead'" in (chk["sql"] or ""):
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ('theorem','def',
                                               'structure','class')),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved','frozen','dead')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_goals SELECT * FROM goals;
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 6 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase5(conn: sqlite3.Connection) -> None:
    """Phase 5 — widen `goals.status` CHECK to accept 'frozen' (root
    pre-launch state). Same rebuild pattern as phase 4. Backfill: for
    every problem with bootstrap_done=0 flip its root goal's status from
    'open' to 'frozen' — the legacy bootstrap_done=0 condition is exactly
    the new frozen condition.

    Pre-condition: PRAGMA user_version < 5.

    Post-condition (caller sets user_version = 5):
      - goals.status CHECK accepts {'open','attempting','proved','shelved',
        'pending_strategist_review','disproved','frozen'}
      - Roots of bootstrap_done=0 problems are 'frozen'
      - All other rows preserved unchanged
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone()
    if chk and "'frozen'" in (chk["sql"] or ""):
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ('theorem','def',
                                               'structure','class')),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved','frozen')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_goals SELECT * FROM goals;
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)
        prob_cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(problems)")}
        if "bootstrap_done" in prob_cols:
            conn.execute(
                "UPDATE goals SET status = 'frozen', updated_at = ? "
                " WHERE origin = 'root' AND status = 'open' "
                "   AND problem IN (SELECT name FROM problems "
                "                    WHERE bootstrap_done = 0)",
                (now(),),
            )
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 5 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase3(conn: sqlite3.Connection) -> None:
    """Phase 2.5 — widen strategist_decisions.trigger_kind CHECK to
    accept 'inject_batch_done'. SQLite cannot ALTER a CHECK constraint;
    rebuild the table with the new CHECK clause, copy rows, swap.

    Pre-condition: PRAGMA user_version < 3. The previous phase 2 ALTER
    TABLE ADD COLUMN block has already added `batch_id` to the live
    table (additive, no CHECK on that column), so the rebuild here only
    has to widen the trigger_kind CHECK and preserve every other column.

    Post-condition (caller sets user_version = 3):
      - strategist_decisions.trigger_kind CHECK accepts 'inject_batch_done'
      - idx_sd_batch_id index present (matches SCHEMA constant)
      - All existing rows preserved unchanged
    """
    # Skip if rebuild already happened (fresh DB built from current
    # SCHEMA has the widened CHECK + index already; this lets the
    # phase 3 guard be idempotent on those DBs).
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table'"
        " AND name = 'strategist_decisions'"
    ).fetchone()
    if chk and "inject_batch_done" in (chk["sql"] or ""):
        # CHECK already wide enough; just ensure the index exists.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sd_batch_id"
            " ON strategist_decisions(batch_id)")
        conn.commit()
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_strategist_decisions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                problem             TEXT NOT NULL REFERENCES problems(name),
                triggered_at_tick   INTEGER NOT NULL,
                trigger_kind        TEXT NOT NULL
                                        CHECK(trigger_kind IN
                                              ('first_launch','pending_review',
                                               'routine','inject_batch_done')),
                decision_kind       TEXT NOT NULL
                                        CHECK(decision_kind IN
                                              ('Inject','ConfirmShelve','Reopen',
                                               'EmitDirective','InitializeDefs',
                                               'RequestUserAmend','Noop')),
                target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                brief               TEXT NULL DEFAULT NULL,
                reason              TEXT NULL DEFAULT NULL,
                payload             TEXT NOT NULL DEFAULT '{}',
                batch_id            TEXT NULL DEFAULT NULL,
                outcome             TEXT NULL DEFAULT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );
            INSERT INTO _new_strategist_decisions
                (id, problem, triggered_at_tick, trigger_kind, decision_kind,
                 target_id, brief, reason, payload, batch_id, outcome,
                 created_at, updated_at)
            SELECT id, problem, triggered_at_tick, trigger_kind, decision_kind,
                   target_id, brief, reason, payload, batch_id, outcome,
                   created_at, updated_at
            FROM strategist_decisions;
            DROP TABLE strategist_decisions;
            ALTER TABLE _new_strategist_decisions RENAME TO strategist_decisions;
            CREATE INDEX IF NOT EXISTS idx_sd_problem
                ON strategist_decisions(problem);
            CREATE INDEX IF NOT EXISTS idx_sd_outcome
                ON strategist_decisions(outcome);
            CREATE INDEX IF NOT EXISTS idx_sd_batch_id
                ON strategist_decisions(batch_id);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 3 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


# ---------------------------------------------------------------------
# Goal helpers
# ---------------------------------------------------------------------

def insert_goal(conn: sqlite3.Connection, *, problem: str, slug: str,
                lean_path: str, statement: str, origin: str,
                depth: int = 0,
                kind: str = 'theorem',
                entry_kind: str = 'Builder',
                status: str = 'open') -> int:
    ts = now()
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts, entry_kind,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (problem, slug, lean_path, statement,
         kind, origin, status, depth, entry_kind, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_goal(conn: sqlite3.Connection, goal_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM goals WHERE id = ?", (goal_id,)
    ).fetchone()


def set_alias_target(conn: sqlite3.Connection, goal_id: int,
                     target_id: int) -> None:
    """Record that `goal_id` is an alias whose proof delegates
    to `target_id`'s file. The alias chain stays flat: if `target_id`
    is itself an alias, its own alias_target_id is followed transparently
    by the caller before passing in (see _resolve_alias_root in dedupe)."""
    conn.execute(
        "UPDATE goals SET alias_target_id = ?, updated_at = ?"
        " WHERE id = ?",
        (target_id, now(), goal_id),
    )
    conn.commit()


def aliases_pointing_at(conn: sqlite3.Connection,
                        target_id: int) -> list[int]:
    """Return ids of every goal whose alias_target_id == target_id.
    Used by prune.is_retained to keep an orphan canonical alive while
    any live goal aliases to it."""
    return [int(r["id"]) for r in conn.execute(
        "SELECT id FROM goals WHERE alias_target_id = ?", (target_id,)
    ).fetchall()]


def update_goal_status(conn: sqlite3.Connection, goal_id: int,
                       status: str) -> None:
    # Leaving 'proved' (rollback, manual reset) invalidates any prior
    # axiom_probe pass — clear integrity_verified in the same UPDATE so
    # the dispatcher gate picks the root up again on the next tick.
    # No-op for rows that were never verified (still 0).
    if status == 'proved':
        conn.execute(
            "UPDATE goals SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), goal_id),
        )
    else:
        conn.execute(
            "UPDATE goals SET status = ?, integrity_verified = 0,"
            " updated_at = ? WHERE id = ?",
            (status, now(), goal_id),
        )
    conn.commit()


def set_integrity_verified(conn: sqlite3.Connection, goal_id: int) -> None:
    """Mark a proved root as having passed `root_integrity_gate`. The
    flag stays set until `update_goal_status` flips the goal off
    'proved' (cascade rollback path)."""
    conn.execute(
        "UPDATE goals SET integrity_verified = 1, updated_at = ?"
        " WHERE id = ?",
        (now(), goal_id),
    )
    conn.commit()


def unverified_proved_roots(conn: sqlite3.Connection) -> list[str]:
    """Problems whose root is `proved` but `integrity_verified = 0`.
    Replaces the per-tick `for problem_name in manifests` scan that
    used to drive `verify.root_integrity_gate`. Ordering is by goals.id
    so iteration is deterministic across ticks."""
    return [str(r["problem"]) for r in conn.execute(
        "SELECT problem FROM goals"
        " WHERE origin = 'root' AND status = 'proved'"
        "   AND integrity_verified = 0"
        " ORDER BY id"
    ).fetchall()]


def set_goal_detached(conn: sqlite3.Connection, goal_id: int,
                      detached: bool = True) -> None:
    """Phase 2 — Strategist Reopen sets `detached=1` when the goal's
    upward strategy chain is broken (any ancestor strategy ∈ {dead,
    superseded}). BFS then dispatches on the goal standalone via the
    `open_goals` recursive CTE's `detached=1` seed. Reset to 0 by
    `update_goal_status` flipping non-'attempting' status (cascade
    rollback would otherwise leave stale detach flag)."""
    conn.execute(
        "UPDATE goals SET detached = ?, updated_at = ? WHERE id = ?",
        (1 if detached else 0, now(), goal_id),
    )
    conn.commit()


def set_inject_decision_produced_goal(
    conn: sqlite3.Connection, decision_id: int, goal_id: int,
) -> None:
    """Link an Inject decision row to the Forward goal it produced.
    The decision's `outcome` stays NULL until the goal reaches a
    terminal status — see `propagate_inject_outcome_from_goal`.

    Single-write invariant: a given Strategist decision row produces
    AT MOST one artifact (one goal OR one strategy, not both). If
    either column is already populated, we are about to write a
    second produced-artifact onto the same audit row — the symptom
    of a double dispatch (e.g. residue_thm 2026-05-21: recovery
    hardcoded-Forward re-enqueued an Inject(Backward) as Forward, so
    decision #128 ended up with produced_strategy_id=s10559 from the
    Backward path AND produced_goal_id=g2494 from the Forward
    misroute). Reject the write and log; the decision's first
    produced artifact stays canonical for outcome propagation.
    """
    existing = conn.execute(
        "SELECT produced_goal_id, produced_strategy_id"
        " FROM strategist_decisions WHERE id = ?",
        (decision_id,),
    ).fetchone()
    if existing is None:
        return
    if existing["produced_goal_id"] is not None:
        if int(existing["produced_goal_id"]) == int(goal_id):
            return  # idempotent re-write — same goal, no-op
        print(f"[db] refusing to overwrite produced_goal_id on decision "
              f"{decision_id}: existing={existing['produced_goal_id']}, "
              f"attempted={goal_id}", flush=True)
        return
    if existing["produced_strategy_id"] is not None:
        # Backward Inject dual-set is legitimate: the decision row
        # already has produced_goal_id=target written at INSERT
        # (`_commit_inject_redispatch`), and the worker later sets
        # produced_strategy_id on a strategy whose goal_id == target.
        # Only refuse when the strategy points at a DIFFERENT goal —
        # the residue_thm misroute symptom this guard exists for.
        strat = conn.execute(
            "SELECT goal_id FROM strategies WHERE id = ?",
            (int(existing["produced_strategy_id"]),),
        ).fetchone()
        if strat is None or int(strat["goal_id"]) != int(goal_id):
            print(f"[db] refusing to set produced_goal_id={goal_id} on "
                  f"decision {decision_id}: produced_strategy_id="
                  f"{existing['produced_strategy_id']} already set "
                  f"(double-dispatch indicator)", flush=True)
            return
    conn.execute(
        "UPDATE strategist_decisions SET produced_goal_id = ?,"
        " updated_at = ? WHERE id = ?",
        (goal_id, now(), decision_id),
    )
    conn.commit()


def set_inject_decision_outcome_detail(
    conn: sqlite3.Connection, decision_id: int, detail: str | None,
) -> None:
    """Stash a pipeline's rich terminal detail (e.g. a Forward decline's
    `## Why` reasoning) on its Inject decision row's `outcome_detail`
    column, so the Strategist's next wake sees WHY the brief was declined
    (#4) — not just the coarse `outcome` enum.

    Only writes while `outcome` is still NULL (pre-cascade): a real
    settled outcome must not be disturbed. `cascade_one`'s later outcome
    write preserves this value via COALESCE. No-op on empty detail."""
    if not detail:
        return
    conn.execute(
        "UPDATE strategist_decisions SET outcome_detail = ?, updated_at = ?"
        " WHERE id = ? AND outcome IS NULL",
        (detail, now(), decision_id),
    )
    conn.commit()


def propagate_inject_outcome_from_goal(
    conn: sqlite3.Connection, goal_id: int,
) -> int | None:
    """When `goal_id` reaches a terminal status, fill the outcome of
    the Inject decision row whose `produced_goal_id` points at it
    (if any, and if its outcome is still NULL).

    Mapping: goal status='proved' → outcome='success'. disproved /
    dead → outcome='failed:<status>'. Other statuses are not terminal
    and this function is a no-op for them — IN PARTICULAR `shelved`,
    which is a reopenable / parked soft-terminal: a shelved goal is NOT
    a completed inject, so its outcome stays NULL (the stall predicate's
    active-check, not a settled outcome, governs whether it suppresses
    T4). Treating shelved as settling here re-fired `inject_batch_done`
    every park (P13 4284 futile spin, 2026-06-15).

    Returns the affected decision row id (caller may then fire
    `_maybe_enqueue_inject_batch_done`), or None if nothing was
    propagated.

    Idempotent: re-running on an already-propagated goal does
    nothing (the `outcome IS NULL` guard).
    """
    row = conn.execute(
        "SELECT id FROM strategist_decisions"
        " WHERE produced_goal_id = ? AND outcome IS NULL",
        (goal_id,),
    ).fetchone()
    if row is None:
        return None
    g = conn.execute(
        "SELECT status FROM goals WHERE id = ?", (goal_id,)
    ).fetchone()
    if g is None:
        return None
    status = str(g["status"])
    if status == "proved":
        outcome = "success"
    elif status in ("disproved", "dead"):
        outcome = f"failed:{status}"
    else:
        return None  # not terminal (incl. shelved — reopenable); wait
    conn.execute(
        "UPDATE strategist_decisions SET outcome = ?, updated_at = ?"
        " WHERE id = ? AND outcome IS NULL",
        (outcome, now(), int(row["id"])),
    )
    conn.commit()
    return int(row["id"])


def set_inject_decision_produced_strategy(
    conn: sqlite3.Connection, decision_id: int, strategy_id: int,
) -> None:
    """Link an Inject(Backward/Builder) decision row to the strategy
    its dispatched worker just created. The decision's `outcome`
    stays NULL until the strategy reaches a terminal status — see
    `propagate_inject_outcome_from_strategy`.

    Single-write invariant — see `set_inject_decision_produced_goal`
    for the failure mode this guards against.
    """
    existing = conn.execute(
        "SELECT produced_goal_id, produced_strategy_id"
        " FROM strategist_decisions WHERE id = ?",
        (decision_id,),
    ).fetchone()
    if existing is None:
        return
    if existing["produced_strategy_id"] is not None:
        if int(existing["produced_strategy_id"]) == int(strategy_id):
            return  # idempotent re-write
        print(f"[db] refusing to overwrite produced_strategy_id on "
              f"decision {decision_id}: existing="
              f"{existing['produced_strategy_id']}, "
              f"attempted={strategy_id}", flush=True)
        return
    if existing["produced_goal_id"] is not None:
        # Backward Inject dual-set is legitimate: the decision row's
        # produced_goal_id was written at INSERT (via
        # `_commit_inject_redispatch`) and equals target_id; the
        # worker's just-reserved strategy lives on that same goal.
        # Refuse only when the strategy is on a DIFFERENT goal — the
        # residue_thm 2026-05-21 misroute symptom this guard exists for.
        strat = conn.execute(
            "SELECT goal_id FROM strategies WHERE id = ?",
            (int(strategy_id),),
        ).fetchone()
        if strat is None or int(strat["goal_id"]) != int(existing["produced_goal_id"]):
            print(f"[db] refusing to set produced_strategy_id={strategy_id} "
                  f"on decision {decision_id}: produced_goal_id="
                  f"{existing['produced_goal_id']} already set "
                  f"(double-dispatch indicator)", flush=True)
            return
    conn.execute(
        "UPDATE strategist_decisions SET produced_strategy_id = ?,"
        " updated_at = ? WHERE id = ?",
        (strategy_id, now(), decision_id),
    )
    conn.commit()


def propagate_inject_outcome_from_strategy(
    conn: sqlite3.Connection, strategy_id: int,
) -> int | None:
    """When `strategy_id` reaches a terminal status, fill the outcome
    of the Inject(Backward/Builder) decision row whose
    `produced_strategy_id` points at it (if any, and if outcome is
    still NULL).

    Mapping: strategy 'succeeded' → 'success'. 'superseded' → 'success'
    (the goal got proved by a sibling — Strategist's intent of "make
    this goal terminal-proved" was met, even though by a different
    decomposition). 'dead' → 'failed:dead'. 'stalled' → 'failed:stalled'
    (subgoals all settled, >=1 soft-shelved — parked but reopenable).
    Other statuses are not terminal and this function is a no-op.

    Returns the affected decision row id (caller may then fire
    `_maybe_enqueue_inject_batch_done`), or None if nothing was
    propagated.

    Idempotent: re-running on an already-propagated strategy is a
    no-op via the `outcome IS NULL` guard.
    """
    row = conn.execute(
        "SELECT id FROM strategist_decisions"
        " WHERE produced_strategy_id = ? AND outcome IS NULL",
        (strategy_id,),
    ).fetchone()
    if row is None:
        return None
    s = conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (strategy_id,)
    ).fetchone()
    if s is None:
        return None
    status = str(s["status"])
    if status in ("succeeded", "superseded"):
        outcome = "success"
    elif status == "dead":
        outcome = "failed:dead"
    elif status == "stalled":
        outcome = "failed:stalled"
    else:
        return None  # not terminal; wait
    conn.execute(
        "UPDATE strategist_decisions SET outcome = ?, updated_at = ?"
        " WHERE id = ? AND outcome IS NULL",
        (outcome, now(), int(row["id"])),
    )
    conn.commit()
    return int(row["id"])


# ---------------------------------------------------------------------
# Phase 2 — problem-level Strategist state helpers
# ---------------------------------------------------------------------

def set_problem_bootstrap_done(conn: sqlite3.Connection, problem: str) -> None:
    """Mark a problem as past the T0 first-launch trigger. Set after
    Strategist's first commit on that problem (any decision kind)."""
    conn.execute(
        "UPDATE problems SET bootstrap_done = 1 WHERE name = ?",
        (problem,),
    )
    conn.commit()


def set_problem_strategist_directive(conn: sqlite3.Connection,
                                     problem: str,
                                     directive: str | None) -> None:
    """Overwrite-on-write standing directive. EmitDirective /
    Reopen-with-directive sets non-empty text; passing None / empty
    clears it (the cascade reset path)."""
    conn.execute(
        "UPDATE problems SET strategist_directive = ? WHERE name = ?",
        (directive if directive else None, problem),
    )
    conn.commit()


def update_problem_last_strategist_at(conn: sqlite3.Connection,
                                      problem: str) -> None:
    """Touch the last-Strategist-commit timestamp. Called on every Strategist
    commit regardless of decision_kind / trigger_kind. (Event-driven; does
    NOT drive T1 — that reads `last_routine_at`.)"""
    conn.execute(
        "UPDATE problems SET last_strategist_at = ? WHERE name = ?",
        (now(), problem),
    )
    conn.commit()


def update_problem_last_routine_at(conn: sqlite3.Connection,
                                   problem: str) -> None:
    """Touch the ROUTINE-only clock that drives T1. Called ONLY on a
    `trigger_kind='routine'` Strategist commit, so the routine audit fires on
    its own fixed cadence instead of being reset by event-driven triggers."""
    conn.execute(
        "UPDATE problems SET last_routine_at = ? WHERE name = ?",
        (now(), problem),
    )
    conn.commit()


def unacknowledged_inject_batches(conn: sqlite3.Connection,
                                  problem: str) -> list[str]:
    """Return batch_ids of Inject batches on this problem where every
    row's `outcome` is filled (batch fully terminated) AND the most
    recent row update is newer than the problem's last_strategist_at
    (i.e. Strategist hasn't seen this completion yet).

    Used by the dispatcher's trigger-derivation block to fire
    `inject_batch_done` Strategist invocations. Per Phase 2.5 §X,
    the acknowledgement ratchet is `last_strategist_at`: a Strategist
    commit advances it, so subsequent batch-done queries naturally
    deduplicate without a per-row `acked_at` column.

    NULL `last_strategist_at` (problem never had a Strategist commit)
    behaves as 'all batches are unacknowledged' — coalesced to
    '1970-01-01T00:00:00' so SQL comparison works.
    """
    rows = conn.execute(
        "SELECT batch_id,"
        "       SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) AS pending,"
        "       MAX(updated_at) AS last_update"
        " FROM strategist_decisions"
        " WHERE problem = ? AND batch_id IS NOT NULL"
        " GROUP BY batch_id"
        " HAVING pending = 0",
        (problem,),
    ).fetchall()
    if not rows:
        return []
    lsa_row = conn.execute(
        "SELECT COALESCE(last_strategist_at, '1970-01-01T00:00:00+00:00')"
        " AS lsa FROM problems WHERE name = ?",
        (problem,),
    ).fetchone()
    lsa = str(lsa_row["lsa"]) if lsa_row else '1970-01-01T00:00:00+00:00'
    return [str(r["batch_id"]) for r in rows
            if str(r["last_update"]) > lsa]


def problems_needing_t0(conn: sqlite3.Connection,
                        scope: str | None = None
                        ) -> list[tuple[str, int]]:
    """Return [(problem_name, root_goal_id)] for problems whose root
    goal is `frozen` — the pre-first_launch state cli init writes
    (Phase 5). Caller is responsible for the awaiting_human gate +
    in-flight Strategist dedup. Root goal id is computed via the
    standard `origin='root'` join.

    Filtering on `status='frozen'` (NOT on `bootstrap_done`) naturally
    excludes terminal roots: pre-Phase-2 already-proved problems keep
    `bootstrap_done=0` forever (never Strategist'd), and gating on that
    column would burn one Strategist spawn per such problem on every
    fresh daemon start. A root that is `open` without ever being
    Strategist'd (legacy reset paths) is instead covered by T1's
    NULL-`last_strategist_at` = ancient rule.
    """
    # In-flight Inject suppression: if Strategist's prior commit on this
    # problem produced work still LIVE (in flight), suppress T0 — Strategist
    # will be re-fired by the cascade-side `inject_batch_done` trigger when
    # the last outcome lands; T0 firing meanwhile just burns spawns on Noop
    # ("waiting for Forward"). Uses `has_live_inflight_inject` (NULL inject
    # whose produced goal is not parked/shelved), NOT the old blanket "any
    # NULL-outcome batch row" test: once `shelved` stopped settling, a
    # shelved-produced inject stays NULL forever and the blanket test would
    # wedge T0 (the Phase 11 disease). `has_live` (not the stall predicate's
    # narrower active-check) so a just-committed Forward inject whose worker
    # has not yet registered its lemma still counts as in-flight here — T0
    # has no worker-queue check to lean on. (For a `frozen` root this is
    # near-vacuous — injects only exist after first_launch un-freezes — but
    # kept correct per the same-class-fix discipline.)
    sql = (
        "SELECT p.name, g.id AS root_id"
        " FROM problems p"
        " JOIN goals g ON g.problem = p.name AND g.origin = 'root'"
        " WHERE g.status = 'frozen'"
    )
    args: tuple = ()
    if scope is not None:
        sql += " AND p.name LIKE ?"
        args = (scope,)
    sql += " ORDER BY p.name"
    return [(r["name"], int(r["root_id"])) for r in conn.execute(sql, args)
            if not has_live_inflight_inject(conn, str(r["name"]))]


def problems_needing_t1(conn: sqlite3.Connection, *,
                        max_age_sec: float,
                        scope: str | None = None,
                        since_iso: str | None = None,
                        ) -> list[tuple[str, int]]:
    """Return [(problem_name, root_goal_id)] for problems whose ROUTINE clock
    (`last_routine_at`) is older than `max_age_sec`. Excludes problems whose
    root goal is already terminal (proved / shelved / disproved / frozen).

    Two deliberate departures from the event-driven triggers (T0 / T2), so the
    routine audit fires on its own fixed running-time cadence — its
    methodological job (periodic full-tree survey) is distinct from reacting
    to a shelve or a batch completion, and must not be starved by a busy event
    stream (stokes 2026-06-12: 0 routine over 5h):

      1. Reads `last_routine_at` (bumped ONLY by a routine commit), not
         `last_strategist_at` (bumped by every commit). So pending_review /
         inject_batch_done commits do NOT reset the routine clock.
      2. NO in-flight-batch suppression (T0 keeps it; routine does not) — the
         routine audit is independent of batch resolution.

    `since_iso` (daemon start, ISO): the clock baseline is
    `max(last_routine_at, since_iso)`, so paused/down time does not count
    toward the interval — a long pause doesn't make routine fire immediately
    on restart; it waits `max_age_sec` of running time. NULL last_routine_at
    is "ancient" (never routine'd), so the first routine fires `max_age_sec`
    after startup."""
    # SQLite julianday() yields fractional days; convert max_age_sec to days.
    max_age_days = max_age_sec / 86400.0
    # Clock baseline: later of last_routine_at (or epoch, if never routine'd)
    # and the daemon start, so paused/down time is excluded.
    if since_iso is not None:
        baseline_sql = ("max(julianday(coalesce(p.last_routine_at,"
                        " '1970-01-01')), julianday(?))")
        args: list = [since_iso, max_age_days]
    else:
        baseline_sql = "julianday(coalesce(p.last_routine_at, '1970-01-01'))"
        args = [max_age_days]
    sql = (
        "SELECT p.name, g.id AS root_id"
        " FROM problems p"
        " JOIN goals g ON g.problem = p.name AND g.origin = 'root'"
        " WHERE g.status NOT IN ('proved','shelved','disproved','frozen')"
        f"   AND julianday('now') - {baseline_sql} > ?"
    )
    if scope is not None:
        sql += " AND p.name LIKE ?"
        args.append(scope)
    sql += " ORDER BY p.name"
    return [(r["name"], int(r["root_id"])) for r in conn.execute(sql, tuple(args))]


def problems_with_pending_review(conn: sqlite3.Connection, *,
                                 scope: str | None = None
                                 ) -> list[tuple[str, int]]:
    """Return [(problem_name, root_goal_id)] for problems with at least one
    goal in `pending_strategist_review` whose root is not HARD-terminal
    (proved / disproved). A `shelved` root is NOT excluded: the
    ConfirmShelve+Inject endgame deliberately parks the root `shelved` while
    the Strategist works bricks, so a brick that shelves to
    `pending_strategist_review` under a parked root still needs its review
    enqueued — excluding shelved roots here orphaned exactly that case (P13
    `per_chart_stokes_generic` under a shelved `main`, 2026-06-14), and on a
    fresh daemon start (no other in-flight work) idle-exited the run.

    The per-tick stuck-state reconciler (`reconcile_stuck_states`) enqueues a
    Strategist for each so a pending review never orphans when the cascade-
    time fast-path enqueue (`_enqueue_strategist_review`) is deduped / lost /
    not restored at restart — the lost-wakeup that left P13 goals stuck
    (2026-06-13) and wedged Banach-Tarski g3246 for 30+ min (2026-05-27). The
    spawn-time `_derive_strategist_trigger` then sees the pending goal and
    runs a `pending_review` wake.

    No in-flight-batch suppression (unlike T0/T1): a pending review and an
    unacknowledged Inject batch are not mutually exclusive — `_derive_
    strategist_trigger` orders them (batch first), and the caller's per-root
    Strategist dedup prevents a double-enqueue."""
    sql = (
        "SELECT DISTINCT p.name, g_root.id AS root_id"
        " FROM problems p"
        " JOIN goals g_root ON g_root.problem = p.name"
        "   AND g_root.origin = 'root'"
        " JOIN goals g_pend ON g_pend.problem = p.name"
        "   AND g_pend.status = 'pending_strategist_review'"
        " WHERE g_root.status NOT IN ('proved','disproved')"
    )
    args: tuple = ()
    if scope is not None:
        sql += " AND p.name LIKE ?"
        args = (scope,)
    sql += " ORDER BY p.name"
    return [(r["name"], int(r["root_id"])) for r in conn.execute(sql, args)]


def null_inject_redispatch_specs(conn: sqlite3.Connection, *,
                                 scope: str | None = None
                                 ) -> list[dict]:
    """Queue specs for every NULL-outcome Inject decision that still needs a
    worker (its produced artifact does not exist yet).

    Shared by startup `recovery` (re-enqueues all — clean slate) and the
    per-tick `reconcile_stuck_states` (re-enqueues only those with no
    in-flight worker). Encodes the produced-artifact guards so an Inject is
    NOT redispatched once its outcome will propagate from the artifact's
    terminal: a Forward that already registered its lemma (`produced_goal_id`
    set), or a Backward that already committed a strategy
    (`produced_strategy_id` set) — both are commit-time WORK ARTIFACTS, so
    their presence means the worker reached its product and the outcome will
    propagate from there. A BUILDER HAS NO SUCH ARTIFACT: it proves its
    target in place, and `produced_goal_id` is set to `=target` at commit as
    an outcome backlink, NOT a work-done signal — it is non-NULL from the
    very start. So a killed Builder must be judged by its TARGET'S status,
    not by `produced_goal_id` (the parked-target check below). Gating Builder
    on `produced_goal_id` is exactly what wedged P13 4284 (2026-06-15): every
    killed Builder was skipped forever (backlink set at commit) while
    `has_active_inflight_inject` counted it active → the Strategist was
    suppressed and the work was never resumed → permanent deadlock.
    ALSO skips a Backward/Builder whose TARGET goal is no longer awaiting a
    worker (parked/terminal — e.g. a return_to_parent that shelved the target
    without committing a strategy): its NULL outcome is permanent now that
    `shelved` no longer settles, but the work is parked, not missing —
    redispatching would re-spin it forever (P13 4284, 2026-06-15). A
    NULL-outcome Inject whose worker died on infra failure (no artifact,
    target still open/attempting) wedges the problem via the in-flight
    active-check (`has_active_inflight_inject`) — so it must be redispatched.

    Returns dicts: `{decision_id, problem, kind, target_id, target_kind}`."""
    sql = (
        "SELECT id, problem, payload, target_id, produced_goal_id,"
        " produced_strategy_id FROM strategist_decisions"
        " WHERE decision_kind = 'Inject' AND outcome IS NULL"
    )
    args: tuple = ()
    if scope is not None:
        sql += " AND problem LIKE ?"
        args = (scope,)
    specs: list[dict] = []
    for r in conn.execute(sql, args):
        try:
            payload = json.loads(r["payload"] or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {}
        pipeline = payload.get("pipeline")
        if pipeline == "Forward":
            if r["produced_goal_id"] is not None:
                continue  # lemma landed; outcome propagates from goal
            specs.append({
                "decision_id": int(r["id"]), "problem": str(r["problem"]),
                "kind": "Forward", "target_id": str(r["problem"]),
                "target_kind": "Problem",
            })
        elif pipeline in ("Backward", "Builder"):
            if r["target_id"] is None:
                continue  # malformed — no target_goal_id; skip not dispatch
            if pipeline == "Backward" and r["produced_strategy_id"] is not None:
                continue  # strategy committed; outcome from strategy terminal
            # NB: NO produced_goal_id guard for Builder — it proves in place,
            # so produced_goal_id is a commit-time backlink (=target), not a
            # work-done artifact (see docstring). Builder is judged solely by
            # its target's status, immediately below.
            # Target no longer awaiting a worker (parked / terminal): the
            # worker already RAN and parked it (e.g. a Backward
            # return_to_parent that committed no strategy → target shelved,
            # or pending_strategist_review awaiting a Strategist verdict).
            # Its NULL outcome is now permanent (shelved no longer settles —
            # see propagate_inject_outcome_from_goal), but the work is NOT
            # missing, so redispatching would re-spin the parked goal forever
            # (the P13 4284 disease, here via the redispatch path). Only
            # redispatch a target that genuinely still awaits a worker.
            tgt = conn.execute(
                "SELECT status FROM goals WHERE id = ?",
                (int(r["target_id"]),),
            ).fetchone()
            if tgt is None or str(tgt["status"]) not in ("open", "attempting"):
                continue
            specs.append({
                "decision_id": int(r["id"]), "problem": str(r["problem"]),
                "kind": pipeline, "target_id": str(int(r["target_id"])),
                "target_kind": "Goal",
            })
        # Unknown pipeline (legacy / malformed) — skip silently.
    return specs


def queue_has_decision(conn: sqlite3.Connection, decision_id: int) -> bool:
    """True iff a queue row carries `decision_id` (Inject-authored dispatch).
    Used by `reconcile_stuck_states` to avoid re-enqueuing a NULL-outcome
    Inject whose worker is already queued."""
    row = conn.execute(
        "SELECT 1 FROM queue WHERE decision_id = ? LIMIT 1", (decision_id,),
    ).fetchone()
    return row is not None


def has_active_inflight_inject(conn: sqlite3.Connection, problem: str) -> bool:
    """True iff `problem` has a NULL-outcome Inject decision whose produced
    work is still genuinely ACTIVE:

      * `produced_goal_id`     → goal status open / attempting, OR
      * `produced_strategy_id` → strategy 'proposed' with >=1 alive subgoal
        (open / attempting / pending_strategist_review).

    The precise notion of "an inject batch is still in flight", shared by the
    stall predicate (`is_problem_stalled` condition 4) and the T0 first_launch
    suppression (`problems_needing_t0`). REPLACES the old blanket "any
    NULL-outcome batch row exists" test that both used: once `shelved` stopped
    settling its inject (it is reopenable / parked — see
    `propagate_inject_outcome_from_goal`), a shelved-produced inject stays NULL
    forever, so the blanket test would suppress T0/T4 forever (a permanent
    wedge — the Phase 11 disease). Only ACTIVE produced work counts as
    in-flight; a freshly-committed inject is additionally covered by its
    enqueued worker (queue row) in the stall predicate's condition 3."""
    if conn.execute(
        "SELECT 1 FROM strategist_decisions sd"
        " JOIN goals g ON g.id = sd.produced_goal_id"
        " WHERE sd.problem = ? AND sd.decision_kind = 'Inject'"
        "   AND sd.batch_id IS NOT NULL AND sd.outcome IS NULL"
        "   AND g.status IN ('open','attempting') LIMIT 1",
        (problem,),
    ).fetchone() is not None:
        return True
    if conn.execute(
        "SELECT 1 FROM strategist_decisions sd"
        " JOIN strategies s ON s.id = sd.produced_strategy_id"
        " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        " JOIN goals g ON g.id = ss.subgoal_id"
        " WHERE sd.problem = ? AND sd.decision_kind = 'Inject'"
        "   AND sd.batch_id IS NOT NULL AND sd.outcome IS NULL"
        "   AND s.status = 'proposed'"
        "   AND g.status IN ('open','attempting','pending_strategist_review')"
        " LIMIT 1",
        (problem,),
    ).fetchone() is not None:
        return True
    return False


def has_live_inflight_inject(conn: sqlite3.Connection, problem: str) -> bool:
    """True iff `problem` has a NULL-outcome Inject decision that is still
    LIVE — i.e. NOT parked. A NULL inject is parked iff its produced goal is
    `shelved` (reopenable, but its outcome now stays NULL forever — see
    `propagate_inject_outcome_from_goal`); every other NULL inject is live:
    its worker is still producing (a Forward before lemma registration has
    `produced_goal_id` NULL), or its produced goal / strategy is genuinely in
    progress.

    BROADER than `has_active_inflight_inject` on purpose. This is for
    suppression sites with NO in-flight-WORKER visibility — T0
    (`problems_needing_t0`) and the verify_decision Noop-guard on a blocked
    root — which must treat a just-committed Forward inject whose worker has
    not yet registered its lemma (produced_goal_id NULL) as in-flight, so the
    Strategist waits instead of firing / being forced into redundant work.
    The stall predicate (`is_problem_stalled`) instead uses the narrower
    active-check, because its condition 3 separately covers the enqueued-
    worker window — see that function and `has_active_inflight_inject`."""
    return conn.execute(
        "SELECT 1 FROM strategist_decisions sd"
        " WHERE sd.problem = ? AND sd.decision_kind = 'Inject'"
        "   AND sd.batch_id IS NOT NULL AND sd.outcome IS NULL"
        "   AND NOT EXISTS ("
        "     SELECT 1 FROM goals g"
        "     WHERE g.id = sd.produced_goal_id AND g.status = 'shelved'"
        "   ) LIMIT 1",
        (problem,),
    ).fetchone() is not None


def is_problem_stalled(conn: sqlite3.Connection, problem: str, *,
                       running: "set[tuple] | None" = None) -> bool:
    """True iff `problem` is structurally STALLED:

      1. root not terminal (proved / shelved / disproved),
      2. zero DISPATCHABLE open goals — open goals reachable from root via
         'proposed' / 'succeeded' strategies. An ORPHANED open goal (its
         strategy chain died) is NOT dispatchable, so it does NOT count;
         a raw `status='open'` probe would wrongly mask the stall.
      3. no in-flight Backward / Builder / Forward worker (queue + the
         optional in-memory `running` set).
      4. no NULL-outcome Inject whose produced work is still ACTIVE (an
         open/attempting produced goal, or a 'proposed' produced strategy
         with >=1 alive subgoal). This SUBSUMES the old blanket "any
         NULL-outcome inject batch suppresses" pre-filter that lived in
         `problems_stalled`. The narrower active-check is what lets a
         SHELVED-produced NULL inject (outcome stays NULL forever now that
         shelved no longer settles — see propagate_inject_outcome_from_goal)
         STOP suppressing T4; the blanket pre-filter would have wedged the
         problem forever instead (the Phase 11 disease).

    SINGLE SOURCE OF TRUTH for the stall signal, shared by
    `problems_stalled` (T4 enqueue) and `_section_stall_warning`
    (Strategist Context.md). The two MUST agree: if T4 fires a Strategist
    on a stall whose warning the Strategist's context then fails to
    surface, the Strategist Noop-confirms, the problem re-stalls, and T4
    re-fires → a Strategist livelock (P13 2026-06-13: the two had diverged
    on raw vs reachable open-goal counting — fixing one without the other
    turned a clean give-up into an EmitDirective spin). `running` is the
    dispatcher's live set; omit it (context-compile has none) for a
    queue-only in-flight check (harmless brief false-positive while a
    worker is mid-spawn)."""
    root = conn.execute(
        "SELECT status FROM goals WHERE problem = ? AND origin = 'root' LIMIT 1",
        (problem,),
    ).fetchone()
    if root is None or str(root["status"]) in ("proved", "shelved",
                                               "disproved"):
        return False
    # 2. any DISPATCHABLE (alive-reachable) open goal → not stalled.
    if conn.execute(
        "WITH RECURSIVE alive(id) AS ("
        "  SELECT id FROM goals WHERE problem = ? AND origin = 'root'"
        "  UNION"
        "  SELECT g.id FROM goals g"
        "  JOIN strategy_subgoals ss ON ss.subgoal_id = g.id"
        "  JOIN strategies s ON s.id = ss.strategy_id"
        "  JOIN alive a ON a.id = s.goal_id"
        "  WHERE s.status IN ('proposed','succeeded')"
        ") SELECT 1 FROM goals"
        " WHERE problem = ? AND status = 'open' AND id IN alive LIMIT 1",
        (problem, problem),
    ).fetchone() is not None:
        return False
    # 3. any in-flight Backward / Builder / Forward worker (queue + running).
    if conn.execute(
        "SELECT 1 FROM queue q"
        " JOIN goals g ON g.id = CAST(q.target_id AS INTEGER)"
        " WHERE g.problem = ? AND q.kind IN ('Backward','Builder') LIMIT 1",
        (problem,),
    ).fetchone() is not None:
        return False
    if conn.execute(
        "SELECT 1 FROM queue WHERE target_id = ? AND kind = 'Forward' LIMIT 1",
        (problem,),
    ).fetchone() is not None:
        return False
    run = running or set()
    if any(len(t) >= 2 and t[1] == "Forward" and t[0] == problem for t in run):
        return False
    bw_bu_ids = {t[0] for t in run
                 if len(t) >= 2 and t[1] in ("Backward", "Builder")}
    if bw_bu_ids:
        placeholders = ",".join("?" * len(bw_bu_ids))
        if conn.execute(
            f"SELECT 1 FROM goals WHERE problem = ?"
            f" AND CAST(id AS TEXT) IN ({placeholders}) LIMIT 1",
            (problem, *bw_bu_ids),
        ).fetchone() is not None:
            return False
    # 4. a NULL-outcome Inject whose produced work is genuinely ACTIVE keeps
    #    the problem in-flight (the batch is still resolving; inject_batch_done
    #    will wake Strategist). REPLACES the old blanket batch-suppression
    #    pre-filter — a NULL inject whose produced goal got SHELVED is parked,
    #    not in flight, and must NOT suppress T4 (else permanent wedge).
    if has_active_inflight_inject(conn, problem):
        return False
    return True


def problems_stalled(conn: sqlite3.Connection, *,
                     scope: str | None = None,
                     running: "set[tuple[str, str]] | None" = None,
                     ) -> list[tuple[str, int]]:
    """Return [(problem_name, root_goal_id)] for problems matching the
    structural stall signal:

      1. root not yet terminal (proved/shelved/disproved)
      2. zero `open_goals` reachable in scope (BFS has nothing to dispatch)
      3. no in-flight Backward / Builder / Forward worker on this problem
         (neither in the dispatcher's `running` set nor in the queue)
      4. no NULL-outcome Inject whose produced work is still ACTIVE

    Conditions 2-4 are evaluated by `is_problem_stalled` (the shared
    single-source predicate); the candidate SQL here only applies
    condition 1 (root-not-terminal). When all four hold, the dispatcher
    can dispatch nothing on this
    problem until Strategist intervenes. Routine T1 fires every 60 min
    which is too slow (polar 2026-05-23: 174 min stall before budget
    exhaust). T4 trigger uses this signal to enqueue Strategist
    immediately. Pairs with `_section_stall_warning` in Strategist
    Context.md which re-checks the signal and surfaces a header so
    Strategist knows not to Noop.

    `running`: caller's live in-memory set of (target_id, kind) tuples.
    Optional — when omitted the check uses queue rows only (may
    false-positive briefly while a worker is mid-spawn but not yet in
    the queue; the false-positive is harmless: Strategist enqueue is
    idempotent via `is_in_queue` dedup at the call site).
    """
    # Candidate pre-filter is root-not-terminal ONLY. In-flight Inject
    # suppression is NO LONGER a blanket "any NULL-outcome batch row"
    # pre-filter here — that wedged the problem forever once `shelved`
    # stopped settling (a shelved-produced inject stays NULL forever).
    # It now lives in `is_problem_stalled` as a precise ACTIVE-check
    # (condition 4: suppress only while the inject's produced work is
    # open/attempting or a proposed strategy with an alive subgoal),
    # keeping T4 and `_section_stall_warning` in lockstep automatically.
    sql = (
        "SELECT p.name, g.id AS root_id"
        " FROM problems p"
        " JOIN goals g ON g.problem = p.name AND g.origin = 'root'"
        " WHERE g.status NOT IN ('proved','shelved','disproved')"
    )
    args: tuple = ()
    if scope is not None:
        sql += " AND p.name LIKE ?"
        args = (scope,)
    sql += " ORDER BY p.name"
    candidates = list(conn.execute(sql, args))
    if not candidates:
        return []

    # Per-candidate structural stall test via the shared single-source
    # predicate (keeps T4 and `_section_stall_warning` in lockstep). The
    # candidate SQL above only applied the root-not-terminal pre-filter;
    # the in-flight-Inject active-check is condition 4 inside the predicate.
    run = running or set()
    stalled: list[tuple[str, int]] = []
    for r in candidates:
        prob = str(r["name"])
        if is_problem_stalled(conn, prob, running=run):
            stalled.append((prob, int(r["root_id"])))
    return stalled


def problem_has_awaiting_human(conn: sqlite3.Connection, problem: str) -> bool:
    """True iff this problem has a `strategist_decisions` row with
    `outcome='awaiting_human'`. While true the dispatcher should pause
    all Strategist + Backward + Builder + Forward dispatch on this
    problem until operator resolves the row (handled in dispatcher's
    pop loop / strategist_triggers)."""
    try:
        row = conn.execute(
            "SELECT 1 FROM strategist_decisions"
            " WHERE problem = ? AND outcome = 'awaiting_human' LIMIT 1",
            (problem,),
        ).fetchone()
    except sqlite3.OperationalError:
        # Pre-Phase 2 schema (table missing).
        return False
    return row is not None


def scoped_problem_names(conn: sqlite3.Connection, scope: str) -> list[str]:
    """Distinct problem names that have at least one goal and match the
    SQL LIKE `scope` pattern. The dispatcher's periodic TREE.md refresh
    uses this so a `--scope` run only re-renders + atomic-replaces the
    in-scope trees each tick, instead of churning all ~281 problems'
    TREE.md — on Windows the rapid replace of unrelated trees raised
    transient WinError 5 sharing violations (caught, but noise)."""
    return [str(r[0]) for r in conn.execute(
        "SELECT DISTINCT problem FROM goals WHERE problem LIKE ?"
        " ORDER BY problem", (scope,))]


def dispatchable_open_goals(conn: sqlite3.Connection,
                            *, scope: str | None = None
                            ) -> list[sqlite3.Row]:
    """`open_goals(scope)` minus goals whose problem is paused on an
    unresolved `RequestUserAmend` (`outcome='awaiting_human'`).

    bfs_refill silently skips awaiting_human problems, so their open
    goals can make no progress this run. The dispatcher's idle-exit
    check uses this (not raw `open_goals`) so a scoped daemon whose only
    in-scope problem is paused EXITS with a report instead of livelocking
    forever — 2026-06-12 P12 (stokes_induced_orient) was paused on a
    Defs.lean amend, but the unscoped `open_goals` saw brouwer's unrelated
    open goal and never exited, burning the periodic tree-write each tick
    and reading as a multi-hour hang."""
    goals = open_goals(conn, scope=scope)
    if not goals:
        return []
    problems = {str(g["problem"]) for g in goals}
    paused = {p for p in problems if problem_has_awaiting_human(conn, p)}
    if not paused:
        return goals
    return [g for g in goals if str(g["problem"]) not in paused]


def update_goal_entry_kind(conn: sqlite3.Connection, goal_id: int,
                           entry_kind: str) -> None:
    """Persist the dispatch-routing directive on a goal. Used by
    cascade for agent_declined (Builder) to flip routing to Backward
    without inflating attempts (Phase 7 — decision 5: attempts is
    LLM-call failure count, not a routing inflation knob)."""
    conn.execute(
        "UPDATE goals SET entry_kind = ?, updated_at = ? WHERE id = ?",
        (entry_kind, now(), goal_id),
    )
    conn.commit()


def increment_goal_attempts(conn: sqlite3.Connection, goal_id: int) -> int:
    conn.execute(
        "UPDATE goals SET attempts = attempts + 1, updated_at = ? WHERE id = ?",
        (now(), goal_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT attempts FROM goals WHERE id = ?", (goal_id,)
    ).fetchone()
    return int(row["attempts"]) if row else 0


def goals_reachable_excluding(conn: sqlite3.Connection, *,
                              problem: str,
                              exclude_goal_id: int) -> set[int]:
    """Goal ids in `problem` reachable from a root / detached seed via
    proposed|succeeded strategies WITHOUT passing through
    `exclude_goal_id` (it is removed as a node, cutting every path that
    ran through it — transitively, since the CTE never re-adds it).

    The shelve cascade uses this to spare a descendant of a just-
    terminated goal that still has an INDEPENDENT live path to root — a
    cross-branch cited / auto-linked sibling. A shared (multi-parent) DAG
    node must only be cascade-shelved when it loses its LAST live parent,
    not merely the one that just died; otherwise a goal another live
    strategy still needs becomes un-dispatchable and that strategy hangs.
    Mirrors `open_goals`' alive CTE (root ∪ detached ∪ subgoals-of-live-
    strategies-of-live-goals), scoped to one problem, minus the excluded
    node. Maintains the invariant `open ⇒ reachable`."""
    rows = conn.execute(
        "WITH RECURSIVE alive(id) AS ("
        "    SELECT id FROM goals"
        "      WHERE problem = ? AND origin = 'root' AND id != ?"
        "    UNION"
        "    SELECT id FROM goals"
        "      WHERE problem = ? AND detached = 1 AND id != ?"
        "    UNION"
        "    SELECT g.id FROM goals g"
        "    JOIN strategy_subgoals ss ON ss.subgoal_id = g.id"
        "    JOIN strategies s ON s.id = ss.strategy_id"
        "    JOIN alive a ON a.id = s.goal_id"
        "    WHERE g.problem = ? AND g.id != ?"
        "      AND s.status IN ('proposed','succeeded')"
        ") SELECT id FROM alive",
        (problem, exclude_goal_id, problem, exclude_goal_id,
         problem, exclude_goal_id),
    ).fetchall()
    return {int(r["id"]) for r in rows}


def open_goals(conn: sqlite3.Connection,
               *, scope: str | None = None) -> list[sqlite3.Row]:
    """Open goals eligible for dispatch.

    Walks the strategy DAG from each root: a goal is 'reachable' iff
    every strategy on some ancestor chain back to a root is alive
    ('proposed' or 'succeeded'). Open goals not reachable this way are
    orphaned by an upstream supersede / dead and must NOT be dispatched.

    The recursive CTE handles arbitrary depth — fixing the prior bug
    where a depth-2 sub-goal of a 'proposed' strategy was kept alive
    even when that strategy's own goal was orphaned upstream.

    `scope` (optional SQL LIKE pattern): when set, only return goals
    whose problem matches. Used by `dispatcher.run(scope=...)` so a
    benchmark daemon doesn't dispatch unrelated research problems
    sitting in the same workspace.
    """
    # Phase 2 — `detached=1` goals are dispatchable independently
    # (Strategist Reopen on a goal whose upward strategy chain is dead
    # auto-flagged them; framework treats them as if they have a live
    # parent strategy). UNION'd into the alive seed set so descendants
    # via their own live strategies also propagate.
    sql = (
        "WITH RECURSIVE alive(id) AS ("
        "    SELECT id FROM goals WHERE origin = 'root'"
        "    UNION"
        "    SELECT id FROM goals WHERE detached = 1"
        "    UNION"
        "    SELECT g.id FROM goals g"
        "    JOIN strategy_subgoals ss ON ss.subgoal_id = g.id"
        "    JOIN strategies s ON s.id = ss.strategy_id"
        "    JOIN alive a ON a.id = s.goal_id"
        "    WHERE s.status IN ('proposed','succeeded')"
        ") "
        "SELECT g.* FROM goals g "
        "JOIN problems p ON p.name = g.problem "
        "WHERE g.status = 'open' AND g.id IN alive "
        # Curry-Howard unified — any kind whose body carries `sorry`
        # is a deferred obligation and enters BFS. Forward commits
        # sorry-free outputs as 'proved' directly; sorry-bearing
        # outputs land here regardless of kind. `next_worker_kind`
        # returns Builder/Backward; `_skeleton.build_strategy_skeleton`
        # preserves the original `theorem|def|structure|class` keyword
        # in the strategy patch so the elaborator sees a matching
        # declaration head. Pre-unification this filter was
        # `g.kind = 'theorem'`, which silently stranded any
        # `def := sorry` Forward output at status='open' or hid the
        # stub behind a fake-proved status (brouwer 2026-05-22 G3).
        # Phase 5 — first-launch race protection now lives in goals.status:
        # root inits as 'frozen' and Strategist must explicitly
        # `Reopen(root)` to release BFS. The `g.status = 'open'` filter
        # above already excludes frozen roots, so no separate gate is
        # needed here. (Sub-goals never become frozen — only roots — so
        # this filter cleanly maps to the legacy bootstrap_done=1 gate
        # without ambiguity.)
    )
    params: tuple = ()
    if scope is not None:
        sql += "AND g.problem LIKE ? "
        params = (scope,)
    sql += "ORDER BY g.id"
    return list(conn.execute(sql, params))


def root_proved(conn: sqlite3.Connection, problem: str | None = None,
                scope: str | None = None) -> bool:
    """True iff all root goals in scope have status='proved'.

    `problem`: exact-match filter (single problem).
    `scope`: SQL LIKE pattern — matches `dispatcher.run(scope=...)`
        usage. Required for scoped runs: an unfiltered call checks
        every root in the DB, so a `--scope sylvester_gallai` run
        whose SG root is proved returns False because miniF2F roots
        sitting in the same workspace are still open. Observed
        2026-05-19 SG run: root proved, daemon exit logged
        `roots_proved=False` + returned exit code 1 even though the
        scoped problem succeeded.
    """
    sql = "SELECT count(*) AS c FROM goals WHERE origin = 'root' AND status != 'proved'"
    args: tuple = ()
    if problem:
        sql += " AND problem = ?"
        args = (problem,)
    elif scope is not None:
        sql += " AND problem LIKE ?"
        args = (scope,)
    row = conn.execute(sql, args).fetchone()
    return row is not None and int(row["c"]) == 0


# ---------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------

def insert_strategy(conn: sqlite3.Connection, *, goal_id: int,
                    lean_path: str, created_by: str,
                    proposal_md: str = "", scratch_path: str = "") -> int:
    """Insert a new strategy. `lean_path` is the parent goal's target;
    `scratch_path` is this strategy's standalone patch module path.
    `scratch_path` may be left empty here and UPDATE'd via
    `update_strategy_scratch_path` once the sid is known and paths
    derived from it have been computed."""
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at)"
        " VALUES (?, ?, ?, 'proposed', ?, ?, ?)",
        (goal_id, lean_path, scratch_path, proposal_md, created_by, now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_strategy_scratch_path(conn: sqlite3.Connection, strategy_id: int,
                                 scratch_path: str) -> None:
    conn.execute(
        "UPDATE strategies SET scratch_path = ? WHERE id = ?",
        (scratch_path, strategy_id),
    )
    conn.commit()


def mark_other_strategies_superseded(conn: sqlite3.Connection, *,
                                     goal_id: int, winner_id: int) -> int:
    """When one strategy wins Verify, mark all other live strategies of
    the same goal as 'superseded'. Returns the number of strategies
    affected. In-flight workers on those strategies' sub-goals will
    cascade as no-op once goal is proved.

    Iterates per-row through `update_strategy_status` so the inject-
    outcome propagation hook fires for each superseded strategy — a
    bulk UPDATE would silently skip the per-row hook and leave any
    associated Inject(Backward/Builder) decisions un-resolved.
    """
    rows = conn.execute(
        "SELECT id FROM strategies"
        " WHERE goal_id = ? AND id != ? AND status = 'proposed'",
        (goal_id, winner_id),
    ).fetchall()
    for r in rows:
        update_strategy_status(conn, int(r["id"]), "superseded")
    return len(rows)


def link_subgoal(conn: sqlite3.Connection, *, strategy_id: int,
                 subgoal_id: int, position: int) -> None:
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, ?)",
        (strategy_id, subgoal_id, position),
    )
    conn.commit()


def update_strategy_status(conn: sqlite3.Connection, strategy_id: int,
                           status: str) -> None:
    conn.execute(
        "UPDATE strategies SET status = ? WHERE id = ?",
        (status, strategy_id),
    )
    conn.commit()
    # When a strategy reaches a terminal status, propagate the outcome
    # back to any Inject(Backward/Builder) decision that produced it
    # and fire the batch-done Strategist wake-up if its batch is now
    # fully resolved. Mirrors the goal-side handling in
    # `_set_goal_terminal_and_propagate`. No-op for non-terminal
    # transitions and for strategies not tied to an Inject decision.
    if status in ("succeeded", "dead", "superseded"):
        d = propagate_inject_outcome_from_strategy(conn, strategy_id)
        if d is not None:
            maybe_enqueue_inject_batch_done(conn, d)
    elif status == "stalled":
        # 'stalled' is terminal-for-propagation but a PARKED state, not a
        # completion. Fill the producing Inject's outcome so the in-flight-
        # batch clause stops suppressing T4 — but do NOT fire
        # inject_batch_done. Whether a parked collapse warrants a Strategist
        # wake is T4's call (`is_problem_stalled`): if sibling Injects left
        # alive alternatives the problem is not stalled and no wake is
        # owed; if nothing is alive T4 fires. Unconditionally waking here
        # (as 'dead'/'succeeded' do) re-plans work the prior Strategist run
        # already pivoted on — the duplicate-wake this status was added to
        # kill. Reopen of a subgoal flips the strategy back to 'proposed'.
        propagate_inject_outcome_from_strategy(conn, strategy_id)


def maybe_enqueue_inject_batch_done(conn: sqlite3.Connection,
                                    decision_id: int) -> None:
    """If `decision_id` belongs to an Inject batch (batch_id non-NULL)
    AND every sibling row in the batch now has `outcome` filled, fire
    a single 'inject_batch_done' Strategist trigger on this problem.

    Idempotent via the queue dedup inside the helper: a duplicate
    Strategist trigger for the same root is silently dropped. Solo
    Inject (batch_id NULL) is a no-op.

    Lives in db.py (not dispatcher.py) so that
    `update_strategy_status` can call it without a backward import
    when wiring strategy-terminal propagation; dispatcher.py
    re-exports under its previous private name for tests that
    referenced it.
    """
    row = conn.execute(
        "SELECT batch_id, problem FROM strategist_decisions WHERE id = ?",
        (decision_id,),
    ).fetchone()
    if row is None or row["batch_id"] is None:
        return
    batch_id = str(row["batch_id"])
    problem = str(row["problem"])
    pending = conn.execute(
        "SELECT COUNT(*) AS n FROM strategist_decisions"
        " WHERE batch_id = ? AND outcome IS NULL",
        (batch_id,),
    ).fetchone()
    if int(pending["n"]) > 0:
        return
    root_row = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND origin = 'root'",
        (problem,),
    ).fetchone()
    if root_row is None:
        return
    root_id = str(root_row["id"])
    if is_in_queue(conn, target_id=root_id, kind="Strategist"):
        return
    # Priority 20 — same band as T2 pending_review; batch completion is
    # an event-driven follow-up that supersedes routine T1 wall-clock.
    enqueue(conn, kind="Strategist", target_id=root_id,
            target_kind="Goal", priority=20)


def reconcile_settled_inject_outcomes(
    conn: sqlite3.Connection, *, scope: str | None = None,
) -> int:
    """Resolve NULL-outcome Inject batch decisions whose produced work has
    SETTLED, so a permanently-NULL outcome can no longer suppress the T4
    stall trigger (`problems_stalled`) or block `inject_batch_done`.

    Complements `null_inject_redispatch_specs` (worker DIED with no
    artifact → re-dispatch): this is the opposite case — the work exists
    and has settled, only the outcome propagation never fired. Settled,
    by inject kind:

      * Forward (no `produced_strategy_id`): `produced_goal_id` reached a
        HARD-terminal goal status (proved / disproved / dead — `shelved`
        is reopenable, does NOT settle) but goal-side propagation never
        ran (the transition predated the hook or took a path that
        bypassed it) → re-run `propagate_inject_outcome_from_goal`.
      * Backward / Builder: `produced_strategy_id` reached a terminal
        strategy status → re-run `propagate_inject_outcome_from_strategy`;
        OR the strategy is still 'proposed' yet has ≥1 subgoal and ZERO
        alive ones (all proved / shelved — the canonical DEADLOCK: a
        SOFT-shelved subgoal kept the strategy 'proposed', but
        `produced_goal_id`=target only terminates at problem end, so the
        NULL outcome suppressed T4 → permanent wedge).

        BACKSTOP role (Phase 11): the PRIMARY path now flips such a parent
        strategy to its terminal status at shelve-time
        (`_maybe_stall_parent_strategies`), so this branch rarely fires.
        When it does (a soft-shelve site that bypassed the hook), drive the
        strategy terminal via `update_strategy_status`: 'succeeded' iff every
        subgoal proved (a missed verify) → wakes to assemble; else 'stalled'
        (≥1 soft-shelved, reopenable) → fills the outcome WITHOUT waking.
        A parked-collapse wake is T4's call (`is_problem_stalled`), NOT an
        unconditional `inject_batch_done` — waking here re-plans work a prior
        Strategist run already pivoted on (the duplicate-wake the 'stalled'
        status was introduced to kill). The strategy stays reopenable: a
        subgoal Reopen flips 'stalled' → 'proposed'.

    Fires `maybe_enqueue_inject_batch_done` only via `update_strategy_status`
    for genuine completions ('succeeded'/'superseded'/'dead'); 'stalled'
    fills the outcome silently. Returns the count resolved. Idempotent
    (every fill is `outcome IS NULL`-guarded). In-flight safe: a 'proposed'
    strategy with any alive subgoal is genuinely in flight and left
    untouched."""
    sql = (
        "SELECT sd.id, sd.produced_goal_id, sd.produced_strategy_id,"
        "       g.status AS goal_status, s.status AS strat_status"
        " FROM strategist_decisions sd"
        " LEFT JOIN goals g ON g.id = sd.produced_goal_id"
        " LEFT JOIN strategies s ON s.id = sd.produced_strategy_id"
        " WHERE sd.decision_kind = 'Inject' AND sd.batch_id IS NOT NULL"
        "   AND sd.outcome IS NULL"
    )
    args: tuple = ()
    if scope is not None:
        sql += " AND sd.problem LIKE ?"
        args = (scope,)
    rows = list(conn.execute(sql, args))
    resolved = 0
    for r in rows:
        did = int(r["id"])
        sid = r["produced_strategy_id"]
        filled: int | None = None
        if sid is not None:
            sstat = (str(r["strat_status"])
                     if r["strat_status"] is not None else None)
            if sstat in ("succeeded", "superseded", "dead"):
                filled = propagate_inject_outcome_from_strategy(
                    conn, int(sid))
            elif sstat == "proposed":
                sub = conn.execute(
                    "SELECT g2.status AS st, COUNT(*) AS n"
                    " FROM strategy_subgoals ss"
                    " JOIN goals g2 ON g2.id = ss.subgoal_id"
                    " WHERE ss.strategy_id = ? GROUP BY g2.status",
                    (int(sid),),
                ).fetchall()
                comp = {str(x["st"]): int(x["n"]) for x in sub}
                total = sum(comp.values())
                alive = (comp.get("open", 0) + comp.get("attempting", 0)
                         + comp.get("pending_strategist_review", 0))
                if total > 0 and alive == 0:
                    # BACKSTOP only: the primary path flips the parent
                    # strategy to its terminal status at shelve-time
                    # (`_maybe_stall_parent_strategies`). If a soft-shelve
                    # site was missed, drive the strategy terminal here so
                    # status + inject outcome stay consistent. 'succeeded'
                    # (all proved — a missed verify) wakes to assemble;
                    # 'stalled' (>=1 soft-shelved, reopenable) fills the
                    # outcome WITHOUT waking — the parked-collapse wake is
                    # T4's call, not an unconditional inject_batch_done.
                    # update_strategy_status performs both the propagation
                    # and the (success-only) batch-done enqueue.
                    new_status = ("succeeded"
                                  if comp.get("proved", 0) == total
                                  else "stalled")
                    update_strategy_status(conn, int(sid), new_status)
                    resolved += 1
                    continue
        elif r["produced_goal_id"] is not None and \
                str(r["goal_status"]) in ("proved", "disproved", "dead"):
            # `shelved` intentionally excluded — reopenable/parked, not a
            # settled inject (see propagate_inject_outcome_from_goal). The
            # stall predicate's active-check governs T4 suppression instead.
            filled = propagate_inject_outcome_from_goal(
                conn, int(r["produced_goal_id"]))
        if filled is not None:
            maybe_enqueue_inject_batch_done(conn, filled)
            resolved += 1
    if resolved:
        print(f"[reconcile] resolved {resolved} settled NULL-outcome "
              f"Inject decision(s)", flush=True)
    return resolved


def delete_strategy(conn: sqlite3.Connection, strategy_id: int) -> None:
    """Remove a strategy row outright.

    #101 — When a pipeline fails before the agent did any real work
    (quota_exhausted / spawn_fast_fail / missing_dep / gateway_unreachable
    / transient_timeout), the strategy row is an empty shell: no
    proposal_md, no scratch_path, no strategy_subgoals link. Marking it
    `dead` would leave forensic noise (the SG run accumulated 8587 such
    rows). Delete instead — the row never reflected real agent output.

    Caller guarantees no `strategy_subgoals` rows exist (FK is enforced
    by PRAGMA foreign_keys=ON; infra failures occur before
    `_backward_parse_and_commit` would `link_subgoal`). dead_attempts
    has no FK to strategies, so historical dead_attempts referencing
    a deleted strategy_id stay readable."""
    conn.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
    conn.commit()


def strategies_ready_for_verify(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Strategies whose all sub-goals are proved AND whose own parent goal
    is still alive (not already proved by a sibling strategy). The
    parent-alive check prevents Verify thrashing when an OR sibling has
    already won the goal — without it bfs_refill keeps re-enqueueing
    the doomed Verify forever.

    A 0-subgoal strategy (Phase 6.5 Backward leaf-bypass — agent wrote a
    complete proof in patch.lean with no decomposition) is also ready:
    the NOT EXISTS clause is vacuously true when no strategy_subgoals
    rows exist for that strategy.
    """
    return list(conn.execute(
        "SELECT s.* FROM strategies s "
        "JOIN goals g ON g.id = s.goal_id "
        "WHERE s.status = 'proposed' "
        "  AND g.status NOT IN ('proved','shelved') "
        "  AND s.scratch_path != '' "
        "  AND NOT EXISTS ("
        "    SELECT 1 FROM strategy_subgoals ss"
        "    JOIN goals sg ON sg.id = ss.subgoal_id"
        "    WHERE ss.strategy_id = s.id AND sg.status != 'proved'"
        "  )"
        # Deterministic order so per-goal Verify serialization (the
        # per-goal-bfs cap in bfs_refill) picks the same sibling on
        # each tick — without this, sqlite's natural rowid order is
        # nominal but documented-as-undefined.
        " ORDER BY s.id"
    ))


# ---------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------

def record_pipeline(conn: sqlite3.Connection, *, pipeline_id: str, kind: str,
                    target_id: str, target_kind: str, status: str,
                    outcome: str, started_at: str) -> None:
    """INSERT a finished pipeline row. Status is 'succeeded' or 'failed' only.

    Live state ('this daemon has a worker on target X') is held in
    dispatcher's in-memory _running set, never persisted to DB.
    """
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pipeline_id, kind, target_id, target_kind, status, outcome,
         started_at, now()),
    )
    conn.commit()


def is_in_queue(conn: sqlite3.Connection, *, target_id: str,
                kind: str) -> bool:
    """True if a (target_id, kind) row exists in queue. Live-pipeline check
    lives in dispatcher's in-memory _running set, not DB."""
    row = conn.execute(
        "SELECT 1 FROM queue WHERE target_id = ? AND kind = ? LIMIT 1",
        (target_id, kind),
    ).fetchone()
    return row is not None


def queue_count(conn: sqlite3.Connection, *, target_id: str, kind: str) -> int:
    """Count queue entries matching (target_id, kind). Used by OR-parallel
    dispatch to enforce per-goal Backward fanout."""
    row = conn.execute(
        "SELECT count(*) AS n FROM queue WHERE target_id = ? AND kind = ?",
        (target_id, kind),
    ).fetchone()
    return int(row["n"])


def queue_size(conn: sqlite3.Connection) -> int:
    """Total queue rows. Non-destructive (unlike pop_queue)."""
    row = conn.execute("SELECT count(*) AS n FROM queue").fetchone()
    return int(row["n"])


# ---------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------

def enqueue(conn: sqlite3.Connection, *, kind: str, target_id: str,
            priority: int = 0, target_kind: str = "Goal",
            decision_id: int | None = None) -> None:
    """Insert a dispatch queue entry.

    Phase 2 — `target_kind` defaults to 'Goal' (matches every pre-Phase 2
    caller). Forward callers pass `target_kind='Problem'` with
    `target_id=problem_name`. `decision_id` is non-None only when the
    queue entry was emitted by a Strategist Inject decision — the
    spawned pipeline pulls the brief from `strategist_decisions.brief`
    via this FK at cold-start (see `compile_context`).
    """
    conn.execute(
        "INSERT INTO queue (kind, target_id, target_kind, priority,"
        " decision_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (kind, target_id, target_kind, priority, decision_id, now()),
    )
    conn.commit()


def pop_queue(conn: sqlite3.Connection) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT * FROM queue ORDER BY priority DESC, id ASC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM queue WHERE id = ?", (row["id"],))
    conn.commit()
    return row


def flush_queue_kind(conn: sqlite3.Connection, *, kind: str) -> int:
    """Drop every queued entry of `kind`. Returns rows deleted.

    Used when a per-kind cooldown engages (e.g. quota_exhausted) so
    the dispatcher's pop loop doesn't drain the pre-cooldown backlog
    against an exhausted provider. bfs_refill repopulates after the
    cooldown clears."""
    cur = conn.execute("DELETE FROM queue WHERE kind = ?", (kind,))
    conn.commit()
    return cur.rowcount or 0


def queue_contains(conn: sqlite3.Connection, *, kind: str,
                   target_id: str) -> bool:
    """True iff a queue entry of `kind` for `target_id` is pending.

    The dispatcher's pop loop dedups only against the in-flight `running`
    set; it does NOT dedup two queued rows against each other (and a row
    popped while a same-key job runs is silently dropped). The Librarian
    re-enqueue path calls this before enqueueing so a chain step is never
    queued twice for one problem."""
    row = conn.execute(
        "SELECT 1 FROM queue WHERE kind = ? AND target_id = ? LIMIT 1",
        (kind, target_id),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------
# Dead attempt helpers
# ---------------------------------------------------------------------

def record_dead_attempt(conn: sqlite3.Connection, *, target_id: int,
                        target_kind: str, pipeline_id: str,
                        failure_reason: str, failure_detail: str = "",
                        proposal_md: str = "",
                        artifacts: str = "") -> None:
    """Record a failed pipeline. `artifacts` is a JSON dict {filename: text}
    capturing all agent output files for forensic review (since the
    .attempts/<pid>/ filesystem dir is rmtree'd at pipeline end)."""
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, failure_detail, proposal_md, artifacts, ts)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (target_id, target_kind, pipeline_id, failure_reason,
         failure_detail, proposal_md, artifacts, now()),
    )
    conn.commit()


def recent_dead_attempts(conn: sqlite3.Connection, *, target_id: int,
                         target_kind: str, k: int = 5) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM dead_attempts WHERE target_id = ? AND target_kind = ?"
        " ORDER BY id DESC LIMIT ?",
        (target_id, target_kind, k),
    ))


# ---------------------------------------------------------------------
# library_decls — Librarian per-declaration state (plan §7)
# ---------------------------------------------------------------------

def upsert_library_decl(conn: sqlite3.Connection, *, problem: str,
                        slug: str, source_goal_id: int | None) -> int:
    """Insert a candidate library_decl, or return the existing row's id.
    Idempotent on (problem, slug) so re-running Step 0 inventory / dedup
    is safe (re-entrancy, plan §8). Does not reset verdict/lifecycle on
    an existing row — later work-kind setters advance those."""
    ts = now()
    conn.execute(
        "INSERT INTO library_decls (problem, slug, source_goal_id,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(problem, slug) DO NOTHING",
        (problem, slug, source_goal_id, ts, ts),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM library_decls WHERE problem = ? AND slug = ?",
        (problem, slug),
    ).fetchone()
    return int(row["id"])


def set_library_verdict(conn: sqlite3.Connection, *, problem: str,
                        slug: str, verdict: str,
                        citation: str | None = None) -> None:
    """dedup work: record a verdict + optional citation, advance to
    'deduped' (or terminal 'dropped'/'cited' when the verdict is final).
    Verdict→lifecycle: keep→deduped, cite-mathlib/cite-library→cited,
    drop/merge→dropped."""
    lifecycle = {
        "keep": "deduped",
        "cite-mathlib": "cited",
        "cite-library": "cited",
        "drop": "dropped",
        "merge": "dropped",
    }.get(verdict, "deduped")
    conn.execute(
        "UPDATE library_decls SET verdict = ?, citation = ?,"
        " lifecycle = ?, updated_at = ? WHERE problem = ? AND slug = ?",
        (verdict, citation, lifecycle, now(), problem, slug),
    )
    conn.commit()


def set_library_classification(conn: sqlite3.Connection, *, problem: str,
                               slug: str, target_file: str,
                               target_name: str | None,
                               file_order: int) -> None:
    """classify work: record file placement + in-file order, advance a
    'deduped' (keep) decl to 'classified'. No-op on already-terminal
    (dropped/cited) rows."""
    conn.execute(
        "UPDATE library_decls SET target_file = ?, target_name = ?,"
        " file_order = ?, lifecycle = 'classified', updated_at = ?"
        " WHERE problem = ? AND slug = ? AND lifecycle = 'deduped'",
        (target_file, target_name, file_order, now(), problem, slug),
    )
    conn.commit()


def mark_library_migrated(conn: sqlite3.Connection, *, problem: str,
                          slug: str, target_name: str | None = None) -> None:
    """migrate work: a 'classified' decl was reshaped into its Library
    file and passed Gate A + build. Advance to terminal 'migrated'.

    `target_name` backfills the migrated Library declaration's fully-
    qualified name — classify wrote it NULL because the Library decl name
    isn't known until the migrate patch exists. `COALESCE` keeps any
    existing value when called without one, so no caller regresses a name
    already recorded."""
    conn.execute(
        "UPDATE library_decls SET lifecycle = 'migrated',"
        " target_name = COALESCE(?, target_name), updated_at = ?"
        " WHERE problem = ? AND slug = ? AND lifecycle = 'classified'",
        (target_name, now(), problem, slug),
    )
    conn.commit()


def mark_library_cleaned(conn: sqlite3.Connection, *, problem: str,
                         slug: str) -> None:
    """cleanup work (Step 4): a 'migrated' decl was reshaped to PR-ready form
    (unused hyps removed, variables factored, docstring) and passed the
    re-gate. Advance to terminal 'cleaned'."""
    conn.execute(
        "UPDATE library_decls SET lifecycle = 'cleaned', updated_at = ?"
        " WHERE problem = ? AND slug = ? AND lifecycle = 'migrated'",
        (now(), problem, slug),
    )
    conn.commit()


def set_library_renamed(conn: sqlite3.Connection, *, problem: str,
                        slug: str, old_fqn: str, new_fqn: str) -> None:
    """cleanup work (Step 4, P4 rename): a kept decl was renamed to a mathlib-
    aligned name. Record the new fqn in `target_name` (INDEX harvest + Gate B
    re-derivation use it) and the ORIGINAL fqn in `renamed_from` so consumer
    files self-apply `{old → new}` via deferred-rewire when their turn comes.

    `renamed_from` uses COALESCE: a decl renamed more than once across re-cleans
    keeps its FIRST (pre-cleanup) fqn, so the consumer rewrite chain stays
    anchored to the name consumers actually wrote. Lifecycle is untouched — the
    decl survives; `mark_library_cleaned` advances it separately."""
    conn.execute(
        "UPDATE library_decls SET target_name = ?,"
        " renamed_from = COALESCE(renamed_from, ?), updated_at = ?"
        " WHERE problem = ? AND slug = ?",
        (new_fqn, old_fqn, now(), problem, slug),
    )
    conn.commit()


# ---------------------------------------------------------------------
# librarian_fail_counts — persistent Librarian chain retry cap (#92, B#3)
# ---------------------------------------------------------------------

def librarian_fail_counts_all(conn: sqlite3.Connection) -> "dict[str, int]":
    """The whole persisted per-unit fail tally — loaded into the dispatcher's
    in-memory dict at daemon startup so the chain retry cap survives a restart
    (a genuinely-stuck unit STALLs instead of looping forever across restarts)."""
    return {r["target_id"]: r["n"] for r in conn.execute(
        "SELECT target_id, n FROM librarian_fail_counts")}


def set_librarian_fail_count(conn: sqlite3.Connection, *, target_id: str,
                             n: int) -> None:
    """Write-through a unit's fail count (upsert) when the in-memory dict is
    bumped."""
    ts = now()
    conn.execute(
        "INSERT INTO librarian_fail_counts (target_id, n, updated_at)"
        " VALUES (?, ?, ?) ON CONFLICT(target_id) DO UPDATE SET"
        " n = excluded.n, updated_at = excluded.updated_at",
        (target_id, n, ts),
    )
    conn.commit()


def clear_librarian_fail_count(conn: sqlite3.Connection, *,
                               target_id: str) -> None:
    """Drop a unit's fail count on success (mirrors the in-memory pop)."""
    conn.execute("DELETE FROM librarian_fail_counts WHERE target_id = ?",
                 (target_id,))
    conn.commit()


def library_decls_for(conn: sqlite3.Connection, problem: str,
                      *, lifecycle: str | None = None) -> list[sqlite3.Row]:
    """All library_decls for a problem, optionally filtered to one
    lifecycle state. Ordered by file_order then id for stable display."""
    if lifecycle is None:
        return list(conn.execute(
            "SELECT * FROM library_decls WHERE problem = ?"
            " ORDER BY file_order IS NULL, file_order, id",
            (problem,),
        ))
    return list(conn.execute(
        "SELECT * FROM library_decls WHERE problem = ? AND lifecycle = ?"
        " ORDER BY file_order IS NULL, file_order, id",
        (problem, lifecycle),
    ))
