"""Acceptance tests for slice 1c, step c1: the task table, busy and idle, and the notices that follow from them.

Black box: a real server process on localhost; people through the session cookie, agents through the agent API.
Nothing here imports the server's code.

    python -m pytest tests/test_m1c.py -q
"""
from __future__ import annotations

import time

import httpx
import pytest

from test_m1b import SLUG, Agent, Person, build_world, frame, until
from test_m1b2 import leave, notices, system_messages

LOCKED = ("Task {id} was assigned by {person}: only {person} changes its title or who holds it. Keep its body current, "
          "and mark it done when it is.")
OPEN = ("Open task {id} [{group}]: {title}. An agent of {group} that has no task may take it (task_update with id={id} "
        "and responsible set to its own name).")
NOT_YOURS = "Task {id} is {agent}'s. Ask {agent} to change it or to hand it over."
NOT_YOURS_OFFLINE = ("Task {id} is {agent}'s, and {agent} is offline. Its user has not allowed others to move its tasks: "
                     "ask {person}, or make a task of your own.")
ASK_FIRST = ("{agent} is another collaborator's agent, so you cannot put a task in its name. Leave the task without a "
             "responsible member and ask {agent} to claim it.")
RECOORDINATE = ("(Asterism notice. No answer needed. If this changes who should do which task, settle it with the agents "
                "you work with and update the task table.)")
OWN_A, OWN_B = "alice-agents", "bob-agents"


@pytest.fixture(scope="module")
def t(tmp_path_factory):
    """alice owns the project and has the agents a1 and a2; bob has b1; carol has none. All agents are online."""
    world = build_world(tmp_path_factory.mktemp("datac"))
    yield world
    world.srv.stop()


# ------------------------------------------------------------------ helpers

def clip(text: str) -> str:
    s = " ".join(text.split())
    return s if len(s) <= 120 else s[:120] + "…"


def err(r: httpx.Response) -> str:
    return r.json().get("error", "")


def p_make(person: Person, **body) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/tasks", json=body)


def p_change(person: Person, tid: int, **body) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/tasks/{tid}", json=body)


def p_remove(person: Person, tid: int) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/tasks/{tid}/remove")


def made(r: httpx.Response) -> dict:
    assert r.status_code in (200, 201), r.text
    return r.json()["task"]


def a_task(agent: Agent, **body) -> httpx.Response:
    return agent.c.post(f"/{SLUG}/api/agent/task", json=body)


def a_tasks(agent: Agent) -> list[dict]:
    r = agent.c.get(f"/{SLUG}/api/agent/tasks")
    assert r.status_code == 200, r.text
    return r.json()["tasks"]


def table(person: Person) -> dict[int, dict]:
    r = person.c.get(f"/{SLUG}/api/tasks")
    assert r.status_code == 200, r.text
    return {x["id"]: x for g in r.json()["groups"] for x in g["tasks"]}


def busy(person: Person, agent: str) -> bool:
    return next(a for a in person.members()["agents"] if a["name"] == agent)["busy"]


def wipe(t):
    """Remove every task, each by a person who may: an agent's task by the agent's person."""
    for tid, x in table(t.alice).items():
        who = t.bob if x["responsible_kind"] == "agent" and x["responsible"] == "b1" else t.alice
        assert p_remove(who, tid).status_code == 200, (tid, x)
    assert table(t.alice) == {}


def told(agent: Agent, text: str, timeout=6.0) -> dict:
    """The delivery of the system's message with exactly this text."""
    def find():
        with agent.lock:
            return [d for d in agent.got if d.get("kind") == "message" and d["message"]["text"] == text]
    found = until(find, timeout)
    assert found, f"{agent.name} was not told: {text}"
    assert (found[0]["message"]["from"], found[0]["message"]["relation"], found[0]["message"]["in"]) == ("system", "system", "#general")
    usual = frame(found[0]["message"])
    assert found[0]["frame"] == usual or found[0]["frame"].startswith(usual + chr(10) + "(While you were offline "), found[0]["frame"]
    return found[0]


def not_told(agent: Agent, piece: str, wait=1.5):
    time.sleep(wait)
    with agent.lock:
        hits = [d for d in agent.got if d.get("kind") in ("message", "notice") and piece in d["message"]["text"]]
    assert not hits, f"{agent.name} was told about {piece} and should not have been: {hits[0]['message']['text']}"


