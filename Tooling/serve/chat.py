"""serve.chat — the Assistant panel's backend.

POST /api/chat streams one answer over SSE; `/api/chat/sessions` is the
CRUD around the transcripts it is filed on (`serve/chat_sessions.py`
owns the disk). The answerer is a headless spawn with a READ-ONLY tool
surface — it explains progress, code and framework mechanics; it can
never act. That is a soundness boundary, same tier as "sign-off cannot
be machine-signed" (design SoT: docs/internal/chat_explainer_design.md;
the 2026-09-06 redesign is web/docs/assistant_redesign_2026-09-06.md).

WHICH backend answers is a seat like any other: `explainer.provider` →
`ASTERISM_EXPLAINER_PROVIDER` → `ASTERISM_LLM_PROVIDER` → claude, the
chain every pipeline resolves through. This module knows none of the
dialects; `llm/explainer.py` owns them, and owns the two places where a
backend gives the reader LESS than claude does (conversation memory,
read fence). Both are published on /api/chat/state so the drawer can
say so — an explainer that quietly answers every question from a blank
context, or quietly reads outside the workspace, would be the same
hardwired-to-claude assumption wearing a registry.

Conversation continuity rides whatever the seated provider declares
(`capabilities.session_resume`): claude replays a caller-minted session
id, agy replays the conversation id it minted itself, and a provider
that resumes nothing gets no resume flag and reports
`conversation_memory: false`. One question at a time (single slot,
non-blocking lock → 409 busy).

The TRANSCRIPT is ours and the provider's session is theirs, and the
two can now come apart: `truncate_to` (edit & re-ask) deletes turns no
CLI can un-say, and a swept provider session dies while the record
lives. Both land in the same place — the turn is planned cold and the
kept turns are replayed into the prompt (`_replay_block`), which is why
the panel's old "the engine reads your next question fresh" caveat is
retired. It does read the conversation; it just re-reads it from us.

Page awareness: the client freezes {page kind, name} at send time and
the context block is built from that frozen value — the QPaper lesson
(2026-04-17): answer the page the user ASKED on, not the page they
navigated to mid-stream. Context is re-sent only when the page key
changes between messages; the session carries the rest.

Sessions are bound to a PROJECT (HID §1.1-2, §3.5): every Project has
its own transcripts, keyed here, so a question can never be filed on
another shelf's conversation (422) and switching Project cannot carry
an Erdos answer into a Topology page. The Project-picker page has no
Project and gets its own key (`_global`, which is not a legal Project
name, so it cannot collide with one). And the panel
follows the cursor: `focus` names the object on screen — a goal, a
group, a document, a problem — and its section joins the context block.
That is §1.4's "the panel receives the current screen's context", the
one thing it has that the old Ask did not.

Grounding: the model cites app objects with bracket tokens
([goal:…]/[problem:…]/…). The client — never the model — turns those
into navigation links, so a hallucinated citation can at worst point
at a real object badly, not invent a route (QPaper's paper_id lesson).
"""
from __future__ import annotations

import json
import queue
import sqlite3
import subprocess
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..llm import explainer
from ..state import db
from . import chat_sessions
from . import model_catalog

_MAX_MESSAGE = 8_000        # chars — a question, not an upload
_MAX_CONTEXT = 6_000        # chars — prebuilt page context budget
#: Sub-budgets, so a Project with 300 problems cannot crowd out the page
#: the question was asked on. The page block keeps whatever is left.
_MAX_PROJECT = 1_200
_MAX_FOCUS = 1_800

#: The replayed conversation's budget, and one turn's share of it (§2).
#: A transcript is unbounded and a prompt is not.
_MAX_REPLAY = 12_000
_MAX_REPLAY_TURN = 2_000

#: An SSE COMMENT on the wire this often while the CLI is silent, so a
#: proxy (or the browser) never sees a socket with nothing on it. A
#: comment, not a frame: the browser's reducer must not have to know
#: this exists.
_KEEPALIVE_SEC = 15.0

#: Fallback for `explainer.idle_sec` — the clock that decides a turn is
#: dead. It is an IDLE clock: a turn that keeps calling tools is
#: working, however long it takes, and the wall clock this replaced
#: killed answers that were visibly making progress.
_IDLE_SEC_DEFAULT = 600

_REPLAY_HEADER = (
    "[Earlier in this conversation — replayed because the engine's session\n"
    "was reset; answer as a continuation.]\n")

#: The session key for a conversation with no Project — the picker page
#: (§1.4). `_global` starts with an underscore, which `projects.NAME_RE`
#: refuses, so no Project can ever take this key.
GLOBAL_SESSION_KEY = "_global"

#: The keys a `focus` object may carry, in the order their sections are
#: laid out. A focus with several is legal (a goal inside a group) and
#: each one contributes its own section — the panel is describing one
#: screen, not answering a query.
FOCUS_KINDS: "tuple[str, ...]" = ("problem", "group_id", "goal_id",
                                  "doc_path")

