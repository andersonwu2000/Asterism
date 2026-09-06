"""One revision's judge verdict, read on demand.

Its own module and not a slice of `timeline.py`: the Programme cluster
there is tangled with the groups tree (see this package's header), and
this read touches none of it — a row id, the verdict JSON, and the
adversary parser that owns the verdict's shape.
"""
from __future__ import annotations

import json
import sqlite3


def programme_verdict(conn: sqlite3.Connection, problem: str,
                      rev_id: int) -> "dict | None":
    """ONE revision's judge verdict, read on demand.

    Not a field on the Programme read and not a column on the Timeline
    poll: union_closed's last 100 revisions carry 152 KB of verdict and
    the Timeline polls every 15s. The row already on screen names the
    revision; this answers the question a reader asks about ONE of them.

    Everything here is new material as of 2026-08-29 (judge calibration
    survey, knives 0+1): a rejected row used to hard-code verdict=NULL,
    which destroyed 89 final verdicts and left the one row a reader most
    wants to open — the proposal that was killed — with nothing to open;
    and a `clear` used to be allowed as the bare word on most of the
    criteria, so "why did this pass" had no answer on the record.

    The criteria are read through `adversary.split_criterion`, the
    parser's own splitter — a criterion takes a LIST now, and a private
    copy of that reading in the serve layer is the drift that made every
    rebut report as `passed` for a week (44ff4321)."""
    try:
        row = conn.execute(
            "SELECT * FROM programme_revisions WHERE id = ? AND"
            " problem = ?", (int(rev_id), problem)).fetchone()
    except sqlite3.OperationalError:
        return None  # pre-v30 DB
    if row is None:
        return None
    cols = set(row.keys())

    def _col(name: str):
        return row[name] if name in cols else None

    from ...pipeline.adversary import (
        CRITERIA_KEYS, criteria_names, split_criterion)
    v: "dict" = {}
    try:
        v = json.loads(_col("verdict") or "{}") or {}
    except (TypeError, ValueError):
        v = {}
    if not isinstance(v, dict):
        v = {}
    names = criteria_names()
    raw = v.get("criteria")
    criteria = []
    if isinstance(raw, dict):
        # the rubric's order, not the JSON's — a judge that emits its
        # keys out of order must not reorder the rubric on the page
        for k in CRITERIA_KEYS:
            if k not in raw:
                continue
            state, bullets = split_criterion(raw[k])
            criteria.append({"key": k, "name": names.get(k),
                             "state": state, "bullets": bullets})
    stamp = {"model": _col("judge_model"),
             "provider": _col("judge_provider"),
             "effort": _col("judge_effort"),
             "rubric_sha": _col("rubric_sha")}
    return {
        "rev": int(row["rev"]),
        "status": str(row["status"]),
        "rounds": int(row["rounds"]),
        "created_at": str(row["created_at"]),
        "ruling": v.get("verdict") if isinstance(v.get("verdict"), str)
        else None,
        "criteria": criteria,
        "criticisms": [str(x) for x in (v.get("criticisms") or [])],
        "reservations": [str(x) for x in (v.get("reservations") or [])],
        # NULL on every verdict written before the stamp landed
        # (2026-08-28) — the console says "not recorded" rather than
        # inventing a seat
        "judge": stamp if any(stamp.values()) else None,
        "discard_reason": _col("discard_reason"),
        "discard_channel": _col("discard_channel"),
    }
