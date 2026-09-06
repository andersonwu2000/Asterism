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
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Tooling.llm import capabilities as caps
from Tooling.llm import explainer
from Tooling.serve import chat as _chat
from Tooling.serve import chat_sessions as _sessions
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


def _session(client: TestClient, project: "str | None" = None) -> str:
    """A conversation to file questions on — what the panel does on
    mount when it holds no id for this Project."""
    r = client.post("/api/chat/sessions", json={"project": project})
    assert r.status_code == 200, r.text
    return r.json()["id"]


# -- endpoint contracts (no spawn) -----------------------------------------


def test_chat_state_shape(workspace: Path) -> None:
    r = _client(workspace).get("/api/chat/state")
    assert r.status_code == 200
    body = r.json()
    assert body["busy"] is False
    # the seat, and the two ways a seat can be honestly worse
    assert body["provider"] == "claude"
    assert body["conversation_memory"] is True
    assert body["read_scope"] == explainer.READ_SCOPE_WORKSPACE
    # RETIRED by the redesign: `has_session`/`session_key` described a
    # single live conversation per Project (there are many now, and the
    # browser holds which one is current), and `models` was a hand-kept
    # tuple on the backend (the picker's source is the catalog, §4).
    for gone in ("has_session", "session_key", "models"):
        assert gone not in body, gone


def test_the_picker_offers_every_explainer_backed_provider(
    workspace: Path,
) -> None:
    """§4: ONE picker, grouped by the backend that runs each name, from
    the same catalog the settings page reads. Filtered to providers that
    have an explainer backend — offering `codex` here would offer a
    choice the endpoint refuses by name a moment later."""
    from Tooling.serve import model_catalog

    body = _client(workspace).get("/api/chat/state").json()
    providers = {g["provider"] for g in body["groups"]}
    assert providers == set(explainer.BACKENDS)
    assert "codex" not in providers
    catalog = {g["provider"]: g["models"]
               for g in model_catalog.model_groups(workspace)}
    for g in body["groups"]:
        assert g["models"] == catalog[g["provider"]]
    # the default must be pickable, or the control cannot show the truth
    assert body["model_default"] in {m for g in body["groups"]
                                     for m in g["models"]}