def level_for(person: Person, text: str) -> str:
    seen = until(lambda: system_messages(person, text), 6)
    assert seen, f"no message from the system says: {text}"
    return seen[-1]["level"]


def system_count(person: Person) -> int:
    return len([m for m in person.read() if m["from_kind"] == "system"])


def come_back(t, agent: Agent):
    agent.register(agent.name)
    assert until(lambda: t.alice.is_online(agent.name), 6)


# ------------------------------------------------------------------ the table, for people

def test_people_make_tasks_and_everybody_sees_the_table(t):
    r = p_make(t.alice, group="ai", text="  Find out who can check Lemma 3.2 [p1]  ")
    assert r.status_code == 201, r.text
    one = r.json()["task"]
    assert one == {"id": one["id"], "group": "ai", "title": "Find out who can check Lemma 3.2 [p1]", "body": "",
                   "responsible": None, "responsible_kind": None, "assigned_by": None, "posted_by": "alice",
                   "posted_at": one["posted_at"], "taken_at": None, "body_at": one["body_at"], "update_every_h": None,
                   "overdue": False, "done": False, "done_at": None}, \
        "an open task: nobody responsible, no lock, no online (f7: who posted it, when; 1t: a title, no body, not done)"
    r = p_make(t.carol, group="human", text="Read the draft [p2]", responsible="bob")
    assert r.status_code == 400 and err(r) == "not_an_agent", "a task is given to an agent or to nobody (f5)"
    two = made(p_make(t.carol, group="human", text="Read the draft [p2]"))
    assert (two["responsible"], two["responsible_kind"], two["assigned_by"]) == (None, None, None), \
        "an ordinary member may make tasks"
    assert two["id"] > one["id"] and "online" not in two

    everything = t.bob.c.get(f"/{SLUG}/api/tasks").json()["groups"]
    names = [g["name"] for g in everything]
    assert {"owner", "human", "ai", OWN_A, OWN_B} <= set(names), "every group is on the table"
    ai = next(g for g in everything if g["name"] == "ai")
    assert {m["name"]: m["kind"] for m in ai["members"]} == {"a1": "agent", "a2": "agent", "b1": "agent"}
    assert all(set(m) >= {"online", "busy"} for m in ai["members"])
    assert [x["id"] for x in ai["tasks"]] == [one["id"]]
    assert table(t.carol)[two["id"]]["title"] == "Read the draft [p2]"

    assert err(p_make(t.alice, group="ai", text="   ")) == "bad_request"
    long = made(p_make(t.alice, group="ai", title="長" * 200, body="長" * 10_000))
    assert (long["title"], long["body"]) == ("長" * 200, "長" * 10_000), "characters, not bytes"
    assert err(p_make(t.alice, group="ai", title="x" * 201)) == "too_long"
    assert err(p_make(t.alice, group="ai", title="x", body="x" * 10_001)) == "too_long"
    assert p_make(t.alice, group="no-such-group", text="x").status_code in (400, 404)
    r = p_make(t.alice, group="human", text="x", responsible="a1")
    assert r.status_code == 400 and err(r) == "not_in_group" and "human" in r.json()["message"], r.text
    assert p_change(t.alice, 999_999, text="x").status_code == 404

    changed = made(p_change(t.bob, one["id"], text="Find out who can check Lemma 3.3 [p1]"))
    assert changed["title"].endswith("3.3 [p1]"), "a task nobody's agent holds is anybody's to change"
    assert made(p_change(t.bob, two["id"], responsible=""))["responsible"] is None
    r = p_remove(t.carol, two["id"])
    assert r.status_code == 200 and r.json() == {"removed": two["id"]} and two["id"] not in table(t.alice)
    wipe(t)


def test_the_page_shows_the_table_above_the_channels(t):
    page = t.alice.c.get(f"/{SLUG}")
    assert page.status_code == 200 and 'id="members-toggle"' in page.text and 'id="task-panel"' not in page.text,         "tasks are shown under the agents in the member list (f4), not in a panel"
    mine = t.alice.c.get(f"/{SLUG}/my")
    assert mine.status_code == 200 and "之後的版本才生效" not in mine.text, "every switch is in force now"


# ------------------------------------------------------------------ the table, for agents

