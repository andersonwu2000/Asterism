"""serve.chat — the explainer drawer's backend.

One endpoint pair: POST /api/chat streams an answer over SSE; POST
/api/chat/clear forgets the conversation. The answerer is a headless
spawn with a READ-ONLY tool surface — it explains progress, code and
framework mechanics; it can never act. That is a soundness boundary,
same tier as "sign-off cannot be machine-signed" (design SoT:
docs/internal/chat_explainer_design.md).

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
non-blocking lock → 409 busy). The browser owns display history; the
provider's session owns model context; /api/chat/clear drops both ends
together.

Page awareness: the client freezes {page kind, name} at send time and
the context block is built from that frozen value — the QPaper lesson
(2026-04-17): answer the page the user ASKED on, not the page they
navigated to mid-stream. Context is re-sent only when the page key
changes between messages; the session carries the rest.

The session is bound to a PROJECT (HID §1.1-2, §3.5): one conversation
per Project, keyed here, so switching Project switches session instead
of carrying an Erdos answer into a Topology page. The Project-picker
page has no Project and gets its own key (`_global`, which is not a
legal Project name, so it cannot collide with one). And the panel
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
import os
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

_MAX_MESSAGE = 8_000        # chars — a question, not an upload
_MAX_CONTEXT = 6_000        # chars — prebuilt page context budget
#: Sub-budgets, so a Project with 300 problems cannot crowd out the page
#: the question was asked on. The page block keeps whatever is left.
_MAX_PROJECT = 1_200
_MAX_FOCUS = 1_800
_TIMEOUT_SEC = int(os.environ.get("ASTERISM_EXPLAINER_TIMEOUT", "300"))

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
the Project's `agent/` shelf (`write_project_doc`; `user/` is the \
person's). You may prepare a framework command (`prepare_command`): it \
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
`write_project_doc` are the Project's documents. Read `user/` before \
writing beside it. Documents are for a mathematician: English, LaTeX \
for math.
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
    """One conversation per Project (§1.1-2), plus the one slot.

    The maps are keyed by `_session_key(project)`, so the Project the
    person is in decides which conversation a question continues. The
    lock stays SINGLE: the constraint is one question at a time on this
    machine, not one per Project — a second spawn would double the cost
    of the same subscription while the first is still thinking.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()      # ONE question at a time
        #: session key → the seated provider's resume handle for that
        #: conversation: a caller-minted uuid, a provider-minted
        #: conversation id, or absent on a backend that resumes nothing
        self.sessions: "dict[str, str]" = {}
        #: session key → the page key its context was last built for
        self.page_keys: "dict[str, str]" = {}

    @property
    def session_id(self) -> "str | None":
        """The Project-less conversation — the drawer's whole world
        before Projects, and still the picker page's own session."""
        return self.sessions.get(GLOBAL_SESSION_KEY)


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

    `page` is the frozen screen ({kind: board|problem|library|engine|
    papers, name?}). `project` binds the conversation (§1.1-2); omit it
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
    page: "dict | None" = None   # {kind: board|problem|library|engine|papers, name?}
    model: "str | None" = None   # one of /api/chat/state's `models`
    project: "str | None" = None
    focus: "dict | None" = None


