"""People and their browser sign-in. A person is a GitHub account; the server keeps no password."""
from __future__ import annotations

import re
import sqlite3
import urllib.parse
from typing import Any

import httpx

from . import config, util
from .errors import ApiError

WEB_SESSION_TTL_S = 30 * 24 * 3600
LOGIN_STATE_TTL_S = 600
_REASON_DROP_RE = re.compile(r"[^a-z0-9_]")


class SignInFailed(ApiError):
    """A GitHub sign-in that did not go through: which step failed and a short fixed reason, for the log."""

    def __init__(self, step: str, reason: str, message: str):
        super().__init__(502, "github_failed", message)
        self.step, self.reason = step, reason


def _bounded(raw: Any) -> str:
    """A reason word taken from GitHub's answer: only [a-z0-9_], at most 60 characters."""
    return _REASON_DROP_RE.sub("", str(raw).lower())[:60]


def person(db: sqlite3.Connection, person_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()


def public(p: sqlite3.Row) -> dict[str, Any]:
    return {"name": p["name"], "github_login": p["github_login"]}


def _free_name(db: sqlite3.Connection, login: str) -> str:
    """A person's name defaults to the GitHub login; a name held by another account gets a suffix."""
    base = login[:36]
    name, n = base, 1
    while db.execute("SELECT 1 FROM people WHERE name = ?", (name,)).fetchone():
        n += 1
        name = f"{base}-{n}"
    return name


def upsert_github(db: sqlite3.Connection, github_id: str, login: str) -> sqlite3.Row:
    """The person behind a GitHub account, created on first sign-in. The id is what identifies the
    account; the login can change on GitHub and is refreshed here."""
    with db:
        row = db.execute("SELECT * FROM people WHERE github_id = ?", (github_id,)).fetchone()
        if row:
            if row["github_login"] != login:
                db.execute("UPDATE people SET github_login = ? WHERE id = ?", (login, row["id"]))
            pid = row["id"]
        else:
            pid = db.execute("INSERT INTO people (name, github_id, github_login, created) VALUES (?, ?, ?, ?)",
                             (_free_name(db, login), github_id, login, util.now())).lastrowid
            util.log("person_created", person=pid, github_login=login)
    return person(db, pid)


def start_web_session(db: sqlite3.Connection, person_id: int) -> str:
    """Returns the cookie value; only its digest is stored."""
    token = util.new_secret()
    with db:
        db.execute("DELETE FROM web_sessions WHERE expires < ?", (util.now(),))
        db.execute("INSERT INTO web_sessions (digest, person_id, created, expires) VALUES (?, ?, ?, ?)",
                   (util.digest(token), person_id, util.now(), util.now() + WEB_SESSION_TTL_S))
    util.log("signed_in", person=person_id)
    return token


def web_session_person(db: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    row = db.execute("SELECT person_id, expires FROM web_sessions WHERE digest = ?", (util.digest(token),)).fetchone()
    if not row or row["expires"] < util.now():
        return None
    return person(db, row["person_id"])


def end_web_session(db: sqlite3.Connection, token: str | None) -> None:
    if token:
        with db:
            db.execute("DELETE FROM web_sessions WHERE digest = ?", (util.digest(token),))


# --------------------------------------------------------------------------- GitHub OAuth web flow (real mode)

def github_redirect_uri() -> str:
    return config.get().public_url + "/login/callback"


def begin_github(db: sqlite3.Connection, next_path: str) -> tuple[str, str]:
    """Returns (the GitHub address to send the browser to, the state the browser must bring back)."""
    state = util.new_secret()
    with db:
        db.execute("DELETE FROM login_states WHERE expires < ?", (util.now(),))
        db.execute("INSERT INTO login_states (digest, next, expires) VALUES (?, ?, ?)",
                   (util.digest(state), util.safe_next(next_path), util.now() + LOGIN_STATE_TTL_S))
    q = urllib.parse.urlencode({"client_id": config.get().github_client_id, "redirect_uri": github_redirect_uri(),
                                "state": state, "allow_signup": "true"})
    return f"{config.get().github_web_url}/login/oauth/authorize?{q}", state


def take_login_state(db: sqlite3.Connection, state: str) -> str | None:
    """The `next` path stored with this state, once."""
    key = util.digest(state)
    with db:
        row = db.execute("SELECT next, expires FROM login_states WHERE digest = ?", (key,)).fetchone()
        db.execute("DELETE FROM login_states WHERE digest = ?", (key,))
    if not row or row["expires"] < util.now():
        return None
    return row["next"]


async def finish_github(db: sqlite3.Connection, code: str) -> sqlite3.Row:
    """Exchange the callback's code for a GitHub token, read the account's id and login, and forget the token.
    Every failure raises SignInFailed; the caller writes it down once."""
    s = config.get()
    refused = "GitHub did not accept the sign-in. Try again."
    unknown = "GitHub did not say who signed in. Try again."
    async with httpx.AsyncClient(timeout=20) as c:
        try:
            r = await c.post(s.github_web_url + "/login/oauth/access_token", headers={"Accept": "application/json"},
                             data={"client_id": s.github_client_id, "client_secret": s.github_client_secret,
                                   "code": code, "redirect_uri": github_redirect_uri()})
            answer = r.json()
        except (httpx.HTTPError, ValueError):
            raise SignInFailed("token", "unreachable", refused) from None
        if not isinstance(answer, dict):
            raise SignInFailed("token", "unreachable", refused)
        token = answer.get("access_token") if r.status_code == 200 else None
        if not token:
            reason = _bounded(answer["error"]) if answer.get("error") else ""
            raise SignInFailed("token", reason or f"http_{r.status_code}", refused)
        try:
            u = await c.get(s.github_api_url + "/user", headers={"Authorization": f"Bearer {token}",
                                                                 "Accept": "application/vnd.github+json"})
            if u.status_code != 200:
                raise SignInFailed("user", f"http_{u.status_code}", unknown)
            info = u.json()
        except (httpx.HTTPError, ValueError):
            raise SignInFailed("user", "unreachable", unknown) from None
    if not isinstance(info, dict):
        raise SignInFailed("user", "unreachable", unknown)
    gid, login = info.get("id"), info.get("login")
    if not isinstance(gid, int) or not isinstance(login, str) or not util.GITHUB_LOGIN_RE.fullmatch(login):
        raise SignInFailed("account", "unusable", "GitHub answered with an account this server cannot use.")
    return upsert_github(db, str(gid), login)
