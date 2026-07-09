"""Fixture-based tests for the PutnamBench adapter — no clone needed.

Run: python -m pytest Benchmarks/putnambench/test_adapter.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Benchmarks/ dirs are deliberately not packages; load by path.
_spec = importlib.util.spec_from_file_location(
    "putnam_adapter", Path(__file__).parent / "adapter.py")
adapter = importlib.util.module_from_spec(_spec)
sys.modules["putnam_adapter"] = adapter
_spec.loader.exec_module(adapter)


SOLUTION_FILE = """import Mathlib

open MeasureTheory Set

abbrev putnam_1999_a1_solution : Set ℝ := sorry
-- {x | 0 < x}
/--
Find all $x$ such that something holds.
-/
theorem putnam_1999_a1
(f : ℝ → ℝ)
(hf : ∀ x, f x = x)
: {x : ℝ | f x > 0} = putnam_1999_a1_solution :=
sorry
"""

PROOF_ONLY_FILE = """import Mathlib

/--
Show that $1 + 1 = 2$.
-/
theorem putnam_2000_b2 : 1 + 1 = 2 :=
sorry
"""

AUX_DEF_FILE = """import Mathlib

open Filter

abbrev putnam_1997_b5_solution : ℕ := sorry
-- 2
def tetration : ℕ → ℕ → ℕ
  | _, 0 => 1
  | b, (m + 1) => b^(tetration b m)
/--
Docstring here.
-/
theorem putnam_1997_b5 (n : ℕ) (hn : n ≥ 2) :
  tetration 2 n = putnam_1997_b5_solution :=
sorry
"""

# `let x := e` inside the statement must not truncate the signature.
INTERNAL_ASSIGN_FILE = """import Mathlib

/--
Doc.
-/
theorem putnam_1969_b4 : ∀ n : ℕ, let m := n + 1; m > n :=
sorry
"""

STRAY_COMMENT_FILE = """import Mathlib

--Note: The original problem asks to exhibit a function.
/--
Doc.
-/
theorem putnam_1962_b2 : True :=
sorry
"""


def _parse(tmp_path: Path, text: str, name: str) -> "adapter.ProblemSpec":
    p = tmp_path / f"{name}.lean"
    p.write_text(text, encoding="utf-8")
    return adapter.parse_problem_file(p)


def test_solution_abbrev_substituted(tmp_path: Path) -> None:
    spec = _parse(tmp_path, SOLUTION_FILE, "putnam_1999_a1")
    assert spec.name == "putnam_1999_a1"
    assert spec.solution_name == "putnam_1999_a1_solution"
    assert spec.decls == [
        "noncomputable abbrev putnam_1999_a1_solution : Set ℝ "
        ":= {x | 0 < x}"]
    assert spec.opens == ["MeasureTheory Set"]
    assert spec.informal.startswith("Find all $x$")
    # Upstream line structure preserved; top-level `:` → `,` + newline.
    assert spec.signature == (
        "∀ (f : ℝ → ℝ)\n(hf : ∀ x, f x = x),\n"
        "{x : ℝ | f x > 0} = putnam_1999_a1_solution")


def test_proof_only_no_defs(tmp_path: Path) -> None:
    spec = _parse(tmp_path, PROOF_ONLY_FILE, "putnam_2000_b2")
    assert spec.solution_name == ""
    assert spec.decls == []
    assert spec.signature == "1 + 1 = 2"  # nullary → bare conclusion


def test_multiline_aux_def_verbatim(tmp_path: Path) -> None:
    spec = _parse(tmp_path, AUX_DEF_FILE, "putnam_1997_b5")
    assert len(spec.decls) == 2
    assert spec.decls[1].startswith("def tetration : ℕ → ℕ → ℕ")
    assert "| b, (m + 1) => b^(tetration b m)" in spec.decls[1]


def test_internal_assign_does_not_truncate(tmp_path: Path) -> None:
    spec = _parse(tmp_path, INTERNAL_ASSIGN_FILE, "putnam_1969_b4")
    assert "let m := n + 1; m > n" in spec.signature


# putnam_1965_b4 regression: a `let` binding inside the statement is
# terminated by the LINE BREAK — collapsing to one line is a parse
# error. Line structure must survive normalization.
LET_STATEMENT_FILE = """import Mathlib

/--
Doc.
-/
theorem putnam_1965_b4
    (n : ℕ)
    (hn : 0 < n) :
    let m := n + 1
    m > n :=
  sorry
