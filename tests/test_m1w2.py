"""Slice 1w step w2 (server side): deleting and renaming repository files with the person's own authorization; a
chosen computer writes instead of the server (here a stand-in program answers the write deliveries).

    python -m pytest tests/test_m1w2.py -q
"""
from __future__ import annotations

import base64
import threading
import time

import httpx
import pytest

from test_m1b import SLUG, until
from test_m1d import CONTENT, FakeGitHub, new_key, sha, start
from test_m1j import Computer

WAIT_S = 3


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    public, pem = new_key()
    hub = FakeGitHub(public)
    hub.files = dict(CONTENT)
    hub.files.update({"notes/old-name.md": b"# keep me\n", "notes/remove-me.md": b"bye\n"})
    hub.commit()
    hub.user_tokens = {"u-alice": {"login": "alice", "push": True}, "u-bob": {"login": "bob", "push": True}}
    world = start(tmp_path_factory.mktemp("w2"), hub, pem, ASTERISM_WRITE_WAIT_S=str(WAIT_S))
    world.hub = hub
    for person, token in ((world.alice, "u-alice"), (world.bob, "u-bob")):
        assert person.c.post("/test/login", json={"github_login": person.name, "github_token": token}).status_code == 200
    yield world
    world.srv.stop()
    hub.stop()


def blob(w, path) -> str:
    return sha(b"blob", w.hub.files[path])


# ------------------------------------------------------------------ delete and rename, server path

def test_a_file_is_deleted_in_one_commit_in_the_persons_name(w):
    stale = blob(w, "notes/remove-me.md")
    r = w.alice.c.post(f"/{SLUG}/api/files/delete", json={"path": "notes/remove-me.md", "base": stale})
    assert r.status_code == 200, r.text
    assert "notes/remove-me.md" not in w.hub.files
    last = w.hub.writes[-1]
    assert (last["op"], last["login"], last["message"]) == ("delete", "alice", "Delete notes/remove-me.md via Asterism")
    again = w.alice.c.post(f"/{SLUG}/api/files/delete", json={"path": "notes/remove-me.md", "base": stale})
    assert again.status_code == 404
    w.hub.files["notes/alpha.md"] = b"changed meanwhile\n"
    w.hub.commit()
    r = w.alice.c.post(f"/{SLUG}/api/files/delete", json={"path": "notes/alpha.md", "base": sha(b"blob", b"a\n")})
    assert r.status_code == 409 and r.json()["error"] == "conflict" and r.json()["current"] == blob(w, "notes/alpha.md")
    assert "notes/alpha.md" in w.hub.files
    assert w.hub.install_writes == 0


def test_a_file_is_renamed_in_one_commit_without_force(w):
    base = blob(w, "notes/old-name.md")
    r = w.alice.c.post(f"/{SLUG}/api/files/rename", json={"path": "notes/old-name.md", "to": "notes/new-name.md", "base": base})
    assert r.status_code == 200, r.text
    assert "notes/old-name.md" not in w.hub.files and w.hub.files["notes/new-name.md"] == b"# keep me\n"
    last = w.hub.writes[-1]
    assert last["op"] == "ref" and last["force"] is False and last["login"] == "alice"
    assert last["message"] == "Rename notes/old-name.md to notes/new-name.md via Asterism"
    r = w.alice.c.post(f"/{SLUG}/api/files/rename", json={"path": "notes/new-name.md", "to": "README.md",
                                                           "base": blob(w, "notes/new-name.md")})
    assert r.status_code == 409 and r.json()["error"] == "conflict", "the target exists"
    for bad in ("../x.md", ".git/x", "a\\b"):
        r = w.alice.c.post(f"/{SLUG}/api/files/rename", json={"path": "notes/new-name.md", "to": bad,
                                                               "base": blob(w, "notes/new-name.md")})
        assert r.status_code in (400, 404), bad
    assert w.hub.install_writes == 0


# ------------------------------------------------------------------ a chosen computer

def credential_id(person) -> int:
    creds = person.c.get(f"/{SLUG}/api/my").json()["credentials"]
    return next(c["id"] for c in creds if c["kind"] == "computer")


