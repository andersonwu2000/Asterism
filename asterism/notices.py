"""Changes of an agent's presence: holding it offline (`unanswered`, `silent`), bringing it back, and the one
notice per change that the system posts in #general.

sync() compares what presence says now with what was last announced (agents.announced, kept in the
database so a restart neither repeats nor loses a change) and posts the notice when they differ. It is
called where a change happens (poll opened, leave, subscribe, a tool call ending a hold) and, for the
changes that time makes (no poll any more, a subscription expired, a grace that ended), by the background task.
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
    """A session that only left its computer's list (`session_closed`) is offline at once for delivery, but
    its going is announced only once ASTERISM_NOTICE_GRACE_S has passed without it coming back
    (agents.quiet_since holds when that started); a session back in time is neither announced nor logged.
    Every other way of going offline is announced at once."""
    a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if a is None:
        return
    because = presence.offline_because(pj.slug, a, pj.db)
    online = because is None
    if a["announced"] == 1 and because == "session_closed":
        if a["quiet_since"] is None:
            with pj.db:
                pj.db.execute("UPDATE agents SET quiet_since = ? WHERE id = ?", (util.now(), agent_id))
            presence.kick()             # the background task looks again when the grace ends
            return
        if util.now() - a["quiet_since"] < config.get().notice_grace_s:
            return
    if a["quiet_since"] is not None:    # back within the grace, announced now, or gone another way
        with pj.db:
            pj.db.execute("UPDATE agents SET quiet_since = NULL WHERE id = ?", (agent_id,))
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


def online_now(pj: Project, agent_ids: list[int]) -> dict[int, bool]:
    """agent id -> online, taken before a change that settle() then looks at."""
    out = {}
    for aid in agent_ids:
        a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (aid,)).fetchone()
        if a is not None:
            out[aid] = presence.is_online(pj.slug, a, pj.db)
    return out


def settle(pj: Project, before: dict[int, bool]) -> None:
    """After a change that may have brought agents online without a poll of their own opening (a computer
    connected, a session reported again, a session bound): an agent that was offline and is online now gets
    what a returning agent gets when its own poll opens (its waiting normal-level deliveries are dropped),
    and each change is announced."""
    for aid, was in before.items():
        a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (aid,)).fetchone()
        if a is None:
            continue
        if not was and presence.is_online(pj.slug, a, pj.db):
            messaging.drop_unheard(pj, messaging.agent_member(a))
        sync(pj, aid)


def sync_computer(pj: Project, cred_id: int) -> None:
    """Write the change of a computer's connection to the log, once per change. When it goes away, the
    per-session polls of its agents (if any) are woken: deliveries go out through them from now on."""
    r = pj.db.execute("SELECT connected FROM credentials WHERE id = ?", (cred_id,)).fetchone()
    if r is None:
        return
    now = presence.computer_connected(pj.slug, cred_id, pj.db)
    if bool(r["connected"]) == now:
        return
    with pj.db:
        pj.db.execute("UPDATE credentials SET connected = ? WHERE id = ?", (int(now), cred_id))
    util.log("computer_connected" if now else "computer_disconnected", project=pj.slug, credential=cred_id)
    if not now:
        for a in pj.db.execute("SELECT id FROM agents WHERE credential_id = ?", (cred_id,)).fetchall():
            messaging.notify(pj.slug, a["id"])


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
