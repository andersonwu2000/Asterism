"""The task table: who does what. A task belongs to one group (fixed when it is made), has a text, and may have a
responsible agent of that group: a task is given to an agent or to nobody, never to a person. A person who makes an
agent responsible locks the task in their own name (`assigned_by`); an agent never locks. There is no status, done
mark or history: a task that is done is removed.

The rules, for every entrance:
- every change needs `edit_tasks`; an agent acts only in the groups it is in;
- changing the task of an agent is directing that agent: the agent itself, its person and that person's other
  agents always may; others need the agent's `others_assign` switch (and, a person, `assign_tasks`);
- a locked task is changed only by the person who locked it and the agent's person;
- another person's agent changes nothing of an agent's task: it asks that agent, which changes it itself. Only
  when that agent is offline and its switch is on may it take the task over;
- an agent that coordinates (`coordinate_tasks`) changes, removes, takes and gives the tasks of another person's
  agent directly, whenever that agent's switch is on; it never locks, and a lock holds against it too.

When a change is made by somebody other than the agent it concerns, the system tells that agent in the project's
notice channel.
Being responsible for a task is what makes an agent busy (presence.busy).
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from . import messaging, presence, projects, util
from .errors import ApiError, bad_request, forbidden, not_found
from .messaging import Member
from .projects import Actor, Project

TEXT_MAX = 2_000
CLIP = 120
NOTICE_TASKS = 10

# Agent-facing wording, word for word from the specification.
LOCKED = "Task {id} was assigned by {person}, so only {person} can change it. When it is done, tell {person}."
NOT_YOURS = "Task {id} is {agent}'s. Ask {agent} to change it or to hand it over."
NOT_YOURS_OFFLINE = ("Task {id} is {agent}'s, and {agent} is offline. Its user has not allowed others to move its tasks: "
                     "ask {person}, or make a task of your own.")
TAKE_OVER_ONLY = ("Task {id} is {agent}'s, and {agent} is offline. You may take it over (set responsible to your own "
                  "name); change it after that.")
ASK_FIRST = ("{agent} is another collaborator's agent, so you cannot put a task in its name. Leave the task without a "
             "responsible member and ask {agent} to claim it.")
# agent-facing: approved by the user (2026-11-16)
NOT_AN_AGENT = "{name} is a person. A task is given to an agent, or to nobody (responsible empty)."
# What a person, or an agent that coordinates, is told when the agent's person keeps its tasks to their own side.
CLOSED = "{agent} is an agent of {person}, who has not allowed others to give it tasks or to change its tasks."
TOLD = {
    "removed": "{actor} removed task {id} [{group}] of {agent}.",
    "assigned": "{actor} assigned task {id} [{group}] to {agent}: {text}",
    "gave": "{actor} gave task {id} [{group}] to {agent}: {text}",
    "took": "{actor} took task {id} [{group}] from {agent}.",
    "changed": "{actor} changed task {id} [{group}] of {agent}: {text}",
    "released": "{actor} released task {id} [{group}]: {agent} may change it now.",
}
BEFORE = " It was {previous}'s before."


def clip(text: str) -> str:
    """Every run of whitespace one space, cut to its first 120 characters."""
    s = " ".join(text.split())
    return s if len(s) <= CLIP else s[:CLIP] + "…"


# --------------------------------------------------------------------------- reading

@dataclass(frozen=True)
class State:
    """What a change looks at: the task's text, its responsible member and who locked it (a person id)."""
    text: str
    responsible: Member | None
    assigned_by: int | None


def _member(pj: Project, kind: str | None, mid: int | None) -> Member | None:
    if kind == "person":
        r = pj.db.execute("SELECT * FROM people WHERE person_id = ?", (mid,)).fetchone()
        return Member("person", r["person_id"], r["person_id"], r["name"]) if r else None
    if kind == "agent":
        a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (mid,)).fetchone()
        return messaging.agent_member(a) if a else None
    return None


