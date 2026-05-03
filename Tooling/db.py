"""DB schema + connection. Single source of truth.

Tables (see docs/architecture.md §4):
  problems, goals, strategies, strategy_subgoals,
  pipelines, dead_attempts, queue
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
    manifest_path  TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem     TEXT    NOT NULL REFERENCES problems(name),
    slug        TEXT    NOT NULL,
    lean_path   TEXT    NOT NULL UNIQUE,
    statement   TEXT    NOT NULL,
    difficulty  INTEGER NOT NULL DEFAULT 4,
    -- kind / origin enums kept minimal; extend when implementing
    -- forward / generalizer / refuter / construction (architecture.md §12).
    kind        TEXT    NOT NULL DEFAULT 'theorem'
                    CHECK(kind IN ('theorem')),
    origin      TEXT    NOT NULL
                    CHECK(origin IN ('root','backward')),
    status      TEXT    NOT NULL
                    CHECK(status IN ('open','attempting','proved','shelved')),
    depth       INTEGER NOT NULL DEFAULT 0,
    attempts    INTEGER NOT NULL DEFAULT 0,
    -- F33 — claude CLI session UUID for same-session Builder retry.
    -- Set on first Builder dispatch; reused on retry via `claude --resume`;
    -- cleared on timeout (rc=124), stale-session fallback (rc=125), or
    -- when Builder threshold reached (next dispatch is Backward).
    builder_session_id TEXT NULL DEFAULT NULL,
    -- F53 — same idea as builder_session_id but for Backward retries.
    -- A Backward dispatch that fails lake_build_error preserves the
    -- session so the next Backward dispatch on the same goal can
    -- `--resume` with the lake stderr inlined and edit one file
    -- instead of cold-restarting from Context.md.
    backward_session_id TEXT NULL DEFAULT NULL,
    -- F42 — when this goal is an alias (its lean file's proof body
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
CREATE TABLE IF NOT EXISTS pipelines (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL CHECK(kind IN ('Builder','Backward','Verify')),
    target_id   TEXT NOT NULL,
    target_kind TEXT NOT NULL CHECK(target_kind IN ('Goal','Strategy')),
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

CREATE TABLE IF NOT EXISTS queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL CHECK(kind IN ('Builder','Backward','Verify')),
    target_id   TEXT NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC, id ASC);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    # P1-#6: lift busy-timeout from sqlite3's 5s default to 30s.
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
    # F33 — additive migration for older DBs created before
    # builder_session_id existed in the goals table. CREATE TABLE IF
    # NOT EXISTS is a no-op when the table is already present, so a
    # blind ALTER TABLE is needed to backfill the column. Idempotent
    # via "duplicate column name" detection.
    for col, ddl in (
        ("builder_session_id",  # F33
         "ALTER TABLE goals ADD COLUMN builder_session_id TEXT NULL"
         " DEFAULT NULL"),
        ("alias_target_id",     # F42
         "ALTER TABLE goals ADD COLUMN alias_target_id INTEGER NULL"
         " DEFAULT NULL REFERENCES goals(id)"),
        ("backward_session_id", # F53
         "ALTER TABLE goals ADD COLUMN backward_session_id TEXT NULL"
         " DEFAULT NULL"),
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    conn.commit()


# ---------------------------------------------------------------------
# Goal helpers
# ---------------------------------------------------------------------

def insert_goal(conn: sqlite3.Connection, *, problem: str, slug: str,
                lean_path: str, statement: str, origin: str,
                difficulty: int = 4, depth: int = 0,
                kind: str = 'theorem') -> int:
    ts = now()
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement, difficulty,"
        " kind, origin, status, depth, attempts, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, 0, ?, ?)",
        (problem, slug, lean_path, statement, difficulty,
         kind, origin, depth, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_goal(conn: sqlite3.Connection, goal_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM goals WHERE id = ?", (goal_id,)
    ).fetchone()


def set_alias_target(conn: sqlite3.Connection, goal_id: int,
                     target_id: int) -> None:
    """F42 — record that `goal_id` is an alias whose proof delegates
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
    """F42 — return ids of every goal whose alias_target_id == target_id.
    Used by prune.is_retained to keep an orphan canonical alive while
    any live goal aliases to it."""
    return [int(r["id"]) for r in conn.execute(
        "SELECT id FROM goals WHERE alias_target_id = ?", (target_id,)
    ).fetchall()]


