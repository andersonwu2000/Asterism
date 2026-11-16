"""f6a: permissions that hold, channel permissions, the switches as permissions, making and unmaking projects,
channels and groups, default groups closed to hand changes, a nickname per project, a language, v1's favicon.

    python -m pytest tests/test_m1f6.py -q
"""
from __future__ import annotations

import httpx
import pytest

from test_m1b import ROOT, SLUG, Person, build_world


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataf6"))
    yield world
    world.srv.stop()


def channels_of(person) -> list[str]:
    return [c["name"] for c in person.places()["channels"]]


def overrides(person, channel, body) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/channels/{channel}/permissions", json={"overrides": body})


def groups_of(person, name) -> list[str]:
    m = person.c.get(f"/{SLUG}/api/members").json()
    row = next(x for x in m["people"] + m["agents"] if x["name"] == name)
    return row["groups"]


# ------------------------------------------------------------------ channel permissions

def test_a_channel_hidden_from_a_group_does_not_exist_for_its_members(w):
    assert w.alice.c.post(f"/{SLUG}/api/channels", json={"name": "secret"}).status_code == 201
    assert w.alice.c.post(f"/{SLUG}/api/groups", json={"name": "insiders", "permissions": ["read", "post"]}).status_code == 201
    assert w.alice.c.post(f"/{SLUG}/api/members/bob/groups", json={"add": ["insiders"], "remove": []}).status_code == 200
    r = overrides(w.alice, "secret", {"human": {"read": "deny"}, "ai": {"read": "deny"}, "insiders": {"read": "allow"}})
    assert r.status_code == 200, r.text
    got = w.alice.c.get(f"/{SLUG}/api/channels/secret/permissions").json()["overrides"]
    assert got["human"]["read"] == "deny" and got["insiders"]["read"] == "allow" and got["human"]["post"] == "inherit"
    w.alice.say("@carol @a1 @b1 only insiders [p1]", to="#secret")
    assert "secret" not in channels_of(w.carol)
    assert w.carol.c.get(f"/{SLUG}/api/messages", params={"in": "#secret"}).status_code == 404
    assert w.carol.c.get(f"/{SLUG}/api/search", params={"q": "p1"}).json()["results"] == []
    assert "secret" in channels_of(w.bob), "a group that allows wins over one that denies"
    assert any("[p1]" in m["text"] for m in w.bob.read("#secret"))
    assert "secret" in channels_of(w.alice), "the owner group is never denied"
    who = w.a1.c.get(f"/{SLUG}/api/agent/whoami").json()
    assert "secret" not in [c["name"] for c in who["channels"]]
    w.a1.absent("[p1]")
    w.b1.absent("[p1]")
    assert w.a1.messages(place="#secret").status_code == 404


def test_post_can_be_denied_in_one_channel(w):
    assert w.alice.c.post(f"/{SLUG}/api/channels", json={"name": "notices"}).status_code == 201
    assert overrides(w.alice, "notices", {"human": {"post": "deny"}, "ai": {"post": "deny"}}).status_code == 200
    assert w.carol.post("not here [p2]", to="#notices").status_code == 403
    assert w.a1.send("nor here [p2]", to="#notices").status_code == 403
    assert w.alice.post("the owner may [p2]", to="#notices").status_code == 201
    assert any("[p2]" in m["text"] for m in w.carol.read("#notices")), "reading is still allowed"


def test_channel_permissions_need_manage_channels(w):
    r = overrides(w.carol, "notices", {"human": {"post": "inherit"}})
    assert r.status_code == 403
    assert overrides(w.alice, "notices", {"human": {"post": "maybe"}}).status_code == 400
    assert overrides(w.alice, "notices", {"nobody-group": {"post": "deny"}}).status_code in (400, 404)


# ------------------------------------------------------------------ the switches are permissions

def test_the_switches_are_permissions_of_a_persons_agent_group(w):
    own = "alice-agents"
    w.alice.switches(others_mention=True)
    perms = next(g for g in w.alice.c.get(f"/{SLUG}/api/members").json()["groups"] if g["name"] == own)["permissions"]
    assert "others_mention" in perms
    r = w.alice.c.post(f"/{SLUG}/api/groups/{own}", json={"permissions": perms + ["others_assign"]})
    assert r.status_code == 200, r.text
    perms = next(g for g in w.alice.c.get(f"/{SLUG}/api/members").json()["groups"] if g["name"] == own)["permissions"]
    assert "others_assign" in perms
    assert w.bob.c.post(f"/{SLUG}/api/groups/{own}", json={"permissions": []}).status_code == 403
    r = w.alice.c.post(f"/{SLUG}/api/groups", json={"name": "wrongly", "permissions": ["read", "others_mention"]})
    assert r.status_code == 400, "only a person's agent group carries them"


