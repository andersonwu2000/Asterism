"""Agents: authorising a computer (device flow), a session registering as an agent, and the agent's side of
messages (send, messages, wait, the poll that hands out deliveries, ack).

The helper-facing HTTP API and both MCP faces call these with a Caller that says which person, credential
and session a call comes from.
"""
from __future__ import annotations

import asyncio
import re
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from . import config, messaging, notices, presence, projects, util
from .errors import ApiError, bad_request, conflict, invalid_credential, not_found
from .projects import Actor, Project
from .store import Store

LOCAL_KINDS = ("claude-code", "codex")
DEVICE_KINDS = ("claude-code", "codex", "other")      # `other`: the helper was told no particular agent
USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"           # no vowels (no words), no look-alikes
SESSION_RE = re.compile(r"[\x21-\x7e]{1,200}")
POLL_MAX_S = 60.0

NOT_REGISTERED = "This session is not registered. Call register with your agent name first."


# --------------------------------------------------------------------------- device flow (RFC 8628)

def _device_error(code: str, message: str) -> ApiError:
    return ApiError(400, code, message)


def _norm_user_code(raw: str) -> str:
    return "".join(ch for ch in str(raw).upper() if ch.isalnum())


def device_start(store: Store, slug: str, kind: Any, computer: Any) -> dict[str, Any]:
    projects.open_project(store, slug)
    if kind not in DEVICE_KINDS:
        raise bad_request("invalid_kind", "kind must be one of: " + ", ".join(DEVICE_KINDS))
    label = util.clean_label(computer)
    if not label:
        raise bad_request("invalid_computer", "computer must name this computer.")
    db = store.accounts()
    device_code = util.new_secret()
    t, ttl = util.now(), config.get().device_ttl_s
    with db:
        db.execute("DELETE FROM device_requests WHERE expires < ?", (t - 86400,))
        while True:
            user = "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(8))
            if not db.execute("SELECT 1 FROM device_requests WHERE user_digest = ?", (util.digest(user),)).fetchone():
                break
        db.execute("INSERT INTO device_requests (slug, device_digest, user_digest, kind, computer, created, expires, status) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')", (slug, util.digest(device_code), util.digest(user), kind, label, t, t + ttl))
    shown = f"{user[:4]}-{user[4:]}"
    uri = f"{config.get().public_url}/{slug}/device"
    util.log("device_started", project=slug, kind=kind, computer=label)
    return {"device_code": device_code, "user_code": shown, "verification_uri": uri,
            "verification_uri_complete": f"{uri}?code={shown}", "interval": 3, "expires_in": int(ttl)}


def _status(r: sqlite3.Row) -> str:
    if r["status"] == "issued":
        return "approved"
    if r["status"] == "pending" and r["expires"] < util.now():
        return "expired"
    return r["status"]


def _device_by_user_code(store: Store, slug: str, user_code: str) -> sqlite3.Row:
    r = store.accounts().execute("SELECT * FROM device_requests WHERE user_digest = ? AND slug = ?",
                                 (util.digest(_norm_user_code(user_code)), slug)).fetchone()
    if not r:
        raise not_found("There is no such authorisation request. Check the code, or start again.")
    return r


def device_view(store: Store, slug: str, person: sqlite3.Row, user_code: str) -> dict[str, Any]:
    pj = projects.open_project(store, slug)
    actor = projects.require_member(pj, person)
    r = _device_by_user_code(store, slug, user_code)
    return {"computer": r["computer"], "kind": r["kind"], "status": _status(r),
            "switches": projects.switches(pj, actor.person_id)}


def device_decide(store: Store, slug: str, person: sqlite3.Row, user_code: str, decision: Any,
                  switches: Any = None) -> dict[str, Any]:
    """The signed-in person approves or denies a computer acting in their name; the switches of their
    own group are set with the same click."""
    pj = projects.open_project(store, slug)
    actor = projects.require_member(pj, person)
    projects.require(pj, actor, "manage_own_agents", "Authorising agents needs the manage_own_agents permission.")
    if decision not in ("approve", "deny"):
        raise bad_request("invalid_decision", "decision must be approve or deny.")
    r = _device_by_user_code(store, slug, user_code)
    status = _status(r)
    if status == "expired":
        raise ApiError(410, "gone", "This request has expired. Start the authorisation again.")
    if status != "pending":
        raise conflict(f"This request was already {status}.")
    if decision == "approve" and switches is not None:
        projects.set_switches(pj, actor, switches)
    db = store.accounts()
    with db:
        db.execute("UPDATE device_requests SET status = ?, person_id = ? WHERE id = ?",
                   ("approved" if decision == "approve" else "denied", person["id"], r["id"]))
    util.log("device_decided", project=slug, request=r["id"], decision=decision, person=person["id"])
    return {"status": "approved" if decision == "approve" else "denied"}