def _state(pj: Project, row: sqlite3.Row) -> State:
    return State(row["text"], _member(pj, row["responsible_kind"], row["responsible_id"]), row["assigned_by"])


def _group_name(pj: Project, group_id: int) -> str:
    g = pj.db.execute("SELECT name FROM groups WHERE id = ?", (group_id,)).fetchone()
    return g["name"] if g else ""


def view(pj: Project, row: sqlite3.Row) -> dict[str, Any]:
    """The task object; `online` only when an agent is responsible."""
    who = _member(pj, row["responsible_kind"], row["responsible_id"])
    out: dict[str, Any] = {"id": row["id"], "group": _group_name(pj, row["group_id"]), "text": row["text"],
                           "responsible": who.name if who else None, "responsible_kind": who.kind if who else None}
    if who and who.kind == "agent":
        a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (who.id,)).fetchone()
        out["online"] = presence.is_online(pj.slug, a, pj.db)
    out["assigned_by"] = projects.person_name(pj, row["assigned_by"]) if row["assigned_by"] is not None else None
    return out


def _task(pj: Project, tid: Any) -> sqlite3.Row:
    n = tid if isinstance(tid, int) and not isinstance(tid, bool) else \
        int(tid) if isinstance(tid, str) and re.fullmatch(r"\d{1,18}", tid.strip()) else None
    if n is None:
        raise bad_request("bad_request", "id must be the number of a task.")
    row = pj.db.execute("SELECT * FROM tasks WHERE id = ?", (n,)).fetchone()
    if row is None:
        raise not_found(f"There is no task {n}. The tasks call lists them.")
    return row


def _in_group(pj: Project, group_id: int, m: Member) -> bool:
    return pj.db.execute("SELECT 1 FROM group_members WHERE group_id = ? AND member_kind = ? AND member_id = ?",
                         (group_id, m.kind, m.id)).fetchone() is not None


def table(pj: Project, actor: Actor) -> dict[str, Any]:
    """For people: every group in the order of the members API, with its members (online; busy for agents)
    and its tasks by id."""
    projects.require(pj, actor, "read", "Reading the project needs the read permission.")
    out = []
    for g in projects.ordered_groups(pj):
        members: list[dict[str, Any]] = [
            {"name": r["name"], "kind": "person", "online": projects.person_online(r)}
            for r in pj.db.execute("SELECT p.* FROM people p JOIN group_members m ON m.member_id = p.person_id "
                                   "AND m.member_kind = 'person' WHERE m.group_id = ? ORDER BY p.joined, p.person_id",
                                   (g["id"],))]
        for a in pj.db.execute("SELECT a.* FROM agents a JOIN group_members m ON m.member_id = a.id "
                               "AND m.member_kind = 'agent' WHERE m.group_id = ? ORDER BY a.id", (g["id"],)):
            members.append({"name": a["name"], "kind": "agent", "online": presence.is_online(pj.slug, a, pj.db),
                            "busy": presence.busy(pj.db, a)})
        rows = pj.db.execute("SELECT * FROM tasks WHERE group_id = ? ORDER BY id", (g["id"],)).fetchall()
        out.append({"name": g["name"], "kind": g["kind"], "members": members, "tasks": [view(pj, r) for r in rows]})
    return {"groups": out}


def agent_tasks(pj: Project, a: sqlite3.Row) -> dict[str, Any]:
    """For an agent: the tasks of every group it is in, by group name, then id."""
    rows = pj.db.execute("SELECT t.* FROM tasks t JOIN groups g ON g.id = t.group_id JOIN group_members m "
                         "ON m.group_id = g.id AND m.member_kind = 'agent' AND m.member_id = ? ORDER BY g.name, t.id",
                         (a["id"],)).fetchall()
    return {"tasks": [view(pj, r) for r in rows]}


# --------------------------------------------------------------------------- checks shared by people and agents

def _text(v: Any) -> str:
    if not isinstance(v, str) or not v.strip():
        raise bad_request("bad_request", "text must be the task: 1 to 2,000 characters.")
    v = v.strip()
    if len(v) > TEXT_MAX:
        raise bad_request("too_long", f"The text is {len(v):,} characters; the most for a task is 2,000. Keep the task "
                                      f"short and put the details in a file in the repository.")
    return v


