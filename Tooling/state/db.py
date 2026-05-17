"""DB schema + connection. Single source of truth.

Tables (see docs/architecture.md §4):
  problems, goals, strategies, strategy_subgoals,
  pipelines, dead_attempts, queue, strategist_decisions (Phase 2)

Schema version tracked via `PRAGMA user_version`:
  0 = pre-Phase 2 (everything before strategist_decisions)
  2 = Phase 2 (new tables/columns/CHECK extensions; see docs/phase2/)
"""
from __future__ import annotations

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
    -- Phase 2 — wall-clock timestamp of last Strategist commit. Drives T1
    -- trigger (routine ≥ `strategist.interval_min` since this).
    last_strategist_at TEXT NULL DEFAULT NULL
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
                    CHECK(kind IN ('theorem')),
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
    -- Split rule: failure_reason='agent_infeasible' → 'disproved';
    --             failure_reason='agent_shelved' → 'pending_strategist_review';
    --             failure_reason='parent_needs_fix' → 'shelved'.
    status      TEXT    NOT NULL
                    CHECK(status IN ('open','attempting','proved','shelved',
                                     'pending_strategist_review','disproved')),
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
                     CHECK(status IN ('proposed','succeeded','dead','superseded')),
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
                                   'Strategist','Forward')),
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
                                   'Strategist','Forward')),
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
-- 'awaiting_human', 'accepted', 'rejected', 'consumed').
CREATE TABLE IF NOT EXISTS strategist_decisions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    problem             TEXT NOT NULL REFERENCES problems(name),
    triggered_at_tick   INTEGER NOT NULL,
    trigger_kind        TEXT NOT NULL
                            CHECK(trigger_kind IN
                                  ('first_launch','pending_review','routine')),
    decision_kind       TEXT NOT NULL
                            CHECK(decision_kind IN
                                  ('Inject','ConfirmShelve','Reopen',
                                   'EmitDirective','InitializeDefs',
                                   'RequestUserAmend','Noop')),
    target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
    brief               TEXT NULL DEFAULT NULL,
    reason              TEXT NULL DEFAULT NULL,
    payload             TEXT NOT NULL DEFAULT '{}',
    outcome             TEXT NULL DEFAULT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC, id ASC);
CREATE INDEX IF NOT EXISTS idx_sd_problem ON strategist_decisions(problem);
CREATE INDEX IF NOT EXISTS idx_sd_outcome ON strategist_decisions(outcome);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # Additive migrations for older DBs (CREATE TABLE IF NOT EXISTS is
    # a no-op when the table already exists, so blind ALTER TABLE is
    # needed to backfill columns added in later versions). Idempotent
    # via "duplicate column name" detection.
    for col, ddl in (
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
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
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
    Phase 2 code (per `docs/internal/phase2_migration_plan.md §E`).
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


# ---------------------------------------------------------------------
# Goal helpers
# ---------------------------------------------------------------------

def insert_goal(conn: sqlite3.Connection, *, problem: str, slug: str,
                lean_path: str, statement: str, origin: str,
                depth: int = 0,
                kind: str = 'theorem',
                entry_kind: str = 'Builder') -> int:
    ts = now()
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts, entry_kind,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 'open', ?, 0, ?, ?, ?)",
        (problem, slug, lean_path, statement,
         kind, origin, depth, entry_kind, ts, ts),
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
    """Touch the timestamp Strategist's T1 trigger reads to compute
    `wall_clock_age >= interval_min`. Called on every Strategist commit
    regardless of decision_kind."""
    conn.execute(
        "UPDATE problems SET last_strategist_at = ? WHERE name = ?",
        (now(), problem),
    )
    conn.commit()


def problems_needing_t0(conn: sqlite3.Connection,
                        scope: str | None = None
                        ) -> list[tuple[str, int]]:
    """Return [(problem_name, root_goal_id)] for problems with
    `bootstrap_done=0`. Caller is responsible for the awaiting_human
    gate + in-flight Strategist dedup. Root goal id is computed via
    the standard `origin='root'` join."""
    sql = (
        "SELECT p.name, g.id AS root_id"
        " FROM problems p"
        " JOIN goals g ON g.problem = p.name AND g.origin = 'root'"
        " WHERE p.bootstrap_done = 0"
    )
    args: tuple = ()
    if scope is not None:
        sql += " AND p.name LIKE ?"
        args = (scope,)
    sql += " ORDER BY p.name"
    return [(r["name"], int(r["root_id"])) for r in conn.execute(sql, args)]


def problems_needing_t1(conn: sqlite3.Connection, *,
                        max_age_sec: float,
                        scope: str | None = None
                        ) -> list[tuple[str, int]]:
    """Return [(problem_name, root_goal_id)] for problems whose
    `last_strategist_at` is older than `max_age_sec` seconds (or NULL).
    Excludes problems whose root goal is already terminal (proved /
    shelved / disproved) since Strategist has nothing to do there.
    NULL last_strategist_at is treated as "ancient" (never strategist'd,
    eligible for T1 immediately)."""
    # SQLite julianday() yields fractional days; convert max_age_sec to
    # days for arithmetic. NULL last_strategist_at → coalesce to '1970'.
    max_age_days = max_age_sec / 86400.0
    sql = (
        "SELECT p.name, g.id AS root_id"
        " FROM problems p"
        " JOIN goals g ON g.problem = p.name AND g.origin = 'root'"
        " WHERE p.bootstrap_done = 1"
        "   AND g.status NOT IN ('proved','shelved','disproved')"
        "   AND ("
        "      p.last_strategist_at IS NULL"
        "      OR julianday('now') - julianday(p.last_strategist_at) > ?"
        "   )"
    )
    args: tuple = (max_age_days,)
    if scope is not None:
        sql += " AND p.name LIKE ?"
        args = (max_age_days, scope)
    sql += " ORDER BY p.name"
    return [(r["name"], int(r["root_id"])) for r in conn.execute(sql, args)]


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
        "WHERE g.status = 'open' AND g.id IN alive "
    )
    params: tuple = ()
    if scope is not None:
        sql += "AND g.problem LIKE ? "
        params = (scope,)
    sql += "ORDER BY g.id"
    return list(conn.execute(sql, params))


def root_proved(conn: sqlite3.Connection, problem: str | None = None) -> bool:
    sql = "SELECT count(*) AS c FROM goals WHERE origin = 'root' AND status != 'proved'"
    args: tuple = ()
    if problem:
        sql += " AND problem = ?"
        args = (problem,)
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
    cascade as no-op once goal is proved."""
    cur = conn.execute(
        "UPDATE strategies SET status = 'superseded'"
        " WHERE goal_id = ? AND id != ? AND status = 'proposed'",
        (goal_id, winner_id),
    )
    conn.commit()
    return int(cur.rowcount)


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
