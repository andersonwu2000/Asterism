"""Server-rendered pages. Every text comes from the message catalogue (tr), every value is escaped.

Forms marked data-api are sent as JSON by /static/app.js to the same JSON API that scripts use, so a
page does nothing the API does not; the OAuth consent form is a plain form because it ends in a redirect.

The look is DESIGN.md's: one stylesheet (/static/app.css) and no styles in the page. A page of a project sits in
the project's frame, four cells beside the rail (#rail, rail.js): the top-left cell (#corner, one line over the
second column), the second column (the channels #side in chat, kept current by frame.js; the conversations in private
messages; the explorer #explorer in files; the agents #agent-side on the agent page; the scopes #work-side on the
work page; the sections #settings-nav in
settings), the top-right cell (the page's title or tabs and its actions) and the page itself. The other pages are a
simple centred column.
"""
from __future__ import annotations

import base64
import hashlib
import json
import urllib.parse
from html import escape
from typing import Any, Iterable

from . import assets
from .i18n import Translator
from .projects import SWITCHES


def e(v: Any) -> str:
    return escape("" if v is None else str(v), quote=True)


def q(v: str) -> str:
    return urllib.parse.quote(v, safe="")


# Chooses the theme before the first paint (the stored choice, else the system's) and which second columns the reader
# folded away (DESIGN: layout), so neither flashes. The Content-Security-Policy allows exactly this script by its hash
# (THEME_CSP), so the hash is taken from this text.
THEME_SCRIPT = ('(function(){var d=document.documentElement,t=null,f=null;try{t=localStorage.getItem("asterism-theme");'
                'f=localStorage.getItem("asterism-folded")}catch(e){}'
                'if(t!=="dark"&&t!=="light"){t=window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches'
                '?"light":"dark"}d.setAttribute("data-theme",t);if(f)d.setAttribute("data-folded",f)})();')
THEME_CSP = "'sha256-" + base64.b64encode(hashlib.sha256(THEME_SCRIPT.encode()).digest()).decode() + "'"


def _attrs(data: dict[str, Any]) -> str:
    """data- attributes: strings as they are, anything else as JSON."""
    return " ".join(f'data-{k}="{e(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))}"'
                    for k, v in data.items())


def _theme_button(tr: Translator) -> str:
    """The theme switch; base.js keeps its label naming the end it switches to."""
    return (f'<button type="button" id="theme-toggle" class="quiet-btn" aria-label="{e(tr("theme.to_light_label"))}">'
            f'{e(tr("theme.to_light"))}</button>')


def open_button(tr: Translator) -> str:
    """Opens the navigation drawer below 900 px (rail.js); not shown on wider screens."""
    return (f'<button type="button" id="side-open" class="icon-btn side-open" aria-controls="nav" aria-expanded="false" '
            f'aria-label="{e(tr("nav.open"))}"><span class="burger" aria-hidden="true"></span></button>')


# Line drawings on a 24-unit grid, stroked in currentColor; always decorative (the word or the label says it).
GLYPHS = {
    "chat": '<path d="M4 5h16v11H9l-5 4z"/>',
    "dm": '<path d="M3 6h12v8H7l-4 3z"/><path d="M15 9h6v8l-3-2.5h-6v-.5"/>',
    "files": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    "schedules": '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
    "members": '<circle cx="9" cy="9" r="3"/><path d="M3 19c0-3 3-5 6-5s6 2 6 5"/><rect x="15.5" y="6" width="5" height="5" rx="1"/>',
    "my": '<rect x="4" y="5" width="16" height="11" rx="2"/><path d="M9 20h6M12 16v4"/>',
    "column": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M9.5 4.5v15"/>',
    "rendered": '<path d="M6 3h8l4 4v14H6z"/><path d="M9 12h6M9 15h6M9 18h3"/>',
    "source": '<path d="M9 7l-5 5 5 5M15 7l5 5-5 5"/>',
    "split": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M12 4.5v15M6.5 9h3M6.5 12h3M14.5 9h3M14.5 12h3"/>',
    "github": '<path d="M13 4h7v7M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "save": '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',
    "chevron": '<path d="M7 10l5 5 5-5"/>',
    "invite": '<circle cx="10" cy="8" r="3.5"/><path d="M3.5 19.5c0-3.3 2.9-5.5 6.5-5.5s6.5 2.2 6.5 5.5"/><path d="M19 7v6M16 10h6"/>',
    "tasks": '<path d="M10 6h10M10 12h10M10 18h10"/><path d="M4 6l1.5 1.5L8 5M4 12l1.5 1.5L8 11M4 18l1.5 1.5L8 17"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1'
            'M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
    # A channel's settings: three sliders.
    "sliders": '<path d="M4 7h9M17 7h3M4 12h3M11 12h9M4 17h11M19 17h1"/><circle cx="15" cy="7" r="2"/>'
               '<circle cx="9" cy="12" r="2"/><circle cx="17" cy="17" r="2"/>',
    "burger": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    # The composer's send control (1y): an upward arrow; the button around it is the filled circle.
    "send": '<path d="M12 18.5V6M6.5 11.5L12 6l5.5 5.5"/>',
    # Add a reaction (1y): a face with a small plus.
    "react": '<path d="M19.5 12a7.5 7.5 0 1 1-6-7.35"/><path d="M9 14.5c.8 1 1.8 1.5 3 1.5s2.2-.5 3-1.5"/>'
             '<path d="M9.5 10h.01M14.5 10h.01"/><path d="M19 3v5M16.5 5.5h5"/>',
    # Edit (1y): a pencil.
    "edit": '<path d="M5 19l1-4L16 5l3 3L9 18z"/><path d="M14 7l3 3"/>',
    # Delete (1y): a bin.
    "bin": '<path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12"/>',
    "reply": '<path d="M10 8L5 12.5l5 4.5"/><path d="M5.5 12.5H14a5 5 0 0 1 5 5v1"/>',
    # A channel some members may not read.
    "lock": '<rect x="6" y="11" width="12" height="9" rx="2"/><path d="M9 11V8.5a3 3 0 0 1 6 0V11"/>',
    "dots": '<circle cx="6" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="18" cy="12" r="1.2"/>',
    "grip": '<circle cx="9" cy="7" r="1"/><circle cx="15" cy="7" r="1"/><circle cx="9" cy="12" r="1"/>'
            '<circle cx="15" cy="12" r="1"/><circle cx="9" cy="17" r="1"/><circle cx="15" cy="17" r="1"/>',
}

# The glyphs the page scripts draw (A.glyph clones them from this template).
SCRIPT_GLYPHS = ("sliders", "chevron", "dots", "grip", "lock", "react", "edit", "bin", "reply")


def glyph(name: str, size: int = 20, extra: str = "") -> str:
    return (f'<svg class="glyph" aria-hidden="true" focusable="false" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"{extra}>'
            f'{GLYPHS[name]}</svg>')


def _glyph_set() -> str:
    return ('<template id="glyphs">' + "".join(glyph(n, 16, f' data-glyph="{n}"') for n in SCRIPT_GLYPHS)
            + '</template>')


def dropdown(tr: Translator, name: str, options: list[tuple[str, str]], label: str, value: str | None = None,
             data_list: bool = False) -> str:
    """The one dropdown (base.js wires every [data-dropdown]): a button with the current choice and a chevron that
    opens the choices as a menu; the hidden field beside it carries the value for a form."""
    cur = value if value is not None and any(v == value for v, _ in options) else (options[0][0] if options else "")
    shown = next((t for v, t in options if v == cur), "")
    return (f'<span class="dropdown-field"><button type="button" class="dropdown" aria-haspopup="menu" aria-expanded="false" '
            f'aria-label="{e(label)}" title="{e(label)}" data-dropdown="{e(json.dumps(options, ensure_ascii=False))}">'
            f'<span class="dropdown-value">{e(shown)}</span>{glyph("chevron", 16)}</button>'
            f'<input type="hidden" name="{e(name)}" value="{e(cur)}"{" data-list" if data_list else ""}></span>')


# The display face (the project's name) and the body face: on every page, before anything is drawn.
PRELOAD_FONTS = ("fraunces-latin-wght-normal.woff2", "inter-latin-400-normal.woff2")


