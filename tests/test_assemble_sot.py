"""Structural SoT pin for `state.assemble` (task #5 Step A): the gateway's
validate-side and the pipeline's commit-side must use the SAME objects for
every shared line-scan regex and the framework-import injection — identity,
not equality, so a "helpful" local re-definition on either side trips here
instead of resurrecting the hand-mirrored `_GW_*` drift class.
"""
from __future__ import annotations

from pathlib import Path

from Tooling.state import assemble


def test_pipeline_names_are_assemble_objects() -> None:
    from Tooling import pipeline
    from Tooling.pipeline import _cite_gate, forward
    assert forward.SLUG_RE is assemble.SLUG_RE
    assert forward.SLUG_MAX_LEN is assemble.SLUG_MAX_LEN
    assert forward._DECL_HEAD_RE is assemble.DECL_HEAD_RE
    assert _cite_gate._PROBLEM_IMPORT_RE is assemble.PROBLEM_IMPORT_RE
    assert pipeline._SORRY_STUB_RE is assemble.SORRY_STUB_RE


def test_gateway_names_are_assemble_objects() -> None:
    from Tooling.lsp import gateway
    assert gateway._GW_PROBLEM_IMPORT_RE is assemble.PROBLEM_IMPORT_RE
    assert gateway._GW_SLUG_RE is assemble.SLUG_RE
    assert gateway._GW_DECL_HEAD_RE is assemble.DECL_HEAD_RE
    assert gateway._GW_SORRY_STUB_RE is assemble.SORRY_STUB_RE
    assert gateway._GW_THEOREM_RE is assemble.THEOREM_LINE_RE


def test_import_injection_identical_both_sides(tmp_path: Path) -> None:
    """validate's `_ensure_imports` and commit's `_ensure_imports_subgoal`
    must produce byte-identical output — both delegate to
    `assemble.ensure_framework_imports`."""
    from Tooling.lsp import gateway
    from Tooling.pipeline import backward
    (tmp_path / "Problems" / "p").mkdir(parents=True)
    (tmp_path / "Problems" / "p" / "Defs.lean").write_text(
        "def marker : Nat := 0\n", encoding="utf-8")
    for content in (
        "theorem t : True := trivial\n",                     # both missing
        "import Mathlib\ntheorem t : True := trivial\n",     # Defs missing
        "import Mathlib\nimport Problems.p.Defs\nx\n",       # nothing missing
    ):
        via_commit = backward._ensure_imports_subgoal(
            content, problem="p", workspace=tmp_path)
        via_validate = gateway._ensure_imports(content, "p", tmp_path)
        assert via_commit == via_validate
        assert via_commit == assemble.ensure_framework_imports(
            content, problem="p", workspace=tmp_path)
