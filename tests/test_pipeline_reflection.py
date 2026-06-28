"""Unit tests for `Tooling/pipeline/_reflection.py` (Model B).

The agent-spawning side of reflection is best-effort (any exception is
swallowed; the dispatcher must never block on a failed reflection) and is
exercised end-to-end by live runs rather than mocked here. This file pins the
deterministic helpers: prompt template substitution, the existing-globals
render, and the decision-JSON → KB applier.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, kb
from Tooling.pipeline import PipelineResult
from Tooling.pipeline._retry import SpawnCtx, run_with_session_retries
from Tooling.pipeline import _reflection
from Tooling.pipeline._reflection import _render_globals, _render_prompt


# ---------------------------------------------------------------------
# Prompt template substitution
# ---------------------------------------------------------------------

def test_render_prompt_substitutes_braced_fields() -> None:
    template = "Hello {name}, you are {role}."
    out = _render_prompt(template, name="alice", role="agent")
    assert out == "Hello alice, you are agent."


def test_render_prompt_does_not_format_content_with_braces() -> None:
    """Lesson content can contain literal `{` (set-builder notation, Lean
    tactic blocks). Plain str.replace dodges str.format's brace-as-spec."""
    template = "Existing: {global_lessons}"
    lessons = "- {x : ℕ // x > 0} doesn't reduce\n- ‖a‖ ≤ ‖b‖"
    out = _render_prompt(template, global_lessons=lessons)
    assert "{x : ℕ // x > 0}" in out


# ---------------------------------------------------------------------
# _render_globals — the dedup/edit surface shown to the agent
# ---------------------------------------------------------------------

def test_render_globals_empty() -> None:
    assert _render_globals([]) == "(none yet)"


def test_render_globals_id_tagged_with_body() -> None:
    rows = [{"id": 3, "title": "prefer X over Y", "body": "line1\nline2"},
            {"id": 7, "title": "no body here", "body": ""}]
    out = _render_globals(rows)
    assert "- [id 3] prefer X over Y" in out
    assert "    line1" in out and "    line2" in out
    assert "- [id 7] no body here" in out


# ---------------------------------------------------------------------
# _apply_decision — decision JSON → KB write
# ---------------------------------------------------------------------

