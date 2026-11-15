"""Server-rendered pages. Every text comes from the message catalogue (tr), every value is escaped.

Forms marked data-api are sent as JSON by /static/app.js to the same JSON API that scripts use, so a
page does nothing the API does not; the OAuth consent form is a plain form because it ends in a redirect.

The look is DESIGN.md's: one stylesheet (/static/app.css) and no styles in the page. A page of a project sits in
the project's frame: the rail (#rail, rail.js) on the far left, then the mode's second column (the channels #side in
chat, kept current by frame.js; the explorer #explorer in files), then the page; the other pages are a simple centred
column.
"""
from __future__ import annotations

import base64
import hashlib
import json
import urllib.parse
from html import escape
from typing import Any, Iterable

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
    "pin": '<path d="M9 4h6l-1 5.5 3 2.5v2H7v-2l3-2.5z"/><path d="M12 14v6"/>',
    "tasks": '<path d="M10 6h10M10 12h10M10 18h10"/><path d="M4 6l1.5 1.5L8 5M4 12l1.5 1.5L8 11M4 18l1.5 1.5L8 17"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1'
            'M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
}

# The glyphs the page scripts draw (A.glyph clones them from this template).
SCRIPT_GLYPHS = ("gear",)


def glyph(name: str, size: int = 20, extra: str = "") -> str:
    return (f'<svg class="glyph" aria-hidden="true" focusable="false" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"{extra}>'
            f'{GLYPHS[name]}</svg>')


def _glyph_set() -> str:
    return ('<template id="glyphs">' + "".join(glyph(n, 16, f' data-glyph="{n}"') for n in SCRIPT_GLYPHS)
            + '</template>')


def fold_button(tr: Translator, mode: str, target: str, label_key: str, button_id: str) -> str:
    """Folds the mode's second column away on a wide screen and brings it back (rail.js); remembered per mode."""
    label = e(tr(label_key))
    return (f'<button type="button" id="{button_id}" class="icon-btn fold-btn" data-fold="{mode}" aria-controls="{target}" '
            f'aria-expanded="true" aria-label="{label}" title="{label}">{glyph("column")}</button>')


def layout(tr: Translator, title: str, body: str, person: dict[str, Any] | None = None,
           frame: dict[str, Any] | None = None, here: str = "", status: int = 200,
           styles: Iterable[str] = (), scripts: Iterable[str] = (), header: str | None = None,
           page_class: str = "") -> tuple[str, int]:
    """A page. With `frame` (a page of a project) it sits in the project's frame, `here` naming the current page of
    the navigation; without, in a simple centred column. `styles` and `scripts`: further files under /static; the
    scripts load after base.js (and frame.js) and before app.js. `header`: the page's own header instead of its title."""
    msgs = e(json.dumps(tr.js_messages(), ensure_ascii=False))
    links = "".join(f'<link rel="stylesheet" href="/static/{e(x)}">' for x in styles)
    shared = ["base.js"] + (["frame.js", "rail.js", "project.js"] if frame else [])
    tags = "".join(f'<script src="/static/{e(x)}"></script>' for x in [*shared, *scripts, "app.js"])
    if frame:
        head = header if header is not None else (
            f'<header class="page-head">{open_button(tr)}<h1 class="page-title">{e(title)}</h1></header>')
        # The second column belongs to the mode: the channels in chat, the explorer in files, none elsewhere.
        column = (_side(tr, person, frame) if here == "messages" else _explorer(tr, frame) if here == "files" else "")
        mode = {"messages": "chat", "files": "files"}.get(here, "page")
        main = (f'<div class="shell mode-{mode}{" has-column" if column else ""}">'
                f'<div id="nav" class="nav" aria-label="{e(tr("nav.label"))}">{_rail(tr, person, frame, here)}{column}</div>'
                f'<div id="side-scrim" hidden></div>'
                f'<main id="page" class="page {e(page_class)}">{head}{body}</main></div>{_glyph_set()}')
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
            f'<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">'
            f'<link rel="stylesheet" href="/static/app.css">{links}'
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


def _place_link(tr: Translator, slug: str, place: str, inner: str, unread: int, important: int, muted: bool) -> str:
    """One place of the navigation; frame.js redraws the lists with the same markup. A channel's row also has a
    gear to its settings (shown on hover and focus)."""
    cls = "place" + (" unread" if unread and not muted else "") + (" muted" if muted else "")
    gear = ""
    if place.startswith("#"):
        label = e(tr("chan.gear", place=place))
        gear = (f'<a class="place-gear" href="{e(channel_settings_href(slug, place[1:]))}" aria-label="{label}" '
                f'title="{label}">{glyph("gear", 16)}</a>')
    return (f'<li class="place-row"><a class="{cls}" href="/{e(q(slug))}#{e(q(place))}" data-place="{e(place)}">{inner}'
            f'{_count(tr, unread, important, muted)}</a>{gear}</li>')