def layout(tr: Translator, title: str, body: str, person: dict[str, Any] | None = None,
           frame: dict[str, Any] | None = None, here: str = "", status: int = 200,
           styles: Iterable[str] = (), scripts: Iterable[str] = (), page_class: str = "",
           corner: str = "", column: str = "", bar: str = "") -> tuple[str, int]:
    """A page. With `frame` (a page of a project) it sits in the project's frame, `here` naming the current mode
    (messages, dm, files, agent, work, settings): `corner` is the top-left cell, `column` the second column (an element of
    class "column"), `bar` the top-right cell after the drawer's button, `body` the page. Without, in a simple centred
    column. `styles` and `scripts`: further files under /static; the scripts load after base.js (and frame.js) and
    before app.js."""
    msgs = e(json.dumps(tr.js_messages(), ensure_ascii=False))
    links = "".join(f'<link rel="stylesheet" href="{e(assets.url(x))}">' for x in styles)
    shared = ["base.js"] + (["frame.js", "rail.js", "project.js"] if frame else [])
    tags = "".join(f'<script src="{e(assets.url(x))}"></script>' for x in [*shared, *scripts, "app.js"])
    # The faces every page draws first, asked for at once (the stylesheet names the same addresses).
    preload = "".join(f'<link rel="preload" href="{e(assets.url("vendor/fonts/" + x))}" as="font" type="font/woff2" '
                      f'crossorigin>' for x in PRELOAD_FONTS)
    if frame:
        mode = MODES.get(here, here)
        # The top bar is two cells of the frame's grid on a wide screen (rail.js moves the top-left one into the
        # drawer below 900 px); the second column is the cell under the top-left one.
        main = (f'<div class="shell mode-{e(mode)}">'
                f'<div id="nav" class="nav" aria-label="{e(tr("nav.label"))}">{_rail(tr, person, frame, here)}{column}</div>'
                f'<div id="side-scrim" hidden></div>'
                f'<header id="topbar" class="topbar"><div id="corner" class="corner">{corner}</div>'
                f'<div class="bar">{open_button(tr)}{bar}</div></header>'
                f'<main id="page" class="page {e(page_class)}">{body}</main></div>{_glyph_set()}{_invite_panel(tr, frame)}')
        cls = "framed"
    else:
        who = ""
        if person:
            who = (f'<span class="me">{e(tr("nav.signed_in_as", name=person["name"]))}</span>'
                   f'<form method="post" action="/logout"><button class="quiet-btn">{e(tr("nav.logout"))}</button></form>')
        main = (f'<header class="plain-head"><a class="brand" href="/">{e(tr("app.name"))}</a>'
                f'<span class="spacer"></span>{who}{_theme_button(tr)}</header>'
                f'<main id="page" class="column"><h1 class="page-title">{e(title)}</h1>{body}</main>')
        cls = "plain"
    html = (f'<!doctype html><html lang="{e(tr.locale)}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<script>{THEME_SCRIPT}</script>'
            f'<link rel="icon" href="{e(assets.url("favicon.svg"))}" type="image/svg+xml">'
            f'<link rel="stylesheet" href="{e(assets.url("app.css"))}">{preload}{links}'
            f'<title>{e(tr("page.title", title=title, app=tr("app.name")))}</title></head>'
            f'<body class="{cls}" data-msg="{msgs}">{main}{tags}</body></html>')
    return html, status


def message(tr: Translator, title_key: str, text: str, status: int, **ctx: Any) -> tuple[str, int]:
    return layout(tr, tr(title_key), f"<p>{e(text)}</p>", status=status, **ctx)


# --------------------------------------------------------------------------- the project's frame

def _repo_text(repo: str) -> str:
    return repo.split("://", 1)[-1].rstrip("/")


def _count(tr: Translator, unread: int, important: int, muted: bool) -> str:
    """Important unread: an inverted pill with that count, muted or not (muting silences a place's talk, not a
    message that names the reader). Other unread: the plain count, none in a muted place (DESIGN: muted)."""
    if important:
        said = tr("nav.important_muted", k=important) if muted else tr("nav.important", n=unread, k=important)
        return (f'<span class="pill" aria-hidden="true">{e(important)}</span>'
                f'<span class="vh">{e(said)}</span>')
    if unread and not muted:
        return (f'<span class="count" aria-hidden="true">{e(unread)}</span>'
                f'<span class="vh">{e(tr("nav.unread", n=unread))}</span>')
    return ""


def channel_settings_href(slug: str, name: str) -> str:
    return f"/{q(slug)}/channels/{q(name)}/settings"


def dm_href(slug: str, name: str) -> str:
    return f"/{q(slug)}/dm/{q(name)}"


def _place_link(tr: Translator, slug: str, place: str, inner: str, unread: int, important: int, muted: bool) -> str:
    """One place of the navigation; frame.js redraws the lists with the same markup. A channel's row also has a
    sliders mark to its settings (shown on hover and focus); a private conversation's row leads to its own page."""
    cls = "place" + (" unread" if unread and not muted else "") + (" muted" if muted else "")
    gear = ""
    if place.startswith("#"):
        label = e(tr("chan.gear", place=place))
        gear = (f'<a class="place-gear" href="{e(channel_settings_href(slug, place[1:]))}" aria-label="{label}" '
                f'title="{label}">{glyph("sliders", 16)}</a>')
        href = f"/{e(q(slug))}#{e(q(place))}"
    else:
        href = e(dm_href(slug, place))
    return (f'<li class="place-row"><a class="{cls}" href="{href}" data-place="{e(place)}">{inner}'
            f'{_count(tr, unread, important, muted)}</a>{gear}</li>')


def presence_mark(tr: Translator, who: dict[str, Any] | None) -> str:
    """Shape says who, fill says state: a square for a person, a disc for an agent, filled when online."""
    kind = "agent" if who and who.get("kind") == "agent" else "person"
    on = bool(who and who.get("online"))
    return (f'<span class="presence {kind}{" on" if on else ""}" role="img" '
            f'aria-label="{e(tr("presence.online" if on else "presence.offline"))}"></span>')


def _menu_item(tr: Translator, label_key: str, act: str = "", href: str = "") -> str:
    """An item of a menu drawn here (the markup of base.js's menus): a destination, or an act for project.js."""
    if href:
        return f'<a class="menu-item" role="menuitem" tabindex="-1" href="{e(href)}">{e(tr(label_key))}</a>'
    return (f'<button type="button" class="menu-item" role="menuitem" tabindex="-1" data-act="{act}">'
            f'{e(tr(label_key))}</button>')


def _project_button(tr: Translator, f: dict[str, Any]) -> str:
    """The project's name (display voice) as the button of the project menu, at the left of the top bar. The menu
    offers each item only to who may use it; project.js opens it and does its acts."""
    slug, mine = f["slug"], set(f["perms"])
    items = []
    if f["can_admin"]:
        items.append(_menu_item(tr, "pm.invite_people", act="invite-people"))
    if "manage_own_agents" in mine:
        items.append(_menu_item(tr, "pm.invite_agent", act="invite-agent"))
    if items:
        items.append('<div class="menu-sep" role="separator"></div>')
    items.append(_menu_item(tr, "pm.settings", href=f"/{q(slug)}/settings"))
    if f["can_create"]:
        items.append(_menu_item(tr, "pm.new_channel", act="new-channel"))
    items.append(_menu_item(tr, "pm.my", href=f"/{q(slug)}/agent"))
    return (f'<div class="topbar-project">'
            f'<button type="button" id="project-menu-button" class="project-name" aria-haspopup="menu" '
            f'aria-expanded="false" aria-controls="project-menu" title="{e(tr("pm.open"))}">'
            f'<span class="project-name-text">{e(f["name"])}</span>{glyph("chevron", 16)}</button>'
            f'<div id="project-menu" class="menu" role="menu" aria-label="{e(tr("pm.open"))}" tabindex="-1" popover="manual">'
            f'{"".join(items)}</div></div>')


def _repo_link(tr: Translator, repo: str) -> str:
    return (f'<a class="project-repo" href="{e(repo)}" target="_blank" rel="noopener noreferrer" '
            f'title="{e(tr("nav.repo"))}">{e(_repo_text(repo))}</a>')


# The rail's buttons in their order: (page, glyph, word, full name, id). Members, groups and the project's settings
# are reached from the project menu; tasks and scheduled messages are the work page's tabs.
RAIL = (("messages", "chat", "rail.chat", "nav.messages", "rail-chat"), ("dm", "dm", "rail.dm", "nav.dm", "rail-dm"),
        ("files", "files", "rail.files", "nav.files", "rail-files"), ("agent", "my", "rail.my", "nav.my", "rail-my"),
        ("work", "tasks", "rail.work", "nav.work", "rail-work"))