def test_apply_decision_skip_paths(tmp_path: Path,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    dp = tmp_path / "_reflection_decision.json"
    # no file → skip (never raises)
    assert "skip" in _reflection._apply_decision("p", 1, "s1", dp)
    # explicit skip
    dp.write_text('{"action": "skip"}', encoding="utf-8")
    assert _reflection._apply_decision("p", 1, "s1", dp) == "skip"
    # malformed JSON → skip, no raise
    dp.write_text("not json at all", encoding="utf-8")
    assert "skip" in _reflection._apply_decision("p", 1, "s1", dp)
    # unknown action → skip
    dp.write_text('{"action": "frobnicate"}', encoding="utf-8")
    assert "skip" in _reflection._apply_decision("p", 1, "s1", dp)


def _seed_problem_goal(tmp_path: Path) -> int:
    conn = db.connect()
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES ('p', 'Problems/p/Manifest.md', ?)", (db.now(),))
    gid = db.insert_goal(
        conn, problem="p", slug="g", lean_path="Problems/p/Root.lean",
        statement="True", origin="root")
    conn.commit()
    conn.close()
    return gid


def test_apply_decision_global_add_edit_and_node_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    gid = _seed_problem_goal(tmp_path)
    dp = tmp_path / "_reflection_decision.json"

    # node action retired → falls through to skip, writes nothing
    dp.write_text(json.dumps(
        {"action": "node", "title": "node insight", "body": "b1"}),
        encoding="utf-8")
    assert "skip" in _reflection._apply_decision("p", gid, "sid1", dp)

    # global add → node_id NULL
    dp.write_text(json.dumps(
        {"action": "global_add", "title": "global insight"}),
        encoding="utf-8")
    assert "global add" in _reflection._apply_decision("p", gid, "sid2", dp)

    conn = db.connect()
    rows = {r["title"]: r for r in kb.entries_for_problem(conn, "p")}
    assert "node insight" not in rows           # node decision wrote nothing
    assert rows["global insight"]["node_id"] is None
    gl_id = kb.global_lessons(conn, "p")[0]["id"]
    conn.close()

    # global edit by id
    dp.write_text(json.dumps(
        {"action": "global_edit", "id": gl_id, "title": "fixed", "body": "b2"}),
        encoding="utf-8")
    out = _reflection._apply_decision("p", gid, "sid3", dp)
    assert "global edit" in out and "ok" in out
    conn = db.connect()
    g = kb.global_lessons(conn, "p")[0]
    assert (g["title"], g["body"]) == ("fixed", "b2")
    conn.close()


def test_apply_decision_idempotent_on_sid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    gid = _seed_problem_goal(tmp_path)
    dp = tmp_path / "_reflection_decision.json"
    dp.write_text(json.dumps({"action": "global_add", "title": "once"}),
                  encoding="utf-8")
    assert "wrote" in _reflection._apply_decision("p", gid, "samesid", dp)
    # same sid → idempotent, no duplicate
    assert "dup" in _reflection._apply_decision("p", gid, "samesid", dp)
    conn = db.connect()
    assert len(kb.global_lessons(conn, "p")) == 1
    conn.close()


# ---------------------------------------------------------------------
# Trigger gate (T2 — exercises `_retry._maybe_reflect`)
# ---------------------------------------------------------------------

def _make_run(*, parse_outcome: PipelineResult | None = None,
              spawn_rc: int = 0):
    spawn_calls: list[SpawnCtx] = []
    parse_calls: list[int] = []
    pm_calls: list[str] = []

    def spawn_fn(ctx: SpawnCtx) -> int:
        spawn_calls.append(ctx)
        return spawn_rc

    def parse_fn() -> PipelineResult:
        parse_calls.append(1)
        if parse_outcome is None:
            return PipelineResult(
                outcome="failed", failure_reason="lake_build_error",
                failure_detail="(stub)")
        return parse_outcome

    def postmortem_fn(sid: str) -> None:
        pm_calls.append(sid)

    return spawn_fn, parse_fn, postmortem_fn, spawn_calls, parse_calls, pm_calls


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    db.init_schema(c)
    return c


def _seed_min_goal(conn: sqlite3.Connection) -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()))
    conn.commit()
    return db.insert_goal(
        conn, problem="p", slug="g", lean_path="Problems/p/Root.lean",
        statement="True", origin="root")


@pytest.mark.parametrize("outcome,reason,should_fire", [
    ("proved",     "",                       True),
    ("success",    "",                       True),
    ("exhausted",  "lake_build_error",       True),
    ("failed",     "agent_declined",         True),
    ("failed",     "agent_infeasible",       True),
    ("failed",     "goal_no_longer_open",    False),
    ("failed",     "spawn_fast_fail",        False),
    ("failed",     "quota_exhausted",        False),
    ("failed",     "missing_dep",            False),
    ("moot",       "",                       False),
])
def test_reflection_trigger_gate(
    conn: sqlite3.Connection, tmp_path: Path,
    outcome: str, reason: str, should_fire: bool,
) -> None:
    """`_maybe_reflect` filters by outcome + failure_reason: fire on proved /
    success / exhausted / agent_declined / agent_infeasible; skip moot,
    race-detected `goal_no_longer_open`, and infra rcs."""
    gid = _seed_min_goal(conn)
    fired: list[tuple[str, PipelineResult]] = []

    def reflect(sid: str, result: PipelineResult) -> None:
        fired.append((sid, result))

    spawn_fn, parse_fn, pm_fn, *_ = _make_run(
        parse_outcome=PipelineResult(outcome=outcome, failure_reason=reason))

    if outcome == "moot":
        for _ in range(3):
            db.increment_goal_attempts(conn, gid)

    run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-gate",
        budget_threshold=3, shelve_threshold=8, attempts_dir=tmp_path,
        spawn_fn=spawn_fn, parse_fn=parse_fn, postmortem_fn=pm_fn,
        reflection_fn=reflect)

    assert bool(fired) == should_fire, (
        f"outcome={outcome} reason={reason} expected fire={should_fire}, "
        f"got {len(fired)} call(s)")


# ---------------------------------------------------------------------
# C3-A — reflection retracts a directive its attempt disproved (sentinel)
# ---------------------------------------------------------------------

