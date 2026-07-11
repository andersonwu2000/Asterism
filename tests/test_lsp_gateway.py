"""Tooling/lsp_gateway.py — module-level smoke + REST + slot pool.

Phase 2: 1 server + W persistent workers + LRU content swap on tool
call. These tests don't spawn a real `lake serve` (integration-level);
they verify the in-memory machinery: tool registration, session
metadata, REST endpoint contract, contextvar plumbing, slot pool LRU
ordering + lock contention.

End-to-end (gateway subprocess + claude HTTP MCP + real lake serve +
real Mathlib elaborate) lives outside the unit suite — see PN run
validation in Phase 2 acceptance.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from Tooling.lsp import gateway as lsp_gateway
from Tooling.lsp.gateway import (
    SessionMetadata,
    _ensure_imports,
    _format_diag,
    _release_session_internal,
    _session_ctx,
    _state,
)
from Tooling.state import db


@pytest.mark.skipif(sys.platform != "win32",
                    reason="asyncio.WindowsSelectorEventLoopPolicy does not "
                           "exist in POSIX asyncio builds")
def test_install_windows_event_loop_policy_on_win32(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On Windows, the gateway switches asyncio to Selector policy
    before starting uvicorn — works around the
    IocpProactor.accept WinError 64 race observed in SG run #14
    (2026-05-11) which left the listening socket bound but no longer
    accepting connections."""
    import asyncio
    monkeypatch.setattr(lsp_gateway.sys, "platform", "win32")
    calls = {"policy": None}

    def fake_set_policy(p):
        calls["policy"] = p

    monkeypatch.setattr(asyncio, "set_event_loop_policy", fake_set_policy)
    lsp_gateway._install_windows_event_loop_policy()
    assert isinstance(calls["policy"], asyncio.WindowsSelectorEventLoopPolicy)


def test_install_windows_event_loop_policy_noop_on_non_win32(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On non-Windows platforms the helper is a no-op — Selector vs
    Proactor is a Windows-only consideration; Linux/macOS already use
    epoll/kqueue without this issue."""
    import asyncio
    monkeypatch.setattr(lsp_gateway.sys, "platform", "linux")
    calls = {"n": 0}
    monkeypatch.setattr(asyncio, "set_event_loop_policy",
                        lambda p: calls.__setitem__("n", calls["n"] + 1))
    lsp_gateway._install_windows_event_loop_policy()
    assert calls["n"] == 0


def test_four_tools_registered() -> None:
    """The gateway exposes the same 4 tools as the per-spawn server
    (apply_edit / goal_at / errors_at / validate_file) so agents see
    an identical surface."""
    names = {t.name for t in lsp_gateway.mcp._tool_manager.list_tools()}
    assert names == {"apply_edit", "goal_at", "errors_at",
                     "validate_file"}


def test_format_diag_normalizes_lsp_shape() -> None:
    """LSP-wire format: 0-indexed line/col + numeric severity. Our
    format normalizes to 1-indexed line + named severity for readable
    forensic + agent-friendly output."""
    raw = {
        "range": {"start": {"line": 5, "character": 12}},
        "severity": 1,
        "message": "boom",
    }
    formatted = _format_diag(raw)
    assert formatted == {"line": 6, "col": 12,
                         "severity": "error", "message": "boom"}


def test_ensure_imports_idempotent(tmp_path: Path) -> None:
    """`_ensure_imports` prepends Mathlib + Defs imports when missing.
    Repeat calls don't double-add."""
    pdir = tmp_path / "Problems" / "myprob"
    pdir.mkdir(parents=True)
    (pdir / "Defs.lean").write_text("namespace Foo\nend Foo\n",
                                     encoding="utf-8")
    bare = "theorem t : True := by sorry"
    once = _ensure_imports(bare, "myprob", tmp_path)
    twice = _ensure_imports(once, "myprob", tmp_path)
    assert "import Mathlib" in once
    assert "import Problems.myprob.Defs" in once
    assert once == twice  # idempotent


def test_session_release_idempotent_unknown_token() -> None:
    """`_release_session_internal` on a token not in the session map
    must be a silent no-op — daemon teardown calls it on stale tokens
    and shouldn't throw."""
    _release_session_internal("nonexistent-token-xyz")  # no raise


def test_current_session_uses_contextvar(tmp_path: Path) -> None:
    """Tool bodies resolve their session via _session_ctx contextvar
    (set by SessionHeaderMiddleware on each HTTP request). Verify the
    plumbing without HTTP: directly set the contextvar, register a
    fake session, confirm `_current_session()` returns it."""
    fake = SessionMetadata(
        pipeline_id="pipe-test",
        target_path=tmp_path / "x.lean",
        problem="test",
        workspace=tmp_path,
        log_path=None,
        file_content="",
    )
    token = "test-token-abc"
    with _state.sessions_lock:
        _state.sessions[token] = fake
    try:
        ctx = _session_ctx.set(token)
        try:
            assert lsp_gateway._current_session() is fake
        finally:
            _session_ctx.reset(ctx)
        # Outside the contextvar set: returns None.
        assert lsp_gateway._current_session() is None
    finally:
        with _state.sessions_lock:
            _state.sessions.pop(token, None)


def test_session_header_middleware_sets_and_resets_contextvar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`SessionHeaderMiddleware.__call__` reads X-Asterism-Session,
    sets the contextvar, calls the inner ASGI app, then resets. Verify
    the lifecycle: app sees the token, post-call returns to None."""
    seen: list = []

    async def app(scope, receive, send):
        seen.append(_session_ctx.get())

    mw = lsp_gateway.SessionHeaderMiddleware(app)
    scope = {
        "type": "http",
        "headers": [(b"x-asterism-session", b"hdr-token-123")],
    }

    import asyncio
    asyncio.run(mw(scope, lambda: None, lambda x: None))

    assert seen == ["hdr-token-123"]
    # After the middleware returns, the contextvar is back to default.
    assert _session_ctx.get() is None


def test_session_header_middleware_no_header_yields_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requests without X-Asterism-Session (e.g. /health) get None
    on the contextvar; tool calls in that scope correctly report
    'no session'."""
    seen: list = []

    async def app(scope, receive, send):
        seen.append(_session_ctx.get())

    mw = lsp_gateway.SessionHeaderMiddleware(app)
    scope = {"type": "http", "headers": []}

    import asyncio
    asyncio.run(mw(scope, lambda: None, lambda x: None))

    assert seen == [None]


# ─── Phase 2: slot pool + 1:1 binding + lock contention ───────────

def _make_fake_slot(
    slot_id: int, *,
    claimed_by: str | None = None,
    content_pipeline_id: str | None = None,
    last_used: float = 0.0,
) -> lsp_gateway.WorkerSlot:
    """Bare WorkerSlot for in-memory tests — no real LSP. Defaults
    leave the slot unclaimed and content-less (post-warmup state)."""
    return lsp_gateway.WorkerSlot(
        slot_id=slot_id,
        slot_path=Path(f"/fake/slot_{slot_id}.lean"),
        slot_uri=f"file:///fake/slot_{slot_id}.lean",
        claimed_by=claimed_by,
        content_pipeline_id=content_pipeline_id,
        last_used_ts=last_used,
    )


def test_acquire_slot_hot_path_no_swap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Pipeline's claimed slot already has its content didChanged in
    (hot state) → acquire returns 'hot' WITHOUT invoking LSP
    didChange. Verify by stubbing backend methods."""
    slots = [_make_fake_slot(0),
             _make_fake_slot(1, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A",
                             last_used=20.0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, *a, **kw): self.calls.append("didChange")
        def clear_diagnostics(self, *a): self.calls.append("clear")
        def wait_for_diagnostics(self, *a, **kw):
            self.calls.append("wait_diag")
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="content for pipe-A",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=True) as (s, kind):
        assert s.slot_id == 1  # the slot claimed for pipe-A
        assert kind == "hot"
    # No didChange / clear calls — pure hot-path acquire.
    assert fake.calls == []


def test_resync_buffer_from_disk_adopts_newer_disk(tmp_path: Path) -> None:
    """T1: an external Write/Edit advances disk past the in-memory mirror;
    `_resync_buffer_from_disk` adopts disk so swap_in tools didChange the
    current content (no phantom stale-line diagnostics)."""
    target = tmp_path / "patch.lean"
    target.write_text("theorem t : True := by trivial\n", encoding="utf-8")
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=target,
        problem="p", workspace=tmp_path, log_path=None,
        file_content="STALE BUFFER",
    )
    lsp_gateway._resync_buffer_from_disk(meta)
    assert meta.file_content == "theorem t : True := by trivial\n"


def test_resync_buffer_from_disk_noop_when_in_sync(tmp_path: Path) -> None:
    """No mismatch → no mutation (cheap, idempotent — the common case
    where the agent only ever used apply_edit)."""
    target = tmp_path / "patch.lean"
    content = "import Mathlib\n"
    target.write_text(content, encoding="utf-8")
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=target,
        problem="p", workspace=tmp_path, log_path=None,
        file_content=content,
    )
    lsp_gateway._resync_buffer_from_disk(meta)
    assert meta.file_content == content


def test_resync_buffer_from_disk_missing_file_is_noop(
    tmp_path: Path,
) -> None:
    """Disk file absent (never written yet) → keep the mirror, never
    crash on the OSError."""
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "nope.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="in-memory only",
    )
    lsp_gateway._resync_buffer_from_disk(meta)
    assert meta.file_content == "in-memory only"


def test_sorry_start_col_finds_first_sorry(tmp_path: Path) -> None:
    """B#4: goal_at's fallback re-queries at the `sorry` token's start (where
    the goal is still live; empty inside/after — verified 2026-06-22). The
    helper returns that 0-indexed column on the agent's 1-indexed line."""
    target = tmp_path / "patch.lean"
    target.write_text(
        "theorem t1 : True := by sorry\n"        # sorry @ col 24
        "theorem t2 (p : Prop) : p := by\n"
        "  sorry\n"                               # sorry @ col 2
        "-- a comment line\n",                    # no sorry
        encoding="utf-8")
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="p", target_path=target, problem="p",
        workspace=tmp_path, log_path=None, file_content="")
    assert lsp_gateway._sorry_start_col(meta, 1) == 24
    assert lsp_gateway._sorry_start_col(meta, 3) == 2
    assert lsp_gateway._sorry_start_col(meta, 4) is None    # no sorry
    assert lsp_gateway._sorry_start_col(meta, 99) is None   # out of range


