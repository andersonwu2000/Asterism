"""The Programme's decided history, and one revision's whole debate
(human_interface_design.md §1.4-2, third bullet: "提供 Programme 定案歷史
和各定案下的辯論歷史").

Its own module and not a slice of `timeline.py` for the reason
`verdict.py` is: the Programme cluster there is tangled with the groups
tree, and this reads nothing of it beyond which group a chain belongs
to. It is also read ON DEMAND — a debate carries every round's draft,
which is kilobytes per round, and nothing may put that on a poll.

`programme()` already answers "what is the standing argument"; this
answers the two questions a reader asks NEXT — what came before it, and
how each of those was argued. The list carries no body and no dialogue
for the same reason the Programme's own history does not: a list is
read to choose a row.
"""
from __future__ import annotations

import json
import sqlite3

from .timeline import _group_clause, _top_group_id


def _judge_stamp(row: sqlite3.Row, cols: "set[str]") -> "dict | None":
    """Which seat judged this revision — None when the row predates the
    stamp (2026-08-28). The console says "not recorded" rather than
    inventing one."""
    stamp = {k: (row[f"judge_{k}"] if f"judge_{k}" in cols else None)
             for k in ("model", "provider", "effort")}
    stamp["rubric_sha"] = row["rubric_sha"] if "rubric_sha" in cols else None
    return stamp if any(stamp.values()) else None


def _col(row: sqlite3.Row, cols: "set[str]", name: str):
    return row[name] if name in cols else None


def programme_revisions(conn: sqlite3.Connection, problem: str,
                        group_id: "int | None" = None,
                        limit: int = 200) -> "list[dict]":
    """One group's decided chain, newest first.

    `group_id` defaults to the TOP group — the argument a problem-level
    read means. Chains never interleave (v35): every group numbers its
    revisions from 1, so a problem-wide list would present one
    argument's rev 2 as the successor of another's rev 1.
    """
    if group_id is None:
        group_id = _top_group_id(conn, problem)
    clause, args = _group_clause(group_id)
    try:
        rows = conn.execute(
            "SELECT * FROM programme_revisions WHERE problem = ?" + clause +
            " ORDER BY id DESC LIMIT ?",
            (problem,) + args + (int(limit),)).fetchall()
    except sqlite3.OperationalError:
        return []  # pre-v30 DB
    out: "list[dict]" = []
    for r in rows:
        cols = set(r.keys())
        out.append({
            "id": int(r["id"]),
            "rev": int(r["rev"]),
            "status": str(r["status"]),
            "rounds": int(r["rounds"]),
            "created_at": str(r["created_at"]),
            "group_id": (None if _col(r, cols, "group_id") is None
                         else int(r["group_id"])),
            # WHY it was dropped: prose for the reader (v34) and the
            # machine-readable channel beside it (v37)
            "discard_reason": _col(r, cols, "discard_reason"),
            "discard_channel": _col(r, cols, "discard_channel"),
            "judge": _judge_stamp(r, cols),
        })
    return out


def _rounds(raw: "str | None") -> "list[dict]":
    """The stored dialogue as ROUNDS the page can lay out.

    One stored turn is the judge's, and it carries the body it was fired
    at (`pipeline/strategist/wake.py`): that pairing IS the round — what
    the author put on the table, and what came back at it. Splitting it
    into two records here would ask the page to re-pair them.

    Tolerant: a row whose dialogue is missing, truncated or not a list
    reads as no rounds. A debate nobody can render is still a revision
    a reader may open.
    """
    try:
        turns = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(turns, list):
        return []
    from ...pipeline.adversary import CRITERIA_KEYS, criteria_names, split_criterion
    names = criteria_names()
    out: "list[dict]" = []
    for t in turns:
        if not isinstance(t, dict):
            continue
        v = t.get("verdict") if isinstance(t.get("verdict"), dict) else {}
        raw_criteria = v.get("criteria")
        criteria: "list[dict]" = []
        if isinstance(raw_criteria, dict):
            # the rubric's order, not the JSON's (same law as the final
            # verdict read: a judge that emits its keys out of order
            # must not reorder the rubric on the page)
            for k in CRITERIA_KEYS:
                if k not in raw_criteria:
                    continue
                state, bullets = split_criterion(raw_criteria[k])
                criteria.append({"key": k, "name": names.get(k),
                                 "state": state, "bullets": bullets})
        out.append({
            "round": t.get("round") if isinstance(t.get("round"), int)
            else None,
            # the draft this round argued about — the strategist's half
            "proposal": (str(t["proposal"]) if isinstance(t.get("proposal"),
                                                          str) else None),
            "criticisms": [str(c) for c in (t.get("criticisms") or [])],
            "ruling": v.get("verdict") if isinstance(v.get("verdict"), str)
            else None,
            "criteria": criteria,
            "reservations": [str(x) for x in (v.get("reservations") or [])],
        })
    return out


def programme_revision(conn: sqlite3.Connection, problem: str,
                       rev_id: int) -> "dict | None":
    """One revision: the body that was decided, the debate that got
    there, and the verdict that closed it.

    Keyed by the ROW id, not by `rev`: a rejected proposal and the
    revision that later takes its number are two rows with one number.
    The closing verdict is `verdict.programme_verdict` verbatim — one
    reading of a verdict in this codebase, never two.
    """
    try:
        row = conn.execute(
            "SELECT * FROM programme_revisions WHERE id = ? AND problem = ?",
            (int(rev_id), problem)).fetchone()
    except sqlite3.OperationalError:
        return None  # pre-v30 DB
    if row is None:
        return None
    cols = set(row.keys())
    from .verdict import programme_verdict
    return {
        "id": int(row["id"]),
        "rev": int(row["rev"]),
        "status": str(row["status"]),
        "rounds": int(row["rounds"]),
        "created_at": str(row["created_at"]),
        "group_id": (None if _col(row, cols, "group_id") is None
                     else int(row["group_id"])),
        "body": str(row["body"]),
        "discard_reason": _col(row, cols, "discard_reason"),
        "discard_channel": _col(row, cols, "discard_channel"),
        # the author's own note after a discard (2026-08-30) — its
        # record, unverified, and the page must say so
        "last_words": _col(row, cols, "last_words"),
        "judge": _judge_stamp(row, cols),
        "dialogue": _rounds(_col(row, cols, "dialogue")),
        "verdict": programme_verdict(conn, problem, int(rev_id)),
    }
