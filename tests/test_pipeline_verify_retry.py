"""F41 — Verify-time patch retry.

When `_strategy_sNN.lean` fails Step 1 lake build (sub-goals proved
individually but combined patch fails to elaborate — typically
implicit-arg / typeclass drift), the framework asks the LLM ONCE to
rewrite the strategy patch (sub-goals untouched). On success the
Verify continues to Step 2; on failure the original patch is restored
and the standard cascade fires.

These tests exercise the retry decision tree without spawning a real
LLM or invoking lake. Both `agent.spawn_llm` and `pipeline._lake_build`
are monkeypatched so the test runs in milliseconds.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from Tooling import agent, db, manifest, pipeline


# ---------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------

def _seed_problem_with_strategy(
    tmp_path: Path, conn: sqlite3.Connection,
) -> tuple[int, Path, Path]:
    """Build a workspace tree with a Problem, a root goal, a strategy,
    and 2 sub-goals (each its own L_*.lean file with a real proved
    body). Returns (strategy_id, scratch_path, attempts_dir)."""
    problem = "p"
    pdir = tmp_path / "Problems" / problem
    proofs_dir = pdir / "proofs"
    proofs_dir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n## Statement\n\nTrue\n", encoding="utf-8")

    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        (problem, str(pdir / "Manifest.md"), db.now()))
    conn.commit()

    # Root goal
    root_lean = pdir / "Root.lean"
    root_lean.write_text(
        "import Mathlib\ntheorem main : True := by trivial\n",
        encoding="utf-8")
    rel_root = str(root_lean.relative_to(tmp_path)).replace("\\", "/")
    gid = db.insert_goal(
        conn, problem=problem, slug="main", lean_path=rel_root,
        statement="True", origin="root", depth=0,
    )

    # Strategy
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path=rel_root,
        scratch_path=f"Problems/{problem}/proofs/_strategy_s1.lean",
        created_by="pid-bw",
        proposal_md="seed strategy")

    # Sub-goals (2)
    for i in (1, 2):
        slug = f"s{sid}_sub_{i}"
        sub_path = proofs_dir / f"L_{slug}.lean"
        sub_path.write_text(
            f"theorem {slug} : True := by trivial\n", encoding="utf-8")
        rel = str(sub_path.relative_to(tmp_path)).replace("\\", "/")
        sg_id = db.insert_goal(
            conn, problem=problem, slug=slug, lean_path=rel,
            statement="True", origin="backward", depth=1,
        )
        conn.execute(
            "UPDATE goals SET status='proved' WHERE id=?", (sg_id,))
        conn.execute(
            "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position) "
            "VALUES (?, ?, ?)", (sid, sg_id, i - 1))
    conn.commit()

    # Strategy scratch file (the combined patch)
    scratch_abs = proofs_dir / "_strategy_s1.lean"
    scratch_abs.write_text(
        f"import Mathlib\ntheorem s{sid} : True := by trivial\n",
        encoding="utf-8")

    # Attempts dir as run_verify will use it
    attempts_dir = tmp_path / ".attempts" / "pid-verify"
    attempts_dir.mkdir(parents=True)

    return sid, scratch_abs, attempts_dir


def _strategy_row(conn: sqlite3.Connection, sid: int) -> sqlite3.Row:
    """Pull the strategy row joined with goal info, matching what
    run_verify queries."""
    return conn.execute(
        "SELECT s.*, g.status AS goal_status, g.slug AS goal_slug,"
        "       g.statement AS goal_statement, g.problem AS goal_problem"
        " FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE s.id = ?",
        (sid,),
    ).fetchone()


# ---------------------------------------------------------------------
# _verify_patch_retry — direct unit tests
# ---------------------------------------------------------------------

def test_retry_off_when_env_disabled(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASTERISM_VERIFY_RETRY=0 → retry is a no-op (returns False, None)
    without touching the scratch file or invoking the LLM."""
    monkeypatch.setenv("ASTERISM_VERIFY_RETRY", "0")
    sid, scratch_abs, _ = _seed_problem_with_strategy(tmp_path, conn)
    spawn_called = []
    monkeypatch.setattr(agent, "spawn_llm",
                        lambda **kw: spawn_called.append(kw) or 0)
    original = scratch_abs.read_text(encoding="utf-8")

    ok, err = pipeline._verify_patch_retry(
        conn, workspace=tmp_path, pipeline_id="pid-verify",
        strategy=_strategy_row(conn, sid),
        scratch_abs=scratch_abs,
        lake_err="some error",
    )
    assert ok is False
    assert err is None
    assert not spawn_called  # LLM never invoked
    assert scratch_abs.read_text(encoding="utf-8") == original  # untouched


