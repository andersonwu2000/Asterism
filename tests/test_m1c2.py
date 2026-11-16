"""Acceptance tests for slice 1c, step c2: pins on channels and scheduled messages.

Black box: a real server process on localhost; people through the session cookie, agents through the agent API.

    python -m pytest tests/test_m1c2.py -q
"""
from __future__ import annotations

import datetime
import json
import re
import time
import urllib.parse

import httpx
import pytest

from test_m1b import ENV, SLUG, Person, build_world, frame, until
from test_m1b2 import leave, of_kind

MIN_EVERY_S, REMIND_S, REDELIVER_WAIT = 2, 6, 1.5
ENVS = dict(ENV, ASTERISM_SCHEDULE_MIN_EVERY_S=str(MIN_EVERY_S))
REPO = "https://github.com/example/lab"
REMINDER = "You have not answered message {id} from {sender}. Answer with send, reply_to={id}."


@pytest.fixture(scope="module")
def s(tmp_path_factory):
    """alice owns the project and has the agents a1 and a2; bob has b1; carol has none. All agents are online.
    `human` only reads and posts; what it held beyond that is held by `planners`, which alice and bob are in, carol not
    (default groups are never left by hand, f6: a person is limited through the default group's permissions)."""
    world = build_world(tmp_path_factory.mktemp("datac2"), ENVS)
    more = ["create_channel", "create_schedule", "assign_tasks", "manage_own_agents", "edit_tasks"]
    assert world.alice.c.post(f"/{SLUG}/api/groups", json={"name": "planners", "permissions": ["read", "post"] + more}).status_code == 201
    for who in ("alice", "bob"):
        r = world.alice.c.post(f"/{SLUG}/api/members/{who}/groups", json={"add": ["planners"], "remove": []})
        assert r.status_code == 200, r.text
    r = world.alice.c.post(f"/{SLUG}/api/groups/human", json={"permissions": ["read", "post"]})
    assert r.status_code == 200, r.text
    yield world
    world.srv.stop()


# ------------------------------------------------------------------ helpers

def err(r: httpx.Response) -> str:
    return r.json().get("error", "")


def now_iso(plus: float = 0.0) -> str:
    at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=plus)
    return at.strftime("%Y-%m-%dT%H:%M:%SZ")


def pin(person: Person, channel="general", **body) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/channels/{channel}/pins", json=body)


def unpin(person: Person, pid: int, channel="general") -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/channels/{channel}/pins/{pid}/remove")


def schedule(person: Person, **body) -> httpx.Response:
    body.setdefault("start_at", now_iso())
    body.setdefault("level", "muted")
    body.setdefault("to", "#general")
    return person.c.post(f"/{SLUG}/api/schedules", json=body)


def made(r: httpx.Response) -> dict:
    assert r.status_code in (200, 201), r.text
    return r.json()["schedule"]


def change(person: Person, sid: int, **body) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/schedules/{sid}", json=body)


def remove(person: Person, sid: int) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/schedules/{sid}/remove")


def schedules(person: Person) -> dict[int, dict]:
    r = person.c.get(f"/{SLUG}/api/schedules")
    assert r.status_code == 200, r.text
    return {x["id"]: x for x in r.json()["schedules"]}


def posted(person: Person, tag: str, place="#general") -> list[dict]:
    return [m for m in person.read(place) if tag in m["text"]]


def one_run(person: Person, tag: str, place="#general") -> dict:
    """The single message a schedule that runs once has posted."""
    found = until(lambda: posted(person, tag, place), 6)
    assert found and len(found) == 1, found
    return found[0]


def logged(w, event: str, **fields) -> list[dict]:
    lines = (w.srv.data / "log.jsonl").read_text(encoding="utf-8").splitlines()
    out = [e for e in map(json.loads, filter(str.strip, lines)) if e.get("event") == event]
    return [e for e in out if all(e.get(k) == x for k, x in fields.items())]


# ------------------------------------------------------------------ pins