def presence_mark(tr: Translator, who: dict[str, Any] | None) -> str:
    """Shape says who, fill says state: a square for a person, a disc for an agent, filled when it is online."""
    if not who or who.get("kind") != "agent":
        return f'<span class="presence person" role="img" aria-label="{e(tr("presence.person"))}"></span>'
    on = bool(who.get("online"))
    return (f'<span class="presence agent{" on" if on else ""}" role="img" '
            f'aria-label="{e(tr("presence.online" if on else "presence.offline"))}"></span>')


def _reveal(tr: Translator, target: str, label_key: str) -> str:
    return (f'<button type="button" class="icon-btn small" data-reveal="{target}" aria-expanded="false" '
            f'aria-controls="{target}" aria-label="{e(tr(label_key))}"><span class="plus" aria-hidden="true"></span></button>')


def _menu_item(tr: Translator, label_key: str, act: str = "", href: str = "") -> str:
    """An item of a menu drawn here (the markup of base.js's menus): a destination, or an act for project.js."""
    if href:
        return f'<a class="menu-item" role="menuitem" tabindex="-1" href="{e(href)}">{e(tr(label_key))}</a>'
    return (f'<button type="button" class="menu-item" role="menuitem" tabindex="-1" data-act="{act}">'
            f'{e(tr(label_key))}</button>')


def _project_head(tr: Translator, f: dict[str, Any], under: str) -> str:
    """The top of a second column: the project's name (display voice) as the button of the project menu, a mono
    line under it, and beside it the invitation of people for who may invite. The menu offers each item only to
    who may use it; project.js opens it and does its acts."""
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
    items.append(_menu_item(tr, "pm.my", href=f"/{q(slug)}/my"))
    invite = ""
    if f["can_admin"]:
        label = e(tr("pm.invite_icon"))
        invite = (f'<button type="button" id="invite-open" class="icon-btn small invite-open" data-act="invite-people" '
                  f'aria-label="{label}" title="{label}">{glyph("invite", 18)}</button>')
    return (f'<div class="side-project"><div class="project-text">'
            f'<button type="button" id="project-menu-button" class="project-name" aria-haspopup="menu" '
            f'aria-expanded="false" aria-controls="project-menu" title="{e(tr("pm.open"))}">'
            f'<span class="project-name-text">{e(f["name"])}</span>{glyph("chevron", 16)}</button>{under}</div>{invite}'
            f'<div id="project-menu" class="menu" role="menu" aria-label="{e(tr("pm.open"))}" tabindex="-1" popover="manual">'
            f'{"".join(items)}</div></div>')


def _repo_link(tr: Translator, repo: str) -> str:
    return (f'<a class="project-repo" href="{e(repo)}" target="_blank" rel="noopener noreferrer" '
            f'title="{e(tr("nav.repo"))}">{e(_repo_text(repo))}</a>')


# The rail's buttons in their order: (page, glyph, word, full name). Members, groups and the project's settings are
# reached from the project menu.
RAIL = (("messages", "chat", "rail.chat", "nav.messages"), ("files", "files", "rail.files", "nav.files"),
        ("schedules", "schedules", "rail.schedules", "nav.schedules"), ("my", "my", "rail.my", "nav.my"))


def _rail(tr: Translator, person: Any, f: dict[str, Any], here: str) -> str:
    """The fixed rail on the far left of every page of a project: the top-level buttons, then the theme switch and
    the reader. rail.js keeps the count of important messages on the chat button and where each mode last was."""
    slug, me = f["slug"], (person["name"] if person else "")
    items = []
    for page, icon, word, full in RAIL:
        href = f"/{q(slug)}" if page == "messages" else f"/{q(slug)}/{page}"
        ident = {"messages": ' id="rail-chat"', "files": ' id="rail-files"'}.get(page, "")
        current = ' aria-current="page"' if page == here else ""
        count = ""
        if page == "messages":
            k = f["important"] if here != "messages" else 0
            count = (f'<span id="rail-count" class="rail-count"{"" if k else " hidden"}>'
                     f'<span class="pill" aria-hidden="true">{e(k)}</span>'
                     f'<span class="vh">{e(tr("rail.important", k=k))}</span></span>')
        items.append(f'<li><a{ident} class="rail-btn" href="{e(href)}" title="{e(tr(full))}"{current}>'
                     f'<span class="rail-tile">{glyph(icon)}{count}</span><span class="rail-word">{e(tr(word))}</span></a></li>')
    data = {"slug": slug, "me": me, "here": here, "directory": f["directory"], "repo": f["repo"], "perms": f["perms"]}
    initial = (me[:1] or "?").upper()
    reader = (f'<button type="button" id="rail-me" class="rail-me" popovertarget="me-menu" '
              f'aria-label="{e(tr("rail.me", name=me))}" title="{e(me)}"><span aria-hidden="true">{e(initial)}</span></button>'
              f'<div id="me-menu" class="me-menu" popover><p class="me-name">{e(me)}</p>'
              f'<a class="me-row" href="/">{e(tr("rail.home"))}</a>'
              f'<form method="post" action="/logout"><button class="me-row">{e(tr("nav.logout"))}</button></form></div>')
    return (f'<nav id="rail" class="rail" aria-label="{e(tr("rail.label"))}" {_attrs(data)}>'
            f'<button type="button" id="side-close" class="icon-btn nav-close" aria-label="{e(tr("nav.close"))}">'
            f'<span class="cross" aria-hidden="true"></span></button>'
            f'<ul class="rail-list">{"".join(items)}</ul>'
            f'<div class="rail-foot">{_theme_button(tr)}{reader}</div></nav>')