class NotAnAgent(ApiError):
    """A `responsible` that names a person. The message is the agents' sentence; the web pages say it in the
    reader's language (`name` is the person named)."""
    def __init__(self, name: str):
        super().__init__(400, "not_an_agent", NOT_AN_AGENT.format(name=name))
        self.name = name


def _who(pj: Project, name: Any) -> Member | None:
    """The agent a `responsible` names; empty or null is nobody. A person is never given a task."""
    if name is None or name == "":
        return None
    m = messaging.member_by_name(pj, name) if isinstance(name, str) else None
    if m is None:
        raise not_found(f"There is no member '{name}'. responsible is an agent's name, or empty for nobody.")
    if m.kind != "agent":
        raise NotAnAgent(m.name)
    return m


def _check_in_group(pj: Project, group_id: int, m: Member | None) -> None:
    if m is not None and not _in_group(pj, group_id, m):
        g = _group_name(pj, group_id)
        raise bad_request("not_in_group", f"{m.name} is not in the group '{g}', so it cannot be responsible for a "
                                          f"task of '{g}'.")


def _edit(pj: Project, actor: Actor) -> None:
    message = ("Changing the task table needs the edit_tasks permission." if actor.agent_id is None else
               "Changing the task table needs the edit_tasks permission. Ask your user to give it to you.")
    projects.require(pj, actor, "edit_tasks", message)


def _agent_row(pj: Project, m: Member) -> sqlite3.Row:
    return pj.db.execute("SELECT * FROM agents WHERE id = ?", (m.id,)).fetchone()


def _others_assign(pj: Project, agent: Member) -> bool:
    return projects.switch_on(pj, agent.person_id, "others_assign")


# --------------------------------------------------------------------------- people

def _person_may_direct(pj: Project, actor: Actor, agent: Member) -> None:
    """Giving a task to an agent, or changing one it is responsible for: its own person always; anyone else
    needs that agent's others_assign switch and the assign_tasks permission."""
    if agent.person_id == actor.person_id:
        return
    owner = projects.person_name(pj, agent.person_id)
    if not _others_assign(pj, agent):
        raise forbidden(CLOSED.format(agent=agent.name, person=owner))
    projects.require(pj, actor, "assign_tasks", f"{agent.name} is an agent of {owner}; giving it tasks or changing its "
                                                f"tasks needs the assign_tasks permission.")


def _person_may_touch(pj: Project, actor: Actor, tid: int, before: State) -> None:
    r = before.responsible
    if r is None or r.kind != "agent" or r.person_id == actor.person_id:
        return
    if before.assigned_by is not None:
        if before.assigned_by != actor.person_id:
            by, owner = projects.person_name(pj, before.assigned_by), projects.person_name(pj, r.person_id)
            who = by if by == owner else f"{by} or {owner}"
            raise ApiError(403, "task_locked", f"Task {tid} was assigned to {r.name} by {by}, so only {who} can "
                                               f"change it.")
        return
    _person_may_direct(pj, actor, r)


def _locked(v: Any) -> bool | None:
    if v is None or isinstance(v, bool):
        return v
    raise bad_request("bad_request", "locked must be true or false.")


def _lock_after(actor: Actor, before: State | None, now: Member | None, locked: bool | None) -> int | None:
    """Who has the task locked after a person's request."""
    if now is None or now.kind != "agent":
        if locked:
            raise bad_request("bad_request", "Only a task an agent is responsible for can be locked.")
        return None
    if locked is not None:
        return actor.person_id if locked else None
    if before is None or before.responsible != now:     # the request makes this agent responsible
        return actor.person_id
    return before.assigned_by


