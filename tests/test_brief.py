"""Unit tests for `Tooling/brief.py` — BRIEF.md render + write surface.

The reflection-spawn side of LESSONS.md is tested in
`test_pipeline_reflection.py`. This file covers the framework-managed
half: section assembly, atomic write, multi-problem fan-out.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling import agent  # noqa - establishes import order, see brief.py
from Tooling.state import brief
from Tooling.state.manifest import Manifest


def _mk_problem_dir(tmp_path: Path, name: str = "p") -> Path:
    pdir = tmp_path / "Problems" / name
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def test_render_minimal_manifest_includes_sandbox_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An almost-empty Manifest still renders the always-on Sandbox
    section + the BRIEF auto-render header."""
    # Stub lemma_lookup so the test doesn't shell out to lake.
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {})

    mfst = Manifest(problem="p", statement="True")
    out = brief.render(tmp_path, mfst)
    assert "# p — BRIEF" in out
    assert "## Sandbox" in out
    assert "Reads allowed" in out


def test_render_includes_forbidden_and_strategic_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {})

    mfst = Manifest(
        problem="p", statement="T",
        forbidden_lemmas=["Some.banned_lemma"],
        strategic_notes="Avoid path X. Prefer path Y.",
    )
    out = brief.render(tmp_path, mfst)
    assert "## FORBIDDEN_LEMMAS" in out
    assert "Some.banned_lemma" in out
    assert "## Strategic notes" in out
    assert "Avoid path X" in out


def test_render_no_mathlib_hints_section(tmp_path: Path) -> None:
    """`## Lemma hints` was retired (target-1 pre-search replaces it): a
    Manifest with mathlib hints no longer renders a `## Mathlib lemmas`
    section in BRIEF."""
    mfst = Manifest(
        problem="p", statement="T",
        mathlib_hints=["Nat.factorial — n! is positive"],
    )
    out = brief.render(tmp_path, mfst)
    assert "## Mathlib lemmas" not in out
    assert "Nat.factorial" not in out


def test_write_returns_none_when_problem_dir_missing(
    tmp_path: Path,
) -> None:
    """No `Problems/<p>/` on disk → no write, returns None. Defends
    against test fixtures + mid-reset races without crashing."""
    mfst = Manifest(problem="ghost_problem", statement="T")
    assert brief.write(tmp_path, mfst) is None


def test_write_produces_atomic_brief_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`brief.write` writes BRIEF.md atomically. Final file content
    equals what `render` would have produced."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {})

    pdir = _mk_problem_dir(tmp_path)
    mfst = Manifest(problem="p", statement="T",
                    strategic_notes="hello world")

    target = brief.write(tmp_path, mfst)
    assert target is not None
    assert target == pdir / "BRIEF.md"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == brief.render(tmp_path, mfst)
    # No tmp leftovers in the problem dir.
    leftovers = [p for p in pdir.iterdir() if p.name.startswith("BRIEF.")]
    assert leftovers == [target], f"unexpected files: {leftovers}"


def test_write_for_all_problems_swallows_per_problem_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If one problem's render raises, `write_for_all_problems` logs
    and continues so other problems still get refreshed."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {})

    _mk_problem_dir(tmp_path, "good")
    _mk_problem_dir(tmp_path, "bad")
    good_mfst = Manifest(problem="good", statement="T")
    bad_mfst = Manifest(problem="bad", statement="T")

    # Force `bad` to raise inside write.
    real_write = brief.write
    def faulty_write(workspace, mfst):
        if mfst.problem == "bad":
            raise RuntimeError("simulated render failure")
        return real_write(workspace, mfst)
    monkeypatch.setattr(brief, "write", faulty_write)

    # No exception should escape.
    brief.write_for_all_problems(
        conn=None,  # write_for_all_problems doesn't use conn currently
        workspace=tmp_path,
        manifests={"good": good_mfst, "bad": bad_mfst},
    )

    # `good` still got its BRIEF.md.
    assert (tmp_path / "Problems/good/BRIEF.md").exists()
    # `bad` did not (the faulty write raised).
    assert not (tmp_path / "Problems/bad/BRIEF.md").exists()
