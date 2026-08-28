"""Status chip — one derivation, shared by board() (this module) and
problem_detail() (edges.py): the same five inputs (awaiting-human,
sign-off-pending, bridged, ingested, structural stall) collapse to one
displayed word by one function, so the two surfaces cannot drift.

Split out of `data.py` 2026-08-28 (Phase B, B3) unchanged.
"""
from __future__ import annotations

import sqlite3

from ...state import db


# ---------------------------------------------------------------------
# Status chip — one derivation, shared by board and problem detail.
# Precedence: blocked-on-human first (red/yellow), then terminal states,
# then the structural stall signal, else proving.
# ---------------------------------------------------------------------

def _status_chip(*, awaiting: bool, signoff: bool, bridged: bool,
                 ingested: bool, stalled: bool) -> str:
    if awaiting:
        return "awaiting_human"
    if signoff:
        return "signoff_pending"
    if bridged:
        return "bridged"
    if ingested:
        return "ingested"
    if stalled:
        return "stalled"
    return "proving"


def _live_daemon_pid(daemon: "dict | None") -> "int | None":
    if daemon and daemon.get("running") and daemon.get("pid"):
        return int(daemon["pid"])
    return None


def _working(conn: sqlite3.Connection, daemon: "dict | None",
             name: str) -> bool:
    """True iff a live daemon is actually on this problem (scope LIKE
    match; empty scope = workspace-wide run)."""
    if _live_daemon_pid(daemon) is None:
        return False
    scope = daemon.get("scope") if daemon else None
    if not scope:
        return True
    row = conn.execute("SELECT ? LIKE ?", (name, scope)).fetchone()
    return bool(row and row[0])


def _refine_chip(chip: str, *, working: bool, scoped: bool,
                 progressed: bool, queued: int) -> str:
    """Presentation refinements shared by board() and problem_detail()
    — the two surfaces must agree.

    "proving" is an engine-liveness claim, not a DB-residue reading:
    without a live daemon scoped to this problem it degrades to
    "paused" (unfinished work remains) or "idle" (never launched).
    Within a live run, stalled+queued means the engine is between
    batches (the pending Strategist wake) — show proving, don't
    flicker red in the gap; a never-launched stalled problem (frozen
    root / zero goals) is idle, not stuck.
    """
    if chip in ("stalled", "proving") and working and scoped:
        # A live daemon scoped to THIS problem IS the work signal, even
        # before the first goal exists — a freshly-Run problem read
        # "idle" through the whole gateway warm-up (Test.Test3).
        return "proving"
    if chip == "stalled":
        if queued > 0:
            chip = "proving"
        elif not progressed:
            return "idle"
    if chip == "proving" and not working:
        return "paused" if progressed else "idle"
    return chip


def _awaiting_set(conn: sqlite3.Connection) -> set[str]:
    return {str(r[0]) for r in conn.execute(
        "SELECT DISTINCT problem FROM strategist_decisions"
        " WHERE outcome = 'awaiting_human'")}


def board(conn: sqlite3.Connection, *, daemon: "dict | None" = None) -> dict:
    """Campaign-board aggregation: one row per problem, batch queries
    (no per-problem N+1 except the shared stall predicate). `daemon` is
    the `daemon_status()` dict — status chips and in-flight counts are
    engine-liveness claims, so they must be gated on it (None = treat
    as not running)."""
    problems = conn.execute(
        "SELECT name, created_at, ingest_signoff_pending, ingested_at,"
        " library_bridged_at FROM problems ORDER BY name").fetchall()

    goal_counts: dict[str, dict[str, int]] = {}
    for r in conn.execute(
            "SELECT problem, status, COUNT(*) AS n FROM goals"
            " GROUP BY problem, status"):
        goal_counts.setdefault(str(r["problem"]), {})[str(r["status"])] = \
            int(r["n"])

    # Leases are only live work while their owner (the daemon) is the
    # running one — a dead owner's lease is residue awaiting reclaim,
    # not an agent (it rendered as "1 agent running now" for 8 days).
    inflight: dict[str, int] = {}
    live_pid = _live_daemon_pid(daemon)
    if live_pid is not None:
        for r in conn.execute(
                "SELECT problem, COUNT(*) AS n FROM queue"
                " WHERE owner_pid = ? GROUP BY problem", (live_pid,)):
            inflight[str(r["problem"])] = int(r["n"])
    queued: dict[str, int] = {}
    for r in conn.execute(
            "SELECT problem, COUNT(*) AS n FROM queue GROUP BY problem"):
        queued[str(r["problem"])] = int(r["n"])

    last_event: dict[str, str] = {}
    for r in conn.execute(
            "SELECT problem, MAX(updated_at) AS t FROM strategist_decisions"
            " GROUP BY problem"):
        if r["t"]:
            last_event[str(r["problem"])] = str(r["t"])
    for r in conn.execute(
            "SELECT problem, MAX(created_at) AS t FROM goals"
            " GROUP BY problem"):
        if r["t"] and str(r["t"]) > last_event.get(str(r["problem"]), ""):
            last_event[str(r["problem"])] = str(r["t"])

    awaiting = _awaiting_set(conn)
    stalled = set(db.problems_stalled(conn))

    rows = []
    for p in problems:
        name = str(p["name"])
        counts = goal_counts.get(name, {})
        chip = _status_chip(
            awaiting=name in awaiting,
            signoff=bool(p["ingest_signoff_pending"]),
            bridged=p["library_bridged_at"] is not None,
            ingested=p["ingested_at"] is not None,
            stalled=name in stalled,
        )
        progressed = any(counts.get(s, 0) for s in
                         ("open", "attempting", "proved", "shelved",
                          "pending_strategist_review"))
        chip = _refine_chip(
            chip, working=_working(conn, daemon, name),
            scoped=bool(daemon and daemon.get("scope")),
            progressed=progressed, queued=queued.get(name, 0))
        rows.append({
            "name": name,
            "status": chip,
            "goals": {
                "open": counts.get("open", 0) + counts.get("attempting", 0),
                "proved": counts.get("proved", 0),
                "shelved": counts.get("shelved", 0)
                + counts.get("pending_shelve_confirm", 0),
                "total": sum(counts.values()),
            },
            "in_flight": inflight.get(name, 0),
            "queued": queued.get(name, 0),
            "last_event": last_event.get(name),
            "created_at": str(p["created_at"]),
        })
    return {"problems": rows}