def _side(tr: Translator, person: Any, f: dict[str, Any]) -> str:
    """Chat's second column: the project, its channels and the private conversations (frame.js keeps them current)."""
    slug, me = f["slug"], (person["name"] if person else "")
    places, directory = f["places"], f["directory"]
    channels = "".join(
        _place_link(tr, slug, "#" + c["name"], f'<span class="place-name">#{e(c["name"])}</span>'
                    + (f'<span class="note">{e(tr("nav.muted"))}</span>' if c["muted"] else ""),
                    c["unread"], c["important"], c["muted"]) for c in places["channels"])
    private = []
    for p in places["private"]:
        who = directory.get(p["with"])
        agent = bool(who and who.get("kind") == "agent")
        note = (f'<span class="note">{e(tr("nav.my_agent"))}</span>' if agent and who.get("owner") == me else "")
        if agent and who.get("busy"):
            note += f'<span class="note">{e(tr("nav.busy"))}</span>'
        private.append(_place_link(tr, slug, p["with"],
                                   f'{presence_mark(tr, who)}<span class="place-name">{e(p["with"])}</span>{note}',
                                   p["unread"], p["important"], False))
    start = plus_channel = plus_private = ""
    if f["can_create"]:            # the same floating form as the project menu's "create channel" (project.js)
        label = e(tr("nav.new_channel"))
        plus_channel = (f'<button type="button" class="icon-btn small" data-act="new-channel" aria-label="{label}" '
                        f'title="{label}"><span class="plus" aria-hidden="true"></span></button>')
    options = "".join(f'<option value="{e(n)}">{e(n)}</option>' for n in f["people"])
    options += "".join(f'<option value="{e(n)}">{e(tr("msg.my_agent", name=n))}</option>' for n in f["agents"])
    if options:
        plus_private = _reveal(tr, "new-private", "nav.start_private")
        start = (f'<form id="new-private" class="side-form" hidden><select name="with" aria-label="{e(tr("msg.choose_member"))}">'
                 f'{options}</select><div class="row"><button class="btn primary">{e(tr("msg.start_private"))}</button>'
                 f'<button type="button" class="btn" data-dismiss>{e(tr("nav.cancel"))}</button></div></form>')
    return (f'<nav id="side" class="column" aria-label="{e(tr("nav.places"))}"><div class="side-inner">'
            f'{_project_head(tr, f, _repo_link(tr, f["repo"]))}'
            f'<section class="side-sec"><div class="side-head"><h2>{e(tr("msg.channels"))}</h2>{plus_channel}</div>'
            f'<ul id="side-channels" class="side-list">{channels}</ul></section>'
            f'<section class="side-sec"><div class="side-head"><h2>{e(tr("msg.private"))}</h2>{plus_private}</div>'
            f'{start}<ul id="side-private" class="side-list">{"".join(private)}</ul></section>'
            f'</div></nav>')


def _explorer(tr: Translator, f: dict[str, Any]) -> str:
    """Files' second column: the repository and its branch, the two sources (the repository, a local folder), the
    local folder's controls, a filter, the tree (explorer.js draws it, local.js reads the folder). Nothing of a local
    folder is ever known here: its name is filled in by the page script."""
    ref = f'<span id="explorer-ref" class="project-repo">{e(_repo_text(f["repo"]))}</span>'
    label = e(tr("files.filter"))
    sources = "".join(f'<button type="button" class="source-btn" data-source="{s}" aria-pressed="{"true" if s == "repo" else "false"}">'
                      f'{e(tr(k))}</button>' for s, k in (("repo", "files.source_repo"), ("local", "files.source_local")))
    acts = e(tr("local.folder_acts"))
    local = (f'<div id="local-bar" class="local-bar" hidden>'
             f'<p id="local-unsupported" class="explorer-note" hidden>{e(tr("local.unsupported"))}</p>'
             f'<button type="button" id="local-open" class="btn">{e(tr("local.open"))}</button>'
             f'<button type="button" id="local-restore" class="btn" hidden></button>'
             f'<div id="local-folder" class="local-folder" hidden><span id="local-name" class="local-name"></span>'
             f'<button type="button" id="local-acts" class="row-acts shown" aria-label="{acts}" title="{acts}">'
             f'<span class="dots" aria-hidden="true"></span></button></div>'
             f'<button type="button" id="local-forget" class="quiet-btn" hidden>{e(tr("local.forget"))}</button>'
             f'<p id="local-note" class="explorer-note" role="status"></p></div>')
    return (f'<aside id="explorer" class="column explorer" aria-label="{e(tr("files.explorer"))}"><div class="side-inner">'
            f'{_project_head(tr, f, ref)}'
            f'<div id="source-switch" class="source-switch" role="group" aria-label="{e(tr("files.source"))}">{sources}</div>'
            f'{local}'
            f'<div class="explorer-filter"><input id="explorer-filter" type="search" placeholder="{label}" aria-label="{label}" '
            f'autocomplete="off" spellcheck="false" autocapitalize="off"></div>'
            f'<p id="explorer-note" class="explorer-note" hidden></p>'
            f'<ul id="explorer-tree" class="tree" role="tree" aria-label="{e(tr("files.tree"))}"></ul>'
            f'<p id="explorer-status" class="vh" role="status"></p>'
            f'</div></aside>')


