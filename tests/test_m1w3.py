"""Slice 1w step w3: a computer is known across projects by the machine id its program reports; the writing computer
is chosen per account; while one is chosen no GitHub token is kept; my computers are listed across projects.

    python -m pytest tests/test_m1w3.py -q
"""
from __future__ import annotations

import httpx
import pytest

from test_m1b import SLUG, build_world

M1, M2 = "a" * 32, "b" * 32


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("w3"))
    yield world
    world.srv.stop()


def link(person, slug=SLUG) -> str:
    r = person.c.post(f"/{slug}/api/my/agent-invites")
    assert r.status_code == 201, r.text
    return r.json()["url"]


def redeem(url, machine=None, computer="lab-pc") -> str:
    body = {"computer": computer, "product": "codex", **({"machine": machine} if machine else {})}
    r = httpx.post(url + "/redeem", json=body, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["credential"]


def report(srv, slug, cred, **body):
    r = httpx.post(f"{srv.url}/{slug}/api/computer/sessions", json={"sessions": [], **body},
                   headers={"Authorization": "Bearer " + cred}, timeout=30)
    assert r.status_code == 200, r.text


def computers(person) -> list[dict]:
    r = person.c.get("/api/me/computers")
    assert r.status_code == 200, r.text
    return r.json()["computers"]


def test_a_computer_is_known_by_its_machine_id_across_projects(w):
    cred1 = redeem(link(w.alice), machine=M1)
    report(w.srv, SLUG, cred1, machine=M1, version="0.1.13", git=True)
    other = w.alice.c.post("/api/projects", json={"name": "Second Lab"})
    assert other.status_code == 201, other.text
    w.slug2 = other.json()["slug"]
    cred2 = redeem(link(w.alice, w.slug2), machine=M1)
    report(w.srv, w.slug2, cred2, machine=M1, version="0.1.13", git=True)
    mine = [c for c in computers(w.alice) if c.get("machine") == M1]
    assert len(mine) == 1, mine
    c = mine[0]
    assert {p["slug"] for p in c["projects"]} == {SLUG, w.slug2}
    assert c["version"] == "0.1.13" and c["git"] is True
    assert all(x.get("machine") != M1 for x in computers(w.bob)), "only one's own computers"


def test_the_writing_computer_is_chosen_for_the_account(w):
    assert w.alice.c.post("/api/me/writer", json={"machine": M1}).status_code == 200
    state = w.alice.c.get("/api/me/writer").json()
    assert state["mode"] == "computer" and state["machine"] == M1 and state["github"] == "none"
    for slug in (SLUG, w.slug2):
        got = w.alice.c.get(f"/{slug}/api/files/can-write").json()
        assert got["can_write"] is False and got["reason"] in ("computer_offline", "computer_cannot_push"), (slug, got)
    third = w.alice.c.post("/api/projects", json={"name": "Third Lab"}).json()["slug"]
    got = w.alice.c.get(f"/{third}/api/files/can-write").json()
    assert got["reason"] == "computer_not_here", got
    r = w.alice.c.post(f"/{third}/api/files/save", json={"path": "a.md", "content": "x\n", "base": None})
    assert r.json()["error"] == "computer_not_here", r.text


def test_no_token_is_kept_while_a_computer_writes(w):
    r = w.alice.c.post("/test/login", json={"github_login": "alice", "github_token": "u-alice"})
    assert r.status_code == 200
    assert w.alice.c.get("/api/me/writer").json()["github"] == "none", "signing in stored no token"
    assert w.alice.c.post("/api/me/writer", json={"machine": None}).status_code == 200
    state = w.alice.c.get("/api/me/writer").json()
    assert state["mode"] == "server" and state["github"] == "none", "back to the server: authorise again"


def test_what_cannot_be_chosen(w):
    cred = redeem(link(w.bob), machine=M2, computer="bob-pc")
    report(w.srv, SLUG, cred, machine=M2, version="0.1.13", git=False)
    r = w.bob.c.post("/api/me/writer", json={"machine": M2})
    assert r.status_code == 409 and r.json()["error"] == "computer_cannot_push", r.text
    assert w.bob.c.post("/api/me/writer", json={"machine": "c" * 32}).status_code == 404
    assert w.bob.c.post("/api/me/writer", json={"machine": M1}).status_code == 404, "alice's machine is not bob's"
    old = next(c for c in w.bob.c.get(f"/{SLUG}/api/my").json()["credentials"] if c["kind"] == "computer" and not c.get("machine"))
    r = w.bob.c.post(f"/{SLUG}/api/me/writer", json={"credential": old["id"]})
    assert r.status_code == 409 and r.json()["error"] == "computer_too_old", r.text
    assert httpx.post(f"{w.srv.url}/api/me/writer", json={"machine": None}).status_code in (401, 403)