def update_goal_status(conn: sqlite3.Connection, goal_id: int,
                       status: str) -> None:
    conn.execute(
        "UPDATE goals SET status = ?, updated_at = ? WHERE id = ?",
        (status, now(), goal_id),
    )
    conn.commit()


def set_builder_session_id(conn: sqlite3.Connection, goal_id: int,
                           session_id: str | None) -> None:
    """F33 — record (or clear with None) the claude CLI session UUID
    for same-session Builder retry."""
    conn.execute(
        "UPDATE goals SET builder_session_id = ?, updated_at = ?"
        " WHERE id = ?",
        (session_id, now(), goal_id),
    )
    conn.commit()


def get_builder_session_id(conn: sqlite3.Connection,
                           goal_id: int) -> str | None:
    row = conn.execute(
        "SELECT builder_session_id FROM goals WHERE id = ?",
        (goal_id,),
    ).fetchone()
    if row is None:
        return None
    val = row["builder_session_id"]
    return str(val) if val else None


def set_backward_session_id(conn: sqlite3.Connection, goal_id: int,
                            session_id: str | None) -> None:
    """F53 — record (or clear with None) the claude CLI session UUID
    for same-session Backward retry."""
    conn.execute(
        "UPDATE goals SET backward_session_id = ?, updated_at = ?"
        " WHERE id = ?",
        (session_id, now(), goal_id),
    )
    conn.commit()


def get_backward_session_id(conn: sqlite3.Connection,
                            goal_id: int) -> str | None:
    row = conn.execute(
        "SELECT backward_session_id FROM goals WHERE id = ?",
        (goal_id,),
    ).fetchone()
    if row is None:
        return None
    val = row["backward_session_id"]
    return str(val) if val else None


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


def open_goals(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Open goals eligible for dispatch.

    Walks the strategy DAG from each root: a goal is 'reachable' iff
    every strategy on some ancestor chain back to a root is alive
    ('proposed' or 'succeeded'). Open goals not reachable this way are
    orphaned by an upstream supersede / dead and must NOT be dispatched.

    The recursive CTE handles arbitrary depth — fixing the prior bug
    where a depth-2 sub-goal of a 'proposed' strategy was kept alive
    even when that strategy's own goal was orphaned upstream.
    """
    return list(conn.execute(
        "WITH RECURSIVE alive(id) AS ("
        "    SELECT id FROM goals WHERE origin = 'root'"
        "    UNION"
        "    SELECT g.id FROM goals g"
        "    JOIN strategy_subgoals ss ON ss.subgoal_id = g.id"
        "    JOIN strategies s ON s.id = ss.strategy_id"
        "    JOIN alive a ON a.id = s.goal_id"
        "    WHERE s.status IN ('proposed','succeeded')"
        ") "
        "SELECT g.* FROM goals g "
        "WHERE g.status = 'open' AND g.id IN alive "
        "ORDER BY g.id"
    ))


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


def strategies_ready_for_verify(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Strategies whose all sub-goals are proved AND whose own parent goal
    is still alive (not already proved by a sibling strategy). The
    parent-alive check prevents Verify thrashing when an OR sibling has
    already won the goal — without it bfs_refill keeps re-enqueueing
    the doomed Verify forever.
    """
    return list(conn.execute(
        "SELECT s.* FROM strategies s "
        "JOIN goals g ON g.id = s.goal_id "
        "WHERE s.status = 'proposed' "
        "  AND g.status NOT IN ('proved','shelved') "
        "  AND NOT EXISTS ("
        "    SELECT 1 FROM strategy_subgoals ss"
        "    JOIN goals sg ON sg.id = ss.subgoal_id"
        "    WHERE ss.strategy_id = s.id AND sg.status != 'proved'"
        "  )"
        "  AND EXISTS ("
        "    SELECT 1 FROM strategy_subgoals ss WHERE ss.strategy_id = s.id"
        "  )"
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
            priority: int = 0) -> None:
    conn.execute(
        "INSERT INTO queue (kind, target_id, priority, created_at) VALUES (?, ?, ?, ?)",
        (kind, target_id, priority, now()),
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