_SYSTEM_PROMPT = """You are the explainer inside Asterism's console — \
a proving framework where LLM agents build machine-checked Lean proofs \
and a human signs off on the results. The person asking is a \
mathematician using the console, not a developer.

Rules:
1. You never change proofs, goals, the database or the running engine, \
and you never approve or sign anything. You may write documents under \
the Project's `user/` shelf and nowhere else (`write_project_doc`; \
that is the shelf the console calls "yours", the one the person can \
edit). You may prepare a framework command (`prepare_command`): it \
checks the command and shows what it would affect, then stops — the \
person confirms it in the console. Asked to shelve, delegate, mark or \
inject: prepare it, say what it would close, hand it over.
2. Grounded. Anchor answers in what you can actually read (the context \
block, files under the workspace, the public notes site for design \
rationale). Cite objects with bracket tokens so the UI can link them: \
[problem:NAME], [goal:PROBLEM:SLUG], [library:PROBLEM], [paper:ID]. \
Use the token forms exactly; never write URLs or file paths as \
citations. If you are not sure, say so plainly.
3. Audience. Plain mathematical language first, engine vocabulary \
only when asked. Answer in the language the user writes in, matching \
their script variant (Traditional Chinese in, Traditional Chinese \
out — never switch to Simplified, and vice versa). Keep answers \
short by default — one focused paragraph unless depth is asked for. \
No emoji.
4. Lean code and statements go in fenced code blocks; inline math in \
$...$.
5. Tools: `inspect` reads files and the record; `loogle` searches \
Mathlib; `paper_search` / `paper_fetch` find and shelve papers; \
`compute` runs a sandboxed calculation; `daemon_status` says what the \
engine is doing; `list_project_docs` / `read_project_doc` / \
`write_project_doc` are the Project's documents, and `tex_check` \
compiles a `.tex` you wrote and hands back the errors. Read `user/` \
before writing beside it, and write only there. Documents are for a \
mathematician: English, LaTeX for math.
"""

_CONTEXT_HEADER = (
    "[Context — auto-attached snapshot of what the user is looking at; "
    "it may be stale by the time you answer deeper questions, so verify "
    "against files/DB-derived context when precision matters.]\n")


# ---------------------------------------------------------------------------
# page context


def _connect(workspace: Path) -> "sqlite3.Connection | None":
    path = workspace / "asterism.db"
    if not path.exists():
        return None
    try:
        return db.connect_readonly(path)
    except Exception:  # noqa: BLE001 — context is best-effort garnish
        return None


def _clip(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _problem_context(conn: sqlite3.Connection, name: str) -> str:
    prow = conn.execute(
        "SELECT name, state, ingest_signoff_pending, ingested_at,"
        " strategist_directive FROM problems WHERE name = ?",
        (name,)).fetchone()
    if prow is None:
        return f"Problem page: {name} (unknown problem)."
    counts: dict[str, int] = {}
    for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM goals WHERE problem = ?"
            " GROUP BY status", (name,)):
        counts[str(r["status"])] = int(r["n"])
    roots = [
        {"slug": str(r["slug"]), "status": str(r["status"]),
         "statement": _clip(r["statement"], 300)}
        for r in conn.execute(
            "SELECT slug, status, statement FROM goals"
            " WHERE problem = ? AND depth = 0 ORDER BY id LIMIT 6",
            (name,))]
    recent = [
        {"kind": str(d["decision_kind"]),
         "at": str(d["created_at"]),
         "brief": _clip(d["brief"] or d["reason"] or "", 220),
         "outcome": d["outcome"]}
        for d in conn.execute(
            "SELECT decision_kind, brief, reason, outcome, created_at"
            " FROM strategist_decisions WHERE problem = ?"
            " ORDER BY id DESC LIMIT 6", (name,))]
    awaiting = [
        _clip(d["brief"] or "", 200)
        for d in conn.execute(
            "SELECT brief FROM strategist_decisions WHERE problem = ?"
            " AND decision_kind = 'RequestUserAmend' AND outcome IS NULL"
            " ORDER BY id DESC LIMIT 2", (name,))]
    ctx = {
        "page": "problem", "problem": str(prow["name"]),
        "state": str(prow["state"]),
        "signoff_pending": bool(prow["ingest_signoff_pending"]),
        "ingested_at": prow["ingested_at"],
        "goal_counts": counts,
        "root_goals": roots,
        "recent_decisions": recent,
        "directive_head": _clip(prow["strategist_directive"] or "", 300),
    }
    if awaiting:
        ctx["awaiting_user"] = awaiting
    return (json.dumps(ctx, ensure_ascii=False)
            + f"\nDeeper detail: Problems/{name.replace('.', '/')}/ holds"
              " problem.json (the durable intent seed), proofs/, .drafts/"
              "strategist_plan.md (the strategist's live plan note).")


