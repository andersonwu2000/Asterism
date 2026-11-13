"""Server-rendered pages. Every text comes from the message catalogue (tr), every value is escaped.

Forms marked data-api are sent as JSON by /static/app.js to the same JSON API that scripts use, so a
page does nothing the API does not; the OAuth consent form is a plain form because it ends in a redirect.
"""
from __future__ import annotations

import json
import urllib.parse
from html import escape
from typing import Any, Iterable

from .i18n import Translator
from .projects import SWITCHES

ENFORCED_SWITCHES = {"others_regroup", "others_mention", "others_channel"}   # others_assign waits for tasks


def e(v: Any) -> str:
    return escape("" if v is None else str(v), quote=True)


def q(v: str) -> str:
    return urllib.parse.quote(v, safe="")


STYLE = """body{font-family:system-ui,sans-serif;max-width:60rem;margin:1rem auto;padding:0 1rem;line-height:1.5}
nav a,nav form{margin-right:1rem}nav form{display:inline}table{border-collapse:collapse;margin:.5rem 0}
td,th{border:1px solid #ccc;padding:.25rem .5rem;text-align:left;vertical-align:top}form.inline{display:inline}
.muted{color:#666}.out{color:#a40}code{word-break:break-all}body.wide{max-width:none}"""


def layout(tr: Translator, title: str, body: str, person: dict[str, Any] | None = None,
           slug: str | None = None, can_admin: bool = False, status: int = 200,
           styles: Iterable[str] = (), scripts: Iterable[str] = (), wide: bool = False) -> tuple[str, int]:
    """`styles` and `scripts`: further files under /static, loaded before the page's own app.js."""
    nav = [f'<a href="/">{e(tr("nav.home"))}</a>']
    if person and slug:
        nav.append(f'<a href="/{q(slug)}">{e(tr("nav.messages"))}</a>')
        nav.append(f'<a href="/{q(slug)}/members">{e(tr("nav.members"))}</a>')
        nav.append(f'<a href="/{q(slug)}/my">{e(tr("nav.my"))}</a>')
        if can_admin:
            nav.append(f'<a href="/{q(slug)}/admin">{e(tr("nav.admin"))}</a>')
    if person:
        nav.append(f'<span class="muted">{e(tr("nav.signed_in_as", name=person["name"]))}</span>')
        nav.append(f'<form method="post" action="/logout"><button>{e(tr("nav.logout"))}</button></form>')
    msgs = e(json.dumps(tr.js_messages(), ensure_ascii=False))
    links = "".join(f'<link rel="stylesheet" href="/static/{e(x)}">' for x in styles)
    tags = "".join(f'<script src="/static/{e(x)}"></script>' for x in scripts)
    html = (f'<!doctype html><html lang="{e(tr.locale)}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(tr("page.title", title=title, app=tr("app.name")))}</title><style>{STYLE}</style>{links}</head>'
            f'<body data-msg="{msgs}"{' class="wide"' if wide else ""}><nav>{"".join(nav)}</nav>'
            f'<main><h1>{e(title)}</h1>{body}</main>{tags}<script src="/static/app.js"></script></body></html>')
    return html, status


def message(tr: Translator, title_key: str, text: str, status: int, **ctx: Any) -> tuple[str, int]:
    return layout(tr, tr(title_key), f"<p>{e(text)}</p>", status=status, **ctx)


def _table(head: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    """Cells are HTML already escaped by the caller."""
    h = "".join(f"<th>{c}</th>" for c in head)
    r = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{r}</tbody></table>"


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
                f'<p><a href="/login?next=/">{e(tr("login.github"))}</a></p>')
        return layout(tr, tr("home.title"), body)
    if projects:
        items = "".join(f'<li><a href="/{q(p["slug"])}">{e(p["name"])}</a></li>' for p in projects)
        body = f'<h2>{e(tr("home.projects"))}</h2><ul>{items}</ul>'
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
    body = (f'<p>{e(tr("landing.people"))}</p><p><a href="{e(login)}">{e(tr("login.github"))}</a></p>'
            f'<p lang="en">{e(AGENT_LINE)}</p>')
    return layout(tr, tr("landing.title", slug=slug), body)


