"""Acceptance checks for M1 slice 1b, second step: reminders, offline rules, notices, events for the connector.

Black box, same harness as test_m1b.py, with a server of its own whose reminder time is short. Every test uses
agents of its own: an agent that leaves an important message unanswered is reminded and may go offline, and that
must not leak into another test.

    python -m pytest tests/test_m1b2.py -x -q
"""
import base64
import hashlib
import hmac
import http.server
import json
import secrets
import threading
import time

import httpx
import pytest

from test_m1b import ENV, SLUG, Agent, build_world, connector_token, free_port, mention, remote_tool, rpc, until

OFFLINE_S, REDELIVER_S, REMIND_S = 3, 2, 4
ENV2 = dict(ENV, ASTERISM_OFFLINE_AFTER_S=str(OFFLINE_S), ASTERISM_REDELIVER_AFTER_S=str(REDELIVER_S),
            ASTERISM_REMIND_AFTER_S=str(REMIND_S))
REMINDER = "You have not answered message {id} from {sender}. Answer with send, reply_to={id}."
EVENT_DESCRIPTION = ("A message has arrived for the agent named in `agent`. The event carries the whole message, so you do "
                     "not need a tool to read it. `relation` says who the sender is to you. If `level` is important, "
                     "answer with send and reply_to set to its id.")


@pytest.fixture(scope="module")
def v(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("data2"), ENV2)
    yield world
    world.srv.stop()


def fresh(v, name, cred=None, acks=True) -> Agent:
    a = Agent(v.srv, cred or v.cred_a, "s-" + name).register(name)
    a.acks = acks
    a.online()
    assert until(lambda: v.alice.is_online(name)), f"{name} did not come online"
    return a


def of_kind(agent: Agent, kind: str) -> list[dict]:
    with agent.lock:
        return [d for d in agent.got if d.get("kind") == kind]


def notices(agent: Agent, text: str) -> list[dict]:
    return [d for d in of_kind(agent, "notice") if d["message"]["text"] == text]


def tool_call(agent: Agent):
    """Any tool call: what shows the server that the agent itself is alive."""
    r = agent.c.get(f"/{SLUG}/api/agent/whoami")
    assert r.status_code == 200, r.text


def leave(agent: Agent):
    agent.c.post(f"/{SLUG}/api/agent/leave")


def logged(v, event: str, **fields) -> list[dict]:
    lines = (v.srv.data / "log.jsonl").read_text(encoding="utf-8").splitlines()
    out = [e for e in map(json.loads, filter(str.strip, lines)) if e.get("event") == event]
    return [e for e in out if all(e.get(k) == x for k, x in fields.items())]


def system_messages(person, text: str) -> list[dict]:
    return [m for m in person.read() if m["from_kind"] == "system" and m["text"] == text]


# ------------------------------------------------------------------ reminders

def test_an_unanswered_important_message_is_followed_by_one_reminder(v):
    r = fresh(v, "r1")
    sent = v.alice.say("@r1 what is the status? [f1]")
    r.take("[f1]")
    time.sleep(REMIND_S - 1.5)
    assert not of_kind(r, "reminder"), "not before ASTERISM_REMIND_AFTER_S"
    got = until(lambda: of_kind(r, "reminder"), 5)
    assert got, "no reminder came"
    assert got[0]["frame"] == REMINDER.format(id=sent["id"], sender="alice") and got[0]["about"] == sent["id"]
    r.say("here it is [f1a]", reply_to=sent["id"])
    time.sleep(REMIND_S * 2 + 1.5)
    assert len(of_kind(r, "reminder")) == 1, "an answered message is not reminded about again"
    assert v.alice.is_online("r1"), "and its agent stays online"
    leave(r)


