"""Scheduled messages: a text a person has posted in their name at a time, once or every so often.

A run is an ordinary message from the creator (messaging.post_scheduled): what differs is that mentions are
not looked for, every reader's level comes from the schedule, and one schedule never stacks the answers an
agent owes. A repeating schedule runs on its grid start_at + k * every_s; a time missed (the server was down,
the schedule was paused, or it was made with a start in the past) is made up for by one run, then it is back
on its grid. A schedule that runs once is removed when it has run. One that cannot run (its creator lost the
permissions, or its place is no longer one they can post to) is paused with the reason until somebody resumes
or removes it. The background task (upkeep) runs what is due and sleeps until next_due.
"""
from __future__ import annotations

import datetime
import math
import sqlite3
from typing import Any

from . import config, messaging, presence, projects, util
from .errors import bad_request, conflict, forbidden, not_found
from .messaging import Member
from .projects import Actor, Project

NEEDS = ("create_schedule",)   # and post where it posts: a channel's own (an override may grant it), else the project's
CONTENT = ("to", "text", "level", "start_at", "every_s")


# --------------------------------------------------------------------------- reading

def _iso(t: float | None) -> str | None:
    return util.iso(t) if t is not None else None


def view(pj: Project, r: sqlite3.Row) -> dict[str, Any]:
    return {"id": r["id"], "by": projects.person_name(pj, r["person_id"]), "to": r["to_name"], "text": r["text"],
            "level": r["level"], "start_at": _iso(r["start_at"]), "every_s": r["every_s"], "next_at": _iso(r["next_at"]),
            "paused": bool(r["paused"]), "paused_because": r["paused_because"], "last_message": r["last_message"]}


def listing(pj: Project, actor: Actor) -> dict[str, Any]:
    projects.require(pj, actor, "read", "Reading the project needs the read permission.")
    shut = {"#" + n for n in messaging.channel_names(pj)} \
        - messaging.readable(pj, messaging.person_member(pj, actor.person_id))
    return {"schedules": [view(pj, r) for r in pj.db.execute("SELECT * FROM schedules ORDER BY id")
                          if r["place"] not in shut]}


def _row(pj: Project, sid: int) -> sqlite3.Row:
    r = pj.db.execute("SELECT * FROM schedules WHERE id = ?", (sid,)).fetchone()
    if r is None:
        raise not_found(f"There is no schedule {sid}.")
    return r


# --------------------------------------------------------------------------- checks

def _level(v: Any) -> str:
    if v not in messaging.LEVELS:
        raise bad_request("bad_request", "level must be important, normal or muted.")
    return v


def _start(v: Any) -> float:
    try:
        at = datetime.datetime.fromisoformat(v) if isinstance(v, str) else None
    except ValueError:
        at = None
    if at is None or at.tzinfo is None:
        raise bad_request("bad_request", "start_at must be an ISO 8601 time with Z or an offset, such as "
                                         "2026-11-15T12:00:00Z.")
    return at.timestamp()


def _every(v: Any) -> int | None:
    if v is None:
        return None
    least = config.get().schedule_min_every_s
    if not isinstance(v, int) or isinstance(v, bool) or v < least:
        raise bad_request("bad_request", f"every_s is the number of seconds between runs, at least {least:g}; "
                                         f"leave it out (or null) to run once.")
    return v


def _place(pj: Project, creator: Member, to: Any) -> tuple[str, str]:
    """(the place key, `to` as shown) for a place the creator could post to now; the refusals of posting."""
    place, other = messaging.resolve_place(pj, creator, to)
    if not messaging.may_post_in(pj, creator, place):
        raise forbidden("Posting messages needs the post permission.")
    return place, (place if other is None else other.name)


def _creator(pj: Project, r: sqlite3.Row) -> Member | None:
    p = pj.db.execute("SELECT * FROM people WHERE person_id = ?", (r["person_id"],)).fetchone()
    return Member("person", p["person_id"], p["person_id"], p["name"]) if p else None


