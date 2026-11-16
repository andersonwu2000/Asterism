"""Frontend f4: groups in an order with "show separately" and the defaults apart, presence for people, private
messages on their own page, a top bar in chat, a tidier files mode with file search.

    python -m pytest tests/test_m1f4.py -q
"""
from __future__ import annotations

import re
import time

import httpx
import pytest

from test_m1b import ENV, ROOT, SLUG, build_world
from test_m1d import CONTENT, FakeGitHub, new_key, start

BEAT_OFF_S = 3


@pytest.fixture(scope="module")
def g(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataf4"), dict(ENV, ASTERISM_PERSON_OFFLINE_AFTER_S=str(BEAT_OFF_S)))
    yield world
    world.srv.stop()


def groups(person) -> list[dict]:
    r = person.c.get(f"/{SLUG}/api/members")
    assert r.status_code == 200, r.text
    return r.json()["groups"]


def make(person, name, perms=("read",)):
    r = person.c.post(f"/{SLUG}/api/groups", json={"name": name, "permissions": list(perms)})
    assert r.status_code == 201, r.text


def order(person, names) -> httpx.Response:
    return person.c.post(f"/{SLUG}/api/groups/order", json={"names": names})


# ------------------------------------------------------------------ groups

def test_groups_have_an_order_and_the_defaults_come_last(g):
    make(g.alice, "provers")
    make(g.alice, "readers")
    got = groups(g.alice)
    plain = [x["name"] for x in got if not x.get("default")]
    defaults = [x for x in got if x.get("default")]
    assert {x["name"] for x in defaults} == {"owner", "human", "ai"}
    assert got[-3:] == defaults, "the default groups come last"
    assert all("position" not in x for x in defaults)
    assert [x["position"] for x in got if not x.get("default")] == list(range(len(plain)))
    assert plain[-2:] == ["provers", "readers"], "a new group goes to the bottom"
    wanted = ["readers", "provers"] + [n for n in plain if n not in ("readers", "provers")]
    r = order(g.alice, wanted)
    assert r.status_code == 200, r.text
    assert [x["name"] for x in groups(g.bob) if not x.get("default")] == wanted, "everyone sees the new order"


def test_an_order_must_name_every_group_once_and_only_those(g):
    plain = [x["name"] for x in groups(g.alice) if not x.get("default")]
    for bad in (plain[:-1], plain + [plain[0]], plain + ["nobody"], plain + ["human"], "readers", None):
        r = order(g.alice, bad)
        assert r.status_code == 400, (bad, r.text)
    assert [x["name"] for x in groups(g.alice) if not x.get("default")] == plain, "nothing changed"
    assert order(g.carol, list(reversed(plain))).status_code == 403, "ordering needs manage_groups"


def test_a_group_can_be_shown_separately(g):
    assert all(x.get("separate") is False for x in groups(g.alice) if not x.get("default"))
    assert all("separate" not in x for x in groups(g.alice) if x.get("default"))
    r = g.alice.c.post(f"/{SLUG}/api/groups/provers", json={"separate": True})
    assert r.status_code == 200, r.text
    assert next(x for x in groups(g.bob) if x["name"] == "provers")["separate"] is True
    assert g.carol.c.post(f"/{SLUG}/api/groups/provers", json={"separate": False}).status_code == 403
    own = f"{g.bob.name}-agents"
    assert any(x["name"] == own for x in groups(g.bob)), own
    assert g.bob.c.post(f"/{SLUG}/api/groups/{own}", json={"separate": True}).status_code == 200, "a person's own agent group"
    assert g.alice.c.post(f"/{SLUG}/api/groups/human", json={"separate": True}).status_code in (400, 403, 409)
    assert g.alice.c.post(f"/{SLUG}/api/groups/provers", json={"separate": "yes"}).status_code == 400


# ------------------------------------------------------------------ presence for people

def test_a_person_is_online_while_a_page_is_open(g):
    def online(name):
        return next(p for p in g.alice.c.get(f"/{SLUG}/api/members").json()["people"] if p["name"] == name)["online"]
    assert online("carol") is False
    r = g.carol.c.post(f"/{SLUG}/api/presence", json={})
    assert r.status_code == 200, r.text
    assert online("carol") is True
    time.sleep(BEAT_OFF_S + 1.5)
    assert online("carol") is False, "no beat for a while: offline"
    assert httpx.post(f"{g.srv.url}/{SLUG}/api/presence", json={}).status_code in (401, 403)
    before = [m for m in g.alice.read() if m["from_kind"] == "system"]
    g.carol.c.post(f"/{SLUG}/api/presence", json={})
    assert [m for m in g.alice.read() if m["from_kind"] == "system"] == before, "nobody is told"


# ------------------------------------------------------------------ pages

def test_the_words_say_group_not_identity_group(g):
    for path in ("", "/settings/groups", "/settings/members", "/files", "/dm"):
        page = g.alice.c.get(f"/{SLUG}{path}")
        assert page.status_code == 200, path
        assert "身份組" not in page.text and "身分組" not in page.text, path
    words = (ROOT / "asterism" / "i18n.py").read_text(encoding="utf-8")
    assert "身份組" not in words and "群組" in words


def test_no_native_select_remains_in_any_page(g):
    for path in ("", "/settings/groups", "/settings/members", "/settings/invites", "/my", "/schedules", "/files", "/dm"):
        page = g.alice.c.get(f"/{SLUG}{path}").text
        assert "<select" not in page, path
    scripts = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "asterism" / "static").glob("*.js"))
    assert not re.search(r"createElement\(\s*[\"']select[\"']", scripts) and 'make("select"' not in scripts, \
        "no script builds a native select either"


