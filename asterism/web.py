"""HTTP entrances. Each handler only reads the request, calls one domain function and shapes the answer.

Three faces share the domain: the web (session cookie; JSON API and pages), the local agent API (bearer
credential + session header; the computer's connection uses the credential alone), and the remote MCP
endpoint for ChatGPT (OAuth access token). Invitation links, downloads and install scripts need nothing.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hmac
import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import accounts, agents, computers, config, downloads, messaging, oauth, pages, projects, tools, upkeep, util
from .errors import ApiError, bad_request, not_signed_in
from .i18n import Translator, pick_locale
from .projects import Actor, Project
from .store import Store

SESSION_COOKIE = "asterism_session"
LOGIN_COOKIE = "asterism_login"
STATIC = Path(__file__).resolve().parent / "static"

_store: Store | None = None


def store() -> Store:
    assert _store is not None
    return _store


# --------------------------------------------------------------------------- request helpers

def tr_for(request: Request) -> Translator:
    return Translator(pick_locale(request.headers.get("accept-language")))


def signed_in(request: Request):
    return accounts.web_session_person(store().accounts(), request.cookies.get(SESSION_COOKIE))


def require_person(request: Request):
    p = signed_in(request)
    if p is None:
        raise not_signed_in()
    return p


def member_actor(request: Request, slug: str) -> tuple[Project, Actor]:
    person = require_person(request)
    pj = projects.open_project(store(), slug)
    return pj, projects.require_member(pj, person)


async def body_json(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        raise bad_request("invalid_json", "The body must be a JSON object.") from None
    if not isinstance(data, dict):
        raise bad_request("invalid_json", "The body must be a JSON object.")
    return data


async def body_form(request: Request) -> dict[str, str]:
    raw = (await request.body()).decode("utf-8", "replace")
    return dict(urllib.parse.parse_qsl(raw, keep_blank_values=True))


def error_json(e: ApiError) -> JSONResponse:
    return JSONResponse({"error": e.code, "message": e.message}, status_code=e.status)


def set_session_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(SESSION_COOKIE, token, max_age=accounts.WEB_SESSION_TTL_S, httponly=True, samesite="lax",
                    secure=config.get().secure_cookies, path="/")


def login_redirect(request: Request, target: str | None = None) -> RedirectResponse:
    if target is None:
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse("/login?" + urllib.parse.urlencode({"next": util.safe_next(target)}), status_code=303)


def html(page: tuple[str, int]) -> HTMLResponse:
    return HTMLResponse(page[0], status_code=page[1], headers={"Cache-Control": "no-store"})


def api(fn: Callable[[Request], Awaitable[Any]], status: int = 200) -> Callable[[Request], Awaitable[Response]]:
    """A JSON endpoint: the handler returns data or raises ApiError."""
    async def endpoint(request: Request) -> Response:
        try:
            return JSONResponse(await fn(request), status_code=status, headers={"Cache-Control": "no-store"})
        except ApiError as e:
            return error_json(e)
    return endpoint


def page_error(request: Request, e: ApiError, person=None) -> Response:
    tr = tr_for(request)
    key = {"not_found": "error.not_found", "forbidden": "error.forbidden", "gone": "error.gone",
           "not_signed_in": "error.not_signed_in"}.get(e.code)
    text = tr(key) if key else tr("error.generic", code=e.code)
    return html(pages.message(tr, "error.title", text, e.status, person=person))


def can_admin(pj: Project, actor: Actor) -> bool:
    return bool({"manage_members", "manage_groups"} & projects.permissions(pj, actor))


# --------------------------------------------------------------------------- sign-in

async def home(request: Request) -> Response:
    person = signed_in(request)
    mine = projects.projects_of(store(), person) if person else []
    return html(pages.home(tr_for(request), person, mine))


async def login(request: Request) -> Response:
    nxt = util.safe_next(request.query_params.get("next"))
    if signed_in(request):
        return RedirectResponse(nxt, status_code=303)
    if config.get().test_mode:
        return html(pages.test_login(tr_for(request), nxt))
    url, state = accounts.begin_github(store().accounts(), nxt)
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(LOGIN_COOKIE, state, max_age=accounts.LOGIN_STATE_TTL_S, httponly=True, samesite="lax",
                    secure=config.get().secure_cookies, path="/login")
    return resp


async def login_callback(request: Request) -> Response:
    tr = tr_for(request)
    if config.get().test_mode:
        return html(pages.message(tr, "error.title", tr("error.not_found"), 404))
    code, state = request.query_params.get("code", ""), request.query_params.get("state", "")
    cookie = request.cookies.get(LOGIN_COOKIE, "")
    # The state must come back to the browser that started the sign-in (no login CSRF).
    # Each failure is written down once, as the step and a fixed word; never the code, state or cookie.
    if not code or not state or not cookie:
        util.log("github_sign_in_failed", step="state", reason="missing")
        return html(pages.message(tr, "login.title", tr("login.failed"), 400))
    if not hmac.compare_digest(state.encode("utf-8", "surrogatepass"), cookie.encode("utf-8", "surrogatepass")):
        util.log("github_sign_in_failed", step="state", reason="mismatch")
        return html(pages.message(tr, "login.title", tr("login.failed"), 400))
    nxt = accounts.take_login_state(store().accounts(), state)
    if nxt is None:
        util.log("github_sign_in_failed", step="state", reason="expired")      # unknown, used or expired
        return html(pages.message(tr, "login.title", tr("login.failed"), 400))
    try:
        person = await accounts.finish_github(store().accounts(), code)
    except accounts.SignInFailed as e:
        util.log("github_sign_in_failed", step=e.step, reason=e.reason)
        return html(pages.message(tr, "login.title", tr("login.failed"), 502))
    except Exception:  # noqa: BLE001 - anything unforeseen while saving the account: the person just tries again
        util.log("github_sign_in_failed", step="account", reason="server_error")
        return html(pages.message(tr, "login.title", tr("login.failed"), 502))
    resp = RedirectResponse(nxt, status_code=303)
    set_session_cookie(resp, accounts.start_web_session(store().accounts(), person["id"]))
    resp.delete_cookie(LOGIN_COOKIE, path="/login")
    return resp


async def test_login(request: Request) -> Response:
    """Test mode only (not routed otherwise): sign in as any GitHub login."""
    try:
        login_name = (await body_json(request)).get("github_login")
    except ApiError as e:
        return error_json(e)
    if not isinstance(login_name, str) or not util.GITHUB_LOGIN_RE.fullmatch(login_name):
        return error_json(bad_request("invalid_login", "github_login must be a GitHub login."))
    person = accounts.upsert_github(store().accounts(), "test:" + login_name.lower(), login_name)
    resp = JSONResponse({"person": accounts.public(person)})
    set_session_cookie(resp, accounts.start_web_session(store().accounts(), person["id"]))
    return resp


async def logout(request: Request) -> Response:
    accounts.end_web_session(store().accounts(), request.cookies.get(SESSION_COOKIE))
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


async def me(request: Request) -> Any:
    return {"signed_in": True, "person": accounts.public(require_person(request))}


# --------------------------------------------------------------------------- static

STATIC_TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".woff2": "font/woff2",
                ".woff": "font/woff", ".ttf": "font/ttf"}


async def static_file(request: Request) -> Response:
    """The pages' scripts, styles and the vendored libraries. Types are fixed here (the system's guesses
    differ between machines, and the browser refuses a script of the wrong type)."""
    path = (STATIC / request.path_params["path"]).resolve()
    ctype = STATIC_TYPES.get(path.suffix)
    if ctype is None or not path.is_relative_to(STATIC) or not path.is_file():
        return Response("not found", status_code=404, media_type="text/plain")
    return Response(path.read_bytes(), media_type=ctype, headers={"Cache-Control": "no-cache"})


# --------------------------------------------------------------------------- downloads (no authentication)

async def dl_manifest(request: Request) -> Response:
    return JSONResponse(downloads.public_manifest(config.get().data, config.get().public_url),
                        headers={"Cache-Control": "no-cache"})


async def dl_file(request: Request) -> Response:
    path = downloads.build(config.get().data, request.path_params["name"])
    if path is None:
        return Response("not found", status_code=404, media_type="text/plain")
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)


async def install_script(request: Request) -> Response:
    which = request.url.path.lstrip("/")             # the route fixes it: install.sh or install.ps1
    return PlainTextResponse(downloads.install_script(which, config.get().public_url),
                             headers={"Cache-Control": "no-cache"})


# --------------------------------------------------------------------------- agent invitation links

async def api_agent_invites(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return computers.create_invite(pj, actor)


async def agent_invite_page(request: Request) -> Response:
    """What an agent reads at its invitation link: plain text, no session needed."""
    try:
        text = computers.invite_text(store(), request.path_params["slug"], request.path_params["code"])
    except ApiError as e:
        return PlainTextResponse(e.message, status_code=e.status, headers={"Cache-Control": "no-store"})
    return PlainTextResponse(text, headers={"Cache-Control": "no-store"})


def bearer(request: Request) -> str | None:
    """The credential of an `Authorization: Bearer` header, or None."""
    scheme, _, cred = request.headers.get("authorization", "").partition(" ")
    return (cred.strip() or None) if scheme.lower() == "bearer" else None


async def agent_invite_redeem(request: Request) -> Any:
    b = await body_json(request)
    return computers.redeem(store(), request.path_params["slug"], request.path_params["code"], bearer(request),
                            b.get("computer"), b.get("product"))


# --------------------------------------------------------------------------- the computer's connection (resident program)

def computer_caller(request: Request) -> agents.Caller:
    return agents.credential_caller(store(), request.path_params["slug"], bearer(request), None, None)


async def computer_sessions(request: Request) -> Any:
    c = computer_caller(request)
    return computers.report_sessions(c, (await body_json(request)).get("sessions"))


async def computer_poll(request: Request) -> Any:
    c = computer_caller(request)
    try:
        timeout = float(request.query_params.get("timeout", "25"))
    except ValueError:
        raise bad_request("invalid_timeout", "timeout must be a number of seconds.") from None
    return await computers.poll(c, timeout, disconnect_watch(request))


async def computer_ack(request: Request) -> Any:
    c = computer_caller(request)
    return computers.ack(c, (await body_json(request)).get("deliveries"))


# --------------------------------------------------------------------------- joining

async def join(request: Request) -> Response:
    code = request.path_params["code"]
    if request.method == "POST":
        try:
            return JSONResponse(projects.accept_invite(store(), code, require_person(request)))
        except ApiError as e:
            return error_json(e)
    person = signed_in(request)
    if person is None:
        return login_redirect(request)
    try:
        return html(pages.join(tr_for(request), person, code, projects.invite_preview(store(), code)))
    except ApiError as e:
        return page_error(request, e, person)


# --------------------------------------------------------------------------- project JSON API (session cookie)

async def api_members(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.members_view(pj, actor)


async def api_invites(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.create_invite(pj, actor, (await body_json(request)).get("github_login"))


async def api_groups(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    b = await body_json(request)
    return projects.create_group(pj, actor, b.get("name"), b.get("permissions"))


async def api_member_groups(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    b = await body_json(request)
    return projects.change_groups(pj, actor, request.path_params["name"], b.get("add"), b.get("remove"))


async def api_member_remove(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.remove_member(pj, actor, request.path_params["name"])


async def api_my(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.my_view(pj, actor)


async def api_switches(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.set_switches(pj, actor, await body_json(request))


async def api_revoke(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.revoke_credential(pj, actor, request.path_params["cred"])


# --------------------------------------------------------------------------- agent API (per session)

def agent_caller(request: Request) -> agents.Caller:
    return agents.credential_caller(store(), request.path_params["slug"], bearer(request),
                                    request.headers.get("x-asterism-session"), request.headers.get("x-asterism-client"))


def agent_api(fn: Callable[[Request, agents.Caller], Awaitable[Any]], tool: str | None = "before"
              ) -> Callable[[Request], Awaitable[Response]]:
    """An agent endpoint: every answer carries the agent's unread summary. A tool (every endpoint but poll
    and ack) shows the agent itself is alive: `tool` says whether that is recorded before the call or, for
    register, after it (the session is bound by the call)."""
    async def endpoint(request: Request) -> Any:
        c = agent_caller(request)
        if tool == "before":
            agents.active(c)
        out = await fn(request, c)
        if tool == "after":
            agents.active(c)
        return agents.with_unread(c, out)
    return api(endpoint)


def disconnect_watch(request: Request) -> Callable[[], Awaitable[None]]:
    """Ends when the client goes away (killed, network gone), so a held request stops at once."""
    async def disconnected() -> None:
        while (await request.receive())["type"] != "http.disconnect":
            pass
    return disconnected


async def agent_register(request: Request, c: agents.Caller) -> Any:
    b = await body_json(request)
    return agents.register(c, b.get("name"), b.get("takeover", False))


async def agent_leave(request: Request, c: agents.Caller) -> Any:
    return agents.leave(c)


async def agent_whoami(request: Request, c: agents.Caller) -> Any:
    return agents.whoami(c)


async def agent_poll(request: Request, c: agents.Caller) -> Any:
    try:
        timeout = float(request.query_params.get("timeout", "25"))
    except ValueError:
        raise bad_request("invalid_timeout", "timeout must be a number of seconds.") from None
    # The client going away ends the poll at once, which is what turns its agent offline after the grace
    # period instead of after the full poll timeout.
    return await agents.poll(c, timeout, disconnect_watch(request))


async def agent_send(request: Request, c: agents.Caller) -> Any:
    b = await body_json(request)
    return agents.send(c, b.get("to"), b.get("text"), b.get("reply_to"))


async def agent_messages(request: Request, c: agents.Caller) -> Any:
    q = request.query_params
    return agents.messages(c, q.get("in"), q.get("id"), q.get("before"), q.get("limit"))


async def agent_wait(request: Request, c: agents.Caller) -> Any:
    return await agents.wait(c, request.query_params.get("timeout_s"), disconnect_watch(request))


async def agent_ack(request: Request, c: agents.Caller) -> Any:
    return agents.ack(c, (await body_json(request)).get("deliveries"))


# --------------------------------------------------------------------------- messages for people (session cookie)

def member_self(request: Request, slug: str) -> tuple[Project, Actor, messaging.Member]:
    pj, actor = member_actor(request, slug)
    return pj, actor, messaging.person_member(pj, actor.person_id)


async def api_channels(request: Request) -> Any:
    pj, _, me = member_self(request, request.path_params["slug"])
    return messaging.channels_view(pj, me)


async def api_channel_create(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return messaging.create_channel(pj, actor, (await body_json(request)).get("name"))


async def api_channel_mute(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    b = await body_json(request)
    return messaging.set_mute(pj, actor, request.path_params["name"], b.get("muted"), b.get("agent"))


async def api_messages(request: Request) -> Any:
    pj, _, me = member_self(request, request.path_params["slug"])
    q = request.query_params
    return messaging.person_messages(pj, me, q.get("in"), q.get("before"), q.get("after"), q.get("limit"))


async def api_post(request: Request) -> Any:
    pj, _, me = member_self(request, request.path_params["slug"])
    b = await body_json(request)
    out = messaging.send(pj, me, b.get("to"), b.get("text"), b.get("reply_to"))
    return {"id": out["id"], "mentions": out["mentions"]}


async def api_read(request: Request) -> Any:
    pj, _, me = member_self(request, request.path_params["slug"])
    b = await body_json(request)
    return messaging.mark_read(pj, me, b.get("in"), b.get("upto"))


# --------------------------------------------------------------------------- remote MCP (ChatGPT connector)

MCP_REFUSED_WINDOW_S = 60
MCP_REFUSED_MAX = 1000
# (project, reason, client) -> when (monotonic) it was last written down; insertion order is oldest first.
_mcp_refused_seen: dict[tuple[str, str, str], float] = {}


def _log_mcp_refused(request: Request, slug: str, reason: str) -> None:
    """Write down a refused connector call, the same (project, reason, client) at most once a window.
    Never the token."""
    client = util.clean_label(request.headers.get("user-agent"), 80)
    key, t = (slug, reason, client), time.monotonic()
    seen = _mcp_refused_seen
    while seen:                                   # drop what has left the window, oldest first
        oldest = next(iter(seen))
        if seen[oldest] > t - MCP_REFUSED_WINDOW_S:
            break
        del seen[oldest]
    if key in seen:
        return
    if len(seen) >= MCP_REFUSED_MAX:
        del seen[next(iter(seen))]
    seen[key] = t
    util.log("mcp_refused", project=slug, reason=reason, client=client)


def _unauthorized(request: Request, slug: str) -> Response:
    error = ', error="invalid_token"' if request.headers.get("authorization") else ""
    return JSONResponse({"error": "invalid_token" if error else "unauthorized",
                         "message": "This endpoint needs an OAuth access token; see the resource metadata."},
                        status_code=401,
                        headers={"WWW-Authenticate": f'Bearer resource_metadata="{oauth.resource_metadata_url(slug)}"{error}'})


async def mcp(request: Request) -> Response:
    slug = request.path_params["slug"]
    if store().project(slug) is None:
        return error_json(ApiError(404, "not_found", f"There is no project '{slug}'."))
    if request.method != "POST":
        return Response(status_code=405, headers={"Allow": "POST"})
    session = request.headers.get("x-openai-session")
    caller, refused = oauth.bearer_caller(store(), slug, request.headers.get("authorization"), session)
    if caller is None:
        _log_mcp_refused(request, slug, refused)
        return _unauthorized(request, slug)
    try:
        msg = json.loads(await request.body())
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error: send JSON."}},
                            status_code=400)

    def caller_for() -> agents.Caller:
        if session is not None and not tools.SESSION_HEADER_RE.fullmatch(session):
            raise bad_request("invalid_session", "The x-openai-session header is not a usable session id.")
        return caller
    answer = await tools.handle(caller_for, msg, disconnect_watch(request))
    if answer is None:
        return Response(status_code=202)
    _log_mcp_call(slug, caller, msg, answer)
    return JSONResponse(answer, headers={"Cache-Control": "no-store"})


_MCP_NAME_DROP = re.compile(r"[^A-Za-z0-9_./-]")


def _mcp_name(raw: Any) -> str | None:
    """A method or tool name fit for the log: only [A-Za-z0-9_./-], at most 40 characters."""
    return _MCP_NAME_DROP.sub("", raw)[:40] if isinstance(raw, str) else None


def _log_mcp_call(slug: str, caller: agents.Caller, msg: Any, answer: dict[str, Any]) -> None:
    """One line per authenticated JSON-RPC request: names and the outcome, never arguments, texts, tokens or
    session ids."""
    method = _mcp_name(msg.get("method")) if isinstance(msg, dict) else None
    params = msg.get("params") if isinstance(msg, dict) and isinstance(msg.get("params"), dict) else {}
    raw_tool = params.get("name") if method == "tools/call" else None
    if "error" in answer:
        known = isinstance(raw_tool, str) and raw_tool in {t["name"] for t in tools.TOOLS}
        outcome = "unknown_tool" if method == "tools/call" and not known else "error"
    else:
        outcome = "refused" if isinstance(answer.get("result"), dict) and answer["result"].get("isError") else "ok"
    try:
        a = agents.bound_agent(caller)
    except ApiError:
        a = None
    util.log("mcp_call", project=slug, person=caller.person_id, method=method,
             tool=_mcp_name(raw_tool) if method == "tools/call" else None, agent=a["name"] if a else None,
             outcome=outcome)


# --------------------------------------------------------------------------- OAuth authorization server

async def oauth_prm(request: Request) -> Response:
    slug = request.path_params["slug"]
    if store().project(slug) is None:
        return error_json(ApiError(404, "not_found", f"There is no project '{slug}'."))
    return JSONResponse(oauth.protected_resource_doc(slug))


async def oauth_asm(request: Request) -> Response:
    return JSONResponse(oauth.authorization_server_doc())


def _oauth_error(e: oauth.OAuthError) -> JSONResponse:
    return JSONResponse({"error": e.error, "error_description": e.description}, status_code=e.status,
                        headers={"Cache-Control": "no-store"})


async def oauth_register(request: Request) -> Response:
    try:
        body = json.loads(await request.body() or b"null")
    except ValueError:
        body = None
    try:
        return JSONResponse(oauth.register_client(store().accounts(), body), status_code=201,
                            headers={"Cache-Control": "no-store"})
    except oauth.OAuthError as e:
        return _oauth_error(e)


async def oauth_token(request: Request) -> Response:
    f = await body_form(request)
    basic = request.headers.get("authorization", "")
    if not f.get("client_id") and basic.lower().startswith("basic "):      # client_secret_basic with an empty secret
        try:
            f["client_id"] = urllib.parse.unquote(base64.b64decode(basic[6:]).decode("utf-8").partition(":")[0])
        except ValueError:
            pass
    try:
        return JSONResponse(oauth.token(store(), f), headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    except oauth.OAuthError as e:
        return _oauth_error(e)


CONSENT_FIELDS = ("response_type", "client_id", "redirect_uri", "state", "code_challenge", "code_challenge_method",
                  "resource", "scope")


async def oauth_authorize(request: Request) -> Response:
    """GET shows the consent page; its form posts the same parameters back with a decision."""
    tr = tr_for(request)
    p = dict(request.query_params)
    if request.method == "POST":
        p.update(await body_form(request))
    db = store().accounts()
    try:
        client, redirect = oauth.check_request(db, p)
    except oauth.Untrusted as why:
        util.log("oauth_refused", reason=str(why))
        return html(pages.message(tr, "consent.title", tr("consent.untrusted"), 400))
    problem = oauth.request_problem(p)
    if problem:
        return RedirectResponse(oauth.back_to_client(redirect, error=problem[0], error_description=problem[1],
                                                     state=p.get("state")), status_code=302)
    person = signed_in(request)
    params = {k: p[k] for k in CONSENT_FIELDS if k in p}
    if person is None:
        return login_redirect(request, "/oauth/authorize?" + urllib.parse.urlencode(params))
    pj = projects.open_project(store(), oauth.slug_of_resource(p["resource"]))
    if not projects.member(pj, person):
        return html(pages.message(tr, "consent.title", tr("consent.not_member"), 403, person=person))
    actor = Actor(person["id"])
    decision = p.get("decision")
    if request.method == "GET" or decision not in ("approve", "deny"):
        host = urllib.parse.urlsplit(redirect).hostname or redirect
        return html(pages.consent(tr, person, client["name"], host, projects.info(pj)["name"], params,
                                  projects.switches(pj, actor.person_id)))
    if decision == "deny":
        util.log("oauth_denied", client=client["client_id"], person=person["id"])
        return RedirectResponse(oauth.back_to_client(redirect, error="access_denied", state=p.get("state")), status_code=302)
    try:
        projects.require(pj, actor, "manage_own_agents", "Authorising agents needs the manage_own_agents permission.")
        if p.get("switches") == "1":        # the consent form always sends the four switches
            projects.set_switches(pj, actor, {k: p.get(k) in ("1", "on", "true") for k in projects.SWITCHES})
    except ApiError as e:
        return page_error(request, e, person)
    return RedirectResponse(oauth.approve(store(), person["id"], client, redirect, p), status_code=302)


# --------------------------------------------------------------------------- project pages

def _page_context(request: Request, slug: str):
    """(person, project, actor) for a project page, or the Response to send instead."""
    person = signed_in(request)
    if person is None:
        return login_redirect(request)
    try:
        pj = projects.open_project(store(), slug)
        actor = projects.require_member(pj, person)
    except ApiError as e:
        return page_error(request, e, person)
    return person, pj, actor


async def messages_page(request: Request) -> Response:
    """The project's address: channels and private conversations, served with the page script that talks to
    the JSON API."""
    slug = request.path_params["slug"]
    if store().project(slug) is None:
        return page_error(request, ApiError(404, "not_found", ""), signed_in(request))
    if signed_in(request) is None:      # people are asked to sign in, agents for an invitation link
        return html(pages.landing(tr_for(request), slug))
    ctx = _page_context(request, slug)
    if isinstance(ctx, Response):
        return ctx
    person, pj, actor = ctx
    me = messaging.person_member(pj, actor.person_id)
    view = {"places": messaging.channels_view(pj, me),
            "can_create": "create_channel" in projects.permissions(pj, actor),
            "people": [r["name"] for r in pj.db.execute("SELECT name FROM people WHERE person_id != ? ORDER BY name",
                                                         (actor.person_id,))],
            "agents": [r["name"] for r in pj.db.execute("SELECT name FROM agents WHERE person_id = ? ORDER BY name",
                                                         (actor.person_id,))],
            "agent_mutes": messaging.agent_mutes(pj, actor.person_id)}
    return html(pages.messages(tr_for(request), person, pj.slug, view, can_admin(pj, actor)))


async def members_page(request: Request) -> Response:
    ctx = _page_context(request, request.path_params["slug"])
    if isinstance(ctx, Response):
        return ctx
    person, pj, actor = ctx
    try:
        view = projects.members_view(pj, actor)
    except ApiError as e:
        return page_error(request, e, person)
    return html(pages.members(tr_for(request), person, view, can_admin(pj, actor)))


async def my_page(request: Request) -> Response:
    ctx = _page_context(request, request.path_params["slug"])
    if isinstance(ctx, Response):
        return ctx
    person, pj, actor = ctx
    return html(pages.my(tr_for(request), person, pj.slug, projects.my_view(pj, actor), projects.group_list(pj),
                         projects.groups_assignable(pj, actor), can_admin(pj, actor)))


async def admin_page(request: Request) -> Response:
    ctx = _page_context(request, request.path_params["slug"])
    if isinstance(ctx, Response):
        return ctx
    person, pj, actor = ctx
    if not can_admin(pj, actor):
        return page_error(request, ApiError(403, "forbidden", ""), person)
    view = {"project": projects.info(pj), **projects.people_and_agents(pj), "groups": projects.group_list(pj)}
    return html(pages.admin(tr_for(request), person, pj.slug, view, projects.permissions(pj, actor)))


# --------------------------------------------------------------------------- guard middleware

# Paths that never act on the session cookie, so a cross-site check would only get in the way of
# clients that are not browsers.
COOKIELESS_SUFFIXES = ("/mcp", "/redeem")
COOKIELESS_PREFIXES = ("/oauth/token", "/oauth/register")
COOKIELESS_PARTS = ("/api/agent/", "/api/computer/")
CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'"


class Guard:
    """Refuses cross-site state-changing requests that carry the session cookie (on top of SameSite=Lax),
    and adds the security headers to every answer."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self._cross_site(scope):
            resp = JSONResponse({"error": "forbidden", "message": "Cross-site requests are refused."}, status_code=403)
            await resp(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                names = {k.lower() for k, _ in headers}
                extra = [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"same-origin"),
                         (b"x-frame-options", b"DENY")]
                ctype = dict(headers).get(b"content-type", b"")
                if ctype.startswith(b"text/html"):
                    extra.append((b"content-security-policy", CSP.encode()))
                headers += [(k, v) for k, v in extra if k not in names]
                message["headers"] = headers
            await send(message)
        await self.app(scope, receive, send_with_headers)

    @staticmethod
    def _cross_site(scope: Scope) -> bool:
        if scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return False
        path = scope["path"]
        if path.endswith(COOKIELESS_SUFFIXES) or path.startswith(COOKIELESS_PREFIXES) \
                or any(p in path for p in COOKIELESS_PARTS):
            return False
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        if SESSION_COOKIE + "=" not in headers.get("cookie", ""):
            return False
        if headers.get("sec-fetch-site") == "cross-site":
            return True
        origin = headers.get("origin")
        if origin is None:
            return False                 # not a browser, or a browser that sends no Origin on same-origin posts
        allowed = {urllib.parse.urlsplit(config.get().public_url).netloc, headers.get("host", "")}
        return origin == "null" or urllib.parse.urlsplit(origin).netloc not in allowed