# --------------------------------------------------------------------------- small parts

def _table(head: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    """Cells are HTML already escaped by the caller. The table scrolls inside its box on a narrow screen."""
    h = "".join(f"<th>{c}</th>" for c in head)
    r = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{h}</tr></thead><tbody>{r}</tbody></table></div>'


def _status(tr: Translator, a: dict[str, Any]) -> str:
    if a["online"]:
        return e(tr("state.online"))
    why = a.get("offline_because")
    return e(tr("state.offline")) + (f'<br><small class="muted">{e(tr("offline." + why))}</small>' if why else "")


def _kind(tr: Translator, kind: str) -> str:
    return e(tr(f"kind.{kind}") if tr.has(f"kind.{kind}") else kind)


def _when(tr: Translator, t: str | None) -> str:
    return e(t.replace("T", " ").replace("Z", " UTC") if t else tr("state.none"))


def _group_label(tr: Translator, groups: dict[str, dict[str, Any]], name: str) -> str:
    g = groups.get(name)
    return tr.group(name, g["kind"], g.get("owner", "")) if g else name


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
            "channel": (("set.group.channel", ("overview", "notifications", "pins")),)}


def settings_sections(scope: str, can_invite: bool) -> list[str]:
    """The sections a member may open: every member reads members and groups; invitations are for who may invite."""
    return [x for _, xs in SETTINGS[scope] for x in xs if x != "invites" or can_invite]


def settings(tr: Translator, person: dict[str, Any], frame: dict[str, Any], scope: str, section: str,
             view: dict[str, Any], permissions: list[str], management: Iterable[str],
             channel: dict[str, Any] | None = None) -> tuple[str, int]:
    """Project settings (scope "project") and one channel's settings (scope "channel") as one full-page layer over
    the frame: the list of sections (#settings-nav) on the left, the section on the right, the close control
    (#settings-close, also Escape) at the top right. `section` "" is the bare address: the first section on a wide
    screen, the list of sections on a narrow one. settings.js switches sections in place (each has its address),
    draws members, groups, mutes and pins from the JSON API starting from `view` (/api/members), and closes the layer
    back to the page it was opened from. Groups keep the elements of the former members page (#groups,
    #group-detail, #group-create for who may create groups)."""
    slug = frame["slug"]
    mine = view["me"]["permissions"]
    sections = settings_sections(scope, frame["can_admin"])
    base = f"/{q(slug)}/settings" if scope == "project" else channel_settings_href(slug, channel["name"])
    current = section or sections[0]
    nav = []
    for heading, names in SETTINGS[scope]:
        rows = []
        for x in names:
            if x in sections:
                cur = ' aria-current="page"' if x == section else ""
                rows.append(f'<li><a class="place" href="{e(base)}/{x}" data-section="{x}"{cur}>{e(tr("set." + x))}</a></li>')
        nav.append(f'<h2 class="settings-heading">{e(tr(heading))}</h2><ul class="side-list">{"".join(rows)}</ul>')
    what = frame["name"] if scope == "project" else "#" + channel["name"]
    title = tr("set.project_title") if scope == "project" else tr("set.channel_title", name=channel["name"])
    parts = {}
    if scope == "project":
        parts["overview"] = (f'<dl class="set-facts"><dt>{e(tr("set.name"))}</dt><dd class="set-name">{e(frame["name"])}</dd>'
                             f'<dt>{e(tr("set.repo"))}</dt><dd>{_repo_link(tr, frame["repo"])}</dd></dl>'
                             f'<p class="dim">{e(tr("set.overview_readonly"))}</p>')
        parts["members"] = (f'<p class="dim">{e(tr("mem.all_hint"))}</p>'
                            f'<div class="set-filter"><input id="members-filter" type="search" placeholder="{e(tr("mem.filter_members"))}" '
                            f'aria-label="{e(tr("mem.filter_members"))}" autocomplete="off" spellcheck="false"></div>'
                            f'<div id="members-table"></div>')
        parts["groups"] = _groups_section(tr, mine, permissions)
        if "invites" in sections:
            parts["invites"] = (f'<p class="dim">{e(tr("admin.invite_hint"))}</p>'
                                f'<form class="stack" data-api="/{q(slug)}/api/invites" data-show="url"><label class="field">'
                                f'<span>{e(tr("admin.invite_login"))}</span><input name="github_login" autocomplete="off"></label>'
                                f'<div class="row"><button class="btn primary">{e(tr("admin.invite_button"))}</button></div>'
                                f'<p><code class="out" data-out></code></p></form>')
    else:
        name = channel["name"]
        parts["overview"] = (f'<dl class="set-facts"><dt>{e(tr("set.name"))}</dt><dd class="set-name mono">#{e(name)}</dd></dl>'
                             f'<p class="dim">{e(tr("set.channel_readonly"))}</p>')
        boxes = [(tr("msg.mute_me"), "", channel["muted"])]
        boxes += [(tr("msg.mute_agent", name=a), a, a in channel["agent_mutes"]) for a in frame["agents"]]
        rows = "".join(f'<div class="perm-row"><input type="checkbox" id="mute-{i}" data-mute="{e(a)}"{" checked" if on else ""}>'
                       f'<label class="perm-text" for="mute-{i}"><span class="perm-name">{e(label)}</span>'
                       f'<span class="out" aria-live="polite"></span></label></div>'
                       for i, (label, a, on) in enumerate(boxes))
        parts["notifications"] = f'<p class="dim">{e(tr("set.notify_hint"))}</p><div class="perm-list">{rows}</div>'
        parts["pins"] = (f'<p class="dim">{e(tr("set.pins_hint"))}</p>'
                         f'<div id="set-pins" data-can-pin="{"1" if frame["can_create"] else ""}"></div>')
    body_secs = "".join(
        f'<section class="set-sec" data-section="{x}" aria-labelledby="set-h-{x}"{"" if x == current else " hidden"}>'
        f'<h1 id="set-h-{x}" class="page-title set-title">{e(tr("set." + x))}</h1>{parts[x]}</section>' for x in sections)
    close = e(tr("set.close"))
    data = {"slug": slug, "scope": scope, "section": section, "base": base, "view": view, "catalogue": permissions,
            "management": sorted(management), **({"channel": channel["name"]} if channel else {})}
    body = (f'<div id="settings-layer" class="settings-layer{" at-list" if not section else ""}" {_attrs(data)}>'
            f'<nav id="settings-nav" class="settings-nav" aria-label="{e(tr("set.sections"))}"><div class="settings-nav-inner">'
            f'<p class="settings-for">{e(what)}</p>{"".join(nav)}</div></nav>'
            f'<div class="settings-main"><div class="settings-bar">{open_button(tr)}'
            f'<a id="settings-back" class="btn quiet settings-back" href="{e(base)}">{e(tr("set.back"))}</a>'
            f'<span class="spacer"></span><div class="settings-close">'
            f'<button type="button" id="settings-close" class="icon-btn" aria-label="{close}" title="{close}" '
            f'aria-keyshortcuts="Escape"><span class="cross" aria-hidden="true"></span></button>'
            f'<span class="esc" aria-hidden="true">{e(tr("set.esc"))}</span></div></div>'
            f'<div class="settings-body">{body_secs}</div></div></div>')
    return layout(tr, title, body, person, frame, "settings", header="", page_class="settings-page",
                  scripts=["people.js", "settings.js"])


