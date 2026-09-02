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
from .timeline import _LIFE_RANK, problem_events


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


#: rows per page when the caller names no limit, and the ceiling on
#: what it may ask for. The per-task feed is unpaginated because one
#: task's history is one task's; a shelf's is every task's at once.
_EVENTS_PAGE = 200
_EVENTS_MAX = 2000


def project_events(conn: sqlite3.Connection, project: str, *,
                   limit: "int | None" = None,
                   before: "str | None" = None) -> dict:
    """The Project's Timeline: the per-task feeds unioned, newest first.

    Same rows as `/api/problems/{p}/events` — the same query, so the two
    surfaces can never disagree about what happened — each carrying the
    `problem` it came from, which is the one thing a shelf-wide reader
    needs that a task-wide reader already knows.

    `log_since` is per problem and deliberately NOT one number: it marks
    where a task's engine-written record starts (below it, landings are
    dated by inference), and a single shelf-wide line would mislabel
    every other task's rows. It keeps its own key so a client reusing
    the per-task reader cannot mistake the map for that feed's string.

    Pagination: `before` is exclusive on `at`, and a page therefore
    never ends in the middle of a timestamp — the rows sharing the last
    row's second ride along, or the next request would skip them.
    `next_before` is the cursor for that request, None at the end.
    """
    names = sorted(_projects.problems_of(conn, project))
    events: "list[dict]" = []
    log_since: "dict[str, str | None]" = {}
    for name in names:
        feed = problem_events(conn, name)
        log_since[name] = feed.get("log_since")
        for e in feed["events"]:
            e["problem"] = name
            events.append(e)
    events.sort(key=lambda e: (e["at"], _LIFE_RANK.get(e["kind"], 5),
                               str(e["id"])), reverse=True)
    if before:
        events = [e for e in events if e["at"] < before]
    n = max(1, min(int(limit or _EVENTS_PAGE), _EVENTS_MAX))
    page = events[:n]
    while len(page) < len(events) and events[len(page)]["at"] == page[-1]["at"]:
        page.append(events[len(page)])
    more = len(page) < len(events)
    return {
        "project": project,
        "problems": names,
        "log_since_by_problem": log_since,
        "events": page,
        "next_before": page[-1]["at"] if (more and page) else None,
    }