# ------------------------------------------------------------------ default groups

def test_nobody_is_put_into_or_taken_out_of_a_default_group_by_hand(w):
    for body in ({"add": ["owner"], "remove": []}, {"add": [], "remove": ["human"]}, {"add": ["ai"], "remove": []}):
        r = w.alice.c.post(f"/{SLUG}/api/members/carol/groups", json=body)
        assert r.status_code == 409, (body, r.text)
    assert "owner" not in groups_of(w.alice, "carol") and "human" in groups_of(w.alice, "carol")


# ------------------------------------------------------------------ channels and groups renamed, removed

def test_channels_are_renamed_and_deleted_for_good(w):
    assert w.alice.c.post(f"/{SLUG}/api/channels", json={"name": "scratch"}).status_code == 201
    w.alice.say("kept through a rename [p3]", to="#scratch")
    assert w.carol.c.post(f"/{SLUG}/api/channels/scratch", json={"name": "other"}).status_code == 403
    r = w.alice.c.post(f"/{SLUG}/api/channels/scratch", json={"name": "renamed"})
    assert r.status_code == 200, r.text
    assert "renamed" in channels_of(w.bob) and "scratch" not in channels_of(w.bob)
    assert any("[p3]" in m["text"] for m in w.bob.read("#renamed"))
    assert w.carol.c.post(f"/{SLUG}/api/channels/renamed/delete").status_code == 403
    assert w.alice.c.post(f"/{SLUG}/api/channels/renamed/delete").status_code == 200
    assert "renamed" not in channels_of(w.bob)
    assert w.bob.c.get(f"/{SLUG}/api/search", params={"q": "p3"}).json()["results"] == [], "its messages are gone"


def test_custom_groups_are_renamed_default_and_agent_groups_are_not(w):
    assert w.alice.c.post(f"/{SLUG}/api/groups", json={"name": "drafters", "permissions": ["read"]}).status_code == 201
    r = w.alice.c.post(f"/{SLUG}/api/groups/drafters", json={"name": "writers"})
    assert r.status_code == 200, r.text
    names = [g["name"] for g in w.alice.c.get(f"/{SLUG}/api/members").json()["groups"]]
    assert "writers" in names and "drafters" not in names
    assert w.alice.c.post(f"/{SLUG}/api/groups/writers", json={"name": "insiders"}).status_code == 409, "taken"
    assert w.alice.c.post(f"/{SLUG}/api/groups/human", json={"name": "people"}).status_code in (403, 409)
    assert w.alice.c.post(f"/{SLUG}/api/groups/alice-agents", json={"name": "mine"}).status_code in (403, 409)
    assert w.carol.c.post(f"/{SLUG}/api/groups/writers", json={"name": "scribes"}).status_code == 403


# ------------------------------------------------------------------ a nickname per project

def test_a_person_sets_their_name_in_a_project(w):
    old = w.carol.say("said before the new name [p4]")
    r = w.carol.c.post(f"/{SLUG}/api/me/name", json={"name": "cara"})
    assert r.status_code == 200, r.text
    m = w.alice.c.get(f"/{SLUG}/api/members").json()
    row = next(p for p in m["people"] if p["name"] == "cara")
    assert row["github_login"] == "carol", "the GitHub login stays"
    assert next(x for x in w.alice.read() if x["id"] == old["id"])["from"] == "cara", "past messages show it too"
    sent = w.alice.say("@cara hello [p4]")
    assert [x["name"] for x in sent["mentions"]] == ["cara"] and sent["mentions"][0].get("result") != "unknown"
    for taken in ("a1", "bob", "human", "writers"):
        assert w.carol.c.post(f"/{SLUG}/api/me/name", json={"name": taken}).status_code == 409, taken
    assert w.carol.c.post(f"/{SLUG}/api/me/name", json={"name": "bad name!"}).status_code == 400
    assert w.carol.c.post(f"/{SLUG}/api/me/name", json={"name": "carol"}).status_code == 200


# ------------------------------------------------------------------ language

