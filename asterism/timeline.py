"""An agent's timeline, for the agent page: the messages it sent or was handed, and its changes of state (online,
offline with the reason, a new status), oldest first.

The changes of state are written down where they are decided (notices.sync for presence, statuses.py for statuses) in
the project's database, from f6b on; earlier ones are not recovered. Each is kept with the newest message id at the
moment it happened, so the timeline places it among the messages without comparing clocks. Nothing is announced:
this is a record for people to read, never something an agent is handed.

A reader sees only what they may read: messages of the channels they may read, and the private conversation between
the agent and themselves; the agent's own person also its private conversations with that person's other agents
(1v: on this page only; nowhere else are they the person's to read); the changes of state with the project's read
permission, as the member list.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from . import messaging, util
from .errors import bad_request, not_found
from .projects import Actor, Project

STATES = ("online", "offline", "status")
LIMIT_DEFAULT, LIMIT_MAX = 50, 200
_STATE_CURSOR = re.compile(r"s(\d{1,18})")
_NEVER = 1 << 62                    # larger than any id


def note(pj: Project, agent_id: int, state: str, reason: str | None = None, title: str | None = None) -> None:
    """Write down one change of an agent's state (outside any other transaction of the caller). `title`: a status's
    new title ('' when it was cleared)."""
    with pj.db:
        newest = pj.db.execute("SELECT coalesce(max(id), 0) FROM messages").fetchone()[0]
        pj.db.execute("INSERT INTO agent_states (agent_id, state, reason, title, after_message, at) "
                      "VALUES (?, ?, ?, ?, ?, ?)", (agent_id, state, reason, title, newest, util.now()))


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


def _state_view(r: sqlite3.Row) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "state", "id": f"s{r['id']}", "at": util.iso(r["at"]), "state": r["state"]}
    if r["reason"]:
        out["reason"] = r["reason"]
    if r["state"] == "status":
        out["title"] = r["title"] or ""
    return out


def timeline(pj: Project, actor: Actor, name: str, before: Any, limit: Any, only: Any = None) -> dict[str, Any]:
    """The newest `limit` items of the agent's timeline older than `before`, oldest first, and whether there are
    older ones. `only` "concerns": of the messages, only those the agent sent, those that mention it, its private
    conversation with the reader and, for its own person, with that person's other agents (the changes of state all
    the same). A message of the latter kind is named from the agent's side: `in` and `with` the other agent, at
    level normal for the reader. Every message the agent was given carries `agent_level`, its own level for it
    (1g)."""
    if only not in (None, "", "concerns"):
        raise bad_request("bad_request", "only is concerns, or nothing for everything.")
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
    # Its own person also reads its private conversations with that person's other agents (1v).
    pairs = [messaging.private_place(agent, messaging.agent_member(o)) for o in pj.db.execute(
        "SELECT * FROM agents WHERE person_id = ? AND id != ? ORDER BY id", (actor.person_id, a["id"]))] \
        if a["person_id"] == actor.person_id else []
    places = [private, *pairs]
    marks = ",".join("?" * len(places))
    # The agent's messages, each set from its own index (what it sent; what was delivered to it or it read in full;
    # its private conversations the reader may read), then what the reader may read of them.
    # Mentions are kept as a JSON list of names; a name is quoted there exactly as json.dumps writes it.
    concerns = (f"AND (m.sender_kind = 'agent' AND m.sender_id = ? OR m.place IN ({marks}) OR instr(m.mentions, ?) > 0) "
                if only == "concerns" else "")
    rows = pj.db.execute(
        f"SELECT m.* FROM messages m WHERE m.id IN ("
        f"SELECT id FROM messages WHERE sender_kind = 'agent' AND sender_id = ? "
        f"UNION SELECT message_id FROM deliveries WHERE agent_id = ? AND kind IN ('message', 'notice') "
        f"UNION SELECT message_id FROM levels WHERE reader_kind = 'agent' AND reader_id = ? AND seen IS NOT NULL "
        f"UNION SELECT id FROM messages WHERE place IN ({marks})) "
        f"AND m.id < ? AND (m.place IN ({','.join('?' * len(chans)) or 'NULL'}) OR m.place IN ({marks})) "
        f"{concerns}ORDER BY m.id DESC LIMIT ?",
        (a["id"], a["id"], a["id"], *places, below, *chans, *places,
         *((a["id"], *places, json.dumps(a["name"])) if concerns else ()), n + 1)).fetchall()
    states = pj.db.execute(
        "SELECT * FROM agent_states WHERE agent_id = ? AND (after_message < ? OR (after_message = ? AND id < ?)) "
        "ORDER BY after_message DESC, id DESC LIMIT ?", (a["id"], after_below, after_below, id_below, n + 1)).fetchall()
    # Newest first: a message by (its id, 0), a change of state by (the message it came after, 1, its id).
    merged = sorted([((r["id"], 0, 0), "m", r) for r in rows] + [((s["after_message"], 1, s["id"]), "s", s) for s in states],
                    key=lambda x: x[0], reverse=True)
    more = len(merged) > n
    page = list(reversed(merged[:n]))
    msgs = [r for _, k, r in page if k == "m"]
    shown = {m["id"]: m for m in messaging.views(pj, [r for r in msgs if r["place"] not in pairs], me)}
    for m in messaging.views(pj, [r for r in msgs if r["place"] in pairs], me, side=agent):
        shown[m["id"]] = dict(m, **{"with": m["in"]})
    # 1g: the agent's own level of each message it was given (none for what it sent itself).
    if msgs:
        marks = ",".join("?" * len(msgs))
        for r in pj.db.execute(f"SELECT message_id, level FROM levels WHERE reader_kind = 'agent' AND reader_id = ? "
                               f"AND message_id IN ({marks})", (a["id"], *[r["id"] for r in msgs])):
            if r["message_id"] in shown:
                shown[r["message_id"]]["agent_level"] = r["level"]
    items: list[dict[str, Any]] = []
    for _, k, r in page:
        if k == "m":
            sent = r["sender_kind"] == "agent" and r["sender_id"] == a["id"]
            items.append({"kind": "message", "message": shown[r["id"]], "dir": "sent" if sent else "received"})
        else:
            items.append(_state_view(r))
    return {"items": items, "more": more}
