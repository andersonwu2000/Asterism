"""Who is online. Only the server process knows which polls are open, so that lives in memory; the time of
the latest poll is also written to the database, so a restart does not flip everyone offline before their
programs reconnect.

Online, the one definition every part of the server uses: the agent is bound to a session, it is not held
offline (`unanswered` or `silent`, until its session calls a tool), and
- a local agent (Claude Code, Codex): either its session has a presence poll of its own open, or had one
  less than ASTERISM_OFFLINE_AFTER_S ago (the per-session API); or the credential its session came
  through has a computer poll open, or had one less than ASTERISM_OFFLINE_AFTER_S ago, and the bound
  session is in the list of sessions that computer reported (the resident program);
- a connector agent (ChatGPT): it has a live event subscription.

A local agent's deliveries go out through one path only: the computer poll while via_computer() holds,
otherwise its own per-session poll.

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
# Computer polls: (project, credential id) -> how many are open, and the events that wake them.
_computers: dict[tuple[str, int], int] = defaultdict(int)
_computer_wakers: dict[tuple[str, int], set[asyncio.Event]] = defaultdict(set)
_kick: asyncio.Event | None = None


def held(a: sqlite3.Row) -> bool:
    return a["offline_reason"] in HOLDS


def busy(db: sqlite3.Connection, a: sqlite3.Row) -> bool:
    """The agent holds a task; idle is not busy. The one definition every rule that needs it calls (notices,
    channel messages without a mention). There is no task table yet, so no agent is busy."""
    return False


def subscribed(db: sqlite3.Connection, agent_id: int) -> bool:
    return db.execute("SELECT 1 FROM subscriptions WHERE agent_id = ? AND expires > ?",
                      (agent_id, util.now())).fetchone() is not None


def polling(slug: str, a: sqlite3.Row) -> bool:
    return bool(a["session"]) and _open.get((slug, a["id"], a["session"]), 0) > 0


def computer_connected(slug: str, cred_id: int | None, db: sqlite3.Connection) -> bool:
    """The computer behind this credential has its connection open, or had it less than
    ASTERISM_OFFLINE_AFTER_S ago; a revoked credential is never connected."""
    if not cred_id:
        return False
    r = db.execute("SELECT last_poll FROM credentials WHERE id = ? AND revoked IS NULL", (cred_id,)).fetchone()
    if r is None:
        return False
    if _computers.get((slug, cred_id), 0) > 0:
        return True
    return bool(r["last_poll"]) and util.now() - r["last_poll"] < config.get().offline_after_s


def reported(db: sqlite3.Connection, cred_id: int | None, session: str | None) -> bool:
    """The computer behind this credential said it can wake this session."""
    return bool(cred_id and session) and db.execute(
        "SELECT 1 FROM computer_sessions WHERE credential_id = ? AND session = ?", (cred_id, session)).fetchone() is not None


def via_computer(slug: str, a: sqlite3.Row, db: sqlite3.Connection) -> bool:
    """The agent's deliveries go out through its computer's connection rather than its own poll."""
    return a["kind"] != "chatgpt" and computer_connected(slug, a["credential_id"], db) \
        and reported(db, a["credential_id"], a["session"])


OFFLINE_BECAUSE = ("not_bound", "no_computer", "session_closed", "no_subscription", "unanswered", "silent")


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
    if computer_connected(slug, a["credential_id"], db):
        return None if reported(db, a["credential_id"], a["session"]) else "session_closed"
    return "no_computer"


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


def computer_opened(slug: str, cred_id: int, waker: asyncio.Event) -> None:
    _computers[(slug, cred_id)] += 1
    _computer_wakers[(slug, cred_id)].add(waker)


def computer_closed(slug: str, cred_id: int, waker: asyncio.Event) -> None:
    key = (slug, cred_id)
    _computers[key] -= 1
    if _computers[key] <= 0:
        del _computers[key]
    _computer_wakers[key].discard(waker)
    if not _computer_wakers[key]:
        del _computer_wakers[key]
    kick()


def computer_open(slug: str, cred_id: int) -> bool:
    return _computers.get((slug, cred_id), 0) > 0


def computer_changed(slug: str, cred_id: int) -> None:
    """Make the open computer polls of this credential look again (its session list changed, it was revoked)."""
    for w in list(_computer_wakers.get((slug, cred_id), ())):
        w.set()
    kick()


def binding_changed(slug: str, agent_id: int) -> None:
    """End the open polls of an agent whose session was unbound, replaced or removed; the computer polls of
    the project look again at which agents they serve."""
    for w in list(_wakers.get((slug, agent_id), ())):
        w.set()
    for (s, _), ws in list(_computer_wakers.items()):
        if s == slug:
            for w in list(ws):
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
