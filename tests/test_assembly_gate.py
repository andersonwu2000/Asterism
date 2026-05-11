"""Assembly gate — verify `:= by sorry` placeholders are detected
before sub-goal dispatch.

See `Tooling/pipeline/_assembly.py` for the design rationale.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.pipeline._assembly import (
    assembly_gate_check_sorry,
    strip_lean_comments,
)


# -------- strip_lean_comments ---------------------------------------


def test_strip_line_comments() -> None:
    src = (
        "import Mathlib\n"
        "-- this is a comment with sorry inside\n"
        "theorem foo : True := trivial\n"
    )
    out = strip_lean_comments(src)
    assert "sorry" not in out
    assert "trivial" in out


def test_strip_block_comments() -> None:
    src = (
        "import Mathlib\n"
        "/- a block\n"
        "   comment with sorry across\n"
        "   multiple lines -/\n"
        "theorem foo : True := trivial\n"
    )
    out = strip_lean_comments(src)
    assert "sorry" not in out
    assert "trivial" in out


def test_strip_doc_comments() -> None:
    src = (
        "/-- doc comment mentioning sorry -/\n"
        "theorem foo : True := trivial\n"
    )
    out = strip_lean_comments(src)
    assert "sorry" not in out


def test_strip_preserves_code() -> None:
    src = (
        "theorem bar (x : ℕ) : x + 0 = x := by\n"
        "  -- closes by ring\n"
        "  ring\n"
    )
    out = strip_lean_comments(src)
    # Pre-strip the trailing whitespace from the stripped line.
    assert "theorem bar" in out
    assert "ring" in out


# -------- assembly_gate_check_sorry ---------------------------------


def test_gate_passes_clean_strategy(tmp_path: Path) -> None:
    """Strategy with real sub-goal references passes."""
    f = tmp_path / "_strategy_s100.lean"
    f.write_text(
        "import Mathlib\n"
        "import Problems.p.proofs.L_lemma_a\n"
        "import Problems.p.proofs.L_lemma_b\n"
        "namespace Problems.p\n"
        "theorem s100 : True := by\n"
        "  have h_a := lemma_a\n"
        "  have h_b := lemma_b h_a\n"
        "  exact h_b\n"
        "end Problems.p\n",
        encoding="utf-8",
    )
    ok, msg = assembly_gate_check_sorry(f)
    assert ok, f"expected pass, got: {msg}"


def test_gate_rejects_placeholder_sorry(tmp_path: Path) -> None:
    """Strategy with `:= by sorry` in body (agent forgot transcribe) is rejected."""
    f = tmp_path / "_strategy_s101.lean"
    f.write_text(
        "import Mathlib\n"
        "namespace Problems.p\n"
        "theorem s101 : True := by\n"
        "  have h_a : True := by sorry\n"  # placeholder left in
        "  exact h_a\n"
        "end Problems.p\n",
        encoding="utf-8",
    )
    ok, msg = assembly_gate_check_sorry(f)
    assert not ok
    assert "sorry" in msg
    assert f.name in msg


def test_gate_rejects_bare_sorry(tmp_path: Path) -> None:
    """`:= sorry` (term-mode sorry, no `by`) also caught."""
    f = tmp_path / "_strategy_s102.lean"
    f.write_text(
        "import Mathlib\n"
        "namespace Problems.p\n"
        "theorem s102 : True := sorry\n"
        "end Problems.p\n",
        encoding="utf-8",
    )
    ok, _ = assembly_gate_check_sorry(f)
    assert not ok


def test_gate_ignores_sorry_in_comments(tmp_path: Path) -> None:
    """Annotation comments mentioning `sorry` are fine."""
    f = tmp_path / "_strategy_s103.lean"
    f.write_text(
        "import Mathlib\n"
        "namespace Problems.p\n"
        "-- This strategy avoids the sorry-placeholder approach by\n"
        "-- directly invoking lemma_a's :=, not by sorry'ing it.\n"
        "theorem s103 : True := by\n"
        "  have h_a := lemma_a\n"
        "  exact h_a\n"
        "end Problems.p\n",
        encoding="utf-8",
    )
    ok, msg = assembly_gate_check_sorry(f)
    assert ok, f"expected pass (sorry only in comments), got: {msg}"


def test_gate_ignores_sorry_in_block_comments(tmp_path: Path) -> None:
    f = tmp_path / "_strategy_s104.lean"
    f.write_text(
        "import Mathlib\n"
        "namespace Problems.p\n"
        "/-\n"
        "  Rationale: we chose not to leave sorry placeholders\n"
        "  in the strategy body to maintain axiom hygiene.\n"
        "-/\n"
        "theorem s104 : True := by\n"
        "  exact trivial\n"
        "end Problems.p\n",
        encoding="utf-8",
    )
    ok, msg = assembly_gate_check_sorry(f)
    assert ok, f"expected pass, got: {msg}"


def test_gate_catches_partial_transcription(tmp_path: Path) -> None:
    """Agent transcribed h_a but forgot h_b (mixed case)."""
    f = tmp_path / "_strategy_s105.lean"
    f.write_text(
        "import Mathlib\n"
        "namespace Problems.p\n"
        "theorem s105 : True := by\n"
        "  have h_a := lemma_a\n"
        "  have h_b : True := by sorry\n"  # left as placeholder
        "  exact h_b\n"
        "end Problems.p\n",
        encoding="utf-8",
    )
    ok, _ = assembly_gate_check_sorry(f)
    assert not ok


def test_gate_reports_filename(tmp_path: Path) -> None:
    """Error message should name the offending file for diagnostics."""
    f = tmp_path / "_strategy_s106.lean"
    f.write_text(
        "theorem s106 : True := by sorry\n", encoding="utf-8")
    ok, msg = assembly_gate_check_sorry(f)
    assert not ok
    assert "_strategy_s106.lean" in msg


def test_gate_handles_missing_file(tmp_path: Path) -> None:
    ok, msg = assembly_gate_check_sorry(tmp_path / "does_not_exist.lean")
    assert not ok
    assert "cannot read" in msg