# The modes whose second column the button of the mode one is in folds away (rail.js): (fold key, the column's id).
FOLDS = {"messages": ("chat", "side"), "dm": ("dm", "side"), "files": ("files", "explorer"),
         "agent": ("agent", "agent-side"), "work": ("work", "work-side")}
# The class of the frame for each mode (`here`): it names what folds and the second column's width.
MODES = {"messages": "chat", "dm": "dm", "files": "files", "agent": "agent", "work": "work", "settings": "settings"}


def _rail(tr: Translator, person: Any, f: dict[str, Any], here: str) -> str:
    """The fixed rail on the far left of every page of a project: the top-level buttons, then the reader, whose menu
    opens the personal settings (the theme is one of them) and signs out. rail.js keeps the counts of important messages on the chat and private-messages buttons, where each
    mode last was, and folds the second column when the button of the mode one is in is pressed again."""
    slug, me = f["slug"], (person["name"] if person else "")
    items = []
    for page, icon, word, full, ident in RAIL:
        href = f"/{q(slug)}" if page == "messages" else f"/{q(slug)}/{page}"
        current = ' aria-current="page"' if page == here else ""
        fold, title = "", tr(full)
        if page == here and page in FOLDS:
            fold = f' data-fold="{FOLDS[page][0]}" aria-controls="{FOLDS[page][1]}" aria-expanded="true"'
            title = tr("rail.fold_hint", name=tr(full))
        count = ""
        if page in ("messages", "dm"):
            k = (f["important"] if page == "messages" else f["important_private"]) if here != page else 0
            count = (f'<span id="{ident}-count" class="rail-count"{"" if k else " hidden"}>'
                     f'<span class="pill" aria-hidden="true">{e(k)}</span>'
                     f'<span class="vh">{e(tr("rail.important", k=k))}</span></span>')
        items.append(f'<li><a id="{ident}" class="rail-btn" href="{e(href)}" title="{e(title)}"{current}{fold}>'
                     f'<span class="rail-tile">{glyph(icon)}{count}</span><span class="rail-word">{e(tr(word))}</span></a></li>')
    data = {"slug": slug, "me": me, "here": here, "directory": f["directory"], "repo": f["repo"], "perms": f["perms"],
            "beat": f.get("beat_s", 20)}
    # The reader's avatar (1z), else the first letter of their name; frame.js follows a change.
    version = (f["directory"].get(me) or {}).get("avatar") or ""
    face = (f'<img alt="" src="/{e(q(slug))}/api/avatars/person/{e(q(me))}?v={e(q(version))}">' if version
            else e((me[:1] or "?").upper()))
    reader = (f'<button type="button" id="rail-me" class="rail-me" popovertarget="me-menu" data-v="{e(version)}" '
              f'aria-label="{e(tr("rail.me", name=me))}" title="{e(me)}"><span aria-hidden="true">{face}</span></button>'
              f'<div id="me-menu" class="me-menu" popover><p class="me-name">{e(me)}</p>'
              f'<a class="me-row" id="me-settings" href="/{e(q(slug))}/me">{e(tr("rail.settings"))}</a>'
              f'<a class="me-row" href="/">{e(tr("rail.home"))}</a>'
              f'<form method="post" action="/logout"><button class="me-row">{e(tr("nav.logout"))}</button></form></div>')
    return (f'<nav id="rail" class="rail" aria-label="{e(tr("rail.label"))}" {_attrs(data)}>'
            f'<button type="button" id="side-close" class="icon-btn nav-close" aria-label="{e(tr("nav.close"))}">'
            f'<span class="cross" aria-hidden="true"></span></button>'
            f'<ul class="rail-list">{"".join(items)}</ul>'
            f'<div class="rail-foot">{reader}</div></nav>')


def _lock_mark(tr: Translator) -> str:
    """A small lock after a channel's name: some members may not read it (frame.js draws the same)."""
    return (f'<span class="lock-mark" title="{e(tr("nav.restricted"))}">{glyph("lock", 12)}'
            f'<span class="vh">{e(tr("nav.restricted"))}</span></span>')


def _side(tr: Translator, f: dict[str, Any]) -> str:
    """Chat's second column: the channels (frame.js keeps them current). The project's name is in the top-left cell."""
    slug, places = f["slug"], f["places"]
    channels = "".join(
        _place_link(tr, slug, "#" + c["name"], f'<span class="place-name">#{e(c["name"])}</span>'
                    + (_lock_mark(tr) if c.get("restricted") else "")
                    + (f'<span class="note">{e(tr("nav.muted"))}</span>' if c["muted"] else ""),
                    c["unread"], c["important"], c["muted"]) for c in places["channels"])
    plus_channel = ""
    if f["can_create"]:            # the same floating form as the project menu's "create channel" (project.js)
        label = e(tr("nav.new_channel"))
        plus_channel = (f'<button type="button" class="icon-btn small" data-act="new-channel" aria-label="{label}" '
                        f'title="{label}"><span class="plus" aria-hidden="true"></span></button>')
    return (f'<nav id="side" class="column" aria-label="{e(tr("nav.places"))}"><div class="side-inner">'
            f'<section class="side-sec"><div class="side-head"><h2>{e(tr("msg.channels"))}</h2>{plus_channel}</div>'
            f'<ul id="side-channels" class="side-list">{channels}</ul></section>'
            f'</div></nav>')


def _dm_side(tr: Translator, f: dict[str, Any]) -> str:
    """Private messages' second column: the conversations, newest first, with their unread marks (frame.js keeps them
    current), and "new conversation", a menu of the members one may write to privately (frame.js)."""
    slug, directory = f["slug"], f["directory"]
    rows = []
    for p in f["places"]["private"]:
        rows.append(_place_link(tr, slug, p["with"],
                                f'{presence_mark(tr, directory.get(p["with"]))}<span class="place-name">{e(p["with"])}</span>',
                                p["unread"], p["important"], False))
    choices = [{"name": n, "agent": False} for n in f["people"]] + [{"name": n, "agent": True} for n in f["agents"]]
    plus = ""
    if choices:
        label = e(tr("nav.start_private"))
        plus = (f'<button type="button" id="dm-new" class="icon-btn small" aria-haspopup="menu" aria-expanded="false" '
                f'aria-label="{label}" title="{label}" data-choices="{e(json.dumps(choices, ensure_ascii=False))}">'
                f'<span class="plus" aria-hidden="true"></span></button>')
    return (f'<nav id="side" class="column" aria-label="{e(tr("dm.list"))}"><div class="side-inner">'
            f'<section class="side-sec"><div class="side-head"><h2>{e(tr("msg.private"))}</h2>{plus}</div>'
            f'<ul id="dm-list" class="side-list">{"".join(rows)}</ul>'
            f'<p id="dm-none" class="side-note"{" hidden" if rows else ""}>{e(tr("dm.none"))}</p></section>'
            f'</div></nav>')


def _source_button(tr: Translator) -> str:
    """Files' top-left cell: the two sources side by side (1x), the repository and a local folder (by their catalogue
    names), the one shown pressed; explorer.js keeps aria-pressed current."""
    buttons = "".join(f'<button type="button" class="seg-btn" data-source="{k}" aria-pressed="{"true" if k == "repo" else "false"}">'
                      f'{e(tr(key))}</button>' for k, key in (("repo", "files.source_repo"), ("local", "files.source_local")))
    return f'<div id="source-switch" class="seg source-switch" role="group" aria-label="{e(tr("files.source"))}">{buttons}</div>'