def test_files_and_messages_are_pinned_to_a_channel(s):
    before = len([m for m in s.alice.read() if m["from_kind"] == "system"])
    r = pin(s.bob, path="  notes/MAP.md ")
    assert r.status_code == 201, r.text
    one = r.json()["pin"]
    assert one == {"id": one["id"], "kind": "file", "path": "notes/MAP.md", "url": REPO + "/blob/HEAD/notes/MAP.md", "by": "bob"}
    odd = pin(s.alice, path="notes/研究 圖景.md").json()["pin"]
    assert odd["url"] == REPO + "/blob/HEAD/notes/" + urllib.parse.quote("研究 圖景.md"), "each segment is percent-encoded"

    said = s.bob.say("The plan for this week: " + "one more step, " * 12 + "[pn1]")
    two = pin(s.alice, message=said["id"])
    assert two.status_code == 201, two.text
    two = two.json()["pin"]
    cut = " ".join(("The plan for this week: " + "one more step, " * 12 + "[pn1]").split())[:120] + "…"
    assert two == {"id": two["id"], "kind": "message", "message": said["id"], "from": "bob", "text": cut, "by": "alice"}

    for bad in ("", "   ", "/abs/path.md", "a/../b.md", "a\\b.md", "a//b.md", "./a.md", "a/./b.md", "x" * 301, "a\nb.md"):
        r = pin(s.alice, path=bad)
        assert r.status_code == 400 and err(r) == "bad_request", repr(bad)
    assert pin(s.alice, path="x" * 300).status_code == 201, "300 characters is still a path"
    assert err(pin(s.alice)) == "bad_request" and err(pin(s.alice, path="a.md", message=said["id"])) == "bad_request"
    assert pin(s.alice, message=999_999).status_code == 404
    assert s.alice.c.post(f"/{SLUG}/api/channels", json={"name": "side"}).status_code == 201
    elsewhere = s.alice.say("said in the side channel [pn2]", to="#side")
    r = pin(s.alice, message=elsewhere["id"])
    assert r.status_code == 400 and "#side" in r.json()["message"], "a channel pins its own messages"
    assert pin(s.alice, "side", message=elsewhere["id"]).status_code == 201
    assert pin(s.alice, "nowhere", path="a.md").status_code == 404
    assert pin(s.alice, path="notes/MAP.md").status_code == 409 and pin(s.bob, message=said["id"]).status_code == 409
    r = pin(s.carol, path="carol.md")
    assert r.status_code == 403 and err(r) == "forbidden", "carol may read and post, not arrange channels"
    assert unpin(s.carol, one["id"]).status_code == 403

    for i in range(6):                                      # four are there; six more make ten
        assert pin(s.alice, path=f"fill/{i}.md").status_code == 201
    r = pin(s.alice, path="one-too-many.md")
    assert r.status_code == 409 and ("10" in r.json()["message"] or "ten" in r.json()["message"]), r.text

    general = s.carol.channel("general")
    assert [p["id"] for p in general["pins"]][:3] == [one["id"], odd["id"], two["id"]], "oldest first, for everyone"
    assert len(general["pins"]) == 10 and len(s.carol.channel("side")["pins"]) == 1
    who = s.a1.c.get(f"/{SLUG}/api/agent/whoami").json()
    seen = next(c for c in who["channels"] if c["name"] == "general")["pins"]
    assert seen[:3] == [{"file": "notes/MAP.md"}, {"file": "notes/研究 圖景.md"}, {"message": said["id"]}]
    assert next(c for c in who["channels"] if c["name"] == "side")["pins"] == [{"message": elsewhere["id"]}]

    r = unpin(s.bob, odd["id"])
    assert r.status_code == 200 and r.json() == {"removed": odd["id"]}
    assert unpin(s.bob, odd["id"]).status_code == 404 and unpin(s.bob, two["id"], "side").status_code == 404
    assert odd["id"] not in [p["id"] for p in s.alice.channel("general")["pins"]]
    assert pin(s.alice, path="room-again.md").status_code == 201
    assert len([m for m in s.alice.read() if m["from_kind"] == "system"]) == before, "nobody is told about a pin"
    page = s.alice.c.get(f"/{SLUG}")
    assert page.status_code == 200 and 'id="pins"' not in page.text, "the page shows no pins (the user's ruling, f4)"


# ------------------------------------------------------------------ scheduled messages