def _board_context(conn: sqlite3.Connection, workspace: Path,
                   project: "str | None" = None) -> str:
    """Board = the overview page, so the context is an overview: state
    counts + the live run + what needs the human + what moved lately.
    (An alphabetical LIMIT slice shipped first and made the model cite
    whatever early-alphabet problem looked busy — wrong by design.)

    Inside a Project the overview is THAT shelf's (§1.4, the FK). A
    workspace-wide "what needs the human" handed the model another
    shelf's blocked task while the person stood in this one — the same
    reason `_project_context` lists only its own problems. Only the
    engine block stays workspace-wide: there is one engine."""
    where, args = "", ()
    if project is not None:
        where, args = " WHERE project = ?", (project,)
    counts = {str(r["state"]): int(r["n"]) for r in conn.execute(
        "SELECT state, COUNT(*) AS n FROM problems" + where
        + " GROUP BY state", args)}
    awaiting = [str(r["name"]) for r in conn.execute(
        "SELECT name FROM problems WHERE state = 'awaiting_human'"
        + (" AND project = ?" if project is not None else "")
        + " ORDER BY name LIMIT 10", args)]
    recent = [
        {"name": str(r["name"]), "state": str(r["state"]),
         "last_decision_at": r["last_strategist_at"]}
        for r in conn.execute(
            "SELECT name, state, last_strategist_at FROM problems"
            " WHERE last_strategist_at IS NOT NULL"
            + (" AND project = ?" if project is not None else "")
            + " ORDER BY last_strategist_at DESC LIMIT 8", args)]
    daemon: dict = {}
    try:
        from .daemon_cache import daemon_status
        d = daemon_status(workspace)
        daemon = {"running": d.get("running"), "scope": d.get("scope"),
                  "started_at": d.get("started_at")}
    except Exception:  # noqa: BLE001 — garnish
        pass
    return json.dumps({
        "page": "board", "problem_state_counts": counts,
        "engine": daemon, "awaiting_human": awaiting,
        "recently_active": recent,
    }, ensure_ascii=False)


def _project_context(conn: sqlite3.Connection, project: str) -> str:
    """The Project's shelf: its blurb and the problems filed under it.

    Its OWN problems — a Project is the unit the person switched into,
    and handing over the whole board would put another shelf's problem
    one hallucination away from being cited as this one's.
    """
    row = conn.execute("SELECT description FROM projects WHERE name = ?",
                       (project,)).fetchone()
    problems = [
        {"name": str(r["name"]), "state": str(r["state"]),
         "goals": int(r["goals"]), "proved": int(r["proved"])}
        for r in conn.execute(
            "SELECT p.name AS name, p.state AS state,"
            " (SELECT COUNT(*) FROM goals g WHERE g.problem = p.name)"
            "   AS goals,"
            " (SELECT COUNT(*) FROM goals g WHERE g.problem = p.name"
            "   AND g.status = 'proved') AS proved"
            " FROM problems p WHERE p.project = ? ORDER BY p.name",
            (project,))]
    ctx: dict = {"project": project,
                 "known": row is not None,
                 "description": _clip(row["description"] if row else "", 300),
                 "problem_count": len(problems),
                 "problems": problems[:40]}
    if len(problems) > 40:
        ctx["problems_omitted"] = len(problems) - 40
    return "Project: " + json.dumps(ctx, ensure_ascii=False)