def test_an_agent_sees_only_the_tasks_of_its_groups(t):
    assert t.alice.c.post(f"/{SLUG}/api/groups", json={"name": "topic", "permissions": []}).status_code == 201
    for member in ("alice", "a1"):
        r = t.alice.c.post(f"/{SLUG}/api/members/{member}/groups", json={"add": ["topic"], "remove": []})
        assert r.status_code == 200, r.text
    in_topic = made(p_make(t.alice, group="topic", text="Sketch the topic [g1]"))
    in_own = made(p_make(t.alice, group=OWN_A, text="Keep the map current [g2]"))
    in_ai = made(p_make(t.alice, group="ai", text="Anybody: check the bibliography [g3]"))
    in_bobs = made(p_make(t.bob, group=OWN_B, text="Bob's own list [g4]"))

    seen = a_tasks(t.a1)
    assert [x["id"] for x in seen] == [in_ai["id"], in_own["id"], in_topic["id"]], "ordered by group name, then id"
    assert seen[0] == in_ai, "the same object a person sees"
    assert [x["id"] for x in a_tasks(t.a2)] == [in_ai["id"], in_own["id"]], "a2 is not in topic"
    assert [x["id"] for x in a_tasks(t.b1)] == [in_ai["id"], in_bobs["id"]]

    r = a_task(t.a2, id=in_topic["id"], text="not mine to touch")
    assert r.status_code == 403 and err(r) == "forbidden" and "topic" in r.json()["message"], r.text
    r = a_task(t.a2, group="topic", text="nor to add to")
    assert r.status_code == 403 and "ai" in r.json()["message"] and OWN_A in r.json()["message"], "it is told its groups"
    assert a_task(t.a2, group="no-such-group", text="x").status_code == 403
    assert a_task(t.a1, id=999_999, text="x").status_code == 404
    assert err(a_task(t.a1, group="topic")) == "bad_request", "a new task needs its title"
    assert err(a_task(t.a1, id=in_topic["id"])) == "bad_request", "a change must name something to change"
    r = a_task(t.a1, id=in_topic["id"], text="Sketch the topic, v2 [g1]")
    assert made(r)["title"] == "Sketch the topic, v2 [g1]" and isinstance(r.json().get("unread", []), list)
    wipe(t)


def test_agents_of_one_person_settle_tasks_among_themselves(t):
    """One task per agent (1t): a1 holds one, a2 the other; an open task is announced to the idle agents of its group,
    and its poster is told when it is taken."""
    before = system_count(t.alice)
    mine = made(a_task(t.a1, group=OWN_A, text="Prove the easy direction [s1]", responsible="a1"))
    assert (mine["responsible"], mine["responsible_kind"], mine["online"], mine["assigned_by"]) == ("a1", "agent", True, None)
    assert until(lambda: busy(t.alice, "a1"), 3) and not busy(t.alice, "a2"), "holding a task is what busy means"
    made(a_task(t.a1, id=mine["id"], text="Prove the easy direction, both cases [s1]"))
    time.sleep(1.0)
    assert system_count(t.alice) == before, "what an agent does with its own task is told to nobody"
    open_one = made(a_task(t.a1, group=OWN_A, text="Somebody: tidy the notation [s2]"))
    assert open_one["responsible"] is None
    opened = OPEN.format(id=open_one["id"], group=OWN_A, title="Somebody: tidy the notation [s2]")
    assert told(t.a2, opened)["message"]["level"] == "normal", "an open task is announced to the idle agents of its group"
    not_told(t.b1, "[s2]", 1.0)

    made(a_task(t.a2, id=mine["id"], text="Prove the easy direction; case 2 is open [s1]"))
    d = told(t.a1, f"a2 changed task {mine['id']} [{OWN_A}] of a1: Prove the easy direction; case 2 is open [s1]")
    assert d["message"]["level"] == "normal" and d["frame"].endswith("(Asterism message. No answer needed.)")
    assert level_for(t.alice, d["message"]["text"]) == "muted" and level_for(t.bob, d["message"]["text"]) == "muted"
    not_told(t.b1, "[s1]", 1.0)

    taken = made(a_task(t.a2, id=mine["id"], responsible="a2"))
    assert taken["responsible"] == "a2"
    assert told(t.a1, f"a2 took task {mine['id']} [{OWN_A}] from a1.")["message"]["level"] == "normal"
    assert until(lambda: busy(t.alice, "a2") and not busy(t.alice, "a1"), 3), "the last task went: idle again"

    made(a_task(t.a2, id=mine["id"], responsible="a1"))
    told(t.a1, f"a2 gave task {mine['id']} [{OWN_A}] to a1: Prove the easy direction; case 2 is open [s1]")
    made(a_task(t.a2, id=open_one["id"], responsible="a2"))            # claiming an open task: its poster is told
    claimed = f"a2 gave task {open_one['id']} [{OWN_A}] to a2: Somebody: tidy the notation [s2]"
    assert told(t.a1, claimed)["message"]["level"] == "normal"
    made(a_task(t.a2, id=open_one["id"], responsible=""))              # giving it up: open again, told to idle agents
    assert table(t.alice)[open_one["id"]]["responsible"] is None
    not_told(t.a1, opened, 1.0)                                         # and a1 holds a task, so not to a1

    r = a_task(t.a2, id=mine["id"], remove=True)
    assert r.status_code == 200 and r.json()["removed"] == mine["id"]
    told(t.a1, f"a2 removed task {mine['id']} [{OWN_A}] of a1.")
    r = a_task(t.a1, id=open_one["id"], responsible="b1")
    assert r.status_code == 400 and err(r) == "not_in_group", "b1 is not in alice's ownership group"
    wipe(t)