def test_sorry_start_col_missing_file_is_none(tmp_path: Path) -> None:
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="p", target_path=tmp_path / "nope.lean", problem="p",
        workspace=tmp_path, log_path=None, file_content="")
    assert lsp_gateway._sorry_start_col(meta, 1) is None


def test_goal_present_distinguishes_live_vs_empty() -> None:
    assert lsp_gateway._goal_present({"goals": ["⊢ True"]})
    assert lsp_gateway._goal_present({"rendered": "⊢ True"})
    assert not lsp_gateway._goal_present({"goals": []})
    assert not lsp_gateway._goal_present({})
    assert not lsp_gateway._goal_present(None)


def test_inline_sibling_stubs_hoists_imports_and_maps_lines() -> None:
    """T3: sibling decls precede content; all imports hoisted+deduped to
    the top; line_map sends content-body lines back to their original
    1-indexed positions, AGENT-written import lines back to their own
    origin (a bad import is the agent's diagnostic, not sibling noise),
    and framework/sibling lines to None."""
    content = (
        "import Mathlib\n"            # line 1
        "import Problems.p.Defs\n"    # line 2
        "\n"                          # line 3
        "namespace Problems.p\n"      # line 4
        "theorem s1 : True := by\n"   # line 5
        "  have h := helper 3\n"      # line 6
        "  trivial\n"                 # line 7
        "end Problems.p\n"            # line 8
    )
    sibling = (
        "import Mathlib\n"
        "import Problems.p.extra\n"
        "namespace Problems.p\n"
        "theorem helper (n : Nat) : True := by sorry\n"
        "end Problems.p\n"
    )
    merged, line_map = lsp_gateway._inline_sibling_stubs(
        content, [sibling], ["import Mathlib", "import Problems.p.Defs"])
    lines = merged.split("\n")
    # imports hoisted + deduped (Mathlib + Defs once, extra once)
    assert [ln for ln in lines if ln.startswith("import ")] == [
        "import Mathlib", "import Problems.p.Defs", "import Problems.p.extra"]
    # no import line appears after the first non-import content line
    first_body = next(i for i, ln in enumerate(lines)
                      if ln and not ln.startswith("import "))
    assert all(not ln.startswith("import ") for ln in lines[first_body:])
    # sibling decl precedes the content's main theorem (forward ref ok)
    assert merged.index("theorem helper") < merged.index("theorem s1")
    # line_map sends the content-body lines back to their originals
    s1_idx = next(i for i, ln in enumerate(lines)
                  if ln.startswith("theorem s1"))
    assert line_map[s1_idx] == 5
    have_idx = next(i for i, ln in enumerate(lines)
                    if "have h := helper" in ln)
    assert line_map[have_idx] == 6
    # agent-written imports keep their origin (content lines 1-2); the
    # sibling's own import is framework-region (None)
    assert line_map[0] == 1 and line_map[1] == 2
    extra_idx = next(i for i, ln in enumerate(lines)
                     if ln == "import Problems.p.extra")
    assert line_map[extra_idx] is None
    helper_idx = next(i for i, ln in enumerate(lines)
                      if ln.startswith("theorem helper"))
    assert line_map[helper_idx] is None
    # sibling block is wrapped in an anonymous section (open/variable
    # scoping mirror of its future module boundary)
    sec_idx = next(i for i, ln in enumerate(lines) if ln == "section")
    end_idx = next(i for i, ln in enumerate(lines) if ln == "end")
    assert sec_idx < helper_idx < end_idx
    s1_body = next(i for i, ln in enumerate(lines)
                   if ln.startswith("theorem s1"))
    assert end_idx < s1_body


def test_collect_sibling_stubs_referenced_not_declared(
    tmp_path: Path,
) -> None:
    """Only stubs the content REFERENCES but does not DECLARE are
    collected; an unreferenced stub is skipped."""
    (tmp_path / "new_helper.lean").write_text(
        "namespace Problems.p\ntheorem helper : True := by sorry\n"
        "end Problems.p\n", encoding="utf-8")
    (tmp_path / "new_unused.lean").write_text(
        "namespace Problems.p\ntheorem unused : True := by sorry\n"
        "end Problems.p\n", encoding="utf-8")
    content = ("namespace Problems.p\n"
               "theorem s1 : True := by have h := helper; trivial\n"
               "end Problems.p\n")
    got = lsp_gateway._collect_referenced_sibling_stubs(tmp_path, content)
    assert [slug for slug, _ in got] == ["helper"]


def test_collect_sibling_stubs_skips_self_declared(
    tmp_path: Path,
) -> None:
    """Validating the stub itself: content DECLARES `helper`, so it must
    not be inlined onto itself (would duplicate the declaration)."""
    (tmp_path / "new_helper.lean").write_text(
        "theorem helper : True := by sorry\n", encoding="utf-8")
    content = ("namespace Problems.p\n"
               "theorem helper : True := by sorry\nend Problems.p\n")
    got = lsp_gateway._collect_referenced_sibling_stubs(tmp_path, content)
    assert got == []


def test_remap_inlined_diags_maps_and_filters() -> None:
    """Patch-region diagnostics remap to original content lines; sibling-
    region warnings (sorry noise) drop; sibling-region errors are tagged
    and kept."""
    # lines 1-3 = import/sibling region (None); 4→10, 5→11
    line_map = [None, None, None, 10, 11]
    formatted = [
        {"line": 4, "col": 0, "severity": "error", "message": "patch err"},
        {"line": 2, "col": 0, "severity": "warning",
         "message": "declaration uses 'sorry'"},
        {"line": 1, "col": 0, "severity": "error",
         "message": "sibling broke"},
    ]
    out = lsp_gateway._remap_inlined_diags(formatted, line_map)
    assert {"line": 10, "col": 0, "severity": "error",
            "message": "patch err"} in out
    # sibling-region sorry warning dropped
    assert all("sorry" not in f["message"] for f in out)
    # sibling-region error tagged + kept
    tagged = [f for f in out if "[inlined sibling stub]" in f["message"]]
    assert len(tagged) == 1 and "sibling broke" in tagged[0]["message"]
    assert len(out) == 2


def test_inline_sibling_stubs_emits_opens() -> None:
    """`opens` are emitted between the hoisted imports and the bodies (so
    they precede every `namespace`), one `open X` per entry, all mapped to
    None as framework prefix; content body still maps to its origin."""
    content = (
        "import Mathlib\n"             # line 1
        "namespace Problems.p\n"      # line 2
        "theorem s1 : True := by trivial\n"  # line 3
        "end Problems.p\n"            # line 4
    )
    merged, line_map = lsp_gateway._inline_sibling_stubs(
        content, [], ["import Mathlib"],
        opens=["MeasureTheory", "scoped ContDiff"])
    lines = merged.split("\n")
    open_idxs = [i for i, ln in enumerate(lines) if ln.startswith("open ")]
    assert [lines[i] for i in open_idxs] == [
        "open MeasureTheory", "open scoped ContDiff"]
    # opens sit after the last import and before the first namespace
    last_import = max(i for i, ln in enumerate(lines)
                      if ln.startswith("import "))
    first_ns = next(i for i, ln in enumerate(lines)
                    if ln.startswith("namespace "))
    assert last_import < min(open_idxs) and max(open_idxs) < first_ns
    # opens are framework prefix → None; content theorem maps home (line 3)
    assert all(line_map[i] is None for i in open_idxs)
    s1_idx = next(i for i, ln in enumerate(lines)
                  if ln.startswith("theorem s1"))
    assert line_map[s1_idx] == 3


