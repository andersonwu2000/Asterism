"""P2-#2 — direct entry-point tests for `pipeline.run_builder`.

Coverage was inverted: 50+ tests on private helpers (_signature_prefix,
_lake_build_modules, _promote_to_alias, ...) but 0 direct
`run_builder` tests. The four happy / unhappy paths are covered here:

  - tactic_try Phase 1 closes the goal (e.g. `rfl` on a fresh stub).
  - tactic_try Phase 1 fails → falls through to Phase 2 LLM in same dispatch.
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
        statement="True", origin="root", depth=0,
    )


def _mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="True")


_FAKE_HINT_OUT = (
    "info: x.lean:1:1: Try these:\n"
    "  [apply] 🎉️ trivial\n"
)


def test_run_builder_phase1_tactic_try_closes_fresh_stub(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh `:= by sorry` goal goes through Mathlib `hint`. With
    _lake_build stubbed to return a Try-these block whose first marker
    is `🎉️ trivial`, Phase 1 captures that as the winner and
    run_builder returns 'proved' without ever spawning the LLM."""
    gid = _seed_problem(conn, tmp_path)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: (True, _FAKE_HINT_OUT))
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
    grabs patch.lean (Phase 6: single output, leading comment block +
    body), lake-builds, returns 'proved'. The proved goal file IS the
    patch.lean verbatim — agent already wrote the annotation in place."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)  # bypass tactic_try

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "patch.lean").write_text(
            "-- main: trivial direct proof\n"
            "-- closes via `trivial`\n"
            "import Mathlib\ntheorem main : True := trivial\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: (True, ""))

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-llm-ok")
    assert r.outcome == "proved"
    goal = db.get_goal(conn, gid)
    proved_text = (tmp_path / goal["lean_path"]).read_text(encoding="utf-8")
    assert proved_text.startswith("-- main: trivial direct proof")
    assert "-- closes via `trivial`" in proved_text


def test_run_builder_phase2_empty_leading_comments_fails_no_annotation(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 6 requires patch.lean to open with a leading `--` comment
    block (the goal's annotation source). A patch lacking it → outcome
    'failed' with reason 'agent_no_annotation'; goal_lean rolls back to
    its sorry stub so retry can proceed cleanly."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)  # bypass tactic_try
    goal = db.get_goal(conn, gid)
    original_text = (tmp_path / goal["lean_path"]).read_text(encoding="utf-8")

    def fake_spawn(**kw):
        # No leading comment block — agent forgot the annotation.
        (kw["attempts_dir"] / "patch.lean").write_text(
            "import Mathlib\ntheorem main : True := trivial\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: (True, ""))

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-llm-no-annot")
    assert r.outcome == "failed"
    assert r.failure_reason == "agent_no_annotation"
    # Rolled back to original sorry stub
    assert (tmp_path / goal["lean_path"]).read_text(encoding="utf-8") == original_text


def test_run_builder_decline_returns_agent_declined(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 6 decline channel: agent writes patch.lean with a leading
    `-- decline: too_hard` directive and `:= by sorry` body kept. Maps
    to outcome='failed' / reason='agent_declined' so cascade fast-tracks
    to Backward."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "patch.lean").write_text(
            "-- decline: too_hard\n"
            "-- this needs decomposition; no direct tactic suffices\n"
            "import Mathlib\ntheorem main : True := by sorry\n",
            encoding="utf-8")
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


# ---------------------------------------------------------------------
# F55 — wrapper persists/clears partial-output draft per outcome
# ---------------------------------------------------------------------

def _drafts_path_for(tmp_path: Path, gid: int) -> Path:
    return tmp_path / "Problems" / "p" / ".drafts" / f"builder_g{gid}.md"


def test_run_builder_wrapper_persists_progress_note_after_timeout(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F55 — Builder times out (rc=124). Framework triggers postmortem
    spawn that writes _progress.md. Wrapper then persists _progress.md
    into .drafts/ so the next spawn sees the captured state + blocker."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)

    def fake_spawn(**kw):
        # Main spawn times out. Postmortem spawn (is_postmortem=True)
        # writes the note and exits 0.
        if kw.get("is_postmortem"):
            (kw["attempts_dir"] / "_progress.md").write_text(
                "tried bogus_tactic; need a divisibility lemma I can't name",
                encoding="utf-8")
            return 0
        return 124  # main timeout
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-timeout-1")
    draft = _drafts_path_for(tmp_path, gid)
    assert draft.exists()
    body = draft.read_text(encoding="utf-8")
    assert "_progress.md" in body
    assert "divisibility lemma" in body


def test_run_builder_wrapper_no_persist_when_postmortem_skipped(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-timeout failure (lake_build_error) → no postmortem fires →
    no _progress.md → no draft persisted. F33 warm-resume covers this
    failure mode separately; F55 is timeout-specific."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "patch.lean").write_text(
            "garbage", encoding="utf-8")
        (kw["attempts_dir"] / "PROPOSAL.md").write_text(
            "tried", encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: (False, "error: garbage"))

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-lake-fail")
    assert r.outcome == "failed"
    assert r.failure_reason == "lake_build_error"
    draft = _drafts_path_for(tmp_path, gid)
    assert not draft.exists()


def test_run_builder_wrapper_clears_draft_on_proved(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F55 — successful build clears any prior draft so a future
    Builder dispatch on this same goal (rare; cascade re-open) starts
    clean."""
    gid = _seed_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)
    # Pre-seed a stale draft from an earlier failed attempt
    draft = _drafts_path_for(tmp_path, gid)
    draft.parent.mkdir(parents=True)
    draft.write_text("stale prior content", encoding="utf-8")

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "patch.lean").write_text(
            "-- main: ok\n"
            "import Mathlib\ntheorem main : True := trivial",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build", lambda ws, t: (True, ""))

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-ok")
    assert r.outcome == "proved"
    assert not draft.exists()


def test_run_builder_phase1_fail_falls_through_to_llm(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Phase 1 `hint` returns no winner, Builder must NOT terminate
    early — it falls through to Phase 2 LLM in the SAME dispatch.

    Two `_lake_build` invocations to model: Phase 1 probe build and
    Phase 2 patch build. Phase 1 fails, Phase 2 succeeds. Asserts
    spawn_llm got called and the final outcome is `proved`.
    """
    gid = _seed_problem(conn, tmp_path)

    # _lake_build sequence: Phase 1 probe fail → Phase 2 patch ok.
    # Returns (ok, output) per call.
    build_calls = iter([
        (False, "error: No suggestions available"),  # Phase 1 probe
        (True, ""),                                   # Phase 2 lake_build
    ])
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: next(build_calls))

    spawn_calls = []
    def fake_spawn(**kw):
        spawn_calls.append(1)
        (kw["attempts_dir"] / "patch.lean").write_text(
            "-- main: fall-through proof\n"
            "import Mathlib\ntheorem main : True := trivial\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=_mfst(),
        pipeline_id="pid-ft")
    assert r.outcome == "proved"
    assert spawn_calls == [1]  # Phase 2 LLM was reached