def test_whoami_says_who_is_busy_and_lists_the_channels(t):
    made(a_task(t.a2, group=OWN_A, text="Hold this [w1]", responsible="a2"))
    who = t.a1.c.get(f"/{SLUG}/api/agent/whoami").json()
    flags = {a["name"]: a["busy"] for a in who["agents"]}
    assert flags["a2"] is True and flags["a1"] is False and flags["b1"] is False
    assert {"name": "general"} in who["channels"], "a channel is its name (pins retired, 1z)"
    wipe(t)


# ------------------------------------------------------------------ a person's assignment is locked

def test_a_task_a_person_assigns_is_locked(t):
    text = "Write up the proof of Lemma 3.2 [k1]"
    one = made(p_make(t.alice, group=OWN_A, text=text, responsible="a1"))
    assert (one["responsible"], one["assigned_by"]) == ("a1", "alice"), "making an agent responsible locks the task"
    d = told(t.a1, f"alice assigned task {one['id']} [{OWN_A}] to a1: {text}")
    assert d["message"]["level"] == "important"
    assert d["frame"].endswith(f"(Asterism message. To answer: send with reply_to={d['message']['id']}.)")
    assert level_for(t.bob, d["message"]["text"]) == "muted" and level_for(t.alice, d["message"]["text"]) == "muted"
    assert t.a1.send("On it [k1a]", reply_to=d["message"]["id"]).status_code == 200, "it answers where the message is"

    refusal = LOCKED.format(id=one["id"], person="alice")
    for who, change in ((t.a1, {"text": "something easier"}), (t.a1, {"remove": True}), (t.a1, {"responsible": ""}),
                        (t.a1, {"responsible": "a2"}), (t.a2, {"text": "x"}), (t.a2, {"responsible": "a2"})):
        r = a_task(who, id=one["id"], **change)
        assert r.status_code == 403 and err(r) == "task_locked" and r.json()["message"] == refusal, (change, r.text)
    assert table(t.alice)[one["id"]]["title"] == text
    kept = made(a_task(t.a1, id=one["id"], body="Half written; the constant is still open [k1]"))
    assert (kept["assigned_by"], kept["body"]) == ("alice", "Half written; the constant is still open [k1]"), \
        "the lock covers title and holder: its holder keeps the body current (1t)"

    new ="Write up the proof of Lemma 3.2, with the corrected constant [k1]"
    assert made(p_change(t.alice, one["id"], text=new))["assigned_by"] == "alice"
    assert told(t.a1, f"alice changed task {one['id']} [{OWN_A}] of a1: {new}")["message"]["level"] == "important"

    moved = made(p_change(t.alice, one["id"], responsible="a2"))
    assert (moved["responsible"], moved["assigned_by"]) == ("a2", "alice")
    both = f"alice assigned task {one['id']} [{OWN_A}] to a2: {new} It was a1's before."
    assert told(t.a2, both)["message"]["level"] == "important" and told(t.a1, both)["message"]["level"] == "important"

    assert made(p_change(t.alice, one["id"], locked=False))["assigned_by"] is None
    told(t.a2, f"alice released task {one['id']} [{OWN_A}]: a2 may change it now.")
    assert made(a_task(t.a2, id=one["id"], text="mine to shape now [k1]"))["title"].startswith("mine")
    assert made(p_change(t.alice, one["id"], locked=True))["assigned_by"] == "alice"
    told(t.a2, f"alice assigned task {one['id']} [{OWN_A}] to a2: mine to shape now [k1]")
    assert err(a_task(t.a2, id=one["id"], remove=True)) == "task_locked"

    plain = made(p_make(t.alice, group=OWN_A, text="Not an order, only a note [k2]", responsible="a1", locked=False))
    assert plain["assigned_by"] is None
    told(t.a1, f"alice gave task {plain['id']} [{OWN_A}] to a1: Not an order, only a note [k2]")
    assert made(p_change(t.alice, one["id"], responsible=""))["assigned_by"] is None, "no agent, no lock"
    told(t.a2, f"alice took task {one['id']} [{OWN_A}] from a2.")
    assert p_remove(t.alice, plain["id"]).status_code == 200
    assert told(t.a1, f"alice removed task {plain['id']} [{OWN_A}] of a1.")["message"]["level"] == "important"
    wipe(t)