def test_inline_sibling_stubs_sections_fence_sibling_opens() -> None:
    """A sibling stub's file-scope `open` stays inside its section fence:
    at commit the stub is its own module and `import` does not propagate
    opens, so letting them reach `content` in the single unit was a
    false-green (content leaning on a sibling's `open` validated green,
    then died at the post-commit lake build)."""
    content = ("theorem s1 : True := by have h := helper; trivial\n")
    sib_a = ("import Mathlib\n"
             "open CategoryTheory\n"
             "theorem helper : True := by sorry\n")
    sib_b = ("theorem other : True := by sorry\n")
    merged, line_map = lsp_gateway._inline_sibling_stubs(
        content, [sib_a, sib_b], ["import Mathlib"])
    lines = merged.split("\n")
    open_idx = next(i for i, ln in enumerate(lines)
                    if ln == "open CategoryTheory")
    # the open sits strictly inside sib_a's section … end fence
    sec_before = max(i for i in range(open_idx) if lines[i] == "section")
    end_after = next(i for i in range(open_idx, len(lines))
                     if lines[i] == "end")
    assert sec_before < open_idx < end_after
    # sib_b and the content body both start after that fence closes
    other_idx = next(i for i, ln in enumerate(lines)
                     if ln.startswith("theorem other"))
    s1_idx = next(i for i, ln in enumerate(lines)
                  if ln.startswith("theorem s1"))
    assert end_after < other_idx < s1_idx
    # every sibling-region line (sections included) maps to None
    assert all(line_map[i] is None for i in range(sec_before, end_after + 1))
    assert line_map[s1_idx] == 1


def test_commit_header_for_mirrors_commit_injections(tmp_path: Path) -> None:
    """`commit_header` = exactly what assemble_for_commit + the batch-edge
    injection will add to THIS content at commit: missing framework
    imports, intra-batch sub-goal imports (referenced, not self-declared,
    comment-stripped), and Defs + carried opens not already in content."""
    prob = "p"
    pdir = db.problem_dir(tmp_path, prob)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Defs.lean").write_text(
        "import Mathlib\nopen MeasureTheory\n", encoding="utf-8")
    attempts = tmp_path / "att"
    attempts.mkdir()
    (attempts / "new_helper.lean").write_text(
        "theorem helper : True := by sorry\n", encoding="utf-8")
    (attempts / "new_ghost.lean").write_text(
        "theorem ghost : True := by sorry\n", encoding="utf-8")
    content = ("theorem s1 : True := by\n"
               "  -- ghost only in this comment\n"
               "  have h := helper\n"
               "  trivial\n")
    hdr = lsp_gateway._commit_header_for(
        content, prob, tmp_path, attempts, extra_opens=["open Real"])
    # framework imports (both missing) + the referenced batch edge only:
    # `ghost` appears in a comment alone — commit's scan strips comments
    assert hdr["imports"] == [
        "import Mathlib", "import Problems.p.Defs",
        "import Problems.p.proofs.L_helper"]
    assert hdr["opens"] == ["open MeasureTheory", "open Real"]
    # validating the stub ITSELF never predicts a self-import
    hdr_self = lsp_gateway._commit_header_for(
        "theorem helper : True := by sorry\n", prob, tmp_path, attempts)
    assert "import Problems.p.proofs.L_helper" not in hdr_self["imports"]


def test_stub_fingerprint_and_resync_invalidation(tmp_path: Path) -> None:
    """agent_feedback #4a (2026-07-11): a `new_*.lean` written after the
    last elaboration must invalidate slot ownership — pre-fix errors_at /
    goal_at kept the previous merged unit and reported phantom unknown
    identifiers on citations that validate_file (which rebuilds the unit
    each call) accepted."""
    att = tmp_path / "att"
    att.mkdir()
    target = att / "patch.lean"
    target.write_text("theorem t : True := trivial\n", encoding="utf-8")
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-1", target_path=target, problem="p",
        workspace=tmp_path, file_content=target.read_text(encoding="utf-8"))

    class _Slot:
        claimed_by = "pipe-1"
        content_pipeline_id = "pipe-1"
    slot = _Slot()
    old_workers = lsp_gateway._state.workers
    lsp_gateway._state.workers = [slot]
    try:
        lsp_gateway._resync_buffer_from_disk(meta)  # seeds fingerprint
        slot.content_pipeline_id = "pipe-1"
        lsp_gateway._resync_buffer_from_disk(meta)  # no change → kept
        assert slot.content_pipeline_id == "pipe-1"
        (att / "new_helper.lean").write_text(
            "theorem helper : True := by sorry\n", encoding="utf-8")
        lsp_gateway._resync_buffer_from_disk(meta)  # new stub → invalidated
        assert slot.content_pipeline_id is None
        assert meta.stub_fingerprint and meta.stub_fingerprint[0][0] == (
            "new_helper.lean")
    finally:
        lsp_gateway._state.workers = old_workers


def test_slug_collision_submission_flags_existing_goal(
        tmp_path: Path) -> None:
    """agent_feedback #4b (2026-07-11): a batch stub whose slug already
    names a goal gets a pre-commit warning (commit would auto-suffix
    `_2` or reject as circular) instead of all-green LSP + a bounce."""
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'm', ?)", (db.now(),))
    db.insert_goal(conn, problem="p", slug="taken",
                   lean_path="Problems/p/proofs/L_taken.lean",
                   statement="T", origin="backward")
    conn.commit()
    conn.close()

    sc = lsp_gateway._slug_collision_submission(
        {"taken", "fresh"}, "p", tmp_path)
    assert sc is not None and sc["ok"] is False
    assert [i["slug"] for i in sc["issues"]] == ["taken"]
    assert "auto-suffixes" in sc["issues"][0]["hint"]
    # no collisions → checked+ok; empty stub set → None (nothing to say)
    ok = lsp_gateway._slug_collision_submission({"fresh"}, "p", tmp_path)
    assert ok == {"checked": True, "ok": True}
    assert lsp_gateway._slug_collision_submission(set(), "p", tmp_path) is None


def test_toposort_siblings_orders_referenced_first() -> None:
    """A stub whose body references another stub's slug is emitted AFTER
    it (decl-before-use), regardless of input/glob order; a reference cycle
    drops nobody."""
    a = "namespace P\ntheorem a_lemma : True := by sorry\nend P\n"
    b = ("namespace P\ntheorem b_lemma : True := by\n"
         "  have := a_lemma\n  trivial\nend P\n")
    # feed reversed (b before a) to prove ordering is by reference, not input
    ordered = lsp_gateway._toposort_siblings(
        [("b_lemma", b), ("a_lemma", a)])
    assert [s for s, _ in ordered] == ["a_lemma", "b_lemma"]
    # mutual reference (cycle): both retained, neither dropped
    x = "theorem x_l : True := by have := y_l\n"
    y = "theorem y_l : True := by have := x_l\n"
    cyc = lsp_gateway._toposort_siblings([("x_l", x), ("y_l", y)])
    assert {s for s, _ in cyc} == {"x_l", "y_l"}


def test_build_compilation_unit_injects_defs_opens_and_orders(
    tmp_path: Path,
) -> None:
    """End-to-end: the single compilation unit carries Defs.lean's opens,
    inlines referenced siblings ahead of content, and returns a line_map
    that sends content-body lines home plus the inlined slug list."""
    prob = "p"
    pdir = db.problem_dir(tmp_path, prob)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Defs.lean").write_text(
        "import Mathlib\nopen MeasureTheory\n", encoding="utf-8")
    attempts = tmp_path / "att"
    attempts.mkdir()
    (attempts / "new_helper.lean").write_text(
        "namespace P\ntheorem helper : True := by sorry\nend P\n",
        encoding="utf-8")
    content = ("namespace P\n"                                    # line 1
               "theorem s1 : True := by have h := helper; trivial\n"  # line 2
               "end P\n")                                         # line 3
    merged, line_map, slugs = lsp_gateway._build_compilation_unit(
        content, prob, tmp_path, attempts)
    assert slugs == ["helper"]
    assert "open MeasureTheory" in merged
    assert merged.index("theorem helper") < merged.index("theorem s1")
    lines = merged.split("\n")
    s1_idx = next(i for i, ln in enumerate(lines)
                  if ln.startswith("theorem s1"))
    assert line_map[s1_idx] == 2


