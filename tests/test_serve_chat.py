"""Explainer chat contract tests — everything EXCEPT a real spawn.

Same charter as the other serve tests: tmp workspace, no toolchain or
CLI spawn, no network. The spawn boundary is covered by construction
tests on the command line (read-only tool surface is an invariant, not
a hope) and a fake-Popen streaming test for the SSE path.

The provider-dialect half lives in `tests/test_explainer_backend.py`;
what is pinned HERE is the endpoint's behaviour — that it follows the
seated provider's DECLARATION rather than a provider's name.
"""
from __future__ import annotations

import io
import json
import queue
import sqlite3
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Tooling.llm import capabilities as caps
from Tooling.llm import explainer
from Tooling.serve import chat as _chat
from Tooling.serve.app import create_app
from Tooling.state import db


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    return tmp_path


def _open_db(workspace: Path) -> sqlite3.Connection:
    conn = db.connect(workspace / "asterism.db")
    db.init_schema(conn)
    return conn


def _client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


# -- endpoint contracts (no spawn) -----------------------------------------


def test_chat_state_shape(workspace: Path) -> None:
    r = _client(workspace).get("/api/chat/state")
    assert r.status_code == 200
    body = r.json()
    assert body["busy"] is False
    assert body["has_session"] is False
    assert body["models"] == ["haiku", "sonnet", "opus"]
    # the seat, and the two ways a seat can be honestly worse
    assert body["provider"] == "claude"
    assert body["conversation_memory"] is True
    assert body["read_scope"] == explainer.READ_SCOPE_WORKSPACE


def test_chat_state_publishes_the_seated_providers_own_answers(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seat the explainer on agy and the page must change what it
    promises: agy's models, no workspace read fence (its `read_file`
    permission is honoured in no direction), and a memory that comes
    from the CLI's own conversation id."""
    monkeypatch.setenv("ASTERISM_EXPLAINER_PROVIDER", "agy")
    body = _client(workspace).get("/api/chat/state").json()
    assert body["provider"] == "antigravity"
    assert body["models"] == list(explainer.ANTIGRAVITY.models)
    assert body["model_default"] == explainer.ANTIGRAVITY.default_model
    assert body["read_scope"] == explainer.READ_SCOPE_PROCESS
    assert "cannot be scoped" in body["read_note"]
    assert body["conversation_memory"] is True


def test_chat_rejects_empty_and_oversize(workspace: Path) -> None:
    c = _client(workspace)
    assert c.post("/api/chat", json={"message": "  "}).status_code == 400
    big = "x" * (_chat._MAX_MESSAGE + 1)
    assert c.post("/api/chat", json={"message": big}).status_code == 413


def test_chat_clear_resets_session(workspace: Path) -> None:
    c = _client(workspace)
    r = c.post("/api/chat/clear")
    assert r.status_code == 200 and r.json() == {"cleared": True}


# -- page context ----------------------------------------------------------


def test_page_context_fresh_workspace(workspace: Path) -> None:
    key, ctx = _chat._page_context(workspace, {"kind": "board"})
    assert key == "board:"
    assert "fresh workspace" in ctx.lower() or "no database" in ctx.lower()


def test_page_context_problem(workspace: Path) -> None:
    conn = _open_db(workspace)
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)",
        ("Topology.toy", db.now()))
    conn.execute(
        "INSERT INTO goals (problem, slug, statement, status, kind,"
        " origin, depth, lean_path, created_at, updated_at)"
        " VALUES (?, 'main', 'theorem main : True', 'open', 'theorem',"
        " 'root', 0, 'proofs/main.lean', ?, ?)",
        ("Topology.toy", db.now(), db.now()))
    conn.commit()
    conn.close()
    key, ctx = _chat._page_context(
        workspace, {"kind": "problem", "name": "Topology.toy"})
    assert key == "problem:Topology.toy"
    parsed = json.loads(ctx.split("\nDeeper detail:")[0])
    assert parsed["problem"] == "Topology.toy"
    assert parsed["goal_counts"] == {"open": 1}
    assert parsed["root_goals"][0]["slug"] == "main"


