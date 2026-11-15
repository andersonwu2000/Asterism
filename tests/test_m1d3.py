"""Local files and the editor, as far as a test can own them: the page offers two sources, the editor is served
from this server with its licences and the recipe that built it, and the page's policy stays tight. What a local
file's content does never reaches the server, so the rest is judged in a browser.

    python -m pytest tests/test_m1d3.py -q
"""
from __future__ import annotations

import json
import re

import httpx
import pytest

from test_m1b import ROOT, SLUG, build_world

VENDOR = ROOT / "asterism" / "static" / "vendor" / "codemirror"
RECIPE = ROOT / "tools" / "editor"
PINNED = {"codemirror": "6.0.2", "@codemirror/lang-markdown": "6.5.2"}


@pytest.fixture(scope="module")
def e(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("datad3"))
    yield world
    world.srv.stop()


def test_the_files_page_offers_the_repository_and_a_local_folder(e):
    page = e.alice.c.get(f"/{SLUG}/files")
    assert page.status_code == 200
    for needed in ('id="source-switch"', 'id="local-open"', 'id="file-save"', 'id="explorer"', 'id="view-switch"'):
        assert needed in page.text, needed
    assert "/static/vendor/codemirror/" in page.text, "the editor is loaded from this server"
    assert "<style" not in page.text and "googleapis" not in page.text and "cdn." not in page.text and "unpkg" not in page.text
    assert "/static/vendor/codemirror/" not in e.alice.c.get(f"/{SLUG}").text, "chat does not load the editor"


def test_the_editor_is_served_from_here_with_its_licences(e):
    bundle = sorted(VENDOR.glob("*.js"))
    assert len(bundle) == 1, "one file, built once"
    r = httpx.get(f"{e.srv.url}/static/vendor/codemirror/{bundle[0].name}")
    assert r.status_code == 200 and len(r.content) > 200_000 and "javascript" in r.headers["content-type"]
    text = bundle[0].read_text(encoding="utf-8", errors="replace")
    assert not re.search(r"\beval\(|new Function\(", text), "nothing in it needs unsafe-eval"
    assert not re.search(r"https?://(?!codemirror\.net|lezer\.codemirror\.net|github\.com|www\.w3\.org|developer\.mozilla\.org)[a-z0-9.-]+/[^\s\"']*\.js",
                         text), "it loads no script from elsewhere"
    assert any(VENDOR.glob("LICENSE*")), "the licences travel with it"
    note = (ROOT / "asterism" / "static" / "vendor" / "README").read_text(encoding="utf-8")
    for name, version in PINNED.items():
        assert name in note and version in note, f"the vendor note names {name} {version}"


def test_the_recipe_that_built_it_is_in_the_repository():
    manifest = json.loads((RECIPE / "package.json").read_text(encoding="utf-8"))
    deps = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
    for name, version in PINNED.items():
        assert deps.get(name) == version, f"{name} is pinned to {version} exactly, not a range"
    assert all(re.fullmatch(r"\d+\.\d+\.\d+", v) for v in deps.values()), f"every version is exact: {deps}"
    lock = json.loads((RECIPE / "package-lock.json").read_text(encoding="utf-8"))
    packages = lock["packages"]
    assert packages["node_modules/codemirror"]["version"] == "6.0.2"
    assert all("integrity" in p for k, p in packages.items() if k.startswith("node_modules/") and not p.get("link")), \
        "every package in the lock has its integrity hash"
    assert (RECIPE / "README.md").is_file() and any(RECIPE.glob("*.js")) or any(RECIPE.glob("*.mjs"))
    assert not (RECIPE / "node_modules").exists() or (ROOT / ".gitignore").read_text(encoding="utf-8").count("node_modules"), \
        "what the recipe downloads is not committed"


def test_the_pages_policy_stays_tight(e):
    csp = e.alice.c.get(f"/{SLUG}/files").headers["content-security-policy"]
    parts = {d.split()[0]: d.split()[1:] for d in (x.strip() for x in csp.split(";")) if d}
    assert "'unsafe-eval'" not in csp and "*" not in csp.replace("'", ""), csp
    assert "blob:" in parts["img-src"] and "blob:" in parts["frame-src"], "a local picture or PDF is shown through an object URL"
    for directive, sources in parts.items():
        if directive not in ("img-src", "frame-src"):
            assert "blob:" not in sources and "data:" not in sources, f"{directive}: {sources}"
    assert parts["script-src"][0] == "'self'" and all(s == "'self'" or s.startswith("'sha256-") for s in parts["script-src"])
    assert parts["default-src"] == ["'self'"] and parts["frame-ancestors"] == ["'none'"]
