"""Multi-Problem Strategist round-robin (P7 C51).

Per phase7_smarts.md task 6 and architecture_pipelines.md §5:
  - `K_strategist` is a GLOBAL accumulator over `pipeline_finished` events
    (default P×2, P=4 → K=8). Once K events have happened since the last
    Strategist commit, the next Problem in strict A→B→C→A rotation is
    eligible.
  - Cooldown is GLOBAL non-overlapping: only one Strategist instance is
    in flight at any moment. The cooldown is released after that
    instance's commit lands (i.e. its strategist_decisions row appears).
  - Round-robin order is the alphabetical sort of `problems` table when
    no rotation state exists; afterwards the LAST chosen Problem rotates
    to the back.

State persistence:
  - Stored in a tiny `strategist_state` row (key/value pair table).
  - Two keys:
      'last_problem'      — slug of the most recently selected Problem.
      'finished_count_at' — finished_at timestamp of the most recent
                            counted pipeline. `_finished_count_since`
                            counts rows with finished_at > marker, which
                            zeroes the K accumulator after each consume.

Public API:
    select_next(conn, problems, K=8, cooldown_active=None) -> str | None

`problems` is the caller-supplied ordered list of Problem names (caller
typically pulls from the `problems` table or `META.md scan`). Returning
None means K is not yet reached or cooldown is active.

`cooldown_active` accepts a callable returning bool; if omitted the
function infers cooldown by looking for a Strategist pipeline row with
status='running' (single-instance enforcement at the runtime level).
"""
from __future__ import annotations

import sqlite3
from typing import Callable


_DEFAULT_K = 8


# ---------------------------------------------------------------------------
# Lazy schema bootstrap (key/value table)
# ---------------------------------------------------------------------------

_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS strategist_state (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _ensure_state_table(conn: sqlite3.Connection) -> None:
    conn.execute(_BOOTSTRAP_SQL)


def _read_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM strategist_state WHERE key = ?", (key,)
    ).fetchone()
    return row[0] if row else None


def _write_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO strategist_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ---------------------------------------------------------------------------
# Cooldown helpers
# ---------------------------------------------------------------------------


def is_strategist_running(conn: sqlite3.Connection) -> bool:
    """Cooldown predicate: any in-flight Strategist pipeline row?"""
    row = conn.execute(
        "SELECT COUNT(*) FROM pipelines "
        "WHERE kind = 'Strategist' AND status = 'running'"
    ).fetchone()
    return bool(row[0])


def _finished_count_since(conn: sqlite3.Connection, marker_ts: str) -> int:
    """Count non-Strategist pipelines that finished strictly after `marker_ts`.

    Empty marker counts ALL finished rows (initial bootstrap). Strategist-
    kind rows are excluded (counting our own commits would create a self-
    trigger feedback loop).
    """
    if marker_ts:
        row = conn.execute(
            "SELECT COUNT(*) FROM pipelines "
            "WHERE finished_at IS NOT NULL AND finished_at > ? "
            "  AND kind != 'Strategist'",
            (marker_ts,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM pipelines "
            "WHERE finished_at IS NOT NULL AND kind != 'Strategist'"
        ).fetchone()
    return row[0]


def _max_finished_at(conn: sqlite3.Connection) -> str:
    """Most recent finished_at across all non-Strategist pipelines.

    Empty string when no rows exist (zero state).
    """
    row = conn.execute(
        "SELECT MAX(finished_at) FROM pipelines "
        "WHERE finished_at IS NOT NULL AND kind != 'Strategist'"
    ).fetchone()
    return row[0] or ""


# ---------------------------------------------------------------------------
# Public selection
# ---------------------------------------------------------------------------


def select_next(
    conn: sqlite3.Connection,
    problems: list[str],
    *,
    K: int = _DEFAULT_K,
    cooldown_active: Callable[[], bool] | None = None,
) -> str | None:
    """Pick the next Problem to run Strategist on.

    Returns the Problem name, or None if K events haven't accumulated or
    the cooldown is active.

    Caller is responsible for actually invoking Strategist with the
    returned Problem name; `consume(conn, problem)` should be called
    AFTER the Strategist commit so the K counter resets.
    """
    if not problems:
        return None

    _ensure_state_table(conn)

    if cooldown_active is None:
        cooldown_active = lambda: is_strategist_running(conn)
    if cooldown_active():
        return None

    marker = _read_state(conn, "finished_count_at") or ""
    if _finished_count_since(conn, marker) < K:
        return None

    last_problem = _read_state(conn, "last_problem")
    if last_problem is None or last_problem not in problems:
        # Fresh start (or last_problem was removed) → first in the list.
        return problems[0]
    idx = problems.index(last_problem)
    return problems[(idx + 1) % len(problems)]


def consume(conn: sqlite3.Connection, problem: str) -> None:
    """Mark `problem` as the most-recently selected and reset the K counter.

    Call after Strategist's commit step so the next select_next() picks
    the next Problem in rotation.
    """
    _ensure_state_table(conn)
    _write_state(conn, "last_problem", problem)
    _write_state(conn, "finished_count_at", _max_finished_at(conn))
