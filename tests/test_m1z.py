"""Slice 1z: pins are gone (agents' whoami included), repository files are refreshed by hand, avatars for people and
agents (an agent's set by its person), the rail's board button.

    python -m pytest tests/test_m1z.py -q
"""
from __future__ import annotations

import base64
import struct
import zlib

import httpx
import pytest

from test_m1b import SLUG, build_world
from test_m1d import CONTENT, FakeGitHub, new_key, start


@pytest.fixture(scope="module")
def z(tmp_path_factory):
    public, pem = new_key()
    hub = FakeGitHub(public)
    hub.files = dict(CONTENT)
    hub.commit()
    world = start(tmp_path_factory.mktemp("z"), hub, pem)
    world.hub = hub
    yield world
    world.srv.stop()
    hub.stop()


def png(w: int, h: int) -> bytes:
    """A small valid PNG of w x h grey pixels."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x80" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_pins_are_gone(z):
    assert z.alice.c.post(f"/{SLUG}/api/channels/general/pins", json={"path": "README.md"}).status_code in (404, 405)
    who = z.a1.c.get(f"/{SLUG}/api/agent/whoami").json()
    assert all(set(c) == {"name"} for c in who["channels"]), who["channels"]
    assert all("pins" not in c for c in z.alice.places()["channels"])
    page = z.alice.c.get(f"/{SLUG}").text
    assert "釘選" not in page and "pin" not in page.lower().replace("spinner", "").replace("pinch", "")


def test_repository_files_are_refreshed_by_hand(z):
    first = z.alice.c.get(f"/{SLUG}/api/files/list", params={"dir": ""}).json()["commit"]
    z.hub.files["late.md"] = b"pushed later\n"
    z.hub.commit()
    assert z.alice.c.get(f"/{SLUG}/api/files/list", params={"dir": ""}).json()["commit"] == first, \
        "inside the trust time nothing is asked of GitHub"
    r = z.alice.c.post(f"/{SLUG}/api/files/refresh")
    assert r.status_code == 200 and r.json()["changed"] is True and r.json()["commit"] != first, r.text
    names = [e["name"] for e in z.alice.c.get(f"/{SLUG}/api/files/list", params={"dir": ""}).json()["entries"]]
    assert "late.md" in names
    again = z.alice.c.post(f"/{SLUG}/api/files/refresh").json()
    assert again["changed"] is False
    assert httpx.post(f"{z.srv.url}/{SLUG}/api/files/refresh").status_code in (401, 403)


def test_a_person_sets_their_avatar_and_an_agents_person_sets_its(z):
    good = b64(png(128, 128))
    assert z.alice.c.post(f"/{SLUG}/api/me/avatar", json={"image": good}).status_code == 200
    got = z.bob.c.get(f"/{SLUG}/api/avatars/person/alice")
    assert got.status_code == 200 and got.content.startswith(b"\x89PNG") and got.headers.get("etag")
    row = next(p for p in z.bob.members()["people"] if p["name"] == "alice")
    assert row["avatar"], "members' views say there is one"
    assert z.bob.c.post(f"/{SLUG}/api/agents/a1/avatar", json={"image": good}).status_code == 403, "only its person"
    assert z.alice.c.post(f"/{SLUG}/api/agents/a1/avatar", json={"image": good}).status_code == 200
    assert z.carol.c.get(f"/{SLUG}/api/avatars/agent/a1").status_code == 200
    for bad in (b64(png(64, 64)), b64(b"not an image"), b64(png(128, 128) + b"x" * 70_000)):
        assert z.alice.c.post(f"/{SLUG}/api/me/avatar", json={"image": bad}).status_code == 400
    assert z.alice.c.post(f"/{SLUG}/api/me/avatar", json={"image": None}).status_code == 200
    assert z.bob.c.get(f"/{SLUG}/api/avatars/person/alice").status_code == 404
    assert next(p for p in z.bob.members()["people"] if p["name"] == "alice")["avatar"] is None
    assert httpx.get(f"{z.srv.url}/{SLUG}/api/avatars/agent/a1").status_code in (401, 403)


def test_the_rail_says_board(z):
    rail = z.alice.c.get(f"/{SLUG}").text.split('id="rail"', 1)[1].split("</nav>", 1)[0]
    assert "看板" in rail and f'href="/{SLUG}/work"' in rail