def test_a_schedule_posts_in_its_creators_name_at_its_own_level(s):
    text = "@b1 @a2 everybody: where do you stand? [sc1]"
    r = schedule(s.alice, text=text, level="important")
    assert r.status_code == 201, r.text
    sch = r.json()["schedule"]
    assert (sch["by"], sch["to"], sch["text"], sch["level"], sch["every_s"], sch["paused"]) == \
        ("alice", "#general", text, "important", None, False)
    m = one_run(s.bob, "[sc1]")
    assert (m["from"], m["from_kind"], m["scheduled"], m["mentions"], m["level"]) == ("alice", "person", True, [], "important"), \
        "important for every person, and an @ in the text mentions nobody"
    for own in (s.a1, s.a2):
        d = own.take("[sc1]")
        assert (d["message"]["from"], d["message"]["relation"], d["message"]["level"]) == ("alice", "your own user", "important")
        assert d["frame"] == frame(d["message"])
        own.say("here [sc1a]", reply_to=m["id"])
    s.b1.absent("[sc1]")
    seen = [x for x in s.b1.messages(place="#general", limit=200).json()["messages"] if "[sc1]" in x["text"]]
    assert seen and seen[0]["level"] == "muted", "bob has not opened his agents to others' mentions"
    assert until(lambda: sch["id"] not in schedules(s.alice), 4), "a schedule that runs once is gone when it has run"
    assert logged(s, "schedule_run", schedule=sch["id"], message=m["id"])

    s.bob.switches(others_mention=True)
    try:
        made(schedule(s.alice, text="and with the switch open [sc2]", level="important"))
        d = s.b1.take("[sc2]")
        assert (d["message"]["relation"], d["message"]["level"]) == ("another collaborator", "important")
        for agent in (s.a1, s.a2, s.b1):
            agent.take("[sc2]")
            agent.say("noted [sc2a]", reply_to=d["message"]["id"])
    finally:
        s.bob.switches(others_mention=False)


def test_normal_and_muted_schedules(s):
    r = s.a1.c.post(f"/{SLUG}/api/agent/task", json={"group": "alice-agents", "text": "busy with this [sc]", "responsible": "a1"})
    assert r.status_code == 200, r.text
    assert s.alice.c.post(f"/{SLUG}/api/channels/general/mute", json={"muted": True, "agent": "a2"}).status_code == 200
    assert s.carol.c.post(f"/{SLUG}/api/channels/general/mute", json={"muted": True}).status_code == 200
    try:
        made(schedule(s.alice, text="for whoever is around [sc3]", level="normal"))
        d = s.a1.take("[sc3]")
        assert d["message"]["level"] == "normal" and d["frame"].endswith("(Asterism message. No answer needed.)"), \
            "its own user's schedule reaches it though it is busy: the schedule's level decides"
        s.a2.absent("[sc3]", 1.0)
        s.b1.absent("[sc3]", 0.2)
        assert one_run(s.bob, "[sc3]")["level"] == "normal" and one_run(s.carol, "[sc3]")["level"] == "muted"

        made(schedule(s.alice, text="only to be found later [sc4]", level="muted"))
        assert one_run(s.bob, "[sc4]")["level"] == "muted"
        s.a1.absent("[sc4]", 1.0)
    finally:
        s.alice.c.post(f"/{SLUG}/api/channels/general/mute", json={"muted": False, "agent": "a2"})
        s.carol.c.post(f"/{SLUG}/api/channels/general/mute", json={"muted": False})
        tid = r.json()["task"]["id"]
        s.a1.c.post(f"/{SLUG}/api/agent/task", json={"id": tid, "remove": True})


def test_a_schedule_goes_where_its_creator_may_write(s):
    made(schedule(s.alice, to="a1", text="between the two of us [sc5]", level="important"))
    d = s.a1.take("[sc5]")
    assert d["message"].get("private") is True and d["message"]["level"] == "important" and 'in="private"' in d["frame"]
    s.a1.say("yes [sc5a]", reply_to=d["message"]["id"])
    s.a2.absent("[sc5]", 0.5)
    assert posted(s.bob, "[sc5]") == []

    r = schedule(s.alice, to="b1", text="not hers to write to [sc6]")
    assert r.status_code == 403, "nobody but its own person writes privately to an agent"
    assert schedule(s.alice, to="#nowhere", text="x").status_code == 404
    made(schedule(s.bob, to="alice", text="person to person [sc7]", level="normal"))
    assert one_run(s.alice, "[sc7]", place="bob")["level"] == "normal", "the schedule's level, in a private conversation too"

    assert schedule(s.carol, text="carol may not schedule [sc8]").status_code == 403
    for bad in ({"level": "loud"}, {"every_s": MIN_EVERY_S - 1}, {"every_s": "often"}, {"text": ""}, {"text": "x" * 4_001},
                {"start_at": "tomorrow"}, {"start_at": None}):
        r = schedule(s.alice, **{"text": "never posted [sc9]", **bad})
        assert r.status_code == 400, (bad, r.text)
    time.sleep(1.0)
    assert posted(s.alice, "[sc9]") == [] and posted(s.alice, "[sc8]") == []