def _setup_reflection_ws(tmp_path: Path, directive: str):
    conn = db.connect()
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, "
        "bootstrap_done, strategist_directive) VALUES (?, ?, ?, 1, ?)",
        ("p", "Problems/p/Manifest.md", db.now(), directive))
    conn.commit()
    conn.close()
    problem_dir = tmp_path / "Problems" / "p"
    attempts = tmp_path / ".attempts" / "pid"
    prompt_dir = tmp_path / "prompts"
    for d in (problem_dir, attempts, prompt_dir):
        d.mkdir(parents=True)
    (prompt_dir / "reflection.md").write_text(
        "{outcome} :: {directive} :: {global_lessons} :: {decision_path}",
        encoding="utf-8")
    return problem_dir, attempts, prompt_dir


def _read_directive_p() -> "str | None":
    conn = db.connect()
    try:
        return conn.execute(
            "SELECT strategist_directive FROM problems WHERE name='p'"
        ).fetchone()["strategist_directive"]
    finally:
        conn.close()


def test_attempt_reflection_retracts_directive_on_sentinel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    problem_dir, attempts, prompt_dir = _setup_reflection_ws(
        tmp_path, "cite lemma X (it exists)")

    def fake_spawn(**kw):  # agent retracts mid-spawn
        (attempts / "_directive_retract.md").write_text(
            "lemma X was disproved this attempt", encoding="utf-8")
        return 0
    monkeypatch.setattr(_reflection.agent, "spawn_llm", fake_spawn)

    _reflection.attempt_reflection(
        kind="backward", sid="s1", slug="g", outcome="failed", goal_id=1,
        problem="p", problem_dir=problem_dir, attempts_dir=attempts,
        prompt_dir=prompt_dir, workspace=tmp_path)
    assert _read_directive_p() is None          # retracted


def test_attempt_reflection_keeps_directive_without_sentinel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    problem_dir, attempts, prompt_dir = _setup_reflection_ws(tmp_path, "keep me")
    monkeypatch.setattr(_reflection.agent, "spawn_llm", lambda **kw: 0)
    _reflection.attempt_reflection(
        kind="backward", sid="s1", slug="g", outcome="failed", goal_id=1,
        problem="p", problem_dir=problem_dir, attempts_dir=attempts,
        prompt_dir=prompt_dir, workspace=tmp_path)
    assert _read_directive_p() == "keep me"     # untouched


def test_attempt_reflection_uses_full_problem_name_for_kb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (multi-chart stress-test bug): a NAMESPACED problem
    (`Geometry.foo` → `Problems/Geometry/foo`, leaf `foo`) must write KB lessons
    under the FULL registered name, not `problem_dir.name` (the leaf) — else the
    `kb_entries.problem → problems(name)` FK fails and the decision is dropped
    ('decision skipped — FOREIGN KEY constraint failed')."""
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES ('Geometry.foo', 'Problems/Geometry/foo/Manifest.md', ?, 1)",
        (db.now(),))
    gid = db.insert_goal(
        conn, problem="Geometry.foo", slug="g",
        lean_path="Problems/Geometry/foo/Root.lean", statement="True",
        origin="root")
    conn.commit()
    conn.close()

    problem_dir = tmp_path / "Problems" / "Geometry" / "foo"   # .name == 'foo'
    attempts = tmp_path / ".attempts" / "pid"
    prompt_dir = tmp_path / "prompts"
    for d in (problem_dir, attempts, prompt_dir):
        d.mkdir(parents=True)
    (prompt_dir / "reflection.md").write_text(
        "{global_lessons} :: {decision_path}", encoding="utf-8")

    def fake_spawn(**kw):  # agent records a global insight
        (attempts / "_reflection_decision.json").write_text(
            json.dumps({"action": "global_add", "title": "real insight"}),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(_reflection.agent, "spawn_llm", fake_spawn)

    _reflection.attempt_reflection(
        kind="backward", sid="sX", slug="g", outcome="proved", goal_id=gid,
        problem="Geometry.foo", problem_dir=problem_dir, attempts_dir=attempts,
        prompt_dir=prompt_dir, workspace=tmp_path)

    conn = db.connect()
    try:
        full = kb.entries_for_problem(conn, "Geometry.foo")
        assert [r["title"] for r in full] == ["real insight"]   # landed
        assert full[0]["node_id"] is None                       # global
        assert kb.entries_for_problem(conn, "foo") == []         # NOT the leaf
    finally:
        conn.close()