def _focus_context(conn: sqlite3.Connection, workspace: Path,
                   project: "str | None", focus: dict) -> str:
    """What the person has open on screen, section by section (§1.4).

    A focus that names nothing gets a section saying so, with the id in
    it. Silence would be worse than a miss: the model would describe the
    page instead and the person would read that as an answer about the
    star they clicked.
    """
    from ..state import groups as _groups

    parts: "list[str]" = []
    for kind in FOCUS_KINDS:
        if kind not in focus or focus[kind] in (None, ""):
            continue
        value = focus[kind]
        if kind == "problem":
            parts.append("Focus (problem): "
                         + _problem_context(conn, str(value)))
            continue
        if kind == "goal_id":
            try:
                gid = int(value)
            except (TypeError, ValueError):
                parts.append(f"Focus (goal): {value!r} is not a goal id.")
                continue
            g = db.get_goal(conn, gid)
            if g is None:
                parts.append(f"Focus (goal): no goal {gid} in this "
                             f"workspace — say so rather than answering "
                             f"about the page.")
                continue
            grp = _groups.group_for_goal(conn, str(g["problem"]), gid)
            parts.append("Focus (goal): " + json.dumps({
                "goal_id": gid, "problem": str(g["problem"]),
                "slug": str(g["slug"]), "status": str(g["status"]),
                "statement": _clip(g["statement"], 700),
                "group_id": None if grp is None else int(grp["id"]),
            }, ensure_ascii=False))
            continue
        if kind == "group_id":
            try:
                grid = int(value)
            except (TypeError, ValueError):
                parts.append(f"Focus (group): {value!r} is not a group id.")
                continue
            row = _groups.get(conn, grid)
            if row is None:
                parts.append(f"Focus (group): no group {grid} in this "
                             f"workspace.")
                continue
            parts.append("Focus (group): " + json.dumps({
                "group_id": grid, "problem": str(row["problem"]),
                "status": str(row["status"]),
                "anchor_goal_id": (None if row["anchor_goal_id"] is None
                                   else int(row["anchor_goal_id"])),
                "charter": _clip(row["charter"], 900),
            }, ensure_ascii=False))
            continue
        # doc_path — the file under the cursor in the documents pane.
        from ..state import project_docs as _docs
        if not project:
            parts.append(f"Focus (document): {value!r} — no Project was "
                         f"named with this question, so the document "
                         f"root is unknown.")
            continue
        try:
            raw = _docs.read(workspace, project, str(value))
        except KeyError:
            parts.append(f"Focus (document): {value!r} is not in this "
                         f"Project's documents.")
            continue
        except (ValueError, OSError) as e:
            parts.append(f"Focus (document): {value!r} cannot be read "
                         f"({e}).")
            continue
        if _docs.is_binary(str(value)):
            parts.append(f"Focus (document): {value!r} — {len(raw)} bytes "
                         f"of binary; the person is looking at it, you "
                         f"cannot read it here.")
            continue
        head = raw.decode("utf-8", errors="replace")[:_MAX_FOCUS]
        parts.append(f"Focus (document) {value!r}:\n{head}")
    return "\n\n".join(parts)


def _focus_key(focus: "dict | None") -> str:
    """The focus, as part of the page key — so moving the cursor to
    another star re-sends the context instead of letting the session's
    memory answer about the previous one."""
    if not focus:
        return ""
    return ";".join(f"{k}={focus[k]}" for k in FOCUS_KINDS
                    if focus.get(k) not in (None, ""))


def _page_context(workspace: Path, page: "dict | None", *,
                  project: "str | None" = None,
                  focus: "dict | None" = None) -> "tuple[str, str]":
    """(page_key, context_text). Best-effort; empty context is legal
    (fresh workspace, no DB).

    With neither `project` nor `focus` this is byte-for-byte what the
    drawer got before Projects existed — the key included, because the
    key is what decides whether a session is re-primed.
    """
    kind = str((page or {}).get("kind") or "board")
    name = (page or {}).get("name")
    key = f"{kind}:{name or ''}"
    if project:
        key += f"|project={project}"
    fkey = _focus_key(focus)
    if fkey:
        key += f"|focus={fkey}"

    def _decorate(conn: sqlite3.Connection, text: str) -> str:
        parts = [text]
        if focus:
            try:
                block = _focus_context(conn, workspace, project, focus)
            except sqlite3.Error:
                block = ""
            if block:
                parts.append(block[:_MAX_FOCUS])
        if project:
            try:
                parts.append(_project_context(conn, project)[:_MAX_PROJECT])
            except sqlite3.Error:
                pass
        return "\n\n".join(p for p in parts if p)

    conn = _connect(workspace)
    try:
        if conn is None:
            return key, f"Page: {kind}. (No database yet — fresh workspace.)"
        if kind == "problem" and name:
            return key, _decorate(conn, _problem_context(conn, str(name)))
        if kind == "library" and name:
            return key, _decorate(conn, (
                f"Library chapter page for problem {name!r}: the archived,"
                f" human-signed form of its proofs. Sources live under"
                f" Library/ (Lean files; Read them for exact statements)."
            ))
        if kind == "engine":
            # the console IS an overview surface — give it the board's
            # whole-run context (QA: an Engine-page question got "the
            # current view only shows daemon status" because that was
            # literally all we handed over)
            return key, _decorate(
                conn, _board_context(conn, workspace, project))
        return key, _decorate(
            conn, _board_context(conn, workspace, project))
    except sqlite3.Error:
        return key, f"Page: {kind}. (Context query failed — answer from" \
                    f" files instead.)"
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# spawn plumbing (dialects live in llm/explainer.py)


