"""Statuses (1s): what each agent is working on, and a line about each person.

- An agent's status is a `title` (one line, up to 200 characters; empty: no status) and a `body` (up to 10,000,
  kept as written), written only by the agent itself (set_status). A field left out keeps its value; an empty title
  clears both. `status_at` says when the agent last set it, changed or not (any set_status is an update); a new
  title goes into the agent's timeline.
- Its person may ask for an update every `update_every_h` hours (1 to 168; one hour is ASTERISM_STATUS_HOUR_S). An
  agent whose last change, or the moment that was asked if later, is older than that is overdue
  (projects.status_overdue): it is reminded once per period, privately from the system (UPDATE_DUE, important), and
  its next set_status answers that reminder. Nobody else is told; the pages mark it.
- A person's status is a title only, per project, set by the person. It is never overdue and goes nowhere else.

A status changes nothing of how messages reach an agent.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from . import config, messaging, projects, timeline, util
from .errors import bad_request, forbidden, not_found
from .projects import Actor, Project

TITLE_MAX = 200
BODY_MAX = 10_000
EVERY_MAX_H = 168

# Agent-facing wording, word for word from the specification (approved by the user, 2026-11-22).
UPDATE_DUE = ("Your person asked for a status update every {hours} h; the last was {ago} ago. Write where you stand "
              "with set_status.")


# --------------------------------------------------------------------------- reading

def view(pj: Project, a: sqlite3.Row, owners: dict[int, str] | None = None) -> dict[str, Any]:
    """An agent's status, the same for agents and people."""
    owner = owners.get(a["person_id"], "") if owners is not None else projects.person_name(pj, a["person_id"])
    return {"agent": a["name"], "person": owner, "title": a["status_title"], "body": a["status_body"],
            "at": util.iso(a["status_at"]), "update_every_h": a["update_every_h"],
            "overdue": projects.status_overdue(a)}


def _owners(pj: Project) -> dict[int, str]:
    return {r["person_id"]: r["name"] for r in pj.db.execute("SELECT person_id, name FROM people")}


def agent_statuses(pj: Project, a: sqlite3.Row) -> dict[str, Any]:
    """For an agent (statuses): every agent that shares at least one group with it, itself included."""
    rows = pj.db.execute("SELECT DISTINCT x.* FROM agents x JOIN group_members o ON o.member_kind = 'agent' "
                         "AND o.member_id = x.id JOIN group_members m ON m.group_id = o.group_id "
                         "AND m.member_kind = 'agent' AND m.member_id = ? ORDER BY x.id", (a["id"],)).fetchall()
    if not any(r["id"] == a["id"] for r in rows):         # an agent in no group still reads its own
        rows = [a] + list(rows)
    owners = _owners(pj)
    return {"statuses": [view(pj, r, owners) for r in rows]}


def board(pj: Project, actor: Actor) -> dict[str, Any]:
    """For people (the dashboard): every agent's status with its groups, and every person's."""
    projects.require(pj, actor, "read", "Reading the project needs the read permission.")
    owners = _owners(pj)
    agents = []
    for a in pj.db.execute("SELECT * FROM agents ORDER BY id"):
        item = view(pj, a, owners)
        item["groups"] = [g["name"] for g in projects.groups_of(pj, "agent", a["id"])]
        agents.append(item)
    people = [{"name": r["name"], "title": r["status_title"], "at": util.iso(r["status_at"])}
              for r in pj.db.execute("SELECT * FROM people ORDER BY joined, person_id")]
    return {"agents": agents, "people": people}


# --------------------------------------------------------------------------- writing

def _title(v: Any) -> str:
    """One line: every run of whitespace becomes one space."""
    if not isinstance(v, str):
        raise bad_request("bad_request", "title must be text: one line of 0 to 200 characters.")
    v = " ".join(v.split())
    if len(v) > TITLE_MAX:
        raise bad_request("too_long", f"The title is {len(v):,} characters; the most is 200. Put the rest in the body.")
    return v


def _body(v: Any) -> str:
    if not isinstance(v, str):
        raise bad_request("bad_request", "body must be text: 0 to 10,000 characters.")
    if len(v) > BODY_MAX:
        raise bad_request("too_long", f"The body is {len(v):,} characters; the most is 10,000. Put the details in a "
                                      f"file in the repository.")
    return v


