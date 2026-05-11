"""Tests for the miniF2F adapter. Fixture-based — no real miniF2F clone
needed. Each test synthesizes one or more miniF2F-style .lean files in
tmp_path, runs the adapter, and inspects the emitted Problem dirs.

Lives under `Benchmarks/minif2f/` (not `tests/`) because this is a
benchmark driver, not Asterism framework code. Run via:

    python -m pytest Benchmarks/minif2f/test_adapter.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load adapter.py as a module — sibling file in this directory, not a
# package member, so we use importlib instead of `from X import Y`.
_ADAPTER_PATH = Path(__file__).parent / "adapter.py"
_spec = importlib.util.spec_from_file_location(
    "minif2f_adapter", _ADAPTER_PATH)
minif2f = importlib.util.module_from_spec(_spec)
sys.modules["minif2f_adapter"] = minif2f
_spec.loader.exec_module(minif2f)


# ---------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------

_ALGEBRA_PROBLEM = """\
import MiniF2F.Minif2fImport
open BigOperators Real Nat Topology

theorem algebra_amgm_faxinrrp2msqrt2le2mxm1div2x
  (x : ℝ)
  (h₀ : 0 < x) :
  x + 1 / (2 * x) ≥ Real.sqrt 2 := by
  sorry
"""

_NUMBERTHEORY_PROBLEM = """\
import MiniF2F.Minif2fImport
open BigOperators Real Nat Topology

theorem mathd_numbertheory_185 (n : ℕ) (h : 5 * n % 17 = 8) :
  n % 17 = 5 := by
  sorry
"""

_MULTI_THEOREM = """\
import MiniF2F.Minif2fImport
open Real

theorem ex_first (a : ℝ) : a + 0 = a := by sorry

theorem ex_second (b : ℝ) : b * 1 = b := by sorry
"""

_NO_THEOREM = """\
-- Helper module, no theorems
import Mathlib

def foo (x : ℕ) : ℕ := x + 1
"""

# Real-world miniF2F (yangky11 fork) format
_REAL_MINIF2F = """\
import Mathlib

set_option maxHeartbeats 0

open BigOperators Real Nat Topology Rat

theorem aime_1983_p9 (x : ℝ) (h₀ : 0 < x ∧ x < Real.pi) :
  12 ≤ (9 * (x ^ 2 * Real.sin x ^ 2) + 4) / (x * Real.sin x) := by sorry
