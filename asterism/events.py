"""MCP Events for the ChatGPT connector: how a hosted agent (dot), of which nothing runs between turns, is
woken. ChatGPT subscribes a webhook for one agent; each delivery for that agent (message, notice, reminder)
is POSTed there as a signed event and ChatGPT starts a turn. Carried over from the M0 spike, where it was
observed working against the real ChatGPT: the subscribe answer, the verification challenge, Standard
Webhooks signatures, callback addresses resolved and pinned to a public address, redirects not followed.

What this server adds: subscriptions live in the project's database (a restart keeps them), and the
attempts follow the delivery rules of the contract: a 2xx to an event hands it over (`delivered`, how
`event`); no 2xx, one more attempt after ASTERISM_REDELIVER_AFTER_S; then the agent is offline
(`unanswered`). The POSTs run in tasks of their own, never in a sender's request.

The signing secret is kept in clear (it is needed to sign) and is never logged; neither are callback paths,
bodies or signatures.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import sqlite3
import urllib.parse
from typing import Any

import httpx

from . import config, messaging, notices, presence, util
from .agents import Caller
from .projects import Project

EVENT = "message.arrived"
EVENT_DEF = {
    "name": EVENT,
    "description": ("A message has arrived for the agent named in `agent`. The event carries the whole message, so you "
                    "do not need a tool to read it. `relation` says who the sender is to you. If `level` is important, "
                    "answer with send and reply_to set to its id."),
    "delivery": ["webhook"],
    # The subscriber names its agent: ChatGPT subscribes from its task service, outside the agent's
    # conversation, so the request itself cannot say whose it is.
    "inputSchema": {
        "type": "object",
        "properties": {"agent": {"type": "string", "minLength": 1,
                                 "description": "The name you registered as with the `register` tool (`whoami` shows it)."}},
        "required": ["agent"],
        "additionalProperties": False,
    },
    "payloadSchema": {
        "type": "object",
        "properties": {
            "agent": {"type": "string", "description": "the agent the message is for"},
            "kind": {"type": "string", "enum": ["message", "notice", "reminder"]},
            "id": {"type": "integer", "description": "the message id; answer with send and reply_to set to it"},
            "in": {"type": "string", "description": "the channel (#name) or, for a private message, the other member"},
            "private": {"type": "boolean"},
            "from": {"type": "string"},
            "from_kind": {"type": "string", "enum": ["person", "agent", "system"]},
            "relation": {"type": "string", "description": ("who the sender is to you: `your own user`, `agent of your "
                                                            "own user`, `another collaborator`, `agent of another "
                                                            "collaborator` or `system`")},
            "level": {"type": "string", "enum": ["important", "normal", "muted"]},
            "reply_to": {"type": ["integer", "null"]},
            "text": {"type": "string"},
            "sent_at": {"type": "string", "format": "date-time"},
            "mentions": {"type": "array", "items": {"type": "string"}},
            "about": {"type": "integer", "description": "a reminder: the message it reminds you to answer"},
        },
        "required": ["agent", "kind", "from", "relation", "text"],
    },
}
SUB_MIN_TTL_S = 60          # a shorter request is raised to this (unless the longest lifetime is shorter)
ROTATE_S = 3600             # after a new secret, also sign with the old one this long (the receiver may lag)
CALLBACK_TIMEOUT_S = 10
MAX_EVENT_BYTES = 256 * 1024
MAX_REPLY_BYTES = 64 * 1024
CALLBACK_ERROR = -32015     # CallbackEndpointError as numbered on the OpenAI page
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
HOW_TO_SUBSCRIBE = ('Register first with the `register` tool, then subscribe with arguments '
                    '{"agent": "<your registered name>"}.')

_tls: Any = None
_flying: set[tuple[str, int]] = set()          # deliveries whose POSTs are running
_tasks: set[asyncio.Task[None]] = set()        # a task nobody holds may be collected


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code, self.data = code, data


class CallbackError(Exception):
    """A callback could not be used. `reason` is one of the categories of the draft spec."""

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason


def tls_context() -> Any:
    """One TLS context for all callback requests (building one costs CPU on the event loop)."""
    global _tls
    if _tls is None:
        _tls = httpx.create_ssl_context()
    return _tls


def sub_id(person_id: int, url: str, name: str, arguments: Any) -> str:
    """Deterministic: the same subscriber, callback, event and arguments always give the same id."""
    key = json.dumps([person_id, url, name, arguments], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sub_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def _host(url: str) -> str:
    """For the log: callback URLs can carry a token in the path, so only the host is written down."""
    return urllib.parse.urlsplit(url).hostname or "?"


def _signing_key(secret: Any) -> bytes:
    if not isinstance(secret, str) or not secret.startswith("whsec_"):
        raise RpcError(-32602, "delivery.secret must be a Standard Webhooks secret: whsec_<base64>")
    try:
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
    except ValueError:
        raise RpcError(-32602, "delivery.secret is not valid base64 after the whsec_ prefix") from None
    if not 24 <= len(key) <= 64:
        raise RpcError(-32602, "delivery.secret must decode to 24 to 64 bytes")
    return key


def _keys(sub: sqlite3.Row) -> list[bytes]:
    """The keys to sign with: the current one, and during a rotation the previous one as well."""
    keys = [_signing_key(sub["secret"])]
    if sub["old_secret"] and (sub["old_until"] or 0) > util.now():
        keys.append(_signing_key(sub["old_secret"]))
    return keys


def check_callback_url(url: Any) -> str:
    """https in real mode; in test mode also plain http to this computer."""
    parts = urllib.parse.urlsplit(url) if isinstance(url, str) else None
    if not parts or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise RpcError(-32602, "delivery.url must be an absolute URL without user info or fragment")
    if parts.scheme == "https":
        return url
    if parts.scheme == "http" and config.get().test_mode and parts.hostname in LOOPBACK:
        return url
    raise RpcError(-32602, "delivery.url must use https")


def _public(addr: str) -> bool:
    ip = ipaddress.ip_address(addr.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def _pinned(url: str) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Resolve the callback host now, at connection time, refuse non-public addresses, and connect to the
    address that was checked (a second lookup could answer differently). The original name is kept for the
    Host header and for TLS, so the certificate is still checked against it. A plain-http callback passed
    check_callback_url only in test mode, on this computer, and is used as it is."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "http":
        return url, {}, {}
    host, port = parts.hostname or "", parts.port or 443
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise CallbackError("connection_refused", "cannot resolve the callback host") from None
    addrs = [str(i[4][0]) for i in infos]
    if not addrs or not all(_public(a) for a in addrs):
        raise CallbackError("connection_refused", "the callback host is not a public address")
    ip = addrs[0]
    netloc = (f"[{ip}]" if ":" in ip else ip) + f":{port}"
    target = urllib.parse.urlunsplit(("https", netloc, parts.path or "/", parts.query, ""))
    host_header = host if parts.port in (None, 443) else f"{host}:{port}"
    return target, {"Host": host_header}, {"sni_hostname": host}


async def webhook(url: str, msg_id: str, body: bytes, sid: str, keys: list[bytes]) -> tuple[int, bytes]:
    """One signed POST (Standard Webhooks). Every call signs afresh: a new timestamp, a new signature.
    Redirects are not followed, and the answer is read only up to MAX_REPLY_BYTES."""
    if len(body) > MAX_EVENT_BYTES:
        raise CallbackError("payload_too_large", f"{len(body)} bytes is over the 256 KiB limit")
    ts = str(int(util.now()))
    signed = f"{msg_id}.{ts}.".encode("utf-8") + body
    sig = " ".join("v1," + base64.b64encode(hmac.new(k, signed, hashlib.sha256).digest()).decode("ascii")
                   for k in keys)
    target, headers, ext = await _pinned(url)
    headers.update({"Content-Type": "application/json", "webhook-id": msg_id, "webhook-timestamp": ts,
                    "webhook-signature": sig, "X-MCP-Subscription-Id": sid})
    try:
        # trust_env=False: a proxy from the environment would connect to the name, not the checked address
        async with httpx.AsyncClient(timeout=CALLBACK_TIMEOUT_S, follow_redirects=False, trust_env=False,
                                     verify=tls_context()) as c:
            async with c.stream("POST", target, content=body, headers=headers, extensions=ext) as r:
                data = b""
                async for chunk in r.aiter_bytes():
                    data += chunk
                    if len(data) > MAX_REPLY_BYTES:
                        break
                return r.status_code, data[:MAX_REPLY_BYTES]
    except httpx.TimeoutException as e:
        raise CallbackError("timeout", f"the callback did not answer in time ({type(e).__name__})") from None
    except httpx.HTTPError as e:
        tls = "ssl" in repr(e).lower() or "certificate" in repr(e).lower()
        raise CallbackError("tls_error" if tls else "connection_refused", type(e).__name__) from None


async def verify_callback(url: str, sid: str, key: bytes) -> None:
    """The challenge handshake: the callback must answer 2xx and echo a single-use challenge."""
    challenge = secrets.token_urlsafe(32)
    body = json.dumps({"type": "verification", "challenge": challenge}, separators=(",", ":")).encode("utf-8")
    status, reply = await webhook(url, "msg_verification_" + secrets.token_hex(12), body, sid, [key])
    if status >= 400:
        raise CallbackError(f"http_{min(status // 100, 5)}xx", f"the callback answered HTTP {status}")
    if not 200 <= status < 300:
        raise CallbackError("challenge_failed", f"the callback answered HTTP {status} (redirects are not followed)")
    try:
        echoed = json.loads(reply).get("challenge")
    except (ValueError, AttributeError):
        echoed = None
    if not isinstance(echoed, str) or not hmac.compare_digest(echoed.encode("utf-8"), challenge.encode("utf-8")):
        raise CallbackError("challenge_failed", "the callback did not echo the challenge")


# --------------------------------------------------------------------------- events/* (JSON-RPC)

def _event_args(p: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    """The identity of a subscription in a request: event name, arguments, callback URL."""
    if p.get("name") != EVENT:
        raise RpcError(-32023, f"unknown event {p.get('name')!r}; this server offers {EVENT!r}",
                       {"kind": "event", "name": p.get("name")})
    args = p.get("arguments") or {}
    if not isinstance(args, dict):
        raise RpcError(-32602, "arguments must be an object")
    delivery = p.get("delivery")
    if not isinstance(delivery, dict):
        raise RpcError(-32602, "delivery is missing")
    return EVENT, args, check_callback_url(delivery.get("url"))


def _check_agent(pj: Project, person_id: int, args: dict[str, Any]) -> sqlite3.Row:
    """The agent a subscription names: an existing connector agent of the token's person."""
    agent = args.get("agent")
    if set(args) - {"agent"}:
        raise RpcError(-32602, f"{EVENT} takes one argument, agent. {HOW_TO_SUBSCRIBE}")
    if not isinstance(agent, str) or not agent:
        raise RpcError(-32602, f"Name the agent to notify in arguments.agent. {HOW_TO_SUBSCRIBE}")
    a = pj.db.execute("SELECT * FROM agents WHERE name = ?", (agent,)).fetchone()
    if a is None:
        raise RpcError(-32023, f"There is no agent {agent!r}. {HOW_TO_SUBSCRIBE}", {"kind": "agent", "name": agent})
    if a["person_id"] != person_id:
        raise RpcError(-32024, f"The agent {agent!r} belongs to another collaborator; this connector can only subscribe "
                               f"for its own agents. {HOW_TO_SUBSCRIBE}")
    if a["kind"] != "chatgpt":
        raise RpcError(-32024, f"The agent {agent!r} is a local agent; its messages reach it through its helper. "
                               f"{HOW_TO_SUBSCRIBE}")
    return a