def _groups_section(tr: Translator, mine: list[str], permissions: list[str]) -> str:
    """Groups, as a list with a filter and "new group" (#groups); a chosen group (?g= in the address) is drawn in
    #group-detail, with the list as a middle column. The form to make a group (#group-create) is here only for a
    person who may manage groups, offering only what they hold."""
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
        create = (f'<form id="group-create" class="card group-create" hidden><h2>{e(tr("mem.new_group"))}</h2>'
                  f'<label class="field"><span>{e(tr("mem.create_name"))}</span><input name="name" required maxlength="40" '
                  f'autocomplete="off" spellcheck="false" autocapitalize="off"></label>'
                  f'<fieldset class="perm-set"><legend>{e(tr("mem.create_perms"))}</legend>{boxes}</fieldset>'
                  f'<div class="row"><button class="btn primary">{e(tr("mem.create"))}</button>'
                  f'<button type="button" class="btn" data-dismiss>{e(tr("mem.cancel"))}</button>'
                  f'<span class="out" data-out aria-live="polite"></span></div></form>')
    label = e(tr("mem.filter"))
    return (f'<div id="groups-root" class="groups-page">'
            f'<nav id="groups" class="groups-list" aria-label="{e(tr("mem.list_label"))}"><div class="groups-head">'
            f'<input id="groups-filter" type="search" placeholder="{label}" aria-label="{label}" autocomplete="off" '
            f'spellcheck="false">{plus}</div><div id="groups-body"></div></nav>'
            f'<div class="group-main">{create}<section id="group-detail" class="group-detail" tabindex="-1"></section></div>'
            f'</div>')


def _group_buttons(tr: Translator, slug: str, member: str, current: list[str], groups: dict[str, dict[str, Any]],
                   addable: list[str], remove_key: str, add_key: str) -> str:
    """Remove buttons for each editable group the member is in, and a picker to add one."""
    api = f"/{q(slug)}/api/members/{q(member)}/groups"
    out = []
    for g in current:
        if groups.get(g, {}).get("kind") == "ownership":
            out.append(f'<span class="tag">{e(_group_label(tr, groups, g))}</span>')
            continue
        out.append(f'<form class="inline" data-api="{api}"><input type="hidden" name="remove" data-list value="{e(g)}">'
                   f'<button class="chip-btn" title="{e(tr(remove_key, group=g))}">{e(_group_label(tr, groups, g))}<span class="cross" aria-hidden="true"></span></button></form>')
    choices = [g for g in addable if g not in current]
    if choices:
        opts = "".join(f'<option value="{e(g)}">{e(_group_label(tr, groups, g))}</option>' for g in choices)
        out.append(f'<form class="inline" data-api="{api}"><select name="add" data-list aria-label="{e(tr(add_key))}">{opts}</select>'
                   f'<button class="btn">{e(tr(add_key))}</button><span class="out" data-out></span></form>')
    return f'<div class="wrap-row">{"".join(out)}</div>'


