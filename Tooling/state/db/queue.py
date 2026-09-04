from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from .core import now, scope_sql


# ---------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------

#: The band a PERSON's dispatch takes (human_interface_design §3.2). NOT a
#: fast lane: 2 is the ordinary BFS band, so a human request "只進佇列、
#: 不插隊" (owner ruling 2026-09-02) — it neither outranks the goals BFS
#: already queued nor sinks below them, while a machine-authored Inject at
#: 10 is the framework promoting its own next experiment.
#:
#: One home rather than two: the commit path stamps it when the command is
#: applied, and the recovery / reconcile helpers that revive a lost queue
#: row restore the SAME band — a request re-banded by the very pass that
#: rescued it is a silent reordering nobody would look for.
HUMAN_PRIORITY = 2


def enqueue(conn: sqlite3.Connection, *, kind: str, target_id: str,
            problem: str,
            priority: int = 0, target_kind: str = "Goal",
            decision_id: int | None = None,
            payload: "dict | None" = None) -> None:
    """Insert a dispatch queue entry.

    Phase 2 — `target_kind` defaults to 'Goal' (matches every pre-Phase 2
    caller). Forward callers pass `target_kind='Problem'` with
    `target_id=problem_name`. `decision_id` is non-None only when the
    queue entry was emitted by a Strategist Inject decision — the
    spawned pipeline pulls the brief from `strategist_decisions.brief`
    via this FK at cold-start (see `compile_context`).

    v17 — `problem` is REQUIRED (scope-safe pop/flush/recovery keys on
    it); `payload` is optional structured per-row data (JSON-encoded
    here): librarian per-file units pass `{"file": <rel path>}` with a
    plain `target_id=problem` instead of the retired \\x1f smuggle.
    """
    import json as _json
    conn.execute(
        "INSERT INTO queue (kind, target_id, target_kind, priority,"
        " decision_id, problem, payload, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (kind, target_id, target_kind, priority, decision_id, problem,
         _json.dumps(payload) if payload else None, now()),
    )
    conn.commit()


def pop_queue(conn: sqlite3.Connection, *, scope: "str | None" = None,
              lease_owner: "int | None" = None,
              exclude_kinds: "tuple[str, ...] | None" = None,
              ) -> sqlite3.Row | None:
    """CLAIM the highest-priority unleased row (v17 lease semantics).

    The row is NOT deleted: it gets `owner_pid`+`leased_at` stamped and
    stays visible to every in-queue check (`is_in_queue`/`queue_contains`
    count leased rows — a claimed-but-unfinished unit must still read as
    "in queue" or refill re-enqueues a duplicate). The dispatcher deletes
    it via `complete_queue_row` when the pipeline finishes (or when a
    pop-loop skip discards it); a crashed owner's lease is released by
    `release_expired_leases` (dead PID or TTL).

    `scope` filters to one problem's rows (None = all rows — an unscoped
    daemon still pops everything; concurrent double-dispatch is prevented
    by the lease, not by scope). `exclude_kinds` leaves rows of those
    kinds unclaimed (NL-first startup: Lean kinds wait out the gateway
    warm without losing their queue position). BEGIN IMMEDIATE makes
    the select+claim atomic across processes (WAL single-writer)."""
    owner = lease_owner if lease_owner is not None else os.getpid()
    excl_sql = ""
    excl_params: "tuple[str, ...]" = ()
    if exclude_kinds:
        excl_sql = (" AND kind NOT IN ("
                    + ",".join("?" * len(exclude_kinds)) + ")")
        excl_params = tuple(exclude_kinds)
    conn.execute("BEGIN IMMEDIATE")
    try:
        # `scope` is a LIKE pattern or an explicit list — one
        # translation, `db.scope_sql` (core.py).
        _scope_sql, _scope_args = scope_sql(scope)
        row = conn.execute(
            "SELECT * FROM queue WHERE owner_pid IS NULL"
            + (f" AND {_scope_sql}" if _scope_sql else "")
            + excl_sql +
            " ORDER BY priority DESC, id ASC LIMIT 1",
            (*_scope_args, *excl_params)).fetchone()
        if row is None:
            conn.commit()
            return None
        conn.execute(
            "UPDATE queue SET owner_pid = ?, leased_at = ? WHERE id = ?",
            (owner, now(), row["id"]))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return row


def complete_queue_row(conn: sqlite3.Connection, row_id: int) -> None:
    """Release a claimed queue row for good — the unit finished (any
    outcome; refill re-derives retries) or the pop loop discarded it."""
    conn.execute("DELETE FROM queue WHERE id = ?", (row_id,))
    conn.commit()


def unclaim_queue_row(conn: sqlite3.Connection, row_id: int) -> None:
    """Put a popped row BACK — "not yet", not "never".

    The pop loop's other skips all `complete_queue_row` (delete), on the
    reasoning that refill re-derives whatever still needs doing. A
    per-target cooldown is different in kind: the work is still wanted
    and the only thing wrong is the clock, so deleting it would depend
    on refill re-deriving a row that a retry path — not refill — put
    there. Releasing the lease keeps the row exactly where it was and
    lets the next tick claim it once the cooldown has passed."""
    conn.execute(
        "UPDATE queue SET owner_pid = NULL, leased_at = NULL WHERE id = ?",
        (row_id,))
    conn.commit()