def test_chat_state_publishes_the_seated_providers_own_answers(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seat the explainer on agy and the page must change what it
    promises: no workspace read fence (its `read_file` permission is
    honoured in no direction), a memory that comes from the CLI's own
    conversation id, and agy's own default model."""
    monkeypatch.setenv("ASTERISM_EXPLAINER_PROVIDER", "agy")
    body = _client(workspace).get("/api/chat/state").json()
    assert body["provider"] == "antigravity"
    assert body["model_default"] == explainer.ANTIGRAVITY.default_model
    assert body["read_scope"] == explainer.READ_SCOPE_PROCESS
    assert "cannot be scoped" in body["read_note"]
    assert body["conversation_memory"] is True


def test_chat_rejects_empty_and_oversize(workspace: Path) -> None:
    c = _client(workspace)
    sid = _session(c)
    assert c.post("/api/chat", json={"message": "  ", "session_id": sid}
                  ).status_code == 400
    big = "x" * (_chat._MAX_MESSAGE + 1)
    assert c.post("/api/chat", json={"message": big, "session_id": sid}
                  ).status_code == 413


def test_a_question_needs_a_session_that_exists(workspace: Path) -> None:
    """§2: `session_id` is required and an unknown one is a 404. The
    panel holding an id from a session deleted in another tab must be
    told so, not quietly filed on a new transcript."""
    c = _client(workspace)
    assert c.post("/api/chat", json={"message": "hi"}).status_code == 422
    r = c.post("/api/chat", json={"message": "hi", "session_id": "0" * 32})
    assert r.status_code == 404


def test_the_clear_endpoint_is_retired(workspace: Path) -> None:
    """Deleting the session is the act now (§1, the sessions fold's row
    strip). `clear` dropped both ends of ONE live conversation and had
    nothing to say about the other four."""
    assert _client(workspace).post(
        "/api/chat/clear").status_code in (404, 405)


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


# -- tool events, from a stream that actually happened ---------------------
#
# Captured 2026-09-06 from the real CLI, trimmed (signatures, usage
# detail and the tool result's tail cut; nothing renamed):
#
#   claude -p "Use the Glob tool to list web/src/lib/*.test.ts and reply
#   with the count only" --model claude-haiku-4-5 --output-format
#   stream-json --verbose --include-partial-messages --tools Glob
#   --allowed-tools "Glob(D:/Asterism/**)" --setting-sources ""
#   --disable-slash-commands
#
# A hand-written fixture here would freeze a GUESSED contract
# (frontend_state.md, 2026-07-29) — and the guess would have been wrong
# twice: `content_block_start` carries `input: {}` with the arguments
# arriving later as `input_json_delta` fragments, and the tool RESULT is
# not a stream_event at all but a top-level `user` message whose
# `content` was a plain string, with no `is_error` key on success.

_REAL_STREAM = [
    "{\"type\": \"system\", \"subtype\": \"init\", \"session_id\": \"455eaf84-f81c-467a-9c0d-edac0b9670ee\"}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_start\", \"index\": 0, \"content_block\": {\"type\": \"thinking\", \"thinking\": \"\", \"signature\": \"\"}}}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_stop\", \"index\": 0}}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_start\", \"index\": 1, \"content_block\": {\"type\": \"tool_use\", \"id\": \"toolu_01SBiojN8vWRodJ4FB3gXzhZ\", \"name\": \"Glob\", \"input\": {}, \"caller\": {\"type\": \"direct\"}}}}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_delta\", \"index\": 1, \"delta\": {\"type\": \"input_json_delta\", \"partial_json\": \"\"}}}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_delta\", \"index\": 1, \"delta\": {\"type\": \"input_json_delta\", \"partial_json\": \"{\\\"pattern\\\": \\\"web/src/lib/*.test.ts\"}}}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_delta\", \"index\": 1, \"delta\": {\"type\": \"input_json_delta\", \"partial_json\": \"\\\"}\"}}}",
    "{\"type\": \"assistant\", \"message\": {\"role\": \"assistant\", \"content\": [{\"type\": \"tool_use\", \"id\": \"toolu_01SBiojN8vWRodJ4FB3gXzhZ\", \"name\": \"Glob\", \"input\": {\"pattern\": \"web/src/lib/*.test.ts\"}, \"caller\": {\"type\": \"direct\"}}]}}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_stop\", \"index\": 1}}",
    "{\"type\": \"user\", \"message\": {\"role\": \"user\", \"content\": [{\"tool_use_id\": \"toolu_01SBiojN8vWRodJ4FB3gXzhZ\", \"type\": \"tool_result\", \"content\": \"web\\\\src\\\\lib\\\\groupTree.test.ts\\nweb\\\\src\\\\lib\\\\models.test.ts\\nweb \u2026\"}]}}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_start\", \"index\": 1, \"content_block\": {\"type\": \"text\", \"text\": \"\"}}}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_delta\", \"index\": 1, \"delta\": {\"type\": \"text_delta\", \"text\": \"21\"}}}",
    "{\"type\": \"stream_event\", \"event\": {\"type\": \"content_block_stop\", \"index\": 1}}",
    "{\"type\": \"result\", \"subtype\": \"success\", \"is_error\": false, \"num_turns\": 2, \"usage\": {\"output_tokens\": 331}}",
]


def test_reader_reports_the_tool_call_and_its_result() -> None:
    """§3: one row per tool call. `tool_start` when the arguments are
    complete (the block's stop, not its start — at the start `input` is
    `{}` and the panel would draw a row with no argument), `tool_end`
    when the result comes back, paired by the id the CLI minted."""
    q: "queue.Queue" = queue.Queue()
    explainer.CLAUDE.reader(_FakeProc(_REAL_STREAM), q)
    events = _drain(q)
    kinds = [e["type"] for e in events]
    assert "tool_start" in kinds and "tool_end" in kinds
    start = next(e for e in events if e["type"] == "tool_start")
    end = next(e for e in events if e["type"] == "tool_end")
    assert start == {"type": "tool_start",
                     "id": "toolu_01SBiojN8vWRodJ4FB3gXzhZ",
                     "name": "Glob",
                     "input": {"pattern": "web/src/lib/*.test.ts"}}
    assert end["id"] == start["id"] and end["ok"] is True
    assert isinstance(end["ms"], int) and end["ms"] >= 0
    assert "groupTree.test.ts" in end["result"]
    assert kinds.index("tool_start") < kinds.index("tool_end")
    # the events that already existed are untouched
    assert kinds[0] == "status"
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "21"
    assert events[-1] == {"type": "done", "ok": True, "subtype": "success",
                          "turns": 2, "output_tokens": 331}


def test_reader_clips_tool_arguments_and_results() -> None:
    """A `Read` of a 40k file would otherwise put 40k of prose in an
    SSE frame and in the transcript on disk. 200 chars is what the row
    can show."""
    long = "x" * 900
    lines = [
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_start", "index": 0,
            "content_block": {"type": "tool_use", "id": "t1",
                              "name": "Read", "input": {}}}}),
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "input_json_delta",
                      "partial_json": json.dumps(
                          {"file_path": long,
                           "nested": {"query": long},
                           "n": 7})}}}),
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_stop", "index": 0}}),
        json.dumps({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1",
             "content": [{"type": "text", "text": long}],
             "is_error": True}]}}),
    ]
    q: "queue.Queue" = queue.Queue()
    explainer.CLAUDE.reader(_FakeProc(lines), q)
    events = _drain(q)
    start = next(e for e in events if e["type"] == "tool_start")
    assert len(start["input"]["file_path"]) <= 200
    assert len(start["input"]["nested"]["query"]) <= 200
    assert start["input"]["n"] == 7, "only strings are clipped"
    end = next(e for e in events if e["type"] == "tool_end")
    assert len(end["result"]) <= 200
    assert end["ok"] is False, "is_error must reach the row"


