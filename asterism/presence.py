"""Who is online. Only the server process knows which presence polls are open, so that lives in memory;
the time of the latest poll is also written to the database, so a restart does not flip everyone offline
before their helpers reconnect.

Online, the one definition every part of the server uses: the agent is bound to a session, it is not held
offline (`unanswered` or `silent`, until its session calls a tool), and
- a local agent (Claude Code, Codex): its session has a presence poll open, or had one less than
  ASTERISM_OFFLINE_AFTER_S ago;
- a connector agent (ChatGPT): it has a live event subscription.

The background task (upkeep) is woken through kick() whenever something may have changed what is due.
"""
from __future__ import annotations

import asyncio
import sqlite3
from collections import defaultdict

from . import config, util

HOLDS = ("unanswered", "silent")

_open: dict[tuple[str, int, str], int] = defaultdict(int)
_wakers: dict[tuple[str, int], set[asyncio.Event]] = defaultdict(set)
_kick: asyncio.Event | None = None


def held(a: sqlite3.Row) -> bool:
    return a["offline_reason"] in HOLDS


def subscribed(db: sqlite3.Connection, agent_id: int) -> bool:
    return db.execute("SELECT 1 FROM subscriptions WHERE agent_id = ? AND expires > ?",
                      (agent_id, util.now())).fetchone() is not None


def polling(slug: str, a: sqlite3.Row) -> bool:
    return bool(a["session"]) and _open.get((slug, a["id"], a["session"]), 0) > 0


OFFLINE_BECAUSE = ("not_bound", "no_helper", "no_subscription", "unanswered", "silent")


def offline_because(slug: str, a: sqlite3.Row, db: sqlite3.Connection) -> str | None:
    """Why the agent is offline (one of OFFLINE_BECAUSE), or None when it is online."""
    if not a["session"]:
        return "not_bound"
    if held(a):
        return a["offline_reason"]
    if a["kind"] == "chatgpt":
        return None if subscribed(db, a["id"]) else "no_subscription"
    if polling(slug, a) or (a["last_poll"] and util.now() - a["last_poll"] < config.get().offline_after_s):
        return None
    return "no_helper"


def is_online(slug: str, a: sqlite3.Row, db: sqlite3.Connection) -> bool:
    return offline_because(slug, a, db) is None


def opened(slug: str, agent_id: int, session: str, waker: asyncio.Event) -> None:
    _open[(slug, agent_id, session)] += 1
    _wakers[(slug, agent_id)].add(waker)


def closed(slug: str, agent_id: int, session: str, waker: asyncio.Event) -> None:
    key = (slug, agent_id, session)
    _open[key] -= 1
    if _open[key] <= 0:
        del _open[key]
    _wakers[(slug, agent_id)].discard(waker)
    if not _wakers[(slug, agent_id)]:
        del _wakers[(slug, agent_id)]
    kick()


def binding_changed(slug: str, agent_id: int) -> None:
    """End the open polls of an agent whose session was unbound, replaced or removed."""
    for w in list(_wakers.get((slug, agent_id), ())):
        w.set()
    kick()


def kicker() -> asyncio.Event:
    """The event the background task waits on (created inside the running loop)."""
    global _kick
    _kick = asyncio.Event()
    return _kick


def kick() -> None:
    if _kick is not None:
        _kick.set()