def person_create(pj: Project, actor: Actor, body: dict[str, Any]) -> dict[str, Any]:
    _edit(pj, actor)
    gname = body.get("group")
    g = projects.group_by_name(pj, gname) if isinstance(gname, str) else None
    if g is None:
        raise not_found(f"There is no group '{gname}'.")
    text = _text(body.get("text"))
    now = _who(pj, body.get("responsible"))
    locked = _locked(body.get("locked"))
    _check_in_group(pj, g["id"], now)
    if now is not None and now.kind == "agent":
        _person_may_direct(pj, actor, now)
    after = State(text, now, _lock_after(actor, None, now, locked))
    return {"task": _write(pj, messaging.person_member(pj, actor.person_id), g["id"], None, None, after)}


def person_change(pj: Project, actor: Actor, tid: Any, body: dict[str, Any]) -> dict[str, Any]:
    _edit(pj, actor)
    row = _task(pj, tid)
    if not {"text", "responsible", "locked"} & set(body):
        raise bad_request("bad_request", "Say what to change: text, responsible or locked.")
    text = _text(body["text"]) if "text" in body else row["text"]
    locked = _locked(body.get("locked"))
    asked = _who(pj, body["responsible"]) if "responsible" in body else None
    before = _state(pj, row)
    _person_may_touch(pj, actor, row["id"], before)
    now = asked if "responsible" in body else before.responsible
    if now != before.responsible:
        _check_in_group(pj, row["group_id"], now)
        if now is not None and now.kind == "agent":
            _person_may_direct(pj, actor, now)
    after = State(text, now, _lock_after(actor, before, now, locked))
    return {"task": _write(pj, messaging.person_member(pj, actor.person_id), row["group_id"], row["id"], before, after)}


def person_remove(pj: Project, actor: Actor, tid: Any) -> dict[str, Any]:
    _edit(pj, actor)
    row = _task(pj, tid)
    before = _state(pj, row)
    _person_may_touch(pj, actor, row["id"], before)
    return _remove(pj, messaging.person_member(pj, actor.person_id), row, before)


# --------------------------------------------------------------------------- agents

def agent_update(pj: Project, a: sqlite3.Row, body: dict[str, Any]) -> dict[str, Any]:
    """task_update. The order of the checks: `responsible` names an agent or nobody; the task exists; the agent is
    in its group; the lock; whose task it is; the new responsible member is in the group; then whether the agent may
    put the task in its name."""
    me = messaging.agent_member(a)
    actor = Actor(a["person_id"], a["id"])
    _edit(pj, actor)
    if "responsible" in body:
        _who(pj, body["responsible"])          # a person is refused before anything else is looked at
    coordinates = "coordinate_tasks" in projects.permissions(pj, actor)
    mine = [g["name"] for g in projects.groups_of(pj, "agent", a["id"])]
    if body.get("id") is None:
        gname = body.get("group")
        if gname is None or gname == "":
            raise bad_request("bad_request", "A new task needs `group` (one of yours: " + ", ".join(mine) + ") and `text`.")
        g = projects.group_by_name(pj, gname) if isinstance(gname, str) else None
        if g is None or g["name"] not in mine:
            raise forbidden(f"You can make tasks only in the groups you are in: {', '.join(mine)}.")
        text = _text(body.get("text"))
        now = _who(pj, body.get("responsible"))
        _check_in_group(pj, g["id"], now)
        _may_name(pj, me, now, coordinates)
        return {"task": _write(pj, me, g["id"], None, None, State(text, now, None))}

    row = _task(pj, body.get("id"))
    tid, group = row["id"], _group_name(pj, row["group_id"])
    if group not in mine:
        raise forbidden(f"Task {tid} is in the group '{group}', which you are not in. You act only on the tasks of "
                        f"your groups: {', '.join(mine)}.")
    remove = body.get("remove") is True
    if not remove and "text" not in body and "responsible" not in body:
        raise bad_request("bad_request", "Say what to change: text, responsible, or remove=true.")
    text = _text(body["text"]) if "text" in body and not remove else row["text"]
    before = _state(pj, row)
    if before.assigned_by is not None:
        person = projects.person_name(pj, before.assigned_by)
        raise ApiError(403, "task_locked", LOCKED.format(id=tid, person=person))
    r = before.responsible
    if r is not None and r.kind == "agent" and r.person_id != me.person_id and coordinates:
        if not _others_assign(pj, r):
            raise forbidden(CLOSED.format(agent=r.name, person=projects.person_name(pj, r.person_id)))
    elif r is not None and r.kind == "agent" and r.person_id != me.person_id:
        if presence.is_online(pj.slug, _agent_row(pj, r), pj.db):
            raise ApiError(403, "not_yours", NOT_YOURS.format(id=tid, agent=r.name))
        if not _others_assign(pj, r):
            raise ApiError(403, "not_yours", NOT_YOURS_OFFLINE.format(id=tid, agent=r.name,
                                                                     person=projects.person_name(pj, r.person_id)))
        if remove or "text" in body or body.get("responsible") != me.name:
            raise ApiError(403, "not_yours", TAKE_OVER_ONLY.format(id=tid, agent=r.name))
    if remove:
        return _remove(pj, me, row, before)
    now = _who(pj, body["responsible"]) if "responsible" in body else before.responsible
    if now != before.responsible:
        _check_in_group(pj, row["group_id"], now)
        _may_name(pj, me, now, coordinates)
    return {"task": _write(pj, me, row["group_id"], tid, before, State(text, now, None))}