def test_reader_emits_an_end_whose_start_it_never_saw() -> None:
    """Never drop what the engine said (§3's reduction rule, on the
    backend side): a resumed turn can carry a result whose call was
    made before this process attached."""
    lines = [json.dumps({"type": "user", "message": {"role": "user",
             "content": [{"type": "tool_result", "tool_use_id": "ghost",
                          "content": "done"}]}})]
    q: "queue.Queue" = queue.Queue()
    explainer.CLAUDE.reader(_FakeProc(lines), q)
    events = _drain(q)
    assert events[0] == {"type": "tool_end", "id": "ghost", "ok": True,
                         "ms": None, "result": "done"}


def test_reader_survives_arguments_that_never_parse() -> None:
    """A truncated stream (killed spawn) leaves half a JSON fragment.
    The row is still worth drawing — the tool name is the information."""
    lines = [
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_start", "index": 0,
            "content_block": {"type": "tool_use", "id": "t1",
                              "name": "loogle", "input": {}}}}),
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "input_json_delta",
                      "partial_json": "{\"query\": \"Nat.Pri"}}}),
        json.dumps({"type": "stream_event", "event": {
            "type": "content_block_stop", "index": 0}}),
    ]
    q: "queue.Queue" = queue.Queue()
    explainer.CLAUDE.reader(_FakeProc(lines), q)
    events = _drain(q)
    assert events[0] == {"type": "status", "stage": "reading",
                         "tool": "loogle"}
    assert events[1] == {"type": "tool_start", "id": "t1", "name": "loogle",
                         "input": {}}


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


#: Which stdout the next fake spawn serves. `_STREAM` is the minimal
#: answer; a test that needs tool rows swaps in the captured one.
_ACTIVE_STREAM: "dict[str, list[str]]" = {"lines": _STREAM}


class _FakePopen:
    """Enough of Popen for the SSE generator; records the argv."""

    def __init__(self, argv, **_kw) -> None:
        self.argv = list(argv)
        self.stdout = io.StringIO("\n".join(_ACTIVE_STREAM["lines"]) + "\n")
        self.stderr = io.StringIO("")
        self.killed = False

    def wait(self, timeout=None) -> int:  # noqa: ARG002
        return 0

    def poll(self) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True


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
    monkeypatch.setitem(_ACTIVE_STREAM, "lines", _STREAM)
    return seen


def _ask(client: TestClient, text: str = "hi", *, session: str,
         **body) -> "list[dict]":
    """One question on one session; returns the frames it streamed."""
    frames: "list[dict]" = []
    with client.stream("POST", "/api/chat",
                       json={"message": text, "session_id": session,
                             **body}) as r:
        assert r.status_code == 200, r.read()
        for line in r.iter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[6:]))
    return frames


def _prompt(p: "_FakePopen") -> str:
    return p.argv[p.argv.index("-p") + 1]