def test_a_repeating_schedule_can_be_paused_changed_and_removed(s):
    sch = made(schedule(s.bob, text="tick [rp1]", every_s=MIN_EVERY_S))
    assert sch["every_s"] == MIN_EVERY_S and sch["next_at"]
    assert until(lambda: len(posted(s.alice, "[rp1]")) >= 2, 8), "it keeps running"
    now = schedules(s.carol)[sch["id"]]
    assert now["last_message"] == posted(s.alice, "[rp1]")[-1]["id"], "every member sees every schedule"

    assert change(s.carol, sch["id"], paused=True).status_code == 403
    assert change(s.alice, sch["id"], text="alice's words in bob's mouth").status_code == 403, "only the creator changes what it says"
    assert made(change(s.alice, sch["id"], paused=True))["paused"] is True, "the owner may stop it"
    time.sleep(0.3)
    count = len(posted(s.alice, "[rp1]"))
    time.sleep(MIN_EVERY_S * 2 + 0.5)
    assert len(posted(s.alice, "[rp1]")) == count, "paused: nothing is posted"

    time.sleep(MIN_EVERY_S)                                 # three times or more have been missed by now
    again = made(change(s.bob, sch["id"], paused=False, text="tock [rp1]"))
    assert again["paused"] is False and again["paused_because"] is None
    time.sleep(1.0)
    after = len(posted(s.alice, "[rp1]"))
    assert count + 1 <= after <= count + 2, "what was missed is made up for by one run, at once (and one more may be due)"
    assert posted(s.alice, "[rp1]")[-1]["text"] == "tock [rp1]"
    assert until(lambda: len(posted(s.alice, "[rp1]")) >= after + 1, MIN_EVERY_S + 2), "and then it goes on"

    assert remove(s.carol, sch["id"]).status_code == 403
    r = remove(s.alice, sch["id"])
    assert r.status_code == 200 and r.json() == {"removed": sch["id"]} and sch["id"] not in schedules(s.bob)
    time.sleep(0.3)
    count = len(posted(s.alice, "[rp1]"))
    time.sleep(MIN_EVERY_S + 1.0)
    assert len(posted(s.alice, "[rp1]")) == count
    assert change(s.bob, sch["id"], paused=True).status_code == 404


def test_time_missed_while_the_server_was_down_is_made_up_once(s):
    sch = made(schedule(s.alice, text="heartbeat [dn1]", every_s=MIN_EVERY_S))
    assert until(lambda: len(posted(s.bob, "[dn1]")) >= 1, 5)
    s.srv.stop()
    time.sleep(MIN_EVERY_S * 4 + 1)                          # four runs are missed
    count = None
    try:
        s.srv.start()
        time.sleep(0.8)
        count = len(posted(s.bob, "[dn1]"))
    finally:
        if count is not None:
            assert remove(s.alice, sch["id"]).status_code == 200
    assert count <= len(logged(s, "schedule_run", schedule=sch["id"])) <= count + 1, "every run is in the log"
    assert count in (2, 3, 4), f"{count} posted: before the stop there were one or two; after it one run makes up for four"
    page = s.alice.c.get(f"/{SLUG}/schedules")
    assert page.status_code == 200 and 'id="schedules"' in page.text and 'id="schedule-form"' in page.text
    assert 'id="schedule-form"' not in s.carol.c.get(f"/{SLUG}/schedules").text, "no form for who may not create"


def test_a_schedule_whose_person_or_place_is_gone(s):
    """This test removes bob from the project: keep it the last one that uses the shared world."""
    theirs = made(schedule(s.bob, text="bob's own [gn1]", every_s=MIN_EVERY_S))
    to_bob = made(schedule(s.alice, to="bob", text="alice to bob [gn2]", every_s=MIN_EVERY_S, level="normal"))
    assert until(lambda: posted(s.alice, "[gn1]") and posted(s.alice, "[gn2]", place="bob"), 6)
    assert s.alice.c.post(f"/{SLUG}/api/members/bob/remove").status_code == 200
    assert until(lambda: schedules(s.alice).get(to_bob["id"], {}).get("paused"), 6), "a schedule with nowhere to go is paused"
    now = schedules(s.alice)
    assert theirs["id"] not in now, "a person's schedules go with the person"
    assert now[to_bob["id"]]["paused_because"] == "target"
    assert logged(s, "schedule_paused", schedule=to_bob["id"], because="target")
    r = change(s.alice, to_bob["id"], paused=False)
    assert r.status_code == 409 and err(r) == "conflict", "it cannot be resumed as it is"
    assert made(change(s.alice, to_bob["id"], to="#general", paused=False))["paused"] is False
    assert remove(s.alice, to_bob["id"]).status_code == 200

    # the creator loses the permission: carol's group is given it, a schedule is made, and it is taken away again
    assert s.alice.c.post(f"/{SLUG}/api/members/carol/groups", json={"add": ["planners"], "remove": []}).status_code == 200
    hers = made(schedule(s.carol, text="while she may [gn3]", every_s=MIN_EVERY_S))
    assert until(lambda: posted(s.alice, "[gn3]"), 5)
    assert s.alice.c.post(f"/{SLUG}/api/members/carol/groups", json={"add": [], "remove": ["planners"]}).status_code == 200
    assert until(lambda: schedules(s.alice)[hers["id"]]["paused"], 6)
    assert schedules(s.alice)[hers["id"]]["paused_because"] == "permission"
    assert remove(s.alice, hers["id"]).status_code == 200


