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
import sqlite3
import time
import urllib.parse
from typing import Any, AsyncIterator, Awaitable, Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response,
                                 StreamingResponse)
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import (accounts, agents, assets, avatars, computers, config, downloads, files, messaging, oauth, pages, projects,
               replays, schedules, statuses, timeline, tools, upkeep, usertokens, util, writer, writes)
from .errors import ApiError, bad_request, not_signed_in
from .i18n import LOCALES, Translator, pick_locale
from .projects import Actor, Project
from .store import Store

SESSION_COOKIE = "asterism_session"
LOGIN_COOKIE = "asterism_login"

_store: Store | None = None


def store() -> Store:
    assert _store is not None
    return _store


# --------------------------------------------------------------------------- request helpers

def tr_for(request: Request) -> Translator:
    """The pages' language: the one the signed-in person chose, else the browser's."""
    person = signed_in(request)
    return Translator(pick_locale(person["locale"] if person else None, request.headers.get("accept-language")))


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
    return JSONResponse({**e.fields, "error": e.code, "message": e.message}, status_code=e.status)


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
    """A JSON endpoint: the handler returns data or raises ApiError. A POST of a project's API with an
    Idempotency-Key is done once however often it is sent (see `idempotent`)."""
    async def answer(request: Request) -> Response:
        try:
            return JSONResponse(await fn(request), status_code=status, headers={"Cache-Control": "no-store"})
        except ApiError as e:
            return error_json(e)

    async def endpoint(request: Request) -> Response:
        raw_key, slug = request.headers.get("idempotency-key"), request.path_params.get("slug")
        if raw_key is None or request.method != "POST" or not isinstance(slug, str) \
                or not request.url.path.startswith(f"/{slug}/api/"):
            return await answer(request)
        return await idempotent(request, slug, raw_key, answer)
    return endpoint


# The requests with a key being done right now: (project, caller, key) -> set when the request is over.
_running: dict[tuple[str, str, str], asyncio.Event] = {}


def replay_scope(request: Request, db: sqlite3.Connection) -> str | None:
    """Whose keys a request's key is among: an agent's credential with its session header (the computer's
    connection: the credential alone), or a person's account. None for a caller who is nobody here."""
    if any(p in request.url.path for p in COOKIELESS_PARTS):
        cred = bearer(request)
        row = cred and db.execute("SELECT id FROM credentials WHERE digest = ? AND revoked IS NULL",
                                  (util.digest(cred),)).fetchone()
        if not row:
            return None
        return util.digest(f"credential:{row['id']}:{request.headers.get('x-asterism-session', '')}")
    person = signed_in(request)
    return None if person is None else util.digest(f"person:{person['id']}")


async def idempotent(request: Request, slug: str, raw_key: str,
                     answer: Callable[[Request], Awaitable[Response]]) -> Response:
    """The first request with a key is done and its answer (below 500) kept with the key, its path and body; the
    same request again gets that answer back, also while the first is still being done (it waits for it). The
    check, the work and keeping the answer have no await between them other than the work's own, and a second
    request with the key waits for the first, so the work is never done twice."""
    try:
        key = replays.check_key(raw_key)
    except ApiError as e:
        return error_json(e)
    body = replays.body_digest(await request.body())
    db = store().project(slug)
    scope = replay_scope(request, db) if db is not None else None
    if db is None or scope is None:
        return await answer(request)          # refused by the endpoint itself: nobody to keep an answer for
    name = (slug, scope, key)
    while True:
        kept = replays.find(db, scope, key, util.now())
        if kept is not None:
            if (kept["path"], kept["body"]) != (request.url.path, body):
                return error_json(replays.key_reused())
            return Response(kept["answer"], status_code=kept["status"], media_type="application/json",
                            headers={"Cache-Control": "no-store", "Idempotent-Replayed": "true"})
        running = _running.get(name)
        if running is None:
            break
        await running.wait()                  # then its kept answer, or (a failure, not kept) our own turn
    done = _running[name] = asyncio.Event()
    try:
        resp = await answer(request)
        # Kept with the project, unless the request deleted it (then there is nothing to keep it in).
        if resp.status_code < 500 and store().project(slug) is db:
            replays.keep(db, scope, key, request.url.path, body, resp.status_code, bytes(resp.body))
    finally:
        del _running[name]
        done.set()
    return resp


def page_error(request: Request, e: ApiError, person=None) -> Response:
    tr = tr_for(request)
    key = {"not_found": "error.not_found", "forbidden": "error.forbidden", "gone": "error.gone",
           "not_signed_in": "error.not_signed_in"}.get(e.code)
    text = tr(key) if key else tr("error.generic", code=e.code)
    return html(pages.message(tr, "error.title", text, e.status, person=person))


def can_admin(pj: Project, actor: Actor) -> bool:
    """Who may invite people: the project menu's invitation and the settings' invitations section."""
    return "manage_members" in projects.permissions(pj, actor)


# --------------------------------------------------------------------------- sign-in

async def home(request: Request) -> Response:
    person = signed_in(request)
    mine = projects.projects_of(store(), person) if person else []
    return html(pages.home(tr_for(request), person, mine))