def test_others_need_the_agents_switch(t):
    """`others_assign` of the ownership group: off by default, and it outranks every permission, the owner's too."""
    text = "Compare with the bound in the survey [o1]"
    r = p_make(t.bob, group="ai", text=text, responsible="a1")
    assert r.status_code == 403 and "a1" in r.json()["message"], "bob may assign tasks, but alice's agents are closed"
    r = p_make(t.alice, group="ai", text=text, responsible="b1")
    assert r.status_code == 403, "the owner of the project has no way around bob's switch either"
    own = made(a_task(t.a1, group="ai", text="My own plan [o2]", responsible="a1"))
    for attempt in (p_change(t.bob, own["id"], text="bob's idea of it"), p_change(t.bob, own["id"], responsible=""),
                    p_remove(t.bob, own["id"]), p_change(t.bob, own["id"], locked=True)):
        assert attempt.status_code == 403, attempt.text
    assert table(t.alice)[own["id"]]["title"] == "My own plan [o2]"

    t.alice.switches(others_assign=True)
    try:
        # to a2: a1 holds its own task, which one task per agent (1t) would put back on the board
        one = made(p_make(t.bob, group="ai", text=text, responsible="a2"))
        assert one["assigned_by"] == "bob"
        assert told(t.a2, f"bob assigned task {one['id']} [ai] to a2: {text}")["message"]["level"] == "important"
        assert err(a_task(t.a2, id=one["id"], remove=True)) == "task_locked"
        assert a_task(t.a2, id=one["id"], remove=True).json()["message"] == LOCKED.format(id=one["id"], person="bob")
        r = p_change(t.carol, one["id"], text="carol's version")
        assert r.status_code == 403 and err(r) == "task_locked", "a locked task: only who assigned it and the agent's person"
        assert made(p_change(t.alice, one["id"], text=text + " (alice: after Friday)"))["assigned_by"] == "bob"
        told(t.a2, f"alice changed task {one['id']} [ai] of a2: {text} (alice: after Friday)")
        assert made(p_change(t.carol, own["id"], text="My own plan, as carol reads it [o2]"))["assigned_by"] is None, \
            "open to others now: a member who may assign tasks changes an unlocked one"
        assert p_remove(t.bob, one["id"]).status_code == 200
        told(t.a2, f"bob removed task {one['id']} [ai] of a2.")
    finally:
        t.alice.switches(others_assign=False)
    assert p_change(t.bob, own["id"], text="closed again").status_code == 403
    wipe(t)


# ------------------------------------------------------------------ another person's agent must ask (the handshake)

