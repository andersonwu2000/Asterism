"""failure_replay stage (P3 C22).

Reads dead_attempts from DB for the given target. Backward calls with
target_kind='Goal'; Builder calls with target_kind='Strategy'. The K_digest
cap (default 5) bounds how many summaries land in agent prompts to keep
them tractable.

Spec impl §6.1:

    SELECT reason_summary, ts FROM dead_attempts
    WHERE target_id = ? AND target_kind = ?
    ORDER BY ts DESC LIMIT ?    -- ? = K_digest

Public API:
    failure_replay(conn, target_id, target_kind, k_digest=5) -> list[dict]

Returns the K_digest most recent dead_attempts for `(target_id, target_kind)`,
each as a dict with keys `reason`, `outcome`, `ts`. Empty list if no failures
recorded yet.
"""
from __future__ import annotations

import sqlite3

DEFAULT_K_DIGEST: int = 5


def failure_replay(
    conn: sqlite3.Connection,
    target_id: int | str,
    target_kind: str,
    k_digest: int = DEFAULT_K_DIGEST,
) -> list[dict]:
    if target_kind not in ("Goal", "Strategy"):
        raise ValueError(
            f"unknown target_kind: {target_kind!r}; valid: 'Goal' | 'Strategy'."
        )
    rows = conn.execute(
        "SELECT reason_summary, outcome, ts FROM dead_attempts "
        "WHERE target_id = ? AND target_kind = ? "
        "ORDER BY ts DESC LIMIT ?",
        (str(target_id), target_kind, k_digest),
    ).fetchall()
    return [{"reason": r[0], "outcome": r[1], "ts": r[2]} for r in rows]