class _ChatState:
    """The one slot.

    Nothing else lives here any more: the resume handle and the page key
    a conversation was last primed for are FIELDS ON THE RECORD now
    (§2), so they survive a serve restart with the transcript instead of
    dying with the process that happened to hold them.

    The lock stays SINGLE: the constraint is one question at a time on
    this machine, not one per Project — a second spawn would double the
    cost of the same subscription while the first is still thinking. It
    also guards the transcript a live answer is being written into: a
    rename, a truncation or a delete while the stream runs is a 409.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()      # ONE question at a time


def _session_key(project: "str | None") -> str:
    """Which conversation this question belongs to.

    Refuses a name that is not a Project name: the key reaches a SQL
    parameter and a dict, and "whatever the client sent" is not a
    vocabulary either of them should learn.
    """
    from ..state import projects as _projects
    name = (project or "").strip()
    if not name:
        return GLOBAL_SESSION_KEY
    if not _projects.NAME_RE.fullmatch(name):
        raise HTTPException(
            status_code=422,
            detail=f"invalid project name {project!r} — one identifier "
                   f"(letter, then letters/digits/underscore); omit it "
                   f"for the Project-picker conversation")
    return name


class ChatBody(BaseModel):
    """One question.

    `page` is the frozen screen ({kind: board|problem|library|engine,
    name?}). `project` binds the conversation (§1.1-2); omit it
    on the picker page. `focus` is what the person has OPEN on that
    screen and carries one or more of:

        {"problem":  "Erdos.p1"}    the problem being read
        {"group_id": 12}            the group whose Programme is open
        {"goal_id":  3141}          the star that was clicked
        {"doc_path": "user/x.md"}   the document under the cursor,
                                    relative to the Project's docs root

    Each key present contributes its own section to the context block,
    and the focus is part of the page key — moving to another star
    re-primes the session instead of letting it answer about the last.
    """

    message: str
    session_id: str              # the transcript this turn is filed on
    page: "dict | None" = None   # {kind: board|problem|library|engine, name?}
    model: "str | None" = None   # one of /api/chat/state's `groups`
    project: "str | None" = None
    focus: "dict | None" = None
    #: `edit & re-ask`: drop `turns[n:]` before this question, where
    #: turn n is the question being edited. The engine's handle goes
    #: with them and the kept turns are replayed instead.
    truncate_to: "int | None" = None


class SessionBody(BaseModel):
    """Which shelf a new conversation belongs to. Absent = the
    Project-picker page's own (`_global`)."""

    project: "str | None" = None


class RenameBody(BaseModel):
    """A conversation's name. Empty hands it back to the machine."""

    title: str = ""


def _clip_turn(text: str) -> str:
    return (text if len(text) <= _MAX_REPLAY_TURN
            else text[:_MAX_REPLAY_TURN - 1] + "…")


def _replay_block(turns: "list[dict]") -> str:
    """The conversation so far, for a turn the engine cannot resume.

    Most recent FIRST while filling the budget — an answer continues the
    last exchange, so if anything has to be dropped it is the oldest —
    then written back in reading order, because that is the order a
    reader (and a model) understands a dialogue in. Tool rows are not
    replayed: they were the engine's own working, and it can do it
    again if it needs to.
    """
    if not turns:
        return ""
    kept: "list[str]" = []
    budget = _MAX_REPLAY
    for turn in reversed(turns):
        line = (f"{turn.get('role') or 'user'}: "
                f"{_clip_turn(str(turn.get('text') or ''))}")
        if len(line) + 1 > budget:
            break
        budget -= len(line) + 1
        kept.append(line)
    if not kept:
        return ""
    kept.reverse()
    return _REPLAY_HEADER + "\n".join(kept) + "\n"