def test_page_context_unknown_problem(workspace: Path) -> None:
    _open_db(workspace).close()
    key, ctx = _chat._page_context(
        workspace, {"kind": "problem", "name": "No.such"})
    assert "unknown problem" in ctx


def test_page_context_bounded(workspace: Path) -> None:
    conn = _open_db(workspace)
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)",
        ("Topology.big", db.now()))
    for i in range(40):
        conn.execute(
            "INSERT INTO goals (problem, slug, statement, status, kind,"
            " origin, depth, lean_path, created_at, updated_at)"
            " VALUES (?, ?, ?, 'open', 'theorem', 'root', 0, ?, ?, ?)",
            ("Topology.big", f"g{i}", "s " * 500, f"proofs/g{i}.lean",
             db.now(), db.now()))
    conn.commit()
    conn.close()
    _, ctx = _chat._page_context(
        workspace, {"kind": "problem", "name": "Topology.big"})
    # roots are capped at 6 and statements clipped — stays in budget
    assert len(ctx) < _chat._MAX_CONTEXT


# -- stream reader ---------------------------------------------------------


class _FakeProc:
    def __init__(self, lines: "list[str]") -> None:
        self.stdout = io.StringIO("\n".join(lines) + "\n")


def _drain(q: "queue.Queue") -> "list[dict]":
    out = []
    while True:
        item = q.get(timeout=2)
        if item is None:
            return out
        out.append(item)


def test_reader_translates_stream_json() -> None:
    lines = [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s"}),
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_start",
            "content_block": {"type": "tool_use", "name": "Read"}}}),
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "hel"}}}),
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "lo"}}}),
        "not json at all",
        json.dumps({"type": "result", "subtype": "success",
                    "is_error": False, "num_turns": 2,
                    "usage": {"output_tokens": 9}}),
    ]
    q: "queue.Queue" = queue.Queue()
    t = threading.Thread(target=explainer.CLAUDE.reader,
                         args=(_FakeProc(lines), q))
    t.start()
    events = _drain(q)
    t.join(timeout=2)
    kinds = [e["type"] for e in events]
    assert kinds == ["status", "status", "delta", "delta", "done"]
    assert events[1] == {"type": "status", "stage": "reading",
                         "tool": "Read"}
    assert "".join(e["text"] for e in events if e["type"] == "delta") \
        == "hello"
    assert events[-1] == {"type": "done", "ok": True, "subtype": "success",
                          "turns": 2, "output_tokens": 9}


def test_reader_thinking_and_error_result() -> None:
    lines = [
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_start",
            "content_block": {"type": "thinking"}}}),
        json.dumps({"type": "result", "subtype": "error_during_execution",
                    "is_error": True}),
    ]
    q: "queue.Queue" = queue.Queue()
    explainer.CLAUDE.reader(_FakeProc(lines), q)
    events = _drain(q)
    assert events[0] == {"type": "status", "stage": "thinking"}
    assert events[-1]["type"] == "done" and events[-1]["ok"] is False


# -- busy slot -------------------------------------------------------------


# -- the endpoint follows the DECLARATION, not the provider's name ---------


_STREAM = [
    json.dumps({"type": "system", "subtype": "init"}),
    json.dumps({"type": "stream_event", "event": {
        "type": "content_block_delta",
        "delta": {"type": "text_delta", "text": "hi"}}}),
    json.dumps({"type": "result", "subtype": "success", "is_error": False,
                "num_turns": 1, "usage": {"output_tokens": 2}}),
]


class _FakePopen:
    """Enough of Popen for the SSE generator; records the argv."""

    def __init__(self, argv, **_kw) -> None:
        self.argv = list(argv)
        self.stdout = io.StringIO("\n".join(_STREAM) + "\n")
        self.stderr = io.StringIO("")

    def wait(self, timeout=None) -> int:  # noqa: ARG002
        return 0

    def poll(self) -> int:
        return 0

    def kill(self) -> None:
        pass


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> "list[_FakePopen]":
    """No real CLI, but the REAL availability gate: only the executable
    lookup is stubbed, so every test below still crosses it."""
    seen: "list[_FakePopen]" = []

    def _popen(argv, **kw):
        p = _FakePopen(argv, **kw)
        seen.append(p)
        return p

    monkeypatch.setattr(_chat.subprocess, "Popen", _popen)
    monkeypatch.setattr(explainer.CLAUDE, "executable",
                        lambda: "C:/claude.exe")
    monkeypatch.setattr(explainer.ANTIGRAVITY, "executable",
                        lambda: "C:/agy.exe")
    return seen