def test_an_active_agent_is_reminded_again_and_a_silent_one_goes_offline(v):
    busy, idle = fresh(v, "r2"), fresh(v, "r3")
    sent = v.alice.say("@r2 @r3 please answer [f2]")
    busy.take("[f2]")
    idle.take("[f2]")
    end = time.time() + REMIND_S * 2 + 2.5
    while time.time() < end:                               # r2 keeps working without answering; r3 does nothing,
        tool_call(busy)                                    # though its helper acknowledges everything
        time.sleep(0.8)
    assert len(of_kind(busy, "reminder")) >= 2 and v.alice.is_online("r2"), "seen alive: reminded again, not offline"
    assert until(lambda: not v.alice.is_online("r3"), 6), "no tool call in a whole period: offline, open poll or not"
    assert len(of_kind(idle, "reminder")) == 1
    assert logged(v, "agent_offline", agent="r3", reason="silent")

    off = "r3 is offline."
    assert until(lambda: system_messages(v.alice, off), 5), "the system says so in #general"
    m = system_messages(v.alice, off)[0]
    assert (m["from"], m["relation"], m["level"]) == ("system", "system", "important"), "alice was waiting for r3's answer"
    assert system_messages(v.bob, off)[0]["level"] == "muted"
    d = until(lambda: notices(busy, off), 5)
    assert d and d[0]["message"]["level"] == "normal" and d[0]["frame"].endswith("\n(Asterism message. No answer needed.)")
    assert not notices(v.b1, off), "an agent of someone else is not told"

    late = v.alice.say("@r3 this arrived while you were out [f3]")
    assert mention(late, "r3")["result"] == "offline"
    idle.absent("[f3]", 1.0)
    tool_call(idle)                                        # the agent shows itself: online again
    assert until(lambda: v.alice.is_online("r3"), 5)
    idle.take("[f3]")
    on = until(lambda: [m for m in system_messages(v.alice, "r3 is online.")], 5)
    assert on and on[-1]["level"] == "normal"
    idle.say("sorry, here [f2a]", reply_to=sent["id"])
    idle.say("and this [f3a]", reply_to=late["id"])
    busy.say("done [f2b]", reply_to=sent["id"])
    leave(busy)
    leave(idle)


def test_a_helper_that_never_acknowledges_makes_its_agent_offline(v):
    u = fresh(v, "u1", acks=False)
    sent = v.alice.say("@u1 hello? [u1]")
    assert until(lambda: len(u.tagged("[u1]")) >= 2, REDELIVER_S * 2 + 3), "handed out a second time"
    assert until(lambda: not v.alice.is_online("u1"), REDELIVER_S + 4), "twice without an acknowledgement: offline"
    assert logged(v, "agent_offline", agent="u1", reason="unanswered")
    n = len(u.tagged("[u1]"))
    u.acks = True
    tool_call(u)
    assert until(lambda: v.alice.is_online("u1"), 5)
    assert until(lambda: len(u.tagged("[u1]")) > n, 6), "what was never acknowledged is handed out again"
    u.say("yes [u1a]", reply_to=sent["id"])
    leave(u)


# ------------------------------------------------------------------ notices

def test_notices_reach_only_those_close_to_the_agent(v):
    fresh(v, "n0")                                          # a sibling that is online to hear the notices
    n1 = fresh(v, "n1")
    on, off = "n1 is online.", "n1 is offline."
    seen = until(lambda: system_messages(v.alice, on), 5)
    assert seen and (seen[0]["level"], seen[0]["from"], seen[0]["reply_to"]) == ("normal", "system", None)
    assert system_messages(v.bob, on)[0]["level"] == "muted" and system_messages(v.carol, on)[0]["level"] == "muted"
    assert until(lambda: notices(v.a1, on), 5) and not notices(v.b1, on)

    r = v.alice.c.post(f"/{SLUG}/api/groups", json={"name": "lemma-team", "permissions": []})
    assert r.status_code == 201, r.text
    for member in ("alice", "bob", "n1"):                   # a person gives an agent only groups the person is in
        r = v.alice.c.post(f"/{SLUG}/api/members/{member}/groups", json={"add": ["lemma-team"], "remove": []})
        assert r.status_code == 200, r.text
    leave(n1)
    assert until(lambda: system_messages(v.bob, off), 5)
    assert system_messages(v.bob, off)[0]["level"] == "normal", "bob shares a custom group with n1"
    assert system_messages(v.carol, off)[0]["level"] == "muted", "the default groups do not count"
    assert logged(v, "agent_offline", agent="n1", reason="left") and logged(v, "agent_online", agent="n1")
    time.sleep(REMIND_S + 1.5)
    assert not [d for d in of_kind(v.a1, "reminder")], "nobody is reminded about a notice"


# ------------------------------------------------------------------ events for the connector