def _explorer(tr: Translator, f: dict[str, Any]) -> str:
    """Files' second column: a line with the files menu (the local folder's controls) and the search field (paths of
    the source shown; the results take the tree's place while there is something in it), then the tree (explorer.js
    draws it, local.js reads the folder; the local folder is one folder at the top of its tree). Nothing of a local
    folder is ever known here: its name is filled in by the page script."""
    menu, search = e(tr("files.menu")), e(tr("files.search"))
    local = (f'<div id="local-bar" class="local-bar" hidden>'
             f'<p id="local-unsupported" class="explorer-note" hidden>{e(tr("local.unsupported"))}</p>'
             f'<p id="local-none" class="explorer-note" hidden>{e(tr("local.none"))}</p>'
             f'<button type="button" id="local-open" class="btn">{e(tr("local.open"))}</button>'
             f'<button type="button" id="local-restore" class="btn" hidden></button>'
             f'<p id="local-note" class="explorer-note" role="status"></p></div>')
    return (f'<aside id="explorer" class="column explorer" aria-label="{e(tr("files.explorer"))}"><div class="side-inner">'
            f'<div class="explorer-top">'
            f'<button type="button" id="files-menu" class="icon-btn" aria-haspopup="menu" aria-expanded="false" '
            f'aria-label="{menu}" title="{menu}">{glyph("burger")}</button>'
            f'<div class="files-search" role="search">{glyph("search", 16)}'
            f'<input id="files-search" type="search" placeholder="{e(tr("files.search_placeholder"))}" '
            f'aria-label="{search}" role="combobox" aria-autocomplete="list" aria-expanded="false" '
            f'aria-controls="files-found" autocomplete="off" spellcheck="false" autocapitalize="off" maxlength="200">'
            f'</div></div>'
            f'<p id="explorer-ref" class="explorer-ref">{e(_repo_text(f["repo"]))}</p>'
            f'{local}'
            f'<p id="explorer-note" class="explorer-note" role="status" hidden></p>'
            f'<ul id="explorer-tree" class="tree" role="tree" aria-label="{e(tr("files.tree"))}"></ul>'
            f'<ul id="files-found" class="tree found" role="listbox" aria-label="{e(tr("files.found"))}" hidden></ul>'
            f'<p id="files-found-status" class="explorer-note" role="status" hidden></p>'
            f'<p id="explorer-status" class="vh" role="status"></p>'
            f'</div></aside>')


def _chat_bar(tr: Translator) -> str:
    """The top-right cell in chat and private messages: the place's name (a channel's opens its settings, a private
    conversation's the other member's card), and at the right the member list toggle and the search icon. The
    project's name, the menu's button, is the top-left cell."""
    tools = (_tool(tr, "members-toggle", "members", "bar.members", 'aria-expanded="false" aria-controls="member-panel"')
             + _tool(tr, "search-open", "search", "bar.search", 'aria-expanded="false" aria-controls="search-results"'))
    return (f'<h1 id="place-title" class="place-title"><button type="button" id="place-button" class="place-btn"></button></h1>'
            f'<span class="spacer"></span>'
            f'<div class="room-tools" role="group" aria-label="{e(tr("bar.tools"))}">{tools}</div>')


def _invite_panel(tr: Translator, f: dict[str, Any]) -> str:
    """What inviting an agent of mine shows, in the floating panel that the project menu's item and the agent page's
    action open (project.js moves it there): making a link (#invite-make), what one agrees to by sending it
    (#invite-consent) and the answer (#invite-result, Asterism.showInvite). Only for who may manage their agents."""
    if "manage_own_agents" not in f["perms"]:
        return ""
    return (f'<div id="invite-panel" class="invite-panel" hidden><p class="dim">{e(tr("invite.skip"))}</p>'
            f'<p class="row"><button type="button" class="btn primary" id="invite-make" '
            f'data-api="/{q(f["slug"])}/api/my/agent-invites">{e(tr("invite.button"))}</button>'
            f'<span class="out" data-out></span></p>'
            f'<p class="dim" id="invite-consent">{e(tr("invite.consent"))}</p>'
            f'<div id="invite-result" class="invite-result" hidden></div></div>')


# --------------------------------------------------------------------------- pages

def home(tr: Translator, person: dict[str, Any] | None, projects: list[dict[str, str]]) -> tuple[str, int]:
    if not person:
        body = (f'<p>{e(tr("home.sign_in_hint"))}</p>'
                f'<p><a class="btn primary" href="/login?next=/">{e(tr("login.github"))}</a></p>')
        return layout(tr, tr("home.title"), body)
    if projects:
        items = "".join(f'<li><a class="card-link" href="/{q(p["slug"])}"><span class="card-title">{e(p["name"])}</span>'
                        f'<span class="mono dim">{e(_repo_text(p["repo"]))}</span></a></li>' for p in projects)
        body = f'<h2>{e(tr("home.projects"))}</h2><ul class="cards">{items}</ul>'
    else:
        body = f'<p>{e(tr("home.no_projects"))}</p>'
    # Anyone signed in makes a project (it lives on this server): its name and repository; the server chooses its
    # address (1y). app.js sends the form and opens the new project at the address the answer gives.
    body += (f'<details class="new-project" id="new-project"><summary class="btn">{e(tr("home.new"))}</summary>'
             f'<form class="stack" data-api="/api/projects" data-goto="slug" data-refusal="home.new">'
             f'<label class="field"><span>{e(tr("home.new_name"))}</span><input name="name" required maxlength="80" '
             f'autocomplete="off"></label>'
             f'<label class="field"><span>{e(tr("home.new_repo"))}</span><input name="repo" type="url" data-invalid="error.invalid_repo" '
             f'placeholder="https://github.com/owner/name" autocomplete="off" spellcheck="false">'
             f'<span class="dim">{e(tr("home.new_repo_hint"))}</span></label>'
             f'<div class="row"><button class="btn primary">{e(tr("home.new_create"))}</button>'
             f'<span class="out" data-out aria-live="polite"></span></div></form></details>')
    return layout(tr, tr("home.title"), body, person)


# Agent-facing wording, word for word from the specification; English whatever the page's language.
AGENT_LINE = ('If you are an agent: ask your user for an agent invitation link (from the "my agents" page of this '
              "project) and open it.")


def landing(tr: Translator, slug: str) -> tuple[str, int]:
    """The project's address without a session: a sign-in link for people, one sentence for agents, and
    nothing of the project beyond its slug."""
    login = "/login?" + urllib.parse.urlencode({"next": f"/{slug}"})
    body = (f'<p>{e(tr("landing.people"))}</p><p><a class="btn primary" href="{e(login)}">{e(tr("login.github"))}</a></p>'
            f'<p lang="en" class="dim">{e(AGENT_LINE)}</p>')
    return layout(tr, tr("landing.title", slug=slug), body)


def test_login(tr: Translator, next_path: str) -> tuple[str, int]:
    body = (f'<h2>{e(tr("login.test_heading"))}</h2><p>{e(tr("login.test_hint"))}</p>'
            f'<form class="stack" data-api="/test/login" data-next="{e(next_path)}">'
            f'<label class="field"><span>{e(tr("login.test_field"))}</span><input name="github_login" required autofocus></label>'
            f'<div class="row"><button class="btn primary">{e(tr("login.submit"))}</button> <span class="out" data-out></span></div></form>')
    return layout(tr, tr("login.title"), body)


def join(tr: Translator, person: dict[str, Any], code: str, preview: dict[str, Any]) -> tuple[str, int]:
    p = preview["project"]
    if not preview["usable"]:
        return message(tr, "join.title", tr("join.unusable"), 410, person=person)
    body = f'<p>{e(tr("join.project", name=p["name"]))}</p><p>{e(tr("join.explain"))}</p>'
    if preview["github_login"]:
        body += f'<p class="muted">{e(tr("join.for_login", login=preview["github_login"]))}</p>'
    body += (f'<form data-api="/join/{q(code)}" data-next="/{q(p["slug"])}/members">'
             f'<button class="btn primary">{e(tr("join.button"))}</button> <span class="out" data-out></span></form>')
    return layout(tr, tr("join.title"), body, person)


# The sections of the settings layer, under their small headings: (scope -> ((heading, (section, ...)), ...)).
SETTINGS = {"project": (("set.group.project", ("overview",)), ("set.group.people", ("members", "groups", "invites"))),
            "channel": (("set.group.channel", ("overview", "permissions", "notifications")),),
            "me": (("set.group.me", ("profile", "computers", "writing", "agents")),)}
THEMES = ("dark", "light", "system")
REQUIRED_40, REQUIRED_80 = ' required maxlength="40"', ' required maxlength="80"'
REPO_INPUT = ' type="url" placeholder="https://github.com/owner/name" data-invalid="error.invalid_repo"'


def settings_sections(scope: str, can_invite: bool) -> list[str]:
    """The sections a member may open: every member reads members and groups; invitations are for who may invite."""
    return [x for _, xs in SETTINGS[scope] for x in xs if x != "invites" or can_invite]