# ------------------------------------------------------------------ one schedule never stacks the answers owed

def test_an_agent_owes_one_answer_to_a_schedule_however_often_it_ran(tmp_path):
    """The user's rule of 2026-11-15: the newest message of a schedule is the one to answer; the earlier ones
    become muted for the agent that still owed their answer. The follow-up's clock is not started again, or a
    schedule that runs more often than the reminder would keep an agent from ever being reminded."""
    (tmp_path / "datastack").mkdir()
    w = build_world(tmp_path / "datastack", dict(ENVS, ASTERISM_REMIND_AFTER_S=str(REMIND_S)))
    try:
        sch = made(schedule(w.alice, to="a1", text="where do you stand? [st1]", level="important", every_s=MIN_EVERY_S))
        assert until(lambda: len(w.a1.tagged("[st1]")) >= 3, MIN_EVERY_S * 3 + 2), "every run is put in front of it"
        got = until(lambda: of_kind(w.a1, "reminder"), REMIND_S + 4)
        assert got, "the clock runs from the first message: it is reminded although the schedule keeps posting"
        named = re.fullmatch(REMINDER.format(id="X", sender="alice").replace("X", "([0-9]+)").replace(".", "[.]"), got[0]["frame"])
        assert named and named.group(1) == named.group(2), got[0]["frame"]
        first = min(d["message"]["id"] for d in w.a1.tagged("[st1]"))
        assert int(named.group(1)) > first, "the reminder names the newest message of the schedule, not the first"

        assert made(change(w.alice, sch["id"], paused=True))["paused"] is True
        time.sleep(0.5)
        ids = sorted(d["message"]["id"] for d in w.a1.tagged("[st1]"))
        levels = {i: w.a1.messages(id=i).json()["messages"][0]["level"] for i in ids}
        assert len(ids) >= 3 and levels[ids[-1]] == "important", levels
        assert all(levels[i] == "muted" for i in ids[:-1]), f"the earlier ones are muted for it now: {levels}"
        w.a1.say("here is where I stand [st1a]", reply_to=ids[-1])
        reminders = len(of_kind(w.a1, "reminder"))
        time.sleep(REMIND_S + 1.5)
        assert len(of_kind(w.a1, "reminder")) == reminders, "one answer, to the newest, settles all of them"
        assert w.alice.is_online("a1")
        assert remove(w.alice, sch["id"]).status_code == 200

        # the case the rule was made for: an agent that was away while the schedule ran
        leave(w.a2)
        assert until(lambda: not w.alice.is_online("a2"), 5)
        away = made(schedule(w.alice, to="a2", text="report when you are back [st2]", level="important", every_s=MIN_EVERY_S))
        assert until(lambda: len(posted(w.alice, "[st2]", place="a2")) >= 3, MIN_EVERY_S * 3 + 2)
        assert made(change(w.alice, away["id"], paused=True))["paused"] is True
        time.sleep(0.5)
        ran = [m["id"] for m in posted(w.alice, "[st2]", place="a2")]
        w.a2.register("a2")
        assert until(lambda: w.alice.is_online("a2"), 6)
        assert until(lambda: w.a2.tagged("[st2]"), 6), "what waited for it is handed over when it is back"
        time.sleep(REDELIVER_WAIT)
        handed = [d["message"]["id"] for d in w.a2.tagged("[st2]")]
        assert handed == [ran[-1]], f"one message, the newest, however often it ran while the agent was away: {handed} of {ran}"
        assert w.a2.unread("alice") == 0, "the runs it no longer has to answer are not left as unread either"
        w.a2.say("back, and here is my report [st2a]", reply_to=ran[-1])
        assert remove(w.alice, away["id"]).status_code == 200
    finally:
        w.srv.stop()