def test_login(tr: Translator, next_path: str) -> tuple[str, int]:
    body = (f'<h2>{e(tr("login.test_heading"))}</h2><p>{e(tr("login.test_hint"))}</p>'
            f'<form data-api="/test/login" data-next="{e(next_path)}">'
            f'<label>{e(tr("login.test_field"))} <input name="github_login" required autofocus></label> '
            f'<button>{e(tr("login.submit"))}</button> <span class="out" data-out></span></form>')
    return layout(tr, tr("login.title"), body)


def join(tr: Translator, person: dict[str, Any], code: str, preview: dict[str, Any]) -> tuple[str, int]:
    p = preview["project"]
    if not preview["usable"]:
        return message(tr, "join.title", tr("join.unusable"), 410, person=person)
    body = f'<p>{e(tr("join.project", name=p["name"]))}</p><p>{e(tr("join.explain"))}</p>'
    if preview["github_login"]:
        body += f'<p class="muted">{e(tr("join.for_login", login=preview["github_login"]))}</p>'
    body += (f'<form data-api="/join/{q(code)}" data-next="/{q(p["slug"])}/members">'
             f'<button>{e(tr("join.button"))}</button> <span class="out" data-out></span></form>')
    return layout(tr, tr("join.title"), body, person)


def members(tr: Translator, person: dict[str, Any], view: dict[str, Any], can_admin: bool) -> tuple[str, int]:
    p = view["project"]
    groups = {g["name"]: g for g in view["groups"]}
    order = [g for g in view["groups"] if g["kind"] != "ownership"] + [g for g in view["groups"] if g["kind"] == "ownership"]
    parts = [f'<p>{e(tr("project.line", name=p["name"], repo=p["repo"]))}</p>']
    for g in order:
        people = [x for x in view["people"] if g["name"] in x["groups"]]
        agents = [a for a in view["agents"] if g["name"] in a["groups"]]
        perms = ", ".join(tr(f"perm.{x}") for x in g["permissions"])
        parts.append(f'<section><h2>{e(_group_label(tr, groups, g["name"]))} <small class="muted">{e(g["name"])}</small></h2>')
        if perms:
            parts.append(f'<p class="muted">{e(tr("members.permissions", list=perms))}</p>')
        if not people and not agents:
            parts.append(f'<p class="muted">{e(tr("members.empty"))}</p>')
        if people:
            parts.append(f'<h3>{e(tr("members.people"))}</h3><ul>' + "".join(
                f'<li>{e(x["name"])} <span class="muted">{e(tr("members.github", login=x["github_login"]))}</span></li>' for x in people) + "</ul>")
        if agents:
            parts.append(f'<h3>{e(tr("members.agents"))}</h3>' + _table(
                [e(tr("col.name")), e(tr("col.owner")), e(tr("col.kind")), e(tr("col.status")), e(tr("col.last_active"))],
                [[e(a["name"]), e(a["owner"]), _kind(tr, a["kind"]), _status(tr, a), _when(tr, a["last_active"])] for a in agents]))
        parts.append("</section>")
    return layout(tr, tr("members.title"), "".join(parts), person, p["slug"], can_admin)


def _group_buttons(tr: Translator, slug: str, member: str, current: list[str], groups: dict[str, dict[str, Any]],
                   addable: list[str], remove_key: str, add_key: str) -> str:
    """Remove buttons for each editable group the member is in, and a picker to add one."""
    api = f"/{q(slug)}/api/members/{q(member)}/groups"
    out = []
    for g in current:
        if groups.get(g, {}).get("kind") == "ownership":
            out.append(f'<span class="muted">{e(_group_label(tr, groups, g))}</span>')
            continue
        out.append(f'<form class="inline" data-api="{api}"><input type="hidden" name="remove" data-list value="{e(g)}">'
                   f'<button title="{e(tr(remove_key, group=g))}">{e(tr("group.remove_button", group=_group_label(tr, groups, g)))}</button></form>')
    choices = [g for g in addable if g not in current]
    if choices:
        opts = "".join(f'<option value="{e(g)}">{e(_group_label(tr, groups, g))}</option>' for g in choices)
        out.append(f'<form class="inline" data-api="{api}"><select name="add" data-list>{opts}</select>'
                   f'<button>{e(tr(add_key))}</button><span class="out" data-out></span></form>')
    return " ".join(out)