def device_token(store: Store, slug: str, device_code: Any) -> dict[str, Any]:
    """The helper's poll. The credential is created here, so it exists in clear only in this one answer."""
    pj = projects.open_project(store, slug)
    db = store.accounts()
    r = db.execute("SELECT * FROM device_requests WHERE device_digest = ? AND slug = ?",
                   (util.digest(str(device_code or "")), slug)).fetchone()
    if not r or r["status"] == "issued":
        raise _device_error("expired_token", "This device code is used up or unknown. Start the authorisation again.")
    status = _status(r)
    if status == "expired" or r["expires"] < util.now():
        raise _device_error("expired_token", "Nobody approved this request in time. Start the authorisation again.")
    if status == "denied":
        raise _device_error("access_denied", "The person denied this request.")
    if status == "pending":
        raise _device_error("authorization_pending", "Waiting for the person to approve.")
    holder = pj.db.execute("SELECT name FROM people WHERE person_id = ?", (r["person_id"],)).fetchone()
    if not holder:                      # removed between approving and collecting
        raise _device_error("access_denied", "The approving person is no longer a member.")
    with db:
        db.execute("UPDATE device_requests SET status = 'issued' WHERE id = ?", (r["id"],))
    _, secret = issue_computer_credential(pj, r["person_id"], r["computer"], "device")
    return {"credential": secret, "person": holder["name"]}


def issue_computer_credential(pj: Project, person_id: int, computer: str, via: str) -> tuple[int, str]:
    """A computer authorised to act for the person: by an approved device request or a redeemed agent
    invitation link. Returns (id, the secret)."""
    return projects.issue_credential(pj, person_id, "computer", computer, via)


# --------------------------------------------------------------------------- who is calling

@dataclass(frozen=True)
class Caller:
    pj: Project
    person_id: int
    credential_id: int
    session: str | None       # namespaced: "local:<id>" or "oai:<digest>"
    kind: str                 # what an agent registered from here is: claude-code, codex, chatgpt


def credential_caller(store: Store, slug: str, credential: str | None, session: str | None,
                      kind: str | None) -> Caller:
    """A helper's call: the credential says which person, the session header which session."""
    pj = projects.open_project(store, slug)
    if not credential:
        raise invalid_credential()
    c = pj.db.execute("SELECT * FROM credentials WHERE digest = ? AND revoked IS NULL",
                      (util.digest(credential),)).fetchone()
    if not c or not pj.db.execute("SELECT 1 FROM people WHERE person_id = ?", (c["person_id"],)).fetchone():
        raise invalid_credential()
    touch_credential(pj, c["id"])
    sid = None
    if session:
        if not SESSION_RE.fullmatch(session):
            raise bad_request("invalid_session", "The session id must be 1 to 200 printable characters without spaces.")
        sid = "local:" + session
    return Caller(pj, c["person_id"], c["id"], sid, kind if kind in LOCAL_KINDS else "")


def touch_credential(pj: Project, cred_id: int) -> None:
    with pj.db:
        pj.db.execute("UPDATE credentials SET last_used = ? WHERE id = ?", (util.now(), cred_id))


def bound_agent(c: Caller) -> sqlite3.Row | None:
    """The agent this session is bound to. A session whose agent was taken over is fenced off."""
    if not c.session:
        return None
    a = c.pj.db.execute("SELECT * FROM agents WHERE person_id = ? AND session = ?", (c.person_id, c.session)).fetchone()
    if a:
        return a
    s = c.pj.db.execute("SELECT a.name FROM superseded s JOIN agents a ON a.id = s.agent_id "
                        "WHERE s.person_id = ? AND s.session = ?", (c.person_id, c.session)).fetchone()
    if s:
        raise ApiError(409, "superseded", f"Another session took over the agent '{s['name']}'. "
                                          f"This session no longer acts as '{s['name']}'; stop using it for this project.")
    return None


