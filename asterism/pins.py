"""Pins: at most ten things a channel keeps in view, a file of the repository (its path) or a message of that
channel. People with `create_channel` pin and unpin; agents read them in `whoami`. Nobody is told about a pin:
it is something to look up.
"""
from __future__ import annotations

import sqlite3
import unicodedata
import urllib.parse
from typing import Any

from . import messaging, projects, tasks, util
from .errors import bad_request, conflict, not_found
from .projects import Actor, Project

MOST = 10
PATH_MAX = 300
BAD_PATH = ("A path is a file of the repository: 1 to 300 characters, written with '/', without a leading '/', and "
            "without empty, '.' or '..' parts.")


def _url(pj: Project, path: str) -> str:
    repo = projects.info(pj)["repo"].rstrip("/")
    return repo + "/blob/HEAD/" + "/".join(urllib.parse.quote(seg, safe="") for seg in path.split("/"))


def _view(pj: Project, p: sqlite3.Row, names: dict[int, str]) -> dict[str, Any]:
    if p["by_person"] not in names:
        names[p["by_person"]] = projects.person_name(pj, p["by_person"])
    if p["path"] is not None:
        return {"id": p["id"], "kind": "file", "path": p["path"], "url": _url(pj, p["path"]), "by": names[p["by_person"]]}
    m = pj.db.execute("SELECT sender_name, text FROM messages WHERE id = ?", (p["message_id"],)).fetchone()
    return {"id": p["id"], "kind": "message", "message": p["message_id"], "from": m["sender_name"] if m else None,
            "text": tasks.clip(m["text"]) if m else "", "by": names[p["by_person"]]}


def by_channel(pj: Project) -> dict[str, list[dict[str, Any]]]:
    """channel name -> its pins as people get them, oldest first."""
    out: dict[str, list[dict[str, Any]]] = {}
    names: dict[int, str] = {}
    for p in pj.db.execute("SELECT * FROM pins ORDER BY id"):
        out.setdefault(p["channel"], []).append(_view(pj, p, names))
    return out


def short(pj: Project) -> dict[str, list[dict[str, Any]]]:
    """channel name -> its pins as agents get them in whoami: {"file": path} or {"message": id}."""
    out: dict[str, list[dict[str, Any]]] = {}
    for p in pj.db.execute("SELECT * FROM pins ORDER BY id"):
        out.setdefault(p["channel"], []).append({"file": p["path"]} if p["path"] is not None else {"message": p["message_id"]})
    return out


def _channel(pj: Project, actor: Actor, name: str) -> str:
    """A channel the person may read (any other does not exist for them)."""
    me = messaging.person_member(pj, actor.person_id)
    if name not in messaging.channel_names(pj, me):
        raise messaging._no_channel(pj, "#" + name, me)
    return name


def _may_pin(pj: Project, actor: Actor) -> None:
    projects.require(pj, actor, "create_channel", "Pinning and unpinning need the create_channel permission.")


def _path(v: Any) -> str:
    if not isinstance(v, str):
        raise bad_request("bad_request", BAD_PATH)
    v = v.strip()
    if not 1 <= len(v) <= PATH_MAX or v.startswith("/") or "\\" in v \
            or any(unicodedata.category(c) == "Cc" for c in v) or any(s in ("", ".", "..") for s in v.split("/")):
        raise bad_request("bad_request", BAD_PATH)
    return v


def add(pj: Project, actor: Actor, channel: str, body: dict[str, Any]) -> dict[str, Any]:
    _may_pin(pj, actor)
    _channel(pj, actor, channel)
    path, mid = body.get("path"), body.get("message")
    if (path is None) == (mid is None):
        raise bad_request("bad_request", 'Pin one thing: {"path": "<a file of the repository>"} or {"message": <id>}.')
    if path is not None:
        path = _path(path)
        same = pj.db.execute("SELECT 1 FROM pins WHERE channel = ? AND path = ?", (channel, path)).fetchone()
        what = path
    else:
        me = messaging.person_member(pj, actor.person_id)
        row = messaging._message(pj, me, messaging._int(mid, "message", required=True), "")
        if row["place"] != "#" + channel:
            where = row["place"] if row["place"].startswith("#") else "a private conversation"
            raise bad_request("bad_request", f"Message {row['id']} is in {where}, not in #{channel}. A channel pins "
                                             f"its own messages.")
        mid = row["id"]
        same = pj.db.execute("SELECT 1 FROM pins WHERE channel = ? AND message_id = ?", (channel, mid)).fetchone()
        what = f"Message {mid}"
    if same:
        raise conflict(f"{what} is pinned in #{channel} already.")
    if pj.db.execute("SELECT count(*) FROM pins WHERE channel = ?", (channel,)).fetchone()[0] >= MOST:
        raise conflict(f"#{channel} has {MOST} pins, which is the most a channel holds. Remove one first.")
    with pj.db:
        pid = pj.db.execute("INSERT INTO pins (channel, path, message_id, by_person, created) VALUES (?, ?, ?, ?, ?)",
                            (channel, path, mid if path is None else None, actor.person_id, util.now())).lastrowid
    util.log("pinned", project=pj.slug, channel=channel, pin=pid, by=actor.person_id)
    return {"pin": _view(pj, pj.db.execute("SELECT * FROM pins WHERE id = ?", (pid,)).fetchone(), {})}


def remove(pj: Project, actor: Actor, channel: str, pid: int) -> dict[str, Any]:
    _may_pin(pj, actor)
    _channel(pj, actor, channel)
    with pj.db:
        gone = pj.db.execute("DELETE FROM pins WHERE id = ? AND channel = ?", (pid, channel)).rowcount
    if not gone:
        raise not_found(f"There is no pin {pid} in #{channel}.")
    util.log("unpinned", project=pj.slug, channel=channel, pin=pid, by=actor.person_id)
    return {"removed": pid}
