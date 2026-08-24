"""Formalizer intake stage (update_plan_2026_07 #1).

Contract (user ruling 2026-07-27): intake is an ECONOMY gate, not a
soundness gate — the only binding signal is the decline; every
malfunction degrades to the classic cold flow and never blocks work.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.pipeline import _intake
from Tooling.pipeline._intake import IntakeOutcome, run_intake
from Tooling.llm.base import SpawnRC
from Tooling.state import db, intent as intent_mod
from Tooling import pipeline
from Tooling import agent


PROMPT_DIR = Path("Tooling/prompts")


def _spawn_writing(sentinel_body: "str | None", rc: int = 0):
    def fake_spawn(**kw):
        if sentinel_body is not None:
            (kw["attempts_dir"] / "intake.json").write_text(
                sentinel_body, encoding="utf-8")
        return rc
    return fake_spawn


# ---------------------------------------------------------------------
# run_intake — sentinel parsing
# ---------------------------------------------------------------------

def test_intake_proceed_returns_sid(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(agent, "spawn_llm",
                        _spawn_writing('{"verdict": "proceed"}'))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.sid is not None
    assert out.declined is None and out.infra_rc is None


def test_intake_decline_carries_reason_and_note(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(agent, "spawn_llm", _spawn_writing(json.dumps({
        "verdict": "decline", "reason": "return_to_nl",
        "note": "the Proof argues nothing about λ-coupling"})))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.declined == ("return_to_nl",
                            "the Proof argues nothing about λ-coupling")


def test_intake_missing_sentinel_fails_open(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(agent, "spawn_llm", _spawn_writing(None))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.sid is not None and out.declined is None


def test_intake_malformed_sentinel_fails_open(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(agent, "spawn_llm", _spawn_writing("{not json"))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.sid is not None and out.declined is None


def test_intake_unknown_verdict_fails_open(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(agent, "spawn_llm",
                        _spawn_writing('{"verdict": "maybe"}'))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.sid is not None and out.declined is None


def test_intake_unknown_decline_reason_fails_open(tmp_path, monkeypatch) -> None:
    """Task #124: with a two-word vocabulary, coercing an unknown reason
    (the pre-#124 fail-safe) is a mislabel — proceed instead; the work
    turn carries the full decline vocabulary."""
    monkeypatch.setattr(agent, "spawn_llm", _spawn_writing(json.dumps({
        "verdict": "decline", "reason": "return_to_parent", "note": "x"})))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.declined is None and out.sid is not None


def test_intake_unprovable_decline_carries_counterexample(
    tmp_path, monkeypatch,
) -> None:
    """Task #124 (archaeology: 27/27 disproved goals were killed by a
    fresh agent's unprovable decline, never the transcribing parent —
    the falsity scan belongs at the fresh zero-sunk-cost turn)."""
    monkeypatch.setattr(agent, "spawn_llm", _spawn_writing(json.dumps({
        "verdict": "decline", "reason": "unprovable",
        "note": "n=0: LHS=1, RHS=0 — inequality reversed"})))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.declined == ("unprovable",
                            "n=0: LHS=1, RHS=0 — inequality reversed")


def test_intake_unprovable_without_note_fails_open(
    tmp_path, monkeypatch,
) -> None:
    """The bar is a concrete counterexample — a bare unprovable verdict
    must not flip a goal to disproved on a hunch."""
    monkeypatch.setattr(agent, "spawn_llm", _spawn_writing(json.dumps({
        "verdict": "decline", "reason": "unprovable"})))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.declined is None and out.sid is not None


def test_intake_quota_rc_surfaces_infra(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(agent, "spawn_llm",
                        _spawn_writing(None, rc=SpawnRC.QUOTA_EXHAUSTED))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.infra_rc == SpawnRC.QUOTA_EXHAUSTED


def test_intake_generic_error_degrades_to_cold(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(agent, "spawn_llm", _spawn_writing(None, rc=1))
    out = run_intake(prompt_dir=PROMPT_DIR, attempts_dir=tmp_path,
                     problem_dir=tmp_path, label="t")
    assert out.sid is None and out.declined is None and out.infra_rc is None


# ---------------------------------------------------------------------
# run_backward wiring
# ---------------------------------------------------------------------

def _seed_root_goal(tmp_path: Path, conn: sqlite3.Connection) -> int:
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    conn.execute(
        "INSERT INTO problems (name, created_at,"
        " bootstrap_done) VALUES ('p', ?, 1)",
        (db.now(),))
    conn.commit()
    root = pdir / "Root.lean"
    root.write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem main : True := by sorry\nend Problems.p\n",
        encoding="utf-8")
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path=root.relative_to(tmp_path).as_posix(),
        statement="True", origin="root", depth=0)


@pytest.fixture(autouse=True)
def _no_hint_prepass(monkeypatch):
    """Pin the hint pre-pass OFF for the wiring tests (it would call the
    gateway); intake behavior is what's under test here."""
    from Tooling.pipeline import _axiom
    monkeypatch.setattr(_axiom, "verify_on_own_slot",
                        lambda *a, **k: {"ok": False, "error": "stub"})


