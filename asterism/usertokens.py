"""A person's GitHub authorization, kept so that a repository file saved in the page is committed in their own name
(slice 1w, the server path; writes.py uses it).

Sign-in goes through the GitHub App's user authorization: the token GitHub gives then can do what the person may do
and the App may do, no more. It is kept in the accounts database, encrypted with Fernet (`cryptography`, imported here
only), with its refresh token and expiry when GitHub gives them. The key is a file, ASTERISM_TOKEN_KEY_FILE (default
DATA/token.key), made on first use with mode 0600 where the system has modes; it is never served. A lost or changed
key makes the kept tokens unreadable: they count as not kept, and the next sign-in keeps a new one.

A token close to its expiry is refreshed with its refresh token (one refresh at a time per person: a refresh token
is good once). GitHub refusing the token, or refusing to refresh it, marks it refused: the person signs in again
(`github_reauth`). Revoking deletes it and asks GitHub to revoke it; signing out does not revoke.

NOTHING HERE IS EVER LOGGED, PRINTED OR RETURNED TO A CLIENT. `token()` hands the token to its caller only to put it
in the Authorization header of one request to GitHub.
"""
from __future__ import annotations

import asyncio
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import httpx

from . import config, util

REFRESH_MARGIN_S = 300          # a token is refreshed this long before it expires
TIMEOUT = httpx.Timeout(20, connect=5)
TOKEN_RE = re.compile(r"[\x21-\x7e]{1,1024}")     # what GitHub's tokens look like: printable, no spaces


class NoAuthorization(Exception):
    """No usable authorization: `reason` is "no_token" (none kept) or "reauth" (GitHub refused it)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class Unavailable(Exception):
    """GitHub did not answer a refresh usefully (no answer, 5xx): try again later; nothing was changed."""


# --------------------------------------------------------------------------- the key

_fernets: dict[str, Any] = {}


def key_path() -> Path:
    s = config.get()
    return Path(s.token_key_file) if s.token_key_file else s.data / "token.key"


def _read_or_make_key(path: Path) -> bytes:
    """The key in the file, made first when there is none: created exclusively, mode 0600, never overwritten."""
    try:
        return path.read_bytes().strip()
    except FileNotFoundError:
        pass
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    except FileExistsError:                       # made meanwhile by another start: that one is the key
        return path.read_bytes().strip()
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    util.log("token_key_created")
    return key


def _fernet():
    path = key_path()
    f = _fernets.get(str(path))
    if f is None:
        from cryptography.fernet import Fernet
        f = _fernets[str(path)] = Fernet(_read_or_make_key(path))
    return f


def _seal(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def _open(sealed: str | None) -> str | None:
    """The secret, or None when it cannot be read with the key there is now."""
    if not sealed:
        return None
    from cryptography.fernet import InvalidToken
    try:
        return _fernet().decrypt(sealed.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        return None


# --------------------------------------------------------------------------- keeping

def _number(raw: Any) -> float | None:
    return float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0 else None


def keep(db: sqlite3.Connection, person_id: int, answer: dict[str, Any]) -> bool:
    """Keep the token of GitHub's answer to a code or refresh exchange (access_token, and expires_in, refresh_token,
    refresh_token_expires_in when given) as this person's authorization, in place of any before. False when the
    answer holds no usable token."""
    token, refresh = answer.get("access_token"), answer.get("refresh_token")
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        return False
    if not isinstance(refresh, str) or not TOKEN_RE.fullmatch(refresh):
        refresh = None
    now = util.now()
    life, refresh_life = _number(answer.get("expires_in")), _number(answer.get("refresh_token_expires_in"))
    row = (_seal(token), now + life if life else None, _seal(refresh) if refresh else None,
           now + refresh_life if refresh and refresh_life else None, now)
    with db:
        db.execute("INSERT INTO github_tokens (person_id, token, expires, refresh, refresh_expires, created, refused) "
                   "VALUES (?, ?, ?, ?, ?, ?, NULL) ON CONFLICT(person_id) DO UPDATE SET token = excluded.token, "
                   "expires = excluded.expires, refresh = excluded.refresh, refresh_expires = excluded.refresh_expires, "
                   "created = excluded.created, refused = NULL", (person_id, *row))
    return True


def state(db: sqlite3.Connection, person_id: int) -> str:
    """What the person's settings show: "kept", "refused" (sign in again) or "none"."""
    row = db.execute("SELECT token, refused FROM github_tokens WHERE person_id = ?", (person_id,)).fetchone()
    if row is None or _open(row["token"]) is None:
        return "none"
    return "refused" if row["refused"] else "kept"


