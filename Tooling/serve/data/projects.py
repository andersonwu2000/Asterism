"""Project cards — the read behind `/api/projects` (HID §1.4).

The picker is the first screen the console opens, and a card has to
answer "is anything happening here, and does it want me?" without the
reader opening the shelf. So the three live numbers ride the same row
as the name: `running` (engine liveness), `attention` (blocked on a
human), `last_event` (when this shelf last moved).

Nothing is derived here that a predicate already owns: the shelf
membership comes from `state/projects.list_projects` (the FK, never the
name prefix — §3.1), the awaiting-human set and the last-event map from
`data/status.py` (the board reads the same two), and a running
pipeline's problem from `state/recovery._pipeline_problem`, the
state-layer mirror of the dispatcher's `_problem_of_target`.
"""
from __future__ import annotations

import sqlite3

from ...state import db
from ...state import projects as _projects
from ...state.recovery import _pipeline_problem
from .status import _awaiting_set, _live_daemon_pid, last_event_map


def _running_problems(conn: sqlite3.Connection,
                      daemon: "dict | None") -> "set[str]":
    """Problems the CURRENT daemon run has a pipeline running on.

    A `pipelines` row is INSERTed 'running' at dispatch and finalized at
    completion, so a crashed daemon leaves rows 'running' with no worker
    behind them until the next startup's `recover_at_startup` reaps
    them. Without a live daemon those rows are residue, not work — the
    same reading the board gives a dead owner's queue lease (which
    rendered as "1 agent running now" for 8 days).

    The reap is scope-filtered too, so a scoped daemon leaves an earlier
    crash's out-of-scope rows 'running' forever: a row this run could
    not have dispatched is residue by the same argument, hence the same
    `scope_matches` gate `_working` puts on the board's chips."""
    if _live_daemon_pid(daemon) is None:
        return set()
    scope = daemon.get("scope") if daemon else None
    out: set[str] = set()
    for r in conn.execute(
            "SELECT target_id, target_kind FROM pipelines"
            " WHERE status = 'running'"):
        problem = _pipeline_problem(
            conn, str(r["target_id"]), str(r["target_kind"]))
        if problem and (not scope or db.scope_matches(conn, scope, problem)):
            out.add(problem)
    return out


def project_rows(conn: sqlite3.Connection, *,
                 daemon: "dict | None" = None) -> "list[dict]":
    """`list_projects` rows plus the three live per-shelf numbers. An
    empty Project is legal (§3.1) and reads 0/0/None."""
    running = _running_problems(conn, daemon)
    awaiting = _awaiting_set(conn)
    last = last_event_map(conn)
    stats: dict[str, dict] = {}
    for r in conn.execute(
            "SELECT name, project, ingest_signoff_pending FROM problems"
            " WHERE project IS NOT NULL"):
        name, shelf = str(r["name"]), str(r["project"])
        s = stats.setdefault(shelf, {"running": 0, "attention": 0,
                                     "last_event": None})
        if name in running:
            s["running"] += 1
        if name in awaiting or r["ingest_signoff_pending"]:
            s["attention"] += 1
        at = last.get(name)
        if at and (s["last_event"] is None or at > s["last_event"]):
            s["last_event"] = at
    return [{**row, **stats.get(row["name"], {"running": 0, "attention": 0,
                                              "last_event": None})}
            for row in _projects.list_projects(conn)]