def _may_name(pj: Project, me: Member, now: Member | None, coordinates: bool) -> None:
    """An agent puts a task in the name of itself, an agent of its own person, or nobody (`_who` refuses a person);
    an agent that coordinates also in the name of another person's agent whose switch is on."""
    if now is None or now.kind != "agent" or now.person_id == me.person_id:
        return
    if not coordinates:
        raise ApiError(403, "ask_first", ASK_FIRST.format(agent=now.name))
    if not _others_assign(pj, now):
        raise forbidden(CLOSED.format(agent=now.name, person=projects.person_name(pj, now.person_id)))


# --------------------------------------------------------------------------- writing, and telling the agents

def _write(pj: Project, actor: Member, group_id: int, tid: int | None, before: State | None, after: State) -> dict[str, Any]:
    r = after.responsible
    cols = (after.text, r.kind if r else None, r.id if r else None, after.assigned_by)
    with pj.db:
        if tid is None:
            tid = pj.db.execute("INSERT INTO tasks (group_id, text, responsible_kind, responsible_id, assigned_by, "
                                "created) VALUES (?, ?, ?, ?, ?, ?)", (group_id, *cols, util.now())).lastrowid
        else:
            pj.db.execute("UPDATE tasks SET text = ?, responsible_kind = ?, responsible_id = ?, assigned_by = ? "
                          "WHERE id = ?", (*cols, tid))
    util.log("task_made" if before is None else "task_changed", project=pj.slug, task=tid, by=actor.name)
    _tell(pj, actor, tid, _group_name(pj, group_id), before, after)
    return view(pj, pj.db.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone())


def _remove(pj: Project, actor: Member, row: sqlite3.Row, before: State) -> dict[str, Any]:
    with pj.db:
        pj.db.execute("DELETE FROM tasks WHERE id = ?", (row["id"],))
    util.log("task_removed", project=pj.slug, task=row["id"], by=actor.name)
    _tell(pj, actor, row["id"], _group_name(pj, row["group_id"]), before, None)
    return {"removed": row["id"]}