async def subscribe(c: Caller, p: dict[str, Any]) -> dict[str, Any]:
    """No registered session is needed: ChatGPT subscribes from its task service. The token says which
    person; the subscription names one of that person's connector agents."""
    pj = c.pj
    name, args, url = _event_args(p)
    _check_agent(pj, c.person_id, args)
    delivery = p["delivery"]
    if delivery.get("mode") != "webhook":
        raise RpcError(-32026, "only webhook delivery is offered", {"mode": delivery.get("mode")})
    key = _signing_key(delivery.get("secret"))
    longest = config.get().subscription_ttl_s
    ttl = p.get("ttlMs")
    if ttl is not None and (isinstance(ttl, bool) or not isinstance(ttl, int) or ttl < 0):
        raise RpcError(-32602, "ttlMs must be a non-negative integer or null")
    # No expiry is not granted: a forgotten subscription would wake the agent for ever.
    granted = longest if ttl is None else max(min(SUB_MIN_TTL_S, longest), min(ttl / 1000, longest))
    sid = sub_id(c.person_id, url, name, args)
    util.log("event_subscribe", project=pj.slug, sub=sid, agent=args["agent"], host=_host(url))
    try:
        await verify_callback(url, sid, key)
    except CallbackError as e:
        util.log("event_callback_refused", project=pj.slug, sub=sid, reason=e.reason)
        raise RpcError(CALLBACK_ERROR, f"callback verification failed: {e}", {"reason": e.reason}) from None
    a = _check_agent(pj, c.person_id, args)            # again: the verification took time
    t = util.now()
    was_online = presence.is_online(pj.slug, a, pj.db)
    old = pj.db.execute("SELECT * FROM subscriptions WHERE id = ?", (sid,)).fetchone()
    old_secret, old_until = None, None
    if old and old["secret"] != delivery["secret"]:
        old_secret, old_until = old["secret"], t + ROTATE_S
    elif old and (old["old_until"] or 0) > t:
        old_secret, old_until = old["old_secret"], old["old_until"]
    with pj.db:
        pj.db.execute("INSERT OR REPLACE INTO subscriptions (id, agent_id, person_id, url, arguments, secret, old_secret, "
                      "old_until, expires, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (sid, a["id"], c.person_id, url, json.dumps(args, sort_keys=True), delivery["secret"], old_secret,
                       old_until, t + granted, old["created"] if old else t))
    util.log("event_subscribed", project=pj.slug, sub=sid, agent=a["name"], how="refreshed" if old else "new",
             ttl_s=int(granted))
    if not was_online and not presence.held(a):
        messaging.drop_unheard(pj, messaging.agent_member(a))
    notices.sync(pj, a["id"])
    presence.kick()
    # No replay: message.arrived has no history to resume from, so the cursor is always null. A client that
    # asked to resume from a cursor is told that the history it wanted is not available.
    return {"id": sid, "refreshBefore": util.iso(t + granted), "cursor": None, "truncated": p.get("cursor") is not None}