"""


def _write(source_dir: Path, name: str, body: str) -> Path:
    p = source_dir / name
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------
# parse_problem_file
# ---------------------------------------------------------------------

def test_parse_single_theorem_extracts_name_and_signature(tmp_path: Path):
    src = tmp_path / "algebra.lean"
    src.write_text(_ALGEBRA_PROBLEM, encoding="utf-8")
    specs = minif2f.parse_problem_file(src)
    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "algebra_amgm_faxinrrp2msqrt2le2mxm1div2x"
    assert "(x : ℝ)" in spec.signature
    assert "Real.sqrt 2" in spec.signature
    assert ":=" not in spec.signature  # sig captures up to but not incl `:=`


def test_parse_replays_open_clauses(tmp_path: Path):
    src = tmp_path / "p.lean"
    src.write_text(_ALGEBRA_PROBLEM, encoding="utf-8")
    specs = minif2f.parse_problem_file(src)
    assert specs[0].opens == ["BigOperators Real Nat Topology"]


def test_parse_multi_theorem_returns_all(tmp_path: Path):
    src = tmp_path / "multi.lean"
    src.write_text(_MULTI_THEOREM, encoding="utf-8")
    specs = minif2f.parse_problem_file(src)
    names = [s.name for s in specs]
    assert names == ["ex_first", "ex_second"]


def test_parse_no_theorem_returns_empty(tmp_path: Path):
    src = tmp_path / "helper.lean"
    src.write_text(_NO_THEOREM, encoding="utf-8")
    assert minif2f.parse_problem_file(src) == []


def test_parse_captures_set_option_directives(tmp_path: Path):
    """miniF2F (yangky11 fork) sets `maxHeartbeats 0` per problem so
    Lean elaborator allows unbounded time. Without capturing this,
    Asterism-generated proofs would inherit Mathlib's default heartbeat
    cap and hit `(maxHeartbeats exceeded)` on heavy expressions."""
    src = tmp_path / "p.lean"
    src.write_text(_REAL_MINIF2F, encoding="utf-8")
    specs = minif2f.parse_problem_file(src)
    assert len(specs) == 1
    assert specs[0].set_options == ["maxHeartbeats 0"]
    assert specs[0].opens == ["BigOperators Real Nat Topology Rat"]


def test_emit_defs_replays_set_options(tmp_path: Path):
    src = tmp_path / "p.lean"
    src.write_text(_REAL_MINIF2F, encoding="utf-8")
    spec = minif2f.parse_problem_file(src)[0]
    out = tmp_path / "Problems"
    pdir = minif2f.emit_problem_dir(spec, out)
    defs = (pdir / "Defs.lean").read_text(encoding="utf-8")
    assert "set_option maxHeartbeats 0" in defs


# ---------------------------------------------------------------------
# emit_problem_dir
# ---------------------------------------------------------------------

def test_emit_problem_dir_writes_manifest_and_defs(tmp_path: Path):
    src = tmp_path / "src.lean"
    src.write_text(_ALGEBRA_PROBLEM, encoding="utf-8")
    spec = minif2f.parse_problem_file(src)[0]

    out = tmp_path / "Problems"
    pdir = minif2f.emit_problem_dir(spec, out)
    assert pdir.exists()
    assert pdir.name.startswith("minif2f_")

    manifest_text = (pdir / "Manifest.md").read_text(encoding="utf-8")
    assert "## Statement" in manifest_text
    assert "Real.sqrt 2" in manifest_text
    assert "## Entry kind\nBuilder" in manifest_text
    assert "axioms_whitelist:" in manifest_text
    # Prefix ensures coexistence with hand-authored problems
    assert f"problem: minif2f_{spec.name}" in manifest_text

    defs_text = (pdir / "Defs.lean").read_text(encoding="utf-8")
    assert "import Mathlib" in defs_text
    assert "open BigOperators Real Nat Topology" in defs_text
    assert f"namespace Problems.{spec.slug}" in defs_text


def test_emit_idempotent_on_rerun(tmp_path: Path):
    """Re-running emit on the same spec overwrites cleanly — operators
    can re-import without an explicit reset (won't lose proofs/ which
    asterism reset would have cleaned)."""
    src = tmp_path / "src.lean"
    src.write_text(_ALGEBRA_PROBLEM, encoding="utf-8")
    spec = minif2f.parse_problem_file(src)[0]
    out = tmp_path / "Problems"
    minif2f.emit_problem_dir(spec, out)
    # Drop a fake proofs/ to verify it's untouched on re-emit
    (out / spec.slug / "proofs").mkdir()
    (out / spec.slug / "proofs" / "marker.lean").write_text("--keep")
    minif2f.emit_problem_dir(spec, out)
    assert (out / spec.slug / "proofs" / "marker.lean").exists()


# ---------------------------------------------------------------------
# import_minif2f
# ---------------------------------------------------------------------

def test_import_walks_source_dir_emits_all(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "algebra.lean", _ALGEBRA_PROBLEM)
    _write(src, "numbertheory.lean", _NUMBERTHEORY_PROBLEM)
    _write(src, "multi.lean", _MULTI_THEOREM)
    _write(src, "helper.lean", _NO_THEOREM)
    # Asserted miniF2F-internal helper — should be skipped by filename
    _write(src, "Minif2fImport.lean", "import Mathlib\n")

    out = tmp_path / "Problems"
    result = minif2f.import_minif2f(src, out)

    # 1 + 1 + 2 + 0 = 4 problems imported
    assert len(result.imported) == 4
    slugs = set(result.imported)
    assert "minif2f_algebra_amgm_faxinrrp2msqrt2le2mxm1div2x" in slugs
    assert "minif2f_mathd_numbertheory_185" in slugs
    assert "minif2f_ex_first" in slugs
    assert "minif2f_ex_second" in slugs

    # helper file: no theorem found
    assert "helper.lean" in result.skipped_no_theorem
    # Minif2fImport.lean: filename-blacklisted, not even attempted
    assert "Minif2fImport.lean" not in result.skipped_no_theorem


def test_import_filter_matches_original_name(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "a.lean", _ALGEBRA_PROBLEM)
    _write(src, "n.lean", _NUMBERTHEORY_PROBLEM)
    out = tmp_path / "Problems"

    result = minif2f.import_minif2f(src, out, prefix_filter="algebra_")
    assert len(result.imported) == 1
    assert result.imported[0].endswith("algebra_amgm_faxinrrp2msqrt2le2mxm1div2x")
    assert "mathd_numbertheory_185" in result.skipped_filter


def test_import_limit_caps_count(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "multi.lean", _MULTI_THEOREM)
    _write(src, "a.lean", _ALGEBRA_PROBLEM)
    out = tmp_path / "Problems"

    result = minif2f.import_minif2f(src, out, limit=2)
    assert len(result.imported) == 2


# ---------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------

def test_cli_main_returns_0_on_success(tmp_path: Path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "algebra.lean", _ALGEBRA_PROBLEM)
    out = tmp_path / "Problems"

    rc = minif2f.main([
        "--source", str(src),
        "--output", str(out),
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Imported 1 problem" in captured.out
    assert (out / "minif2f_algebra_amgm_faxinrrp2msqrt2le2mxm1div2x").exists()


def test_cli_main_fails_on_missing_source(tmp_path: Path, capsys):
    rc = minif2f.main([
        "--source", str(tmp_path / "nope"),
        "--output", str(tmp_path / "Problems"),
    ])
    assert rc == 1
    captured = capsys.readouterr()
    assert "FAIL" in captured.err