def test_another_persons_agent_must_ask(t):
    """An agent that is not a coordinator changes a task of somebody else's agent only through that agent: the
    consent is the other agent's own call (the user's decision of 2026-11-15). Since 1t an agent holds one task, so
    b1's offer is claimed by a2 (a1 claiming it would put its own back on the board), and b1, its poster, is told."""
    own = made(a_task(t.a1, group="ai", text="Check the base case [h1]", responsible="a1"))
    refusal = NOT_YOURS.format(id=own["id"], agent="a1")
    for change in ({"text": "b1's idea of it"}, {"remove": True}, {"responsible": "b1"}, {"responsible": ""}):
        r = a_task(t.b1, id=own["id"], **change)
        assert r.status_code == 403 and err(r) == "not_yours" and r.json()["message"] == refusal, (change, r.text)
    r = a_task(t.b1, group="ai", text="For a1: the inductive step [h2]", responsible="a1")
    assert r.status_code == 403 and err(r) == "ask_first" and r.json()["message"] == ASK_FIRST.format(agent="a1"), r.text

    offer = made(a_task(t.b1, group="ai", text="Open: the inductive step [h2]"))
    assert made(a_task(t.a2, id=offer["id"], responsible="a2"))["responsible"] == "a2", "the other agent claims it itself"
    r = a_task(t.b1, id=offer["id"], responsible="a2")
    assert r.status_code == 403, "once it is a2's, b1 has no hand in it"
    claimed = f"a2 gave task {offer['id']} [ai] to a2: Open: the inductive step [h2]"
    assert told(t.b1, claimed)["message"]["level"] == "normal", "its poster is told it was taken (1t)"

    leave(t.a1)                                             # a1 is offline now; its tasks stay its own
    assert until(lambda: not t.alice.is_online("a1"), 5)
    r = a_task(t.b1, id=own["id"], responsible="b1")
    assert r.status_code == 403 and err(r) == "not_yours"
    assert r.json()["message"] == NOT_YOURS_OFFLINE.format(id=own["id"], agent="a1", person="alice"), r.text
    t.alice.switches(others_assign=True)
    try:
        r = a_task(t.b1, id=own["id"], text="while it is away, also change it")
        assert r.status_code == 403 and err(r) == "not_yours", "taking it over is the only thing allowed"
        assert made(a_task(t.b1, id=own["id"], responsible="b1"))["responsible"] == "b1"
        said = f"b1 took task {own['id']} [ai] from a1."
        assert level_for(t.alice, said) == "muted"
        come_back(t, t.a1)
        assert told(t.a1, said)["message"]["level"] == "important", "it is handed the message when it is back"
        r = a_task(t.b1, id=offer["id"], responsible="b1")
        assert r.status_code == 403 and err(r) == "not_yours" and r.json()["message"] == NOT_YOURS.format(id=offer["id"], agent="a2"), \
            "its holder is online: ask it, switch or no switch"
    finally:
        t.alice.switches(others_assign=False)
        if not t.alice.is_online("a1"):
            come_back(t, t.a1)
    wipe(t)


# ------------------------------------------------------------------ busy and idle

def test_a_busy_agent_is_not_sent_channel_talk(t):
    t.a2.say("I am following this channel [b0]", to="#general")           # a recent speaker here, online, idle
    t.alice.say("a thought for whoever listens [b1]")
    assert t.a2.take("[b1]")["message"]["level"] == "normal"
    held = made(a_task(t.a2, group=OWN_A, text="Now I have work [b2]", responsible="a2"))
    t.a2.say("still here [b3]", to="#general")
    t.alice.say("another thought [b4]")
    t.a2.absent("[b4]")
    seen = [m for m in t.a2.messages(place="#general", limit=200).json()["messages"] if "[b4]" in m["text"]]
    assert seen and seen[0]["level"] == "muted", "it is there to read"
    sent = t.alice.say("@a2 but a mention still reaches it [b5]")
    assert t.a2.take("[b5]")["message"]["level"] == "important"
    t.a2.say("yes [b5a]", reply_to=sent["id"])
    made(a_task(t.a2, id=held["id"], responsible=""))
    t.a2.say("free again [b6]", to="#general")
    t.alice.say("a last thought [b7]")
    t.a2.take("[b7]")
    wipe(t)


# ------------------------------------------------------------------ notices of presence

