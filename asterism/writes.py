"""Saving, deleting and renaming a file of the project's repository from the page, committed in the editor's own
name (slice 1w: the server path here; a computer the person chose writes instead when there is one, writer.py).

WHO WRITES: only the person, with their own GitHub authorization (usertokens.py). The app's installation token
(files.py) only ever reads, and nothing here can reach it: `_as_person` is the one place that makes the headers of a
request to GitHub, from the person's token alone. The token can do what the person may do and the app may do.

Who may save: a member with `read` whose permission on the repository includes push, as GitHub tells it to the person's
own token (GET /repos/{o}/{r}: permissions.push), trusted for ASTERISM_FILES_REFRESH_S. One save is one file and one
commit on the default branch (PUT /repos/{o}/{r}/contents/{path}), carrying the blob the editor started from: when
the file changed since, GitHub refuses and nothing is written (conflict, with the blob there now). A delete is one
commit too (DELETE on the contents API, with the blob read). A rename is one commit through the git data API: a tree on
the head's tree with the file under its new name and gone from its old one, a commit on the head, and the branch moved
to it without force, so a head that moved meanwhile refuses and nothing is written (conflict). After a write the
server's view of the repository follows at once (files.wrote). Every write is written down (files_write: project,
person, op, path, commit), never its content. Agents have no way to this.
"""
from __future__ import annotations

import base64
import re
import sqlite3
import time
import urllib.parse
from typing import Any

import httpx

from . import config, files, usertokens, util, writer
from .errors import ApiError, bad_request, not_found
from .projects import Project

MAX_BYTES = 5 * 1024 * 1024
MESSAGE_MOST = 200
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")

REAUTH = ("Saving to GitHub needs your GitHub authorization again: authorise again in your settings (writing shared "
          "files), then save.")
NO_PUSH = "Your GitHub account cannot push to this repository, so files cannot be saved here in your name."
REFUSED = "GitHub refused this change (for example, the branch is protected); nothing was written."
CHANGED = "The file changed on GitHub since you started; nothing was written."
GONE = "There is no such file in the repository (any more)."
# The hash a delete or a rename starts from: the blob read. Anything else of this shape is simply not the file there
# now (a conflict); the server path and the computer compare it, neither uses it otherwise.
BASE_RE = re.compile(r"[0-9A-Za-z]{1,64}")


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


async def can_write(db: sqlite3.Connection, pj: Project, address: str, person_id: int) -> dict[str, Any]:
    """Whether the person may write the repository's files from the page: their chosen computer can (writer.py), or
    GitHub says their own token may push."""
    ch = writer.chosen(pj, person_id)
    if ch is not None:
        return writer.can_write(pj, ch)
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




# --------------------------------------------------------------------------- what a request asks

def _segs(raw: Any) -> list[str]:
    segs = files.check_path(raw)
    if any(s.lower() == ".git" for s in segs):
        raise bad_request("invalid_path", "Nothing inside .git is written from here.")
    return segs


def _message(body: dict[str, Any]) -> str | None:
    message = body.get("message")
    if message is not None:
        if not isinstance(message, str) or len(message) > MESSAGE_MOST or _CONTROL_RE.search(message):
            raise bad_request("invalid_message", f"message must be one line of at most {MESSAGE_MOST} characters.")
        message = message.strip() or None
    return message


def _check_save(body: dict[str, Any]) -> tuple[list[str], bytes, str | None]:
    segs = _segs(body.get("path"))
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
    return segs, data, base


def _check_base(body: dict[str, Any]) -> str:
    base = body.get("base")
    if not isinstance(base, str) or not BASE_RE.fullmatch(base):
        raise bad_request("invalid_base", "base must be the hash of the file as you read it.")
    return base


