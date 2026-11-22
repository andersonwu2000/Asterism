"""A write that is retried is done once: the header Idempotency-Key on every POST of the API, for people and agents.

    python -m pytest tests/test_m1r.py -q
"""
from __future__ import annotations

import re
import secrets
import threading
import time

import httpx
import pytest

from test_m1b import ENV, ROOT, SLUG, build_world

KEEP_S = 4


@pytest.fixture(scope="module")
def r(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datar"), dict(ENV, ASTERISM_REPLAY_KEEP_S=str(KEEP_S)))
    yield world
    world.srv.stop()


def key() -> str:
    return secrets.token_hex(16)


def k(value: str) -> dict:
    return {"Idempotency-Key": value}


def texts(person, tag: str) -> list[dict]:
    return [m for m in person.read("#general") if tag in m["text"]]


def status_of(agent) -> dict:
    got = agent.c.get(f"/{SLUG}/api/agent/statuses")
    assert got.status_code == 200, got.text
    return next(x for x in got.json()["statuses"] if x["agent"] == agent.name)


# ------------------------------------------------------------------ agents

def test_an_agents_message_sent_twice_with_one_key_is_posted_once(r):
    kk = key()
    body = {"to": "#general", "text": "once only [r1]"}
    first = r.a1.c.post(f"/{SLUG}/api/agent/send", json=body, headers=k(kk))
    again = r.a1.c.post(f"/{SLUG}/api/agent/send", json=body, headers=k(kk))
    assert first.status_code == 200, first.text
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"], again.text
    assert again.headers.get("idempotent-replayed") == "true"
    assert "idempotent-replayed" not in first.headers
    assert len(texts(r.alice, "[r1]")) == 1


def test_without_a_key_nothing_changes(r):
    body = {"to": "#general", "text": "twice on purpose [r2]"}
    for _ in range(2):
        got = r.a1.c.post(f"/{SLUG}/api/agent/send", json=body)
        assert got.status_code == 200, got.text
        assert "idempotent-replayed" not in got.headers
    assert len(texts(r.alice, "[r2]")) == 2


def test_the_same_key_from_another_caller_is_another_key(r):
    kk = key()
    for agent in (r.a1, r.b1):
        got = agent.c.post(f"/{SLUG}/api/agent/send", json={"to": "#general", "text": f"from {agent.name} [r3]"},
                           headers=k(kk))
        assert got.status_code == 200 and "idempotent-replayed" not in got.headers, got.text
    assert len(texts(r.alice, "[r3]")) == 2


def test_a_key_used_for_something_else_is_refused(r):
    kk = key()
    assert r.a1.c.post(f"/{SLUG}/api/agent/send", json={"to": "#general", "text": "first [r4]"}, headers=k(kk)).status_code == 200
    other = r.a1.c.post(f"/{SLUG}/api/agent/send", json={"to": "#general", "text": "second [r4]"}, headers=k(kk))
    assert other.status_code == 422 and other.json()["error"] == "key_reused", other.text
    assert isinstance(other.json().get("message"), str) and other.json()["message"]
    elsewhere = r.a1.c.post(f"/{SLUG}/api/agent/status", json={"title": "first [r4]"}, headers=k(kk))
    assert elsewhere.status_code == 422 and elsewhere.json()["error"] == "key_reused", elsewhere.text
    assert [m["text"] for m in texts(r.alice, "[r4]")] == ["first [r4]"]
    assert "[r4]" not in status_of(r.a1)["title"]


def test_the_same_body_written_differently_is_the_same_request(r):
    kk = key()
    one = r.a1.c.post(f"/{SLUG}/api/agent/send", content='{"to": "#general", "text": "spacing [r5]"}',
                      headers={**k(kk), "Content-Type": "application/json"})
    two = r.a1.c.post(f"/{SLUG}/api/agent/send", content='{"text":"spacing [r5]","to":"#general"}',
                      headers={**k(kk), "Content-Type": "application/json"})
    assert one.status_code == 200 and two.status_code == 200, (one.text, two.text)
    assert two.headers.get("idempotent-replayed") == "true"
    assert len(texts(r.alice, "[r5]")) == 1


def test_a_refusal_is_kept_and_given_again(r):
    kk = key()
    body = {"to": "#nowhere", "text": "lost [r6]"}
    first = r.a1.c.post(f"/{SLUG}/api/agent/send", json=body, headers=k(kk))
    assert 400 <= first.status_code < 500, first.text
    again = r.a1.c.post(f"/{SLUG}/api/agent/send", json=body, headers=k(kk))
    assert (again.status_code, again.json()) == (first.status_code, first.json())
    assert again.headers.get("idempotent-replayed") == "true"


def test_an_agents_status_set_twice_with_one_key_is_written_once(r):
    kk = key()
    body = {"title": "one status [r7]"}
    first = r.a1.c.post(f"/{SLUG}/api/agent/status", json=body, headers=k(kk))
    again = r.a1.c.post(f"/{SLUG}/api/agent/status", json=body, headers=k(kk))
    assert first.status_code == 200, first.text
    assert again.status_code == 200 and again.json() == first.json(), again.text
    assert again.headers.get("idempotent-replayed") == "true"
    assert "idempotent-replayed" not in first.headers
    assert status_of(r.a1)["title"] == "one status [r7]"


def test_a_bad_key_is_refused_and_nothing_is_done(r):
    for bad in ("short", "x" * 65, "has space in it ok", "slash/inside/key/ok", "dots.and!marks.here", ""):
        got = r.a1.c.post(f"/{SLUG}/api/agent/send", json={"to": "#general", "text": "bad key [r8]"},
                          headers={"Idempotency-Key": bad})
        assert got.status_code == 400 and got.json()["error"] == "invalid_idempotency_key", (bad, got.text)
    assert texts(r.alice, "[r8]") == []


def test_two_at_once_with_one_key_are_done_once(r):
    kk = key()
    body = {"to": "#general", "text": "racing [r9]"}
    answers: list[httpx.Response] = []

    def go():
        with httpx.Client(base_url=r.srv.url, timeout=30, headers=dict(r.a1.c.headers)) as c:
            answers.append(c.post(f"/{SLUG}/api/agent/send", json=body, headers=k(kk)))
    threads = [threading.Thread(target=go) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert len(answers) == 6 and all(a.status_code == 200 for a in answers), [a.text for a in answers]
    assert len({a.json()["id"] for a in answers}) == 1
    assert sum(a.headers.get("idempotent-replayed") == "true" for a in answers) == 5
    assert len(texts(r.alice, "[r9]")) == 1


def test_a_key_is_forgotten_after_the_keeping_time(r):
    kk = key()
    body = {"to": "#general", "text": "later [r10]"}
    assert r.a1.c.post(f"/{SLUG}/api/agent/send", json=body, headers=k(kk)).status_code == 200
    time.sleep(KEEP_S + 2)
    late = r.a1.c.post(f"/{SLUG}/api/agent/send", json=body, headers=k(kk))
    assert late.status_code == 200 and "idempotent-replayed" not in late.headers, late.text
    assert len(texts(r.alice, "[r10]")) == 2


# ------------------------------------------------------------------ people

def test_a_persons_message_sent_twice_with_one_key_is_posted_once(r):
    kk = key()
    body = {"to": "#general", "text": "from the page [r11]"}
    first = r.alice.c.post(f"/{SLUG}/api/messages", json=body, headers=k(kk))
    again = r.alice.c.post(f"/{SLUG}/api/messages", json=body, headers=k(kk))
    assert first.status_code == 201 and again.status_code == 201, (first.text, again.text)
    assert again.json() == first.json() and again.headers.get("idempotent-replayed") == "true"
    assert len(texts(r.alice, "[r11]")) == 1
    other = r.bob.c.post(f"/{SLUG}/api/messages", json={"to": "#general", "text": "bob's own [r11]"}, headers=k(kk))
    assert other.status_code == 201 and "idempotent-replayed" not in other.headers, "a key is the caller's"


def test_a_persons_schedule_and_channel_with_one_key_are_made_once(r):
    kk = key()
    later = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 86_400))      # it never runs here
    body = {"to": "#general", "text": "page schedule [r12]", "level": "muted", "start_at": later}
    first = r.alice.c.post(f"/{SLUG}/api/schedules", json=body, headers=k(kk))
    again = r.alice.c.post(f"/{SLUG}/api/schedules", json=body, headers=k(kk))
    assert first.status_code == 201 and again.status_code == 201, (first.text, again.text)
    assert again.headers.get("idempotent-replayed") == "true"
    made = [x for x in r.alice.c.get(f"/{SLUG}/api/schedules").json()["schedules"] if "[r12]" in x["text"]]
    assert len(made) == 1, made
    assert r.alice.c.post(f"/{SLUG}/api/schedules/{made[0]['id']}/remove").status_code == 200
    pk = key()
    chan = {"name": "keyed-once"}                          # pins retired (1z): a channel is made once instead
    one = r.alice.c.post(f"/{SLUG}/api/channels", json=chan, headers=k(pk))
    two = r.alice.c.post(f"/{SLUG}/api/channels", json=chan, headers=k(pk))
    assert one.status_code == two.status_code, (one.text, two.text)
    assert two.headers.get("idempotent-replayed") == "true"


def test_reads_are_not_affected(r):
    got = r.alice.c.get(f"/{SLUG}/api/messages", params={"in": "#general"}, headers=k("not a valid key at all"))
    assert got.status_code == 200, "a GET ignores the header"


# ------------------------------------------------------------------ the page

def test_the_page_sends_a_key_with_every_write_and_retries_with_it():
    base = (ROOT / "asterism" / "static" / "base.js").read_text(encoding="utf-8")
    assert "Idempotency-Key" in base, "A.request sends the header"
    assert "getRandomValues" in base, "the key is random"
    assert re.search(r"\b50[234]\b", base), "a proxy's 502/503/504 is retried"