def register(app: FastAPI, workspace: Path) -> None:
    state = _ChatState()
    app.state.chat = state  # tests reach the slot lock through here

    def _default_model(backend) -> str:
        """`explainer.model` when set, else the SEATED backend's own
        default. A stored claude alias would be an invalid slug on
        another provider, so the fallback must move with the seat."""
        from ..core import config
        return str(config.get("explainer.model",
                              env_var="ASTERISM_EXPLAINER_MODEL",
                              default=backend.default_model,
                              workspace=workspace))

    def _groups() -> "list[dict]":
        """The picker's offer: the machine's catalog, filtered to
        providers that HAVE an explainer backend. Offering `codex` here
        would offer a choice `availability()` refuses by name a moment
        later — a picker must not be able to name a dead end."""
        return [g for g in model_catalog.model_groups(workspace)
                if g["provider"] in explainer.BACKENDS]

    def _idle_sec() -> int:
        from ..core import config
        return int(config.get("explainer.idle_sec",
                              env_var="ASTERISM_EXPLAINER_IDLE_SEC",
                              default=_IDLE_SEC_DEFAULT, cast=int,
                              workspace=workspace))

    @app.get("/api/chat/state")
    def chat_state() -> dict:
        """What the panel must know BEFORE the user types.

        `conversation_memory` and `read_scope` are the two ways a
        backend can be honestly worse than claude here (llm/explainer.py
        has the ruling). They ride this endpoint rather than an answer's
        events because both are properties of the seat, and a caveat
        that arrives after the question has been asked is a caveat that
        arrived too late.

        `groups` + `model_default` are the picker (§4). One control
        decides the model AND the backend, because the backend is
        implied by the model and two controls would let them disagree.
        """
        name = explainer.provider(workspace)
        backend = explainer.backend_for(name)
        ok, detail = explainer.availability(name)
        return {
            "busy": state.lock.locked(),
            "provider": name,
            "available": ok,
            "unavailable_detail": detail,
            "conversation_memory": explainer.remembers(name),
            "read_scope": explainer.read_scope(name),
            "read_note": explainer.scope_note(name),
            "model_default": _default_model(backend) if backend else "",
            "groups": _groups(),
        }

    # -- the transcripts (§2) ------------------------------------------

    @app.get("/api/chat/sessions")
    def list_sessions(project: "str | None" = None) -> dict:
        return {"sessions": chat_sessions.list_for(
            workspace, _session_key(project))}

    @app.post("/api/chat/sessions")
    def new_session(body: "SessionBody | None" = None) -> dict:
        """A conversation to file questions on — or the empty one this
        Project already has (§2: `+ new conversation` twice must not
        leave two blank rows in the fold)."""
        key = _session_key(body.project if body else None)
        name = explainer.provider(workspace)
        backend = explainer.backend_for(name)
        return chat_sessions.summary(chat_sessions.create(
            workspace, key,
            model=_default_model(backend) if backend else "",
            provider=name))

    @app.get("/api/chat/sessions/{session_id}")
    def read_session(session_id: str) -> dict:
        record = chat_sessions.get(workspace, session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="unknown session")
        return record

    @app.patch("/api/chat/sessions/{session_id}")
    def rename_session(session_id: str, body: RenameBody) -> dict:
        if state.lock.locked():
            raise HTTPException(status_code=409, detail="busy")
        try:
            return chat_sessions.summary(
                chat_sessions.rename(workspace, session_id, body.title))
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown session")

    @app.delete("/api/chat/sessions/{session_id}")
    def delete_session(session_id: str) -> dict:
        """Deleting the session is the act (`clear` is retired): it
        drops the transcript and abandons the provider's session with
        it — claude ages unreferenced session files out, agy's
        conversation id is simply never replayed."""
        if state.lock.locked():
            raise HTTPException(status_code=409, detail="busy")
        if not chat_sessions.delete(workspace, session_id):
            raise HTTPException(status_code=404, detail="unknown session")
        return {"deleted": True}

    @app.post("/api/chat")
    async def chat(body: ChatBody) -> StreamingResponse:
        message = body.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="empty message")
        if len(message) > _MAX_MESSAGE:
            raise HTTPException(status_code=413, detail="message too long")
        # Everything that can refuse the question refuses it BEFORE the
        # slot is taken: a 4xx that arrives after the lock is held is a
        # 4xx that has already cost the next question its turn.
        session_key = _session_key(body.project)
        session_id = body.session_id
        record = chat_sessions.get(workspace, session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="unknown session")
        if str(record.get("project") or "") != session_key:
            raise HTTPException(
                status_code=422,
                detail=f"this conversation belongs to Project "
                       f"{record.get('project')!r}, not {session_key!r} — "
                       f"a question is filed on its own shelf's transcript")
        seated = explainer.provider(workspace)
        seated_backend = explainer.backend_for(seated)
        if seated_backend is None:
            # no backend at all for the seat: the message names the seat
            # and the backends that could be chosen instead
            raise HTTPException(status_code=503,
                                detail=explainer.availability(seated)[1])
        default_model = _default_model(seated_backend)
        model = (body.model or "").strip() or default_model
        groups = _groups()
        provider = next((g["provider"] for g in groups
                         if model in g["models"]), None)
        if provider is None:
            # The default is always legal even off-list (a seat may be
            # pinned to a name the catalog has not heard of); anything
            # else the person could only have picked from the offer, so
            # the refusal names the offer.
            if model != default_model:
                offer = ", ".join(sorted({m for g in groups
                                          for m in g["models"]}))
                raise HTTPException(
                    status_code=422,
                    detail=f"{model!r} is not a model this machine offers "
                           f"— pick one of: {offer}")
            provider = seated
        if record.get("turns") and record.get("provider") \
                and str(record["provider"]) != provider:
            # §4: the resume handle belongs to ONE CLI. Replaying a
            # claude session id at agy is not a degraded answer, it is
            # a different conversation wearing this one's transcript.
            raise HTTPException(
                status_code=422,
                detail=f"this conversation is held with "
                       f"{record['provider']!r} — start a new conversation "
                       f"to switch backends")
        ok, detail = explainer.availability(provider)
        if not ok:
            raise HTTPException(status_code=503, detail=detail)
        backend = explainer.backend_for(provider)
        assert backend is not None  # availability() just proved it
        idle_sec = _idle_sec()
        if not state.lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="busy")

        # From here the lock is ours; the generator's finally releases
        # it (starlette always iterates the body, even on disconnect).
        # Until the generator exists, release on ANY exception — a
        # failed context build must not wedge the panel shut.
        try:
            if body.truncate_to is not None:
                try:
                    record = chat_sessions.truncate(
                        workspace, session_id, body.truncate_to)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc))
                except KeyError:
                    raise HTTPException(status_code=404,
                                        detail="unknown session")
            prior = list(record.get("turns") or [])
            page_key, context = _page_context(
                workspace, body.page, project=body.project,
                focus=body.focus)
            context = context[:_MAX_CONTEXT]
            # THE DEGRADATION, wired: on a provider that resumes nothing
            # `turn.resume` is False for every question, so the page
            # context below is re-sent every time instead of being left
            # to a session memory that does not exist.
            turn = explainer.plan_turn(provider, record.get("handle"))
            context_block = _CONTEXT_HEADER + context + "\n"
            # What a COLD turn says: the conversation so far, the page,
            # the question. Built even for a warm turn, because the
            # cold retry below needs it — a swept provider session must
            # not lose the transcript we still hold.
            cold_prompt = "\n".join(
                p for p in (_replay_block(prior), context_block, message)
                if p)
            if turn.resume:
                warm: "list[str]" = []
                if page_key != record.get("page_key"):
                    warm.append(context_block)
                prompt = "\n".join([*warm, message])
            else:
                prompt = cold_prompt
            record = chat_sessions.append_user(workspace, session_id, message)
            if len(record.get("turns") or []) == 1:
                # the seat is decided by the FIRST turn, not by creation:
                # the person may move the picker before typing
                record = chat_sessions.set_seat(workspace, session_id,
                                                model=model,
                                                provider=provider)
        except BaseException:
            state.lock.release()
            raise

        def _spawn(t: explainer.Turn, text: str) -> subprocess.Popen:
            from ..core.process_group import no_window_creationflags
            argv, env = backend.launch(
                workspace=workspace, system=_SYSTEM_PROMPT, prompt=text,
                model=model, turn=t, timeout_sec=idle_sec)
            return subprocess.Popen(
                argv, env=env, cwd=str(workspace),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                creationflags=no_window_creationflags(),
            )

        #: The answer being assembled, so the `finally` below can write
        #: it down whatever ends the stream (§2: partial answers are
        #: first-class — the person read what streamed).
        answer: "list[str]" = []
        rows: "list[dict]" = []
        #: `done` is whether the engine ENDED the turn. Without it the
        #: turn stopped, which is a different thing and has to be said
        #: out loud — see `_stopped_note`.
        outcome: "dict[str, object]" = {"ok": False, "note": None,
                                        "done": False}

        async def gen():
            nonlocal turn
            import asyncio
            proc: "subprocess.Popen | None" = None
            persist = True
            try:
                yield _sse({"type": "session", "id": session_id})
                yield _sse({"type": "status", "stage": "context"})
                try:
                    proc = _spawn(turn, prompt)
                except OSError as exc:
                    # Launching is more than exec on some backends: agy's
                    # capability envelope is a directory this call writes.
                    # A failure there must name itself, not surface as a
                    # truncated stream (the panel would roll the question
                    # back with "the stream ended before an answer") —
                    # and the question goes with it, because the panel
                    # has just put the text back in the composer.
                    persist = False
                    chat_sessions.pop_last_user(workspace, session_id)
                    yield _sse({"type": "error",
                                "detail": f"could not start the {provider} "
                                          f"explainer: {exc}"})
                    return
                q: "queue.Queue[dict | None]" = queue.Queue()
                threading.Thread(target=backend.reader, args=(proc, q),
                                 daemon=True, name="chat-reader").start()
                got_any = False
                loop = asyncio.get_running_loop()
                last_event = loop.time()
                last_ping = last_event
                while True:
                    try:
                        item = await asyncio.to_thread(q.get, True, 1.0)
                    except queue.Empty:
                        # IDLE, not a wall: every event resets the clock,
                        # so a turn that keeps calling tools is a turn
                        # that is working, however long it takes.
                        idle_now = loop.time()
                        if idle_now - last_event > idle_sec:
                            outcome["note"] = (f"no word from the explainer "
                                               f"for {idle_sec} s")
                            yield _sse({"type": "error",
                                        "detail": outcome["note"]})
                            break
                        if idle_now - last_ping >= _KEEPALIVE_SEC:
                            last_ping = idle_now
                            yield ": keepalive\n\n"
                        continue
                    last_event = loop.time()
                    last_ping = last_event
                    if item is None:
                        rc = proc.wait()
                        err = ""
                        if proc.stderr is not None:
                            try:
                                err = (proc.stderr.read() or "")[-400:]
                            except (OSError, ValueError):
                                err = ""
                        if rc != 0 and not got_any and turn.resume:
                            # a dead resume handle (aborted turn, swept
                            # session, a conversation id the CLI no
                            # longer knows) gets ONE clean cold retry
                            # before surfacing the error — and the cold
                            # prompt carries the transcript we still hold
                            turn = explainer.plan_turn(provider, None)
                            chat_sessions.set_handle(
                                workspace, session_id, None, None)
                            yield _sse({"type": "status", "stage": "retry"})
                            proc = _spawn(turn, cold_prompt)
                            q2: "queue.Queue[dict | None]" = queue.Queue()
                            threading.Thread(
                                target=backend.reader, args=(proc, q2),
                                daemon=True, name="chat-reader-2").start()
                            q = q2
                            continue
                        if not outcome["done"]:
                            # THE ENGINE WENT AWAY WITHOUT ENDING THE
                            # TURN (2026-09-06 13:48:12Z, mid `tex_check`).
                            # The old guard only spoke when the exit code
                            # was non-zero AND nothing had streamed, so a
                            # turn that had said a sentence first ended
                            # in silence: no `done`, no `error`, a row
                            # left pulsing and `note: None` on the record.
                            outcome["note"] = _stopped_note(
                                provider, rc, rows, err)
                            yield _sse({"type": "error",
                                        "detail": outcome["note"]})
                        break
                    kind = item.get("type")
                    got_any = got_any or kind == "delta"
                    if kind == "delta":
                        answer.append(str(item.get("text") or ""))
                    elif kind == "tool_start":
                        rows.append({"id": item.get("id"),
                                     "name": item.get("name"),
                                     "input": item.get("input"),
                                     "ok": None, "ms": None, "result": ""})
                    elif kind == "tool_end":
                        _settle_row(rows, item)
                    elif kind == "done":
                        outcome["done"] = True
                        outcome["ok"] = bool(item.get("ok"))
                        # The handle to replay next time: the one we
                        # minted (claude), the one the provider minted
                        # and reported (agy), or None — a backend that
                        # resumes nothing must never look resumed.
                        handle = ((item.get("handle") or turn.handle)
                                  if explainer.remembers(provider)
                                  else None)
                        chat_sessions.set_handle(workspace, session_id,
                                                 handle, page_key)
                    yield _sse(item)
                    if kind == "done":
                        break
            except GeneratorExit:
                # the tab closed or the stop button was pressed: nothing
                # can be sent any more, but the record still has to say
                # why this answer is half of one
                if not outcome["done"] and outcome["note"] is None:
                    outcome["note"] = ("the page stopped listening before "
                                       "the answer ended")
                raise
            finally:
                # Runs on every ending, the client walking away included
                # (the stop button and a closed tab both throw in here).
                # Order matters: the spawn dies first, the transcript is
                # written second, and the slot is freed last — a caller
                # that sees the lock released must be able to read the
                # turn it was waiting for.
                if proc is not None and proc.poll() is None:
                    proc.kill()
                if not outcome["done"] and outcome["note"] is None:
                    outcome["note"] = ("the stream ended before the answer "
                                       "did")
                if outcome["note"] is not None:
                    # a call whose result never came back is not still
                    # running, and the record must not read as if the
                    # panel simply stopped watching it
                    _fail_open_rows(rows, str(outcome["note"]))
                if persist:
                    try:
                        chat_sessions.append_assistant(
                            workspace, session_id, "".join(answer),
                            ok=bool(outcome["ok"]), note=outcome["note"],
                            tools=rows)
                    except (KeyError, OSError):
                        pass  # the session was deleted while it answered
                state.lock.release()

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})


