"""F40 — Two-phase Builder delivery.

Behavioral tests over `pipeline.run_builder` covering:
  - default (TWO_PHASE off): single spawn_llm with builder.md
  - opt-in (TWO_PHASE=1): two spawns, phase_a then phase_b
  - phase A wrote no PROPOSAL.md → fail with phase_a_no_proposal
  - phase B fails after phase A succeeds → proposal_md preserved on result
  - phase B always cold (session_id=None) even when phase A had a session

`agent.spawn_llm` and `pipeline._lake_build` are monkeypatched: the fake
spawn writes deterministic outputs into attempts_dir to mimic an LLM,
and lake_build is forced to succeed unless the test wants otherwise.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from Tooling import agent, db, manifest, pipeline


def _seed(tmp_path: Path, conn: sqlite3.Connection) -> tuple[int, manifest.Manifest, Path]:
    """Register a problem with a single root goal whose lean file lives
    under tmp_path. Goal attempts pre-set to 1 so run_builder skips the
    Phase 1 tactic_try fast path and goes straight to LLM Phase 2."""
    problem = "wilson_test"
    problems_dir = tmp_path / "Problems" / problem
    proofs_dir = problems_dir / "proofs"
    proofs_dir.mkdir(parents=True)
    (problems_dir / "Manifest.md").write_text(
        "---\nproblem: wilson_test\nstatement: 'p'\n---\n", encoding="utf-8"
    )
    goal_lean = proofs_dir / "L_main.lean"
    goal_lean.write_text(
        "import Mathlib\ntheorem main_t : True := by trivial\n",
        encoding="utf-8",
    )
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        (problem, str(problems_dir / "Manifest.md"), db.now()),
    )
    conn.commit()
    rel_path = str(goal_lean.relative_to(tmp_path)).replace("\\", "/")
    gid = db.insert_goal(
        conn, problem=problem, slug="main", lean_path=rel_path,
        statement="True", origin="root",
    )
    # Bump attempts to 1 so Phase 1 (tactic_try, only on attempts==0 + sorry stub) is skipped.
    conn.execute(
        "UPDATE goals SET attempts = 1 WHERE id = ?", (gid,),
    )
    conn.commit()
    mfst = manifest.Manifest(problem=problem, statement="True")
    return gid, mfst, tmp_path


def _patch_lake_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "_lake_build", lambda *a, **kw: (True, ""))


def _make_fake_spawn(behaviors: dict[str, Any]) -> tuple[list[dict], Any]:
    """`behaviors` keys are prompt-file basenames; values are callables
    `(attempts_dir) -> rc` (or an int rc for static behavior). Returns
    `(spawn_log, fake_spawn)`. spawn_log accumulates each call's kwargs."""
    log: list[dict] = []

    def fake_spawn(**kwargs: Any) -> int:
        log.append(kwargs)
        prompt_name = kwargs["prompt_path"].name
        attempts = kwargs["attempts_dir"]
        action = behaviors.get(prompt_name)
        if action is None:
            raise AssertionError(f"unexpected prompt {prompt_name}")
        if callable(action):
            return action(attempts)
        return int(action)

    return log, fake_spawn


# ---------------------------------------------------------------------
# Default (single phase) baseline — TWO_PHASE off
# ---------------------------------------------------------------------