def test_merged_line_for_inverts_line_map() -> None:
    """Forward map (content line → merged line) is the inverse of line_map;
    unmapped content lines fall back to themselves; a None map is identity."""
    # merged lines 1-3 = framework prefix (None); 4→content 10, 5→content 11
    line_map = [None, None, None, 10, 11]
    assert lsp_gateway._merged_line_for(line_map, 10) == 4
    assert lsp_gateway._merged_line_for(line_map, 11) == 5
    assert lsp_gateway._merged_line_for(line_map, 99) == 99  # not mapped
    assert lsp_gateway._merged_line_for(None, 7) == 7         # no map


def test_acquire_slot_first_tool_call_cold_warmup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """First tool call after register_session: slot is claimed but its
    content_pipeline_id doesn't match yet (still in warmup state or
    holds a prior claim's stale content). Acquire didChanges this
    pipeline's content in and returns 'cold_warmup'."""
    slots = [_make_fake_slot(0),
             _make_fake_slot(1, claimed_by="pipe-NEW",
                             content_pipeline_id=None, last_used=10.0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, p, c, v): self.calls.append(("didChange", v))
        def clear_diagnostics(self, *a): self.calls.append("clear")
        def wait_for_diagnostics(self, *a, **kw): pass
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-NEW", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="hello",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=True) as (s, kind):
        assert s.slot_id == 1               # the claimed slot
        assert s.content_pipeline_id == "pipe-NEW"  # set after swap
        assert kind == "cold_warmup"
    assert ("didChange", 3) in fake.calls   # version bumped from 2 → 3


def test_acquire_slot_skip_swap_in_for_apply_edit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`swap_in=False` (apply_edit case) skips the didChange-to-mirror
    step; caller will overwrite content via its own RPC. Acquire
    returns 'cold_noswap' without invoking didChange."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id=None, last_used=10.0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, *a, **kw): self.calls.append("didChange")
        def clear_diagnostics(self, *a): self.calls.append("clear")
        def wait_for_diagnostics(self, *a, **kw): pass
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="hello",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=False) as (s, kind):
        assert s.slot_id == 0
        assert kind == "cold_noswap"
    assert "didChange" not in fake.calls
    assert "clear" not in fake.calls


def test_acquire_slot_no_claim_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """If `_acquire_slot` is called for a pipeline that has no
    `register_session`-claimed slot, fail loudly (rather than silently
    seizing some other pipeline's slot)."""
    slots = [_make_fake_slot(0, claimed_by="pipe-OTHER",
                             content_pipeline_id="pipe-OTHER"),
             _make_fake_slot(1, claimed_by=None)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def did_change_full(self, *a, **kw): pass
        def clear_diagnostics(self, *a): pass
        def wait_for_diagnostics(self, *a, **kw): pass
    monkeypatch.setattr(lsp_gateway._state, "backend", _FakeBackend())

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="x",
    )
    with pytest.raises(RuntimeError, match="no slot claimed"):
        with lsp_gateway._acquire_slot(meta, swap_in=False):
            pass


def test_acquire_slot_lock_excludes_concurrent_acquire(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When the pipeline's claimed slot is locked (concurrent tool call
    from the same pipeline), second acquire waits briefly then times
    out. Guards the per-slot mutual-exclusion contract."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A")]
    slots[0].lock.acquire()  # leak — simulates another thread holding
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def did_change_full(self, *a, **kw): pass
        def clear_diagnostics(self, *a): pass
        def wait_for_diagnostics(self, *a, **kw): pass
    monkeypatch.setattr(lsp_gateway._state, "backend", _FakeBackend())

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="x",
    )
    import time as _t
    real_mono = _t.monotonic()
    seq = iter([real_mono, real_mono + 0.05, real_mono + 130.0])
    monkeypatch.setattr(_t, "monotonic", lambda: next(seq))
    with pytest.raises(RuntimeError, match="still busy"):
        with lsp_gateway._acquire_slot(meta, swap_in=False):
            pass
    slots[0].lock.release()


def test_mcp_tools_are_async_for_event_loop_safety() -> None:
    """Regression guard for the miniF2F 20-problem pilot v2 deadlock
    (2026-05-12 02:51): FastMCP's `call_fn_with_arg_validation` calls
    sync tool bodies INLINE on the asyncio event loop (verified by
    reading the SDK source — `return fn(**args)` with no thread
    pool). Tools that block (every one calls `_acquire_slot` which
    can poll up to 120s) saturate the event loop under concurrent
    load, blocking /register / /release / /health and deadlocking
    the daemon.

    Fix: wrap each `@mcp.tool()` with `_offload_to_thread` so the
    handler is async + dispatches sync work to `asyncio.to_thread`.

    This test asserts ALL four MCP tools are coroutine functions
    (i.e. the `_offload_to_thread` wrapper is in place). If a future
    refactor accidentally removes the decorator from a tool, this
    test catches it before it ships."""
    import inspect
    from Tooling.lsp import gateway as gw

    for name in ("apply_edit", "goal_at", "errors_at", "validate_file"):
        fn = getattr(gw, name)
        assert inspect.iscoroutinefunction(fn), (
            f"MCP tool `{name}` must be a coroutine function "
            f"(wrap with `_offload_to_thread`) so its sync body "
            f"doesn't block the asyncio event loop."
        )


def test_verify_endpoint_offloads_sync_body_to_thread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Regression guard for the miniF2F 20-problem pilot deadlock
    (2026-05-12): /verify's sync slot-acquire + LSP RPC work must NOT
    run on the asyncio event loop. If it does, concurrent verify
    requests serialize and starve /register / /release / /health
    handlers (the daemon-side `register_session` urlopen hits its
    120s timeout and the dispatcher worker raises TimeoutError).

    Smoke test: the /verify handler must call asyncio.to_thread on
    `_verify_sync`. We patch `_verify_sync` to a marker function and
    confirm it's invoked off the event loop via `asyncio.to_thread`."""
    import asyncio
    from starlette.requests import Request

    invoked_in_thread: dict[str, object] = {}

    def _stub_verify_sync(target, content, *, write_olean, axioms_for,
                          rpc_timeout, constants_for=None,
                          decl_info=False, decl_info_constants=False):
        # Off-thread invocation: in the main test thread our event loop
        # is running; if to_thread was used we land in a *different*
        # thread.
        import threading
        invoked_in_thread["tid"] = threading.get_ident()
        return {"ok": True, "diagnostic_count": 0, "diagnostics": [],
                "olean_written": False, "olean_path": None,
                "axioms": None, "axiom_error": None}

    monkeypatch.setattr(lsp_gateway, "_verify_sync", _stub_verify_sync)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda **kw: None)

    target = tmp_path / "x.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")

    # Build a minimal ASGI request to feed the async handler
    async def _run():
        scope = {
            "type": "http", "method": "POST", "path": "/verify",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        }
        import json
        body = json.dumps({
            "target_path": str(target),
            "write_olean": False,
        }).encode("utf-8")

        sent = []
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        async def send(msg):
            sent.append(msg)
        # Use Request to feed the handler
        req = Request(scope, receive=receive, send=send)
        resp = await lsp_gateway.verify(req)
        return resp

    asyncio.run(_run())

    assert "tid" in invoked_in_thread, "_verify_sync was not called"
    import threading
    main_tid = threading.get_ident()
    assert invoked_in_thread["tid"] != main_tid, (
        f"_verify_sync ran on the main thread (tid={main_tid}); "
        f"event loop would have been blocked. Expected asyncio.to_thread "
        f"to dispatch to a worker thread."
    )


def test_session_release_clears_slot_claim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Releasing a session clears the `claimed_by` marker on the
    pipeline's claimed slot. `content_pipeline_id` stays in place —
    the next claim will didChange its own content in regardless, so
    eagerly clearing buys nothing."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A"),
             _make_fake_slot(1, claimed_by="pipe-B",
                             content_pipeline_id="pipe-B")]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
    )
    with lsp_gateway._state.sessions_lock:
        lsp_gateway._state.sessions["tok-A"] = meta

    lsp_gateway._release_session_internal("tok-A")

    assert slots[0].claimed_by is None              # released
    assert slots[0].content_pipeline_id == "pipe-A"  # left untouched
    assert slots[1].claimed_by == "pipe-B"          # other slot untouched
    with lsp_gateway._state.sessions_lock:
        assert "tok-A" not in lsp_gateway._state.sessions