def _invite(tr: Translator, slug: str) -> str:
    """The button that makes an agent invitation link; app.js shows what the API answers in #invite-result."""
    return (f'<section class="block"><h2>{e(tr("invite.title"))}</h2><p class="muted">{e(tr("invite.skip"))}</p>'
            f'<p class="row"><button type="button" class="btn primary" id="invite-agent" data-api="/{q(slug)}/api/my/agent-invites">'
            f'{e(tr("invite.button"))}</button> <span class="out" data-out></span></p>'
            f'<p class="muted" id="invite-consent">{e(tr("invite.consent"))}</p>'
            f'<div id="invite-result" class="card invite-result" hidden></div></section>')


def _connection(tr: Translator, c: dict[str, Any]) -> str:
    if "connected" not in c:            # a connector has no program of its own
        return e(tr("state.none"))
    return e(tr("my.connected.yes" if c["connected"] else "my.connected.no"))


def my(tr: Translator, person: dict[str, Any], frame: dict[str, Any], mine: dict[str, Any], groups: list[dict[str, Any]],
       assignable: list[str]) -> tuple[str, int]:
    slug = frame["slug"]
    gmap = {g["name"]: g for g in groups}
    parts = [f'<section class="block"><h2>{e(tr("my.agents"))}</h2>']
    if mine["agents"]:
        rows = []
        for a in mine["agents"]:
            remove = _gone(tr, f"/{q(slug)}/api/members/{q(a['name'])}/remove", "agent", a["name"], tr("my.remove_agent"))
            rows.append([f'<span class="mono">{e(a["name"])}</span>', _kind(tr, a["kind"]), _status(tr, a),
                         _when(tr, a["last_active"]), e(a["generation"]),
                         _group_buttons(tr, slug, a["name"], a["groups"], gmap, assignable, "my.remove_group", "my.add"),
                         remove])
        parts.append(_table([e(tr("col.name")), e(tr("col.kind")), e(tr("col.status")), e(tr("col.last_active")),
                             e(tr("col.generation")), e(tr("col.groups")), e(tr("col.actions"))], rows))
    else:
        parts.append(f'<p class="muted">{e(tr("my.no_agents"))}</p>')
    parts.append("</section>")
    parts.append(_invite(tr, slug))
    parts.append(f'<section class="block"><h2>{e(tr("my.credentials"))}</h2>')
    if mine["credentials"]:
        parts.append(_table(
            [e(tr("col.label")), e(tr("col.kind")), e(tr("col.via")), e(tr("col.connection")), e(tr("col.last_used")),
             e(tr("col.actions"))],
            [[e(c["label"]), e(tr(f"cred.{c['kind']}")),
              e(tr(f"my.via.{c['via']}") if tr.has(f"my.via.{c['via']}") else c["via"]), _connection(tr, c),
              _when(tr, c["last_used"]),
              _gone(tr, f"/{q(slug)}/api/my/credentials/{e(c['id'])}/revoke", "revoke", c["label"], tr("my.revoke"))]
             for c in mine["credentials"]]))
    else:
        parts.append(f'<p class="muted">{e(tr("my.no_credentials"))}</p>')
    parts.append("</section>")
    parts.append(f'<section class="block"><h2>{e(tr("my.switches"))}</h2><p class="muted">{e(tr("my.switches_hint"))}</p>')
    parts.append(switch_boxes(tr, mine["switches"], toggle=f"/{q(slug)}/api/my/switches"))
    parts.append("</section>")
    return layout(tr, tr("my.title"), f'<div class="prose">{"".join(parts)}</div>', person, frame, "my")


def switch_boxes(tr: Translator, values: dict[str, bool], toggle: str | None = None) -> str:
    """The four switches. On "my agents" each saves at once; on an approval page they go with the form."""
    out = []
    for k in SWITCHES:
        checked = " checked" if values.get(k) else ""
        attrs = f'data-toggle="{e(toggle)}"' if toggle else 'value="1"'
        out.append(f'<div class="check"><label><input type="checkbox" name="{k}" {attrs}{checked}> {e(tr("switch." + k))}</label>'
                   f' <span class="out" data-out></span></div>')
    return "".join(out)


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


def _gone(tr: Translator, api: str, kind: str, name: str, label: str) -> str:
    """A button whose act cannot be undone: it opens the floating confirmation (base.js), where `name` is typed."""
    return (f'<form class="inline" data-api="{api}" data-gone="{e(kind)}" data-gone-name="{e(name)}">'
            f'<button class="btn">{e(label)}</button><span class="out" data-out></span></form>')