def _touch(c: Caller, agent_id: int) -> None:
    with c.pj.db:
        c.pj.db.execute("UPDATE agents SET last_active = ? WHERE id = ?", (util.now(), agent_id))


# --------------------------------------------------------------------------- the three tools

def whoami(c: Caller) -> dict[str, Any]:
    a = bound_agent(c)
    pj = c.pj
    out: dict[str, Any] = {"registered": a is not None, "agent": None, "owner": projects.person_name(pj, c.person_id),
                           "groups": [], "generation": None, "project": projects.info(pj)}
    actor = Actor(c.person_id, a["id"] if a else None)
    if a:
        _touch(c, a["id"])
        out.update(agent=a["name"], groups=[g["name"] for g in projects.groups_of(pj, "agent", a["id"])],
                   generation=a["generation"])
    else:
        out["note"] = NOT_REGISTERED
    if "read" in projects.permissions(pj, actor):
        out.update(projects.people_and_agents(pj))
    else:
        out.update(people=[], agents=[], note="This agent lacks the read permission, so the member list is hidden.")
    return out


def register(c: Caller, name: Any, takeover: Any = False) -> dict[str, Any]:
    """Bind this session to an agent name of the caller's person (the table of the registration rules)."""
    pj = c.pj
    takeover = takeover is True
    if not c.session:
        raise bad_request("no_session", "This call carries no session id, so it cannot register. "
                                        "Restart the agent session; the client must provide a session id.")
    projects.check_name(name)
    try:
        current = bound_agent(c)
    except ApiError as e:
        if e.code != "superseded" or not takeover:
            raise
        current = None                  # an explicit takeover is how a fenced-off session comes back
    if current is not None:
        if current["name"] == name:
            _touch(c, current["id"])
            return _registered(pj, current, "same")
        raise conflict(f"This session is already registered as '{current['name']}'. Call leave first, then register again.")
    holder = projects.name_holder(pj, name)
    a = pj.db.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
    if a is None or a["person_id"] != c.person_id:
        if holder:
            raise conflict(projects.describe_holder(pj, holder) + ". Choose another name.")
        if name.lower().endswith(projects.OWNERSHIP_SUFFIX):
            raise conflict(f"Names ending in '{projects.OWNERSHIP_SUFFIX}' are kept for each person's own group. Choose another name.")
        if not c.kind:
            raise bad_request("invalid_client", "Say which agent this is: X-Asterism-Client must be claude-code or codex.")
        return _create(c, name)
    if a["session"] is None:
        return _bind(c, a, "bound")
    if presence.is_online(pj.slug, a, pj.db):
        raise conflict(f"'{name}' is in use by another session that is online. Choose another name.")
    if not takeover:
        raise conflict(f"'{name}' is held by another session that is offline. If you are the same agent continuing "
                       f"its work, call register again with takeover=true; otherwise choose another name.")
    return _bind(c, a, "taken_over")


def _registered(pj: Project, a: sqlite3.Row, how: str) -> dict[str, Any]:
    return {"agent": a["name"], "owner": projects.person_name(pj, a["person_id"]), "generation": a["generation"], "how": how}


def _create(c: Caller, name: str) -> dict[str, Any]:
    pj, t = c.pj, util.now()
    with pj.db:
        aid = pj.db.execute("INSERT INTO agents (name, person_id, kind, created, session, credential_id, generation, "
                            "last_session, last_active, announced) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, 0)",
                            (name, c.person_id, c.kind, t, c.session, c.credential_id, c.session, t)).lastrowid
        for g in (projects.group_by_name(pj, "ai"), projects.ownership_group(pj, c.person_id)):
            pj.db.execute("INSERT OR IGNORE INTO group_members (group_id, member_kind, member_id) VALUES (?, 'agent', ?)",
                          (g["id"], aid))
        pj.db.execute("DELETE FROM superseded WHERE person_id = ? AND session = ?", (c.person_id, c.session))
    a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (aid,)).fetchone()
    util.log("registered", project=pj.slug, agent=name, how="new", generation=1)
    presence.binding_changed(pj.slug, aid)      # an open computer poll may serve the new agent
    notices.sync(pj, aid)                       # online at once when its computer already reported the session
    return _registered(pj, a, "new")