def refuse(db: sqlite3.Connection, person_id: int) -> None:
    """GitHub refused the person's token even fresh: it is marked refused, and the person signs in again."""
    _refuse(db, person_id)


def _refuse(db: sqlite3.Connection, person_id: int) -> None:
    with db:
        db.execute("UPDATE github_tokens SET refused = ? WHERE person_id = ?", (util.now(), person_id))
    util.log("github_token_refused", person=person_id)


# --------------------------------------------------------------------------- using, refreshing

_locks: dict[int, asyncio.Lock] = {}


def _lock(person_id: int) -> asyncio.Lock:
    lock = _locks.get(person_id)
    if lock is None:
        lock = _locks[person_id] = asyncio.Lock()
    return lock


async def _refresh(db: sqlite3.Connection, person_id: int, refresh: str) -> str:
    """Exchange the refresh token for a new pair and keep it. A refusal marks the authorization refused."""
    s = config.get()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as c:
            r = await c.post(s.github_web_url + "/login/oauth/access_token", headers={"Accept": "application/json"},
                             data={"client_id": s.github_client_id, "client_secret": s.github_client_secret,
                                   "grant_type": "refresh_token", "refresh_token": refresh})
    except httpx.HTTPError:
        raise Unavailable() from None
    if r.status_code >= 500:
        raise Unavailable()
    try:
        answer = r.json()
    except ValueError:
        answer = None
    if r.status_code != 200 or not isinstance(answer, dict) or not keep(db, person_id, answer):
        _refuse(db, person_id)
        raise NoAuthorization("reauth")
    util.log("github_token_refreshed", person=person_id)
    return answer["access_token"]


async def token(db: sqlite3.Connection, person_id: int) -> str:
    """The person's token to call GitHub with now, refreshed first when it is about to expire. Raises
    NoAuthorization, or Unavailable when a refresh was needed and GitHub did not answer."""
    async with _lock(person_id):
        row = db.execute("SELECT * FROM github_tokens WHERE person_id = ?", (person_id,)).fetchone()
        current = _open(row["token"]) if row else None
        if current is None:
            raise NoAuthorization("no_token")
        if row["refused"]:
            raise NoAuthorization("reauth")
        if row["expires"] is None or row["expires"] - REFRESH_MARGIN_S > util.now():
            return current
        refresh = _open(row["refresh"])
        if refresh is None or (row["refresh_expires"] is not None and row["refresh_expires"] <= util.now()):
            _refuse(db, person_id)
            raise NoAuthorization("reauth")
        return await _refresh(db, person_id, refresh)


async def refused(db: sqlite3.Connection, person_id: int, used: str) -> str:
    """GitHub answered 401 to `used`: a new token when one can be had (a refresh, or one kept meanwhile), else the
    authorization is marked refused and NoAuthorization("reauth") raised."""
    async with _lock(person_id):
        row = db.execute("SELECT * FROM github_tokens WHERE person_id = ?", (person_id,)).fetchone()
        current = _open(row["token"]) if row else None
        if current is None:
            raise NoAuthorization("no_token")
        if row["refused"]:
            raise NoAuthorization("reauth")
        if current != used:                       # refreshed, or signed in again, meanwhile
            return current
        refresh = _open(row["refresh"])
        if refresh is None:
            _refuse(db, person_id)
            raise NoAuthorization("reauth")
        return await _refresh(db, person_id, refresh)


# --------------------------------------------------------------------------- revoking

async def revoke(db: sqlite3.Connection, person_id: int) -> bool:
    """Delete the person's authorization and ask GitHub to revoke the token (DELETE /applications/{client_id}/token,
    as the App, when the server has the App's client secret). Whether there was one. GitHub not answering does not
    keep it: it is deleted here either way, and an outcome other than 204 is written down (without the token)."""
    async with _lock(person_id):
        row = db.execute("SELECT token FROM github_tokens WHERE person_id = ?", (person_id,)).fetchone()
        with db:
            db.execute("DELETE FROM github_tokens WHERE person_id = ?", (person_id,))
    if row is None:
        return False
    util.log("github_token_revoked", person=person_id)
    current = _open(row["token"])
    s = config.get()
    if current is None or not s.github_client_id or not s.github_client_secret:
        return True
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as c:
            r = await c.request("DELETE", f"{s.github_api_url}/applications/{s.github_client_id}/token",
                                auth=(s.github_client_id, s.github_client_secret),
                                headers={"Accept": "application/vnd.github+json"}, json={"access_token": current})
        if r.status_code not in (204, 404):       # 404: GitHub no longer knows it
            util.log("github_revoke_failed", person=person_id, reason=f"http_{r.status_code}")
    except httpx.HTTPError as e:
        util.log("github_revoke_failed", person=person_id, reason=type(e).__name__.lower())
    return True
