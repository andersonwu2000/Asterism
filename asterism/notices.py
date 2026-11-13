"""Changes of an agent's presence: holding it offline (`unanswered`, `silent`), bringing it back, and the one
notice per change that the system posts in #general.

sync() compares what presence says now with what was last announced (agents.announced, kept in the
database so a restart neither repeats nor loses a change) and posts the notice when they differ. It is
called where a change happens (poll opened, leave, subscribe, a tool call ending a hold) and, for the
changes that time makes (no poll any more, a subscription expired), by the background task.
"""
from __future__ import annotations

import sqlite3

from . import config, messaging, presence, util
from .projects import Project


def _reason(a: sqlite3.Row) -> str:
    if not a["session"]:
        return "left"
    if presence.held(a):
        return a["offline_reason"]
    return "unsubscribed" if a["kind"] == "chatgpt" else "gone"


def sync(pj: Project, agent_id: int) -> None:
    a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if a is None:
        return
    online = presence.is_online(pj.slug, a, pj.db)
    if a["announced"] is not None and bool(a["announced"]) == online:
        return
    with pj.db:
        pj.db.execute("UPDATE agents SET announced = ? WHERE id = ?", (int(online), agent_id))
    if a["announced"] is None:          # first look at an agent from an earlier version: nothing to announce
        return
    if online:
        util.log("agent_online", project=pj.slug, agent=a["name"])
    else:
        util.log("agent_offline", project=pj.slug, agent=a["name"], reason=_reason(a))
    messaging.post_notice(pj, a, online)


def hold(pj: Project, agent_id: int, reason: str) -> None:
    """Make the agent offline until its session calls a tool, whatever its poll or subscription does."""
    with pj.db:
        pj.db.execute("UPDATE agents SET offline_reason = ? WHERE id = ? AND offline_reason IS NULL", (reason, agent_id))
    sync(pj, agent_id)


def release(pj: Project, a: sqlite3.Row) -> None:
    """A tool call ends a hold: what was never acknowledged is handed out again from the start, and the
    reminder clock of what is still unanswered starts again."""
    t = util.now()
    with pj.db:
        pj.db.execute("UPDATE agents SET offline_reason = NULL WHERE id = ?", (a["id"],))
        pj.db.execute("UPDATE deliveries SET state = 'pending', attempts = 0 WHERE agent_id = ? AND state = 'out'",
                      (a["id"],))
        pj.db.execute("UPDATE followups SET period = ?, due = ?, reminders = 0 WHERE agent_id = ? AND answered IS NULL",
                      (t, t + config.get().remind_after_s, a["id"]))
    sync(pj, a["id"])
    messaging.notify(pj.slug, a["id"])