def agent_set(pj: Project, a: sqlite3.Row, body: dict[str, Any]) -> dict[str, Any]:
    """set_status. A field left out (or null) keeps its value; an empty title clears the title and the body. Any
    call is an update (status_at, and it answers the reminders of an update due); a new title is written into the
    agent's timeline."""
    title = _title(body["title"]) if body.get("title") is not None else a["status_title"]
    text = _body(body["body"]) if body.get("body") is not None else a["status_body"]
    if not title:
        if body.get("body") and body.get("title") is None:
            raise bad_request("bad_request", "A status needs a title: give `title` (one line on what you are working "
                                             "on) with the body.")
        text = ""
    t = util.now()
    with pj.db:
        pj.db.execute("UPDATE agents SET status_title = ?, status_body = ?, status_at = ? WHERE id = ?",
                      (title, text, t, a["id"]))
        messaging.answer_by_status(pj, a["id"], t)
    if title != a["status_title"]:
        timeline.note(pj, a["id"], "status", title=title)
    util.log("status_set", project=pj.slug, agent=a["name"])
    return {"status": view(pj, pj.db.execute("SELECT * FROM agents WHERE id = ?", (a["id"],)).fetchone())}


def set_every(pj: Project, actor: Actor, name: str, body: dict[str, Any]) -> dict[str, Any]:
    """The agent's person asks for an update every `hours` hours (1 to 168), or no longer (null). The period counts
    from now."""
    a = pj.db.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
    if a is None:
        raise not_found(f"There is no agent '{name}'.")
    if actor.agent_id is not None or a["person_id"] != actor.person_id:
        raise forbidden(f"Only {projects.person_name(pj, a['person_id'])} asks {name} for status updates.")
    hours = body.get("hours")
    if hours is not None and (isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= EVERY_MAX_H):
        raise bad_request("bad_request", "hours must be a whole number of hours from 1 to 168, or null.")
    with pj.db:
        pj.db.execute("UPDATE agents SET update_every_h = ?, update_every_at = ?, status_reminded = NULL WHERE id = ?",
                      (hours, util.now() if hours is not None else None, a["id"]))
    util.log("status_every_set", project=pj.slug, agent=name, hours=hours)
    return {"status": view(pj, pj.db.execute("SELECT * FROM agents WHERE id = ?", (a["id"],)).fetchone())}


def person_set(pj: Project, actor: Actor, body: dict[str, Any]) -> dict[str, Any]:
    """A person's own status in this project: a title only (a body sent is not kept)."""
    if actor.agent_id is not None:
        raise forbidden("Only a person sets a person's status.")
    title = _title(body.get("title"))
    with pj.db:
        pj.db.execute("UPDATE people SET status_title = ?, status_at = ? WHERE person_id = ?",
                      (title, util.now(), actor.person_id))
    r = pj.db.execute("SELECT * FROM people WHERE person_id = ?", (actor.person_id,)).fetchone()
    return {"name": r["name"], "title": r["status_title"], "at": util.iso(r["status_at"])}


# --------------------------------------------------------------------------- time: updates due

def _hour_s() -> float:
    return config.get().status_hour_s


def _due_at(a: sqlite3.Row) -> float | None:
    """When the agent is reminded next: a period after its last update, and never twice in one period."""
    since = projects.status_since(a)
    if not a["update_every_h"] or since is None:
        return None
    return max(since, a["status_reminded"] or 0) + a["update_every_h"] * _hour_s()


def _ago(seconds: float) -> str:
    """How long ago, in the statuses' hours (ASTERISM_STATUS_HOUR_S): whole hours, or minutes under one."""
    hours = seconds / _hour_s()
    return f"{int(hours)} h" if hours >= 1 else f"{max(1, int(hours * 60))} min"


def sweep(pj: Project, t: float) -> None:
    """The agents whose status update is due reminded (UPDATE_DUE)."""
    for a in pj.db.execute("SELECT * FROM agents WHERE update_every_h IS NOT NULL").fetchall():
        due = _due_at(a)
        if due is None or due > t:
            continue
        with pj.db:
            pj.db.execute("UPDATE agents SET status_reminded = ? WHERE id = ?", (t, a["id"]))
        text = UPDATE_DUE.format(hours=a["update_every_h"], ago=_ago(t - projects.status_since(a)))
        messaging.post_to_agent(pj, a, text, asks_status=True)
        util.log("status_update_due", project=pj.slug, agent=a["name"])


def next_due(pj: Project) -> list[float]:
    return [d for d in (_due_at(a) for a in pj.db.execute("SELECT * FROM agents WHERE update_every_h IS NOT NULL"))
            if d is not None]