def settings(tr: Translator, person: dict[str, Any], frame: dict[str, Any], scope: str, section: str,
             view: dict[str, Any], permissions: list[str], management: Iterable[str],
             channel: dict[str, Any] | None = None, me: dict[str, Any] | None = None) -> tuple[str, int]:
    """Project settings (scope "project"), one channel's settings (scope "channel") and the reader's own settings
    (scope "me", `me`: their name, GitHub login, /api/my, /api/me/computers and /api/me/writer) as one layer in the frame's four cells: the project's name and what is set in the top-left cell, the list of sections (#settings-nav) as the
    second column, the section's title (#settings-title) and the close control (#settings-close, also Escape) in the
    top-right cell, the section as the page. `section` "" is the bare address: the first section. settings.js
    switches sections in place (each has its address), draws members, groups and mutes from the JSON API starting
    from `view` (/api/members), and closes the layer back to the page it was opened from. Groups keep the elements of
    the former members page (#groups, #group-detail, #group-create for who may create groups)."""
    slug = frame["slug"]
    mine = view["me"]["permissions"]
    sections = settings_sections(scope, frame["can_admin"])
    base = {"project": f"/{q(slug)}/settings", "me": f"/{q(slug)}/me"}.get(scope) \
        or channel_settings_href(slug, channel["name"])
    current = section or sections[0]
    nav = []
    for heading, names in SETTINGS[scope]:
        rows = []
        for x in names:
            if x in sections:
                cur = ' aria-current="page"' if x == current else ""
                rows.append(f'<li><a class="place" href="{e(base)}/{x}" data-section="{x}"{cur}>{e(tr("set." + x))}</a></li>')
        nav.append(f'<section class="side-sec"><div class="side-head"><h2>{e(tr(heading))}</h2></div>'
                   f'<ul class="side-list">{"".join(rows)}</ul></section>')
    if scope == "project":
        what, title = tr("set.settings"), tr("set.project_title")
    elif scope == "me":
        what, title = tr("set.me"), tr("set.me_title")
    else:
        what = title = tr("set.channel_title", name=channel["name"])
    parts = {}
    if scope == "me":
        parts.update(_me_sections(tr, slug, me, frame["name"]))
    elif scope == "project":
        parts["overview"] = _project_overview(tr, frame, "project_settings" in mine)
        parts["members"] = (f'<p class="dim">{e(tr("mem.all_hint"))}</p>'
                            f'<div class="set-filter"><input id="members-filter" type="search" placeholder="{e(tr("mem.filter_members"))}" '
                            f'aria-label="{e(tr("mem.filter_members"))}" autocomplete="off" spellcheck="false"></div>'
                            f'<div id="members-table"></div>')
        parts["groups"] = _groups_section(tr, mine, permissions)
        if "invites" in sections:
            # A new invitation (its link shown once, with its copy control), then the unused ones (settings.js).
            parts["invites"] = (f'<p class="dim">{e(tr("admin.invite_hint"))}</p>'
                                f'<form class="stack set-form" id="invite-form"><label class="field">'
                                f'<span>{e(tr("admin.invite_login"))}</span><input name="github_login" maxlength="39" '
                                f'autocomplete="off" spellcheck="false" autocapitalize="off"></label>'
                                f'<div class="row"><button class="btn primary">{e(tr("admin.invite_button"))}</button>'
                                f'<span class="out" aria-live="polite"></span></div>'
                                f'<div id="invite-made" class="panel-result" hidden></div></form>'
                                f'<h3 class="set-sub">{e(tr("admin.unused"))}</h3>'
                                f'<div id="invites-list" class="invites-list"></div>')
    else:
        name = channel["name"]
        can = "manage_channels" in mine
        parts["overview"] = _channel_overview(tr, name, can, channel["notices"])
        parts["permissions"] = (f'<p class="dim">{e(tr("chan.perm.hint"))}</p>'
                                f'<div id="channel-perms" class="chan-perms" data-can="{"1" if can else ""}"></div>')
        boxes = [(tr("msg.mute_me"), "", channel["muted"])]
        boxes += [(tr("msg.mute_agent", name=a), a, a in channel["agent_mutes"]) for a in frame["agents"]]
        rows = "".join(f'<div class="perm-row"><input type="checkbox" id="mute-{i}" data-mute="{e(a)}"{" checked" if on else ""}>'
                       f'<label class="perm-text" for="mute-{i}"><span class="perm-name">{e(label)}</span>'
                       f'<span class="out" aria-live="polite"></span></label></div>'
                       for i, (label, a, on) in enumerate(boxes))
        parts["notifications"] = f'<p class="dim">{e(tr("set.notify_hint"))}</p><div class="perm-list">{rows}</div>'
    # Each section names itself for assistive technology; its title is shown once, in the top-right cell.
    body_secs = "".join(
        f'<section class="set-sec" data-section="{x}" aria-labelledby="set-h-{x}"{"" if x == current else " hidden"}>'
        f'<h2 id="set-h-{x}" class="vh">{e(tr("set." + x))}</h2>{parts[x]}</section>' for x in sections)
    close = e(tr("set.close"))
    data = {"slug": slug, "scope": scope, "section": section, "base": base, "view": view, "catalogue": permissions,
            "management": sorted(management), "switches": list(SWITCHES),
            **({"channel": channel["name"]} if channel else {}),
            **({"my": me["my"], "computers": me["computers"], "writer": me["writer"], "login": me["github_login"],
                "project": frame["name"], "repo": frame["repo"]} if me else {})}
    corner = (f'<p class="corner-title"><span class="corner-name">{e(frame["name"])}</span>'
              f'<span class="corner-word">{e(what)}</span></p>')
    column = (f'<nav id="settings-nav" class="column settings-nav" aria-label="{e(tr("set.sections"))}">'
              f'<div class="side-inner">{"".join(nav)}</div></nav>')
    bar = (f'<h1 id="settings-title" class="bar-title" tabindex="-1">{e(tr("set." + current))}</h1>'
           f'<span class="spacer"></span><div class="settings-close">'
           f'<button type="button" id="settings-close" class="icon-btn" aria-label="{close}" title="{close}" '
           f'aria-keyshortcuts="Escape"><span class="cross" aria-hidden="true"></span></button>'
           f'<span class="esc" aria-hidden="true">{e(tr("set.esc"))}</span></div>')
    body = (f'<div id="settings-layer" class="settings-layer" {_attrs(data)}>'
            f'<div class="settings-body">{body_secs}</div></div>')
    return layout(tr, title, body, person, frame, "settings", page_class="settings-page",
                  scripts=["people.js", "settings.js"] + (["me.js"] if scope == "me" else []),
                  corner=corner, column=column, bar=bar)


def _field(tr: Translator, label_key: str, name: str, value: str, extra: str = "") -> str:
    return (f'<label class="field"><span>{e(tr(label_key))}</span><input name="{e(name)}" value="{e(value)}" '
            f'autocomplete="off" spellcheck="false" autocapitalize="off"{extra}></label>')


def _save_row(tr: Translator, key: str = "set.save") -> str:
    return (f'<div class="row"><button class="btn">{e(tr(key))}</button>'
            f'<span class="out" aria-live="polite"></span></div>')


def _project_overview(tr: Translator, frame: dict[str, Any], can: bool) -> str:
    """The project's name, its repository and where the notices go. For who may change the project's settings each is
    a form (settings.js sends it), and a red "delete project" opens the floating confirmation with the address typed."""
    notice = frame["notice_channel"]
    if not can:
        repo = _repo_link(tr, frame["repo"]) if frame["repo"] else e(tr("set.no_repo"))
        return (f'<dl class="set-facts"><dt>{e(tr("set.name"))}</dt><dd class="set-name">{e(frame["name"])}</dd>'
                f'<dt>{e(tr("set.repo"))}</dt><dd>{repo}</dd>'
                f'<dt>{e(tr("set.notice_channel"))}</dt><dd class="mono">{e(notice)}</dd></dl>'
                f'<p class="dim">{e(tr("set.overview_readonly"))}</p>')
    options = [("#" + c["name"], "#" + c["name"]) for c in frame["places"]["channels"]]
    return (f'<form class="stack set-form" data-project-field="name">'
            f'{_field(tr, "set.name", "name", frame["name"], REQUIRED_80)}{_save_row(tr)}</form>'
            f'<form class="stack set-form" data-project-field="repo">'
            f'{_field(tr, "set.repo", "repo", frame["repo"], REPO_INPUT)}'
            f'<p class="dim">{e(tr("set.repo_hint"))}</p>{_save_row(tr)}</form>'
            f'<form class="stack set-form" data-project-field="notice_channel">'
            f'<div class="field"><span>{e(tr("set.notice_channel"))}</span>'
            f'{dropdown(tr, "notice_channel", options, tr("set.notice_channel"), notice)}</div>'
            f'<p class="dim">{e(tr("set.notice_hint"))}</p>{_save_row(tr)}</form>'
            f'<section class="danger-zone"><h3>{e(tr("set.delete_project"))}</h3>'
            f'<p class="dim">{e(tr("set.delete_project_hint"))}</p>'
            f'<button type="button" class="btn danger" id="project-delete" data-name="{e(frame["name"])}">'
            f'{e(tr("set.delete_project"))}</button></section>')