async def login(request: Request) -> Response:
    """Sign-in: to GitHub's authorization and back to `next`. A person signed in already goes straight to `next`, unless
    they ask to authorise GitHub again (/login/github?again=1, w3: the server keeps the new token as their authorization
    to save repository files, unless a computer of theirs writes them), which runs the same authorization."""
    nxt = util.safe_next(request.query_params.get("next"))
    again = request.url.path == "/login/github" and request.query_params.get("again") == "1"
    if signed_in(request) and not again:
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
    """Test mode only (not routed otherwise): sign in as any GitHub login. `github_token`, when given, is kept as that
    person's GitHub authorization, as a real sign-in keeps the token GitHub gives (tests have no GitHub sign-in)."""
    try:
        body = await body_json(request)
    except ApiError as e:
        return error_json(e)
    login_name, token = body.get("github_login"), body.get("github_token")
    if not isinstance(login_name, str) or not util.GITHUB_LOGIN_RE.fullmatch(login_name):
        return error_json(bad_request("invalid_login", "github_login must be a GitHub login."))
    if token is not None and (not isinstance(token, str) or not usertokens.TOKEN_RE.fullmatch(token)):
        return error_json(bad_request("invalid_token", "github_token must be a token: printable, without spaces."))
    person = accounts.upsert_github(store().accounts(), "test:" + login_name.lower(), login_name)
    if token is not None:
        accounts.keep_token(store().accounts(), person["id"], {"access_token": token})
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


async def api_my_github_revoke(request: Request) -> Any:
    """The person's GitHub authorization for saving files in their name: deleted here and revoked at GitHub."""
    person = require_person(request)
    had = await usertokens.revoke(store().accounts(), person["id"])
    writes.forget_person(person["id"])
    return {"revoked": had, "state": "none"}


async def api_my_writer_state(request: Request) -> Any:
    """Who writes the person's changes to the repositories' files (the server or one of their computers, the same in
    every project), and whether the server holds their GitHub authorization (writer.py)."""
    return writer.state(store().accounts(), require_person(request)["id"])


async def api_my_writer_choose(request: Request) -> Any:
    """The account's writing computer, by its machine id, or none (the server). Choosing one deletes and revokes the
    person's GitHub token (writer.py)."""
    person = require_person(request)
    return await writer.choose_machine(store(), person["id"], (await body_json(request)).get("machine"))


async def api_my_computers(request: Request) -> Any:
    """The person's computers in every project of theirs, and their connectors (computers.mine)."""
    return computers.mine(store(), require_person(request)["id"])


async def api_my_settings(request: Request) -> Any:
    """A person's own settings, for every project: the language of the pages."""
    person = require_person(request)
    return accounts.set_settings(store().accounts(), person["id"], await body_json(request), LOCALES)


async def api_projects_create(request: Request) -> Any:
    """Anyone signed in makes a project."""
    return projects.new_project(store(), require_person(request), await body_json(request))


# --------------------------------------------------------------------------- static

STATIC_TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".woff2": "font/woff2",
                ".woff": "font/woff", ".ttf": "font/ttf",
                ".svg": "image/svg+xml"}


async def static_file(request: Request) -> Response:
    """The pages' scripts, styles, fonts and the vendored libraries. Types are fixed here (the system's guesses
    differ between machines, and the browser refuses a script of the wrong type). An address that names the file's
    present content (?v=, assets.url) is kept by the browser for good; any other is checked again each time, by its
    ETag (assets.py says why: the flash on changing pages)."""
    path = assets.resolve(request.path_params["path"])
    ctype = STATIC_TYPES.get(path.suffix) if path else None
    if ctype is None:
        return Response("not found", status_code=404, media_type="text/plain")
    body, version = assets.content(path)
    etag = f'"{version}"'
    cache = "public, max-age=31536000, immutable" if request.query_params.get("v") == version else "no-cache"
    headers = {"Cache-Control": cache, "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type=ctype, headers=headers)


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
                            b.get("computer"), b.get("product"), b.get("machine"))


# --------------------------------------------------------------------------- the computer's connection (resident program)

def computer_caller(request: Request) -> agents.Caller:
    return agents.credential_caller(store(), request.path_params["slug"], bearer(request), None, None)


async def computer_sessions(request: Request) -> Any:
    c = computer_caller(request)
    b = await body_json(request)
    return computers.report_sessions(c, b.get("sessions"), b.get("quotas"), b.get("git"), b.get("machine"),
                                     b.get("version"))


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


async def computer_write(request: Request) -> Any:
    """The program's outcome of a write it was handed (writer.py)."""
    c = computer_caller(request)
    return computers.write_answer(c, await body_json(request))


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

