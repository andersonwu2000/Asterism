"""The frame and the visual language of the pages (DESIGN.md), as far as a test can own them: the same frame on
every page of a project, colours only through the tokens, the fonts served from this server, no browser dialogs.

    python -m pytest tests/test_m1f.py -q
"""
from __future__ import annotations

import re

import httpx
import pytest

from test_m1b import ROOT, SLUG, build_world

STATIC = ROOT / "asterism" / "static"
TOKENS = ("--color-bg", "--color-surface", "--color-surface-2", "--color-surface-3", "--color-edge", "--color-edge-strong",
          "--color-wash", "--color-wash-2", "--color-wash-3", "--color-ink", "--color-ink-dim", "--color-ink-faint",
          "--color-loud", "--color-destruct")
PAGES = ("", "/schedules", "/members", "/my", "/admin")
COLOUR = re.compile(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3,4}\b|\brgba?\(|\bhsla?\(|\boklch\(|"
                    r":\s*(?:white|black|red|gray|grey|silver)\b")


@pytest.fixture(scope="module")
def f(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("dataf"))
    yield world
    world.srv.stop()


def own_files(suffix: str) -> list:
    """The stylesheets or scripts written for these pages (not the third-party ones under vendor/)."""
    return sorted(p for p in STATIC.rglob("*" + suffix) if "vendor" not in p.parts)


def without_token_blocks(css: str) -> str:
    """The stylesheet with every rule block that only declares `--color-*` tokens taken out."""
    def keep(m: re.Match) -> str:
        body = re.sub(r"/\*.*?\*/", "", m.group(2), flags=re.S)
        decls = [d.strip() for d in body.split(";") if d.strip()]
        only_tokens = decls and all(d.startswith("--color-") or d.startswith("color-scheme") for d in decls)
        return "" if only_tokens else m.group(0)
    return re.sub(r"([^{}]*)\{([^{}]*)\}", keep, css)


def test_every_page_of_a_project_has_the_same_frame(f):
    """A fixed rail on the far left holds the top-level buttons (chat, files, then the other pages); the second
    column belongs to the mode: channels and private conversations in chat, the explorer in files, none elsewhere."""
    for path in PAGES + ("/files",):
        page = f.alice.c.get(f"/{SLUG}{path}")
        assert page.status_code == 200, path
        html = page.text
        for needed in ('id="rail"', 'id="rail-chat"', 'id="rail-files"', 'id="theme-toggle"', 'id="side-open"'):
            assert needed in html, f"{path}: {needed}"
        assert '/static/app.css' in html, path
        assert "<style" not in html, f"{path}: styles live in the stylesheet, not in the page"
        head = html.split("</head>")[0]
        assert "data-theme" in head and "localStorage" in head, f"{path}: the theme is chosen before the first paint"
        assert head.index("data-theme") < head.index("/static/app.css"), f"{path}: the theme script comes before the stylesheet"
        in_chat, in_files = path == "", path == "/files"
        assert ('id="side-channels"' in html and 'id="side-private"' in html) == in_chat, f"{path}: channels belong to chat"
        assert ('id="explorer"' in html) == in_files, f"{path}: the explorer belongs to files"
    messages = f.alice.c.get(f"/{SLUG}").text
    assert 'id="members-toggle"' in messages and 'id="search-open"' in messages and 'id="pins"' not in messages
    files = f.alice.c.get(f"/{SLUG}/files").text
    for needed in ('id="explorer"', 'id="explorer-toggle"', 'id="file-tabs"', 'id="file-view"', 'id="view-switch"'):
        assert needed in files, needed
    deep = f.alice.c.get(f"/{SLUG}/files/notes/deep/MAP.md")
    assert deep.status_code == 200 and 'id="file-view"' in deep.text, "a file has an address of its own"
    assert f.alice.c.get(f"/{SLUG}/files/..%2f..%2fetc").status_code in (200, 400, 404)
    assert 'id="rail"' not in httpx.get(f.srv.url + "/", follow_redirects=True).text, "no project, no rail"
    assert httpx.get(f"{f.srv.url}/{SLUG}/files", follow_redirects=False).status_code in (302, 303, 401), "members only"


def test_colours_come_only_from_the_tokens():
    sheets = own_files(".css")
    assert any(p.name == "app.css" for p in sheets)
    main = (STATIC / "app.css").read_text(encoding="utf-8")
    for token in TOKENS:
        assert main.count(token + ":") >= 2, f"{token} is defined for the dark end and for the light end"
    assert "data-theme" in main and "prefers-reduced-motion" in main and "prefers-color-scheme" in main
    for p in sheets:
        rest = without_token_blocks(p.read_text(encoding="utf-8"))
        rest = re.sub(r"/\*.*?\*/", "", rest, flags=re.S)
        hit = COLOUR.search(rest)
        assert not hit, f"{p.name}: a colour outside the token block: ...{rest[max(0, hit.start() - 60):hit.end() + 20]}..."
    for p in own_files(".js"):
        js = p.read_text(encoding="utf-8")
        hit = re.search(r"#[0-9a-fA-F]{6}\b|\brgba?\(", js)
        assert not hit, f"{p.name}: a colour in a script: ...{js[max(0, hit.start() - 60):hit.end() + 20]}..."
    pages = (ROOT / "asterism" / "pages.py").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?=[;\"'} ])", pages), "pages.py names no colour either"


def test_the_fonts_are_served_from_here(f):
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    for name in ("inter-latin-400-normal.woff2", "inter-latin-600-normal.woff2", "jetbrains-mono-latin-400-normal.woff2",
                 "fraunces-latin-wght-normal.woff2"):
        assert name in css, f"{name} is not used by the stylesheet"
        r = httpx.get(f"{f.srv.url}/static/vendor/fonts/{name}")
        assert r.status_code == 200 and len(r.content) > 10_000, name
    assert "fonts.googleapis.com" not in css and "fonts.gstatic.com" not in css, "nothing is loaded from elsewhere"
    for path in PAGES:
        html = f.alice.c.get(f"/{SLUG}{path}").text
        assert "googleapis" not in html and "gstatic" not in html and "cdn." not in html


def test_no_browser_dialogs():
    for p in own_files(".js"):
        js = p.read_text(encoding="utf-8")
        assert not re.search(r"\b(?:window\.)?(?:confirm|alert|prompt)\(", js), f"{p.name}: acts confirm in place, in two steps"
