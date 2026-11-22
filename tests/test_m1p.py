"""Slice 1p: a private message is important for an agent only when it mentions it (otherwise normal: handed over, no
answer owed); an unanswered important message is reminded about at most twice.

    python -m pytest tests/test_m1p.py -q
"""
from __future__ import annotations

import time

import pytest

from test_m1b import OFFLINE_S, build_world, until
from test_m1b2 import ENV2, REMIND_S, fresh, leave, of_kind, tool_call


@pytest.fixture(scope="module")
def v(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datap"), ENV2)     # short reminder times
    yield world
    world.srv.stop()


def test_a_private_message_owes_an_answer_only_when_it_mentions_its_reader(v):
    one, two = fresh(v, "p1"), fresh(v, "p2")                 # both are alice's agents
    two.say("a result for you, nothing to answer [q1]", to="p1")
    assert one.take("[q1]")["message"]["level"] == "normal", "handed over, and normal"
    v.alice.say("a note from your person [q2]", to="p1")
    assert one.take("[q2]")["message"]["level"] == "normal"
    time.sleep(REMIND_S * 2 + 1.5)
    assert not of_kind(one, "reminder"), "a normal message is never reminded about"
    assert not [m for m in one.messages().json()["messages"] if "[q" in m["text"]], "nor among the unread important ones"

    asked = two.say("@p1 please confirm the constant [q3]", to="p1")
    assert one.take("[q3]")["message"]["level"] == "important"
    got = until(lambda: of_kind(one, "reminder"), REMIND_S + 5)
    assert got and got[0]["about"] == asked["id"], "a mention asks for an answer, in a private conversation too"
    one.say("confirmed [q3a]", to="p2", reply_to=asked["id"])
    assert two.take("[q3a]")["message"]["level"] == "normal", "an answer owes no answer"
    time.sleep(REMIND_S + 1.5)
    assert not of_kind(two, "reminder")
    leave(one)
    leave(two)


def test_a_normal_private_message_waits_for_an_agent_that_is_away(v):
    away = fresh(v, "p3")
    away._stop.set()                                           # its helper stops polling: offline after a while
    assert until(lambda: not v.alice.is_online("p3"), OFFLINE_S + 8)
    v.alice.say("for when you are back [q4]", to="p3")
    away.absent("[q4]", 1.0)
    away.online()
    assert away.take("[q4]", 12)["message"]["level"] == "normal", "handed over when it comes back, as an important one is"
    leave(away)


def test_an_unanswered_message_is_reminded_about_twice_at_most(v):
    busy = fresh(v, "p4")
    v.alice.say("@p4 answer me [q5]")
    busy.take("[q5]")
    end = time.time() + REMIND_S * 5 + 2
    while time.time() < end:                                   # active the whole time, never answering
        tool_call(busy)
        time.sleep(0.8)
    assert len(of_kind(busy, "reminder")) == 2, "two reminders, then no more"
    assert v.alice.is_online("p4")
    leave(busy)