def _bind(c: Caller, a: sqlite3.Row, how: str) -> dict[str, Any]:
    """Bind the session; a session other than the last one raises the generation, and the session that
    held the agent until now is fenced off."""
    pj, t = c.pj, util.now()
    gen = a["generation"] + (1 if a["last_session"] != c.session else 0)
    # An agent is what its present session is: the kind follows the face the session came through.
    kind = c.kind or (a["kind"] if a["kind"] in LOCAL_KINDS else "")
    if not kind:
        raise bad_request("invalid_client", "Say which agent this is: X-Asterism-Client must be claude-code or codex.")
    other_face = (kind == "chatgpt") != (a["kind"] == "chatgpt")
    dropped = [r["id"] for r in pj.db.execute("SELECT id FROM subscriptions WHERE agent_id = ?", (a["id"],))] \
        if other_face and kind != "chatgpt" else []
    before = notices.online_now(pj, [a["id"]])
    with pj.db:
        if how == "taken_over" and a["session"]:
            pj.db.execute("INSERT OR REPLACE INTO superseded (person_id, session, agent_id, at) VALUES (?, ?, ?, ?)",
                          (a["person_id"], a["session"], a["id"], t))
        pj.db.execute("DELETE FROM superseded WHERE person_id = ? AND session = ?", (c.person_id, c.session))
        pj.db.execute("UPDATE agents SET session = ?, credential_id = ?, generation = ?, last_session = ?, "
                      "last_active = ?, last_poll = NULL, kind = ? WHERE id = ?",
                      (c.session, c.credential_id, gen, c.session, t, kind, a["id"]))
        if other_face:
            # A local agent is not reached through event subscriptions; and what the previous face handed out
            # without an acknowledgement goes to the new session from the start, by its own path.
            pj.db.execute("DELETE FROM subscriptions WHERE agent_id = ?", (a["id"],))
            pj.db.execute("UPDATE deliveries SET state = 'pending', attempts = 0 WHERE agent_id = ? AND state = 'out'",
                          (a["id"],))
    for sid in dropped:
        util.log("event_sub_dropped", project=pj.slug, sub=sid, reason="rebound")
    presence.binding_changed(pj.slug, a["id"])
    a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (a["id"],)).fetchone()
    util.log("registered", project=pj.slug, agent=a["name"], how=how, generation=gen,
             **({"kind": kind} if other_face else {}))
    notices.settle(pj, before)          # a session its computer already reported is online at once
    return _registered(pj, a, how)


def leave(c: Caller) -> dict[str, Any]:
    a = bound_agent(c)
    if a is None:
        raise ApiError(409, "not_registered", NOT_REGISTERED)
    with c.pj.db:
        c.pj.db.execute("UPDATE agents SET session = NULL, credential_id = NULL, last_poll = NULL, last_active = ? "
                        "WHERE id = ?", (util.now(), a["id"]))
    presence.binding_changed(c.pj.slug, a["id"])
    util.log("left", project=c.pj.slug, agent=a["name"])
    notices.sync(c.pj, a["id"])
    return {"left": a["name"]}


