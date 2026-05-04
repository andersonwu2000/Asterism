"""F55 — partial-output persistence (Tooling/pipeline/_drafts.py).

Each kind in `PARTIAL_PERSIST` (currently backward + builder) carries
its own per-goal draft file. A failed/timed-out spawn's in-flight
output gets persisted so the next spawn's Context.md can surface it
as a starting sketch.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.pipeline import _drafts


def test_persist_writes_backward_proposal(tmp_path: Path) -> None:
    attempts_dir = tmp_path / ".attempts" / "pid-1"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "PROPOSAL.md").write_text(
        "## My partial decomp\n3 sub-goals via Kelly minimiser.",
        encoding="utf-8",
    )
    problem_dir = tmp_path / "Problems" / "sg"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=42,
    )
    assert out is not None
    assert out == problem_dir / ".drafts" / "backward_g42.md"
    body = out.read_text(encoding="utf-8")
    assert "PROPOSAL.md" in body
    assert "Kelly minimiser" in body


def test_persist_writes_builder_patch(tmp_path: Path) -> None:
    attempts_dir = tmp_path / ".attempts" / "pid-2"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "patch.lean").write_text(
        "theorem g : True := by trivial",
        encoding="utf-8",
    )
    problem_dir = tmp_path / "Problems" / "p"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="builder", goal_id=7,
    )
    assert out is not None
    assert out.name == "builder_g7.md"
    assert "patch.lean" in out.read_text(encoding="utf-8")


def test_persist_no_op_when_source_missing(tmp_path: Path) -> None:
    """No PROPOSAL.md in attempts_dir → no draft written. Common case
    when the spawn died very early (sandbox-exploration phase)."""
    attempts_dir = tmp_path / ".attempts" / "pid-empty"
    attempts_dir.mkdir(parents=True)
    problem_dir = tmp_path / "Problems" / "p"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=1,
    )
    assert out is None
    assert not (problem_dir / ".drafts").exists()


def test_persist_no_op_when_attempts_dir_missing(tmp_path: Path) -> None:
    """Wrapper may call persist on early-exit paths (goal_not_found,
    lean_file_missing) before any spawn touched disk → attempts_dir
    doesn't exist. Must not crash."""
    attempts_dir = tmp_path / ".attempts" / "never-created"
    problem_dir = tmp_path / "Problems" / "p"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=1,
    )
    assert out is None
    assert not (problem_dir / ".drafts").exists()


def test_persist_uses_per_kind_budget(tmp_path: Path) -> None:
    """Builder gets a larger budget than Backward — long Lean tactic
    chains shouldn't lose their tail just because Backward's PROPOSAL
    convention sets the same cap."""
    attempts_dir = tmp_path / ".attempts" / "pid-bd"
    attempts_dir.mkdir(parents=True)
    # Content sized between Backward budget (4000) and Builder budget (8000)
    content = "x" * 6000
    (attempts_dir / "patch.lean").write_text(content, encoding="utf-8")
    problem_dir = tmp_path / "Problems" / "p"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="builder", goal_id=1,
    )
    body = out.read_text(encoding="utf-8")
    assert "truncated" not in body  # under Builder's 8000 cap
    # Same content under Backward kind would truncate
    (attempts_dir / "PROPOSAL.md").write_text(content, encoding="utf-8")
    out2 = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=2,
    )
    assert "truncated" in out2.read_text(encoding="utf-8")


def test_persist_no_op_for_unknown_kind(tmp_path: Path) -> None:
    """Kinds not in PARTIAL_PERSIST (e.g. 'verify') → silent no-op so
    pipeline can call this generically."""
    attempts_dir = tmp_path / ".attempts" / "pid-x"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "PROPOSAL.md").write_text("anything", encoding="utf-8")
    problem_dir = tmp_path / "Problems" / "p"
    assert _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="verify", goal_id=1,
    ) is None