def _checked(op: str, body: dict[str, Any]) -> dict[str, Any]:
    """The request made sure of, the same for both paths: path, to (rename), data (save), base, and the message (the
    default one when none was given)."""
    if op == "save":
        segs, data, base = _check_save(body)
        path = "/".join(segs)
        return {"segs": segs, "path": path, "data": data, "base": base,
                "message": _message(body) or (f"Edit {path} via Asterism" if base else f"Add {path} via Asterism")}
    segs = _segs(body.get("path"))
    path = "/".join(segs)
    base = _check_base(body)
    if op == "delete":
        return {"segs": segs, "path": path, "base": base, "message": _message(body) or f"Delete {path} via Asterism"}
    to_segs = _segs(body.get("to"))
    to = "/".join(to_segs)
    if to == path:
        raise bad_request("invalid_path", "to must be another path than path.")
    return {"segs": segs, "path": path, "to_segs": to_segs, "to": to, "base": base,
            "message": _message(body) or f"Rename {path} to {to} via Asterism"}


async def write(db: sqlite3.Connection, pj: Project, address: str, person_id: int, op: str,
                body: dict[str, Any]) -> dict[str, Any]:
    """One save, delete or rename (`op`) as one commit in the person's name: by their chosen computer when there is
    one (writer.py), else here with their own GitHub token."""
    checked = _checked(op, body)
    ch = writer.chosen(pj, person_id)
    if ch is not None:
        return await writer.write(pj, address, person_id, ch, op, checked)
    if op == "save":
        return await _save(db, pj.slug, address, person_id, checked)
    if op == "delete":
        return await _delete(db, pj.slug, address, person_id, checked)
    return await _rename(db, pj.slug, address, person_id, checked)


# --------------------------------------------------------------------------- the server path

def _url(repo: files.Repo, segs: list[str]) -> str:
    return _api(repo) + "/contents/" + "/".join(urllib.parse.quote(s, safe="") for s in segs)


async def _pushing(db: sqlite3.Connection, person_id: int, repo: files.Repo) -> str:
    """The default branch, when the person may push; forbidden otherwise."""
    push, ref = await _permission(db, person_id, repo)
    if not push:
        raise no_push()
    return ref


def _json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except ValueError:
        raise files.unavailable() from None


def _hash(answer: Any, *keys: str) -> str:
    """The hash at this path of keys in GitHub's answer; github_unavailable when there is none."""
    v = answer
    for k in keys:
        v = v.get(k) if isinstance(v, dict) else None
    if not isinstance(v, str) or not files.HASH_RE.fullmatch(v):
        raise files.unavailable()
    return v


def _tree_of(answer: Any) -> Any:
    commit = answer.get("commit") if isinstance(answer, dict) else None
    tree = commit.get("tree") if isinstance(commit, dict) else None
    return tree.get("sha") if isinstance(tree, dict) else None


async def _refused_why(slug: str, repo: files.Repo, segs: list[str], base: str | None) -> ApiError:
    """GitHub refused the change with 409/422. A conflict when the file is not what the editor started from (its
    hash now, or null when it is gone); otherwise GitHub refused it for another reason."""
    now = await files.blob_now(slug, repo, segs)
    if now != base:
        return ApiError(409, "conflict", CHANGED, {"current": now})
    return ApiError(403, "github_refused", REFUSED)


async def _save(db: sqlite3.Connection, slug: str, address: str, person_id: int,
                checked: dict[str, Any]) -> dict[str, Any]:
    segs, path, base = checked["segs"], checked["path"], checked["base"]
    repo = files.repo_of(address)
    ref = await _pushing(db, person_id, repo)
    put = {"message": checked["message"], "content": base64.b64encode(checked["data"]).decode("ascii"), "branch": ref}
    if base:
        put["sha"] = base
    r = await _person_call(db, person_id, "PUT", _url(repo, segs), put)
    if r.status_code in (409, 422):
        raise await _refused_why(slug, repo, segs, base)
    if r.status_code in (403, 404):                         # the permission changed since it was read
        _permissions.pop((person_id, repo), None)
        raise no_push()
    if r.status_code not in (200, 201):
        raise files.unavailable()
    answer = _json(r)
    sha, commit = _hash(answer, "content", "sha"), _hash(answer, "commit", "sha")
    util.log("files_write", project=slug, person=person_id, path=path, op="save", commit=commit, via="server")
    await files.wrote(slug, repo, ref, commit, _tree_of(answer))
    return {"commit": commit, "sha": sha}


