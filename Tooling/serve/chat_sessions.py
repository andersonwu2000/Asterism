"""serve.chat_sessions — the Assistant's transcripts, on disk.

HID §1.1 bound the conversation to the Project and the first
implementation kept it in a dict on the serve process: one live thread
per Project, gone at restart, invisible to the person who wanted the
answer they read yesterday. The redesign (§2) makes them many, named
and durable.

WHERE. `<workspace>/.asterism/chat/<project_key>/<id>.json`, with
`_global` for the Project-picker page. Runtime state, gitignored with
the rest of `.asterism/`, and deliberately NOT the database: the
daemon's DB is live proof state under a schema with migrations, and a
chat transcript is neither. One module owns every read and write so
that "what is a session" has one answer.

TWO FENCES, because both a session id and a Project key arrive from the
wire and both become path segments. `_ID_RE` admits uuid4 hex and
nothing else; `_KEY_RE` admits an identifier (which is what
`state/projects.NAME_RE` accepts, plus the leading underscore that
makes `_global` unable to collide with a real Project). An id that
fails is ABSENT, not an error, everywhere absence is a legal answer —
the panel holding a stale id from a deleted session must get a 404,
not a 500.

ATOMICITY. Every write is a temp file plus `os.replace`, so a crash
mid-write cannot leave a half-written transcript where the panel
expects JSON. Records are small (one conversation) and written whole:
the alternative — appending turns to a log — would buy nothing here and
cost the invariant that a file either parses or does not exist.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

#: uuid4 hex. The id reaches `Path.__truediv__`, so it is validated
#: before the filesystem is touched at all, not sanitized afterwards.
_ID_RE = re.compile(r"[0-9a-f]{32}")

#: A Project name (`state/projects.NAME_RE`) or `_global`. Same reason.
_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: §2: the title is the first line of turn 0, clipped. Long enough to
#: recognise a question by, short enough for the sessions fold's row.
_MAX_TITLE = 60


def now() -> str:
    """UTC, millisecond ISO-8601 with a `Z` — the shape §2's record
    declares. Sorts correctly as a string, which is what the listing
    orders by."""
    return datetime.now(timezone.utc).isoformat(
        timespec="microseconds").replace("+00:00", "Z")


def derive_title(text: str) -> str:
    """A conversation's name, from the question that opened it."""
    first = (text or "").strip().splitlines()
    line = " ".join(first[0].split()) if first else ""
    return line if len(line) <= _MAX_TITLE else line[:_MAX_TITLE - 1] + "…"


def summary(record: dict) -> dict:
    """The listing row: enough for the fold, without the transcript."""
    return {"id": record["id"], "title": record["title"],
            "updated_at": record["updated_at"],
            "created_at": record["created_at"],
            "turns": len(record.get("turns") or []),
            "model": record.get("model") or "",
            "provider": record.get("provider") or ""}


# ---------------------------------------------------------------------------
# paths


def _root(workspace: Path) -> Path:
    return workspace / ".asterism" / "chat"


def _key(project_key: str) -> str:
    if not _KEY_RE.fullmatch(project_key or ""):
        raise ValueError(f"not a session key: {project_key!r}")
    return project_key


def _find(workspace: Path, session_id: str) -> "Path | None":
    """The file for this id, or None — including for an id that is not
    one. The scan is over Project directories (a handful), and it is
    what lets the panel hold an id alone."""
    if not _ID_RE.fullmatch(session_id or ""):
        return None
    root = _root(workspace)
    if not root.is_dir():
        return None
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        path = d / f"{session_id}.json"
        if path.is_file():
            return path
    return None


def _read(path: Path) -> "dict | None":
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def _write(workspace: Path, record: dict) -> dict:
    """Whole record, atomically. The caller has already stamped
    `updated_at` where the change deserved one."""
    d = _root(workspace) / _key(str(record["project"]))
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{record['id']}.json"
    tmp = d / f".{record['id']}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    os.replace(tmp, path)
    return record


def _load(workspace: Path, session_id: str) -> dict:
    rec = get(workspace, session_id)
    if rec is None:
        raise KeyError(session_id)
    return rec


def _retitle(record: dict) -> dict:
    """Re-derive the title from turn 0 unless the person named it."""
    if not record.get("title_custom"):
        turns = record.get("turns") or []
        record["title"] = (derive_title(str(turns[0].get("text") or ""))
                           if turns else "")
    return record


# ---------------------------------------------------------------------------
# the store


def create(workspace: Path, project_key: str, *, model: str,
           provider: str) -> dict:
    """A session for this Project — or the empty one it already has.

    §2: a zero-turn session is legal, and `+ new conversation` on a
    conversation nobody has spoken into yet must not mint a second blank
    row. The seat is refreshed on reuse: nothing is committed to a
    provider until the first turn.
    """
    key = _key(project_key)
    for rec in sorted(_all(workspace, key),
                      key=lambda r: str(r.get("updated_at") or ""),
                      reverse=True):
        if not rec.get("turns"):
            if rec.get("model") != model or rec.get("provider") != provider:
                rec["model"], rec["provider"] = model, provider
                _write(workspace, rec)
            return rec
    stamp = now()
    return _write(workspace, {
        "id": uuid.uuid4().hex,
        "project": key,
        "title": "",
        "title_custom": False,
        "created_at": stamp,
        "updated_at": stamp,
        "model": model,
        "provider": provider,
        "handle": None,
        "page_key": None,
        "turns": [],
    })