def test_backward_intake_decline_exits_before_work(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gid = _seed_root_goal(tmp_path, conn)
    monkeypatch.setattr(
        _intake, "run_intake",
        lambda **kw: IntakeOutcome(
            declined=("return_to_nl", "unbacked λ-coupling")))
    presearched = {"n": 0}
    from Tooling.pipeline import _presearch
    monkeypatch.setattr(
        _presearch, "ensure_presearch",
        lambda **kw: presearched.__setitem__("n", presearched["n"] + 1))

    def _no_loop(**kw):
        raise AssertionError("work loop must not run after intake decline")
    monkeypatch.setattr("Tooling.pipeline._retry.run_lsp_edit_loop", _no_loop)

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        intent=intent_mod.ProblemIntent(problem="p", charter="True"),
        pipeline_id="pid-intake-decline")
    assert r.failure_reason == "return_to_nl"
    assert "unbacked λ-coupling" in (r.failure_detail or "")
    assert presearched["n"] == 0, "declined goal must not pay presearch"


def test_backward_intake_unprovable_maps_to_agent_infeasible(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task #124 + owner ruling 2026-08-25: an intake unprovable decline
    rides the SAME DECLINE_TO_FAILURE_REASON map as the work-turn
    directive — which now lands `agent_declined` (NON-terminal): the
    claim reaches the Strategist, and disproved is reachable only via
    the kernel-certified `-- decline: disprove` gate."""
    gid = _seed_root_goal(tmp_path, conn)
    monkeypatch.setattr(
        _intake, "run_intake",
        lambda **kw: IntakeOutcome(
            declined=("unprovable", "n=0 breaks the inequality")))

    def _no_loop(**kw):
        raise AssertionError("work loop must not run after intake decline")
    monkeypatch.setattr("Tooling.pipeline._retry.run_lsp_edit_loop", _no_loop)

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        intent=intent_mod.ProblemIntent(problem="p", charter="True"),
        pipeline_id="pid-intake-unprovable")
    assert r.failure_reason == "agent_declined"
    assert "n=0 breaks the inequality" in (r.failure_detail or "")


def test_backward_intake_sid_threads_to_work_loop(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gid = _seed_root_goal(tmp_path, conn)
    monkeypatch.setattr(_intake, "run_intake",
                        lambda **kw: IntakeOutcome(sid="intake-sid-42"))
    from Tooling.pipeline import _presearch
    monkeypatch.setattr(_presearch, "ensure_presearch", lambda **kw: None)
    seen = {}

    def fake_loop(**kw):
        seen["initial_sid"] = kw.get("initial_sid")
        return pipeline.PipelineResult(outcome="moot")
    import Tooling.pipeline.backward as bw
    monkeypatch.setattr(bw, "run_lsp_edit_loop", fake_loop, raising=False)
    monkeypatch.setattr("Tooling.pipeline._retry.run_lsp_edit_loop",
                        fake_loop)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        intent=intent_mod.ProblemIntent(problem="p", charter="True"),
        pipeline_id="pid-intake-sid")
    assert seen.get("initial_sid") == "intake-sid-42"