def unsubscribe(c: Caller, p: dict[str, Any]) -> dict[str, Any]:
    name, args, url = _event_args(p)
    sid = sub_id(c.person_id, url, name, args)
    row = c.pj.db.execute("SELECT agent_id FROM subscriptions WHERE id = ?", (sid,)).fetchone()
    if row:
        with c.pj.db:
            c.pj.db.execute("DELETE FROM subscriptions WHERE id = ?", (sid,))
        util.log("event_unsubscribed", project=c.pj.slug, sub=sid)
        notices.sync(c.pj, row["agent_id"])
    return {}       # idempotent: an unknown subscription is not an error


async def rpc(c: Caller, method: str, params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise RpcError(-32602, "params must be an object")
    if method == "events/list":
        return {"events": [EVENT_DEF]}
    if method == "events/subscribe":
        return await subscribe(c, params)
    if method == "events/unsubscribe":
        return unsubscribe(c, params)
    raise RpcError(-32601, f"Method not found: {method}")


# --------------------------------------------------------------------------- sending events

def expire(pj: Project, t: float) -> None:
    """An expired subscription is gone."""
    for r in pj.db.execute("SELECT id, agent_id FROM subscriptions WHERE expires <= ?", (t,)).fetchall():
        with pj.db:
            pj.db.execute("DELETE FROM subscriptions WHERE id = ?", (r["id"],))
        util.log("event_sub_dropped", project=pj.slug, sub=r["id"], reason="expired")


def launch_due(pj: Project, t: float) -> None:
    """Start sending what is due for the connector agents that are online and not in a `wait`."""
    rows = pj.db.execute("SELECT d.* FROM deliveries d JOIN agents a ON a.id = d.agent_id WHERE a.kind = 'chatgpt' "
                         "AND (d.state = 'pending' OR (d.state = 'out' AND d.attempts < 2 AND d.handed_out <= ?)) "
                         "ORDER BY d.id", (t - config.get().redeliver_after_s,)).fetchall()
    for d in rows:
        if (pj.slug, d["id"]) in _flying or messaging.waiting(pj.slug, d["agent_id"]):
            continue
        a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (d["agent_id"],)).fetchone()
        if a is None or not presence.is_online(pj.slug, a, pj.db):
            continue
        _flying.add((pj.slug, d["id"]))
        task = asyncio.get_running_loop().create_task(_send(pj, d["id"]))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