class Receiver:
    """ChatGPT's side of MCP Events: a callback that checks every signature and keeps what it was sent."""

    def __init__(self):
        self.secret = "whsec_" + base64.b64encode(secrets.token_bytes(24)).decode()
        self.status, self.posts, self.bad, self.lock = 200, [], [], threading.Lock()
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}/callback"
        me = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("content-length") or 0))
                head = {k.lower(): x for k, x in self.headers.items()}
                signed = f"{head.get('webhook-id', '')}.{head.get('webhook-timestamp', '')}.".encode() + body
                key = base64.b64decode(me.secret.removeprefix("whsec_"))
                good = "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
                payload = json.loads(body)
                with me.lock:
                    if good not in head.get("webhook-signature", "").split(" "):
                        me.bad.append(head)
                    me.posts.append({"head": head, "body": payload, "answered": me.status})
                if payload.get("type") == "verification":
                    out, status = json.dumps({"challenge": payload["challenge"]}).encode(), 200
                else:
                    out, status = b"{}", me.status
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def events(self, about: int | None = None, kind: str = "message") -> list[dict]:
        with self.lock:
            evs = [p for p in self.posts if p["body"].get("name") == "message.arrived"]
        return [p for p in evs if p["body"]["data"].get("kind") == kind
                and (about is None or p["body"]["data"].get("id" if kind != "reminder" else "about") == about)]

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def test_the_connector_is_woken_by_signed_events(v):
    token = connector_token(v.srv, v.alice)
    assert not remote_tool(v.srv, "register", token, "conv-e", name="dot-e")[1]
    listed = rpc(v.srv, "events/list", token=token).json()["result"]["events"]
    assert [e["name"] for e in listed] == ["message.arrived"] and listed[0]["description"] == EVENT_DESCRIPTION
    assert not v.alice.is_online("dot-e"), "a connector agent without a subscription cannot be woken"
    recv = Receiver()
    try:
        def subscribe(agent="dot-e", url=None, name="message.arrived"):
            return rpc(v.srv, "events/subscribe", {"name": name, "arguments": {"agent": agent},
                                                   "delivery": {"mode": "webhook", "url": url or recv.url,
                                                                "secret": recv.secret}}, token).json()
        assert "error" in subscribe(agent="b1"), "only for an agent of one's own"
        assert "error" in subscribe(name="files.changed")
        assert "error" in subscribe(url=f"http://127.0.0.1:{free_port()}/nobody"), "the callback must prove itself"
        assert not v.alice.is_online("dot-e")
        sub = subscribe()["result"]
        assert sub["id"] and sub["refreshBefore"] and sub["cursor"] is None
        assert subscribe()["result"]["id"] == sub["id"], "subscribing again refreshes the same subscription"
        assert any(p["body"].get("type") == "verification" for p in recv.posts)
        assert until(lambda: v.alice.is_online("dot-e"), 5), "with a live subscription it is online"

        sent = v.alice.say("@dot-e a question for dot [e1]")
        assert mention(sent, "dot-e")["result"] == "woken"
        got = until(lambda: recv.events(sent["id"]), 8)
        assert got, "no event arrived"
        ev, head = got[0]["body"], got[0]["head"]
        d = ev["data"]
        assert ev["eventId"].startswith("evt_") and ev["cursor"] is None and head["x-mcp-subscription-id"] == sub["id"]
        assert (d["agent"], d["in"], d["from"], d["relation"], d["level"], d["text"]) == \
            ("dot-e", "#general", "alice", "your own user", "important", "@dot-e a question for dot [e1]")
        assert until(lambda: logged(v, "delivered", message=sent["id"], to="dot-e", how="event"), 5)
        assert not remote_tool(v.srv, "send", token, "conv-e", text="the answer [e1a]", reply_to=sent["id"])[1]

        big = v.alice.say("@dot-e " + "證" * 3_980 + " [e2]")                   # the longest message there can be
        got = until(lambda: recv.events(big["id"]), 8)
        assert got and got[0]["body"]["data"]["text"].endswith("[e2]") and "text_omitted" not in got[0]["body"]["data"]
        assert not remote_tool(v.srv, "send", token, "conv-e", text="read it [e2a]", reply_to=big["id"])[1]

        quiet = v.alice.say("@dot-e one you will forget [e4]")
        assert until(lambda: recv.events(quiet["id"]), 8)
        rem = until(lambda: recv.events(quiet["id"], kind="reminder"), REMIND_S + 4)
        assert rem and rem[0]["body"]["data"]["text"] == REMINDER.format(id=quiet["id"], sender="alice")
        assert not remote_tool(v.srv, "send", token, "conv-e", text="sorry [e4a]", reply_to=quiet["id"])[1]

        v.srv.stop()
        v.srv.start()
        after = v.alice.say("@dot-e after the restart [e5]")
        assert until(lambda: recv.events(after["id"]), 10), "a subscription survives a restart"
        assert not remote_tool(v.srv, "send", token, "conv-e", text="still here [e5a]", reply_to=after["id"])[1]

        recv.status = 500
        lost = v.alice.say("@dot-e are you there? [e3]")
        assert until(lambda: not v.alice.is_online("dot-e"), REDELIVER_S * 2 + 6), "no 2xx twice: offline"
        assert len(recv.events(lost["id"])) == 2 and logged(v, "agent_offline", agent="dot-e", reason="unanswered")
        recv.status = 200
        assert not remote_tool(v.srv, "whoami", token, "conv-e")[1]
        assert until(lambda: v.alice.is_online("dot-e"), 5), "a tool call brings it back"
        assert until(lambda: len(recv.events(lost["id"])) == 3, 8), "and what it missed is sent again"
        assert not remote_tool(v.srv, "send", token, "conv-e", text="yes [e3a]", reply_to=lost["id"])[1]

        assert not recv.bad, "every POST carried a valid Standard Webhooks signature"
        gone = rpc(v.srv, "events/unsubscribe", {"name": "message.arrived", "arguments": {"agent": "dot-e"},
                                                 "delivery": {"mode": "webhook", "url": recv.url}}, token).json()
        assert "error" not in gone
        assert until(lambda: not v.alice.is_online("dot-e"), 5)
        assert logged(v, "agent_offline", agent="dot-e", reason="unsubscribed")
        log = (v.srv.data / "log.jsonl").read_text(encoding="utf-8")
        assert recv.secret not in log and recv.secret.removeprefix("whsec_") not in log
    finally:
        recv.stop()


