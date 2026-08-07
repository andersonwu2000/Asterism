"""RequestUserAmend resolution — the write chokepoint for the human's
answer to a Strategist amend request.

The Strategist's `RequestUserAmend` commit writes `.proposed_<file>`
next to the target and inserts a `strategist_decisions` row with
`outcome='awaiting_human'`, which pauses ALL dispatch on the problem
(`db.problem_has_awaiting_human`). Until this module existed the only
resolution path was the operator hand-editing the file and hand-updating
the row. `resolve_amend` is now the single mechanized path (used by the
serve API; the CLI can grow a wrapper when needed):

  accept — write the (possibly operator-edited) body to the real target
           file, delete `.proposed_<file>`, flip the row to 'accepted'.
  reject — delete `.proposed_<file>`, flip the row to 'rejected'; the
           reason rides `outcome_detail` so the Strategist's next wake
           sees WHY.

Either way the awaiting_human gate lifts and a Strategist wake is
enqueued (dedup) so the problem resumes on the next dispatcher tick
instead of waiting for T1/T4.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

from . import db

_ALLOWED_FILES = ("Defs.lean", "Manifest.md", "Root.lean")


def pending_amends(conn: sqlite3.Connection,
                   *, problem: str | None = None) -> list[dict]:
    """All unresolved RequestUserAmend rows, oldest first.

    Each entry: {id, problem, file, proposed_body, question, reason,
    created_at}. `reason` is the Strategist's row-level rationale;
    `question` is the specific ask carried in the payload.
    """
    q = ("SELECT id, problem, reason, payload, created_at"
         " FROM strategist_decisions"
         " WHERE decision_kind = 'RequestUserAmend'"
         "   AND outcome = 'awaiting_human'")
    params: tuple = ()
    if problem is not None:
        q += " AND problem = ?"
        params = (problem,)
    q += " ORDER BY id"
    out: list[dict] = []
    for row in conn.execute(q, params).fetchall():
        try:
            payload = json.loads(row["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        out.append({
            "id": int(row["id"]),
            "problem": str(row["problem"]),
            "file": str(payload.get("file", "")),
            "proposed_body": str(payload.get("proposed_body", "")),
            "question": str(payload.get("question", "")),
            "reason": str(row["reason"] or ""),
            "created_at": str(row["created_at"]),
        })
    return out


def _atomic_write(target: Path, body: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def resolve_amend(conn: sqlite3.Connection, workspace: Path,
                  decision_id: int, *, action: str,
                  body: str | None = None,
                  reason: str | None = None) -> dict:
    """Resolve one awaiting_human RequestUserAmend row.

    action='accept': write `body` (default: the proposed_body as the
    Strategist wrote it) to the target file; action='reject': leave the
    file untouched. Both remove `.proposed_<file>`, stamp the row
    (accepted/rejected + outcome_detail), and enqueue a Strategist wake.

    Raises ValueError on unknown id / already-resolved row / bad action.
    Returns {problem, file, action}.
    """
    if action not in ("accept", "reject"):
        raise ValueError(f"unknown action {action!r} (accept|reject)")
    row = conn.execute(
        "SELECT id, problem, decision_kind, outcome, payload"
        " FROM strategist_decisions WHERE id = ?",
        (decision_id,)).fetchone()
    if row is None:
        raise ValueError(f"no strategist_decisions row {decision_id}")
    if str(row["decision_kind"]) != "RequestUserAmend":
        raise ValueError(
            f"row {decision_id} is {row['decision_kind']!r}, "
            f"not RequestUserAmend")
    if str(row["outcome"] or "") != "awaiting_human":
        raise ValueError(
            f"row {decision_id} already resolved "
            f"(outcome={row['outcome']!r})")

    problem = str(row["problem"])
    payload = json.loads(row["payload"] or "{}")
    file = str(payload.get("file", ""))
    if file not in _ALLOWED_FILES:
        # Same whitelist the Strategist verify gate enforces at request
        # time; a row that violates it is corrupt, not resolvable.
        raise ValueError(f"row {decision_id} targets {file!r} "
                         f"(allowed: {_ALLOWED_FILES})")

    pdir = db.problem_dir(workspace, problem)
    if action == "accept":
        final_body = body if body is not None else str(
            payload.get("proposed_body", ""))
        if not final_body.strip():
            raise ValueError("accept with empty body")
        _atomic_write(pdir / file, final_body)
        # An accepted amendment IS the sanctioned user-file change — move
        # the baseline pin with it (task #120 class sweep: without this
        # row, `root_integrity_gate` would flag the amended file as
        # tampered after the re-prove). Recorded as source='repin' (the
        # schema's sanctioned-ack source; CHECK admits observed/repin).
        from . import manifest as _mfst
        conn.execute(
            "INSERT INTO user_file_history"
            " (problem, file, sha, body, seen_at, source)"
            " VALUES (?, ?, ?, ?, ?, 'repin')",
            (problem, file, _mfst._content_sha(final_body), final_body,
             db.now()))
        # Root.lean amendment changes the problem's canonical statement:
        # sync goals.statement (the CLAUDE.md file-table rule — "改 Root
        # statement 後重 init 或 sync goals.statement"). The root also
        # returns to 'frozen' (pre-launch): whatever proof state the OLD
        # claim had is moot for the new one.
        if file == "Root.lean":
            from ..core.cli import _extract_root_statement
            stmt = _extract_root_statement(final_body)
            if stmt:
                root_row = conn.execute(
                    "SELECT id FROM goals WHERE problem = ? AND"
                    " origin = 'root' LIMIT 1", (problem,)).fetchone()
                if root_row is not None:
                    conn.execute(
                        "UPDATE goals SET statement = ?, attempts = 0,"
                        " updated_at = ? WHERE id = ?",
                        (stmt, db.now(), int(root_row["id"])))
                    # Status via the chokepoint (transitions lint): also
                    # clears integrity_verified — a rewritten root's old
                    # probe pass is void.
                    db.update_goal_status(conn, int(root_row["id"]),
                                          "frozen", event="operator_amend",
                                          reason="root statement rewritten")

    (pdir / f".proposed_{file}").unlink(missing_ok=True)

    outcome = "accepted" if action == "accept" else "rejected"
    detail = (reason or "").strip() or f"{outcome} by operator"
    conn.execute(
        "UPDATE strategist_decisions"
        " SET outcome = ?, outcome_detail = ?, updated_at = ?"
        " WHERE id = ?",
        (outcome, detail, db.now(), decision_id))
    from . import transitions as _transitions
    _transitions.apply_problem_transition(
        conn, problem, "active", event="amend_resolved")

    # Resume the problem promptly (mirrors cli._rewake_strategist; the
    # awaiting_human gate is already lifted by the UPDATE above).
    if not db.is_in_queue(conn, target_id=problem, kind="Strategist"):
        db.enqueue(conn, kind="Strategist", target_id=problem,
                   target_kind="Problem", priority=20, problem=problem)
    conn.commit()
    return {"problem": problem, "file": file, "action": action}
