"""failure_replay stage (P3 C22).

Reads dead_attempts from DB for the given target. Backward calls with
target_kind='Goal'; Builder calls with target_kind='Strategy'; P7 Forward
will call with target_kind='forward'. The K_digest cap (default 5) bounds
how many summaries land in agent prompts to keep them tractable.

Spec impl §6.1 字面為:

    SELECT reason_summary, ts FROM dead_attempts
    WHERE target_id = ? AND target_kind = ?
    ORDER BY ts DESC LIMIT ?    -- ? = K_digest

P2 C14 起為了 agent prompt 多帶 outcome 字串而 SELECT 擴成
`SELECT reason_summary, outcome, ts`；C22 移到此 stage 模組保留同 deviation。
Filter / ORDER / LIMIT 子句完全對齊 §6.1，只多選 outcome 欄位給 prompt 用。

target_kind valid set 對齊 schema_v1.sql CHECK constraint:
    {'Goal', 'Strategy', 'forward'}.
P7 進入 strategist / generalizer 時若 schema CHECK 擴 → 同步擴此 set.

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
    if target_kind not in ("Goal", "Strategy", "forward"):
        raise ValueError(
            f"unknown target_kind: {target_kind!r}; "
            "valid: 'Goal' | 'Strategy' | 'forward' (per schema_v1 CHECK)."
        )
    rows = conn.execute(
        "SELECT reason_summary, outcome, ts FROM dead_attempts "
        "WHERE target_id = ? AND target_kind = ? "
        "ORDER BY ts DESC LIMIT ?",
        (str(target_id), target_kind, k_digest),
    ).fetchall()
    return [{"reason": r[0], "outcome": r[1], "ts": r[2]} for r in rows]