async def poll(c: Caller, timeout: float, disconnected: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
    """Held open by the helper while its session is registered; while it is open the agent is online.
    It answers at once with the deliveries that wait for the agent (unless a `wait` of the agent is open,
    which takes the messages instead), and otherwise ends at the timeout, when the binding changes, or when
    the helper goes away."""
    a = bound_agent(c)
    if a is None:
        raise ApiError(409, "not_registered", NOT_REGISTERED)
    timeout = max(0.0, min(float(timeout), POLL_MAX_S))
    pj, aid, sid = c.pj, a["id"], c.session
    me = messaging.agent_member(a)
    waker = asyncio.Event()

    def mark() -> None:
        with pj.db:
            pj.db.execute("UPDATE agents SET last_poll = ?, last_active = ? WHERE id = ? AND session = ?",
                          (util.now(), util.now(), aid, sid))

    if not presence.is_online(pj.slug, a, pj.db) and not presence.held(a):
        messaging.drop_unheard(pj, me)
    mark()
    presence.opened(pj.slug, aid, sid, waker)
    notices.sync(pj, aid)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    ends = [asyncio.ensure_future(waker.wait()), asyncio.ensure_future(disconnected())]
    try:
        while True:
            news = messaging.listen(pj.slug, aid)
            try:
                left = deadline - loop.time()
                now = pj.db.execute("SELECT * FROM agents WHERE id = ?", (aid,)).fetchone()
                if now is None or now["session"] != sid:
                    return {}
                # An open wait takes the messages (its end wakes us); an agent held offline gets nothing
                # until its session calls a tool (that wakes us too); an agent its computer's connection
                # serves gets its deliveries there (that connection going away wakes us).
                if not messaging.waiting(pj.slug, aid) and not presence.held(now) \
                        and not presence.via_computer(pj.slug, now, pj.db):
                    ds = messaging.hand_out(pj, me)
                    if ds:
                        return {"deliveries": ds}
                    due = messaging.next_due(pj, me)
                    if due is not None:
                        left = min(left, max(0.05, due - util.now()))
                if left <= 0:
                    return {}
                heard = asyncio.ensure_future(news.wait())
                try:
                    await asyncio.wait([*ends, heard], timeout=left, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    heard.cancel()
            finally:
                messaging.unlisten(pj.slug, aid, news)
            if any(t.done() for t in ends):
                return {}
    finally:
        for t in ends:
            t.cancel()
        presence.closed(pj.slug, aid, sid, waker)
        mark()


# --------------------------------------------------------------------------- messages

def active(c: Caller) -> None:
    """The session called a tool (an agent endpoint other than poll and ack): the agent itself is alive.
    That is what the reminder rule counts, and it ends a hold (`unanswered`, `silent`)."""
    try:
        a = bound_agent(c)
    except ApiError:
        return                          # the endpoint itself refuses the call
    if a is None:
        return
    with c.pj.db:
        c.pj.db.execute("UPDATE agents SET last_tool = ? WHERE id = ?", (util.now(), a["id"]))
    if presence.held(a):
        notices.release(c.pj, a)


def _agent(c: Caller) -> sqlite3.Row:
    a = bound_agent(c)
    if a is None:
        raise ApiError(409, "not_registered", NOT_REGISTERED)
    _touch(c, a["id"])
    return a


def with_unread(c: Caller, out: dict[str, Any]) -> dict[str, Any]:
    """Every answer to a registered agent says where it has unread messages."""
    try:
        a = bound_agent(c)
    except ApiError:
        return out
    if a is not None:
        out["unread"] = messaging.unread(c.pj, messaging.agent_member(a))
    return out


def send(c: Caller, to: Any, text: Any, reply_to: Any) -> dict[str, Any]:
    return messaging.send(c.pj, messaging.agent_member(_agent(c)), to, text, reply_to)


def messages(c: Caller, where: Any, mid: Any, before: Any, limit: Any) -> dict[str, Any]:
    return messaging.agent_messages(c.pj, messaging.agent_member(_agent(c)), where, mid, before, limit)


def ack(c: Caller, ids: Any) -> dict[str, Any]:
    return messaging.ack(c.pj, messaging.agent_member(_agent(c)), ids)


async def wait(c: Caller, timeout_s: Any, disconnected: Callable[[], Awaitable[Any]] | None = None) -> dict[str, Any]:
    """Held until a message for the agent (important or normal) that was not handed over is there, or the
    timeout. While it is open the agent's poll hands no messages out."""
    a = _agent(c)
    me, pj = messaging.agent_member(a), c.pj
    try:
        timeout = float(60 if timeout_s is None or timeout_s == "" else timeout_s)
    except (TypeError, ValueError):
        raise bad_request("bad_request", "timeout_s must be a number of seconds (at most 100).") from None
    timeout = max(0.0, min(timeout, messaging.WAIT_MAX_S))
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    messaging.wait_opened(pj.slug, me.id)
    gone = asyncio.ensure_future(disconnected()) if disconnected else None
    try:
        while True:
            news = messaging.listen(pj.slug, me.id)
            try:
                got = messaging.take_for_wait(pj, me)
                if got:
                    return {"messages": got}
                left = deadline - loop.time()
                if left <= 0:
                    return {"messages": []}
                heard = asyncio.ensure_future(news.wait())
                try:
                    await asyncio.wait([heard, *([gone] if gone else [])], timeout=left,
                                       return_when=asyncio.FIRST_COMPLETED)
                finally:
                    heard.cancel()
            finally:
                messaging.unlisten(pj.slug, me.id, news)
            if gone is not None and gone.done():
                return {"messages": []}
    finally:
        if gone is not None:
            gone.cancel()
        messaging.wait_closed(pj.slug, me.id)