def test_second_question_resumes_when_the_declaration_says_it_can(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """Baseline for the flip below: claude declares
    RESUME_CALLER_SESSION_ID, so question 1 pins an id and question 2
    replays it. The handle now lives ON the session record, so it
    survives a serve restart with the transcript."""
    app = create_app(workspace)
    c = TestClient(app)
    sid = _session(c)
    _ask(c, session=sid)
    assert "--session-id" in spawned[0].argv
    assert _sessions.get(workspace, sid)["handle"] == \
        spawned[0].argv[spawned[0].argv.index("--session-id") + 1]
    _ask(c, "and why?", session=sid)
    assert "--resume" in spawned[1].argv


def test_no_resume_flag_and_no_session_when_the_declaration_says_none(
    workspace: Path, spawned: "list[_FakePopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SAME provider name, SAME backend, one field flipped: with
    `session_resume = none` the explainer must stop pretending to have a
    conversation. No resume flag ever reaches the CLI, the record keeps
    no handle, and the drawer is told `conversation_memory: false` —
    otherwise the user asks "and why is that?" into a blank context and
    reads the answer as continuous."""
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
    sid = _session(c)
    _ask(c, session=sid)
    _ask(c, "and why?", session=sid)
    for p in spawned:
        assert "--resume" not in p.argv
        assert "--session-id" not in p.argv
    assert _sessions.get(workspace, sid)["handle"] is None


def test_page_context_is_resent_when_there_is_no_memory(
    workspace: Path, spawned: "list[_FakePopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The degradation has to be WIRED, not only announced: with no
    session to carry it, the page context must ride every prompt.
    (With memory it is sent once and the session keeps it.)"""
    app = create_app(workspace)
    c = TestClient(app)
    sid = _session(c)
    _ask(c, session=sid)
    _ask(c, "again", session=sid)
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
    sid2 = _session(c2)
    _ask(c2, session=sid2)
    _ask(c2, "again", session=sid2)
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
    c = _client(workspace)
    r = c.post("/api/chat", json={"message": "hi",
                                  "session_id": _session(c)})
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
    c = TestClient(create_app(workspace))
    _ask(c, session=_session(c))
    assert spawned and spawned[0].argv[0] == "C:/agy.exe"


def test_chat_busy_returns_409(workspace: Path, monkeypatch) -> None:
    """One question at a time, and while it is in flight the transcript
    it is being written into may not be renamed, truncated or deleted
    out from under it."""
    monkeypatch.setattr(explainer.CLAUDE, "executable",
                        lambda: "C:/claude.exe")
    app = create_app(workspace)
    c = TestClient(app)
    sid = _session(c)
    state = app.state.chat
    assert state.lock.acquire(blocking=False)
    try:
        assert c.post("/api/chat", json={"message": "hi",
                                         "session_id": sid}
                      ).status_code == 409
        assert c.delete(f"/api/chat/sessions/{sid}").status_code == 409
        assert c.patch(f"/api/chat/sessions/{sid}",
                       json={"title": "x"}).status_code == 409
        # …but reading is always allowed: the fold polls
        assert c.get("/api/chat/sessions").status_code == 200
        assert c.get(f"/api/chat/sessions/{sid}").status_code == 200
        assert c.get("/api/chat/state").json()["busy"] is True
    finally:
        state.lock.release()


# -- the session is bound to a Project (HID §1.1-2, §3.5) ------------------


def _flag(p: "_FakePopen", flag: str) -> "str | None":
    return p.argv[p.argv.index(flag) + 1] if flag in p.argv else None


def _prompt_of(p: "_FakePopen") -> str:
    return p.argv[p.argv.index("-p") + 1]


def test_each_project_keeps_its_own_conversation(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """§1.1-2: every Project gets its own transcripts. Two sessions on
    two shelves are two provider conversations — the alternative (one
    site-wide session) answers a question about Erdos out of the context
    of a Topology page."""
    c = TestClient(create_app(workspace))
    erdos_sid = _session(c, "Erdos")
    topo_sid = _session(c, "Topology")
    _ask(c, session=erdos_sid, project="Erdos")
    _ask(c, session=topo_sid, project="Topology")
    _ask(c, "and why?", session=erdos_sid, project="Erdos")
    erdos = _flag(spawned[0], "--session-id")
    topo = _flag(spawned[1], "--session-id")
    assert erdos and topo and erdos != topo
    assert _flag(spawned[2], "--resume") == erdos
    assert [s["id"] for s in c.get(
        "/api/chat/sessions", params={"project": "Erdos"}
    ).json()["sessions"]] == [erdos_sid]


def test_a_question_cannot_be_filed_on_another_shelfs_transcript(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """§2: `project` must match the session's Project. The panel that
    switched shelves without switching session id would otherwise write
    an Erdos answer into the Topology conversation."""
    c = TestClient(create_app(workspace))
    sid = _session(c, "Erdos")
    r = c.post("/api/chat", json={"message": "hi", "session_id": sid,
                                  "project": "Topology"})
    assert r.status_code == 422, r.text
    assert "Erdos" in r.json()["detail"]


def test_the_project_picker_session_is_its_own_key(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """§1.4: the picker page has no Project. Its conversation must not
    become the first Project's — the person asked it with no problem in
    view."""
    c = TestClient(create_app(workspace))
    picker = _session(c)
    erdos = _session(c, "Erdos")
    assert picker != erdos
    _ask(c, session=picker)
    _ask(c, session=erdos, project="Erdos")
    assert _flag(spawned[1], "--resume") is None
    assert _flag(spawned[1], "--session-id") != \
        _flag(spawned[0], "--session-id")
    assert [s["id"] for s in
            c.get("/api/chat/sessions").json()["sessions"]] == [picker]


def test_a_project_name_that_is_not_a_name_is_refused(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    c = TestClient(create_app(workspace))
    r = c.post("/api/chat", json={"message": "hi", "project": "../etc",
                                  "session_id": _session(c)})
    assert r.status_code == 422, r.text
    assert c.post("/api/chat/sessions",
                  json={"project": "../etc"}).status_code == 422


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
    sid = _session(c, "Erdos")
    _ask(c, session=sid, project="Erdos", focus={"goal_id": gid})
    _ask(c, "and this one?", session=sid, project="Erdos",
         focus={"group_id": 1})
    assert _chat._CONTEXT_HEADER in _prompt_of(spawned[1])


def test_the_page_key_is_unchanged_without_a_project_or_focus(
    workspace: Path,
) -> None:
    """Backward compatibility, pinned: the drawer as it ships today
    sends neither, and must keep the exact context it had."""
    key, _ctx = _chat._page_context(workspace, {"kind": "problem",
                                                "name": "Topology.toy"})
    assert key == "problem:Topology.toy"


def test_the_board_context_inside_a_project_names_only_its_own(
    workspace: Path,
) -> None:
    """The Assistant's overview context was workspace-wide even when the
    person was standing inside a Project: another shelf's blocked task
    arrived as "what needs the human", one hallucination away from being
    answered about as if it were this Project's. `_project_context`
    below it already got this right — the overview did not."""
    _seed(workspace)
    conn = _open_db(workspace)
    now = db.now()
    for name in ("Erdos.p1", "Other.p9"):
        conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, brief, reason, payload, outcome,"
            " created_at, updated_at) VALUES (?, 0, 'routine',"
            " 'RequestUserAmend', '', '', '{}', 'awaiting_human', ?, ?)",
            (name, now, now))
        conn.execute("UPDATE problems SET state = 'awaiting_human',"
                     " last_strategist_at = ? WHERE name = ?", (now, name))
    conn.commit()
    conn.close()

    _key, ctx = _chat._page_context(workspace, {"kind": "engine"},
                                    project="Erdos")
    assert "Erdos.p1" in ctx
    assert "Other.p9" not in ctx, "another Project's blocked task is not context"


# -- the sessions endpoints (redesign §2) ---------------------------------


def test_sessions_crud(workspace: Path) -> None:
    c = _client(workspace)
    sid = _session(c, "Erdos")
    assert c.get("/api/chat/sessions",
                 params={"project": "Erdos"}).json()["sessions"][0]["id"] \
        == sid
    # the picker page's conversation is not the Project's
    assert c.get("/api/chat/sessions").json()["sessions"] == []
    full = c.get(f"/api/chat/sessions/{sid}").json()
    assert full["project"] == "Erdos" and full["turns"] == []
    named = c.patch(f"/api/chat/sessions/{sid}",
                    json={"title": "the p1 question"}).json()
    assert named["title"] == "the p1 question"
    assert c.delete(f"/api/chat/sessions/{sid}").json() == {"deleted": True}
    assert c.get(f"/api/chat/sessions/{sid}").status_code == 404
    assert c.delete(f"/api/chat/sessions/{sid}").status_code == 404
    assert c.patch(f"/api/chat/sessions/{sid}",
                   json={"title": "x"}).status_code == 404


def test_a_new_conversation_on_an_untouched_one_is_the_same_one(
    workspace: Path,
) -> None:
    """§2: `+ new conversation` clicked twice must not leave two blank
    rows in the fold."""
    c = _client(workspace)
    assert _session(c, "Erdos") == _session(c, "Erdos")


def test_the_first_frame_names_the_session(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """§3: the panel files the streaming turn on a transcript, and it
    must know which one before any text arrives."""
    c = TestClient(create_app(workspace))
    sid = _session(c)
    frames = _ask(c, session=sid)
    assert frames[0] == {"type": "session", "id": sid}


# -- edit & re-ask: truncation and the replay block ------------------------


def test_edit_and_re_ask_drops_the_later_turns_and_replays_the_rest(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """§2: no CLI can rewind, so a truncated conversation is planned
    COLD and the kept turns ride the prompt. Without the replay the
    engine answers the edited question with no idea what was asked
    before it."""
    c = TestClient(create_app(workspace))
    sid = _session(c)
    _ask(c, "why is p1 stalled?", session=sid)
    _ask(c, "and why is that?", session=sid)
    assert _chat._REPLAY_HEADER not in _prompt(spawned[1]), \
        "a resumed turn replays nothing — the engine has the session"

    _ask(c, "actually, what IS p1?", session=sid, truncate_to=2)
    last = spawned[-1]
    prompt = _prompt(last)
    assert "--resume" not in last.argv, "a truncated session is planned cold"
    assert _chat._REPLAY_HEADER in prompt
    assert "why is p1 stalled?" in prompt
    assert "and why is that?" not in prompt, "a dropped turn is gone"
    assert prompt.rstrip().endswith("actually, what IS p1?")
    rec = _sessions.get(workspace, sid)
    assert [t["text"] for t in rec["turns"]][:3] == [
        "why is p1 stalled?", "hi", "actually, what IS p1?"]


def test_truncate_to_must_name_a_question(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    c = TestClient(create_app(workspace))
    sid = _session(c)
    _ask(c, "why is p1 stalled?", session=sid)
    r = c.post("/api/chat", json={"message": "x", "session_id": sid,
                                  "truncate_to": 1})
    assert r.status_code == 422, r.text
    assert len(_sessions.get(workspace, sid)["turns"]) == 2


def test_the_replay_block_is_bounded(workspace: Path) -> None:
    """Most recent turns first to fit; each turn clipped. A transcript
    is unbounded and the prompt is not."""
    turns = [{"role": "user" if i % 2 == 0 else "assistant",
              "text": f"turn{i} " + "x" * 3_000}
             for i in range(40)]
    block = _chat._replay_block(turns)
    assert _chat._REPLAY_HEADER in block
    assert len(block) <= _chat._MAX_REPLAY + len(_chat._REPLAY_HEADER) + 200
    assert "turn39" in block, "the most recent turn is the one that must fit"
    assert "turn0" not in block
    # …and in reading order, oldest of the kept first
    assert block.index("turn38") < block.index("turn39")
    assert _chat._replay_block([]) == ""


# -- the idle deadline (redesign §3) --------------------------------------


class _SlowPopen(_FakePopen):
    """Alive until killed — so the generator's clock, not the fake's
    exhausted stdout, decides when the turn ends."""

    def poll(self):
        return 0 if self.killed else None


@pytest.fixture
def slow_spawn(monkeypatch: pytest.MonkeyPatch) -> "list[_SlowPopen]":
    seen: "list[_SlowPopen]" = []

    def _popen(argv, **kw):
        p = _SlowPopen(argv, **kw)
        seen.append(p)
        return p

    monkeypatch.setattr(_chat.subprocess, "Popen", _popen)
    monkeypatch.setattr(explainer.CLAUDE, "executable",
                        lambda: "C:/claude.exe")
    monkeypatch.setenv("ASTERISM_EXPLAINER_IDLE_SEC", "1")
    return seen


def test_a_working_turn_is_never_timed_out(
    workspace: Path, slow_spawn: "list[_SlowPopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The complaint this replaces: a wall clock over the whole answer
    killed turns that were visibly working. The clock is now IDLE — any
    event resets it — so a turn that keeps calling tools runs as long as
    it keeps talking."""
    def _reader(proc, out) -> None:
        for i in range(12):          # 3s of work at a 1s idle deadline
            time.sleep(0.25)
            out.put({"type": "tool_start", "id": f"t{i}", "name": "Glob",
                     "input": {}})
        out.put({"type": "delta", "text": "done thinking"})
        out.put({"type": "done", "ok": True, "subtype": "success",
                 "turns": 1, "output_tokens": 3})
        out.put(None)

    monkeypatch.setattr(explainer.CLAUDE, "reader", _reader)
    c = TestClient(create_app(workspace))
    frames = _ask(c, session=_session(c))
    kinds = [f["type"] for f in frames]
    assert "error" not in kinds, [f for f in frames if f["type"] == "error"]
    assert kinds.count("tool_start") == 12 and kinds[-1] == "done"


def test_a_silent_explainer_is_killed_and_named(
    workspace: Path, slow_spawn: "list[_SlowPopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """…and silence is still fatal, with an error that says what was
    silent for how long rather than "answer timed out"."""
    def _reader(proc, out) -> None:
        time.sleep(3)
        out.put(None)

    monkeypatch.setattr(explainer.CLAUDE, "reader", _reader)
    c = TestClient(create_app(workspace))
    frames = _ask(c, session=_session(c))
    err = [f for f in frames if f["type"] == "error"]
    assert err and err[0]["detail"] == "no word from the explainer for 1 s"
    assert slow_spawn[0].killed is True


def test_a_silent_wait_still_writes_to_the_socket(
    workspace: Path, slow_spawn: "list[_SlowPopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§3: an SSE COMMENT every 15s of silence, so a proxy (or the
    browser) never sees a socket with nothing on it. A comment, not a
    frame — the reducer must not have to know about it."""
    monkeypatch.setattr(_chat, "_KEEPALIVE_SEC", 0.3)
    monkeypatch.setenv("ASTERISM_EXPLAINER_IDLE_SEC", "10")

    def _reader(proc, out) -> None:
        time.sleep(1.2)
        out.put({"type": "delta", "text": "at last"})
        out.put({"type": "done", "ok": True, "subtype": "success",
                 "turns": 1, "output_tokens": 2})
        out.put(None)

    monkeypatch.setattr(explainer.CLAUDE, "reader", _reader)
    c = TestClient(create_app(workspace))
    sid = _session(c)
    with c.stream("POST", "/api/chat",
                  json={"message": "hi", "session_id": sid}) as r:
        body = "".join(chunk for chunk in r.iter_text())
    assert ": keepalive\n\n" in body
    assert "\"keepalive\"" not in body, "a comment line, not a data frame"
    assert "at last" in body


def test_the_idle_knob_also_caps_the_backend_that_has_no_stream(
    workspace: Path, spawned: "list[_FakePopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agy has no stream, so its whole-answer clock IS its idle clock —
    one knob, or the two disagree and the death arrives as a kill with
    no envelope to classify."""
    monkeypatch.setenv("ASTERISM_EXPLAINER_PROVIDER", "agy")
    monkeypatch.setenv("ASTERISM_EXPLAINER_IDLE_SEC", "400")
    c = TestClient(create_app(workspace))
    _ask(c, session=_session(c))
    assert _flag(spawned[0], "--print-timeout") == "385s"


# -- the transcript is written as the answer happens ----------------------


def test_the_turns_and_their_tool_rows_land_on_disk(
    workspace: Path, spawned: "list[_FakePopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§2's record, end to end: the question, the answer that streamed,
    and one row per tool call with the duration the panel shows."""
    monkeypatch.setitem(_ACTIVE_STREAM, "lines", _REAL_STREAM)
    c = TestClient(create_app(workspace))
    sid = _session(c)
    _ask(c, "how many lib tests?", session=sid)
    rec = _sessions.get(workspace, sid)
    assert [t["role"] for t in rec["turns"]] == ["user", "assistant"]
    assert rec["turns"][0]["text"] == "how many lib tests?"
    answer = rec["turns"][1]
    assert answer["text"] == "21" and answer["ok"] is True
    assert len(answer["tools"]) == 1
    row = answer["tools"][0]
    assert row["name"] == "Glob" and row["ok"] is True
    assert row["input"] == {"pattern": "web/src/lib/*.test.ts"}
    assert isinstance(row["ms"], int)
    assert "groupTree.test.ts" in row["result"]
    assert rec["title"] == "how many lib tests?"
    assert rec["model"] and rec["provider"] == "claude"


def test_a_question_whose_spawn_failed_leaves_no_trace(
    workspace: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§2: the panel rolls the text back into the composer, so a
    transcript showing the question with no answer would contradict the
    screen."""
    monkeypatch.setattr(explainer.CLAUDE, "executable",
                        lambda: "C:/claude.exe")

    def _boom(*_a, **_kw):
        raise OSError("no such file")

    monkeypatch.setattr(_chat.subprocess, "Popen", _boom)
    c = TestClient(create_app(workspace))
    sid = _session(c)
    frames = _ask(c, "doomed", session=sid)
    assert frames[-1]["type"] == "error"
    assert _sessions.get(workspace, sid)["turns"] == []


def test_a_partial_answer_survives_the_reader_walking_away(
    workspace: Path, slow_spawn: "list[_SlowPopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§2: partial answers are first-class. Closing the tab mid-answer
    must keep what streamed — the person read it."""
    def _reader(proc, out) -> None:
        out.put({"type": "delta", "text": "the task is waiting on"})
        time.sleep(3)
        out.put(None)

    monkeypatch.setattr(explainer.CLAUDE, "reader", _reader)
    app = create_app(workspace)
    c = TestClient(app)
    sid = _session(c)
    with c.stream("POST", "/api/chat",
                  json={"message": "why?", "session_id": sid}) as r:
        for line in r.iter_lines():
            if "\"delta\"" in line:
                break                      # closed tab / stop button
    for _ in range(500):                   # the lock is released last
        if not app.state.chat.lock.locked():
            break
        time.sleep(0.01)
    rec = _sessions.get(workspace, sid)
    assert [t["role"] for t in rec["turns"]] == ["user", "assistant"]
    assert rec["turns"][1]["text"] == "the task is waiting on"
    assert rec["turns"][1]["ok"] is False


# -- the model decides the backend for the turn (redesign §4) -------------


def test_an_off_list_model_is_refused_and_the_offer_is_named(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    c = TestClient(create_app(workspace))
    r = c.post("/api/chat", json={"message": "hi", "session_id": _session(c),
                                  "model": "gpt-9-ultra"})
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "gpt-9-ultra" in detail and "claude-sonnet-5" in detail


def test_the_model_choice_seats_the_backend_for_the_turn(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """§4: one picker decides both. A machine seated on claude that
    picks a gemini name gets agy's spawn — the backend is implied by
    the model, so the two cannot disagree."""
    c = TestClient(create_app(workspace))
    _ask(c, session=_session(c), model="gemini-3.6-flash-high")
    assert spawned[0].argv[0] == "C:/agy.exe"


def test_a_conversation_cannot_change_backends_midway(
    workspace: Path, spawned: "list[_FakePopen]",
) -> None:
    """The resume handle belongs to ONE CLI: switching provider inside a
    session would replay a claude session id at agy."""
    c = TestClient(create_app(workspace))
    sid = _session(c)
    _ask(c, session=sid)
    assert _sessions.get(workspace, sid)["provider"] == "claude"
    r = c.post("/api/chat", json={"message": "and why?", "session_id": sid,
                                  "model": "gemini-3.6-flash-high"})
    assert r.status_code == 422, r.text
    assert "new conversation" in r.json()["detail"]
    # …but a fresh session may be seated anywhere
    _ask(c, session=_session(c), model="gemini-3.6-flash-high")
    assert spawned[-1].argv[0] == "C:/agy.exe"


# -- a turn that ends without ending (incident 2026-09-06 13:44–13:48Z) ---


#: The stream as it stopped that afternoon: a sentence, a tool call,
#: and then nothing — no `tool_result`, no `result`. Built from the
#: captured one so the shape is the CLI's, not a guess.
_CUT_MID_TOOL = [
    _REAL_STREAM[0],
    json.dumps({"type": "stream_event", "event": {
        "type": "content_block_delta", "index": 0,
        "delta": {"type": "text_delta",
                  "text": "I will compile it and read the errors."}}}),
    *_REAL_STREAM[3:9],
]


def test_a_stream_that_stops_mid_tool_reaches_the_panel_as_an_error(
    workspace: Path, spawned: "list[_FakePopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-09-06 13:48:12Z: the CLI went away while `tex_check` was
    still running. The loop broke on the reader's EOF without a `done`,
    the `rc != 0 and not got_any` guard did not fire (prose HAD
    streamed), and so the turn ended with no `done` and no `error` at
    all — the panel kept a `tex_check ▸` row pulsing under an answer
    that never came, and the record read `ok: False, note: None`.

    Silence is not an ending. A turn that stops without `done` is a
    failure that has to SAY so: on the wire, on the record, and on the
    row it stopped inside."""
    monkeypatch.setitem(_ACTIVE_STREAM, "lines", _CUT_MID_TOOL)
    c = TestClient(create_app(workspace))
    sid = _session(c)
    frames = _ask(c, "compile it", session=sid)
    assert [f["type"] for f in frames].count("done") == 0, frames
    assert frames[-1]["type"] == "error", frames
    # the reason names the row it died inside — "it stopped" is not a
    # reason, and the tool is the only thing the reader can act on
    assert "Glob" in frames[-1]["detail"], frames[-1]
    rec = _sessions.get(workspace, sid)
    turn = rec["turns"][-1]
    assert turn["role"] == "assistant" and turn["ok"] is False
    assert turn["note"], turn
    assert turn["tools"][-1]["ok"] is False, turn["tools"]


def test_a_reader_that_walks_away_leaves_the_reason_on_the_record(
    workspace: Path, slow_spawn: "list[_SlowPopen]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The partial answer is kept (that is already pinned above); what
    was missing is WHY it is partial. A turn read back a week later with
    `ok: False` and nothing else cannot be told from a turn the engine
    failed."""
    def _reader(proc, out) -> None:
        out.put({"type": "tool_start", "id": "t1", "name": "tex_check",
                 "input": {"path": "user/paper.tex"}})
        out.put({"type": "delta", "text": "compiling"})
        time.sleep(3)
        out.put(None)

    monkeypatch.setattr(explainer.CLAUDE, "reader", _reader)
    app = create_app(workspace)
    c = TestClient(app)
    sid = _session(c)
    with c.stream("POST", "/api/chat",
                  json={"message": "why?", "session_id": sid}) as r:
        for line in r.iter_lines():
            if "\"delta\"" in line:
                break                      # closed tab / stop button
    for _ in range(500):
        if not app.state.chat.lock.locked():
            break
        time.sleep(0.01)
    turn = _sessions.get(workspace, sid)["turns"][-1]
    assert turn["ok"] is False
    assert turn["note"], turn
    assert turn["tools"][-1]["ok"] is False, turn["tools"]


def test_the_tex_box_fits_inside_the_turn_that_waits_for_it() -> None:
    """A tool call is SILENCE on this stream: nothing crosses it while
    `tex_check` compiles, so the turn's idle deadline is the real
    ceiling on the tex time box — and the CLI's own MCP tool timeout
    has to sit above both, or the answer is discarded before it is
    handed back. Three clocks, one order, pinned here so raising any of
    them alone fails."""
    from Tooling.core import tex_engine
    from Tooling.llm.base import MCP_TOOL_TIMEOUT_SEC

    assert tex_engine.TIMEOUT_SEC + 120 <= _chat._IDLE_SEC_DEFAULT
    assert tex_engine.TIMEOUT_SEC + 300 <= MCP_TOOL_TIMEOUT_SEC
