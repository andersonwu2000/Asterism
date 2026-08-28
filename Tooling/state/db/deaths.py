from __future__ import annotations

import sqlite3

from .core import now


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
    cur = conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, failure_detail, proposal_md, artifacts, ts)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (target_id, target_kind, pipeline_id, failure_reason,
         failure_detail, proposal_md, artifacts, now()),
    )
    conn.commit()
    # Live KB antipattern capture from this failure (Phase 12). The single
    # chokepoint all failure paths flow through, so a new failure site captures
    # automatically. Best-effort + lazy import (kb_ingest imports db) — a KB
    # hiccup must never break failure recording.
    try:
        from .. import kb_ingest
        if kb_ingest.capture_dead_attempt(
                conn, da_id=int(cur.lastrowid), target_id=target_id,
                target_kind=target_kind, reason=failure_reason,
                detail=failure_detail, proposal_md=proposal_md):
            conn.commit()
    except Exception:  # noqa: BLE001
        pass


def recent_dead_attempts(conn: sqlite3.Connection, *, target_id: int,
                         target_kind: str, k: int = 5) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM dead_attempts WHERE target_id = ? AND target_kind = ?"
        " ORDER BY id DESC LIMIT ?",
        (target_id, target_kind, k),
    ))


