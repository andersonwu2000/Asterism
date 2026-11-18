"""Slice 1w (step w1): repository files are edited in the page and saved to GitHub with the editor's own GitHub
authorization; the App's installation token never writes; conflicts are refused; the authorization can be revoked.

    python -m pytest tests/test_m1w.py -q
"""
from __future__ import annotations

import httpx
import pytest

from test_m1b import SLUG
from test_m1d import CONTENT, FakeGitHub, new_key, sha, start


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    public, pem = new_key()
    hub = FakeGitHub(public)
    hub.files = dict(CONTENT)
    hub.commit()
    hub.user_tokens = {"u-alice": {"login": "alice", "push": True}, "u-bob": {"login": "bob", "push": False}}
    world = start(tmp_path_factory.mktemp("w"), hub, pem)
    world.hub = hub
    for person, token in ((world.alice, "u-alice"), (world.bob, "u-bob")):
        r = person.c.post("/test/login", json={"github_login": person.name, "github_token": token})
        assert r.status_code == 200, r.text
    yield world
    world.srv.stop()
    hub.stop()


def save(person, **body) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/files/save", json=body)


def blob(w, path) -> str:
    return sha(b"blob", w.hub.files[path])


def test_who_may_write(w):
    assert w.alice.c.get(f"/{SLUG}/api/files/can-write").json() == {"can_write": True}
    bob = w.bob.c.get(f"/{SLUG}/api/files/can-write").json()
    assert bob["can_write"] is False and bob["reason"] == "no_push"
    carol = w.carol.c.get(f"/{SLUG}/api/files/can-write").json()
    assert carol["can_write"] is False and carol["reason"] == "no_token"


def test_a_save_is_a_commit_in_the_editors_name(w):
    base = blob(w, "notes/alpha.md")
    r = save(w.alice, path="notes/alpha.md", content="a, edited in the page\n", base=base, message="Fix alpha")
    assert r.status_code == 200, r.text
    assert r.json()["commit"] and r.json()["sha"] == blob(w, "notes/alpha.md")
    last = w.hub.writes[-1]
    assert (last["path"], last["login"], last["message"]) == ("notes/alpha.md", "alice", "Fix alpha")
    assert w.hub.install_writes == 0, "the installation token never writes"
    got = w.alice.c.get(f"/{SLUG}/api/files/raw/notes/alpha.md")
    assert got.text == "a, edited in the page\n", "the server follows its own write at once"
    r = save(w.alice, path="notes/new-note.md", content="# New\n", base=None)
    assert r.status_code == 200 and w.hub.writes[-1]["message"] == "Add notes/new-note.md via Asterism", r.text
    r = save(w.alice, path="notes/Zeta.md", content="z2\n", base=blob(w, "notes/Zeta.md"))
    assert r.status_code == 200 and w.hub.writes[-1]["message"] == "Edit notes/Zeta.md via Asterism"


def test_a_save_over_someone_elses_change_is_refused(w):
    stale = blob(w, "notes/lemma32.md")
    w.hub.files["notes/lemma32.md"] = b"# Lemma 3.2\n\nchanged by an agent's push\n"
    w.hub.commit()
    r = save(w.alice, path="notes/lemma32.md", content="mine\n", base=stale)
    assert r.status_code == 409 and r.json()["error"] == "conflict", r.text
    assert r.json()["current"] == blob(w, "notes/lemma32.md")
    assert w.hub.files["notes/lemma32.md"].endswith(b"agent's push\n"), "nothing was written"
    r = save(w.alice, path="notes/lemma32.md", content="mine after all\n", base=r.json()["current"])
    assert r.status_code == 200, "saving over it on purpose names the current version"
    r = save(w.alice, path="README.md", content="x\n", base=None)
    assert r.status_code == 409 and r.json()["error"] == "conflict", "a new file that exists already"


def test_what_cannot_be_saved(w):
    assert save(w.bob, path="notes/alpha.md", content="no\n", base=blob(w, "notes/alpha.md")).status_code == 403
    r = save(w.carol, path="notes/alpha.md", content="no\n", base=blob(w, "notes/alpha.md"))
    assert r.status_code == 409 and r.json()["error"] == "github_reauth", r.text
    for bad in ("../x.md", "notes/../x.md", ".git/config", "a\\b.md", ""):
        assert save(w.alice, path=bad, content="x", base=None).status_code in (400, 404), bad
    assert save(w.alice, path="big.txt", content="x" * (5 * 1024 * 1024 + 1), base=None).status_code in (400, 413)
    assert httpx.post(f"{w.srv.url}/{SLUG}/api/files/save", json={"path": "a.md", "content": "x", "base": None}).status_code in (401, 403)


def test_the_authorization_is_revoked_and_never_shown(w):
    me = w.alice.c.get("/api/me").text + w.alice.c.get(f"/{SLUG}/api/my").text
    assert "u-alice" not in me, "a token is never returned"
    log = (w.data / "log.jsonl").read_text(encoding="utf-8")
    assert "u-alice" not in log and "files_write" in log
    r = w.alice.c.post("/api/me/github/revoke")
    assert r.status_code == 200, r.text
    assert w.alice.c.get(f"/{SLUG}/api/files/can-write").json()["reason"] == "no_token"
    r = save(w.alice, path="notes/alpha.md", content="after revoke\n", base=blob(w, "notes/alpha.md"))
    assert r.status_code == 409 and r.json()["error"] == "github_reauth"
    keyfile = [p for p in w.data.rglob("token.key")]
    assert keyfile, "the key that encrypts tokens lives in the data folder"