def test_a_person_chooses_the_language_of_the_pages(w):
    assert w.bob.c.post("/api/me/settings", json={"locale": "xx"}).status_code == 400
    assert w.bob.c.post("/api/me/settings", json={"locale": "en"}).status_code == 200
    page = w.bob.c.get(f"/{SLUG}").text
    assert '<html lang="en"' in page, page[:200]
    assert w.bob.c.post("/api/me/settings", json={"locale": "zh-TW"}).status_code == 200
    assert '<html lang="zh-TW"' in w.bob.c.get(f"/{SLUG}").text


# ------------------------------------------------------------------ projects

def test_anyone_signed_in_makes_a_project_and_its_owner_renames_and_deletes_it(w):
    dora = Person(w.srv, "dora")
    assert httpx.post(f"{w.srv.url}/api/projects", json={"slug": "dora-lab", "name": "Dora Lab"}).status_code in (401, 403)
    assert dora.c.post("/api/projects", json={"slug": "Bad Slug", "name": "x"}).status_code == 400
    r = dora.c.post("/api/projects", json={"slug": "dora-lab", "name": "Dora Lab"})
    assert r.status_code == 201, r.text
    assert dora.c.post("/api/projects", json={"slug": "dora-lab", "name": "Again"}).status_code == 409
    assert dora.c.post("/api/projects", json={"slug": SLUG, "name": "Taken"}).status_code == 409
    me = next(p for p in dora.c.get("/dora-lab/api/members").json()["people"] if p["github_login"] == "dora")
    assert "owner" in me["groups"] and "human" in me["groups"]
    assert w.alice.c.get("/dora-lab/api/members").status_code in (403, 404), "others are not members"
    assert dora.c.post("/dora-lab/api/project", json={"name": "Dora's Lab"}).status_code == 200
    assert dora.c.post("/dora-lab/api/project", json={"repo": "https://github.com/dora/lab"}).status_code == 200
    assert w.alice.c.post("/dora-lab/api/project/delete", json={"confirm": "dora-lab"}).status_code in (403, 404)
    assert dora.c.post("/dora-lab/api/project/delete", json={"confirm": "wrong"}).status_code == 400
    assert dora.c.post("/dora-lab/api/project/delete", json={"confirm": "dora-lab"}).status_code == 200
    assert dora.c.get("/dora-lab").status_code == 404
    assert dora.c.post("/api/projects", json={"slug": "dora-lab", "name": "Dora Lab"}).status_code == 201, "the name is free"
    assert "新增專案" in dora.c.get("/").text or "New project" in dora.c.get("/").text


# ------------------------------------------------------------------ the frame

def test_the_favicon_is_v1s():
    v1 = ROOT.parent / "Asterism_v1" / "web" / "public" / "favicon.svg"
    if not v1.exists():
        pytest.skip("v1 is not next to this repository")
    ours = ROOT / "asterism" / "static" / "favicon.svg"
    assert ours.read_bytes().strip() == v1.read_bytes().strip()


def test_the_theme_is_a_personal_setting_not_a_rail_button(w):
    page = w.alice.c.get(f"/{SLUG}").text
    rail = page.split('id="rail"', 1)[1].split("</nav>", 1)[0]
    assert 'id="theme-toggle"' not in rail
    assert w.alice.c.get(f"/{SLUG}/me").status_code == 200, "the personal settings layer has an address"


def test_general_is_a_channel_like_the_others_and_notices_go_where_the_project_says(w):
    assert w.alice.c.post(f"/{SLUG}/api/channels", json={"name": "lobby"}).status_code == 201
    assert w.alice.c.post(f"/{SLUG}/api/channels/general", json={"name": "town"}).status_code == 200
    assert w.alice.c.post(f"/{SLUG}/api/channels/town/delete").status_code == 409, "the notice channel stays until another is chosen"
    assert w.carol.c.post(f"/{SLUG}/api/project", json={"notice_channel": "#lobby"}).status_code == 403
    assert w.alice.c.post(f"/{SLUG}/api/project", json={"notice_channel": "#nowhere"}).status_code in (400, 404)
    assert w.alice.c.post(f"/{SLUG}/api/project", json={"notice_channel": "#lobby"}).status_code == 200
    assert w.alice.c.post(f"/{SLUG}/api/channels/town/delete").status_code == 200
    r = w.alice.c.post(f"/{SLUG}/api/tasks", json={"group": "ai", "text": "where is it told [p5]", "responsible": "a2"})
    assert r.status_code == 201, r.text
    told = [m for m in w.alice.read("#lobby") if m["from_kind"] == "system" and "[p5]" in m["text"]]
    assert told, "the task change is announced in the notice channel"
