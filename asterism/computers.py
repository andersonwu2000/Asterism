"""Computers: the agent invitation link that authorises one, and the one connection per computer and project
that the resident program holds for every agent whose session came through that computer's credential.

The connection is three calls with the computer's credential: the list of local sessions the program can wake
right now, a held poll that hands out the deliveries of all those agents, and the acknowledgements. The
delivery rules themselves (redelivery, holds, reminders, notices) are the ones of messaging and notices, per
agent; this module only decides which agents a computer serves.
"""
from __future__ import annotations

import asyncio
import sqlite3
from typing import Any, Awaitable, Callable

from . import agents, config, messaging, notices, presence, projects, util
from .agents import Caller
from .errors import ApiError, bad_request, forbidden, gone, invalid_credential
from .projects import Actor, Project
from .store import Store

POLL_MAX_S = 100.0
SESSIONS_MAX = 1000
LOCAL = "local:"

# Agent-facing wording, word for word from the specification.
INVITE_TEXT = ('You are invited to join the Asterism project "{project}" as an agent of {person}.\n'
               "Run one command, the one for this computer:\n"
               "macOS or Linux: `curl -fsSL {url}/install.sh | sh -s -- {link}`\n"
               "Windows (PowerShell): `& ([scriptblock]::Create((irm {url}/install.ps1))) {link}`\n"
               "If your user gave you a name, add `--name <name>` at the end. The command tells you what to do next.")
EXPIRED = "This invitation link has expired or was already used. Ask your user for a new one."


# --------------------------------------------------------------------------- agent invitation links

def _link(slug: str, code: str) -> str:
    return f"{config.get().public_url}/{slug}/a/{code}"


def create_invite(pj: Project, actor: Actor) -> dict[str, Any]:
    """A single-use link, valid for ASTERISM_AGENT_INVITE_TTL_S, that authorises a computer in the
    member's name. Only its digest is kept."""
    if actor.agent_id is not None:
        raise forbidden("Agents cannot invite agents.")
    projects.require(pj, actor, "manage_own_agents", "Inviting agents needs the manage_own_agents permission.")
    code = util.new_secret()
    t, ttl = util.now(), config.get().agent_invite_ttl_s
    with pj.db:
        pj.db.execute("DELETE FROM agent_invites WHERE expires < ?", (t - 86400,))
        pj.db.execute("INSERT INTO agent_invites (digest, person_id, created, expires) VALUES (?, ?, ?, ?)",
                      (util.digest(code), actor.person_id, t, t + ttl))
    util.log("agent_invite_created", project=pj.slug, person=actor.person_id)
    return {"url": _link(pj.slug, code), "expires_in": int(ttl)}


def _usable(store: Store, slug: str, code: str) -> tuple[Project, sqlite3.Row, str]:
    """(project, invitation, the inviting member's name) for a link that can still be used; 410 otherwise.
    An unknown project answers like an unknown link."""
    db = store.project(slug)
    row = db.execute("SELECT * FROM agent_invites WHERE digest = ?", (util.digest(code),)).fetchone() if db else None
    member = db.execute("SELECT name FROM people WHERE person_id = ?", (row["person_id"],)).fetchone() if row else None
    if not row or row["used"] or row["expires"] < util.now() or not member:
        raise gone(EXPIRED)
    return Project(store, slug, db), row, member["name"]


def invite_text(store: Store, slug: str, code: str) -> str:
    """What the agent reads at the link. Reading does not use the link up."""
    pj, _, person = _usable(store, slug, code)
    return INVITE_TEXT.format(project=projects.info(pj)["name"], person=person, url=config.get().public_url,
                              link=_link(slug, code))


def redeem(store: Store, slug: str, code: str, credential: str | None, computer: Any, product: Any) -> dict[str, Any]:
    """Redeeming the link is the consent: the computer gets a credential of the inviting member, as an
    approved device request gives it. A computer already authorised for that member keeps its credential.
    The link is used up either way, except when the request is refused."""
    pj, row, person = _usable(store, slug, code)
    if product not in agents.LOCAL_KINDS:
        raise bad_request("bad_request", "product must be one of: " + ", ".join(agents.LOCAL_KINDS))
    label = util.clean_label(computer)
    if not label:
        raise bad_request("bad_request", "computer must name this computer.")
    held = pj.db.execute("SELECT * FROM credentials WHERE digest = ? AND revoked IS NULL AND kind = 'computer'",
                         (util.digest(credential),)).fetchone() if credential else None
    if held is not None and held["person_id"] != row["person_id"]:
        raise forbidden("This computer is authorised for another member; this link is for an agent of "
                        f"{person}. Ask {person} to run it on their own computer.")
    secret = None
    if held is not None:
        cred_id = held["id"]
    else:                               # none came, or one that is revoked or unknown: authorise afresh
        cred_id, secret = agents.issue_computer_credential(pj, row["person_id"], label, "invite")
    with pj.db:
        pj.db.execute("UPDATE agent_invites SET used = ?, credential_id = ?, computer = ?, product = ? WHERE digest = ?",
                      (util.now(), cred_id, label, product, row["digest"]))
    util.log("agent_invite_redeemed", project=slug, person=row["person_id"], credential=cred_id, computer=label,
             product=product)
    info = projects.info(pj)
    return {"credential": secret, "person": person, "project": {"name": info["name"], "slug": info["slug"]}}


# --------------------------------------------------------------------------- one connection per computer