def _tell(pj: Project, actor: Member, tid: int, group: str, before: State | None, after: State | None) -> None:
    """The message from the system to the agents a change concerns: the responsible agent before and after it,
    except the one who made it. For each of them: normal when an agent of its own person made the change,
    important when a person or another person's agent did."""
    def agent(s: State | None) -> Member | None:
        return s.responsible if s is not None and s.responsible is not None and s.responsible.kind == "agent" else None
    x, y = agent(before), agent(after)
    concerned = {m.id: m for m in (x, y) if m is not None and m != actor}
    if not concerned:
        return
    fill = {"actor": actor.name, "id": tid, "group": group, "text": clip(after.text) if after else ""}
    if after is None:
        text = TOLD["removed"].format(agent=x.name, **fill)
    elif y is not None and y != x and y != actor:
        text = TOLD["assigned" if after.assigned_by is not None else "gave"].format(agent=y.name, **fill)
        if x is not None and x != actor:
            text += BEFORE.format(previous=x.name)
    elif x is not None and y != x:
        text = TOLD["took"].format(agent=x.name, **fill)
    elif after.assigned_by is not None and after.assigned_by != before.assigned_by:
        text = TOLD["assigned"].format(agent=y.name, **fill)
    elif after.text != before.text:
        text = TOLD["changed"].format(agent=y.name, **fill)
    elif before.assigned_by is not None and after.assigned_by is None:
        text = TOLD["released"].format(agent=y.name, **fill)
    else:
        return
    messaging.post_from_system(pj, text, {aid: "normal" if actor.kind == "agent" and actor.person_id == m.person_id
                                          else "important" for aid, m in concerned.items()})


# --------------------------------------------------------------------------- members that leave

def members_changed(pj: Project, by: Actor) -> None:
    """After members left groups or the project: a task whose responsible member is no longer in its group stays,
    with nobody responsible and no lock (an agent that is still here is told, with `by` as the actor); a task
    locked by a person who left is unlocked; the tasks of a group that is gone go with it."""
    actor = messaging.person_member(pj, by.person_id)
    lost = pj.db.execute("SELECT * FROM tasks t WHERE responsible_kind IS NOT NULL AND NOT EXISTS (SELECT 1 FROM "
                         "group_members m WHERE m.group_id = t.group_id AND m.member_kind = t.responsible_kind "
                         "AND m.member_id = t.responsible_id) ORDER BY id").fetchall()
    told = [(r, _state(pj, r)) for r in lost]
    with pj.db:
        pj.db.execute("DELETE FROM tasks WHERE group_id NOT IN (SELECT id FROM groups)")
        pj.db.executemany("UPDATE tasks SET responsible_kind = NULL, responsible_id = NULL, assigned_by = NULL "
                          "WHERE id = ?", [(r["id"],) for r in lost])
        pj.db.execute("UPDATE tasks SET assigned_by = NULL WHERE assigned_by IS NOT NULL "
                      "AND assigned_by NOT IN (SELECT person_id FROM people)")
    for r, before in told:
        if pj.db.execute("SELECT 1 FROM tasks WHERE id = ?", (r["id"],)).fetchone():
            util.log("task_changed", project=pj.slug, task=r["id"], by=actor.name)
            _tell(pj, actor, r["id"], _group_name(pj, r["group_id"]), before, State(r["text"], None, None))


# --------------------------------------------------------------------------- notices of presence

def presence_text(pj: Project, a: sqlite3.Row, online: bool) -> str:
    """'<name> is online.' / '... offline.', followed by the agent's tasks when it is responsible for any."""
    first = messaging.NOTICE[online].format(name=a["name"])
    rows = pj.db.execute("SELECT t.id, t.text, g.name AS grp FROM tasks t JOIN groups g ON g.id = t.group_id "
                         "WHERE t.responsible_kind = 'agent' AND t.responsible_id = ? ORDER BY t.id", (a["id"],)).fetchall()
    if not rows:
        return first
    lines = [f"{r['id']} [{r['grp']}] {clip(r['text'])}" for r in rows[:NOTICE_TASKS]]
    if len(rows) > NOTICE_TASKS:
        lines.append(f"and {len(rows) - NOTICE_TASKS} more.")
    return first + " Its tasks:\n" + "\n".join(lines)


def assigners(pj: Project, a: sqlite3.Row) -> set[int]:
    """The people who locked one of the agent's tasks."""
    return {r[0] for r in pj.db.execute("SELECT DISTINCT assigned_by FROM tasks WHERE responsible_kind = 'agent' "
                                        "AND responsible_id = ? AND assigned_by IS NOT NULL", (a["id"],))}