class ClearBody(BaseModel):
    """Which conversation to forget. Absent = the Project-less one."""

    project: "str | None" = None


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

    @app.get("/api/chat/state")
    def chat_state(project: "str | None" = None) -> dict:
        """What the drawer must know BEFORE the user types.

        `conversation_memory` and `read_scope` are the two ways a
        backend can be honestly worse than claude here (llm/explainer.py
        has the ruling). They ride this endpoint rather than an answer's
        events because both are properties of the seat, and a caveat
        that arrives after the question has been asked is a caveat that
        arrived too late.

        `has_session` is per Project (§1.1-2): the panel asks about the
        Project it is open in, and a site-wide answer would tell it the
        conversation continues when the person just switched shelves.
        """
        key = _session_key(project)
        name = explainer.provider(workspace)
        backend = explainer.backend_for(name)
        ok, detail = explainer.availability(name)
        return {
            "busy": state.lock.locked(),
            "has_session": key in state.sessions,
            "session_key": key,
            "provider": name,
            "available": ok,
            "unavailable_detail": detail,
            "conversation_memory": explainer.remembers(name),
            "read_scope": explainer.read_scope(name),
            "read_note": explainer.scope_note(name),
            "model_default": _default_model(backend) if backend else "",
            "models": list(backend.models) if backend else [],
        }

    @app.post("/api/chat/clear")
    def chat_clear(body: "ClearBody | None" = None) -> dict:
        """Forget ONE Project's conversation — both ends. The provider's
        session is simply abandoned (claude keeps sessions as files under
        the user's state and ages unreferenced ones out; agy's
        conversation id is dropped and never replayed).

        One Project, not all of them: "clear" is pressed inside a
        Project, and the person clearing their Erdos thread has said
        nothing about the Topology one."""
        if state.lock.locked():
            raise HTTPException(status_code=409, detail="busy")
        key = _session_key(body.project if body else None)
        state.sessions.pop(key, None)
        state.page_keys.pop(key, None)
        return {"cleared": True}

    @app.post("/api/chat")
    async def chat(body: ChatBody) -> StreamingResponse:
        message = body.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="empty message")
        if len(message) > _MAX_MESSAGE:
            raise HTTPException(status_code=413, detail="message too long")
        # Before the slot is taken: a malformed Project name is a bad
        # request, and a 422 that arrives after the lock is held is a
        # 422 that has already cost the next question its turn.
        session_key = _session_key(body.project)
        provider = explainer.provider(workspace)
        ok, detail = explainer.availability(provider)
        if not ok:
            raise HTTPException(status_code=503, detail=detail)
        backend = explainer.backend_for(provider)
        assert backend is not None  # availability() just proved it
        model = (body.model or "").strip() or _default_model(backend)
        if not state.lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="busy")

        # From here the lock is ours; the generator's finally releases
        # it (starlette always iterates the body, even on disconnect).
        # Until the generator exists, release on ANY exception — a
        # failed context build must not wedge the drawer shut.
        try:
            page_key, context = _page_context(
                workspace, body.page, project=body.project,
                focus=body.focus)
            context = context[:_MAX_CONTEXT]
            # THE DEGRADATION, wired: on a provider that resumes nothing
            # `turn.resume` is False for every question, so the page
            # context below is re-sent every time instead of being left
            # to a session memory that does not exist.
            turn = explainer.plan_turn(provider,
                                       state.sessions.get(session_key))
            parts: "list[str]" = []
            if not turn.resume or page_key != state.page_keys.get(
                    session_key):
                parts.append(_CONTEXT_HEADER + context + "\n")
            parts.append(message)
            prompt = "\n".join(parts)
        except BaseException:
            state.lock.release()
            raise

        def _spawn(t: explainer.Turn) -> subprocess.Popen:
            from ..core.process_group import no_window_creationflags
            argv, env = backend.launch(
                workspace=workspace, system=_SYSTEM_PROMPT, prompt=prompt,
                model=model, turn=t, timeout_sec=_TIMEOUT_SEC)
            return subprocess.Popen(
                argv, env=env, cwd=str(workspace),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                creationflags=no_window_creationflags(),
            )

        async def gen():
            nonlocal turn
            import asyncio
            proc: "subprocess.Popen | None" = None
            try:
                yield _sse({"type": "status", "stage": "context"})
                try:
                    proc = _spawn(turn)
                except OSError as exc:
                    # Launching is more than exec on some backends: agy's
                    # capability envelope is a directory this call writes.
                    # A failure there must name itself, not surface as a
                    # truncated stream (the drawer would roll the question
                    # back with "the stream ended before an answer").
                    yield _sse({"type": "error",
                                "detail": f"could not start the {provider} "
                                          f"explainer: {exc}"})
                    return
                q: "queue.Queue[dict | None]" = queue.Queue()
                threading.Thread(target=backend.reader, args=(proc, q),
                                 daemon=True, name="chat-reader").start()
                got_any = False
                deadline = asyncio.get_running_loop().time() + _TIMEOUT_SEC
                while True:
                    try:
                        item = await asyncio.to_thread(q.get, True, 1.0)
                    except queue.Empty:
                        if asyncio.get_running_loop().time() > deadline:
                            yield _sse({"type": "error",
                                        "detail": "answer timed out"})
                            break
                        continue
                    if item is None:
                        rc = proc.wait()
                        if rc != 0 and not got_any:
                            # a dead resume handle (aborted turn, swept
                            # session, a conversation id the CLI no
                            # longer knows) gets ONE clean cold retry
                            # before surfacing the error
                            err = ""
                            if proc.stderr is not None:
                                err = (proc.stderr.read() or "")[-400:]
                            if turn.resume:
                                turn = explainer.plan_turn(provider, None)
                                state.sessions.pop(session_key, None)
                                yield _sse({"type": "status",
                                            "stage": "retry"})
                                proc = _spawn(turn)
                                q2: "queue.Queue[dict | None]" = \
                                    queue.Queue()
                                threading.Thread(
                                    target=backend.reader, args=(proc, q2),
                                    daemon=True,
                                    name="chat-reader-2").start()
                                q = q2
                                continue
                            yield _sse({"type": "error",
                                        "detail": f"{provider} exited "
                                                  f"rc={rc} {err}".strip()})
                        break
                    got_any = got_any or item.get("type") == "delta"
                    if item.get("type") == "done":
                        # The handle to replay next time: the one we
                        # minted (claude), the one the provider minted
                        # and reported (agy), or None — a backend that
                        # resumes nothing must never look resumed.
                        handle = ((item.get("handle") or turn.handle)
                                  if explainer.remembers(provider)
                                  else None)
                        if handle:
                            state.sessions[session_key] = handle
                        else:
                            state.sessions.pop(session_key, None)
                        state.page_keys[session_key] = page_key
                    yield _sse(item)
                    if item.get("type") == "done":
                        break
            except asyncio.CancelledError:
                # client went away (stop button / closed tab) — the
                # answer dies with it, but the session survives for
                # the next question
                raise
            finally:
                if proc is not None and proc.poll() is None:
                    proc.kill()
                state.lock.release()

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