def test_retry_succeeds_when_llm_writes_good_patch(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: LLM returns rc=0 + writes patch.lean, lake_build
    accepts the new patch → returns (True, None) and scratch_abs holds
    the new patch."""
    monkeypatch.delenv("ASTERISM_VERIFY_RETRY", raising=False)
    sid, scratch_abs, _ = _seed_problem_with_strategy(tmp_path, conn)

    new_patch_content = (
        f"import Mathlib\ntheorem s{sid} : True := by trivial -- fixed\n")

    def fake_spawn(**kw):
        attempts_dir = kw["attempts_dir"]
        # Verify the prompt is the verify_retry one
        assert kw["prompt_path"].name == "verify_retry.md"
        # LLM must NOT receive a session_id — F41 retry is always cold
        assert kw.get("session_id") is None
        (attempts_dir / "patch.lean").write_text(
            new_patch_content, encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build", lambda *a, **kw: (True, ""))

    ok, err = pipeline._verify_patch_retry(
        conn, workspace=tmp_path, pipeline_id="pid-verify",
        strategy=_strategy_row(conn, sid),
        scratch_abs=scratch_abs,
        lake_err="elaboration failed",
    )
    assert ok is True
    assert err is None
    assert scratch_abs.read_text(encoding="utf-8") == new_patch_content
    # Backup file must be cleaned up
    backup = scratch_abs.with_suffix(scratch_abs.suffix + ".verify_retry_backup")
    assert not backup.exists()


def test_retry_restores_when_llm_patch_still_fails_lake(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM writes patch.lean but lake_build still rejects it. Original
    scratch must be restored unchanged so the caller can fall through
    to the standard cascade with no contamination."""
    monkeypatch.delenv("ASTERISM_VERIFY_RETRY", raising=False)
    sid, scratch_abs, _ = _seed_problem_with_strategy(tmp_path, conn)
    original = scratch_abs.read_text(encoding="utf-8")

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "patch.lean").write_text(
            "broken patch", encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda *a, **kw: (False, "still broken"))

    ok, err = pipeline._verify_patch_retry(
        conn, workspace=tmp_path, pipeline_id="pid-verify",
        strategy=_strategy_row(conn, sid),
        scratch_abs=scratch_abs,
        lake_err="original error",
    )
    assert ok is False
    assert err == "still broken"
    assert scratch_abs.read_text(encoding="utf-8") == original
    backup = scratch_abs.with_suffix(scratch_abs.suffix + ".verify_retry_backup")
    assert not backup.exists()


def test_retry_restores_when_llm_writes_no_patch(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM returns rc=0 but skips writing patch.lean → no-op restore."""
    monkeypatch.delenv("ASTERISM_VERIFY_RETRY", raising=False)
    sid, scratch_abs, _ = _seed_problem_with_strategy(tmp_path, conn)
    original = scratch_abs.read_text(encoding="utf-8")

    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 0)
    lake_called = []
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda *a, **kw: lake_called.append(1) or (True, ""))

    ok, err = pipeline._verify_patch_retry(
        conn, workspace=tmp_path, pipeline_id="pid-verify",
        strategy=_strategy_row(conn, sid),
        scratch_abs=scratch_abs,
        lake_err="x",
    )
    assert ok is False
    assert err is None
    assert not lake_called  # never re-built since no patch was offered
    assert scratch_abs.read_text(encoding="utf-8") == original


def test_retry_restores_when_llm_rc_nonzero(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM rc != 0 (timeout / quota / spawn error) → no-op restore."""
    monkeypatch.delenv("ASTERISM_VERIFY_RETRY", raising=False)
    sid, scratch_abs, _ = _seed_problem_with_strategy(tmp_path, conn)
    original = scratch_abs.read_text(encoding="utf-8")

    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 124)  # timeout
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda *a, **kw: (True, ""))

    ok, err = pipeline._verify_patch_retry(
        conn, workspace=tmp_path, pipeline_id="pid-verify",
        strategy=_strategy_row(conn, sid),
        scratch_abs=scratch_abs,
        lake_err="x",
    )
    assert ok is False
    assert err is None
    assert scratch_abs.read_text(encoding="utf-8") == original