def _channel_overview(tr: Translator, name: str, can: bool, notices: bool) -> str:
    """A channel's name. For who may manage channels: a form to rename it, and a red "delete channel" (floating
    confirmation), except for the notice channel, which stays until the project chooses another."""
    if not can:
        return (f'<dl class="set-facts"><dt>{e(tr("set.name"))}</dt><dd class="set-name mono">#{e(name)}</dd></dl>'
                f'<p class="dim">{e(tr("set.channel_readonly"))}</p>')
    gone = (f'<p class="dim">{e(tr("chan.delete_notice"))}</p>' if notices else
            f'<p class="dim">{e(tr("chan.delete_hint"))}</p>'
            f'<button type="button" class="btn danger" id="channel-delete">{e(tr("chan.delete"))}</button>')
    return (f'<form class="stack set-form" id="channel-rename">'
            f'{_field(tr, "set.name", "name", name, REQUIRED_40)}'
            f'<p class="dim">{e(tr("chan.rename_hint"))}</p>{_save_row(tr, "chan.rename")}</form>'
            f'<section class="danger-zone"><h3>{e(tr("chan.delete"))}</h3>{gone}</section>')


def _me_sections(tr: Translator, slug: str, me: dict[str, Any], project: str) -> dict[str, str]:
    """The reader's own settings: their name and avatar in this project (#me-avatar, drawn by me.js), their GitHub
    account as a fact, the language and the look of the pages (profile); their computers and connectors (me.js draws
    them from /api/my and /api/me/computers); who writes their changes to the shared files, the server with their
    GitHub authorization or one of their computers (writing: me.js, from /api/me/writer, /api/me/computers and
    can-write); what others may do with their agents (the four permissions of their own agent group, each saved as it
    changes)."""
    langs = "".join(f'<button type="button" class="seg-btn" data-locale="{e(loc)}" lang="{e(loc)}" '
                    f'aria-pressed="{"true" if loc == tr.locale else "false"}">{e(tr("me.lang." + loc))}</button>'
                    for loc in ("zh-TW", "en"))
    themes = "".join(f'<button type="button" class="seg-btn" data-theme-choice="{x}" aria-pressed="false">'
                     f'{e(tr("me.theme." + x))}</button>' for x in THEMES)
    profile = (f'<form class="stack set-form" id="me-name">'
               f'{_field(tr, "me.name", "name", me["name"], REQUIRED_40)}'
               f'<p class="dim">{e(tr("me.name_hint"))}</p>{_save_row(tr)}</form>'
               f'<dl class="set-facts"><dt>{e(tr("me.github"))}</dt><dd class="mono">{e(me["github_login"])}</dd></dl>'
               f'<h3 class="set-sub">{e(tr("me.avatar"))}</h3>'
               f'<div id="me-avatar" class="avatar-set"></div><p class="dim">{e(tr("me.avatar_hint"))}</p>'
               f'<h3 class="set-sub">{e(tr("me.lang"))}</h3>'
               f'<div class="seg" role="group" id="me-locale" aria-label="{e(tr("me.lang"))}">{langs}</div>'
               f'<p class="out" id="me-locale-out" aria-live="polite"></p>'
               f'<h3 class="set-sub">{e(tr("me.theme"))}</h3>'
               f'<div class="seg" role="group" id="me-theme" aria-label="{e(tr("me.theme"))}">{themes}</div>')
    sw = me["my"]["switches"]
    rows = "".join(f'<div class="perm-row"><input type="checkbox" id="me-sw-{k}" data-switch="{k}"{" checked" if sw.get(k) else ""}>'
                   f'<label class="perm-text" for="me-sw-{k}"><span class="perm-name">{e(tr("switch." + k))}</span>'
                   f'<span class="perm-hint">{e(tr("perm_hint." + k))}</span><span class="out" aria-live="polite"></span>'
                   f'</label></div>' for k in SWITCHES)
    agents = (f'<p class="dim">{e(tr("my.switches_hint"))}</p><div class="perm-list" id="me-switches">{rows}</div>'
              f'<p><a href="/{e(q(slug))}/settings/groups?g={e(q(me["name"] + "-agents"))}">{e(tr("ag.group_settings"))}</a></p>')
    computers = (f'<p class="dim my-lead">{e(tr("my.lead", project=project))}</p>'
                 f'<p class="my-stale" id="me-stale" role="status" hidden>{e(tr("my.stale"))}</p>'
                 f'<div id="me-computers"></div>')
    writing = (f'<p class="dim my-lead">{e(tr("wr.lead"))}</p>'
               f'<div id="me-writing"></div>')
    return {"profile": profile, "computers": computers, "writing": writing, "agents": agents}


def _groups_section(tr: Translator, mine: list[str], permissions: list[str]) -> str:
    """Groups, as a list with a filter and "new group" (#groups); a chosen group (?g= in the address) is drawn in
    #group-detail, with the list as a middle column. The form to make a group (#group-create, in a floating panel so
    nothing under it moves) is here only for a person who may manage groups, offering only what they hold."""
    can_make = "manage_groups" in mine
    plus = create = ""
    if can_make:
        plus = (f'<button type="button" id="group-create-open" class="btn" aria-controls="group-create" '
                f'aria-expanded="false"><span class="plus" aria-hidden="true"></span>{e(tr("mem.new_group"))}</button>')
        boxes = "".join(
            f'<label class="perm-row"><input type="checkbox" name="perm" value="{e(p)}">'
            f'<span class="perm-text"><span class="perm-name">{e(tr("perm." + p))}</span>'
            f'<span class="perm-hint">{e(tr("perm_hint." + p))}</span></span></label>'
            for p in permissions if p in mine)
        close = e(tr("pm.close"))
        create = (f'<dialog id="group-create-panel" class="panel" closedby="any" aria-labelledby="group-create-title">'
                  f'<div class="panel-head"><h2 id="group-create-title" class="panel-title">{e(tr("mem.new_group"))}</h2>'
                  f'<button type="button" class="icon-btn" data-close aria-label="{close}" title="{close}">'
                  f'<span class="cross" aria-hidden="true"></span></button></div>'
                  f'<form id="group-create" class="panel-body group-create">'
                  f'<label class="field"><span>{e(tr("mem.create_name"))}</span><input name="name" required maxlength="40" '
                  f'autocomplete="off" spellcheck="false" autocapitalize="off"></label>'
                  f'<fieldset class="perm-set"><legend>{e(tr("mem.create_perms"))}</legend>{boxes}</fieldset>'
                  f'<div class="row form-acts"><span class="out" data-out aria-live="polite"></span>'
                  f'<button type="button" class="btn" data-dismiss>{e(tr("mem.cancel"))}</button>'
                  f'<button class="btn primary">{e(tr("mem.create"))}</button></div></form></dialog>')
    label = e(tr("mem.filter"))
    return (f'<div id="groups-root" class="groups-page">'
            f'<nav id="groups" class="groups-list" aria-label="{e(tr("mem.list_label"))}"><div class="groups-head">'
            f'<input id="groups-filter" type="search" placeholder="{label}" aria-label="{label}" autocomplete="off" '
            f'spellcheck="false">{plus}</div><div id="groups-body"></div></nav>'
            f'<div class="group-main"><section id="group-detail" class="group-detail" tabindex="-1"></section></div>'
            f'</div>{create}')


def switch_boxes(tr: Translator, values: dict[str, bool]) -> str:
    """The four switches of the consent page, sent with its form."""
    return "".join(f'<div class="check"><label><input type="checkbox" name="{k}" value="1"{" checked" if values.get(k) else ""}>'
                   f' {e(tr("switch." + k))}</label></div>' for k in SWITCHES)


def consent(tr: Translator, person: dict[str, Any], client_name: str, host: str, project_name: str,
            params: dict[str, str], switches: dict[str, bool]) -> tuple[str, int]:
    hidden = "".join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k, v in params.items()
                     if k not in ("decision", "switches", *SWITCHES))
    body = (f'<p>{e(tr("consent.ask", client=client_name, project=project_name, host=host))}</p>'
            f'<form method="post" action="/oauth/authorize">{hidden}<input type="hidden" name="switches" value="1">'
            f'<h2>{e(tr("my.switches"))}</h2><p class="muted">{e(tr("my.switches_hint"))}</p>'
            f'{switch_boxes(tr, switches)}'
            f'<p class="row"><button class="btn primary" name="decision" value="approve">{e(tr("consent.approve"))}</button> '
            f'<button class="btn" name="decision" value="deny">{e(tr("consent.deny"))}</button></p></form>')
    return layout(tr, tr("consent.title"), body, person)


