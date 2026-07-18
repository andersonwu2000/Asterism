"""serve.chat — the explainer drawer's backend.

One endpoint pair: POST /api/chat streams an answer over SSE; POST
/api/chat/clear forgets the conversation. The answerer is a headless
`claude` spawn with a READ-ONLY tool surface (Read/Grep/Glob scoped to
the workspace + WebFetch pinned to the public notes site) — it explains
progress, code and framework mechanics; it can never act. That is a
soundness boundary, same tier as "sign-off cannot be machine-signed"
(design SoT: docs/internal/chat_explainer_design.md).

Conversation continuity rides claude CLI session persistence: the
first message mints a session id (--session-id), later messages
--resume it. One question at a time (single slot, non-blocking lock →
409 busy). The browser owns display history; the CLI session owns
model context; /api/chat/clear drops both ends together.

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
import shutil
import sqlite3
import subprocess
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..state import db

_MAX_MESSAGE = 8_000        # chars — a question, not an upload
_MAX_CONTEXT = 6_000        # chars — prebuilt page context budget
_TIMEOUT_SEC = int(os.environ.get("ASTERISM_EXPLAINER_TIMEOUT", "300"))
_MODELS = ("haiku", "sonnet", "opus")   # CLI aliases, cheapest first

# The public notes site doubles as the mechanism knowledge base for
# zip installs (no docs/ in the package; user call 2026-07-18: fetch
# live, don't bundle).
_NOTES_DOMAIN = os.environ.get(
    "ASTERISM_EXPLAINER_NOTES_DOMAIN", "andersonwu2000.github.io")

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
only when asked. Answer in the language the user writes in. Keep \
answers short by default — one focused paragraph unless depth is \
asked for. No emoji.
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


def _board_context(conn: sqlite3.Connection) -> str:
    rows = [
        {"name": str(r["name"]), "state": str(r["state"])}
        for r in conn.execute(
            "SELECT name, state FROM problems ORDER BY name LIMIT 40")]
    return json.dumps({"page": "board", "problems": rows},
                      ensure_ascii=False)


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
            from ..core.cli import daemon_status
            d = daemon_status(workspace)
            slim = {k: d.get(k) for k in
                    ("running", "starting", "scope", "started_at")}
            return key, json.dumps({"page": "engine", "daemon": slim},
                                   ensure_ascii=False)
        if kind == "papers":
            from . import data as _data
            shelf = _data.papers_list(conn, workspace)["papers"][:30]
            rows = [{"id": p["id"],
                     "title": p["title"] or p["source_name"]}
                    for p in shelf]
            return key, json.dumps({"page": "papers", "papers": rows},
                                   ensure_ascii=False)
        return key, _board_context(conn)
    except sqlite3.Error:
        return key, f"Page: {kind}. (Context query failed — answer from" \
                    f" files instead.)"
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# spawn plumbing


def _allowed_tools(workspace: Path) -> str:
    ws = workspace.as_posix()
    patterns = [
        f"Read({ws}/Problems/**)", f"Grep({ws}/Problems/**)",
        f"Read({ws}/Library/**/*.lean)", f"Grep({ws}/Library/**)",
        f"Read({ws}/Papers/**/*.md)", f"Grep({ws}/Papers/**)",
        # dev machines carry design docs in-repo; absent in zip installs
        f"Read({ws}/docs/**/*.md)", f"Grep({ws}/docs/**)",
        f"Glob({ws}/**)",
        f"WebFetch(domain:{_NOTES_DOMAIN})",
    ]
    return " ".join(patterns)


def _chat_cmd(workspace: Path, *, prompt: str, model: str,
              session_id: str, resume: bool) -> "list[str]":
    from ..llm.claude_cli import (_operator_state_deny_rules,
                                  _spawn_guard_settings_path)
    session_flags = (["--resume", session_id] if resume
                     else ["--session-id", session_id])
    return [
        "claude",
        "--model", model,
        "-p", prompt,
        "--append-system-prompt", _SYSTEM_PROMPT,
        # read-only surface: no Write/Edit/Bash in the tool set at all;
        # deny rules below are belt-over-braces for operator state
        "--tools", "Read Grep Glob WebFetch",
        "--allowed-tools", _allowed_tools(workspace),
        "--disallowedTools",
        "Read(**/.env)", "Read(**/.env.*)",
        *_operator_state_deny_rules(),
        "--settings", str(_spawn_guard_settings_path()),
        # no turn cap flag in this CLI — the endpoint's wall timeout is
        # the runaway stop
        "--output-format", "stream-json", "--verbose",
        "--include-partial-messages",
        "--setting-sources", "",
        "--disable-slash-commands",
        "--exclude-dynamic-system-prompt-sections",
        *session_flags,
    ]


def _reader(proc: subprocess.Popen, out: "queue.Queue[dict | None]") -> None:
    """stdout JSONL → UI events. Runs on its own thread; the SSE
    generator drains the queue. None = stream ended."""
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except ValueError:
                continue
            t = obj.get("type")
            if t == "system" and obj.get("subtype") == "init":
                out.put({"type": "status", "stage": "thinking"})
            elif t == "stream_event":
                ev = obj.get("event") or {}
                et = ev.get("type")
                if et == "content_block_start":
                    cb = ev.get("content_block") or {}
                    if cb.get("type") == "tool_use":
                        out.put({"type": "status", "stage": "reading",
                                 "tool": str(cb.get("name") or "")})
                    elif cb.get("type") == "thinking":
                        out.put({"type": "status", "stage": "thinking"})
                elif et == "content_block_delta":
                    d = ev.get("delta") or {}
                    if d.get("type") == "text_delta":
                        txt = d.get("text")
                        if isinstance(txt, str) and txt:
                            out.put({"type": "delta", "text": txt})
            elif t == "result":
                usage = obj.get("usage") or {}
                out.put({
                    "type": "done",
                    "ok": not bool(obj.get("is_error")),
                    "subtype": str(obj.get("subtype") or ""),
                    "turns": obj.get("num_turns"),
                    "output_tokens": usage.get("output_tokens"),
                })
    finally:
        out.put(None)


class _ChatState:
    def __init__(self) -> None:
        self.lock = threading.Lock()      # ONE question at a time
        self.session_id: "str | None" = None
        self.page_key: "str | None" = None


class ChatBody(BaseModel):
    message: str
    page: "dict | None" = None   # {kind: board|problem|library|engine|papers, name?}
    model: "str | None" = None   # haiku | sonnet | opus


def register(app: FastAPI, workspace: Path) -> None:
    state = _ChatState()
    app.state.chat = state  # tests reach the slot lock through here

    def _default_model() -> str:
        from ..core import config
        v = str(config.get("explainer.model",
                           env_var="ASTERISM_EXPLAINER_MODEL",
                           default="sonnet"))
        return v if v in _MODELS else v  # full model ids pass through

    @app.get("/api/chat/state")
    def chat_state() -> dict:
        return {
            "busy": state.lock.locked(),
            "has_session": state.session_id is not None,
            "model_default": _default_model(),
            "models": list(_MODELS),
        }

    @app.post("/api/chat/clear")
    def chat_clear() -> dict:
        """Forget the conversation — both ends. The CLI session is
        simply abandoned (sessions are files under the user's Claude
        state; unreferenced ones age out with the CLI's own hygiene)."""
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
        model = (body.model or "").strip() or _default_model()
        if not shutil.which("claude"):
            raise HTTPException(
                status_code=503,
                detail="Claude Code is not installed — the explainer"
                       " needs it (same login the engine uses)")
        if not state.lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="busy")

        # From here the lock is ours; the generator's finally releases
        # it (starlette always iterates the body, even on disconnect).
        # Until the generator exists, release on ANY exception — a
        # failed context build must not wedge the drawer shut.
        try:
            page_key, context = _page_context(workspace, body.page)
            context = context[:_MAX_CONTEXT]
            resume = state.session_id is not None
            sid = state.session_id or str(uuid.uuid4())
            parts: "list[str]" = []
            if not resume or page_key != state.page_key:
                parts.append(_CONTEXT_HEADER + context + "\n")
            parts.append(message)
            prompt = "\n".join(parts)

            env = dict(os.environ)
            env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        except BaseException:
            state.lock.release()
            raise

        def _spawn(with_resume: bool) -> subprocess.Popen:
            from ..core.process_group import no_window_creationflags
            return subprocess.Popen(
                _chat_cmd(workspace, prompt=prompt, model=model,
                          session_id=sid, resume=with_resume),
                env=env, cwd=str(workspace),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                creationflags=no_window_creationflags(),
            )

        async def gen():
            nonlocal sid, resume
            import asyncio
            proc: "subprocess.Popen | None" = None
            try:
                yield _sse({"type": "status", "stage": "context"})
                proc = _spawn(resume)
                q: "queue.Queue[dict | None]" = queue.Queue()
                threading.Thread(target=_reader, args=(proc, q),
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
                            # a dead --resume (aborted turn, swept
                            # session) gets ONE clean fresh-session
                            # retry before surfacing the error
                            err = ""
                            if proc.stderr is not None:
                                err = (proc.stderr.read() or "")[-400:]
                            if resume:
                                resume = False
                                sid = str(uuid.uuid4())
                                state.session_id = None
                                yield _sse({"type": "status",
                                            "stage": "retry"})
                                proc = _spawn(False)
                                q2: "queue.Queue[dict | None]" = \
                                    queue.Queue()
                                threading.Thread(
                                    target=_reader, args=(proc, q2),
                                    daemon=True,
                                    name="chat-reader-2").start()
                                q = q2
                                continue
                            yield _sse({"type": "error",
                                        "detail": f"claude exited rc={rc}"
                                                  f" {err}".strip()})
                        break
                    got_any = got_any or item.get("type") == "delta"
                    if item.get("type") == "done":
                        state.session_id = sid
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
