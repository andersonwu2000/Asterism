"""Saving a file of the project's repository from the page, committed in the editor's own name (slice 1w, the
server path).

WHO WRITES: only the person, with their own GitHub authorization (usertokens.py). The app's installation token
(files.py) only ever reads, and nothing here can reach it: `_as_person` is the one place that makes the headers of a
request to GitHub, from the person's token alone. The token can do what the person may do and the app may do.

Who may save: a member with `read` whose permission on the repository includes push, as GitHub tells it to the person's
own token (GET /repos/{o}/{r}: permissions.push), trusted for ASTERISM_FILES_REFRESH_S. One save is one file and one
commit on the default branch (PUT /repos/{o}/{r}/contents/{path}), carrying the blob the editor started from: when
the file changed since, GitHub refuses and nothing is written (conflict, with the blob there now). After a save the
server's view of the repository follows at once (files.wrote). Every save is written down (files_write: project,
person, path, commit), never its content. Agents have no way to this.
"""
from __future__ import annotations

import base64
import re
import sqlite3
import time
import urllib.parse
from typing import Any

import httpx

from . import config, files, usertokens, util
from .errors import ApiError, bad_request

MAX_BYTES = 5 * 1024 * 1024
MESSAGE_MOST = 200
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")

REAUTH = "Saving to GitHub needs your GitHub authorization again: sign out and sign in again, then save."
NO_PUSH = "Your GitHub account cannot push to this repository, so files cannot be saved here in your name."
REFUSED = "GitHub refused this change (for example, the branch is protected); nothing was written."


def reauth() -> ApiError:
    return ApiError(409, "github_reauth", REAUTH)


def no_push() -> ApiError:
    return ApiError(403, "forbidden", NO_PUSH)


# --------------------------------------------------------------------------- talking to GitHub as the person

def _as_person(token: str) -> dict[str, str]:
    """The headers of a request made with the person's own token: the only headers a request here carries."""
    return {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}


def _limited(r: httpx.Response) -> bool:
    return r.status_code == 429 or (r.status_code == 403 and r.headers.get("x-ratelimit-remaining") == "0")


async def _call(method: str, url: str, token: str, body: dict[str, Any] | None = None) -> httpx.Response:
    try:
        return await files.client().request(method, url, headers=_as_person(token), json=body)
    except httpx.HTTPError:
        raise files.unavailable() from None


async def _person_call(db: sqlite3.Connection, person_id: int, method: str, url: str,
                       body: dict[str, Any] | None = None) -> httpx.Response:
    """A request with the person's token; a 401 is tried once more with a refreshed token. Raises github_reauth when
    there is no usable authorization, github_unavailable when GitHub does not answer."""
    try:
        token = await usertokens.token(db, person_id)
        r = await _call(method, url, token, body)
        if r.status_code == 401:
            token = await usertokens.refused(db, person_id, token)
            r = await _call(method, url, token, body)
            if r.status_code == 401:                     # refused even as it is now: the person signs in again
                usertokens.refuse(db, person_id)
                raise reauth()
    except usertokens.NoAuthorization:
        raise reauth() from None
    except usertokens.Unavailable:
        raise files.unavailable() from None
    if r.status_code >= 500 or _limited(r):
        raise files.unavailable()
    return r


def _api(repo: files.Repo) -> str:
    return f"{config.get().github_api_url}/repos/{repo.owner}/{repo.name}"


# --------------------------------------------------------------------------- who may save

# (person, repository) -> (until, may push, default branch): what GitHub said to the person's token.
_permissions: dict[tuple[int, files.Repo], tuple[float, bool, str]] = {}


def forget_person(person_id: int) -> None:
    """The person's authorization went (revoked): what was learned with it goes too."""
    for key in [k for k in _permissions if k[0] == person_id]:
        del _permissions[key]


async def _permission(db: sqlite3.Connection, person_id: int, repo: files.Repo) -> tuple[bool, str]:
    """(whether the person may push to the repository, its default branch), as GitHub tells the person's token."""
    key = (person_id, repo)
    known = _permissions.get(key)
    if known is not None and known[0] > time.monotonic():
        return known[1], known[2]
    r = await _person_call(db, person_id, "GET", _api(repo))
    push, ref = False, ""
    if r.status_code == 200:
        try:
            data = r.json()
        except ValueError:
            raise files.unavailable() from None
        perms = data.get("permissions") if isinstance(data, dict) else None
        push = isinstance(perms, dict) and perms.get("push") is True
        ref = data.get("default_branch") if isinstance(data.get("default_branch"), str) else ""
        if not ref or len(ref) > 255 or _CONTROL_RE.search(ref):
            raise files.unavailable()
    elif r.status_code not in (403, 404):                  # anything else GitHub says: it cannot see or push
        raise files.unavailable()
    _permissions[key] = (time.monotonic() + config.get().files_refresh_s, push, ref)
    return push, ref