def answer_writes(pc, answer):
    """A stand-in program: answers each write delivery with what `answer(delivery)` says."""
    stop = threading.Event()

    def loop():
        seen = set()
        while not stop.is_set():
            with pc.lock:
                todo = [d for d in pc.got if d.get("kind") == "write" and d["delivery"] not in seen]
            for d in todo:
                seen.add(d["delivery"])
                pc.c.post(f"/{SLUG}/api/computer/write", json={"delivery": d["delivery"], **answer(d)})
            time.sleep(0.1)
    threading.Thread(target=loop, daemon=True).start()
    return stop


def test_choosing_a_computer_drops_the_servers_token_and_writes_go_there(w):
    pc = Computer(w.srv, w.cred_b)
    # w3: a computer is chosen by the machine id its program reports, so the stand-in reports one first
    pc.c.post(f"/{SLUG}/api/computer/sessions", json={"sessions": [], "git": True, "machine": "b" * 32,
                                                      "version": "0.1.13"})
    r = w.bob.c.post(f"/{SLUG}/api/me/writer", json={"credential": credential_id(w.bob)})
    assert r.status_code == 200, r.text
    pc.connect()
    try:
        # the stand-in program is online once its first poll has reached the server
        assert until(lambda: w.bob.c.get(f"/{SLUG}/api/files/can-write").json()["can_write"] is True, 8)
        state = w.bob.c.get(f"/{SLUG}/api/files/can-write").json()
        assert state["can_write"] is True and state.get("writer"), state
        stop = answer_writes(pc, lambda d: {"result": "done", "commit": "c0ffee", "sha": "beef"})
        try:
            r = w.bob.c.post(f"/{SLUG}/api/files/save", json={"path": "notes/by-pc.md", "content": "from bob's pc\n", "base": None})
            assert r.status_code == 200 and r.json()["commit"] == "c0ffee", r.text
            d = next(g for g in pc.got if g.get("kind") == "write" and g["path"] == "notes/by-pc.md")
            assert d["op"] == "save" and base64.b64decode(d["content_b64"]) == b"from bob's pc\n" and d["base"] is None
            assert d["repo"].startswith("https://github.com/") and d["message"] == "Add notes/by-pc.md via Asterism"
            assert not [x for x in w.hub.writes if x.get("login") == "bob"], "the server wrote nothing for bob"
        finally:
            stop.set()
        stop = answer_writes(pc, lambda d: {"result": "conflict", "current": "abc123"})
        try:
            r = w.bob.c.post(f"/{SLUG}/api/files/delete", json={"path": "README.md", "base": "old"})
            assert r.status_code == 409 and r.json()["error"] == "conflict" and r.json()["current"] == "abc123", r.text
        finally:
            stop.set()
        t0 = time.time()
        r = w.bob.c.post(f"/{SLUG}/api/files/rename", json={"path": "README.md", "to": "READ.md", "base": "x"})
        assert r.json()["error"] == "computer_timeout" and time.time() - t0 < WAIT_S + 5, r.text
    finally:
        pc.disconnect()
    assert until(lambda: w.bob.c.get(f"/{SLUG}/api/files/can-write").json().get("reason") == "computer_offline", 15)
    r = w.bob.c.post(f"/{SLUG}/api/files/save", json={"path": "notes/x.md", "content": "x\n", "base": None})
    assert r.json()["error"] == "computer_offline", r.text
    assert w.bob.c.post(f"/{SLUG}/api/me/writer", json={"credential": None}).status_code == 200
    assert w.bob.c.get(f"/{SLUG}/api/files/can-write").json()["reason"] == "no_token", \
        "the server's token was dropped when the computer was chosen"


def test_only_ones_own_computer_can_be_chosen(w):
    alices = credential_id(w.alice)
    r = w.bob.c.post(f"/{SLUG}/api/me/writer", json={"credential": alices})
    assert r.status_code in (403, 404), r.text
    assert httpx.post(f"{w.srv.url}/{SLUG}/api/me/writer", json={"credential": alices}).status_code in (401, 403)