def _add_local(tr: Translator, public_url: str, slug: str) -> str:
    """How to add a local agent (Claude Code, Codex) through the helper: the commands for this server."""
    helper = f"{public_url}/helper.py"
    join = f"python asterism_helper.py --join {public_url}/{slug} --client"
    return (f'<h2>{e(tr("my.add_local"))}</h2><ol>'
            f'<li>{e(tr("my.add_local.download"))} <code>{e(helper)}</code></li>'
            f'<li>{e(tr("my.add_local.join"))}<br><code>{e(join)} claude</code>{e(tr("my.add_local.or"))}'
            f'<code>{e(join)} codex</code><br><span class="muted">{e(tr("my.add_local.approve"))}</span></li>'
            f'<li>{e(tr("my.add_local.register"))}</li></ol>')


def my(tr: Translator, person: dict[str, Any], slug: str, mine: dict[str, Any], groups: list[dict[str, Any]],
       assignable: list[str], can_admin: bool, public_url: str) -> tuple[str, int]:
    gmap = {g["name"]: g for g in groups}
    parts = [f'<h2>{e(tr("my.agents"))}</h2>']
    if mine["agents"]:
        rows = []
        for a in mine["agents"]:
            remove = (f'<form class="inline" data-api="/{q(slug)}/api/members/{q(a["name"])}/remove" '
                      f'data-confirm="{e(tr("confirm.remove", name=a["name"]))}"><button>{e(tr("my.remove_agent"))}</button>'
                      f'<span class="out" data-out></span></form>')
            rows.append([e(a["name"]), _kind(tr, a["kind"]), _status(tr, a), _when(tr, a["last_active"]),
                         e(a["generation"]),
                         _group_buttons(tr, slug, a["name"], a["groups"], gmap, assignable, "my.remove_group", "my.add"),
                         remove])
        parts.append(_table([e(tr("col.name")), e(tr("col.kind")), e(tr("col.status")), e(tr("col.last_active")),
                             e(tr("col.generation")), e(tr("col.groups")), e(tr("col.actions"))], rows))
    else:
        parts.append(f'<p class="muted">{e(tr("my.no_agents"))}</p>')
    parts.append(_add_local(tr, public_url, slug))
    parts.append(f'<h2>{e(tr("my.credentials"))}</h2>')
    if mine["credentials"]:
        parts.append(_table(
            [e(tr("col.label")), e(tr("col.kind")), e(tr("col.created")), e(tr("col.last_used")), e(tr("col.actions"))],
            [[e(c["label"]), e(tr(f"cred.{c['kind']}")), _when(tr, c["created"]), _when(tr, c["last_used"]),
              f'<form class="inline" data-api="/{q(slug)}/api/my/credentials/{e(c["id"])}/revoke" '
              f'data-confirm="{e(tr("confirm.revoke"))}"><button>{e(tr("my.revoke"))}</button>'
              f'<span class="out" data-out></span></form>'] for c in mine["credentials"]]))
    else:
        parts.append(f'<p class="muted">{e(tr("my.no_credentials"))}</p>')
    parts.append(f'<h2>{e(tr("my.switches"))}</h2><p class="muted">{e(tr("my.switches_hint"))}</p>')
    parts.append(switch_boxes(tr, mine["switches"], toggle=f"/{q(slug)}/api/my/switches"))
    return layout(tr, tr("my.title"), "".join(parts), person, slug, can_admin)


def switch_boxes(tr: Translator, values: dict[str, bool], toggle: str | None = None, form_field: bool = False) -> str:
    """The four switches. On "my agents" each saves at once; on an approval page they go with the form."""
    out = []
    for k in SWITCHES:
        later = "" if k in ENFORCED_SWITCHES else f' <span class="muted">{e(tr("switch.later"))}</span>'
        checked = " checked" if values.get(k) else ""
        if toggle:
            attrs = f'data-toggle="{e(toggle)}"'
        elif form_field:
            attrs = 'value="1"'
        else:
            attrs = 'data-in="switches"'
        out.append(f'<div><label><input type="checkbox" name="{k}" {attrs}{checked}> {e(tr("switch." + k))}</label>'
                   f'{later} <span class="out" data-out></span></div>')
    return "".join(out)