def test_retry_context_md_includes_patch_subs_and_stderr(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: the Context.md the framework writes for the LLM has
    the original patch, both sub-goal lean files, and the truncated
    lake stderr — i.e. all the data F41's retry hypothesis needs."""
    monkeypatch.delenv("ASTERISM_VERIFY_RETRY", raising=False)
    sid, scratch_abs, attempts_dir = _seed_problem_with_strategy(
        tmp_path, conn)

    captured = {}

    def fake_spawn(**kw):
        captured["context_md"] = (kw["attempts_dir"] / "Context.md").read_text(
            encoding="utf-8")
        # Don't write a patch — we only care about Context here
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline._verify_patch_retry(
        conn, workspace=tmp_path, pipeline_id="pid-verify",
        strategy=_strategy_row(conn, sid),
        scratch_abs=scratch_abs,
        lake_err="error: typeclass instance problem stuck Membership ?m.2",
    )

    md = captured["context_md"]
    assert f"strategy s{sid}" in md
    assert f"theorem s{sid}" in md  # original patch text
    assert f"theorem s{sid}_sub_1" in md  # sub-goal lean inlined
    assert f"theorem s{sid}_sub_2" in md
    assert "typeclass instance problem stuck" in md  # stderr surfaced


# ---------------------------------------------------------------------
# run_verify integration — F41 hook fires only on Step 1 lake fail
# ---------------------------------------------------------------------

def test_run_verify_step1_success_skips_retry(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Step 1 lake build passes, retry must not fire."""
    sid, scratch_abs, _ = _seed_problem_with_strategy(tmp_path, conn)
    retry_calls = []
    monkeypatch.setattr(pipeline, "_verify_patch_retry",
                        lambda *a, **kw: retry_calls.append(1) or (False, None))
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda *a, **kw: (True, ""))

    result = pipeline.run_verify(
        conn, strategy_id=sid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-verify",
    )
    assert result.outcome == "proved"
    assert retry_calls == []  # retry never reached


def test_run_verify_step1_fail_then_retry_succeeds(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 1 lake fails → retry succeeds → Step 2 (parent rewrite)
    proceeds → outcome='proved'."""
    sid, scratch_abs, _ = _seed_problem_with_strategy(tmp_path, conn)

    # First lake_build call (Step 1) fails; subsequent (Step 2 parent)
    # succeeds. Use a counter to switch.
    calls = {"n": 0}

    def fake_lake(*a, **kw):
        calls["n"] += 1
        # Step 1 = call 1 → fail; Step 2 = call 2 → succeed
        return (True, "") if calls["n"] >= 2 else (False, "first error")

    monkeypatch.setattr(pipeline, "_lake_build", fake_lake)
    # Retry returns (True, None) — bypasses internal logic for this test.
    monkeypatch.setattr(pipeline, "_verify_patch_retry",
                        lambda *a, **kw: (True, None))

    result = pipeline.run_verify(
        conn, strategy_id=sid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-verify",
    )
    assert result.outcome == "proved"


def test_run_verify_step1_fail_and_retry_fail_drops_to_cascade(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 1 lake fails AND retry fails → standard failure path,
    failure_reason='lake_build_error' carrying the ORIGINAL stderr
    (not the retry's stderr — that's just additional data not
    surfaced through cascade)."""
    sid, scratch_abs, _ = _seed_problem_with_strategy(tmp_path, conn)

    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda *a, **kw: (False, "original step1 error"))
    monkeypatch.setattr(pipeline, "_verify_patch_retry",
                        lambda *a, **kw: (False, "retry stderr"))

    result = pipeline.run_verify(
        conn, strategy_id=sid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-verify",
    )
    assert result.outcome == "failed"
    assert result.failure_reason == "lake_build_error"
    assert "original step1 error" in (result.failure_detail or "")
