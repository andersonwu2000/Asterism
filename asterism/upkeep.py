"""The one background task: everything time makes due.

- reminders for important messages an agent has not answered, and `silent` for an agent that did nothing
  in a whole reminder period;
- `unanswered` for an agent whose helper did not acknowledge a delivery handed out twice;
- events to the connector agents (sent in tasks of their own) and their second attempts;
- expired event subscriptions;
- the presence notices, including the change the 1a window makes (no poll for ASTERISM_OFFLINE_AFTER_S);
- the log lines of a computer's connection going away (no computer poll for ASTERISM_OFFLINE_AFTER_S).

It runs one sweep over all projects, then sleeps until the earliest time something falls due or until it is
kicked (presence.kick: a message was sent, a poll ended, a binding changed, an event attempt finished). A
sweep has no await inside, so it runs as one unit on the event loop. A failure in one item is logged and the
sweep goes on with the next.
"""
from __future__ import annotations

import asyncio
from typing import Callable

from . import config, events, messaging, notices, presence, util
from .projects import Project
from .store import Store

LONGEST_SLEEP_S = 300.0         # a safety net: nothing should need it


def _guard(pj: Project, step: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - one item must not stop the others
        util.log("background_failed", project=pj.slug, step=step, error=type(e).__name__)


def _unanswered(pj: Project, t: float) -> None:
    """A local agent's delivery handed out twice and still not acknowledged a redelivery period later."""
    for r in pj.db.execute("SELECT DISTINCT d.agent_id FROM deliveries d JOIN agents a ON a.id = d.agent_id "
                           "WHERE a.kind != 'chatgpt' AND a.offline_reason IS NULL AND d.state = 'out' "
                           "AND d.attempts >= 2 AND d.handed_out <= ?",
                           (t - config.get().redeliver_after_s,)).fetchall():
        _guard(pj, "unanswered", lambda aid=r["agent_id"]: notices.hold(pj, aid, "unanswered"))


def _remind(pj: Project, f, t: float) -> None:
    """One follow-up that fell due: the first reminder; then another one if the agent called a tool in the
    period that ended, else the agent is offline (`silent`). While the agent is offline the clock waits."""
    period = config.get().remind_after_s
    a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (f["agent_id"],)).fetchone()
    if a is None:
        return
    if not presence.is_online(pj.slug, a, pj.db):
        with pj.db:
            pj.db.execute("UPDATE followups SET period = ?, due = ? WHERE agent_id = ? AND message_id = ?",
                          (t, t + period, f["agent_id"], f["message_id"]))
        return
    if f["reminders"] and not (a["last_tool"] and a["last_tool"] > f["period"]):
        notices.hold(pj, a["id"], "silent")
        return
    with pj.db:
        pj.db.execute("INSERT INTO deliveries (agent_id, kind, message_id, state, how, created) "
                      "VALUES (?, 'reminder', ?, 'pending', 'push', ?)", (a["id"], f["message_id"], t))
        pj.db.execute("UPDATE followups SET reminders = reminders + 1, period = ?, due = ? "
                      "WHERE agent_id = ? AND message_id = ?", (t, t + period, f["agent_id"], f["message_id"]))
    util.log("reminded", project=pj.slug, agent=a["name"], about=f["message_id"])
    messaging.notify(pj.slug, a["id"])


def _due_times(pj: Project) -> list[float]:
    s = config.get()
    out: list[float] = []
    for a in pj.db.execute("SELECT * FROM agents WHERE announced = 1 AND kind != 'chatgpt' AND session IS NOT NULL "
                           "AND offline_reason IS NULL AND last_poll IS NOT NULL"):
        if not presence.polling(pj.slug, a):
            out.append(a["last_poll"] + s.offline_after_s)
    # A session that left its computer's list is announced offline when the grace ends.
    out += [r[0] + s.notice_grace_s for r in pj.db.execute("SELECT quiet_since FROM agents WHERE quiet_since IS NOT NULL")]
    # A computer whose connection closed is disconnected (and its agents offline) a grace period later.
    for r in pj.db.execute("SELECT id, last_poll FROM credentials WHERE connected = 1 AND revoked IS NULL "
                           "AND last_poll IS NOT NULL"):
        if not presence.computer_open(pj.slug, r["id"]):
            out.append(r["last_poll"] + s.offline_after_s)
    out += [r[0] + s.redeliver_after_s for r in pj.db.execute(
        "SELECT d.handed_out FROM deliveries d JOIN agents a ON a.id = d.agent_id WHERE a.kind != 'chatgpt' "
        "AND a.offline_reason IS NULL AND d.state = 'out' AND d.attempts >= 2")]
    out += [r[0] for r in pj.db.execute("SELECT due FROM followups WHERE answered IS NULL AND due IS NOT NULL")]
    return out + events.next_due(pj)


def sweep(store: Store) -> float | None:
    """Do what is due now; return when something falls due next (None: nothing is waiting)."""
    t = util.now()
    due: list[float] = []
    for slug in store.slugs():
        db = store.project(slug)
        if db is None:
            continue
        pj = Project(store, slug, db)
        _guard(pj, "expire", lambda: events.expire(pj, t))
        _guard(pj, "unanswered", lambda: _unanswered(pj, t))
        for f in pj.db.execute("SELECT * FROM followups WHERE answered IS NULL AND due <= ? ORDER BY due", (t,)).fetchall():
            _guard(pj, "remind", lambda f=f: _remind(pj, f, t))
        for r in pj.db.execute("SELECT id FROM credentials WHERE connected = 1").fetchall():
            _guard(pj, "computer", lambda cid=r["id"]: notices.sync_computer(pj, cid))
        for r in pj.db.execute("SELECT id FROM agents").fetchall():
            _guard(pj, "presence", lambda aid=r["id"]: notices.sync(pj, aid))
        _guard(pj, "events", lambda: events.launch_due(pj, t))
        try:
            due += _due_times(pj)
        except Exception as e:  # noqa: BLE001
            util.log("background_failed", project=slug, step="due", error=type(e).__name__)
    # Anything at or before the start of this sweep was handled or waits for a change, which kicks us.
    later = [x for x in due if x > t]
    return min(later) if later else None


async def run(store: Store) -> None:
    kicked = presence.kicker()
    while True:
        kicked.clear()
        try:
            nxt = sweep(store)
        except Exception as e:  # noqa: BLE001 - the task must survive whatever happens
            util.log("background_failed", step="sweep", error=type(e).__name__)
            nxt = None
        wait = LONGEST_SLEEP_S if nxt is None else min(LONGEST_SLEEP_S, max(0.01, nxt - util.now()))
        try:
            await asyncio.wait_for(kicked.wait(), wait)
        except asyncio.TimeoutError:
            pass