def test_register_session_claims_free_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """register_session eagerly claims a free worker slot (1:1 binding).
    The claim is recorded on the first slot whose `claimed_by is None`."""
    target = tmp_path / "x.lean"
    target.write_text("dummy", encoding="utf-8")
    slots = [_make_fake_slot(0, claimed_by="other-pipe"),
             _make_fake_slot(1, claimed_by=None)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda **kw: None)

    token, err = lsp_gateway._register_session_internal(
        pipeline_id="pipe-A", target_path=target,
        problem="p", workspace=tmp_path, log_path=None,
    )
    assert err is None
    assert token
    assert slots[0].claimed_by == "other-pipe"  # unchanged
    assert slots[1].claimed_by == "pipe-A"      # claimed


def _setup_validate_session(monkeypatch, tmp_path, backend):
    """Wire a claimed slot + session + ready backend so `validate_file`
    can run against an in-memory FakeBackend. Returns a reset callback."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A")]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway._state, "backend", backend)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda *a, **kw: None)
    monkeypatch.setattr(lsp_gateway, "_ensure_imports",
                        lambda content, problem, ws: content)
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="pipe-A", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="theorem t : True := trivial\n",
    )
    with lsp_gateway._state.sessions_lock:
        lsp_gateway._state.sessions["tok-A"] = meta
    ctx = lsp_gateway._session_ctx.set("tok-A")
    return ctx


class _DiagBackend:
    """Minimal backend for validate_file: `wait` behavior is injectable;
    `diagnostics_for` returns a fixed list."""
    def __init__(self, *, wait_raises=None, diags=None):
        self._wait_raises = wait_raises
        self._diags = diags or []
    def clear_diagnostics(self, *a, **kw): pass
    def did_change_full(self, *a, **kw): pass
    def wait_for_diagnostics(self, *a, **kw):
        if self._wait_raises is not None:
            raise self._wait_raises
    def diagnostics_for(self, *a, **kw): return list(self._diags)


def test_validate_file_timeout_reports_indeterminate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """#102 — when elaboration doesn't confirm within the wait budget,
    validate_file must NOT report a false ok:true. It reports ok:false +
    timed_out + an error, even though no error diagnostics arrived."""
    backend = _DiagBackend(wait_raises=TimeoutError("budget"))
    ctx = _setup_validate_session(monkeypatch, tmp_path, backend)
    try:
        out = json.loads(asyncio.run(lsp_gateway.validate_file(
            "theorem t : True := by sorry\n")))
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        lsp_gateway._state.sessions.pop("tok-A", None)
    assert out["ok"] is False
    assert out["timed_out"] is True
    assert "error" in out
    assert out["diagnostic_count"] == 0  # no diagnostics, yet not "clean"


def test_validate_file_clean_when_no_diags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Regression guard: the normal path (wait completes, zero error
    diagnostics) still returns ok:true with no timed_out marker."""
    backend = _DiagBackend(wait_raises=None, diags=[])
    ctx = _setup_validate_session(monkeypatch, tmp_path, backend)
    try:
        out = json.loads(asyncio.run(lsp_gateway.validate_file(
            "theorem t : True := trivial\n")))
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        lsp_gateway._state.sessions.pop("tok-A", None)
    assert out["ok"] is True
    assert "timed_out" not in out