def _tool(tr: Translator, ident: str, icon: str, label_key: str, attrs: str, inner: str = "") -> str:
    """An icon button of the channel bar: its name for screen readers and as its tooltip."""
    label = e(tr(label_key))
    return (f'<button type="button" id="{ident}" class="icon-btn tool" aria-label="{label}" title="{label}" {attrs}>'
            f'{glyph(icon)}{inner}</button>')


def _send_button(tr: Translator) -> str:
    """The composer's send control (1y): an upward arrow in a filled circle at the right end of the field, named for
    screen readers; dim and disabled while the field is empty (the page script turns it on)."""
    label = e(tr("msg.send"))
    return (f'<button type="submit" class="send-icon" aria-label="{label}" title="{label}" disabled>'
            f'{glyph("send", 18)}</button>')


def messages(tr: Translator, person: dict[str, Any], frame: dict[str, Any], view: dict[str, Any],
             dm: str | None = None, refused: tuple[str, int] | None = None) -> tuple[str, int]:
    """Chat (`dm` None) and private messages (`dm` the other member's name, "" for none chosen yet): the project menu
    in the top-left cell, the channels or the conversations under it, the place's name (which opens its settings or
    the other member's card), the member list toggle and the search icon in the top-right cell, the chosen place in
    the middle, and the right column showing one thing at a time (the member list with each agent's tasks, or
    search). The second column's lists are the frame's (frame.js); the page scripts keep the rest current through the
    JSON API (messages.js, tasks.js, people.js, search.js; right.js decides what the right column shows). What the
    scripts need is in data- attributes. `refused` (a sentence and a status): a private conversation that cannot be
    had, answered in the same frame with the sentence in the place of the conversation and nothing to write with."""
    if refused is not None:
        said, status = refused
        bar = f'<h1 class="place-title"><span class="place-btn mono">{e(dm)}</span></h1><span class="spacer"></span>'
        body = f'<section class="room room-refused"><p class="refused-note" role="alert">{e(said)}</p></section>'
        return layout(tr, tr("dm.title"), body, person, frame, "dm", status=status, page_class="room-page",
                      corner=_project_button(tr, frame), column=_dm_side(tr, frame), bar=bar)
    data = {"slug": frame["slug"], "me": person["name"], "mode": "chat" if dm is None else "dm",
            "place": dm or "", "can-edit-tasks": "1" if view["can_edit_tasks"] else "",
            "can-manage-channels": "1" if view.get("can_manage_channels") else ""}
    room = (f'<div id="chat" class="room" {_attrs(data)}>'
            f'<div id="scroller" class="scroller"><div class="older-row"><button type="button" id="older" class="btn quiet" hidden>'
            f'{e(tr("msg.older"))}</button></div>'
            f'<ol id="messages" class="messages" aria-live="polite"></ol></div>'
            f'<form id="composer" class="composer"><div id="reply-target" class="reply-target" hidden><span></span>'
            f'<button type="button" id="reply-cancel" class="quiet-btn">{e(tr("msg.reply_cancel"))}</button></div>'
            f'<div class="composer-box"><textarea id="text" rows="1" maxlength="4000" aria-label="{e(tr("msg.input_label"))}" '
            f'placeholder="{e(tr("msg.input_hint"))}"></textarea>'
            f'{_send_button(tr)}</div>'
            f'<div class="out composer-out" id="composer-out" aria-live="polite"></div></form></div>')
    sides = "".join(f'<button type="button" class="seg-btn" data-side="{k}" aria-pressed="{"true" if k == "people" else "false"}">'
                    f'{e(tr("people.side_" + k))}</button>' for k in ("people", "agents"))
    close = e(tr("people.close"))
    people = (f'<aside id="member-panel" class="right-panel" aria-label="{e(tr("bar.members"))}" hidden>'
              f'<div class="right-head"><div id="member-switch" class="seg" role="group" '
              f'aria-label="{e(tr("people.switch"))}">{sides}</div><span class="spacer"></span>'
              f'<button type="button" class="icon-btn right-close" aria-label="{close}" title="{close}">'
              f'<span class="cross" aria-hidden="true"></span></button></div>'
              f'<div id="member-body" class="right-body member-body"></div></aside>')
    search, clear = e(tr("srch.label")), e(tr("srch.close"))
    found = (f'<aside id="search-results" class="right-panel" aria-label="{search}" hidden>'
             f'<div class="right-head"><div class="search-box" role="search">{glyph("search", 16)}'
             f'<span id="search-chip" class="search-chip" hidden><span class="search-chip-text"></span>'
             f'<button type="button" id="search-chip-x" class="chip-x"><span class="cross" aria-hidden="true"></span></button></span>'
             f'<input id="search-input" type="search" placeholder="{e(tr("srch.placeholder"))}" aria-label="{search}" '
             f'role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="search-suggest" '
             f'autocomplete="off" spellcheck="false" autocapitalize="off" maxlength="300">'
             f'<ul id="search-suggest" class="search-suggest" role="listbox" aria-label="{e(tr("srch.suggest"))}" hidden></ul>'
             f'</div><button type="button" class="icon-btn search-close" aria-label="{clear}" title="{clear}">'
             f'<span class="cross" aria-hidden="true"></span></button></div>'
             f'<p id="search-summary" class="right-summary"></p>'
             f'<div id="search-body" class="right-body search-body" aria-live="polite"></div></aside>')
    title = tr("msg.title") if dm is None else tr("dm.title")
    return layout(tr, title, room + people + found, person, frame, "messages" if dm is None else "dm",
                  page_class="room-page", corner=_project_button(tr, frame),
                  column=_side(tr, frame) if dm is None else _dm_side(tr, frame), bar=_chat_bar(tr),
                  styles=["vendor/katex/katex.min.css"],
                  scripts=["vendor/marked/marked.min.js", "vendor/dompurify/purify.min.js", "vendor/katex/katex.min.js",
                           "render.js", "paths.js", "right.js", "tasks.js", "people.js", "emoji.js", "messages.js",
                           "search.js"])


VIEWS = (("rendered", "files.view_rendered"), ("source", "files.view_source"), ("split", "files.view_split"))


def files(tr: Translator, person: dict[str, Any], frame: dict[str, Any], path: str, max_bytes: int) -> tuple[str, int]:
    """Files mode: the repository's files and a local folder's, using the whole page. A shell: the source in the
    top-left cell, the explorer (the second column), the tab strip with "open PDF" (a .tex file's), edit and the view switch
    in the top-right cell and the document are drawn by explorer.js and viewer.js, from the files API (repo.js) and from the reader's own folder in
    the browser (local.js; nothing of it reaches the server). `path` is the file the address names ("" for none);
    `max_bytes`: a larger file is not shown here (the server does not fetch it)."""
    data = {"slug": frame["slug"], "path": path, "repo": frame["repo"],
            "can-manage": "1" if frame["can_admin"] else "", "max-bytes": str(max_bytes)}
    views = "".join(f'<button type="button" class="icon-btn" data-view="{v}" aria-pressed="false" aria-label="{e(tr(k))}" '
                    f'title="{e(tr(k))}">{glyph(v)}</button>' for v, k in VIEWS)
    github, save = e(tr("files.github")), e(tr("files.save"))
    # Edit (a reader who may save in their own GitHub name) with save beside it (also a local file's), or, when saving
    # needs their authorization or their writing computer, a quiet link to that section of their settings: viewer.js
    # shows them for the file shown.
    bar = (f'<h1 class="vh">{e(tr("files.title"))}</h1>'
           f'<div id="file-tabs" class="file-tabs" role="tablist" aria-label="{e(tr("files.tabs"))}"></div>'
           f'<div class="file-tools" role="group" aria-label="{e(tr("files.tools"))}">'
           f'<button type="button" id="file-pdf" class="btn file-pdf" hidden>{e(tr("files.open_pdf"))}</button>'
           f'<button type="button" id="file-edit" class="btn file-word file-edit" aria-pressed="false" '
           f'title="{e(tr("files.edit_title"))}" hidden>{e(tr("files.edit"))}</button>'
           f'<button type="button" id="file-save" class="icon-btn file-save" aria-label="{save}" title="{save}" '
           f'aria-keyshortcuts="Control+S Meta+S" aria-disabled="true" hidden>{glyph("save")}</button>'
           f'<a id="file-auth" class="file-auth" href="/{e(q(frame["slug"]))}/me/writing" '
           f'title="{e(tr("files.need_auth_title"))}" hidden>{e(tr("files.need_auth"))}</a>'
           f'<div id="view-switch" class="view-switch" role="group" aria-label="{e(tr("files.view"))}">{views}</div>'
           f'<a id="file-github" class="icon-btn" aria-label="{github}" title="{github}" target="_blank" '
           f'rel="noopener noreferrer" aria-disabled="true">{glyph("github")}</a></div>')
    body = (f'<section id="files" class="files" {_attrs(data)}>'
            f'<div id="file-view" class="file-view" role="tabpanel" tabindex="-1" aria-label="{e(tr("files.title"))}"></div>'
            f'</section>')
    return layout(tr, tr("files.title"), body, person, frame, "files", page_class="files-page",
                  corner=_source_button(tr), column=_explorer(tr, frame), bar=bar,
                  styles=["vendor/katex/katex.min.css"],
                  scripts=["vendor/marked/marked.min.js", "vendor/dompurify/purify.min.js", "vendor/katex/katex.min.js",
                           "vendor/codemirror/codemirror.min.js", "render.js", "paths.js", "highlight.js", "editor.js",
                           "repo.js", "local.js", "explorer.js", "viewer.js"])