def device(tr: Translator, person: dict[str, Any], slug: str, project_name: str, code: str | None,
           view: dict[str, Any] | None, can_admin: bool) -> tuple[str, int]:
    if not code or view is None:
        body = (f'<form method="get" action="/{q(slug)}/device"><label>{e(tr("device.enter_code"))} '
                f'<input name="code" required autofocus></label> <button>{e(tr("device.lookup"))}</button></form>')
        return layout(tr, tr("device.title"), body, person, slug, can_admin)
    if view["status"] != "pending":
        return layout(tr, tr("device.title"), f'<p>{e(tr("device.status." + view["status"]))}</p>', person, slug, can_admin)
    body = (f'<p>{e(tr("device.ask", computer=view["computer"], kind=tr("kind." + view["kind"]), project=project_name))}</p>'
            f'<p>{e(tr("device.code", code=code))}</p><p class="muted">{e(tr("device.warning"))}</p>'
            f'<form data-api="/{q(slug)}/api/device/{q(code)}" data-ok-approve="{e(tr("device.done.approve"))}" '
            f'data-ok-deny="{e(tr("device.done.deny"))}">'
            f'<h2>{e(tr("my.switches"))}</h2><p class="muted">{e(tr("my.switches_hint"))}</p>'
            f'{switch_boxes(tr, view["switches"])}'
            f'<p><button name="decision" value="approve">{e(tr("device.approve"))}</button> '
            f'<button name="decision" value="deny">{e(tr("device.deny"))}</button> <span class="out" data-out></span></p></form>')
    return layout(tr, tr("device.title"), body, person, slug, can_admin)


def consent(tr: Translator, person: dict[str, Any], client_name: str, host: str, project_name: str,
            params: dict[str, str], switches: dict[str, bool]) -> tuple[str, int]:
    hidden = "".join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k, v in params.items()
                     if k not in ("decision", "switches", *SWITCHES))
    body = (f'<p>{e(tr("consent.ask", client=client_name, project=project_name, host=host))}</p>'
            f'<form method="post" action="/oauth/authorize">{hidden}<input type="hidden" name="switches" value="1">'
            f'<h2>{e(tr("my.switches"))}</h2><p class="muted">{e(tr("my.switches_hint"))}</p>'
            f'{switch_boxes(tr, switches, form_field=True)}'
            f'<p><button name="decision" value="approve">{e(tr("device.approve"))}</button> '
            f'<button name="decision" value="deny">{e(tr("device.deny"))}</button></p></form>')
    return layout(tr, tr("consent.title"), body, person)


def admin(tr: Translator, person: dict[str, Any], slug: str, view: dict[str, Any], mine: set[str]) -> tuple[str, int]:
    gmap = {g["name"]: g for g in view["groups"]}
    editable = [g["name"] for g in view["groups"] if g["kind"] != "ownership"]
    parts = []
    if "manage_members" in mine:
        parts.append(f'<h2>{e(tr("admin.invite"))}</h2><p class="muted">{e(tr("admin.invite_hint"))}</p>'
                     f'<form data-api="/{q(slug)}/api/invites" data-show="url"><label>{e(tr("admin.invite_login"))} '
                     f'<input name="github_login"></label> <button>{e(tr("admin.invite_button"))}</button>'
                     f'<p><code class="out" data-out></code></p></form>')
    parts.append(f'<h2>{e(tr("admin.members"))}</h2>')
    rows = []
    for x in view["people"]:
        groups = _group_buttons(tr, slug, x["name"], x["groups"], gmap, editable, "admin.remove_group", "admin.add") \
            if "manage_groups" in mine else e(", ".join(_group_label(tr, gmap, g) for g in x["groups"]))
        rows.append([e(x["name"]), e(x["github_login"]), groups, _remove(tr, slug, x["name"]) if "manage_members" in mine else ""])
    for a in view["agents"]:
        groups = _group_buttons(tr, slug, a["name"], a["groups"], gmap, editable, "admin.remove_group", "admin.add") \
            if "manage_groups" in mine else e(", ".join(_group_label(tr, gmap, g) for g in a["groups"]))
        rows.append([e(a["name"]), e(tr("admin.agent_of", owner=a["owner"])), groups,
                     _remove(tr, slug, a["name"]) if "manage_members" in mine else ""])
    parts.append(_table([e(tr("col.name")), e(tr("col.github")), e(tr("col.groups")), e(tr("col.actions"))], rows))
    return layout(tr, tr("admin.title"), "".join(parts), person, slug, True)