def test_chat_has_one_top_bar_and_no_pins_or_message_numbers(g):
    page = g.alice.c.get(f"/{SLUG}").text
    for needed in ('id="topbar"', 'id="project-menu-button"', 'id="members-toggle"', 'id="search-open"'):
        assert needed in page, needed
    bar = page.split('id="topbar"', 1)[1]
    assert bar.index('id="project-menu-button"') < bar.index('id="members-toggle"') < bar.index('id="search-open"')
    for gone in ('id="pins"', 'id="pins-toggle"', 'id="task-panel"', 'id="task-toggle"', 'id="invite-open"',
                 'id="side-private"'):
        assert gone not in page, gone
    assert 'id="side-channels"' in page


def test_private_messages_have_their_own_page(g):
    g.alice.say("only for bob [f4dm]", to="bob")
    page = g.bob.c.get(f"/{SLUG}/dm")
    assert page.status_code == 200 and 'id="dm-list"' in page.text and 'id="composer"' in page.text
    one = g.bob.c.get(f"/{SLUG}/dm/alice")
    assert one.status_code == 200 and 'id="dm-list"' in one.text
    assert g.bob.c.get(f"/{SLUG}/dm/nobody-here").status_code == 404
    assert httpx.get(f"{g.srv.url}/{SLUG}/dm", follow_redirects=False).status_code in (302, 303, 401)


def test_files_mode_has_no_project_menu_no_filter_and_a_menu_of_its_own(g):
    page = g.alice.c.get(f"/{SLUG}/files").text
    assert 'id="files-menu"' in page and 'id="source-switch"' in page
    for gone in ('id="project-menu-button"', 'id="explorer-filter"', 'id="local-name"', "（repo）", "（本機）",
                 "(repo)", "(本機)"):
        assert gone not in page, gone


def test_the_tab_marks_are_v1s_kind_marks():
    v1 = (ROOT.parent / "Asterism_v1" / "web" / "src" / "components" / "glyphs.tsx")
    if not v1.exists():
        pytest.skip("v1 is not next to this repository")
    ours = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "asterism" / "static").glob("*.js"))
    for mark in ("M4 4.1l1.6 1.4L4 6.9", "M1 10V1h4.7L9 4.2V10z", "M1.4 8.3l2.4-2.4 1.6 1.5 1.2-1.1L8.6 7.6"):
        assert mark in v1.read_text(encoding="utf-8") and mark in ours, mark


# ------------------------------------------------------------------ file search in the repository

@pytest.fixture(scope="module")
def fs(tmp_path_factory):
    public, pem = new_key()
    hub = FakeGitHub(public)
    hub.files = dict(CONTENT)
    hub.files.update({"notes/orbit/lemma-one.md": b"# one", "notes/orbit/lemma-two.tex": b"x", "papers/Orbit.pdf": b"%PDF"})
    hub.commit()
    world = start(tmp_path_factory.mktemp("f4files"), hub, pem)
    world.hub = hub
    yield world
    world.srv.stop()
    hub.stop()


def find(person, **params) -> httpx.Response:
    return person.c.get(f"/{SLUG}/api/files/find", params=params)


def test_files_are_found_by_every_word_of_their_path(fs):
    r = find(fs.bob, q="ORBIT lemma")
    assert r.status_code == 200, r.text
    body = r.json()
    paths = [p["path"] for p in body["paths"]]
    assert set(paths) == {"notes/orbit/lemma-one.md", "notes/orbit/lemma-two.tex"} and body["complete"] is True
    assert all(p["type"] == "file" for p in body["paths"])
    both = [p["path"] for p in find(fs.bob, q="orbit").json()["paths"]]
    assert "notes/orbit" in both and "papers/Orbit.pdf" in both, "folders too, any case"
    assert both == sorted(both, key=len) or [len(x) for x in both] == sorted(len(x) for x in both), "shortest first"
    assert len(find(fs.bob, q="orbit", limit=1).json()["paths"]) == 1
    assert body["commit"] and body["ref"]


def test_file_search_asks_github_once_per_head_and_says_when_it_is_incomplete(fs):
    before = fs.hub.recursive
    find(fs.bob, q="orbit")
    find(fs.carol, q="lemma")
    assert fs.hub.recursive - before <= 1, "one recursive listing per head, then the cache"
    fs.hub.truncate_after = 2
    fs.hub.files["late/added.md"] = b"new"
    fs.hub.commit()
    time.sleep(3)
    got = None
    for _ in range(20):
        got = find(fs.bob, q="added").json()
        if got.get("complete") is False:
            break
        time.sleep(0.5)
    assert got["complete"] is False, got
    fs.hub.truncate_after = 0


def test_file_search_refuses_what_it_cannot_do(fs):
    assert find(fs.bob, q="").status_code == 400
    assert find(fs.bob, q="x", limit=0).status_code == 400 and find(fs.bob, q="x", limit=201).status_code == 400
    assert httpx.get(f"{fs.srv.url}/{SLUG}/api/files/find", params={"q": "x"}).status_code in (401, 403)
