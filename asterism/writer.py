"""The computer a person chose to write the project's repository files with its own git (slice 1w, step w2).

CHOOSING: in personal settings each authorised computer (a credential of kind computer) can be chosen, at most one per
person and project (people.writer). Choosing one deletes the person's stored GitHub token and asks GitHub to revoke it:
from then on the server holds nothing that can write for them. Choosing none goes back to the server path (writes.py),
which needs a new sign-in. A revoked credential is never the writer (projects._revoke clears the choice).

WRITING: every save, delete and rename of that person is handed to that computer's program as a delivery of the
computer poll (computers.poll), {"kind": "write", "delivery": "w...", "op", "repo", "branch", "path", "to"?,
"content_b64"?, "base", "message"}; the page's request waits until the program answers (POST /api/computer/write) or
ASTERISM_WRITE_WAIT_S passes (computer_timeout). The program commits and pushes from a bare clone of its own, with the
computer's own git credentials; nothing here ever sees them. A write is handed out once and never again (a second
push of the same change would only meet a conflict, but a write must not be done twice): when its answer does not
come in time, the person tries again. The computer offline when the request comes: computer_offline at once.

`can-write` asks that computer instead of GitHub: it holds its connection (presence.computer_connected) and its
program's last report said it has git (credentials.git).

Write ids are strings ("w" and hex), so they never meet the ids of agents' deliveries (integers) in an
acknowledgement. Nothing of a write is kept on disk; the log has the outcome, never the content.
"""
from __future__ import annotations

import asyncio
import base64
import re
import secrets
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from . import config, files, presence, usertokens, util
from .errors import ApiError, bad_request, not_found
from .projects import Actor, Project

HEX_RE = re.compile(r"[0-9a-f]{4,64}")
DELIVERY_RE = re.compile(r"w[0-9a-f]{32}")
DETAIL_MOST = 300
RESULTS = ("done", "conflict", "failed")

OFFLINE = ("The computer you chose to write the repository's files is not connected now, so nothing was written. "
           "Start it (its Asterism program connects by itself), or choose another way in your settings.")
CANNOT_PUSH = ("The computer you chose to write the repository's files cannot write them: its Asterism program "
               "reports no git there (or is older than 0.1.12). Install git, or update the program; nothing was "
               "written.")
TIMEOUT = ("The computer you chose did not say in time whether it wrote the change. It may still have written it: "
           "refresh the files before trying again.")
FAILED = "The computer you chose could not write the change; nothing was written."
GONE = "There is no such file in the repository (any more)."


@dataclass
class _Write:
    id: str
    slug: str
    credential: int
    delivery: dict[str, Any]
    answer: asyncio.Future = field(default_factory=lambda: asyncio.get_running_loop().create_future())


# (project, credential) -> writes waiting to be handed out; delivery id -> every write not answered yet.
_queued: dict[tuple[str, int], list[_Write]] = {}
_open: dict[str, _Write] = {}


# --------------------------------------------------------------------------- choosing

def chosen(pj: Project, person_id: int) -> sqlite3.Row | None:
    """The credential of the computer the person chose, or None (the server path)."""
    row = pj.db.execute("SELECT c.* FROM people p JOIN credentials c ON c.id = p.writer WHERE p.person_id = ? "
                        "AND c.person_id = p.person_id AND c.kind = 'computer' AND c.revoked IS NULL",
                        (person_id,)).fetchone()
    return row


async def choose(pj: Project, actor: Actor, raw: Any, accounts: sqlite3.Connection) -> dict[str, Any]:
    """POST /api/me/writer {"credential": id | null}. Choosing a computer deletes and revokes the person's GitHub
    token (usertokens.revoke); choosing none goes back to the server path."""
    if actor.agent_id is not None:
        raise ApiError(403, "forbidden", "Only a person chooses how their writes are made.")
    if raw is not None and (isinstance(raw, bool) or not isinstance(raw, int)):
        raise bad_request("bad_request", "credential must be the id of one of your computers, or null.")
    if raw is not None:
        row = pj.db.execute("SELECT id FROM credentials WHERE id = ? AND person_id = ? AND kind = 'computer' "
                            "AND revoked IS NULL", (raw, actor.person_id)).fetchone()
        if row is None:
            raise not_found("You have no such computer.")
    with pj.db:
        pj.db.execute("UPDATE people SET writer = ? WHERE person_id = ?", (raw, actor.person_id))
    util.log("files_writer_chosen", project=pj.slug, person=actor.person_id, credential=raw)
    if raw is not None:
        from . import writes                    # writes imports this module
        await usertokens.revoke(accounts, actor.person_id)
        writes.forget_person(actor.person_id)
    return {"writer": raw}


def label(cred: sqlite3.Row) -> dict[str, Any]:
    return {"credential": cred["id"], "label": cred["label"]}