def test_persist_truncates_oversize_content(tmp_path: Path) -> None:
    """Long PROPOSAL gets capped at PARTIAL_BUDGET so Context.md stays
    tight when the inlined draft is later surfaced."""
    attempts_dir = tmp_path / ".attempts" / "pid-big"
    attempts_dir.mkdir(parents=True)
    huge = "x" * (_drafts.PARTIAL_BUDGET + 500)
    (attempts_dir / "PROPOSAL.md").write_text(huge, encoding="utf-8")
    problem_dir = tmp_path / "Problems" / "p"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=99,
    )
    body = out.read_text(encoding="utf-8")
    assert "truncated" in body
    assert len(body) < len(huge) + 500  # full original NOT in body


def test_persist_idempotent_overwrite(tmp_path: Path) -> None:
    """Two persist calls in a row → most recent content wins. (Each
    spawn's last draft replaces the prior one; the agent always sees
    the freshest sketch.)"""
    problem_dir = tmp_path / "Problems" / "p"
    for content in ("first try", "second try, better"):
        attempts_dir = tmp_path / ".attempts" / f"pid-{content[:5]}"
        attempts_dir.mkdir(parents=True)
        (attempts_dir / "PROPOSAL.md").write_text(content, encoding="utf-8")
        _drafts.persist_partials(
            attempts_dir=attempts_dir, problem_dir=problem_dir,
            kind="backward", goal_id=1,
        )
    final = _drafts.read_partial(
        problem_dir=problem_dir, kind="backward", goal_id=1)
    assert "second try, better" in final
    assert "first try" not in final


def test_clear_removes_draft(tmp_path: Path) -> None:
    problem_dir = tmp_path / "Problems" / "p"
    attempts_dir = tmp_path / ".attempts" / "pid-1"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "PROPOSAL.md").write_text("draft", encoding="utf-8")
    _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=5,
    )
    assert _drafts.drafts_path(problem_dir, "backward", 5).exists()
    _drafts.clear_partial(
        problem_dir=problem_dir, kind="backward", goal_id=5)
    assert not _drafts.drafts_path(problem_dir, "backward", 5).exists()


def test_clear_no_error_when_missing(tmp_path: Path) -> None:
    """Most pipelines never produce a draft; clear must tolerate that."""
    _drafts.clear_partial(
        problem_dir=tmp_path / "Problems" / "p",
        kind="backward", goal_id=99,
    )  # no exception


def test_per_goal_isolation(tmp_path: Path) -> None:
    """Drafts for different goals don't interfere — drafts_path includes
    the goal id."""
    problem_dir = tmp_path / "Problems" / "p"
    for gid, content in [(1, "g1 draft"), (2, "g2 draft")]:
        attempts_dir = tmp_path / ".attempts" / f"pid-g{gid}"
        attempts_dir.mkdir(parents=True)
        (attempts_dir / "PROPOSAL.md").write_text(content, encoding="utf-8")
        _drafts.persist_partials(
            attempts_dir=attempts_dir, problem_dir=problem_dir,
            kind="backward", goal_id=gid,
        )
    assert "g1 draft" in _drafts.read_partial(
        problem_dir=problem_dir, kind="backward", goal_id=1)
    assert "g2 draft" in _drafts.read_partial(
        problem_dir=problem_dir, kind="backward", goal_id=2)


def test_per_kind_isolation(tmp_path: Path) -> None:
    """Backward and Builder drafts on the same goal don't collide."""
    problem_dir = tmp_path / "Problems" / "p"
    attempts_dir = tmp_path / ".attempts" / "pid-1"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "PROPOSAL.md").write_text("backward draft", encoding="utf-8")
    (attempts_dir / "patch.lean").write_text("builder draft", encoding="utf-8")
    _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=10,
    )
    _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="builder", goal_id=10,
    )
    bk = _drafts.read_partial(
        problem_dir=problem_dir, kind="backward", goal_id=10)
    bd = _drafts.read_partial(
        problem_dir=problem_dir, kind="builder", goal_id=10)
    assert "backward draft" in bk and "builder draft" not in bk
    assert "builder draft" in bd and "backward draft" not in bd