def _remove(tr: Translator, slug: str, name: str) -> str:
    return (f'<form class="inline" data-api="/{q(slug)}/api/members/{q(name)}/remove" '
            f'data-confirm="{e(tr("confirm.remove", name=name))}"><button>{e(tr("admin.remove"))}</button>'
            f'<span class="out" data-out></span></form>')


def _place_item(tr: Translator, place: str, label: str, unread: int, important: int) -> str:
    """One entry of the places list; the page script redraws the list with the same markup."""
    badge = ""
    if unread:
        badge = f' <span class="count{" important" if important else ""}">{e(unread)}</span>'
    return f'<li><a href="#{e(q(place))}" data-place="{e(place)}">{e(label)}</a>{badge}</li>'


def messages(tr: Translator, person: dict[str, Any], slug: str, view: dict[str, Any], can_admin: bool) -> tuple[str, int]:
    """The messages page. The list of places is rendered here; the page script (messages.js) keeps it and
    the chosen place up to date through the JSON API. What the script needs is in data- attributes."""
    places = view["places"]
    channels = "".join(_place_item(tr, "#" + c["name"], "#" + c["name"], c["unread"], c["important"])
                       for c in places["channels"])
    private = "".join(_place_item(tr, p["with"], p["with"], p["unread"], p["important"]) for p in places["private"])
    options = "".join(f'<option value="{e(n)}">{e(n)}</option>' for n in view["people"])
    options += "".join(f'<option value="{e(n)}">{e(tr("msg.my_agent", name=n))}</option>' for n in view["agents"])
    new_channel = ""
    if view["can_create"]:
        new_channel = (f'<form id="new-channel" class="side-form"><input name="name" required maxlength="40" '
                       f'placeholder="{e(tr("msg.channel_name"))}" '
                       f'aria-label="{e(tr("msg.channel_name"))}"> <button>{e(tr("msg.new_channel"))}</button>'
                       f'<span class="out" data-out></span></form>')
    start = ""
    if options:
        start = (f'<form id="new-private" class="side-form"><select name="with" aria-label="{e(tr("msg.choose_member"))}">'
                 f'{options}</select> <button>{e(tr("msg.start_private"))}</button></form>')
    data = {"slug": slug, "me": person["name"], "agents": view["agents"], "agent-mutes": view["agent_mutes"]}
    attrs = " ".join(f'data-{k}="{e(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))}"'
                     for k, v in data.items())
    body = (f'<div id="chat" {attrs}>'
            f'<aside class="places"><h2>{e(tr("msg.channels"))}</h2><ul id="channels">{channels}</ul>{new_channel}'
            f'<h2>{e(tr("msg.private"))}</h2><ul id="privates">{private}</ul>{start}</aside>'
            f'<section class="room"><header class="room-head"><h2 id="place-title"></h2>'
            f'<button type="button" id="settings-toggle" aria-expanded="false">{e(tr("msg.settings"))}</button></header>'
            f'<div id="settings" hidden></div>'
            f'<button type="button" id="older" hidden>{e(tr("msg.older"))}</button>'
            f'<ol id="messages" aria-live="polite"></ol>'
            f'<form id="composer"><div id="reply-target" hidden><span></span> '
            f'<button type="button" id="reply-cancel">{e(tr("msg.reply_cancel"))}</button></div>'
            f'<textarea id="text" rows="3" maxlength="4000" aria-label="{e(tr("msg.input_label"))}" '
            f'placeholder="{e(tr("msg.input_hint"))}"></textarea>'
            f'<div><button>{e(tr("msg.send"))}</button> <span class="out" id="composer-out"></span></div></form>'
            f'</section></div>')
    return layout(tr, tr("msg.title"), body, person, slug, can_admin, wide=True,
                  styles=["vendor/katex/katex.min.css", "messages.css"],
                  scripts=["vendor/marked/marked.min.js", "vendor/dompurify/purify.min.js",
                           "vendor/katex/katex.min.js", "messages.js"])