async def _delete(db: sqlite3.Connection, slug: str, address: str, person_id: int,
                  checked: dict[str, Any]) -> dict[str, Any]:
    """One file deleted in one commit (DELETE on the contents API with the blob read): changed since, a conflict;
    gone already, not_found."""
    segs, path, base = checked["segs"], checked["path"], checked["base"]
    repo = files.repo_of(address)
    ref = await _pushing(db, person_id, repo)
    r = await _person_call(db, person_id, "DELETE", _url(repo, segs),
                           {"message": checked["message"], "sha": base, "branch": ref})
    if r.status_code in (409, 422):
        raise await _refused_why(slug, repo, segs, base)
    if r.status_code == 404 and await files.blob_now(slug, repo, segs) is None:
        raise not_found(GONE)
    if r.status_code in (403, 404):                         # the file is there: the permission changed since
        _permissions.pop((person_id, repo), None)
        raise no_push()
    if r.status_code != 200:
        raise files.unavailable()
    answer = _json(r)
    commit = _hash(answer, "commit", "sha")
    util.log("files_write", project=slug, person=person_id, path=path, op="delete", commit=commit, via="server")
    await files.wrote(slug, repo, ref, commit, _tree_of(answer))
    return {"commit": commit}


async def _rename(db: sqlite3.Connection, slug: str, address: str, person_id: int,
                  checked: dict[str, Any]) -> dict[str, Any]:
    """One commit that removes `path` and adds `to` with the same blob, through the git data API: the head read now,
    a tree on its tree, a commit on it, and the branch moved there without force (a head that moved meanwhile
    refuses: a conflict, nothing written)."""
    segs, path, to, base = checked["segs"], checked["path"], checked["to"], checked["base"]
    repo = files.repo_of(address)
    await _pushing(db, person_id, repo)
    h, (now, there) = await files.entries_now(slug, repo, [segs, checked["to_segs"]])
    if now is None or now.kind != "file":
        raise not_found(GONE)
    if now.sha != base:
        raise ApiError(409, "conflict", CHANGED, {"current": now.sha})
    if there is not None:
        raise ApiError(409, "conflict", f"There is something at {to} in the repository already; nothing was written.",
                       {"current": now.sha})
    mode = now.mode or "100644"
    git = _api(repo) + "/git"

    async def step(method: str, url: str, body: dict[str, Any], ok: int) -> Any:
        r = await _person_call(db, person_id, method, url, body)
        if r.status_code in (403, 404):
            _permissions.pop((person_id, repo), None)
            raise no_push()
        if r.status_code in (409, 422):
            raise await _moved(slug, repo, segs, base)
        if r.status_code != ok:
            raise files.unavailable()
        return _json(r)

    tree = _hash(await step("POST", git + "/trees", {"base_tree": h.tree, "tree": [
        {"path": to, "mode": mode, "type": "blob", "sha": now.sha},
        {"path": path, "mode": mode, "type": "blob", "sha": None}]}, 201), "sha")
    commit = _hash(await step("POST", git + "/commits", {"message": checked["message"], "tree": tree,
                                                          "parents": [h.commit]}, 201), "sha")
    await step("PATCH", git + "/refs/heads/" + urllib.parse.quote(h.ref, safe="/"), {"sha": commit, "force": False}, 200)
    util.log("files_write", project=slug, person=person_id, path=path, to=to, op="rename", commit=commit, via="server")
    await files.wrote(slug, repo, h.ref, commit, None)
    return {"commit": commit, "sha": now.sha}


async def _moved(slug: str, repo: files.Repo, segs: list[str], base: str) -> ApiError:
    """GitHub refused a step of a rename (409/422), above all moving the branch: it moved meanwhile. A conflict, with
    the file's blob now (not_found when it is gone); nothing was written either way."""
    now = await files.blob_now(slug, repo, segs)
    if now is None:
        return not_found(GONE)
    return ApiError(409, "conflict", CHANGED if now != base else
                    "The branch moved on GitHub while the file was being renamed; nothing was written.", {"current": now})