def _tool(tr: Translator, ident: str, icon: str, label_key: str, attrs: str, inner: str = "") -> str:
    """An icon button of the channel bar: its name for screen readers and as its tooltip."""
    label = e(tr(label_key))
    return (f'<button type="button" id="{ident}" class="icon-btn tool" aria-label="{label}" title="{label}" {attrs}>'
            f'{glyph(icon)}{inner}</button>')


def _right_head(tr: Translator, ident: str, title_key: str, close_key: str, close_cls: str) -> str:
    return (f'<div class="task-head"><h2 id="{ident}-title">{e(tr(title_key))}</h2>'
            f'<span id="{ident}-summary" class="dim small"></span><span class="spacer"></span>'
            f'<button type="button" class="icon-btn {close_cls}" aria-label="{e(tr(close_key))}" title="{e(tr(close_key))}">'
            f'<span class="cross" aria-hidden="true"></span></button></div>')


def messages(tr: Translator, person: dict[str, Any], frame: dict[str, Any], view: dict[str, Any]) -> tuple[str, int]:
    """The messages page: the channel bar (the place's name, which opens its settings or the other member's card;
    the pins, the task table, the member list and the search field), the chosen place in the middle, and the right
    column showing one thing at a time (the task table, the member list, search results). The navigation's lists
    are the frame's (frame.js); the page scripts keep the rest current through the JSON API (messages.js, tasks.js,
    people.js, search.js; right.js decides what the right column shows). What the scripts need is in data-
    attributes."""
    data = {"slug": frame["slug"], "me": person["name"]}
    search = e(tr("srch.label"))
    tools = (_tool(tr, "pins-toggle", "pin", "bar.pins", 'aria-haspopup="dialog" aria-expanded="false" aria-controls="pins"',
                   '<span id="pins-count" class="tool-count" hidden></span>')
             + _tool(tr, "task-toggle", "tasks", "bar.tasks", 'aria-expanded="false" aria-controls="task-panel"')
             + _tool(tr, "members-toggle", "members", "bar.members", 'aria-expanded="false" aria-controls="member-panel"')
             + f'<div class="search-box" role="search">{glyph("search", 16)}'
               f'<span id="search-chip" class="search-chip" hidden><span class="search-chip-text"></span>'
               f'<button type="button" id="search-chip-x" class="chip-x"><span class="cross" aria-hidden="true"></span></button></span>'
               f'<input id="search-input" type="search" placeholder="{e(tr("srch.placeholder"))}" aria-label="{search}" '
               f'role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="search-suggest" '
               f'autocomplete="off" spellcheck="false" autocapitalize="off" maxlength="300">'
               f'<ul id="search-suggest" class="search-suggest" role="listbox" aria-label="{e(tr("srch.suggest"))}" hidden></ul>'
               f'</div>')
    header = (f'<header class="page-head room-head">{open_button(tr)}'
              f'{fold_button(tr, "chat", "side", "nav.places", "side-toggle")}'
              f'<h1 id="place-title" class="page-title place-title"><button type="button" id="place-button" class="place-btn">'
              f'</button></h1><span class="spacer"></span>'
              f'<div class="room-tools" role="group" aria-label="{e(tr("bar.tools"))}">{tools}</div></header>')
    room = (f'<div id="chat" class="room" {_attrs(data)}>'
            f'<div id="pins" class="pins-pop" role="dialog" aria-label="{e(tr("pin.list_label"))}" tabindex="-1" '
            f'data-can-pin="{"1" if frame["can_create"] else ""}" popover="manual" hidden></div>'
            f'<div id="scroller" class="scroller"><div class="older-row"><button type="button" id="older" class="btn quiet" hidden>'
            f'{e(tr("msg.older"))}</button></div>'
            f'<ol id="messages" class="messages" aria-live="polite"></ol></div>'
            f'<form id="composer" class="composer"><div id="reply-target" class="reply-target" hidden><span></span>'
            f'<button type="button" id="reply-cancel" class="quiet-btn">{e(tr("msg.reply_cancel"))}</button></div>'
            f'<div class="composer-box"><textarea id="text" rows="1" maxlength="4000" aria-label="{e(tr("msg.input_label"))}" '
            f'placeholder="{e(tr("msg.input_hint"))}"></textarea>'
            f'<button class="btn primary send">{e(tr("msg.send"))}</button></div>'
            f'<div class="out composer-out" id="composer-out" aria-live="polite"></div></form></div>')
    tasks = (f'<aside id="task-panel" class="task-panel right-panel" aria-labelledby="task-title" hidden '
             f'data-can-edit="{"1" if view["can_edit_tasks"] else ""}">'
             f'<div class="task-head"><h2 id="task-title">{e(tr("task.title"))}</h2><span id="task-summary" class="dim small"></span>'
             f'<span class="spacer"></span><button type="button" id="task-close" class="icon-btn right-close" '
             f'aria-label="{e(tr("task.close"))}"><span class="cross" aria-hidden="true"></span></button></div>'
             f'<div id="task-body" class="task-body"></div></aside>')
    people = (f'<aside id="member-panel" class="task-panel right-panel" aria-labelledby="member-title" hidden>'
              f'{_right_head(tr, "member", "people.title", "people.close", "right-close")}'
              f'<div id="member-body" class="task-body member-body"></div></aside>')
    found = (f'<aside id="search-results" class="task-panel right-panel" aria-labelledby="search-title" hidden>'
             f'{_right_head(tr, "search", "srch.title", "srch.close", "search-close")}'
             f'<div id="search-body" class="task-body search-body" aria-live="polite"></div></aside>')
    return layout(tr, tr("msg.title"), room + tasks + people + found, person, frame, "messages", header=header,
                  page_class="room-page", styles=["vendor/katex/katex.min.css"],
                  scripts=["vendor/marked/marked.min.js", "vendor/dompurify/purify.min.js", "vendor/katex/katex.min.js",
                           "render.js", "paths.js", "right.js", "people.js", "messages.js", "tasks.js", "search.js"])