def next_due(pj: Project) -> list[float]:
    """When an event attempt or a subscription's end falls due."""
    out = [r[0] + config.get().redeliver_after_s for r in pj.db.execute(
        "SELECT d.handed_out FROM deliveries d JOIN agents a ON a.id = d.agent_id WHERE a.kind = 'chatgpt' "
        "AND d.state = 'out' AND d.attempts < 2")]
    r = pj.db.execute("SELECT min(expires) FROM subscriptions").fetchone()
    return out + ([r[0]] if r and r[0] is not None else [])


def _event(pj: Project, d: sqlite3.Row, a: sqlite3.Row) -> tuple[str, bytes]:
    """The event for one delivery. Its id is fixed by the delivery, so every attempt sends the same one."""
    if d["kind"] == "reminder":
        when = util.iso(d["created"])
        data: dict[str, Any] = {"agent": a["name"], "kind": "reminder", "about": d["message_id"],
                                "text": messaging.reminder_text(pj, d["message_id"]), "from": "system",
                                "from_kind": "system", "relation": "system", "sent_at": when}
    else:
        row = pj.db.execute("SELECT * FROM messages WHERE id = ?", (d["message_id"],)).fetchone()
        data = dict(messaging.views(pj, [row], messaging.agent_member(a))[0], agent=a["name"], kind=d["kind"])
        when = data["sent_at"]
    event_id = "evt_" + hashlib.sha256(f"{pj.slug}:{d['id']}:{d['created']}".encode()).hexdigest()[:24]
    event = {"eventId": event_id, "name": EVENT, "timestamp": when, "cursor": None, "data": data}
    return event_id, json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


