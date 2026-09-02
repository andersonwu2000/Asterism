"""The operator bench (`problems.benched`, v47) — its read and its
write in ONE module.

Bench takes a problem off the live path WITHOUT touching its state:
no refill dispatch, no Strategist seat, every goal / revision / last
word kept (owner ruling 2026-08-31 — the hopeless ones stop running,
they are not reset). Split out of `problems.py` 2026-09-03 when the
flag gained a writer: the CLI (`asterism bench`) and the console's
per-task control must flip it the same way, and a second spelling of
"UPDATE problems SET benched" is exactly how the two surfaces would
drift.
"""
from __future__ import annotations

import sqlite3


def problem_benched(conn: sqlite3.Connection, problem: str) -> bool:
    """Operator bench flag (2026-08-31): True = no dispatch, no seats."""
    row = conn.execute("SELECT benched FROM problems WHERE name = ?",
                       (problem,)).fetchone()
    return bool(row and row[0])


def set_benched(conn: sqlite3.Connection, problem: str, *,
                benched: bool) -> "int | None":
    """Flip the bench flag. Returns how many queued rows were flushed
    (0 when unbenching), or None when the problem is unknown — every
    caller answers "no such problem" and none of them may invent one.

    Benching flushes the problem's UNLEASED queue rows so nothing
    already enqueued fires; a LEASED row is in-flight work and finishes
    on its own (bench stops the next dispatch, it does not kill a
    worker). Idempotent in both directions.
    """
    if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                    (problem,)).fetchone() is None:
        return None
    conn.execute("UPDATE problems SET benched = ? WHERE name = ?",
                 (1 if benched else 0, problem))
    flushed = 0
    if benched:
        flushed = conn.execute(
            "DELETE FROM queue WHERE problem = ? AND owner_pid IS NULL",
            (problem,)).rowcount
    conn.commit()
    return int(flushed)
