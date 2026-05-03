"""P2-#2 — direct entry-point tests for `pipeline.run_builder`.

Coverage was inverted: 50+ tests on private helpers (_signature_prefix,
_lake_build_modules, _promote_to_alias, ...) but 0 direct
`run_builder` tests. The four happy / unhappy paths are covered here:

  - tactic_try Phase 1 closes the goal (e.g. `rfl` on a fresh stub).
  - tactic_try exhausted → falls into LLM Phase 2.
  - LLM patch builds → 'proved' + backup cleaned.
  - LLM declines (PROPOSAL.md without patch.lean) → F48 'agent_declined'.
  - LLM patch fails lake → 'lake_build_error', goal_lean restored from backup.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import agent, db, manifest, pipeline


def _seed_problem(conn: sqlite3.Connection, tmp_path: Path) -> int:
    """Build the minimal workspace + DB rows run_builder needs."""
    problem = "p"
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n## Statement\nTrue\n", encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        (problem, str(pdir / "Manifest.md"), db.now()))
    conn.commit()
    root = pdir / "Root.lean"
    root.write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem main : True := by sorry\n"
        "end Problems.p\n",
        encoding="utf-8")
    rel = root.relative_to(tmp_path).as_posix()
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path=rel,
        statement="True", origin="root", difficulty=2, depth=0,
    )


def _mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="True")


def test_run_builder_phase1_tactic_try_closes_fresh_stub(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh `:= by sorry` goal gets `rfl`-tier tactics tried first.
    With _lake_build stubbed True, the FIRST tactic in the list wins
    and run_builder returns 'proved' without ever spawning the LLM."""
    gid = _seed_problem(conn, tmp_path)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: (True, ""))
    spawn_calls = []
    monkeypatch.setattr(agent, "spawn_llm",
                        lambda **kw: spawn_calls.append(1) or 0)

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-tac")
    assert r.outcome == "proved"
    assert not spawn_calls  # Phase 1 short-circuited; no LLM


def test_run_builder_phase2_llm_patch_builds(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When attempts > 0 (forces past Phase 1), Builder spawns the LLM,
    grabs patch.lean, lake-builds against it, returns 'proved'."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)  # bypass tactic_try

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "patch.lean").write_text(
            "import Mathlib\ntheorem main : True := trivial\n",
            encoding="utf-8")
        (kw["attempts_dir"] / "PROPOSAL.md").write_text(
            "trivial direct proof", encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: (True, ""))

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-llm-ok")
    assert r.outcome == "proved"


def test_run_builder_decline_returns_agent_declined(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F48: LLM writes PROPOSAL.md but no patch.lean → outcome='failed'
    with reason='agent_declined' so cascade can fast-track to Backward."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "PROPOSAL.md").write_text(
            "this needs decomposition; no direct tactic suffices",
            encoding="utf-8")
        # NO patch.lean
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-decline")
    assert r.outcome == "failed"
    assert r.failure_reason == "agent_declined"
    assert "decomposition" in r.proposal_md


def test_run_builder_lake_fail_restores_backup(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM produces a patch that lake rejects → goal_lean restored
    from backup unchanged. Reason='lake_build_error'."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)
    goal_lean = tmp_path / db.get_goal(conn, gid)["lean_path"]
    original = goal_lean.read_text(encoding="utf-8")

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "patch.lean").write_text(
            "garbage that won't build", encoding="utf-8")
        (kw["attempts_dir"] / "PROPOSAL.md").write_text("guess", encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: (False, "error: garbage"))

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-bad")
    assert r.outcome == "failed"
    assert r.failure_reason == "lake_build_error"
    assert "garbage" in (r.failure_detail or "")
    # Goal lean unchanged + no .backup leftover
    assert goal_lean.read_text(encoding="utf-8") == original
    assert not goal_lean.with_suffix(goal_lean.suffix + ".backup").exists()


def test_run_builder_forbidden_lemma_blocked(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manifest's `forbidden_lemmas` filter applies to LLM output.
    Patch citing a forbidden name returns failure_reason='forbidden_lemma'
    BEFORE even attempting lake build."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)
    mfst = manifest.Manifest(
        problem="p", statement="True",
        forbidden_lemmas=["Cheat.theorem"])

    lake_calls = []
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: lake_calls.append(1) or (True, ""))

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "patch.lean").write_text(
            "import Mathlib\ntheorem main : True := Cheat.theorem\n",
            encoding="utf-8")
        (kw["attempts_dir"] / "PROPOSAL.md").write_text("p", encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=mfst,
        pipeline_id="pid-forbid")
    assert r.outcome == "failed"
    assert r.failure_reason == "forbidden_lemma"
    assert "Cheat.theorem" in (r.failure_detail or "")
    assert not lake_calls  # rejected before lake