def test_presence_is_told_to_busy_agents_when_it_moves_the_work(t):
    """The two changes that count: an agent with a task goes offline; an agent without one comes online."""
    made(a_task(t.a1, group=OWN_A, text="a1's work [n0]", responsible="a1"))      # a1: busy, and a sibling of a2
    made(a_task(t.b1, group=OWN_B, text="b1's work [n0]", responsible="b1"))      # b1: busy, but not close to a2

    leave(t.a2)                                             # 1. no task, goes offline: nobody's work moves
    assert level_for(t.alice, "a2 is offline.") == "muted"
    not_told(t.a1, "a2 is offline.", 1.5)

    come_back(t, t.a2)                                      # 2. no task, comes online: there is a free agent
    got = until(lambda: notices(t.a1, "a2 is online."), 6)
    assert got and got[-1]["message"]["level"] == "normal"
    assert got[-1]["frame"].endswith("\n" + RECOORDINATE) and "No answer needed.)" not in got[-1]["frame"]
    assert level_for(t.alice, "a2 is online.") == "normal" and level_for(t.bob, "a2 is online.") == "muted"
    assert not notices(t.b1, "a2 is online."), "an agent of someone else is not close"

    long = "Check every constant\nin section 4 " + "and then the next one " * 6 + "[n1]"   # 1t: one task, a long title
    first = made(p_make(t.alice, group=OWN_A, text=long, body="Sections 4.1 to 4.3; " * 20, responsible="a2"))
    told(t.a2, f"alice assigned task {first['id']} [{OWN_A}] to a2: {clip(long)}")
    off = f"a2 is offline. Its tasks:\n{first['id']} [{OWN_A}] {clip(long)}"    # its title, cut; not its body
    assert len(clip(long)) == 121 and "\n" not in clip(long)
    leave(t.a2)                                             # 3. with a task, goes offline: its work is unattended
    got = until(lambda: notices(t.a1, off), 6)
    assert got and got[-1]["message"]["level"] == "normal" and got[-1]["frame"].endswith("\n" + RECOORDINATE)
    assert level_for(t.alice, off) == "important", "alice assigned it"
    assert level_for(t.bob, off) == "muted" and level_for(t.carol, off) == "muted"
    assert not notices(t.b1, off)

    come_back(t, t.a2)                                      # 4. with a task, back online: nothing to settle
    on = off.replace("is offline.", "is online.")
    assert level_for(t.alice, on) == "muted"
    time.sleep(1.5)
    assert not notices(t.a1, on)

    for x in a_tasks(t.a1):                                 # an idle agent is woken by none of this
        if x["responsible"] == "a1":
            made(a_task(t.a1, id=x["id"], responsible=""))
    assert until(lambda: not busy(t.alice, "a1"), 3)
    seen_before = len([d for d in t.a1.got if d.get("kind") == "notice"])
    leave(t.a2)
    assert until(lambda: len(system_messages(t.alice, off)) == 2, 6)
    time.sleep(1.5)
    assert len([d for d in t.a1.got if d.get("kind") == "notice"]) == seen_before, "a1 holds no task now"
    come_back(t, t.a2)
    wipe(t)


def test_the_notice_names_only_the_task_the_agent_holds(t):
    """Before 1t an agent could hold many tasks and the notice cut the list after ten. Now it holds one: an agent that
    took twelve in turn holds the last, the others went back to the board, and the notice names that one."""
    ids = [made(a_task(t.a2, group=OWN_A, text=f"piece {i} [m1]", responsible="a2"))["id"] for i in range(12)]
    assert [x["id"] for x in a_tasks(t.a2) if x["responsible"] == "a2"] == ids[-1:]
    leave(t.a2)
    off = f"a2 is offline. Its tasks:\n{ids[-1]} [{OWN_A}] piece 11 [m1]"
    assert level_for(t.alice, off) == "normal", "alice is close to her own agent"
    come_back(t, t.a2)
    wipe(t)


# ------------------------------------------------------------------ an agent that coordinates