def _computer(c: Caller) -> int:
    """The credential id of a computer's call; the call carries no session."""
    if c.pj.db.execute("SELECT 1 FROM credentials WHERE id = ? AND revoked IS NULL", (c.credential_id,)).fetchone() is None:
        raise invalid_credential()
    return c.credential_id


def _agents_of(pj: Project, cred_id: int) -> list[int]:
    return [r["id"] for r in pj.db.execute("SELECT id FROM agents WHERE credential_id = ?", (cred_id,))]


def report_sessions(c: Caller, sessions: Any) -> dict[str, Any]:
    """The complete list of local sessions the program can wake right now; it replaces the previous one."""
    cred_id = _computer(c)
    pj = c.pj
    if not isinstance(sessions, list) or len(sessions) > SESSIONS_MAX:
        raise bad_request("bad_request", f"sessions must be a list (at most {SESSIONS_MAX}) of {{session, product}}.")
    rows = {}
    for s in sessions:
        sid, product = (s.get("session"), s.get("product")) if isinstance(s, dict) else (None, None)
        if not isinstance(sid, str) or not agents.SESSION_RE.fullmatch(sid):
            raise bad_request("invalid_session", "Each session id must be 1 to 200 printable characters without spaces.")
        if product not in agents.LOCAL_KINDS:
            raise bad_request("bad_request", "product must be one of: " + ", ".join(agents.LOCAL_KINDS))
        rows[LOCAL + sid] = product
    before = notices.online_now(pj, _agents_of(pj, cred_id))
    with pj.db:
        pj.db.execute("DELETE FROM computer_sessions WHERE credential_id = ?", (cred_id,))
        pj.db.executemany("INSERT INTO computer_sessions (credential_id, session, product) VALUES (?, ?, ?)",
                          [(cred_id, sid, product) for sid, product in rows.items()])
    presence.computer_changed(pj.slug, cred_id)
    for aid in before:                  # a per-session poll of a session that left or joined the list looks again
        messaging.notify(pj.slug, aid)
    notices.settle(pj, before)
    return {}


def _served(pj: Project, cred_id: int) -> list[sqlite3.Row]:
    """The agents bound through this credential whose session the computer reported."""
    return pj.db.execute("SELECT a.* FROM agents a JOIN computer_sessions s ON s.credential_id = a.credential_id "
                         "AND s.session = a.session WHERE a.credential_id = ? AND a.kind != 'chatgpt' ORDER BY a.id",
                         (cred_id,)).fetchall()


async def poll(c: Caller, timeout: float, disconnected: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
    """Held open by the resident program; while it is open the computer is connected. It answers at once with
    the deliveries that wait for any agent it serves (each delivery as the per-session poll hands it out, plus
    the agent's name and its session), and otherwise ends at the timeout or when the program goes away.
    Woken by the same signals as the per-session poll."""
    cred_id = _computer(c)
    pj = c.pj
    timeout = max(0.0, min(float(timeout), POLL_MAX_S))
    waker = asyncio.Event()

    def mark() -> None:
        with pj.db:
            pj.db.execute("UPDATE credentials SET last_poll = ? WHERE id = ?", (util.now(), cred_id))

    before = notices.online_now(pj, _agents_of(pj, cred_id))
    mark()
    presence.computer_opened(pj.slug, cred_id, waker)
    try:
        notices.sync_computer(pj, cred_id)
        notices.settle(pj, before)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        gone_away = asyncio.ensure_future(disconnected())
        try:
            while True:
                waker.clear()
                _computer(c)            # revoked while held: 401
                served = _served(pj, cred_id)
                news = {a["id"]: messaging.listen(pj.slug, a["id"]) for a in served}
                try:
                    left = deadline - loop.time()
                    out: list[dict[str, Any]] = []
                    for a in served:
                        # As in the per-session poll: an open wait takes the messages, a held agent gets nothing.
                        if messaging.waiting(pj.slug, a["id"]) or presence.held(a):
                            continue
                        me = messaging.agent_member(a)
                        session = a["session"][len(LOCAL):] if a["session"].startswith(LOCAL) else a["session"]
                        out += [dict(d, agent=a["name"], session=session) for d in messaging.hand_out(pj, me)]
                        due = messaging.next_due(pj, me)
                        if due is not None:
                            left = min(left, max(0.05, due - util.now()))
                    if out:
                        return {"deliveries": out}
                    if left <= 0:
                        return {}
                    wakes = [asyncio.ensure_future(waker.wait()), *[asyncio.ensure_future(n.wait()) for n in news.values()]]
                    try:
                        await asyncio.wait([gone_away, *wakes], timeout=left, return_when=asyncio.FIRST_COMPLETED)
                    finally:
                        for w in wakes:
                            w.cancel()
                finally:
                    for aid, n in news.items():
                        messaging.unlisten(pj.slug, aid, n)
                if gone_away.done():
                    return {}
        finally:
            gone_away.cancel()
    finally:
        presence.computer_closed(pj.slug, cred_id, waker)
        mark()


def ack(c: Caller, ids: Any) -> dict[str, Any]:
    """As the per-session ack, for any agent bound through this credential."""
    cred_id = _computer(c)
    if not isinstance(ids, list):
        raise bad_request("bad_request", "deliveries must be a list of delivery ids.")
    for a in c.pj.db.execute("SELECT * FROM agents WHERE credential_id = ?", (cred_id,)).fetchall():
        messaging.ack(c.pj, messaging.agent_member(a), ids)
    return {}
