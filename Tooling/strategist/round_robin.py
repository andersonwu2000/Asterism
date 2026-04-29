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
from datetime import datetime, timedelta, timezone
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


_DEFAULT_STRATEGIST_STALE_SEC = 4 * 60 * 60  # 4h
# A real Strategist running on opus with M_strategist=5 decisions can take
# 30+ min for the agent stage alone; the original 600s cutoff would mark it
# stale mid-run and break single-instance cooldown.


def _stale_sec() -> int:
    """Stale cutoff for strategist running rows.

    R3 round 2 fix (audit2_c49_c50_c51.md M_R2-1): the original 600s const
    was too short for opus latency. Now 4h default with env override:
        STRATEGIST_STALE_SEC=<int>   override stale threshold (seconds)
    """
    import os
    raw = os.environ.get("STRATEGIST_STALE_SEC")
    if raw:
        try:
            v = int(raw)
            if v > 0:
                return v
        except ValueError:
            pass
    return _DEFAULT_STRATEGIST_STALE_SEC


def _now_iso(now: datetime | None = None) -> str:
    """Wall-clock now with ASTERISM_NOW override (test_hooks.md).

    R3 round 2 fix (audit2_c49_c50_c51.md M_R2-4): is_strategist_running was
    using datetime.now() directly, which ignored the ASTERISM_NOW env hook
    other parts of the framework honor. Now goes through _now_iso() so
    deterministic tests can pin time across the stale-running boundary.
    """
    if now is not None:
        return now.isoformat()
    import os
    raw = os.environ.get("ASTERISM_NOW")
    if raw:
        return raw
    return datetime.now(timezone.utc).isoformat()


def is_strategist_running(conn: sqlite3.Connection) -> bool:
    """Cooldown predicate: any RECENT in-flight Strategist pipeline row?

    R3 fix (audit_c49_c50_c51.md M3 + audit2 M_R2-1 / M_R2-4): formerly
    counted ANY status='running' Strategist row, which left the cooldown
    stuck forever after a crash. Now uses an env-tunable stale threshold
    (default 4h) and honors ASTERISM_NOW for deterministic tests.
    """
    now_str = _now_iso()
    try:
        now_dt = datetime.fromisoformat(now_str)
    except ValueError:
        now_dt = datetime.now(timezone.utc)
    cutoff = (now_dt - timedelta(seconds=_stale_sec())).isoformat()
    row = conn.execute(
        "SELECT COUNT(*) FROM pipelines "
        "WHERE kind = 'Strategist' AND status = 'running' "
        "  AND started_at >= ?",
        (cutoff,),
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