def get(workspace: Path, session_id: str) -> "dict | None":
    path = _find(workspace, session_id)
    return None if path is None else _read(path)


def _all(workspace: Path, project_key: str) -> "list[dict]":
    d = _root(workspace) / _key(project_key)
    if not d.is_dir():
        return []
    out = []
    for p in d.glob("*.json"):
        rec = _read(p)
        if rec is not None and rec.get("id"):
            out.append(rec)
    return out


def list_for(workspace: Path, project_key: str) -> "list[dict]":
    """This Project's conversations, newest activity first. An
    unreadable key lists nothing rather than raising: a listing is a
    read, and the panel asks for one on every mount."""
    try:
        records = _all(workspace, project_key)
    except ValueError:
        return []
    records.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return [summary(r) for r in records]


def rename(workspace: Path, session_id: str, title: str) -> dict:
    """Name it, or hand the name back to the machine (empty title)."""
    rec = _load(workspace, session_id)
    text = " ".join((title or "").split())
    if text:
        rec["title_custom"] = True
        rec["title"] = (text if len(text) <= _MAX_TITLE
                        else text[:_MAX_TITLE - 1] + "…")
    else:
        rec["title_custom"] = False
        _retitle(rec)
    rec["updated_at"] = now()
    return _write(workspace, rec)


def delete(workspace: Path, session_id: str) -> bool:
    path = _find(workspace, session_id)
    if path is None:
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def set_seat(workspace: Path, session_id: str, *, model: str,
             provider: str) -> dict:
    """Which model and backend this conversation is being held with.

    Set from the FIRST turn, not from creation: the person may change
    the picker before typing. It does not move afterwards — the resume
    handle belongs to one CLI (§4).
    """
    rec = _load(workspace, session_id)
    rec["model"], rec["provider"] = model, provider
    return _write(workspace, rec)


def set_handle(workspace: Path, session_id: str, handle: "str | None",
               page_key: "str | None") -> dict:
    """The provider's resume handle and the page its context was built
    for — what `_ChatState.sessions` / `page_keys` used to hold in
    memory, now surviving a serve restart with the transcript."""
    rec = _load(workspace, session_id)
    rec["handle"] = handle or None
    rec["page_key"] = page_key or None
    return _write(workspace, rec)


def append_user(workspace: Path, session_id: str, text: str) -> dict:
    rec = _load(workspace, session_id)
    rec.setdefault("turns", []).append(
        {"role": "user", "text": text, "at": now()})
    _retitle(rec)
    rec["updated_at"] = now()
    return _write(workspace, rec)


def append_assistant(workspace: Path, session_id: str, text: str, *,
                     ok: bool, note: "str | None" = None,
                     tools: "list[dict] | tuple" = ()) -> dict:
    """The answer, written when the stream ends — done, error or the
    client walking away. §2: partial answers are first-class, so this
    is called with whatever streamed rather than only on success."""
    rec = _load(workspace, session_id)
    rec.setdefault("turns", []).append({
        "role": "assistant", "text": text, "at": now(),
        "ok": bool(ok), "note": note, "tools": list(tools)})
    rec["updated_at"] = now()
    return _write(workspace, rec)


def pop_last_user(workspace: Path, session_id: str) -> "dict | None":
    """Drop a question whose answer never started (spawn failure).

    Only a TRAILING user turn: the panel rolls the text back into the
    composer, and eating a settled answer to do it would be worse than
    the row it is removing.
    """
    rec = get(workspace, session_id)
    if rec is None:
        return None
    turns = rec.get("turns") or []
    if turns and turns[-1].get("role") == "user":
        turns.pop()
        _retitle(rec)
        rec["updated_at"] = now()
        _write(workspace, rec)
    return rec


def truncate(workspace: Path, session_id: str, n: int) -> dict:
    """`edit & re-ask`: drop `turns[n:]`, where turn n is a QUESTION.

    The handle goes with them. Neither claude nor agy can rewind a
    session, so a transcript that lost its last exchange must be
    planned cold and replayed into the prompt (§2) — resuming would
    hand the engine its memory of the turns the person just deleted.
    """
    rec = _load(workspace, session_id)
    turns = rec.get("turns") or []
    if not isinstance(n, int) or n < 0 or n >= len(turns) \
            or turns[n].get("role") != "user":
        raise ValueError(
            f"turn {n} is not a question in this conversation "
            f"({len(turns)} turns)")
    rec["turns"] = turns[:n]
    rec["handle"] = None
    rec["page_key"] = None
    _retitle(rec)
    rec["updated_at"] = now()
    return _write(workspace, rec)
