"""Explainer chat contract tests — everything EXCEPT the claude spawn.

Same charter as the other serve tests: tmp workspace, no toolchain or
CLI spawn, no network. The spawn boundary is covered by construction
tests on the command line (read-only tool surface is an invariant, not
a hope) and a fake-Popen streaming test for the SSE path.
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


# -- read-only surface invariants ------------------------------------------


def test_chat_cmd_tool_surface_is_read_only(workspace: Path) -> None:
    cmd = _chat._chat_cmd(workspace, prompt="q", model="sonnet",
                          session_id="s", resume=False)
    tools = cmd[cmd.index("--tools") + 1]
    for banned in ("Write", "Edit", "Bash", "NotebookEdit"):
        assert banned not in tools.split()
    assert "Read" in tools.split() and "Grep" in tools.split()
    # deny rules pin the operator's Claude state out even of Read
    joined = " ".join(cmd)
    assert ".claude/projects" in joined
    assert "Read(**/.env)" in cmd


def test_chat_cmd_session_flags(workspace: Path) -> None:
    fresh = _chat._chat_cmd(workspace, prompt="q", model="sonnet",
                            session_id="abc", resume=False)
    assert ["--session-id", "abc"] == fresh[-2:]
    resumed = _chat._chat_cmd(workspace, prompt="q", model="sonnet",
                              session_id="abc", resume=True)
    assert ["--resume", "abc"] == resumed[-2:]


def test_allowed_tools_scoped_to_workspace(workspace: Path) -> None:
    pats = _chat._allowed_tools(workspace).split()
    ws = workspace.as_posix()
    for p in pats:
        if p.startswith(("Read(", "Grep(", "Glob(")):
            assert ws in p, p
    assert any(p.startswith("WebFetch(domain:") for p in pats)


# -- endpoint contracts (no spawn) -----------------------------------------


def test_chat_state_shape(workspace: Path) -> None:
    r = _client(workspace).get("/api/chat/state")
    assert r.status_code == 200
    body = r.json()
    assert body["busy"] is False
    assert body["has_session"] is False
    assert body["models"] == ["haiku", "sonnet", "opus"]


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
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, ?, ?)",
        ("Topology.toy", "Problems/Topology/toy/Manifest.md", db.now()))
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
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, ?, ?)",
        ("Topology.big", "Problems/Topology/big/Manifest.md", db.now()))
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
    t = threading.Thread(target=_chat._reader, args=(_FakeProc(lines), q))
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
    _chat._reader(_FakeProc(lines), q)
    events = _drain(q)
    assert events[0] == {"type": "status", "stage": "thinking"}
    assert events[-1]["type"] == "done" and events[-1]["ok"] is False


# -- busy slot -------------------------------------------------------------


def test_chat_busy_returns_409(workspace: Path, monkeypatch) -> None:
    monkeypatch.setattr(_chat.shutil, "which", lambda _: "claude")
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