def _action(tr: Translator, ident: str, label_key: str, attrs: str) -> str:
    """The one action of a page's top-right cell, at its right (a round icon button with its name as label and
    tooltip below 900 px)."""
    label = e(tr(label_key))
    return (f'<button type="button" id="{ident}" class="btn ag-action" aria-label="{label}" title="{label}" {attrs}>'
            f'<span class="plus" aria-hidden="true"></span><span class="ag-action-word">{label}</span></button>')


def agent(tr: Translator, person: dict[str, Any], frame: dict[str, Any]) -> tuple[str, int]:
    """The agent page (m1f6_contract.md section 10), in the frame's four cells: the project menu top left; every agent
    of the project in the second column (#agent-list), by group; top right the chosen
    agent (#agent-head: name, kind, owner, model, presence) with its person's acts (#agent-acts) and "invite agent";
    the page is the chosen agent's timeline (#agent-timeline: its messages and changes of state, newest at the
    bottom; #tl-filter: what concerns it, or everything), with a composer (#tl-composer) that its own person writes to
    it with. agentpage.js draws all of it from
    the members (frame.js) and the timeline (/api/agents/{name}/timeline); the chosen agent is the address's query."""
    slug, mine = frame["slug"], set(frame["perms"])
    column = (f'<nav id="agent-side" class="column agent-side" aria-label="{e(tr("agp.list"))}"><div class="side-inner">'
              f'<div id="agent-list" class="agent-list"></div></div></nav>')
    invite = ""
    if "manage_own_agents" in mine:
        invite = _action(tr, "invite-agent", "ag.invite", 'data-act="invite-agent" aria-haspopup="dialog"')
    bar = (f'<h1 id="agent-head" class="agent-head"></h1><span class="spacer"></span>'
           f'<div id="agent-acts" class="agent-acts" role="group" aria-label="{e(tr("agp.acts"))}"></div>{invite}')
    data = {"slug": slug, "me": person["name"]}
    filters = "".join(f'<button type="button" class="seg-btn" data-filter="{k}" '
                      f'aria-pressed="{"true" if k == "concerns" else "false"}">{e(tr("agp.filter." + k))}</button>'
                      for k in ("concerns", "all"))
    body = (f'<section id="agent-timeline" class="room timeline" aria-label="{e(tr("agp.timeline"))}" {_attrs(data)}>'
            f'<div id="tl-filter" class="seg tl-filter" role="group" aria-label="{e(tr("agp.filter"))}">{filters}</div>'
            f'<div id="tl-scroller" class="scroller"><p id="tl-older" class="tl-note" hidden></p>'
            f'<ol id="tl-list" class="messages" aria-live="polite"></ol></div>'
            f'<form id="tl-composer" class="composer" hidden><div class="composer-box">'
            f'<textarea id="tl-text" rows="1" maxlength="4000" aria-label="{e(tr("agp.input_label"))}"></textarea>'
            f'{_send_button(tr)}</div>'
            f'<div class="out composer-out" id="tl-out" aria-live="polite"></div></form></section>')
    return layout(tr, tr("agp.title"), body, person, frame, "agent", page_class="room-page agent-room",
                  corner=_project_button(tr, frame), column=column, bar=bar,
                  styles=["vendor/katex/katex.min.css"],
                  scripts=["vendor/marked/marked.min.js", "vendor/dompurify/purify.min.js", "vendor/katex/katex.min.js",
                           "render.js", "paths.js", "people.js", "agentpage.js"])


# The work page's tabs: (tab, its address under /{slug}/work, its word).
WORK_TABS = (("tasks", "", "ag.tab.tasks"), ("schedules", "/schedules", "ag.tab.schedules"))


def work(tr: Translator, person: dict[str, Any], frame: dict[str, Any], tab: str, view: dict[str, Any]) -> tuple[str, int]:
    """The work page (m1f6_contract.md section 11; the tabs as m1f5_agent_page_design.md built them): the task table
    and the scheduled messages as two tabs at their own addresses, in the frame's four cells: the project menu top
    left, the current tab's scopes as the second column (#work-side, drawn by workpage.js), the tabs (#work-tabs) and
    the tab's one action top right, the tab's list as the page. Each tab is drawn from the JSON API by its script
    (tasktable.js, schedules.js); the form for a new schedule (#schedule-form) is in the page only for who may create
    one."""
    slug = frame["slug"]
    base = f"/{q(slug)}/work"
    tabs = []
    for k, path, key in WORK_TABS:
        cur = ' aria-selected="true" aria-current="page"' if k == tab else ' aria-selected="false"'
        tabs.append(f'<a class="ag-tab" role="tab" href="{e(base + path)}" data-tab="{k}"{cur}>{e(tr(key))}</a>')
    action = ""
    if tab == "tasks" and view["can_edit_tasks"]:
        action = _action(tr, "task-new", "tt.post_task", 'aria-expanded="false"')
    elif tab == "schedules" and view["can_create"]:
        action = _action(tr, "schedule-new", "sch.new", 'aria-expanded="false" aria-controls="schedule-form"')
    bar = (f'<nav id="work-tabs" class="ag-tabs" role="tablist" aria-label="{e(tr("ag.tabs"))}">{"".join(tabs)}</nav>'
           f'<span class="spacer"></span>{action}')
    column = (f'<nav id="work-side" class="column agent-side" aria-label="{e(tr("ag.scopes"))}">'
              f'<div id="work-scopes" class="side-inner"></div></nav>')
    data = {"slug": slug, "me": person["name"], "tab": tab, "can-edit-tasks": "1" if view["can_edit_tasks"] else "",
            "can-manage": "1" if view["can_manage"] else "", "can-create": "1" if view["can_create"] else ""}
    styles: list[str] = []
    if tab == "tasks":
        content = '<div id="task-table" class="ag-view"></div>'
        # A task's body is Markdown with mathematics (render.js), as a message.
        styles = ["vendor/katex/katex.min.css"]
        scripts = ["vendor/marked/marked.min.js", "vendor/dompurify/purify.min.js", "vendor/katex/katex.min.js",
                   "render.js", "people.js", "tasks.js", "workpage.js", "tasktable.js"]
    else:
        data.update({"places": view["places"], "min-every": view["min_every_s"]})
        form = '<form id="schedule-form" class="ag-form sch-form" hidden></form>' if view["can_create"] else ""
        content = f'{form}<div id="schedules" class="ag-view"></div>'
        scripts = ["workpage.js", "schedules.js"]
    # Below 900 px the scope is out of sight in the drawer: the page starts with one line naming it, which opens it.
    body = (f'<div id="work-page" class="agent-page" {_attrs(data)}>'
            f'<div class="ag-read"><button type="button" id="scope-line" class="scope-line" aria-controls="nav" '
            f'aria-label="{e(tr("ag.scope_open"))}" hidden></button>{content}</div></div>')
    title = tr("ag.tab." + tab)
    return layout(tr, title, body, person, frame, "work", page_class="agent-main", corner=_project_button(tr, frame),
                  column=column, bar=bar, styles=styles, scripts=scripts)
