"""A refused edit is an outcome, and it used to leave nothing behind.

`_log_for` sat past every early return in `apply_edit`, so the only
outcome with no trace was the one investigations most need: when an
agent and the framework disagreed about whether an edit had landed,
the session log held the successes and was silent about the refusals
(2026-08-11 — that disagreement is unresolvable to this day).

Two layers here. The BEHAVIOUR tests refuse for real and read the log
back. The STRUCTURAL test walks `apply_edit`'s own AST and requires
every early return to be logged, so the next refusal path added cannot
go quiet the way these did — a list of known refusals would have to be
kept in step by hand, which is how this class of gap opens.
"""
from __future__ import annotations

import ast
import asyncio
import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from Tooling.lsp import gateway as lsp_gateway

#: `apply_edit`'s source, wherever it lives: it left the facade for
#: `gateway/rpc.py` with the A1-4a split, and a path pinned to the
#: package `__init__` would have turned the AST walk below into an
#: "gateway has no 'apply_edit'" error instead of a structural check.
GATEWAY = Path(lsp_gateway.rpc.__file__)


class _Backend:
    def clear_diagnostics(self, *a, **kw): ...
    def did_change_full(self, *a, **kw): ...
    def wait_for_diagnostics(self, *a, **kw): ...
    def diagnostics_for(self, *a, **kw): return []


def _session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
             content: str) -> Path:
    """A claimed session whose log is a real file (the harness that
    misses this bug entirely passes `log_path=None`, and `_log_for` is
    a silent no-op there)."""
    slot = lsp_gateway.WorkerSlot(
        slot_id=0, slot_path=tmp_path / "slot_0.lean",
        slot_uri="file:///fake/slot_0.lean", claimed_by="pipe-A",
        content_pipeline_id="pipe-A")
    monkeypatch.setattr(lsp_gateway._state, "workers", [slot])
    monkeypatch.setattr(lsp_gateway._state, "backend", _Backend())
    monkeypatch.setattr(lsp_gateway.rpc, "_ensure_backend_ready",
                        lambda *a, **kw: None)
    monkeypatch.setattr(lsp_gateway, "_ensure_imports",
                        lambda c, p, w: c)
    target = tmp_path / "x.lean"
    target.write_text(content, encoding="utf-8")
    log = tmp_path / "session.jsonl"
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=target, problem="p",
        workspace=tmp_path, log_path=log, file_content=content)
    with lsp_gateway._state.sessions_lock:
        lsp_gateway._state.sessions["tok-A"] = meta
    return log


@contextmanager
def _claimed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
             content: str):
    """The session is current only inside the block — the contextvar and
    the registry are shared state, and a leaked "tok-A" surfaces as an
    unrelated test failing somewhere else in the worker."""
    log = _session(monkeypatch, tmp_path, content)
    ctx = lsp_gateway._session_ctx.set("tok-A")
    try:
        yield log
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        with lsp_gateway._state.sessions_lock:
            lsp_gateway._state.sessions.pop("tok-A", None)


def _events(log: Path) -> list[dict]:
    if not log.is_file():
        return []
    return [json.loads(line) for line in
            log.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_an_unresolvable_anchor_is_logged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    with _claimed(monkeypatch, tmp_path,
                  "theorem t : True := trivial\n") as log:
        out = json.loads(asyncio.run(lsp_gateway.apply_edit(
            [{"replace": "no such text", "with": "x"}])))

    assert out["edit"].startswith("rejected")
    refusals = [e for e in _events(log) if e.get("outcome") == "refused"]
    assert refusals, (
        "the edit was refused and the session log says nothing — this is "
        "the trace whose absence made an 08-11 dispute unresolvable")
    assert refusals[-1]["event"] == "apply_edit"


def test_a_blocked_construct_is_logged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The metaprogramming gate refuses PRE-write; the file is untouched
    and so, before this, was the log."""
    with _claimed(monkeypatch, tmp_path, "-- body\n") as log:
        out = json.loads(asyncio.run(lsp_gateway.apply_edit(
            [{"replace": "-- body",
              "with": 'elab "x" : tactic => pure ()'}])))

    assert "elab" in out["error"]
    assert [e for e in _events(log) if e.get("outcome") == "refused"]


def test_a_successful_edit_is_not_marked_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    with _claimed(monkeypatch, tmp_path,
                  "theorem t : True := trivial\n") as log:
        out = json.loads(asyncio.run(lsp_gateway.apply_edit(
            [{"replace": "trivial", "with": "by trivial"}])))

    assert "error" not in out, out
    assert not [e for e in _events(log) if e.get("outcome") == "refused"]


def _fn(name: str) -> ast.AST:
    tree = ast.parse(GATEWAY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name):
            return node
    raise AssertionError(f"gateway has no {name!r}")


def _logs(block: list) -> bool:
    return any(isinstance(n, ast.Call)
               and getattr(n.func, "id", "") == "_log_for"
               for stmt in block for n in ast.walk(stmt))


def test_every_early_return_in_apply_edit_logs_first() -> None:
    """The enumeration, computed rather than listed. Each guard clause
    that returns must log inside the same branch.

    The ONE exemption is structural, not a judgement call: the branch
    taken when there is no session has nothing to log against — no
    metadata, no log path. It is identified by what it tests, so it
    cannot quietly grow to cover a second case.
    """
    fn = _fn("apply_edit")
    # Guard clauses AND except handlers: the anchor refusal — the most
    # common one by far, and the one the 08-11 dispute turned on — lives
    # in an `except EditError`, so an `ast.If`-only sweep would have
    # declared this closed while leaving it open.
    branches: list = []
    for stmt in fn.body:
        if isinstance(stmt, ast.If):
            branches.append((ast.unparse(stmt.test), stmt, stmt.body))
        elif isinstance(stmt, ast.Try):
            branches += [(f"except {ast.unparse(h.type) if h.type else ''}",
                          h, h.body) for h in stmt.handlers]
    unlogged = []
    for label, stmt, body in branches:
        if not any(isinstance(n, ast.Return) for n in ast.walk(stmt)):
            continue
        if label == "meta is None":
            continue                      # nothing to log against
        if _logs(body):
            continue
        # `_arg_help` answers a malformed CALL, not a refused edit: no
        # file was named and no anchor was resolved, so there is nothing
        # for an investigation to reconcile.
        if "_arg_help" in ast.unparse(stmt):
            continue
        unlogged.append(label)
    assert unlogged == [], (
        "apply_edit gained a refusal path that returns without logging: "
        f"{unlogged} — a refusal the log cannot see is exactly the gap "
        "this test exists to close")
