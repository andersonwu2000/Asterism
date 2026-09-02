from __future__ import annotations

import sqlite3

from .core import now, scope_sql


# ---------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------

def record_pipeline_start(conn: sqlite3.Connection, *, pipeline_id: str,
                          kind: str, target_id: str,
                          target_kind: str) -> None:
    """INSERT the pipeline row at DISPATCH time with status='running'
    (v38). Existing for the whole pipeline lifetime is what satisfies the
    `dead_attempts.pipeline_id` FK, so forensic rows can be written
    EAGERLY — 1:1 with each `goals.attempts` increment — instead of
    buffered until a normal worker return (the buffer died with the stack
    frame on a worker exception, leaving increments with no evidence).
    `finish_pipeline` sets the terminal status; a daemon crash leaves the
    row 'running' and `recovery.recover_at_startup` finalizes it."""
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES (?, ?, ?, ?, 'running', NULL, ?, NULL)",
        (pipeline_id, kind, target_id, target_kind, now()),
    )
    conn.commit()


def finish_pipeline(conn: sqlite3.Connection, *, pipeline_id: str,
                    status: str, outcome: str) -> None:
    """UPDATE the dispatch-time 'running' row to its terminal status
    ('succeeded' / 'failed') + outcome + finished_at. Raises when the row
    is missing: a finish without a `record_pipeline_start` is a dispatch
    bug — failing loud here beats silently resurrecting the pre-v38
    INSERT-at-completion shape."""
    cur = conn.execute(
        "UPDATE pipelines SET status = ?, outcome = ?, finished_at = ?"
        " WHERE id = ?",
        (status, outcome, now(), pipeline_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise RuntimeError(
            f"finish_pipeline: no pipelines row for {pipeline_id!r} — "
            f"record_pipeline_start was never called for this dispatch")


def is_in_queue(conn: sqlite3.Connection, *, target_id: str,
                kind: str) -> bool:
    """True if a (target_id, kind) row exists in queue — LEASED ROWS COUNT
    (v17): a claimed-but-unfinished unit must still read as "in queue" or
    every refill-side dedup re-enqueues a duplicate while it runs. Same-
    process live-pipeline check additionally lives in dispatcher's
    in-memory _running set."""
    # Empty-problem rows are POISON (2026-08-03 stall): a scoped pop can
    # never dispatch them, so counting them here turns one bad row into
    # a permanent T1/T4 suppression for its target. A poison row must
    # not read as "in queue".
    row = conn.execute(
        "SELECT 1 FROM queue WHERE target_id = ? AND kind = ?"
        " AND problem IS NOT NULL AND problem != '' LIMIT 1",
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


def strict_ancestor_slugs(conn: sqlite3.Connection,
                          goal_id: int) -> "dict[str, str]":
    """`{slug: lean_path}` for every STRICT ancestor of `goal_id` — the
    same walk as `strict_ancestor_ids`, with the names the editing
    tools and the commit gate both match against (one home, 2026-08-30)."""
    ids = strict_ancestor_ids(conn, goal_id)
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT slug, lean_path FROM goals WHERE id IN ({marks})",
        tuple(ids)).fetchall()
    return {r["slug"]: r["lean_path"] for r in rows}


def descendant_ids(conn: sqlite3.Connection, goal_id: int) -> "set[int]":
    """Goal ids of every STRICT descendant of `goal_id` via the
    strategy_subgoals graph — the mirror of `strict_ancestor_ids`. A
    "line" for the routine audit (2026-08-30) is a dispatched root plus
    this set; the tallies the auditor rules on are counted over it."""
    rows = conn.execute(
        "WITH RECURSIVE kids(id) AS ("
        "  SELECT ss.subgoal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    WHERE s.goal_id = ?"
        "  UNION"
        "  SELECT ss.subgoal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    JOIN kids k ON k.id = s.goal_id"
        ") "
        "SELECT id FROM kids",
        (goal_id,),
    ).fetchall()
    return {int(r["id"]) for r in rows} - {int(goal_id)}


def strict_ancestor_ids(conn: sqlite3.Connection,
                        goal_id: int) -> "set[int]":
    """Goal ids of every STRICT ancestor of `goal_id` via the
    strategy_subgoals graph. ONE home (2026-08-26): backward's
    ancestor-link guard and validate's parity cycle mirror both call
    this, so "citation ok" and "commit rejects the circularity" can
    never disagree about what an ancestor is."""
    rows = conn.execute(
        "WITH RECURSIVE ancestors(id) AS ("
        "  SELECT s.goal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    WHERE ss.subgoal_id = ?"
        "  UNION"
        "  SELECT s.goal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    JOIN ancestors a ON a.id = ss.subgoal_id"
        ") "
        "SELECT id FROM ancestors",
        (goal_id,),
    ).fetchall()
    return {int(r["id"]) for r in rows} - {int(goal_id)}


def queue_size(conn: sqlite3.Connection, *,
               scope: "str | None" = None,
               claimable_only: bool = False,
               kinds: "tuple[str, ...] | None" = None) -> int:
    """Queue row count, optionally scoped / unleased-only / kind-set
    (the RAM ledger's yield path asks it "is an NL wake actually
    waiting" — the queued-wakes RESERVE it once sized is retired,
    owner ruling 2026-08-26: demand observed beats demand forecast).
    Non-destructive —
    the dispatcher's `--once` empty check uses `claimable_only=True`
    instead of a probing pop (the old pop-to-test-emptiness silently
    discarded a row when every popped row had been skipped)."""
    q = "SELECT count(*) AS n FROM queue WHERE 1=1"
    args: list = []
    _scope_sql, _scope_args = scope_sql(scope)   # pattern OR explicit list
    if _scope_sql:
        q += f" AND {_scope_sql}"
        args.extend(_scope_args)
    if claimable_only:
        q += " AND owner_pid IS NULL"
    if kinds is not None:
        q += " AND kind IN (" + ",".join("?" for _ in kinds) + ")"
        args.extend(kinds)
    row = conn.execute(q, args).fetchone()
    return int(row["n"])