def _cannot_run(pj: Project, r: sqlite3.Row) -> str | None:
    """Why the schedule cannot run now (permission, target), or None."""
    creator = _creator(pj, r)
    if creator is None or not set(NEEDS) <= projects.person_permissions(pj, creator.id):
        return "permission"
    place = r["place"]
    if place.startswith("#"):
        if pj.db.execute("SELECT 1 FROM channels WHERE name = ?", (place[1:],)).fetchone() is None:
            return "target"
        # The channel is there, but its permissions no longer let the creator read or post in it.
        ok = {"read", "post"} <= projects.channel_access(pj, "person", creator.id).get(place[1:], set())
        return None if ok else "permission"
    else:
        other = messaging._member_by_key(pj, messaging._other_key(place, creator) or "")
        if other is None or not messaging.may_talk_privately(creator, other):
            return "target"
        return None if messaging.may_post_in(pj, creator, place) else "permission"


def _why(pj: Project, r: sqlite3.Row, because: str) -> str:
    name = projects.person_name(pj, r["person_id"])
    if because == "permission" and set(NEEDS) <= projects.person_permissions(pj, r["person_id"]):
        return (f"Schedule {r['id']} cannot run: the permissions of {r['to_name']} no longer let {name} post there. "
                f"Remove it, give it another `to`, or let {name} post in {r['to_name']} first.")
    if because == "permission":
        return (f"Schedule {r['id']} cannot run: {name} no longer holds the create_schedule permission. "
                f"Remove it, or give {name} that permission first.")
    return (f"Schedule {r['id']} cannot run: {name} can no longer post to {r['to_name']}. Give it another `to` in the "
            f"same request to resume it.")


def _first_at(start: float, every: int | None, now: float) -> float:
    """When a schedule whose times were (re)set runs first: at start_at; when that is past, at once if it runs
    once, else at the first time of its grid that is not past."""
    if start >= now or every is None:
        return start
    return start + math.ceil((now - start) / every) * every


def _after_run(start: float, every: int, t: float) -> float:
    """The first time of the grid after a run at `t`: what was missed before it was made up for by that run."""
    return start + (math.floor((t - start) / every) + 1) * every


# --------------------------------------------------------------------------- changing

