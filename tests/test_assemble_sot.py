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


def test_decl_head_matches_inductive() -> None:
    """v19 (Forward inductive support): both sides of the shared head
    matcher accept `inductive`, with the same modifier/attribute
    tolerance as the other kinds."""
    m = assemble.DECL_HEAD_RE.search(
        "inductive provable_formula where\n  | ax : provable_formula")
    assert m is not None
    assert m.group(1) == "inductive"
    assert m.group(2) == "provable_formula"
    m = assemble.DECL_HEAD_RE.search(
        "@[simp] private inductive step_rel : Nat → Nat → Prop where")
    assert m is not None and m.group(1) == "inductive"
    # v20 — named instances (anonymous heads deliberately don't match;
    # forward's parse gate turns those into a targeted error).
    m = assemble.DECL_HEAD_RE.search(
        "noncomputable instance formula_depth : has_depth prop_formula where")
    assert m is not None
    assert m.group(1) == "instance" and m.group(2) == "formula_depth"
    assert assemble.DECL_HEAD_RE.search(
        "instance : has_depth prop_formula where") is None
    # Bare-prefix building block too (signature_prefix / skeleton path).
    import re
    assert re.search(assemble.DECL_KIND_RE_SRC + "foo",
                     "inductive foo : Type where") is not None


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


# ---------------------------------------------------------------------
# assemble_for_commit (Step B) — one normalization rule for every commit
# path: framework imports + Defs opens + carried patch opens + proved-
# sibling imports, all idempotent.
# ---------------------------------------------------------------------

def _mk_problem(tmp_path: Path, defs: str = "def marker : Nat := 0\n"):
    (tmp_path / "Problems" / "p").mkdir(parents=True)
    (tmp_path / "Problems" / "p" / "Defs.lean").write_text(
        defs, encoding="utf-8")


def test_assemble_for_commit_carries_patch_opens(tmp_path: Path) -> None:
    _mk_problem(tmp_path)
    patch = ("import Mathlib\nopen scoped Topology\nopen MeasureTheory\n"
             "theorem s1 : True := by sorry\n")
    opens = assemble.harvest_open_lines(patch)
    assert opens == ["open scoped Topology", "open MeasureTheory"]
    stub = "theorem sub : True := by sorry\n"
    a = assemble.assemble_for_commit(
        stub, problem="p", workspace=tmp_path, carry_opens=opens)
    assert "open scoped Topology" in a.text
    assert "open MeasureTheory" in a.text
    assert a.text.index("import Mathlib") < a.text.index("open scoped")
    # idempotent: re-assembling the output is a no-op
    again = assemble.assemble_for_commit(
        a.text, problem="p", workspace=tmp_path, carry_opens=opens)
    assert again.text == a.text


def test_assemble_for_commit_injects_proved_sibling_import(tmp_path) -> None:
    import sqlite3
    from Tooling.state import db
    _mk_problem(tmp_path)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, manifest_path, created_at) "
                 "VALUES ('p','',datetime('now'))")
    g = db.insert_goal(conn, problem="p", slug="helper_lemma",
                       lean_path="Problems/p/proofs/L_helper_lemma.lean",
                       statement="True", origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    body = "theorem t : True := helper_lemma trivial\n"
    a = assemble.assemble_for_commit(
        body, problem="p", workspace=tmp_path, conn=conn)
    assert "import Problems.p.proofs.L_helper_lemma" in a.text
    assert a.injected_sibling_imports == ["helper_lemma"]
    # declared slugs excluded (a batch's own new sub-goals)
    b = assemble.assemble_for_commit(
        body, problem="p", workspace=tmp_path, conn=conn,
        declared_slugs={"helper_lemma"})
    assert "import Problems.p.proofs.L_helper_lemma" not in b.text


def test_harvest_open_lines_skips_scoped_in_form() -> None:
    text = "open Foo in\ntheorem t : True := trivial\nopen Bar\n"
    assert assemble.harvest_open_lines(text) == ["open Bar"]