def _not_ready(pj: Project, cred: sqlite3.Row) -> str | None:
    if not presence.computer_connected(pj.slug, cred["id"], pj.db):
        return "computer_offline"
    if cred["git"] != 1:
        return "computer_cannot_push"
    return None


def can_write(pj: Project, cred: sqlite3.Row) -> dict[str, Any]:
    reason = _not_ready(pj, cred)
    answer: dict[str, Any] = {"can_write": reason is None, "writer": label(cred)}
    if reason:
        answer["reason"] = reason
    return answer


# --------------------------------------------------------------------------- writing

def take(slug: str, cred_id: int) -> list[dict[str, Any]]:
    """The writes waiting for this computer, handed out now (once: computers.poll)."""
    queued = _queued.pop((slug, cred_id), [])
    return [w.delivery for w in queued if not w.answer.done()]


def _detail(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    text = "".join(ch for ch in raw if ch.isprintable())[:DETAIL_MOST].strip()
    return text or None


async def write(pj: Project, address: str, person_id: int, cred: sqlite3.Row, op: str,
                checked: dict[str, Any]) -> dict[str, Any]:
    """Hand one save, delete or rename to the person's computer and wait for its answer. `checked` is what writes.py
    made of the request: path, to?, data?, base, message."""
    reason = _not_ready(pj, cred)
    if reason == "computer_offline":
        raise ApiError(409, reason, OFFLINE)
    if reason:
        raise ApiError(409, reason, CANNOT_PUSH)
    repo = files.repo_of(address)
    wid = "w" + secrets.token_hex(16)
    delivery: dict[str, Any] = {"kind": "write", "delivery": wid, "op": op, "repo": repo.web,
                                "branch": files.known_ref(pj.slug, repo), "path": checked["path"],
                                "base": checked["base"], "message": checked["message"]}
    if op == "rename":
        delivery["to"] = checked["to"]
    if op == "save":
        delivery["content_b64"] = base64.b64encode(checked["data"]).decode("ascii")
    w = _Write(wid, pj.slug, cred["id"], delivery)
    _queued.setdefault((pj.slug, cred["id"]), []).append(w)
    _open[wid] = w
    presence.computer_changed(pj.slug, cred["id"])         # an open poll of that computer hands it out now
    try:
        got = await asyncio.wait_for(asyncio.shield(w.answer), config.get().write_wait_s)
    except asyncio.TimeoutError:
        util.log("files_write_timeout", project=pj.slug, person=person_id, path=checked["path"], op=op,
                 credential=cred["id"])
        raise ApiError(504, "computer_timeout", TIMEOUT) from None
    finally:
        _open.pop(wid, None)
        left = _queued.get((pj.slug, cred["id"]))
        if left is not None and w in left:
            left.remove(w)
            if not left:
                del _queued[(pj.slug, cred["id"])]
    result = got["result"]
    if result == "done":
        commit = got.get("commit")
        util.log("files_write", project=pj.slug, person=person_id, path=checked["path"], op=op, commit=commit,
                 via="computer", credential=cred["id"])
        files.expire(pj.slug, repo)
        answer: dict[str, Any] = {"commit": commit}
        if op != "delete":
            answer["sha"] = got.get("sha")
        return answer
    if result == "conflict":
        current = got.get("current")
        if current is None and op in ("delete", "rename") and checked["base"] is not None:
            raise not_found(GONE)
        raise ApiError(409, "conflict", "The file changed in the repository since you started; nothing was written.",
                       {"current": current})
    util.log("files_write_failed", project=pj.slug, person=person_id, path=checked["path"], op=op,
             credential=cred["id"])
    extra = {"detail": got["detail"]} if got.get("detail") else None
    raise ApiError(502, "computer_failed", FAILED, extra)


def answer(pj: Project, cred_id: int, body: dict[str, Any]) -> dict[str, Any]:
    """POST /api/computer/write: the program's outcome of one write delivery."""
    wid = body.get("delivery")
    w = _open.get(wid) if isinstance(wid, str) and DELIVERY_RE.fullmatch(wid) else None
    if w is None or w.slug != pj.slug or w.credential != cred_id or w.answer.done():
        raise not_found("No write waits for this delivery (it was answered, or the wait ended).")
    result = body.get("result")
    if result not in RESULTS:
        raise bad_request("bad_request", "result must be one of: " + ", ".join(RESULTS))
    got: dict[str, Any] = {"result": result}
    for key in ("commit", "sha", "current"):
        v = body.get(key)
        if v is not None and (not isinstance(v, str) or not HEX_RE.fullmatch(v)):
            raise bad_request("bad_request", f"{key} must be an object's hash.")
        got[key] = v
    if result == "done" and got["commit"] is None:
        raise bad_request("bad_request", "A write that is done names its commit.")
    got["detail"] = _detail(body.get("detail"))
    w.answer.set_result(got)
    return {}