def release_own_leases(conn: sqlite3.Connection, *,
                       owner_pid: "int | None" = None) -> int:
    """Graceful-shutdown lease sweep: release every queue lease held by
    THIS process. An in-flight worker killed at a daemon exit
    (`_exit_pool_fast` on the ingested/budget paths) leaves its claimed
    row leased to a dead PID — harmless to correctness (the next run's
    `release_expired_leases` reclaims it) but visible as a phantom
    running unit to DB readers (frontend joint test, 2026-07-07). Rows
    are released, not deleted — the next run re-pops them."""
    owner = owner_pid if owner_pid is not None else os.getpid()
    cur = conn.execute(
        "UPDATE queue SET owner_pid = NULL, leased_at = NULL"
        " WHERE owner_pid = ?", (owner,))
    conn.commit()
    return cur.rowcount


def release_expired_leases(conn: sqlite3.Connection, *,
                           scope: "str | None" = None,
                           ttl_sec: float,
                           pid_alive) -> int:
    """Un-claim leased rows whose owner is provably gone: the owner PID is
    dead OR the lease is older than `ttl_sec` (double guard — Windows
    reuses PIDs, so liveness alone can false-positive a recycled PID as
    'still ours'). Released rows become claimable again; returns count."""
    released = 0
    _scope_sql, _scope_args = scope_sql(scope)
    rows = list(conn.execute(
        "SELECT id, owner_pid, leased_at FROM queue"
        " WHERE owner_pid IS NOT NULL"
        + (f" AND {_scope_sql}" if _scope_sql else ""),
        _scope_args))
    for r in rows:
        expired = False
        try:
            stamp = datetime.fromisoformat(str(r["leased_at"]))
            if stamp.tzinfo is None:      # defensive: naive stamp -> UTC
                stamp = stamp.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - stamp).total_seconds()
            expired = age > ttl_sec
        except (TypeError, ValueError):
            expired = True         # unparseable lease stamp -> reclaim
        if expired or not pid_alive(r["owner_pid"]):
            conn.execute(
                "UPDATE queue SET owner_pid = NULL, leased_at = NULL"
                " WHERE id = ?", (r["id"],))
            released += 1
    if released:
        conn.commit()
    return released


def flush_queue_kind(conn: sqlite3.Connection, *, kind: str,
                     scope: "str | None" = None) -> int:
    """Drop every UNLEASED queued entry of `kind` (leased rows are
    in-flight in some dispatcher — yanking them would orphan the lease
    bookkeeping; their pipelines are already running regardless).
    Returns rows deleted.

    Used when a per-kind cooldown engages (e.g. quota_exhausted) so
    the dispatcher's pop loop doesn't drain the pre-cooldown backlog
    against an exhausted provider. bfs_refill repopulates after the
    cooldown clears. `scope` keeps a scoped daemon's cooldown from
    flushing a concurrent daemon's backlog (the #74 class)."""
    _scope_sql, _scope_args = scope_sql(scope)
    cur = conn.execute(
        "DELETE FROM queue WHERE kind = ? AND owner_pid IS NULL"
        + (f" AND {_scope_sql}" if _scope_sql else ""),
        (kind, *_scope_args))
    conn.commit()
    return cur.rowcount or 0


def queue_contains(conn: sqlite3.Connection, *, kind: str,
                   target_id: str,
                   payload_file: "str | None" = None,
                   no_payload: bool = False) -> bool:
    """True iff a queue entry of `kind` for `target_id` is pending — leased
    rows count (see `is_in_queue`).

    The dispatcher's pop loop dedups only against the in-flight `running`
    set; it does NOT dedup two queued rows against each other (and a row
    popped while a same-key job runs is silently dropped). The Librarian
    re-enqueue path calls this before enqueueing so a chain step is never
    queued twice for one problem. `payload_file` narrows the match to a
    per-file unit (v17: the file rides `payload` JSON, not target_id);
    `no_payload=True` matches only PLAIN rows — the serial-phase dedup
    must not mistake a queued per-file unit (same target_id since v17)
    for its own serial row."""
    if payload_file is not None:
        row = conn.execute(
            "SELECT 1 FROM queue WHERE kind = ? AND target_id = ?"
            " AND json_extract(payload, '$.file') = ? LIMIT 1",
            (kind, target_id, payload_file),
        ).fetchone()
    elif no_payload:
        row = conn.execute(
            "SELECT 1 FROM queue WHERE kind = ? AND target_id = ?"
            " AND payload IS NULL LIMIT 1",
            (kind, target_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM queue WHERE kind = ? AND target_id = ? LIMIT 1",
            (kind, target_id),
        ).fetchone()
    return row is not None