def test_verify_sync_unconfirmed_diags_are_transient(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Root-caused 2026-06-29: `/verify` borrows a slot and swaps content
    in, but `diagnostics_for` is versionless and `_acquire_slot`'s swap
    wait is swallowed on a transient (a fresh slot still flushing warmup
    diagnostics; a prior occupant's elaborate in flight). Without a
    confirming re-wait, `_verify_sync` would surface the prior occupant's
    STALE error (e.g. a phantom 'expected token') as a build failure
    against our target. The fix: re-wait at our version; on failure return
    `transient=True` so the caller retries rather than trusting stale
    diagnostics."""
    slots = [_make_fake_slot(0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway._state, "workspace", tmp_path)
    stale = {"severity": 1,
             "range": {"start": {"line": 8, "character": 14}},
             "message": "expected token"}
    backend = _DiagBackend(wait_raises=TimeoutError("warmup in flight"),
                           diags=[stale])
    monkeypatch.setattr(lsp_gateway._state, "backend", backend)

    target = tmp_path / "L_stub.lean"
    target.write_text("import Mathlib\ntheorem t : True := trivial\n",
                      encoding="utf-8")
    out = lsp_gateway._verify_sync(
        target, target.read_text(encoding="utf-8"),
        write_olean=False, axioms_for=None, rpc_timeout=30)
    assert out.get("transient") is True
    assert "error" in out
    # The stale prior-occupant diagnostic must NOT have become the verdict:
    # no ok:false build-failure surfaced from the versionless stale read.
    assert "ok" not in out
    assert "expected token" not in (out.get("error") or "")


def test_verify_sync_confirmed_error_still_surfaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Guard: the fix must NOT mask genuine errors. When the diagnostics
    wait CONFIRMS (no raise), a real error diagnostic is reported as
    ok:false with the diagnostic intact — proving the confirming re-wait
    only catches the unconfirmed case, never a legitimate verdict."""
    slots = [_make_fake_slot(0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway._state, "workspace", tmp_path)
    real = {"severity": 1,
            "range": {"start": {"line": 0, "character": 0}},
            "message": "unknown identifier 'foo'"}
    backend = _DiagBackend(wait_raises=None, diags=[real])
    monkeypatch.setattr(lsp_gateway._state, "backend", backend)

    target = tmp_path / "L_stub.lean"
    target.write_text("import Mathlib\ntheorem t : True := foo\n",
                      encoding="utf-8")
    out = lsp_gateway._verify_sync(
        target, target.read_text(encoding="utf-8"),
        write_olean=False, axioms_for=None, rpc_timeout=30)
    assert out.get("ok") is False
    assert out.get("transient") is not True
    assert any("unknown identifier" in d["message"]
               for d in out.get("diagnostics", []))


class _RpcBackend(_DiagBackend):
    """_DiagBackend + a recording `rpc_call` with per-method canned
    responses (the declInfo/printAxioms RPC surface)."""
    def __init__(self, *, responses=None, **kw):
        super().__init__(**kw)
        self.rpc_calls: list[tuple[str, dict]] = []
        self._responses = responses or {}

    def rpc_call(self, uri, method, params, timeout=None):
        self.rpc_calls.append((method, params))
        resp = self._responses.get(method)
        if isinstance(resp, Exception):
            raise resp
        return resp or {}


def test_verify_sync_decl_info_rpc_surfaces_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`decl_info=True` calls the `Asterism.declInfo` RPC on a clean
    elaborate and surfaces `{commands, decls}` in the response;
    `decl_info=False` (default) never touches the RPC."""
    slots = [_make_fake_slot(0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway._state, "workspace", tmp_path)
    canned = {"ok": True,
              "commands": [{"kind": "Lean.Parser.Command.declaration",
                            "range": {"startLine": 1, "startCol": 0,
                                      "endLine": 1, "endCol": 30}}],
              "decls": [{"fqName": "t", "userName": "t", "kind": "thm",
                         "cmdIdx": 0}]}
    backend = _RpcBackend(responses={"Asterism.declInfo": canned})
    monkeypatch.setattr(lsp_gateway._state, "backend", backend)

    target = tmp_path / "L_stub.lean"
    target.write_text("import Mathlib\ntheorem t : True := trivial\n",
                      encoding="utf-8")
    out = lsp_gateway._verify_sync(
        target, target.read_text(encoding="utf-8"),
        write_olean=False, axioms_for=None, decl_info=True, rpc_timeout=30)
    assert out["ok"] is True
    assert [m for m, _ in backend.rpc_calls] == ["Asterism.declInfo"]
    assert out["decl_info"] == {"commands": canned["commands"],
                                "decls": canned["decls"]}
    assert out["decl_info_error"] is None

    backend.rpc_calls.clear()
    out2 = lsp_gateway._verify_sync(
        target, target.read_text(encoding="utf-8"),
        write_olean=False, axioms_for=None, rpc_timeout=30)
    assert backend.rpc_calls == []
    assert out2["decl_info"] is None


def test_verify_sync_decl_info_rpc_failure_degrades(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A declInfo RPC failure (e.g. stale lean-asterism-server binary
    without the method) degrades to `decl_info_error` — the elaborate
    verdict itself stays intact, mirroring axiom_error semantics."""
    slots = [_make_fake_slot(0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway._state, "workspace", tmp_path)
    backend = _RpcBackend(
        responses={"Asterism.declInfo": RuntimeError("unknown method")})
    monkeypatch.setattr(lsp_gateway._state, "backend", backend)

    target = tmp_path / "L_stub.lean"
    target.write_text("import Mathlib\ntheorem t : True := trivial\n",
                      encoding="utf-8")
    out = lsp_gateway._verify_sync(
        target, target.read_text(encoding="utf-8"),
        write_olean=False, axioms_for=None, decl_info=True, rpc_timeout=30)
    assert out["ok"] is True
    assert out["decl_info"] is None
    assert "declInfo RPC failed" in out["decl_info_error"]


def test_acquire_slot_borrow_mode_uses_any_free_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Probe mode (`borrow=True`) bypasses the claim check — used by the
    /verify endpoint which has no registered session. Grabs any free
    slot (LRU first), didChanges in, clears content_pipeline_id so
    the slot's registered owner reloads on its next acquire."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A",
                             last_used=20.0),
             _make_fake_slot(1, claimed_by=None,
                             content_pipeline_id=None,
                             last_used=10.0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, p, c, v): self.calls.append(("didChange", v))
        def clear_diagnostics(self, *a): self.calls.append("clear")
        def wait_for_diagnostics(self, *a, **kw): pass
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="verify:probe-xyz", target_path=tmp_path / "x.lean",
        problem="", workspace=tmp_path, log_path=None,
        file_content="probe content",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=True, borrow=True) as (s, kind):
        # LRU is slot 1 (last_used=10.0 < 20.0)
        assert s.slot_id == 1
        assert kind == "cold_warmup"
    # After release: content_pipeline_id cleared so the owner (if any)
    # re-loads on next acquire.
    assert slots[1].content_pipeline_id is None
    # Slot 0 (other pipeline's claim) untouched.
    assert slots[0].claimed_by == "pipe-A"
    assert slots[0].content_pipeline_id == "pipe-A"


def test_acquire_slot_borrow_evicts_when_no_unclaimed_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When all slots are claimed by registered sessions, borrow mode
    still proceeds — it locks any unlocked slot, didChanges the probe
    content, then clears `content_pipeline_id` so the claimed owner
    pays one cold_warmup on its next acquire."""
    slots = [_make_fake_slot(0, claimed_by="pipe-A",
                             content_pipeline_id="pipe-A",
                             last_used=20.0)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)

    class _FakeBackend:
        def __init__(self): self.calls = []
        def did_change_full(self, p, c, v): self.calls.append("didChange")
        def clear_diagnostics(self, *a): pass
        def wait_for_diagnostics(self, *a, **kw): pass
    fake = _FakeBackend()
    monkeypatch.setattr(lsp_gateway._state, "backend", fake)

    meta = lsp_gateway.SessionMetadata(
        pipeline_id="verify:probe-xyz", target_path=tmp_path / "x.lean",
        problem="", workspace=tmp_path, log_path=None,
        file_content="probe content",
    )
    with lsp_gateway._acquire_slot(meta, swap_in=True, borrow=True) as (s, kind):
        assert s.slot_id == 0
        assert kind == "cold_warmup"
    # Owner's claim preserved; content_pipeline_id cleared so the next
    # acquire by pipe-A re-loads pipe-A's content (one cold_warmup).
    assert slots[0].claimed_by == "pipe-A"
    assert slots[0].content_pipeline_id is None


def test_register_session_fails_when_pool_exhausted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """If every worker slot is already claimed (dispatch.pool >
    workers count — a configuration error), register_session refuses
    instead of silently sharing a slot."""
    target = tmp_path / "x.lean"
    target.write_text("dummy", encoding="utf-8")
    slots = [_make_fake_slot(0, claimed_by="pipe-X"),
             _make_fake_slot(1, claimed_by="pipe-Y")]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda **kw: None)

    token, err = lsp_gateway._register_session_internal(
        pipeline_id="pipe-Z", target_path=target,
        problem="p", workspace=tmp_path, log_path=None,
    )
    assert token == ""
    assert err is not None
    assert "pool exhausted" in err


# ---------------------------------------------------------------------
# Stale-claim sweep (#118 follow-up — gateway activity-TTL leak fix)
# ---------------------------------------------------------------------

def _build_fake_pool(monkeypatch: pytest.MonkeyPatch,
                     tmp_path: Path, n: int = 2) -> list:
    """Stub out _state.workers with `n` fresh WorkerSlot rows. Yields
    the slots for inspection. Cleans sessions on exit (per-test)."""
    from Tooling.lsp.gateway import WorkerSlot
    slots = [WorkerSlot(slot_id=i,
                        slot_path=tmp_path / f"slot_{i}.lean",
                        slot_uri=f"file:///slot_{i}",
                        file_version=0)
             for i in range(n)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    return slots


def _make_meta(tmp_path: Path, *, pipeline_id: str,
               last_active: float) -> SessionMetadata:
    return SessionMetadata(
        pipeline_id=pipeline_id,
        target_path=tmp_path / f"{pipeline_id}.lean",
        problem="p", workspace=tmp_path, log_path=None,
        file_content="", last_active=last_active,
    )


def test_sweep_reclaims_session_inactive_beyond_ttl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Session whose `last_active` is older than `_LEASE_TTL_SEC`
    must be popped + its claimed slot freed."""
    import time as _t
    slots = _build_fake_pool(monkeypatch, tmp_path, n=2)
    now = _t.monotonic()
    stale = _make_meta(tmp_path, pipeline_id="pipe-stale",
                       last_active=now - lsp_gateway._LEASE_TTL_SEC - 1.0)
    slots[0].claimed_by = "pipe-stale"
    with _state.sessions_lock:
        _state.sessions["stale-tok"] = stale
    try:
        n = lsp_gateway._sweep_stale_claims()
        assert n == 1
        assert "stale-tok" not in _state.sessions
        assert slots[0].claimed_by is None
    finally:
        with _state.sessions_lock:
            _state.sessions.pop("stale-tok", None)


def test_sweep_preserves_fresh_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Session with `last_active` newer than TTL stays put."""
    import time as _t
    slots = _build_fake_pool(monkeypatch, tmp_path, n=2)
    now = _t.monotonic()
    fresh = _make_meta(tmp_path, pipeline_id="pipe-fresh",
                       last_active=now - 1.0)
    slots[0].claimed_by = "pipe-fresh"
    with _state.sessions_lock:
        _state.sessions["fresh-tok"] = fresh
    try:
        n = lsp_gateway._sweep_stale_claims()
        assert n == 0
        assert "fresh-tok" in _state.sessions
        assert slots[0].claimed_by == "pipe-fresh"
    finally:
        with _state.sessions_lock:
            _state.sessions.pop("fresh-tok", None)
        slots[0].claimed_by = None


def test_sweep_handles_mixed_stale_and_fresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Real-world steady-state: some slots are active mid-spawn, some
    are leaks from prior crashes. Sweep reclaims only the stale ones."""
    import time as _t
    slots = _build_fake_pool(monkeypatch, tmp_path, n=4)
    now = _t.monotonic()
    fresh = _make_meta(tmp_path, pipeline_id="pipe-fresh",
                       last_active=now - 5.0)
    stale1 = _make_meta(tmp_path, pipeline_id="pipe-stale1",
                        last_active=now - lsp_gateway._LEASE_TTL_SEC - 10)
    stale2 = _make_meta(tmp_path, pipeline_id="pipe-stale2",
                        last_active=now - lsp_gateway._LEASE_TTL_SEC - 999)
    slots[0].claimed_by = "pipe-fresh"
    slots[1].claimed_by = "pipe-stale1"
    slots[2].claimed_by = "pipe-stale2"
    # slots[3] genuinely free
    with _state.sessions_lock:
        _state.sessions.update({
            "fresh-tok": fresh, "stale1-tok": stale1, "stale2-tok": stale2,
        })
    try:
        n = lsp_gateway._sweep_stale_claims()
        assert n == 2
        assert "fresh-tok" in _state.sessions
        assert "stale1-tok" not in _state.sessions
        assert "stale2-tok" not in _state.sessions
        # Fresh slot untouched; stale slots freed.
        assert slots[0].claimed_by == "pipe-fresh"
        assert slots[1].claimed_by is None
        assert slots[2].claimed_by is None
        assert slots[3].claimed_by is None
    finally:
        with _state.sessions_lock:
            for t in ("fresh-tok", "stale1-tok", "stale2-tok"):
                _state.sessions.pop(t, None)
        for s in slots:
            s.claimed_by = None


def test_sweep_no_op_on_empty_session_map(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Steady-state hot path: no sessions → no work, no errors."""
    _build_fake_pool(monkeypatch, tmp_path, n=4)
    assert lsp_gateway._sweep_stale_claims() == 0


def test_sweep_orphan_session_without_matching_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Defensive: session in `sessions` whose pipeline_id matches no
    slot (e.g. mid-state corruption) still gets popped — sweep doesn't
    require slot match to drop the session entry."""
    import time as _t
    slots = _build_fake_pool(monkeypatch, tmp_path, n=2)
    now = _t.monotonic()
    orphan = _make_meta(tmp_path, pipeline_id="pipe-orphan",
                        last_active=now - lsp_gateway._LEASE_TTL_SEC - 1)
    # No slot has claimed_by="pipe-orphan"
    with _state.sessions_lock:
        _state.sessions["orphan-tok"] = orphan
    try:
        n = lsp_gateway._sweep_stale_claims()
        assert n == 1
        assert "orphan-tok" not in _state.sessions
        # Slots untouched (none matched).
        assert all(s.claimed_by is None for s in slots)
    finally:
        with _state.sessions_lock:
            _state.sessions.pop("orphan-tok", None)


# ─── 2026-07-07 warm-race fix: starting marker + wait-not-race ───

def test_wait_for_starting_gateway_reaps_dead_warmer(tmp_path) -> None:
    """A marker whose pid is dead is residue from a crashed warm — it
    must be cleaned and the caller told to spawn fresh (None)."""
    from Tooling.lsp import lifecycle as lc
    m = lc.gateway_starting_marker(tmp_path)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text("999999999", encoding="utf-8")
    assert lc._wait_for_starting_gateway(tmp_path, budget=5.0) is None
    assert not m.exists()


def test_wait_for_starting_gateway_waits_on_live_warmer(
        tmp_path, monkeypatch) -> None:
    """A live pid mid-warm means WAIT (never spawn a rival that loses
    the port-bind race after its own multi-minute warm); past the
    budget it fails loudly with the pid on record."""
    import os as _os

    import pytest as _pytest

    from Tooling.lsp import lifecycle as lc
    monkeypatch.setattr(lc, "_ping_health", lambda timeout=1.0: None)
    m = lc.gateway_starting_marker(tmp_path)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(str(_os.getpid()), encoding="utf-8")
    with _pytest.raises(RuntimeError, match="still warming"):
        lc._wait_for_starting_gateway(tmp_path, budget=0.1)


def test_gateway_phase_reads_marker(tmp_path, monkeypatch) -> None:
    import os as _os

    from Tooling.lsp import lifecycle as lc
    monkeypatch.setattr(lc, "_ping_health", lambda timeout=0.5: None)
    assert lc.gateway_phase(tmp_path) is None
    m = lc.gateway_starting_marker(tmp_path)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(str(_os.getpid()), encoding="utf-8")
    assert lc.gateway_phase(tmp_path) == "warming"
    monkeypatch.setattr(
        lc, "_ping_health", lambda timeout=0.5: {"backend_ready": True})
    assert lc.gateway_phase(tmp_path) == "ready"


# ─── 2026-06-12 gateway-hang fix: tree-kill + wedge restart ───

def test_client_busy_uris_filters_in_flight() -> None:
    """`busy_uris` reports only URIs whose elaborate is in-flight
    (non-empty fileProgress) — the wedge-watchdog's input signal."""
    import threading
    from Tooling.lsp.client import LspClient
    c = LspClient.__new__(LspClient)  # skip __init__'s subprocess setup
    c._file_progress = {"done": [], "busy1": ["x"], "busy2": ["y", "z"]}
    c._file_progress_lock = threading.Lock()
    assert c.busy_uris() == {"busy1", "busy2"}


def test_client_shutdown_tree_kills_when_proc_wont_exit(monkeypatch) -> None:
    """A backend that ignores graceful shutdown/exit must be tree-killed
    (reaping `lean --server`/`--worker` children) — not left to orphan a
    runaway elaborate (the 2026-06-12 hang root cause)."""
    import subprocess
    import threading
    from Tooling.lsp.client import LspClient
    c = LspClient.__new__(LspClient)
    c._send_lock = threading.Lock()
    c._stopped = threading.Event()
    killed = {"tree": False}

    class _StuckProc:
        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd="lake serve", timeout=timeout)
    c.proc = _StuckProc()
    monkeypatch.setattr(c, "notify", lambda *a, **k: None)
    monkeypatch.setattr(c, "_kill_tree",
                        lambda: killed.__setitem__("tree", True))
    c.shutdown(timeout=0.01)
    assert killed["tree"]


def test_restart_backend_reaps_old_then_rewarms(monkeypatch) -> None:
    """`_restart_backend` shuts the wedged backend down (tree-reaped) then
    re-warms a fresh pool of the same width."""
    order: list[str] = []

    class _FakeBackend:
        def shutdown(self) -> None:
            order.append("shutdown")

    saved = (_state.backend, _state.workspace, list(_state.workers))
    try:
        _state.backend = _FakeBackend()
        _state.workspace = Path(".")
        _state.workers = [object(), object(), object()]  # width 3
        monkeypatch.setattr(lsp_gateway, "_start_workers",
                            lambda ws, n, n_res=0: order.append(f"start:{n}"))
        lsp_gateway._restart_backend("unit test")
        assert order == ["shutdown", "start:3"], order
    finally:
        _state.backend, _state.workspace, _state.workers = (
            saved[0], saved[1], saved[2])


# ---------------------------------------------------------------------
# /verify_session — verify a candidate on the session's OWN claimed slot
# (claimed mode, no borrow eviction). The warm-slot path for framework gates
# that hold a session (Library cleanup mechanical gates).
# ---------------------------------------------------------------------

class _CannedDiagBackend:
    """Fake backend returning canned LSP diagnostics for any slot URI."""

    def __init__(self, canned):
        self._canned = canned

    def clear_diagnostics(self, *a):
        pass

    def did_change_full(self, *a, **kw):
        pass

    def wait_for_diagnostics(self, *a, **kw):
        pass

    def diagnostics_for(self, uri):
        return list(self._canned)


def _register_fake_session(monkeypatch, tmp_path, *, pipeline_id, token,
                           content_pipeline_id=None):
    """Claim a slot for `pipeline_id` and stash a session under `token`."""
    slot = _make_fake_slot(1, claimed_by=pipeline_id,
                           content_pipeline_id=content_pipeline_id)
    monkeypatch.setattr(lsp_gateway._state, "workers", [slot])
    meta = lsp_gateway.SessionMetadata(
        pipeline_id=pipeline_id, target_path=tmp_path / "F.lean",
        problem="p", workspace=tmp_path, log_path=None, file_content="orig")
    with lsp_gateway._state.sessions_lock:
        lsp_gateway._state.sessions[token] = meta
    return slot


def test_verify_session_sync_unknown_token() -> None:
    """An unregistered token → 404 error verdict (no slot work)."""
    saved = lsp_gateway._state.backend
    lsp_gateway._state.backend = object()  # non-None so we pass the ready check
    try:
        with lsp_gateway._state.sessions_lock:
            lsp_gateway._state.sessions.pop("no-such-token", None)
        r = lsp_gateway._verify_session_sync(
            "no-such-token", "theorem t : True := trivial\n",
            write_olean=False, axioms_for=None, rpc_timeout=30, wait_timeout=60)
    finally:
        lsp_gateway._state.backend = saved
    assert r.get("_status") == 404
    assert "unknown session" in r["error"]


def test_verify_session_sync_warning_only_is_ok(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Verify on the CLAIMED slot: a warning-only candidate is `ok` (warnings
    don't fail elaboration), diagnostics are severity-mapped, and the probe
    clears content_pipeline_id so the session reloads its own content next."""
    canned = [{"range": {"start": {"line": 4, "character": 2}}, "severity": 2,
               "message": "unused variable `h`"}]
    monkeypatch.setattr(lsp_gateway._state, "backend",
                        _CannedDiagBackend(canned))
    slot = _register_fake_session(monkeypatch, tmp_path,
                                  pipeline_id="pipe-A", token="tok-A",
                                  content_pipeline_id="pipe-A")
    try:
        r = lsp_gateway._verify_session_sync(
            "tok-A", "theorem t : True := trivial\n",
            write_olean=False, axioms_for=None, rpc_timeout=30, wait_timeout=60)
    finally:
        with lsp_gateway._state.sessions_lock:
            lsp_gateway._state.sessions.pop("tok-A", None)
    assert r["ok"] is True
    assert r["diagnostic_count"] == 1
    assert r["diagnostics"][0]["severity"] == "warning"
    assert r["timed_out"] is False
    assert slot.content_pipeline_id is None  # probe cleared the slot ownership


def test_verify_session_sync_error_diag_not_ok(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """An error-severity diagnostic → ok False."""
    canned = [{"range": {"start": {"line": 0, "character": 0}}, "severity": 1,
               "message": "type mismatch"}]
    monkeypatch.setattr(lsp_gateway._state, "backend",
                        _CannedDiagBackend(canned))
    _register_fake_session(monkeypatch, tmp_path,
                           pipeline_id="pipe-B", token="tok-B",
                           content_pipeline_id="pipe-B")
    try:
        r = lsp_gateway._verify_session_sync(
            "tok-B", "bad\n", write_olean=False, axioms_for=None,
            rpc_timeout=30, wait_timeout=60)
    finally:
        with lsp_gateway._state.sessions_lock:
            lsp_gateway._state.sessions.pop("tok-B", None)
    assert r["ok"] is False
    assert r["diagnostics"][0]["severity"] == "error"


def test_build_compilation_unit_hoists_proved_sibling_imports(
    tmp_path: Path,
) -> None:
    """Task #5 Step C: the unit is derived from the same assemble primitives
    commit runs — a reference to a PROVED sibling the agent forgot to import
    gets the SAME auto-import commit will inject, hoisted into the import
    block (line_map untouched), so validate stops false-REDing what commit
    auto-fixes."""
    import sqlite3
    prob = "p"
    pdir = db.problem_dir(tmp_path, prob)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Defs.lean").write_text("import Mathlib\n", encoding="utf-8")
    attempts = tmp_path / "att"
    attempts.mkdir()
    # a proved sibling in the workspace DB
    conn = sqlite3.connect(tmp_path / "asterism.db")
    conn.row_factory = sqlite3.Row
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, manifest_path, created_at) "
                 "VALUES ('p','',datetime('now'))")
    g = db.insert_goal(conn, problem=prob, slug="helper_lemma",
                       lean_path="Problems/p/proofs/L_helper_lemma.lean",
                       statement="True", origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    conn.close()
    content = ("namespace P\n"                                      # line 1
               "theorem s1 : True := helper_lemma trivial\n"        # line 2
               "end P\n")                                           # line 3
    merged, line_map, slugs = lsp_gateway._build_compilation_unit(
        content, prob, tmp_path, attempts)
    assert "import Problems.p.proofs.L_helper_lemma" in merged
    lines = merged.split("\n")
    imp_idx = next(i for i, ln in enumerate(lines)
                   if "L_helper_lemma" in ln)
    assert line_map[imp_idx] is None          # hoisted prefix, not content
    s1_idx = next(i for i, ln in enumerate(lines)
                  if ln.startswith("theorem s1"))
    assert line_map[s1_idx] == 2              # agent's line numbers intact


def test_build_compilation_unit_no_db_is_noop(tmp_path: Path) -> None:
    """No asterism.db in the workspace (pure unit-test setups) → the
    proved-sibling lookup silently contributes nothing."""
    prob = "p"
    pdir = db.problem_dir(tmp_path, prob)
    pdir.mkdir(parents=True, exist_ok=True)
    attempts = tmp_path / "att"
    attempts.mkdir()
    merged, _, _ = lsp_gateway._build_compilation_unit(
        "theorem t : True := trivial\n", prob, tmp_path, attempts)
    assert "proofs.L_" not in merged


# ---------------------------------------------------------------------
# Interactive reserved slot (serve UI editor) — pipeline=slot identity
# holds in BOTH directions
# ---------------------------------------------------------------------

def _make_reserved_slot(slot_id: int, *, claimed_by: "str | None" = None):
    s = _make_fake_slot(slot_id, claimed_by=claimed_by)
    s.reserved = True
    return s


def test_pipeline_claim_never_takes_reserved_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A free RESERVED slot is invisible to pipeline registration: with
    every unreserved slot claimed, the pool reports exhausted rather
    than invading the editor's slot."""
    target = tmp_path / "x.lean"
    target.write_text("dummy", encoding="utf-8")
    slots = [_make_fake_slot(0, claimed_by="other"),
             _make_reserved_slot(1)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda **kw: None)
    token, err = lsp_gateway._register_session_internal(
        pipeline_id="pipe-A", target_path=target,
        problem="p", workspace=tmp_path, log_path=None,
    )
    assert token == "" and err is not None
    assert "pool exhausted" in err
    assert slots[1].claimed_by is None  # reserved slot untouched


def test_interactive_claim_takes_only_reserved_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Interactive registration claims the reserved slot and never a
    pipeline slot; a second interactive session reports busy."""
    target = tmp_path / "scratch.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")
    slots = [_make_fake_slot(0),            # free pipeline slot
             _make_reserved_slot(1)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda **kw: None)
    token, err = lsp_gateway._register_session_internal(
        pipeline_id="interactive-a", target_path=target,
        problem="", workspace=tmp_path, log_path=None,
        kind="interactive", interactive=True,
    )
    assert err is None and token
    assert slots[0].claimed_by is None       # pipeline slot untouched
    assert slots[1].claimed_by == "interactive-a"
    token2, err2 = lsp_gateway._register_session_internal(
        pipeline_id="interactive-b", target_path=target,
        problem="", workspace=tmp_path, log_path=None,
        kind="interactive", interactive=True,
    )
    assert token2 == "" and "interactive slot busy" in (err2 or "")
    lsp_gateway._release_session_internal(token)
    assert slots[1].claimed_by is None


def test_borrow_order_excludes_reserved() -> None:
    """/verify probe borrows never see the reserved slot, claimed or
    not — the editor's warm buffer is not evictable by one-shots."""
    slots = [_make_reserved_slot(0),
             _make_fake_slot(1, last_used=5.0),
             _make_fake_slot(2, claimed_by="p", last_used=1.0)]
    order = lsp_gateway._borrow_order(slots)
    assert [s.slot_id for s in order] == [1, 2]


def test_compilation_for_interactive_is_identity(tmp_path: Path) -> None:
    """An interactive session's buffer IS the compilation unit — no
    framework merge, identity line_map."""
    meta = lsp_gateway.SessionMetadata(
        pipeline_id="interactive-x", target_path=tmp_path / "s.lean",
        problem="", workspace=tmp_path, kind="interactive",
        file_content="import Mathlib\n#check 1",
    )
    merged, line_map = lsp_gateway._compilation_for(meta)
    assert merged == meta.file_content
    assert line_map == [1, 2]


def test_goal_present_closed_state_is_not_a_goal() -> None:
    """Lean's rendered "no goals" is the CLOSED state — treating that
    truthy string as a live goal silently disabled the B#4
    sorry-fallback (a sorry-line query answered 'no goals' instead of
    re-querying the token start)."""
    gp = lsp_gateway._goal_present
    assert gp({"goals": ["⊢ True"]}) is True
    assert gp({"rendered": "```lean\nn : ℕ\n⊢ 2 * n = n + n\n```"}) is True
    assert gp({"rendered": "no goals", "goals": []}) is False
    assert gp({"rendered": "", "goals": []}) is False
    assert gp(None) is False
    # None position (outside any proof) summarizes readably, not "None"
    assert lsp_gateway._summarize_goal(None) == "no goals"


def test_interactive_reclaim_evicts_stale_interactive_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Last editor wins: a new interactive registration evicts a prior
    interactive claim (orphaned by a hard-killed serve, or an older
    tab) — releasing the reserved slot — while pipeline claims are
    untouchable by construction."""
    target = tmp_path / "scratch.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")
    slots = [_make_fake_slot(0, claimed_by="pipe-A"),
             _make_reserved_slot(1)]
    monkeypatch.setattr(lsp_gateway._state, "workers", slots)
    monkeypatch.setattr(lsp_gateway, "_ensure_backend_ready",
                        lambda **kw: None)
    tok1, err1 = lsp_gateway._register_session_internal(
        pipeline_id="interactive-old", target_path=target,
        problem="", workspace=tmp_path, log_path=None,
        kind="interactive", interactive=True)
    assert err1 is None
    # simulate the endpoint's reclaim: busy → evict interactive claims
    tok2, err2 = lsp_gateway._register_session_internal(
        pipeline_id="interactive-new", target_path=target,
        problem="", workspace=tmp_path, log_path=None,
        kind="interactive", interactive=True)
    assert "interactive slot busy" in (err2 or "")
    with lsp_gateway._state.sessions_lock:
        stale = [t for t, m in lsp_gateway._state.sessions.items()
                 if m.kind == "interactive"]
    for t in stale:
        lsp_gateway._release_session_internal(t)
    tok3, err3 = lsp_gateway._register_session_internal(
        pipeline_id="interactive-new", target_path=target,
        problem="", workspace=tmp_path, log_path=None,
        kind="interactive", interactive=True)
    assert err3 is None and tok3
    assert slots[0].claimed_by == "pipe-A"       # pipeline untouched
    assert slots[1].claimed_by == "interactive-new"
    lsp_gateway._release_session_internal(tok3)