"""


def test_let_line_break_preserved(tmp_path: Path) -> None:
    spec = _parse(tmp_path, LET_STATEMENT_FILE, "putnam_1965_b4")
    assert spec.signature == (
        "∀ (n : ℕ)\n    (hn : 0 < n),\nlet m := n + 1\n    m > n")


# putnam_1964_b4 regression: inline `--` comments between binders must
# be stripped, not merged into the statement text.
COMMENTED_SIG_FILE = """import Mathlib

/--
Doc.
-/
theorem putnam_1964_b4
    {n : ℕ} (hn : 0 < n)
    -- `C` is a collection of circles
    (C : Fin n → ℕ)
    : C = C :=
  sorry
"""


def test_signature_comments_stripped(tmp_path: Path) -> None:
    spec = _parse(tmp_path, COMMENTED_SIG_FILE, "putnam_1964_b4")
    assert "--" not in spec.signature
    assert "collection" not in spec.signature
    assert spec.signature.endswith(",\nC = C")


def test_stray_note_comment_skipped(tmp_path: Path) -> None:
    spec = _parse(tmp_path, STRAY_COMMENT_FILE, "putnam_1962_b2")
    assert spec.signature == "True"


def test_abbrev_without_answer_comment_fails_loud(tmp_path: Path) -> None:
    broken = SOLUTION_FILE.replace("-- {x | 0 < x}\n", "")
    with pytest.raises(adapter.AdapterError, match="answer comment"):
        _parse(tmp_path, broken, "putnam_1999_a1")


def test_emit_three_files(tmp_path: Path) -> None:
    spec = _parse(tmp_path, SOLUTION_FILE, "putnam_1999_a1")
    out = tmp_path / "Problems"
    pdir = adapter.emit_problem_dir(spec, out, upstream_commit="abc1234")
    assert pdir == out / "Putnam" / "putnam_1999_a1"

    root = (pdir / "Root.lean").read_text(encoding="utf-8")
    assert "import Problems.Putnam.putnam_1999_a1.Defs" in root
    assert "open MeasureTheory Set" in root
    assert "namespace Problems.Putnam.putnam_1999_a1" in root
    assert f"theorem main : {spec.signature} := by sorry" in root
    assert "linter.style.longLine false" in root

    defs = (pdir / "Defs.lean").read_text(encoding="utf-8")
    assert "noncomputable abbrev putnam_1999_a1_solution" in defs
    assert "import Problems" not in defs

    mfst = (pdir / "Manifest.md").read_text(encoding="utf-8")
    assert "problem: Putnam.putnam_1999_a1" in mfst
    assert "library: false" in mfst
    assert "Find all $x$" in mfst
    assert "Putnam 1999 A1" in mfst
    assert "abc1234" in mfst
    assert "OFFICIAL" in mfst          # solutions-replaced note
    assert "AttemptDisproof" in mfst   # falsity routing note


def test_emit_proof_only_manifest_note(tmp_path: Path) -> None:
    spec = _parse(tmp_path, PROOF_ONLY_FILE, "putnam_2000_b2")
    pdir = adapter.emit_problem_dir(spec, tmp_path / "Problems")
    mfst = (pdir / "Manifest.md").read_text(encoding="utf-8")
    assert "pure proof task" in mfst


def test_set_option_replayed(tmp_path: Path) -> None:
    text = SOLUTION_FILE.replace(
        "open MeasureTheory Set\n",
        "open MeasureTheory Set\n\nset_option synthInstance.maxSize 127\n")
    spec = _parse(tmp_path, text, "putnam_1999_a1")
    pdir = adapter.emit_problem_dir(spec, tmp_path / "Problems")
    for fname in ("Root.lean", "Defs.lean"):
        assert "set_option synthInstance.maxSize 127" in (
            pdir / fname).read_text(encoding="utf-8")


# Full-corpus canary: only runs when the upstream clone is present
# (gitignored `_ext/`); CI skips it.
_CORPUS = Path(__file__).resolve().parents[2] / \
    "_ext" / "putnambench" / "lean4" / "src"


@pytest.mark.skipif(not _CORPUS.is_dir(), reason="no upstream clone")
def test_full_corpus_parses() -> None:
    files = sorted(_CORPUS.glob("*.lean"))
    assert len(files) >= 600
    for p in files:
        spec = adapter.parse_problem_file(p)  # raises on drift
        assert spec.signature and spec.informal
