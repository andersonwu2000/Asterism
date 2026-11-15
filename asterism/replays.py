"""A write that is retried is done once: the answers kept under an `Idempotency-Key`.

A caller may send the header with any POST of the project's API. The first request with a key is done and its
answer (below 500) is kept with the key, the request's path and its body; the same request again gets that
answer back instead of being done again, and the key used for another request is refused. Keys belong to the
caller (a person, or an agent's credential with its session) and to the project, and are kept
ASTERISM_REPLAY_KEEP_S seconds; the upkeep deletes them after that.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from . import config, util
from .errors import ApiError, bad_request

KEY_RE = re.compile(r"[A-Za-z0-9_-]{16,64}")


def check_key(raw: str) -> str:
    if not KEY_RE.fullmatch(raw):
        raise bad_request("invalid_idempotency_key",
                          "The Idempotency-Key header must be 16 to 64 characters of A-Z, a-z, 0-9, '_' and '-'.")
    return raw


def key_reused() -> ApiError:
    return ApiError(422, "key_reused", "This Idempotency-Key was already used for another request.")


def body_digest(raw: bytes) -> str:
    """The request's body as compared: its JSON after parsing (so spacing and the order of keys do not count); a
    body that is not JSON as its bytes. An empty body is the empty object, as the endpoints read it."""
    try:
        parsed: Any = json.loads(raw) if raw.strip() else {}
        text = "json:" + json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except ValueError:
        text = "raw:" + raw.hex()
    return util.digest(text)


def find(db: sqlite3.Connection, scope: str, key: str, t: float) -> sqlite3.Row | None:
    """The answer kept under this caller's key, unless its keeping time is over."""
    return db.execute("SELECT * FROM replays WHERE scope = ? AND key = ? AND created > ?",
                      (scope, key, t - config.get().replay_keep_s)).fetchone()


def keep(db: sqlite3.Connection, scope: str, key: str, path: str, body: str, status: int, answer: bytes) -> None:
    with db:
        db.execute("INSERT OR REPLACE INTO replays (scope, key, path, body, status, answer, created) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?)", (scope, key, path, body, status, answer, util.now()))


def expire(db: sqlite3.Connection, t: float) -> None:
    with db:
        db.execute("DELETE FROM replays WHERE created <= ?", (t - config.get().replay_keep_s,))
