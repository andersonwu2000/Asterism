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
_TIMEOUT_SEC = int(os.environ.get("ASTERISM_EXPLAINER_TIMEOUT", "300"))

_SYSTEM_PROMPT = """You are the explainer inside Asterism's console — \
a proving framework where LLM agents build machine-checked Lean proofs \
and a human signs off on the results. The person asking is a \
mathematician using the console, not a developer.

Rules:
1. READ-ONLY, always. You explain; you never act. If asked to change, \
approve, reject, run, or delete anything, decline in one sentence and \
point at the UI control that does it. No exceptions — acting would \
break the system's soundness boundary.
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
              " Manifest.md (user intent), proofs/, .drafts/"
              "strategist_plan.md (the strategist's live plan note).")


def _board_context(conn: sqlite3.Connection, workspace: Path) -> str:
    """Board = the overview page, so the context is an overview: state
    counts + the live run + what needs the human + what moved lately.
    (An alphabetical LIMIT slice shipped first and made the model cite
    whatever early-alphabet problem looked busy — wrong by design.)"""
    counts = {str(r["state"]): int(r["n"]) for r in conn.execute(
        "SELECT state, COUNT(*) AS n FROM problems GROUP BY state")}
    awaiting = [str(r["name"]) for r in conn.execute(
        "SELECT name FROM problems WHERE state = 'awaiting_human'"
        " ORDER BY name LIMIT 10")]
    recent = [
        {"name": str(r["name"]), "state": str(r["state"]),
         "last_decision_at": r["last_strategist_at"]}
        for r in conn.execute(
            "SELECT name, state, last_strategist_at FROM problems"
            " WHERE last_strategist_at IS NOT NULL"
            " ORDER BY last_strategist_at DESC LIMIT 8")]
    daemon: dict = {}
    try:
        from ..core.cli import daemon_status
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


def _page_context(workspace: Path, page: "dict | None") -> "tuple[str, str]":
    """(page_key, context_text). Best-effort; empty context is legal
    (fresh workspace, no DB)."""
    kind = str((page or {}).get("kind") or "board")
    name = (page or {}).get("name")
    key = f"{kind}:{name or ''}"
    conn = _connect(workspace)
    try:
        if conn is None:
            return key, f"Page: {kind}. (No database yet — fresh workspace.)"
        if kind == "problem" and name:
            return key, _problem_context(conn, str(name))
        if kind == "library" and name:
            return key, (
                f"Library chapter page for problem {name!r}: the archived,"
                f" human-signed form of its proofs. Sources live under"
                f" Library/ (Lean files; Read them for exact statements)."
            )
        if kind == "engine":
            # the console IS an overview surface — give it the board's
            # whole-run context (QA: an Engine-page question got "the
            # current view only shows daemon status" because that was
            # literally all we handed over)
            return key, _board_context(conn, workspace)
        if kind == "papers":
            from . import data as _data
            shelf = _data.papers_list(conn, workspace)["papers"][:30]
            rows = [{"id": p["id"],
                     "title": p["title"] or p["source_name"]}
                    for p in shelf]
            return key, json.dumps({"page": "papers", "papers": rows},
                                   ensure_ascii=False)
        return key, _board_context(conn, workspace)
    except sqlite3.Error:
        return key, f"Page: {kind}. (Context query failed — answer from" \
                    f" files instead.)"
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# spawn plumbing (dialects live in llm/explainer.py)


class _ChatState:
    def __init__(self) -> None:
        self.lock = threading.Lock()      # ONE question at a time
        #: the seated provider's resume handle for the live conversation
        #: — a caller-minted uuid, a provider-minted conversation id, or
        #: None forever on a backend that resumes nothing
        self.session_id: "str | None" = None
        self.page_key: "str | None" = None


class ChatBody(BaseModel):
    message: str
    page: "dict | None" = None   # {kind: board|problem|library|engine|papers, name?}
    model: "str | None" = None   # one of /api/chat/state's `models`


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
    def chat_state() -> dict:
        """What the drawer must know BEFORE the user types.

        `conversation_memory` and `read_scope` are the two ways a
        backend can be honestly worse than claude here (llm/explainer.py
        has the ruling). They ride this endpoint rather than an answer's
        events because both are properties of the seat, and a caveat
        that arrives after the question has been asked is a caveat that
        arrived too late.
        """
        name = explainer.provider(workspace)
        backend = explainer.backend_for(name)
        ok, detail = explainer.availability(name)
        return {
            "busy": state.lock.locked(),
            "has_session": state.session_id is not None,
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
    def chat_clear() -> dict:
        """Forget the conversation — both ends. The provider's session
        is simply abandoned (claude keeps sessions as files under the
        user's state and ages unreferenced ones out; agy's conversation
        id is dropped and never replayed)."""
        if state.lock.locked():
            raise HTTPException(status_code=409, detail="busy")
        state.session_id = None
        state.page_key = None
        return {"cleared": True}

    @app.post("/api/chat")
    async def chat(body: ChatBody) -> StreamingResponse:
        message = body.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="empty message")
        if len(message) > _MAX_MESSAGE:
            raise HTTPException(status_code=413, detail="message too long")
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
            page_key, context = _page_context(workspace, body.page)
            context = context[:_MAX_CONTEXT]
            # THE DEGRADATION, wired: on a provider that resumes nothing
            # `turn.resume` is False for every question, so the page
            # context below is re-sent every time instead of being left
            # to a session memory that does not exist.
            turn = explainer.plan_turn(provider, state.session_id)
            parts: "list[str]" = []
            if not turn.resume or page_key != state.page_key:
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
                                state.session_id = None
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
                        state.session_id = (
                            (item.get("handle") or turn.handle)
                            if explainer.remembers(provider) else None)
                        state.page_key = page_key
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