# ------------------------------------------------------------------ the page

def test_the_project_address_is_the_messages_page(v):
    r = v.alice.c.get(f"/{SLUG}")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"] and "general" in r.text
    r = httpx.get(f"{v.srv.url}/{SLUG}", follow_redirects=False)       # since the joining flow: a small page, not a redirect
    assert r.status_code == 200 and "/login" in r.text and "general" not in r.text
    assert v.carol.c.get(f"/{SLUG}").status_code == 200


# ------------------------------------------------------------------ what an agent is follows its session

def test_an_agent_is_what_its_present_session_is(v):
    """A connector client that cannot subscribe to events can never be woken. The same agent, taken over by a
    session that came through the helper, is a local agent from then on and is woken like one."""
    def row():
        return next(a for a in v.alice.members()["agents"] if a["name"] == "kite")

    token = connector_token(v.srv, v.alice)
    assert not remote_tool(v.srv, "register", token, "conv-k", name="kite")[1]
    assert (row()["kind"], row()["online"], row()["offline_because"]) == ("chatgpt", False, "no_subscription")
    sent = v.alice.say("@kite can you hear this? [k0]")
    assert mention(sent, "kite")["result"] == "offline"

    local = Agent(v.srv, v.cred_a, "s-kite", client="codex")
    r = local.c.post(f"/{SLUG}/api/agent/register", json={"name": "kite", "takeover": True})
    assert r.status_code == 200 and r.json()["how"] == "taken_over", r.text
    local.name = "kite"
    assert (row()["kind"], row()["online"], row()["offline_because"]) == ("codex", False, "no_computer")
    local.online()
    assert until(lambda: row()["online"], 6), "a local session with an open poll is online, whatever the agent was before"
    assert row()["offline_because"] is None
    local.take("[k0]")                                     # what waited for it arrives now
    local.say("yes [k0a]", reply_to=sent["id"])
    again = v.alice.say("@kite and this? [k1]")
    assert mention(again, "kite")["result"] == "woken"
    local.take("[k1]")
    local.say("yes [k1a]", reply_to=again["id"])

    leave(local)
    assert until(lambda: row()["offline_because"] == "not_bound", 5)
    got, bad = remote_tool(v.srv, "register", token, "conv-k", name="kite", takeover=True)
    assert not bad, got
    assert (row()["kind"], row()["offline_because"]) == ("chatgpt", "no_subscription"), "and back again"
    remote_tool(v.srv, "leave", token, "conv-k")
