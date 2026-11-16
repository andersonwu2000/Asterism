"""An agent's timeline, for the agent page: the messages it sent or was handed, and its changes of state (online,
offline with the reason, a task given to it, taken, released or removed), oldest first.

The changes of state are written down where they are decided (notices.sync for presence, tasks.py for tasks) in
the project's database, from f6b on; earlier ones are not recovered. Each is kept with the newest message id at the
moment it happened, so the timeline places it among the messages without comparing clocks. Nothing is announced:
this is a record for people to read, never something an agent is handed.

A reader sees only what they may read: messages of the channels they may read, and the private conversation between
the agent and themselves (a person is in no other private conversation of an agent); the changes of state with the
project's read permission, as the member list.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any

from . import messaging, util
from .errors import bad_request, not_found
from .messaging import Member
from .projects import Actor, Project

STATES = ("online", "offline", "task_given", "task_taken", "task_released", "task_removed")
LIMIT_DEFAULT, LIMIT_MAX = 50, 200
_STATE_CURSOR = re.compile(r"s(\d{1,18})")
_NEVER = 1 << 62                    # larger than any id


def note(pj: Project, agent_id: int, state: str, reason: str | None = None, task_id: int | None = None,
         by: Member | None = None) -> None:
    """Write down one change of an agent's state (outside any other transaction of the caller)."""
    with pj.db:
        newest = pj.db.execute("SELECT coalesce(max(id), 0) FROM messages").fetchone()[0]
        pj.db.execute("INSERT INTO agent_states (agent_id, state, reason, task_id, by_kind, by_id, after_message, at) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (agent_id, state, reason, task_id, by.kind if by else None, by.id if by else None, newest,
                       util.now()))


def _cursor(pj: Project, agent_id: int, before: Any) -> tuple[int, int, int]:
    """(messages below this id, states below this (after_message, id)) for `before`: a message id, or a change of
    state's id as the timeline gives it ("s12"); nothing for the newest."""
    if before is None or before == "":
        return _NEVER, _NEVER, 0
    raw = str(before).strip()
    m = _STATE_CURSOR.fullmatch(raw)
    if m:
        r = pj.db.execute("SELECT after_message, id FROM agent_states WHERE id = ? AND agent_id = ?",
                          (int(m.group(1)), agent_id)).fetchone()
        if r is None:
            raise bad_request("bad_request", "before names no item of this timeline.")
        return r["after_message"] + 1, r["after_message"], r["id"]
    if re.fullmatch(r"\d{1,18}", raw):
        return int(raw), int(raw), 0
    raise bad_request("bad_request", "before is a message id, or a state's id (s12).")


def _by_name(pj: Project, kind: str | None, mid: int | None) -> str | None:
    if kind == "person":
        r = pj.db.execute("SELECT name FROM people WHERE person_id = ?", (mid,)).fetchone()
    elif kind == "agent":
        r = pj.db.execute("SELECT name FROM agents WHERE id = ?", (mid,)).fetchone()
    else:
        return None
    return r["name"] if r else None


def _state_view(pj: Project, r: sqlite3.Row) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "state", "id": f"s{r['id']}", "at": util.iso(r["at"]), "state": r["state"]}
    if r["reason"]:
        out["reason"] = r["reason"]
    if r["task_id"] is not None:
        out["task"] = r["task_id"]
    who = _by_name(pj, r["by_kind"], r["by_id"])
    if who:
        out["by"] = who
    return out


def timeline(pj: Project, actor: Actor, name: str, before: Any, limit: Any) -> dict[str, Any]:
    """The newest `limit` items of the agent's timeline older than `before`, oldest first, and whether there are
    older ones."""
    me = messaging.person_member(pj, actor.person_id)
    messaging.require_read(pj, me)
    a = pj.db.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
    if a is None:
        raise not_found(f"There is no agent '{name}'.")
    n = messaging._int(limit, "limit")
    n = LIMIT_DEFAULT if n is None else max(1, min(n, LIMIT_MAX))
    below, after_below, id_below = _cursor(pj, a["id"], before)
    agent = messaging.agent_member(a)
    chans = sorted(messaging.readable(pj, me))
    private = messaging.private_place(me, agent)
    # The agent's messages, each set from its own index (what it sent; what was delivered to it or it read in full;
    # its private conversation with the reader), then what the reader may read of them.
    rows = pj.db.execute(
        f"SELECT m.* FROM messages m WHERE m.id IN ("
        f"SELECT id FROM messages WHERE sender_kind = 'agent' AND sender_id = ? "
        f"UNION SELECT message_id FROM deliveries WHERE agent_id = ? AND kind IN ('message', 'notice') "
        f"UNION SELECT message_id FROM levels WHERE reader_kind = 'agent' AND reader_id = ? AND seen IS NOT NULL "
        f"UNION SELECT id FROM messages WHERE place = ?) "
        f"AND m.id < ? AND (m.place IN ({','.join('?' * len(chans)) or 'NULL'}) OR m.place = ?) "
        f"ORDER BY m.id DESC LIMIT ?",
        (a["id"], a["id"], a["id"], private, below, *chans, private, n + 1)).fetchall()
    states = pj.db.execute(
        "SELECT * FROM agent_states WHERE agent_id = ? AND (after_message < ? OR (after_message = ? AND id < ?)) "
        "ORDER BY after_message DESC, id DESC LIMIT ?", (a["id"], after_below, after_below, id_below, n + 1)).fetchall()
    # Newest first: a message by (its id, 0), a change of state by (the message it came after, 1, its id).
    merged = sorted([((r["id"], 0, 0), "m", r) for r in rows] + [((s["after_message"], 1, s["id"]), "s", s) for s in states],
                    key=lambda x: x[0], reverse=True)
    more = len(merged) > n
    page = list(reversed(merged[:n]))
    shown = {m["id"]: m for m in messaging.views(pj, [r for _, k, r in page if k == "m"], me)}
    items: list[dict[str, Any]] = []
    for _, k, r in page:
        if k == "m":
            sent = r["sender_kind"] == "agent" and r["sender_id"] == a["id"]
            items.append({"kind": "message", "message": shown[r["id"]], "dir": "sent" if sent else "received"})
        else:
            items.append(_state_view(pj, r))
    return {"items": items, "more": more}