async def can_write(db: sqlite3.Connection, slug: str, address: str, person_id: int) -> dict[str, Any]:
    repo = files.repo_of(address)
    try:
        await usertokens.token(db, person_id)
    except usertokens.NoAuthorization as e:
        return {"can_write": False, "reason": e.reason}
    except usertokens.Unavailable:
        raise files.unavailable() from None
    try:
        push, _ = await _permission(db, person_id, repo)
    except ApiError as e:
        if e.code == "github_reauth":
            return {"can_write": False, "reason": "reauth"}
        raise
    return {"can_write": True} if push else {"can_write": False, "reason": "no_push"}


# --------------------------------------------------------------------------- saving

def _check(body: dict[str, Any]) -> tuple[list[str], bytes, str | None, str | None]:
    segs = files.check_path(body.get("path"))
    if any(s.lower() == ".git" for s in segs):
        raise bad_request("invalid_path", "Nothing inside .git is saved from here.")
    content = body.get("content")
    if not isinstance(content, str):
        raise bad_request("invalid_content", "content must be the file's text.")
    try:
        data = content.encode("utf-8")
    except UnicodeEncodeError:
        raise bad_request("invalid_content", "content must be text that can be written as UTF-8.") from None
    if len(data) > MAX_BYTES:
        raise ApiError(413, "too_large", "A file saved from here is at most 5 MB.")
    base = body.get("base")
    if base is not None and (not isinstance(base, str) or not files.HASH_RE.fullmatch(base)):
        raise bad_request("invalid_base", "base must be the hash of the file the change started from, or null for a new file.")
    message = body.get("message")
    if message is not None:
        if not isinstance(message, str) or len(message) > MESSAGE_MOST or _CONTROL_RE.search(message):
            raise bad_request("invalid_message", f"message must be one line of at most {MESSAGE_MOST} characters.")
        message = message.strip() or None
    return segs, data, base, message


async def _refused_why(slug: str, repo: files.Repo, segs: list[str], base: str | None) -> ApiError:
    """GitHub refused the change with 409/422. A conflict when the file is not what the editor started from (its
    hash now, or null when it is gone); otherwise GitHub refused it for another reason."""
    now = await files.blob_now(slug, repo, segs)
    if now != base:
        return ApiError(409, "conflict", "The file changed on GitHub since you started; nothing was written.",
                        {"current": now})
    return ApiError(403, "github_refused", REFUSED)


async def save(db: sqlite3.Connection, slug: str, address: str, person_id: int, body: dict[str, Any]) -> dict[str, Any]:
    segs, data, base, message = _check(body)
    path = "/".join(segs)
    repo = files.repo_of(address)
    push, ref = await _permission(db, person_id, repo)
    if not push:
        raise no_push()
    put = {"message": message or (f"Edit {path} via Asterism" if base else f"Add {path} via Asterism"),
           "content": base64.b64encode(data).decode("ascii"), "branch": ref}
    if base:
        put["sha"] = base
    url = _api(repo) + "/contents/" + "/".join(urllib.parse.quote(s, safe="") for s in segs)
    r = await _person_call(db, person_id, "PUT", url, put)
    if r.status_code in (409, 422):
        raise await _refused_why(slug, repo, segs, base)
    if r.status_code in (403, 404):                         # the permission changed since it was read
        _permissions.pop((person_id, repo), None)
        raise no_push()
    if r.status_code not in (200, 201):
        raise files.unavailable()
    try:
        answer = r.json()
        sha, commit = answer["content"]["sha"], answer["commit"]["sha"]
    except (ValueError, KeyError, TypeError):
        raise files.unavailable() from None
    if not isinstance(sha, str) or not isinstance(commit, str) or not files.HASH_RE.fullmatch(sha) \
            or not files.HASH_RE.fullmatch(commit):
        raise files.unavailable()
    util.log("files_write", project=slug, person=person_id, path=path, commit=commit)
    tree = (answer["commit"].get("tree") or {}).get("sha") if isinstance(answer["commit"].get("tree"), dict) else None
    await files.wrote(slug, repo, ref, commit, tree)
    return {"commit": commit, "sha": sha}