def _ask(client: TestClient, text: str = "hi") -> None:
    with client.stream("POST", "/api/chat", json={"message": text}) as r:
        assert r.status_code == 200
        for _ in r.iter_lines():
            pass


def test_second_question_resumes_when_the_declaration_says_it_can(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """Baseline for the flip below: claude declares
    RESUME_CALLER_SESSION_ID, so question 1 pins an id and question 2
    replays it."""
    app = create_app(workspace)
    c = TestClient(app)
    _ask(c)
    assert app.state.chat.session_id is not None
    assert "--session-id" in spawned[0].argv
    _ask(c, "and why?")
    assert "--resume" in spawned[1].argv
    assert c.get("/api/chat/state").json()["has_session"] is True


def test_no_resume_flag_and_no_session_when_the_declaration_says_none(
    workspace: Path, spawned: "list[_FakePopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SAME provider name, SAME backend, one field flipped: with
    `session_resume = none` the explainer must stop pretending to have a
    conversation. No resume flag ever reaches the CLI, the endpoint
    never claims a session, and the drawer is told
    `conversation_memory: false` — otherwise the user asks "and why is
    that?" into a blank context and reads the answer as continuous."""
    monkeypatch.setitem(
        caps.CAPABILITIES, "claude",
        caps.ProviderCapabilities(
            name="claude", rc_contract=caps.RC_STRUCTURED,
            stream_events=True, enforcement_strength=caps.ENFORCEMENT_HARD,
            allow_honoured_actions=caps.ALLOW_HONOURED_ALL,
            session_resume=caps.RESUME_NONE))
    app = create_app(workspace)
    c = TestClient(app)
    assert c.get("/api/chat/state").json()["conversation_memory"] is False
    _ask(c)
    _ask(c, "and why?")
    for p in spawned:
        assert "--resume" not in p.argv
        assert "--session-id" not in p.argv
    assert app.state.chat.session_id is None
    assert c.get("/api/chat/state").json()["has_session"] is False


def test_page_context_is_resent_when_there_is_no_memory(
    workspace: Path, spawned: "list[_FakePopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The degradation has to be WIRED, not only announced: with no
    session to carry it, the page context must ride every prompt.
    (With memory it is sent once and the session keeps it.)"""
    def _prompt(p: "_FakePopen") -> str:
        return p.argv[p.argv.index("-p") + 1]

    app = create_app(workspace)
    c = TestClient(app)
    _ask(c)
    _ask(c, "again")
    assert _chat._CONTEXT_HEADER not in _prompt(spawned[1])

    monkeypatch.setitem(
        caps.CAPABILITIES, "claude",
        caps.ProviderCapabilities(
            name="claude", rc_contract=caps.RC_STRUCTURED,
            stream_events=True, enforcement_strength=caps.ENFORCEMENT_HARD,
            allow_honoured_actions=caps.ALLOW_HONOURED_ALL,
            session_resume=caps.RESUME_NONE))
    spawned.clear()
    c2 = TestClient(create_app(workspace))
    _ask(c2)
    _ask(c2, "again")
    assert _chat._CONTEXT_HEADER in _prompt(spawned[1])


# -- the availability gate names the SEAT, never `claude` ------------------


def test_availability_gate_is_not_hardwired_to_claude(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A machine that installed only agy must not be told to install
    Claude Code — and a machine seated on agy WITHOUT agy must be told
    about agy. The 503 names the seat; the word `claude` appears in it
    only as one of the backends that could be chosen instead."""
    monkeypatch.setenv("ASTERISM_EXPLAINER_PROVIDER", "antigravity")
    monkeypatch.setattr(explainer.ANTIGRAVITY, "executable", lambda: None)
    r = _client(workspace).post("/api/chat", json={"message": "hi"})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert "antigravity" in detail
    assert "Claude Code is not installed" not in detail
    assert "explainer.provider" in detail


def test_the_gate_passes_on_agy_with_no_claude_installed(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
    spawned: "list[_FakePopen]",
) -> None:
    """The point of the whole change, as a test: claude absent, agy
    present, the button works — and the spawn is agy's."""
    monkeypatch.setenv("ASTERISM_EXPLAINER_PROVIDER", "agy")
    monkeypatch.setattr(explainer.CLAUDE, "executable", lambda: None)
    _ask(TestClient(create_app(workspace)))
    assert spawned and spawned[0].argv[0] == "C:/agy.exe"


def test_chat_busy_returns_409(workspace: Path, monkeypatch) -> None:
    monkeypatch.setattr(explainer.CLAUDE, "executable",
                        lambda: "C:/claude.exe")
    app = create_app(workspace)
    c = TestClient(app)
    state = app.state.chat
    assert state.lock.acquire(blocking=False)
    try:
        r = c.post("/api/chat", json={"message": "hi"})
        assert r.status_code == 409
        r = c.post("/api/chat/clear")
        assert r.status_code == 409
    finally:
        state.lock.release()


# -- the session is bound to a Project (HID §1.1-2, §3.5) ------------------


def _ask_in(client: TestClient, text: str = "hi", **body) -> None:
    with client.stream("POST", "/api/chat",
                       json={"message": text, **body}) as r:
        assert r.status_code == 200, r.read()
        for _ in r.iter_lines():
            pass


def _flag(p: "_FakePopen", flag: str) -> "str | None":
    return p.argv[p.argv.index(flag) + 1] if flag in p.argv else None


def _prompt_of(p: "_FakePopen") -> str:
    return p.argv[p.argv.index("-p") + 1]


def test_each_project_keeps_its_own_conversation(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """§1.1-2: switching Project switches session. One transcript per
    Project — the alternative (today's single site-wide session) answers
    a question about Erdos out of the context of a Topology page."""
    c = TestClient(create_app(workspace))
    _ask_in(c, project="Erdos")
    _ask_in(c, project="Topology")
    _ask_in(c, "and why?", project="Erdos")
    erdos = _flag(spawned[0], "--session-id")
    topo = _flag(spawned[1], "--session-id")
    assert erdos and topo and erdos != topo
    assert _flag(spawned[2], "--resume") == erdos


def test_the_project_picker_session_is_its_own_key(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """§1.4: the picker page has no Project. Its conversation must not
    become the first Project's — the person asked it with no problem in
    view."""
    c = TestClient(create_app(workspace))
    _ask_in(c)
    _ask_in(c, project="Erdos")
    assert _flag(spawned[1], "--resume") is None
    assert _flag(spawned[1], "--session-id") != \
        _flag(spawned[0], "--session-id")
    st = c.get("/api/chat/state", params={"project": "Erdos"}).json()
    assert st["has_session"] is True
    assert c.get("/api/chat/state").json()["has_session"] is True


def test_clear_forgets_only_the_named_project(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    c = TestClient(create_app(workspace))
    _ask_in(c, project="Erdos")
    _ask_in(c, project="Topology")
    assert c.post("/api/chat/clear",
                  json={"project": "Erdos"}).json() == {"cleared": True}
    assert c.get("/api/chat/state",
                 params={"project": "Erdos"}).json()["has_session"] is False
    assert c.get("/api/chat/state",
                 params={"project": "Topology"}
                 ).json()["has_session"] is True


def test_a_project_name_that_is_not_a_name_is_refused(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    r = TestClient(create_app(workspace)).post(
        "/api/chat", json={"message": "hi", "project": "../etc"})
    assert r.status_code == 422, r.text


# -- what the panel hands over (HID §1.4, §3.5) ---------------------------


def _seed(workspace: Path) -> "tuple[int, int]":
    """A Project with one problem, one goal and one group."""
    conn = _open_db(workspace)
    now = db.now()
    conn.execute("INSERT INTO projects (name, description, created_at)"
                 " VALUES ('Erdos', 'the shelf', ?)", (now,))
    conn.execute("INSERT INTO projects (name, description, created_at)"
                 " VALUES ('Other', '', ?)", (now,))
    conn.execute("INSERT INTO problems (name, project, state, created_at)"
                 " VALUES ('Erdos.p1', 'Erdos', 'active', ?)", (now,))
    conn.execute("INSERT INTO problems (name, project, state, created_at)"
                 " VALUES ('Other.p9', 'Other', 'active', ?)", (now,))
    conn.execute(
        "INSERT INTO goals (problem, slug, statement, status, kind,"
        " origin, depth, lean_path, created_at, updated_at)"
        " VALUES ('Erdos.p1', 'four_set_deficit', 'theorem d : True',"
        " 'attempting', 'theorem', 'root', 0, 'proofs/d.lean', ?, ?)",
        (now, now))
    gid = int(conn.execute("SELECT id FROM goals").fetchone()["id"])
    conn.execute(
        "INSERT INTO groups (problem, charter, status, anchor_goal_id,"
        " created_at, updated_at) VALUES ('Erdos.p1', 'the deficit is"
        " bounded', 'active', ?, ?, ?)", (gid, now, now))
    grid = int(conn.execute("SELECT id FROM groups").fetchone()["id"])
    conn.commit()
    conn.close()
    return gid, grid


def test_the_project_context_lists_that_projects_problems(
    workspace: Path,
) -> None:
    _seed(workspace)
    _key, ctx = _chat._page_context(workspace, {"kind": "board"},
                                    project="Erdos")
    assert "Erdos.p1" in ctx
    assert "Other.p9" not in ctx, "another Project's problems are not context"


def test_focus_on_a_goal_carries_the_goal(workspace: Path) -> None:
    gid, _grid = _seed(workspace)
    _key, ctx = _chat._page_context(workspace, {"kind": "problem",
                                                "name": "Erdos.p1"},
                                    project="Erdos",
                                    focus={"goal_id": gid})
    assert "four_set_deficit" in ctx
    assert "attempting" in ctx


def test_focus_on_a_group_carries_the_charter(workspace: Path) -> None:
    _gid, grid = _seed(workspace)
    _key, ctx = _chat._page_context(workspace, {"kind": "board"},
                                    project="Erdos",
                                    focus={"group_id": grid})
    assert "the deficit is bounded" in ctx


def test_focus_on_a_document_carries_its_text(workspace: Path) -> None:
    _seed(workspace)
    from Tooling.state import project_docs as _pd
    _pd.write(workspace, "Erdos", "user/plan.md", "the sketch I wrote\n")
    _key, ctx = _chat._page_context(workspace, {"kind": "board"},
                                    project="Erdos",
                                    focus={"doc_path": "user/plan.md"})
    assert "the sketch I wrote" in ctx


def test_focus_on_a_problem_is_that_problems_section(
    workspace: Path,
) -> None:
    _seed(workspace)
    _key, ctx = _chat._page_context(workspace, {"kind": "board"},
                                    project="Erdos",
                                    focus={"problem": "Erdos.p1"})
    assert "four_set_deficit" in ctx


def test_a_focus_that_names_nothing_says_so(workspace: Path) -> None:
    """A dangling id must not be answered with silence: the model would
    describe the page and the person would read it as an answer about
    the star they clicked."""
    _seed(workspace)
    _key, ctx = _chat._page_context(workspace, {"kind": "board"},
                                    project="Erdos",
                                    focus={"goal_id": 99999})
    assert "99999" in ctx


def test_changing_the_focus_re_sends_the_context(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """The context is re-sent when the page key changes, and the focus
    IS the page for a panel that follows the cursor (§1.4). Without it
    the second question is answered about the first star."""
    gid, _grid = _seed(workspace)
    c = TestClient(create_app(workspace))
    _ask_in(c, project="Erdos", focus={"goal_id": gid})
    _ask_in(c, "and this one?", project="Erdos", focus={"group_id": 1})
    assert _chat._CONTEXT_HEADER in _prompt_of(spawned[1])


def test_the_page_key_is_unchanged_without_a_project_or_focus(
    workspace: Path,
) -> None:
    """Backward compatibility, pinned: the drawer as it ships today
    sends neither, and must keep the exact context it had."""
    key, _ctx = _chat._page_context(workspace, {"kind": "problem",
                                                "name": "Topology.toy"})
    assert key == "problem:Topology.toy"