def test_a_coordinating_agent_changes_tasks_directly(t):
    """The user's rule of 2026-11-15: a group may carry the permission to coordinate. An agent that holds it
    changes the tasks of other people's agents directly, where their person has opened them to others; the
    agent concerned is told at level important. It never locks, and a person's lock holds against it."""
    r = t.alice.c.post(f"/{SLUG}/api/groups", json={"name": "coordinators", "permissions": ["coordinate_tasks"]})
    assert r.status_code == 201, r.text
    for member, who in (("bob", t.alice), ("b1", t.bob)):   # an agent holds no permission its person lacks
        r = who.c.post(f"/{SLUG}/api/members/{member}/groups", json={"add": ["coordinators"], "remove": []})
        assert r.status_code == 200, r.text
    own = made(a_task(t.a1, group="ai", text="Check the base case [c1]", responsible="a1"))
    closed = "a1 is an agent of alice, who has not allowed others to give it tasks or to change its tasks."
    for attempt in (a_task(t.b1, id=own["id"], text="b1 rewrites it"), a_task(t.b1, id=own["id"], remove=True),
                    a_task(t.b1, group="ai", text="for a1 [c2]", responsible="a1")):
        assert attempt.status_code == 403 and err(attempt) == "forbidden" and attempt.json()["message"] == closed, attempt.text

    t.alice.switches(others_assign=True)
    try:
        new = "Check the base case, and n = 2 separately [c1]"
        assert made(a_task(t.b1, id=own["id"], text=new))["assigned_by"] is None, "an agent never locks"
        d = told(t.a1, f"b1 changed task {own['id']} [ai] of a1: {new}")
        assert d["message"]["level"] == "important"
        assert d["frame"].endswith(f"(Asterism message. To answer: send with reply_to={d['message']['id']}.)")
        assert t.a1.send("understood [c1a]", reply_to=d["message"]["id"]).status_code == 200

        given = made(a_task(t.b1, group="ai", text="Then the inductive step [c2]", responsible="a1"))
        assert given["assigned_by"] is None
        assert told(t.a1, f"b1 gave task {given['id']} [ai] to a1: Then the inductive step [c2]")["message"]["level"] == "important"
        assert told(t.a1, f"b1 took task {own['id']} [ai] from a1.")["message"]["level"] == "important", \
            "one task per agent (1t): the one a1 held went back to the board"
        assert table(t.alice)[own["id"]]["responsible"] is None
        assert made(a_task(t.a1, id=given["id"], text="The inductive step, my way [c2]"))["responsible"] == "a1", \
            "it is a1's to shape: nothing is locked"
        assert made(a_task(t.b1, id=given["id"], responsible="b1"))["responsible"] == "b1", "online or not, it may take it"
        assert told(t.a1, f"b1 took task {given['id']} [ai] from a1.")["message"]["level"] == "important"

        made(a_task(t.a1, id=own["id"], responsible="a1"))  # a1, free again, takes back the one that went to the board
        assert a_task(t.b1, id=own["id"], remove=True).status_code == 200
        assert told(t.a1, f"b1 removed task {own['id']} [ai] of a1.")["message"]["level"] == "important"
        locked = made(p_make(t.alice, group="ai", text="alice's own order [c3]", responsible="a2"))   # not a1: it takes c4 below
        r = a_task(t.b1, id=locked["id"], text="a coordinator's idea of it")
        assert r.status_code == 403 and err(r) == "task_locked", "a person's lock holds against a coordinator too"
    finally:
        t.alice.switches(others_assign=False)
        t.bob.c.post(f"/{SLUG}/api/members/b1/groups", json={"add": [], "remove": ["coordinators"]})
        t.alice.c.post(f"/{SLUG}/api/members/bob/groups", json={"add": [], "remove": ["coordinators"]})
    again = made(a_task(t.a1, group="ai", text="back to asking [c4]", responsible="a1"))
    assert err(a_task(t.b1, id=again["id"], text="x")) == "not_yours", "without the permission it asks, as before"
    wipe(t)


# ------------------------------------------------------------------ tasks that lose their member (this test removes bob: keep it last)

def test_a_member_that_leaves_stops_being_responsible(t):
    for member in ("alice", "a1"):
        t.alice.c.post(f"/{SLUG}/api/members/{member}/groups", json={"add": ["topic"], "remove": []})
    held = made(p_make(t.alice, group="topic", text="The topic's open question [z1]", responsible="a1"))
    assert held["assigned_by"] == "alice"
    r = t.alice.c.post(f"/{SLUG}/api/members/a1/groups", json={"add": [], "remove": ["topic"]})
    assert r.status_code == 200, r.text
    after = table(t.alice)[held["id"]]
    assert (after["responsible"], after["assigned_by"]) == (None, None), "the task stays, with nobody responsible"
    assert told(t.a1, f"alice took task {held['id']} [topic] from a1.")["message"]["level"] == "important"

    t.alice.switches(others_assign=True)
    kept = made(p_make(t.bob, group="ai", text="Bob wanted this done [z2]", responsible="a1"))
    theirs = made(a_task(t.b1, group="ai", text="b1's own [z3]", responsible="b1"))
    assert kept["assigned_by"] == "bob"
    r = t.alice.c.post(f"/{SLUG}/api/members/bob/remove")
    assert r.status_code == 200, r.text
    now = table(t.alice)
    assert (now[kept["id"]]["responsible"], now[kept["id"]]["assigned_by"]) == ("a1", None), \
        "whoever assigned it is gone: the task stays with the agent, unlocked"
    assert now[theirs["id"]]["responsible"] is None, "b1 went with bob"
    assert made(a_task(t.a1, id=kept["id"], text="mine to shape now [z2]"))["assigned_by"] is None