async def api_project_change(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.change_project(pj, actor, await body_json(request))


async def api_project_delete(request: Request) -> Any:
    """Delete the project for good. Its credentials are revoked first, which ends their open polls; those let go of
    the database in the moments after, and then its file is removed."""
    pj, actor = member_actor(request, request.path_params["slug"])
    projects.delete_project(pj, actor, (await body_json(request)).get("confirm"))
    slug = pj.slug
    await asyncio.sleep(0.2)            # the ended polls write their last mark and return
    store().drop_project(slug)
    files.forget(slug)
    return {"deleted": slug}


async def api_my_name(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.set_name(pj, actor, (await body_json(request)).get("name"))


async def api_my_avatar(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return avatars.set_mine(pj, actor, (await body_json(request)).get("image"))


async def api_agent_avatar(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return avatars.set_agent(pj, actor, request.path_params["name"], (await body_json(request)).get("image"))


async def api_avatar(request: Request) -> Response:
    """A member's avatar, to members with `read`. Its address carries the version (?v=) the views gave: that one is
    kept by the browser for good, any other is checked again by its ETag."""
    try:
        pj, actor = member_actor(request, request.path_params["slug"])
        pic = avatars.picture(pj, actor, request.path_params["kind"], request.path_params["name"])
    except ApiError as e:
        return error_json(e)
    etag = f'"{pic["version"]}"'
    same = request.query_params.get("v") == pic["version"]
    cache = "private, max-age=31536000, immutable" if same else "private, max-age=0, must-revalidate"
    headers = {"Cache-Control": cache, "ETag": etag}
    if files.etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(bytes(pic["image"]), media_type=pic["mime"], headers=headers)


async def api_members(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.members_view(pj, actor)


async def api_invites(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.create_invite(pj, actor, (await body_json(request)).get("github_login"))


async def api_invites_list(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.list_invites(pj, actor)


async def api_invite_revoke(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.revoke_invite(pj, actor, request.path_params["iid"])


async def api_groups(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    b = await body_json(request)
    return projects.create_group(pj, actor, b.get("name"), b.get("permissions"))


async def api_group_change(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.change_group_settings(pj, actor, request.path_params["name"], await body_json(request))


async def api_group_order(request: Request) -> Any:
    """The order of the groups. A group may be named "order" too: a body without `names` changes that group."""
    pj, actor = member_actor(request, request.path_params["slug"])
    b = await body_json(request)
    if "names" not in b and projects.group_by_name(pj, "order"):
        return projects.change_group_settings(pj, actor, "order", b)
    return projects.order_groups(pj, actor, b.get("names"))


async def api_presence(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.beat(pj, actor)


async def api_group_remove(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.remove_group(pj, actor, request.path_params["name"])


async def api_member_groups(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    b = await body_json(request)
    return projects.change_groups(pj, actor, request.path_params["name"], b.get("add"), b.get("remove"))


async def api_member_remove(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.remove_member(pj, actor, request.path_params["name"])


async def api_statuses(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return statuses.board(pj, actor)


async def api_my_status(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return statuses.person_set(pj, actor, await body_json(request))


async def api_agent_update_every(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return statuses.set_every(pj, actor, request.path_params["name"], await body_json(request))


async def api_my(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.my_view(pj, actor)


async def api_switches(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.set_switches(pj, actor, await body_json(request))


async def api_revoke(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return projects.revoke_credential(pj, actor, request.path_params["cred"])


# --------------------------------------------------------------------------- the project's repository (session cookie; reading,
# and saving with the reader's own GitHub authorization)

def reader(request: Request) -> tuple[Project, str]:
    """The project and its repository address, for a member with `read`."""
    pj, actor = member_actor(request, request.path_params["slug"])
    projects.require(pj, actor, "read", files.NO_READ)
    return pj, projects.info(pj)["repo"]


async def api_files_list(request: Request) -> Any:
    pj, repo = reader(request)
    return await files.listing(pj.slug, repo, request.query_params.get("dir"))


async def api_files_refresh(request: Request) -> Any:
    pj, repo = reader(request)
    return await files.refresh(pj.slug, repo)


async def api_files_find(request: Request) -> Any:
    pj, repo = reader(request)
    q = request.query_params
    return await files.find(pj.slug, repo, q.get("q"), q.get("limit"))


async def api_files_resolve(request: Request) -> Any:
    pj, repo = reader(request)
    return await files.resolve(pj.slug, repo, (await body_json(request)).get("paths"))


async def api_files_can_write(request: Request) -> Any:
    """Whether the reader may write files of the repository from the page, in their own name: with their own GitHub
    authorization, or by the computer they chose (writes.py, writer.py)."""
    pj, repo = reader(request)
    return await writes.can_write(store().accounts(), pj, repo, signed_in(request)["id"])


async def _files_write(request: Request, op: str) -> Any:
    pj, repo = reader(request)
    return await writes.write(store().accounts(), pj, repo, signed_in(request)["id"], op, await body_json(request))


async def api_files_save(request: Request) -> Any:
    """One file saved to the repository as one commit, in the reader's own name (writes.py)."""
    return await _files_write(request, "save")


async def api_files_delete(request: Request) -> Any:
    """One file deleted from the repository as one commit, in the reader's own name (writes.py)."""
    return await _files_write(request, "delete")


async def api_files_rename(request: Request) -> Any:
    """One file renamed in the repository as one commit, in the reader's own name (writes.py)."""
    return await _files_write(request, "rename")


async def api_my_writer(request: Request) -> Any:
    """The shortcut that chooses the machine of one of the reader's computers in this project as the account's writer,
    or none (the server, with their own GitHub authorization). Choosing one deletes and revokes their GitHub token
    (writer.py)."""
    pj, actor = member_actor(request, request.path_params["slug"])
    return await writer.choose(pj, actor, (await body_json(request)).get("credential"))


async def api_files_raw(request: Request) -> Response:
    """A file's bytes, typed from a fixed table and never as HTML; whatever it holds cannot act on this origin."""
    try:
        pj, repo = reader(request)
        out = await files.raw(pj.slug, repo, request.path_params["path"], request.headers.get("if-none-match"))
    except ApiError as e:
        resp = error_json(e)
        resp.headers.update(files.headers_for(""))
        return resp
    if isinstance(out, str):
        return Response(status_code=304, headers=dict(files.headers_for(""), ETag=out))
    headers = dict(files.headers_for(out.ctype), ETag=f'"{out.sha}"', **{"Content-Length": str(out.size)})
    if out.attachment:
        headers["Content-Disposition"] = "attachment; filename*=UTF-8''" + urllib.parse.quote(out.name, safe="")
    return StreamingResponse(files.stream(out.file, out.size), media_type=out.ctype, headers=headers)


# --------------------------------------------------------------------------- agent API (per session)

def agent_caller(request: Request) -> agents.Caller:
    return agents.credential_caller(store(), request.path_params["slug"], bearer(request),
                                    request.headers.get("x-asterism-session"), request.headers.get("x-asterism-client"),
                                    request.headers.get("x-asterism-model"))


def agent_api(fn: Callable[[Request, agents.Caller], Awaitable[Any]], tool: str | None = "before"
              ) -> Callable[[Request], Awaitable[Response]]:
    """An agent endpoint: every answer carries the agent's unread summary. A tool (every endpoint but poll
    and ack) shows the agent itself is alive: `tool` says whether that is recorded before the call or, for
    register, after it (the session is bound by the call)."""
    async def endpoint(request: Request) -> Any:
        c = agent_caller(request)
        agents.note_model(c)            # first: a message sent by this call carries the model said with it
        if tool == "before":
            agents.active(c)
        out = await fn(request, c)
        if tool == "after":
            agents.note_model(c)        # register binds the session by the call
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
    return agents.messages(c, q.get("in"), q.get("id"), q.get("before"), q.get("limit"), q.get("all"))


async def agent_wait(request: Request, c: agents.Caller) -> Any:
    return await agents.wait(c, request.query_params.get("timeout_s"), disconnect_watch(request))


async def agent_statuses(request: Request, c: agents.Caller) -> Any:
    return agents.status_list(c)


async def agent_status(request: Request, c: agents.Caller) -> Any:
    return agents.set_status(c, await body_json(request))


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


async def api_channel_rename(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return messaging.rename_channel(pj, actor, request.path_params["name"], (await body_json(request)).get("name"))


async def api_channel_delete(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return messaging.delete_channel(pj, actor, request.path_params["name"])


async def api_channel_permissions(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    if request.method == "POST":
        return messaging.set_channel_permissions(pj, actor, request.path_params["name"],
                                                 (await body_json(request)).get("overrides"))
    return messaging.channel_permissions(pj, actor, request.path_params["name"])


async def api_channel_mute(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    b = await body_json(request)
    return messaging.set_mute(pj, actor, request.path_params["name"], b.get("muted"), b.get("agent"))


async def api_schedules(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return schedules.listing(pj, actor)


async def api_schedule_create(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return schedules.create(pj, actor, await body_json(request))


async def api_schedule_change(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return schedules.change(pj, actor, request.path_params["sid"], await body_json(request))


async def api_schedule_remove(request: Request) -> Any:
    pj, actor = member_actor(request, request.path_params["slug"])
    return schedules.remove(pj, actor, request.path_params["sid"])


async def api_messages(request: Request) -> Any:
    pj, _, me = member_self(request, request.path_params["slug"])
    q = request.query_params
    return messaging.person_messages(pj, me, q.get("in"), q.get("before"), q.get("after"), q.get("limit"))


async def api_agent_timeline(request: Request) -> Any:
    """One agent's timeline (the agent page): its messages and changes of state, as far as the reader may read them."""
    pj, actor = member_actor(request, request.path_params["slug"])
    q = request.query_params
    return timeline.timeline(pj, actor, request.path_params["name"], q.get("before"), q.get("limit"), q.get("only"))


async def api_search(request: Request) -> Any:
    """Search over the messages the person may read (people only; agents have no such tool): the channels they may
    read, and their private conversations with the project's read permission."""
    pj, actor, me = member_self(request, request.path_params["slug"])
    q = request.query_params
    return messaging.search(pj, me, q.get("q"), q.get("in"), q.get("from"), q.get("before"), q.get("limit"))


async def api_post(request: Request) -> Any:
    pj, _, me = member_self(request, request.path_params["slug"])
    b = await body_json(request)
    out = messaging.send(pj, me, b.get("to"), b.get("text"), b.get("reply_to"))
    # `waiting` (1h): the agents it waits for, when there are any.
    return {k: out[k] for k in ("id", "mentions", "waiting") if k in out}


async def api_react(request: Request) -> Any:
    pj, _, me = member_self(request, request.path_params["slug"])
    b = await body_json(request)
    return messaging.react(pj, me, request.path_params["mid"], b.get("emoji"), b.get("on"))


async def api_edit(request: Request) -> Any:
    pj, _, me = member_self(request, request.path_params["slug"])
    return messaging.edit(pj, me, request.path_params["mid"], (await body_json(request)).get("text"))


async def api_delete_message(request: Request) -> Any:
    pj, _, me = member_self(request, request.path_params["slug"])
    return messaging.delete(pj, me, request.path_params["mid"])


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
        if request.headers.get("authorization"):       # a deleted project's token is refused as a revoked one
            _log_mcp_refused(request, slug, "no_project")
            return _unauthorized(request, slug)
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
    answer = await tools.handle(caller_for, msg, disconnect_watch(request),
                                codex=tools.from_codex(request.headers.get("user-agent")))
    if answer is None:
        return Response(status_code=202)
    _log_mcp_call(request, slug, caller, msg, answer)
    return JSONResponse(answer, headers={"Cache-Control": "no-store"})


_MCP_NAME_DROP = re.compile(r"[^A-Za-z0-9_./-]")


def _mcp_name(raw: Any) -> str | None:
    """A method or tool name fit for the log: only [A-Za-z0-9_./-], at most 40 characters."""
    return _MCP_NAME_DROP.sub("", raw)[:40] if isinstance(raw, str) else None


def _printable(raw: Any, most: int) -> str:
    """Text fit for the log: its printable characters only, at most `most` of them."""
    return "".join(c for c in str(raw) if c.isprintable())[:most]


MCP_LIST_MOST = 30                  # header names, _meta keys: at most this many in a log line


def _who_calls(request: Request, method: str | None, params: dict[str, Any]) -> dict[str, Any]:
    """Who calls the connector, for the log (1q): the user agent, the names of the x- headers, the client's name at
    initialize, the key names of a tool call's _meta. Never a value but the user agent's; the values only while the
    server traces (ASTERISM_MCP_TRACE=1), the session id then only as the start of its digest, and never the
    Authorization header or a cookie (neither begins with x-)."""
    xs = sorted({_printable(k.lower(), 60): v for k, v in request.headers.items() if k.lower().startswith("x-")}.items())
    xs = xs[:MCP_LIST_MOST]
    out: dict[str, Any] = {"ua": _printable(request.headers.get("user-agent", ""), 80), "hdr": [k for k, _ in xs]}
    info = params.get("clientInfo") if method == "initialize" else None
    if isinstance(info, dict) and isinstance(info.get("name"), str) and info["name"]:
        version = info.get("version")
        out["client"] = _printable(info["name"] + (f"/{version}" if isinstance(version, str) and version else ""), 80)
    meta = params.get("_meta") if method == "tools/call" else None
    keys = sorted(meta)[:MCP_LIST_MOST] if isinstance(meta, dict) else None
    if keys is not None:
        out["meta"] = [_printable(k, 60) for k in keys]
    if config.get().mcp_trace:
        def shown(k: str, v: str) -> str:
            return util.digest(v)[:8] if k == "x-openai-session" else _printable(v, 120)

        def value(v: Any) -> Any:
            if isinstance(v, str):
                return _printable(v, 120)
            if isinstance(v, (bool, int, float)):
                return v
            return json.dumps(v, ensure_ascii=False, default=str)[:200]
        out["trace"] = {"hdr": {k: shown(k, v) for k, v in xs}}
        if keys is not None:
            out["trace"]["meta"] = {_printable(k, 60): value(meta[k]) for k in keys}
    return out


def _log_mcp_call(request: Request, slug: str, caller: agents.Caller, msg: Any, answer: dict[str, Any]) -> None:
    """One line per authenticated JSON-RPC request: names and the outcome, with who calls (_who_calls), never
    arguments, texts, tokens or session ids."""
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
             outcome=outcome, **_who_calls(request, method, params))


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
        if p.get("switches") == "1":        # the consent form always sends every switch
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
    # In a project's pages the reader is shown by the name they have in that project.
    return {**dict(person), "name": projects.person_name(pj, actor.person_id)}, pj, actor


def _frame(pj: Project, actor: Actor) -> dict[str, Any]:
    """What the project's frame (the rail and the second column on every page of a project) shows: the places with
    their unread counts and the number of messages important for the reader, the members to start a private
    conversation with, who may create a channel or see the settings, and each member's kind, presence, owner and
    avatar for the presence marks and pictures."""
    me = messaging.person_member(pj, actor.person_id)
    mine = projects.permissions(pj, actor)
    pa = projects.people_and_agents(pj, work=True)
    directory = {x["name"]: {"kind": "person", "online": x["online"], "avatar": x["avatar"], "status": x["status"]}
                 for x in pa["people"]}
    directory.update({a["name"]: {"kind": "agent", "online": a["online"], "owner": a["owner"], "work": a["work"],
                                  "status": a["status"], "avatar": a["avatar"]}
                      for a in pa["agents"]})
    info = projects.info(pj)
    # The channels the reader may read (an override may grant one without the project's read), and private
    # conversations with the project's read.
    places = messaging.channels_view(pj, me)
    return {"slug": pj.slug, "name": info["name"], "repo": info["repo"], "notice_channel": "#" + projects.notice_channel(pj),
            # The address ChatGPT adds as a connector (dot joins that way, not by a link; 1i).
            "connector": f"{config.get().public_url}/{pj.slug}/mcp",
            "places": places, "beat_s": config.get().person_beat_s,
            "important": sum(c["important"] for c in places["channels"]),
            # 1g: the private button counts the conversations with people, the agent button those with agents.
            "important_private": sum(p["important"] for p in places["private"] if p["kind"] == "person"),
            "important_agents": sum(p["important"] for p in places["private"] if p["kind"] == "agent"),
            # 2a: and what is unread there, not muted for the reader (a muted channel only with what is important).
            "unread": sum(c["important"] if c["muted"] else c["unread"] for c in places["channels"]),
            "unread_private": sum(p["unread"] for p in places["private"] if p["kind"] == "person"),
            "unread_agents": sum(p["unread"] for p in places["private"] if p["kind"] == "agent"),
            "can_create": "create_channel" in mine, "can_admin": can_admin(pj, actor),
            "perms": [p for p in projects.PERMISSIONS if p in mine],
            "people": [r["name"] for r in pj.db.execute("SELECT name FROM people WHERE person_id != ? ORDER BY name",
                                                         (actor.person_id,))],
            "agents": [r["name"] for r in pj.db.execute("SELECT name FROM agents WHERE person_id = ? ORDER BY name",
                                                         (actor.person_id,))],
            "directory": directory}


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
    mine = projects.permissions(pj, actor)
    view = {"can_manage_channels": "manage_channels" in mine}
    return html(pages.messages(tr_for(request), person, _frame(pj, actor), view))


async def dm_page(request: Request) -> Response:
    """Private messages: the conversations in the second column and one of them (/{slug}/dm/{name}), with the same
    composer as chat. A name one cannot write to privately is not found (or forbidden), as the API says."""
    ctx = _page_context(request, request.path_params["slug"])
    if isinstance(ctx, Response):
        return ctx
    person, pj, actor = ctx
    name = request.path_params.get("name", "")
    # 1g: a conversation with an agent lives on the agent page; its old address leads there, for anybody.
    if name and pj.db.execute("SELECT 1 FROM agents WHERE name = ?", (name,)).fetchone():
        to = f"/{urllib.parse.quote(pj.slug)}/agent?name={urllib.parse.quote(name)}"
        m = request.query_params.get("m", "")
        if re.fullmatch(r"\d{1,18}", m):
            to += f"&m={m}"
        return RedirectResponse(to, status_code=303)
    tr = tr_for(request)
    me = messaging.person_member(pj, actor.person_id)
    try:
        messaging.require_read(pj, me)
    except ApiError as e:
        return page_error(request, e, person)
    view = {"can_manage_channels": False}
    if name:
        # A conversation that cannot be had is answered inside the frame, saying who may have it (m1f7 section 4).
        try:
            messaging.resolve_place(pj, me, name)
        except ApiError as e:
            other = messaging.member_by_name(pj, name)
            if e.status == 403 and other is not None and other.kind == "agent":
                said = tr("dm.refused_agent", name=other.name, owner=projects.person_name(pj, other.person_id))
            elif e.status in (403, 404):
                said = tr("dm.refused_none", name=name) if other is None else tr("error.forbidden")
            else:
                return page_error(request, e, person)
            return html(pages.messages(tr, person, _frame(pj, actor), view, dm=name, refused=(said, e.status)))
    return html(pages.messages(tr, person, _frame(pj, actor), view, dm=name))


async def agents_page(request: Request) -> Response:
    """The agent page (/{slug}/agent, and the former /{slug}/my): every agent of the project and one agent's timeline.
    Which agent is chosen is in the query and is the page script's business."""
    ctx = _page_context(request, request.path_params["slug"])
    if isinstance(ctx, Response):
        return ctx
    person, pj, actor = ctx
    return html(pages.agent(tr_for(request), person, _frame(pj, actor)))


def _work_page(request: Request, tab: str) -> Response:
    """The work page at one of its tabs: the dashboard (/{slug}/work, and the former /{slug}/agent/tasks) and scheduled
    messages (/{slug}/work/schedules, and the former /{slug}/agent/schedules and /{slug}/schedules). The scope of a
    tab is in the query and is the page script's business."""
    ctx = _page_context(request, request.path_params["slug"])
    if isinstance(ctx, Response):
        return ctx
    person, pj, actor = ctx
    mine = projects.permissions(pj, actor)
    view = {"can_create": {"create_schedule", "post"} <= mine, "can_manage": "manage_members" in mine}
    if tab == "schedules":
        view["min_every_s"] = config.get().schedule_min_every_s
        view["places"] = {"channels": messaging.channel_names(pj, messaging.person_member(pj, actor.person_id)),
                          "people": [r["name"] for r in pj.db.execute(
                              "SELECT name FROM people WHERE person_id != ? ORDER BY name", (actor.person_id,))],
                          "agents": [r["name"] for r in pj.db.execute(
                              "SELECT name FROM agents WHERE person_id = ? ORDER BY name", (actor.person_id,))]}
    return html(pages.work(tr_for(request), person, _frame(pj, actor), tab, view))


async def dashboard_page(request: Request) -> Response:
    return _work_page(request, "dashboard")


async def schedules_page(request: Request) -> Response:
    return _work_page(request, "schedules")


def _settings(request: Request, scope: str, section: str, channel: str | None = None) -> Response:
    """The settings layer (the project, one channel, or the reader's own) at `section` ("" for the bare address).
    Every member may open it; the invitations are for who may invite, and an unknown section or channel (or one the
    reader may not read) is not found."""
    ctx = _page_context(request, request.path_params["slug"])
    if isinstance(ctx, Response):
        return ctx
    person, pj, actor = ctx
    frame = _frame(pj, actor)
    try:
        view = projects.members_view(pj, actor)
        if section and section not in pages.settings_sections(scope, True):
            raise ApiError(404, "not_found", "")
        if section and section not in pages.settings_sections(scope, frame["can_admin"]):
            raise ApiError(403, "forbidden", "")
        here = None
        if channel is not None:
            here = next((c for c in frame["places"]["channels"] if c["name"] == channel), None)
            if here is None:
                raise ApiError(404, "not_found", "")
            here = {"name": channel, "muted": here["muted"],
                    "agent_mutes": messaging.agent_mutes(pj, actor.person_id).get(channel, []),
                    "notices": projects.notice_channel(pj) == channel}
        me = None
        if scope == "me":
            acc = accounts.person(store().accounts(), actor.person_id)
            row = pj.db.execute("SELECT status_title FROM people WHERE person_id = ?", (actor.person_id,)).fetchone()
            me = {"name": projects.person_name(pj, actor.person_id), "github_login": acc["github_login"],
                  "status": row["status_title"] if row else "",
                  "my": projects.my_view(pj, actor), "computers": computers.mine(store(), actor.person_id),
                  "writer": writer.state(store().accounts(), actor.person_id)}
    except ApiError as e:
        return page_error(request, e, person)
    return html(pages.settings(tr_for(request), person, frame, scope, section, view, projects.PERMISSIONS,
                               projects.MANAGEMENT, here, me))


async def me_page(request: Request) -> Response:
    """The reader's own settings: their name here, language and look, computers and connectors, what others may do
    with their agents (/{slug}/me, /{slug}/me/{section})."""
    return _settings(request, "me", request.path_params.get("section", ""))


async def settings_page(request: Request) -> Response:
    return _settings(request, "project", request.path_params.get("section", ""))


async def channel_settings_page(request: Request) -> Response:
    return _settings(request, "channel", request.path_params.get("section", ""), request.path_params["name"])


async def members_page(request: Request) -> Response:
    """The former members page: the settings layer at members, or at groups when the address names one (?g=)."""
    return _settings(request, "project", "groups" if request.query_params.get("g") else "members")


async def admin_page(request: Request) -> Response:
    """The former settings page: the settings layer at the invitations."""
    return _settings(request, "project", "invites")


async def files_page(request: Request) -> Response:
    """Files mode, for a member with `read`: a shell that reads the repository through the files API. The address
    may name a file (/{slug}/files/{path}); a path that cannot be one is not found."""
    ctx = _page_context(request, request.path_params["slug"])
    if isinstance(ctx, Response):
        return ctx
    person, pj, actor = ctx
    if "read" not in projects.permissions(pj, actor):
        return page_error(request, ApiError(403, "forbidden", ""), person)
    path = request.path_params.get("path", "")
    if path and files.split_path(path) is None:
        return page_error(request, ApiError(404, "not_found", ""), person)
    page = html(pages.files(tr_for(request), person, _frame(pj, actor), path,
                            int(config.get().files_max_mb * 1024 * 1024)))
    page.headers["Content-Security-Policy"] = FILES_CSP
    return page


# --------------------------------------------------------------------------- guard middleware

# Paths that never act on the session cookie, so a cross-site check would only get in the way of
# clients that are not browsers.
COOKIELESS_SUFFIXES = ("/mcp", "/redeem")
COOKIELESS_PREFIXES = ("/oauth/token", "/oauth/register")
COOKIELESS_PARTS = ("/api/agent/", "/api/computer/")
# frame-src: files mode shows a PDF of the repository in a frame of this origin (the raw endpoint allows only that).
CSP = (f"default-src 'self'; script-src 'self' {pages.THEME_CSP}; style-src 'self' 'unsafe-inline'; img-src 'self'; "
       "frame-src 'self'; frame-ancestors 'none'; base-uri 'none'")
# The files page alone also shows a picture or a PDF of the reader's local folder, through an object URL made in the
# browser (blob:): for pictures and frames, and nowhere else. The Guard keeps a page's own policy.
FILES_CSP = CSP.replace("img-src 'self';", "img-src 'self' blob:;").replace("frame-src 'self';", "frame-src 'self' blob:;")
assert FILES_CSP.count("blob:") == 2


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
        Route("/login/github", login),
        Route("/login/callback", login_callback),
        Route("/logout", logout, methods=["POST"]),
        Route("/api/me", api(me)),
        Route("/api/me/settings", api(api_my_settings), methods=["POST"]),
        Route("/api/me/github/revoke", api(api_my_github_revoke), methods=["POST"]),
        Route("/api/me/writer", api(api_my_writer_state), methods=["GET"]),
        Route("/api/me/writer", api(api_my_writer_choose), methods=["POST"]),
        Route("/api/me/computers", api(api_my_computers), methods=["GET"]),
        Route("/api/projects", api(api_projects_create, 201), methods=["POST"]),
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
        Route("/{slug}/my", agents_page),
        Route("/{slug}/agent", agents_page),
        Route("/{slug}/agent/tasks", dashboard_page),
        Route("/{slug}/agent/schedules", schedules_page),
        Route("/{slug}/work", dashboard_page),
        Route("/{slug}/work/schedules", schedules_page),
        Route("/{slug}/admin", admin_page),
        Route("/{slug}/settings", settings_page),
        Route("/{slug}/settings/{section}", settings_page),
        Route("/{slug}/channels/{name}/settings", channel_settings_page),
        Route("/{slug}/channels/{name}/settings/{section}", channel_settings_page),
        Route("/{slug}/schedules", schedules_page),
        Route("/{slug}/me", me_page),
        Route("/{slug}/me/{section}", me_page),
        Route("/{slug}/dm", dm_page),
        Route("/{slug}/dm/{name}", dm_page),
        Route("/{slug}/files", files_page),
        Route("/{slug}/files/{path:path}", files_page),
        Route("/{slug}/mcp", mcp, methods=["GET", "POST", "DELETE"]),
        Route("/{slug}/api/project", api(api_project_change), methods=["POST"]),
        Route("/{slug}/api/project/delete", api(api_project_delete), methods=["POST"]),
        Route("/{slug}/api/me/name", api(api_my_name), methods=["POST"]),
        Route("/{slug}/api/me/status", api(api_my_status), methods=["POST"]),
        Route("/{slug}/api/me/avatar", api(api_my_avatar), methods=["POST"]),
        Route("/{slug}/api/agents/{name}/avatar", api(api_agent_avatar), methods=["POST"]),
        Route("/{slug}/api/agents/{name}/update-every", api(api_agent_update_every), methods=["POST"]),
        Route("/{slug}/api/avatars/{kind}/{name}", api_avatar, methods=["GET"]),
        Route("/{slug}/api/members", api(api_members)),
        Route("/{slug}/api/invites", api(api_invites, 201), methods=["POST"]),
        Route("/{slug}/api/invites", api(api_invites_list), methods=["GET"]),
        Route("/{slug}/api/invites/{iid}/revoke", api(api_invite_revoke), methods=["POST"]),
        Route("/{slug}/api/groups", api(api_groups, 201), methods=["POST"]),
        Route("/{slug}/api/groups/order", api(api_group_order), methods=["POST"]),
        Route("/{slug}/api/groups/{name}", api(api_group_change), methods=["POST"]),
        Route("/{slug}/api/groups/{name}/remove", api(api_group_remove), methods=["POST"]),
        Route("/{slug}/api/members/{name}/groups", api(api_member_groups), methods=["POST"]),
        Route("/{slug}/api/members/{name}/remove", api(api_member_remove), methods=["POST"]),
        Route("/{slug}/api/my", api(api_my)),
        Route("/{slug}/api/my/switches", api(api_switches), methods=["POST"]),
        Route("/{slug}/api/my/agent-invites", api(api_agent_invites, 201), methods=["POST"]),
        Route("/{slug}/api/my/credentials/{cred:int}/revoke", api(api_revoke), methods=["POST"]),
        Route("/{slug}/api/channels", api(api_channels), methods=["GET"]),
        Route("/{slug}/api/channels", api(api_channel_create, 201), methods=["POST"]),
        Route("/{slug}/api/channels/{name}", api(api_channel_rename), methods=["POST"]),
        Route("/{slug}/api/channels/{name}/delete", api(api_channel_delete), methods=["POST"]),
        Route("/{slug}/api/channels/{name}/permissions", api(api_channel_permissions), methods=["GET", "POST"]),
        Route("/{slug}/api/channels/{name}/mute", api(api_channel_mute), methods=["POST"]),
        Route("/{slug}/api/schedules", api(api_schedules), methods=["GET"]),
        Route("/{slug}/api/schedules", api(api_schedule_create, 201), methods=["POST"]),
        Route("/{slug}/api/schedules/{sid:int}", api(api_schedule_change), methods=["POST"]),
        Route("/{slug}/api/schedules/{sid:int}/remove", api(api_schedule_remove), methods=["POST"]),
        Route("/{slug}/api/messages", api(api_messages), methods=["GET"]),
        Route("/{slug}/api/messages", api(api_post, 201), methods=["POST"]),
        Route("/{slug}/api/messages/{mid:int}/react", api(api_react), methods=["POST"]),
        Route("/{slug}/api/messages/{mid:int}/edit", api(api_edit), methods=["POST"]),
        Route("/{slug}/api/messages/{mid:int}/delete", api(api_delete_message), methods=["POST"]),
        Route("/{slug}/api/read", api(api_read), methods=["POST"]),
        Route("/{slug}/api/search", api(api_search), methods=["GET"]),
        Route("/{slug}/api/agents/{name}/timeline", api(api_agent_timeline), methods=["GET"]),
        Route("/{slug}/api/files/list", api(api_files_list), methods=["GET"]),
        Route("/{slug}/api/files/raw/{path:path}", api_files_raw, methods=["GET"]),
        Route("/{slug}/api/files/resolve", api(api_files_resolve), methods=["POST"]),
        Route("/{slug}/api/files/find", api(api_files_find), methods=["GET"]),
        Route("/{slug}/api/files/refresh", api(api_files_refresh), methods=["POST"]),
        Route("/{slug}/api/files/can-write", api(api_files_can_write), methods=["GET"]),
        Route("/{slug}/api/files/save", api(api_files_save), methods=["POST"]),
        Route("/{slug}/api/files/delete", api(api_files_delete), methods=["POST"]),
        Route("/{slug}/api/files/rename", api(api_files_rename), methods=["POST"]),
        Route("/{slug}/api/me/writer", api(api_my_writer), methods=["POST"]),
        Route("/{slug}/api/presence", api(api_presence), methods=["POST"]),
        Route("/{slug}/api/statuses", api(api_statuses), methods=["GET"]),
        Route("/{slug}/api/agent/register", agent_api(agent_register, "after"), methods=["POST"]),
        Route("/{slug}/api/agent/leave", agent_api(agent_leave, None), methods=["POST"]),
        Route("/{slug}/api/agent/whoami", agent_api(agent_whoami)),
        Route("/{slug}/api/agent/poll", agent_api(agent_poll, None)),
        Route("/{slug}/api/agent/send", agent_api(agent_send), methods=["POST"]),
        Route("/{slug}/api/agent/messages", agent_api(agent_messages)),
        Route("/{slug}/api/agent/wait", agent_api(agent_wait)),
        Route("/{slug}/api/agent/statuses", agent_api(agent_statuses)),
        Route("/{slug}/api/agent/status", agent_api(agent_status), methods=["POST"]),
        Route("/{slug}/api/agent/ack", agent_api(agent_ack, None), methods=["POST"]),
        Route("/{slug}/api/computer/sessions", api(computer_sessions), methods=["POST"]),
        Route("/{slug}/api/computer/poll", api(computer_poll)),
        Route("/{slug}/api/computer/ack", api(computer_ack), methods=["POST"]),
        Route("/{slug}/api/computer/write", api(computer_write), methods=["POST"]),
    ]
    if config.get().test_mode:
        routes.insert(0, Route("/test/login", test_login, methods=["POST"]))

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        upkeep.server_started(s)        # before any request and before the background task's first look
        task = asyncio.get_running_loop().create_task(upkeep.run(s))
        try:
            yield
        finally:
            task.cancel()
            await files.close()
    return Guard(Starlette(routes=routes, lifespan=lifespan))