def _open_rows(rows: "list[dict]") -> "list[dict]":
    """The calls whose result never came back."""
    return [r for r in rows if r.get("ok") is None]


def _stopped_note(provider: str, rc: int, rows: "list[dict]",
                  err: str) -> str:
    """One line saying why a turn stopped instead of ending.

    It NAMES the call it stopped inside where there is one: "it stopped"
    is not a reason, and on 2026-09-06 the call was the whole story —
    `tex_check` had been compiling for four minutes.
    """
    open_now = _open_rows(rows)
    where = ""
    if open_now:
        name = str(open_now[-1].get("name") or "").split("__")[-1]
        where = f" while {name or 'a tool'} was still running"
    tail = f" — {err.strip()}" if err.strip() else ""
    return (f"the {provider} explainer stopped without ending the answer "
            f"(exit {rc}){where}{tail}")


def _fail_open_rows(rows: "list[dict]", reason: str) -> None:
    """Close every call the turn never heard back from, as the failure
    it is. The reason goes in the result, because a row that says
    nothing is what the panel showed for four minutes."""
    for row in _open_rows(rows):
        row["ok"] = False
        if not row.get("result"):
            row["result"] = reason


def _settle_row(rows: "list[dict]", item: dict) -> None:
    """Close the row this result belongs to — or open a settled one.

    An end whose start was never seen still gets a row (§3): a resumed
    turn can carry a result whose call was made before this process
    attached, and dropping it would be the panel deciding the engine
    did not say something it said.
    """
    for row in rows:
        if row["id"] == item.get("id") and row["ok"] is None:
            row.update(ok=bool(item.get("ok")), ms=item.get("ms"),
                       result=item.get("result") or "")
            return
    rows.append({"id": item.get("id"), "name": "", "input": {},
                 "ok": bool(item.get("ok")), "ms": item.get("ms"),
                 "result": item.get("result") or ""})


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