def create(pj: Project, actor: Actor, body: dict[str, Any]) -> dict[str, Any]:
    projects.require(pj, actor, "create_schedule", "Scheduling messages needs the create_schedule permission.")
    creator = messaging.person_member(pj, actor.person_id)
    place, to = _place(pj, creator, body.get("to"))
    text = messaging.check_text(body.get("text"))
    level = _level(body.get("level"))
    start = _start(body.get("start_at"))
    every = _every(body.get("every_s"))
    t = util.now()
    with pj.db:
        sid = pj.db.execute("INSERT INTO schedules (person_id, place, to_name, text, level, start_at, every_s, next_at, "
                            "created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (actor.person_id, place, to, text, level, start, every, start, t)).lastrowid
    util.log("schedule_made", project=pj.slug, schedule=sid, by=actor.person_id)
    presence.kick()
    return {"schedule": view(pj, _row(pj, sid))}


def change(pj: Project, actor: Actor, sid: int, body: dict[str, Any]) -> dict[str, Any]:
    """The creator changes what it says, where and when; the creator and anyone with manage_members pause and
    resume it."""
    r = _row(pj, sid)
    content = [k for k in CONTENT if k in body]
    if not content and "paused" not in body:
        raise bad_request("bad_request", "Say what to change: to, text, level, start_at, every_s or paused.")
    mine = r["person_id"] == actor.person_id
    name = projects.person_name(pj, r["person_id"])
    if content and not mine:
        raise forbidden(f"Only {name}, who made schedule {sid}, changes what it says, where and when.")
    if not mine and "manage_members" not in projects.permissions(pj, actor):
        raise forbidden(f"Only {name}, who made schedule {sid}, and the members' managers pause or resume it.")
    paused = body.get("paused", bool(r["paused"]))
    if not isinstance(paused, bool):
        raise bad_request("bad_request", "paused must be true or false.")
    cols: dict[str, Any] = {}
    if content:
        projects.require(pj, actor, "create_schedule", "Changing a schedule needs the create_schedule permission.")
        if "to" in body:
            cols["place"], cols["to_name"] = _place(pj, messaging.person_member(pj, actor.person_id), body["to"])
        if "text" in body:
            cols["text"] = messaging.check_text(body["text"])
        if "level" in body:
            cols["level"] = _level(body["level"])
        if "start_at" in body:
            cols["start_at"] = _start(body["start_at"])
        if "every_s" in body:
            cols["every_s"] = _every(body["every_s"])
        if "start_at" in cols or "every_s" in cols:
            cols["next_at"] = _first_at(cols.get("start_at", r["start_at"]), cols.get("every_s", r["every_s"]),
                                        util.now())
    if paused:
        cols["paused"] = 1
        if not r["paused"]:
            cols["paused_because"] = None
    elif r["paused"] or "place" in cols:
        after = {**dict(r), **cols}
        because = _cannot_run(pj, after)
        if because is not None:
            raise conflict(_why(pj, after, because))
        cols.update(paused=0, paused_because=None)
    if cols:
        sets = ", ".join(f"{k} = ?" for k in cols)          # keys are this function's own column names
        with pj.db:
            pj.db.execute(f"UPDATE schedules SET {sets} WHERE id = ?", (*cols.values(), sid))
        util.log("schedule_changed", project=pj.slug, schedule=sid, by=actor.person_id)
        presence.kick()
    return {"schedule": view(pj, _row(pj, sid))}


def remove(pj: Project, actor: Actor, sid: int) -> dict[str, Any]:
    r = _row(pj, sid)
    if r["person_id"] != actor.person_id and "manage_members" not in projects.permissions(pj, actor):
        raise forbidden(f"Only {projects.person_name(pj, r['person_id'])}, who made schedule {sid}, and the members' "
                        f"managers remove it.")
    with pj.db:
        pj.db.execute("DELETE FROM schedules WHERE id = ?", (sid,))
    util.log("schedule_removed", project=pj.slug, schedule=sid, by=actor.person_id)
    presence.kick()
    return {"removed": sid}


# --------------------------------------------------------------------------- running (the background task)

def next_due(pj: Project) -> list[float]:
    return [r[0] for r in pj.db.execute("SELECT next_at FROM schedules WHERE paused = 0 AND next_at IS NOT NULL")]


def due(pj: Project, t: float) -> list[int]:
    return [r[0] for r in pj.db.execute("SELECT id FROM schedules WHERE paused = 0 AND next_at <= ? ORDER BY next_at, id",
                                        (t,))]


def run(pj: Project, sid: int, t: float) -> None:
    """Run one schedule that is due: post it, or pause it with the reason it cannot run."""
    r = pj.db.execute("SELECT * FROM schedules WHERE id = ? AND paused = 0", (sid,)).fetchone()
    if r is None:
        return
    because = _cannot_run(pj, r)
    if because is not None:
        with pj.db:
            pj.db.execute("UPDATE schedules SET paused = 1, paused_because = ? WHERE id = ?", (because, sid))
        util.log("schedule_paused", project=pj.slug, schedule=sid, because=because)
        return

    def after(mid: int) -> None:            # in the message's own transaction: a run is posted once
        if r["every_s"] is None:
            pj.db.execute("DELETE FROM schedules WHERE id = ?", (sid,))
        else:
            pj.db.execute("UPDATE schedules SET next_at = ?, last_message = ? WHERE id = ?",
                          (_after_run(r["start_at"], r["every_s"], t), mid, sid))
    mid = messaging.post_scheduled(pj, _creator(pj, r), r["place"], r["text"], r["level"], sid, after)
    util.log("schedule_run", project=pj.slug, schedule=sid, message=mid)