def test_two_phase_off_uses_single_builder_prompt(
    tmp_path: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ASTERISM_BUILDER_TWO_PHASE, run_builder fires exactly one
    spawn_llm against builder.md (the legacy combined prompt)."""
    monkeypatch.delenv("ASTERISM_BUILDER_TWO_PHASE", raising=False)

    def write_both(attempts: Path) -> int:
        (attempts / "PROPOSAL.md").write_text("strat", encoding="utf-8")
        (attempts / "patch.lean").write_text(
            "import Mathlib\ntheorem main_t : True := by trivial\n",
            encoding="utf-8",
        )
        return 0

    log, fake = _make_fake_spawn({"builder.md": write_both})
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _patch_lake_ok(monkeypatch)

    gid, mfst, ws = _seed(tmp_path, conn)
    result = pipeline.run_builder(
        conn, goal_id=gid, workspace=ws, mfst=mfst, pipeline_id="pid-single",
    )
    assert result.outcome == "proved", result.failure_detail
    assert [c["prompt_path"].name for c in log] == ["builder.md"]


# ---------------------------------------------------------------------
# Two-phase happy path
# ---------------------------------------------------------------------

def test_two_phase_on_calls_phase_a_then_phase_b(
    tmp_path: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTERISM_BUILDER_TWO_PHASE", "1")

    def phase_a(attempts: Path) -> int:
        (attempts / "PROPOSAL.md").write_text(
            "use Nat.foo; rewrite then trivial", encoding="utf-8")
        return 0

    def phase_b(attempts: Path) -> int:
        # Sanity check: Phase B can read PROPOSAL.md from the same dir.
        assert (attempts / "PROPOSAL.md").read_text(encoding="utf-8").strip()
        (attempts / "patch.lean").write_text(
            "import Mathlib\ntheorem main_t : True := by trivial\n",
            encoding="utf-8")
        return 0

    log, fake = _make_fake_spawn({
        "builder_phase_a_proposal.md": phase_a,
        "builder_phase_b_patch.md": phase_b,
    })
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _patch_lake_ok(monkeypatch)

    gid, mfst, ws = _seed(tmp_path, conn)
    result = pipeline.run_builder(
        conn, goal_id=gid, workspace=ws, mfst=mfst, pipeline_id="pid-2p-ok",
    )
    assert result.outcome == "proved", result.failure_detail
    assert [c["prompt_path"].name for c in log] == [
        "builder_phase_a_proposal.md",
        "builder_phase_b_patch.md",
    ]


def test_two_phase_phase_b_uses_cold_call_no_session(
    tmp_path: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase A receives a session_id (F33 same-session); Phase B always
    cold so claude / gemini paths agree (PROPOSAL.md sits on disk)."""
    monkeypatch.setenv("ASTERISM_BUILDER_TWO_PHASE", "1")

    def phase_a(d: Path) -> int:
        (d / "PROPOSAL.md").write_text("s", encoding="utf-8")
        return 0

    def phase_b(d: Path) -> int:
        (d / "patch.lean").write_text(
            "import Mathlib\ntheorem main_t : True := by trivial\n",
            encoding="utf-8")
        return 0

    log, fake = _make_fake_spawn({
        "builder_phase_a_proposal.md": phase_a,
        "builder_phase_b_patch.md": phase_b,
    })
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _patch_lake_ok(monkeypatch)

    gid, mfst, ws = _seed(tmp_path, conn)
    pipeline.run_builder(
        conn, goal_id=gid, workspace=ws, mfst=mfst, pipeline_id="pid-2p-cold",
    )
    assert log[0]["session_id"] is not None  # Phase A: F33 active
    assert log[0]["is_retry"] is False
    assert log[1]["session_id"] is None       # Phase B: cold ephemeral
    assert log[1]["is_retry"] is False
    assert log[1]["retry_context"] is None


# ---------------------------------------------------------------------
# Failure modes specific to two-phase
# ---------------------------------------------------------------------

def test_two_phase_phase_a_no_proposal_fails_early(
    tmp_path: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase A returns rc=0 but writes no PROPOSAL.md → fail without
    spawning Phase B (saves a wasted call). failure_reason is
    `phase_a_no_proposal` so the dead_attempt is auditable."""
    monkeypatch.setenv("ASTERISM_BUILDER_TWO_PHASE", "1")

    log, fake = _make_fake_spawn({
        "builder_phase_a_proposal.md": lambda d: 0,  # no file written
    })
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _patch_lake_ok(monkeypatch)

    gid, mfst, ws = _seed(tmp_path, conn)
    result = pipeline.run_builder(
        conn, goal_id=gid, workspace=ws, mfst=mfst, pipeline_id="pid-2p-noprop",
    )
    assert result.outcome == "failed"
    assert result.failure_reason == "phase_a_no_proposal"
    assert len(log) == 1  # Phase B never reached


def test_two_phase_phase_b_failure_preserves_proposal(
    tmp_path: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase B fails (rc!=0) → result.proposal_md carries Phase A's
    output so the dead_attempt record retains the strategy reasoning."""
    monkeypatch.setenv("ASTERISM_BUILDER_TWO_PHASE", "1")

    PROPOSAL_TEXT = "Phase A: chain Nat.dvd_iff with prime_dvd_one"

    def phase_a(d: Path) -> int:
        (d / "PROPOSAL.md").write_text(PROPOSAL_TEXT, encoding="utf-8")
        return 0

    _, fake = _make_fake_spawn({
        "builder_phase_a_proposal.md": phase_a,
        "builder_phase_b_patch.md": 1,  # rc=1, no file written
    })
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _patch_lake_ok(monkeypatch)

    gid, mfst, ws = _seed(tmp_path, conn)
    result = pipeline.run_builder(
        conn, goal_id=gid, workspace=ws, mfst=mfst, pipeline_id="pid-2p-bfail",
    )
    assert result.outcome == "failed"
    assert "phase_b" in (result.failure_detail or "")
    assert PROPOSAL_TEXT in (result.proposal_md or "")


def test_two_phase_phase_a_blank_proposal_treated_as_missing(
    tmp_path: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A whitespace-only PROPOSAL.md must not be accepted as Phase A
    output — Phase B has no real strategy to follow."""
    monkeypatch.setenv("ASTERISM_BUILDER_TWO_PHASE", "1")

    def blank_proposal(d: Path) -> int:
        (d / "PROPOSAL.md").write_text("   \n  \t\n", encoding="utf-8")
        return 0

    log, fake = _make_fake_spawn({
        "builder_phase_a_proposal.md": blank_proposal,
    })
    monkeypatch.setattr(agent, "spawn_llm", fake)

    gid, mfst, ws = _seed(tmp_path, conn)
    result = pipeline.run_builder(
        conn, goal_id=gid, workspace=ws, mfst=mfst, pipeline_id="pid-2p-blank",
    )
    assert result.outcome == "failed"
    assert result.failure_reason == "phase_a_no_proposal"
    assert len(log) == 1