# --------------------------------------------------------------------------- the application

def build_app(s: Store) -> ASGIApp:
    global _store
    _store = s
    routes = [
        Route("/", home),
        Route("/login", login),
        Route("/login/callback", login_callback),
        Route("/logout", logout, methods=["POST"]),
        Route("/api/me", api(me)),
        Route("/static/{path:path}", static_file),
        Route("/join/{code}", join, methods=["GET", "POST"]),
        Route("/.well-known/oauth-protected-resource/{slug}/mcp", oauth_prm),
        Route("/.well-known/oauth-authorization-server", oauth_asm),
        Route("/.well-known/openid-configuration", oauth_asm),
        Route("/oauth/register", oauth_register, methods=["POST"]),
        Route("/oauth/authorize", oauth_authorize, methods=["GET", "POST"]),
        Route("/oauth/token", oauth_token, methods=["POST"]),
        Route("/dl/manifest.json", dl_manifest),
        Route("/dl/{name}", dl_file),
        Route("/install.sh", install_script),
        Route("/install.ps1", install_script),
        Route("/{slug}", messages_page),
        Route("/{slug}/a/{code}", agent_invite_page),
        Route("/{slug}/a/{code}/redeem", api(agent_invite_redeem), methods=["POST"]),
        Route("/{slug}/members", members_page),
        Route("/{slug}/my", my_page),
        Route("/{slug}/admin", admin_page),
        Route("/{slug}/mcp", mcp, methods=["GET", "POST", "DELETE"]),
        Route("/{slug}/api/members", api(api_members)),
        Route("/{slug}/api/invites", api(api_invites, 201), methods=["POST"]),
        Route("/{slug}/api/groups", api(api_groups, 201), methods=["POST"]),
        Route("/{slug}/api/members/{name}/groups", api(api_member_groups), methods=["POST"]),
        Route("/{slug}/api/members/{name}/remove", api(api_member_remove), methods=["POST"]),
        Route("/{slug}/api/my", api(api_my)),
        Route("/{slug}/api/my/switches", api(api_switches), methods=["POST"]),
        Route("/{slug}/api/my/agent-invites", api(api_agent_invites, 201), methods=["POST"]),
        Route("/{slug}/api/my/credentials/{cred:int}/revoke", api(api_revoke), methods=["POST"]),
        Route("/{slug}/api/channels", api(api_channels), methods=["GET"]),
        Route("/{slug}/api/channels", api(api_channel_create, 201), methods=["POST"]),
        Route("/{slug}/api/channels/{name}/mute", api(api_channel_mute), methods=["POST"]),
        Route("/{slug}/api/messages", api(api_messages), methods=["GET"]),
        Route("/{slug}/api/messages", api(api_post, 201), methods=["POST"]),
        Route("/{slug}/api/read", api(api_read), methods=["POST"]),
        Route("/{slug}/api/agent/register", agent_api(agent_register, "after"), methods=["POST"]),
        Route("/{slug}/api/agent/leave", agent_api(agent_leave, None), methods=["POST"]),
        Route("/{slug}/api/agent/whoami", agent_api(agent_whoami)),
        Route("/{slug}/api/agent/poll", agent_api(agent_poll, None)),
        Route("/{slug}/api/agent/send", agent_api(agent_send), methods=["POST"]),
        Route("/{slug}/api/agent/messages", agent_api(agent_messages)),
        Route("/{slug}/api/agent/wait", agent_api(agent_wait)),
        Route("/{slug}/api/agent/ack", agent_api(agent_ack, None), methods=["POST"]),
        Route("/{slug}/api/computer/sessions", api(computer_sessions), methods=["POST"]),
        Route("/{slug}/api/computer/poll", api(computer_poll)),
        Route("/{slug}/api/computer/ack", api(computer_ack), methods=["POST"]),
    ]
    if config.get().test_mode:
        routes.insert(0, Route("/test/login", test_login, methods=["POST"]))

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        task = asyncio.get_running_loop().create_task(upkeep.run(s))
        try:
            yield
        finally:
            task.cancel()
    return Guard(Starlette(routes=routes, lifespan=lifespan))