VIEWS = (("rendered", "files.view_rendered"), ("source", "files.view_source"), ("split", "files.view_split"))


def files(tr: Translator, person: dict[str, Any], frame: dict[str, Any], path: str, max_bytes: int) -> tuple[str, int]:
    """Files mode: the repository's files and a local folder's, using the whole page. A shell: the explorer (the
    frame's second column), the tab strip and the document are drawn by explorer.js and viewer.js, from the files API
    (repo.js) and from the reader's own folder in the browser (local.js; nothing of it reaches the server). `path` is the file the
    address names ("" for none); `max_bytes`: a larger file is not shown here (the server does not fetch it)."""
    data = {"slug": frame["slug"], "path": path, "repo": frame["repo"], "can-pin": "1" if frame["can_create"] else "",
            "can-manage": "1" if frame["can_admin"] else "", "max-bytes": str(max_bytes)}
    views = "".join(f'<button type="button" class="icon-btn" data-view="{v}" aria-pressed="false" aria-label="{e(tr(k))}" '
                    f'title="{e(tr(k))}">{glyph(v)}</button>' for v, k in VIEWS)
    github, save = e(tr("files.github")), e(tr("files.save"))
    header = (f'<header class="page-head files-head">{open_button(tr)}'
              f'{fold_button(tr, "files", "explorer", "files.explorer", "explorer-toggle")}'
              f'<h1 class="vh">{e(tr("files.title"))}</h1>'
              f'<div id="file-tabs" class="file-tabs" role="tablist" aria-label="{e(tr("files.tabs"))}"></div>'
              f'<div class="file-tools" role="group" aria-label="{e(tr("files.tools"))}">'
              f'<div id="view-switch" class="view-switch" role="group" aria-label="{e(tr("files.view"))}">{views}</div>'
              f'<a id="file-github" class="icon-btn" aria-label="{github}" title="{github}" target="_blank" '
              f'rel="noopener noreferrer" aria-disabled="true">{glyph("github")}</a>'
              f'<button type="button" id="file-save" class="icon-btn" aria-label="{save}" title="{save}" '
              f'aria-keyshortcuts="Control+S Meta+S" aria-disabled="true" hidden>{glyph("save")}</button></div></header>')
    body = (f'<section id="files" class="files" {_attrs(data)}>'
            f'<div id="file-view" class="file-view" role="tabpanel" tabindex="-1" aria-label="{e(tr("files.title"))}"></div>'
            f'</section>')
    return layout(tr, tr("files.title"), body, person, frame, "files", header=header, page_class="files-page",
                  styles=["vendor/katex/katex.min.css"],
                  scripts=["vendor/marked/marked.min.js", "vendor/dompurify/purify.min.js", "vendor/katex/katex.min.js",
                           "vendor/codemirror/codemirror.min.js", "render.js", "paths.js", "highlight.js", "editor.js",
                           "repo.js", "local.js", "explorer.js", "viewer.js"])


def schedules(tr: Translator, person: dict[str, Any], frame: dict[str, Any], view: dict[str, Any]) -> tuple[str, int]:
    """The scheduled messages. The list (#schedules) is drawn by schedules.js from the JSON API; the form to make
    one (#schedule-form) is here only for a person who may create, with the places they can post to."""
    data = {"slug": frame["slug"], "me": person["name"], "can-manage": "1" if view["can_manage"] else "",
            "places": view["places"], "min-every": view["min_every_s"]}
    header = (f'<header class="page-head">{open_button(tr)}<div class="head-text"><h1 class="page-title">{e(tr("sch.title"))}</h1>'
              f'<p class="dim">{e(tr("sch.intro"))}</p></div></header>')
    parts = []
    if view["can_create"]:
        parts.append(f'<section class="card sch-new"><h2>{e(tr("sch.new"))}</h2><form id="schedule-form" class="sch-form"></form></section>')
    parts.append(f'<section class="block"><h2>{e(tr("sch.list"))}</h2><div id="schedules" {_attrs(data)}></div></section>')
    return layout(tr, tr("sch.title"), f'<div class="prose">{"".join(parts)}</div>', person, frame, "schedules",
                  header=header, scripts=["schedules.js"])
