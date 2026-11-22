"""f7: what the two reviews asked for that a test can hold: the owner group takes no channel override; unused
invitations are listed and revoked; a private conversation that is not allowed is answered inside the frame.

    python -m pytest tests/test_m1f7.py -q
"""
from __future__ import annotations

import urllib.parse

import httpx
import pytest

from test_m1b import SLUG, Person, build_world


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataf7"))
    yield world
    world.srv.stop()


def test_the_owner_group_takes_no_channel_override(w):
    r = w.alice.c.post(f"/{SLUG}/api/channels/general/permissions", json={"overrides": {"owner": {"read": "deny"}}})
    assert r.status_code == 400, r.text
    got = w.alice.c.get(f"/{SLUG}/api/channels/general/permissions").json()["overrides"]
    assert got.get("owner", {}).get("read", "inherit") == "inherit"


def test_unused_invitations_are_listed_and_revoked(w):
    made = w.alice.c.post(f"/{SLUG}/api/invites", json={"github_login": "dora"})
    assert made.status_code == 201, made.text
    listed = w.alice.c.get(f"/{SLUG}/api/invites")
    assert listed.status_code == 200, listed.text
    row = next(i for i in listed.json()["invites"] if i["github_login"] == "dora")
    assert {"id", "created", "expires"} <= set(row) and "url" not in row, "the link is shown once"
    assert w.carol.c.get(f"/{SLUG}/api/invites").status_code == 403
    assert w.carol.c.post(f"/{SLUG}/api/invites/{row['id']}/revoke").status_code == 403
    assert w.alice.c.post(f"/{SLUG}/api/invites/{row['id']}/revoke").status_code == 200
    assert all(i["id"] != row["id"] for i in w.alice.c.get(f"/{SLUG}/api/invites").json()["invites"])
    dora = Person(w.srv, "dora")
    path = urllib.parse.urlparse(made.json()["url"]).path
    assert dora.c.post(path).status_code in (400, 404, 410), "a revoked invitation no longer works"


def test_a_private_conversation_not_allowed_is_answered_inside_the_frame(w):
    r = w.bob.c.get(f"/{SLUG}/dm/a1")
    assert r.status_code == 403 and 'id="rail"' in r.text, r.status_code
    assert "alice" in r.text, "it says whose agent it is"
    assert httpx.get(f"{w.srv.url}/{SLUG}/dm/a1", follow_redirects=False).status_code in (302, 303, 401)