async def _send(pj: Project, delivery_id: int) -> None:
    """One attempt for one delivery: the event goes to each live subscription of the agent; one 2xx hands
    it over. Otherwise the attempt is counted, and a second one without a 2xx makes the agent offline."""
    try:
        d = pj.db.execute("SELECT * FROM deliveries WHERE id = ?", (delivery_id,)).fetchone()
        a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (d["agent_id"],)).fetchone() if d else None
        if d is None or a is None or d["state"] not in ("pending", "out"):
            return
        event_id, body = _event(pj, d, a)
        if len(body) > MAX_EVENT_BYTES:            # cannot happen with 4,000-character messages; never sent
            util.log("event_too_large", project=pj.slug, delivery=delivery_id, bytes=len(body))
            with pj.db:
                pj.db.execute("UPDATE deliveries SET state = 'dropped', done = ? WHERE id = ?", (util.now(), delivery_id))
            return
        subs = pj.db.execute("SELECT * FROM subscriptions WHERE agent_id = ? AND expires > ?",
                             (a["id"], util.now())).fetchall()
        if not subs:
            return                                  # it went offline meanwhile; nothing was attempted
        ok = False
        for sub in subs:
            try:
                status, _ = await webhook(sub["url"], event_id, body, sub["id"], _keys(sub))
                util.log("event_attempt", project=pj.slug, sub=sub["id"], delivery=delivery_id, status=status)
                ok = ok or 200 <= status < 300
            except (CallbackError, RpcError) as e:
                util.log("event_attempt", project=pj.slug, sub=sub["id"], delivery=delivery_id,
                         reason=getattr(e, "reason", "bad_secret"))
        d = pj.db.execute("SELECT * FROM deliveries WHERE id = ?", (delivery_id,)).fetchone()
        if d is None or d["state"] not in ("pending", "out"):
            return                                  # handed over meanwhile (a wait, messages)
        now = pj.db.execute("SELECT kind FROM agents WHERE id = ?", (a["id"],)).fetchone()
        if now is None or now["kind"] != "chatgpt":
            return                                  # a local session took the agent over meanwhile
        if ok:
            messaging.finish(pj, messaging.agent_member(a), [d], "event")
            return
        with pj.db:
            pj.db.execute("UPDATE deliveries SET state = 'out', handed_out = ?, attempts = attempts + 1 WHERE id = ?",
                          (util.now(), delivery_id))
        if d["attempts"] + 1 >= 2:
            notices.hold(pj, a["id"], "unanswered")
    except Exception as e:  # noqa: BLE001 - one failed delivery must not stop the others
        util.log("background_failed", project=pj.slug, step="event", error=type(e).__name__)
    finally:
        _flying.discard((pj.slug, delivery_id))
        presence.kick()
