"""Librarian Gate A — import-closure (M2).

A self-contained Library file imports only Mathlib/Library; importing
Problems.* or a problem Defs is the violation the gate must catch.
"""
from __future__ import annotations

from pathlib import Path

from Tooling.quality.librarian import gates


# ---------------------------------------------------------------------
# parse_imports
# ---------------------------------------------------------------------

def test_parse_plain_and_dotted_imports():
    text = (
        "import Mathlib\n"
        "import Mathlib.Analysis.InnerProductSpace.Spectrum\n"
        "import Library.LinearAlgebra.jordan\n"
        "\n"
        "theorem foo : True := trivial\n"
    )
    assert gates.parse_imports(text) == [
        "Mathlib",
        "Mathlib.Analysis.InnerProductSpace.Spectrum",
        "Library.LinearAlgebra.jordan",
    ]


def test_parse_tolerates_public_import_prefix():
    """Newer mathlib module syntax: `public import Foo`."""
    text = "public import Mathlib.Tactic.Common\nprivate import Mathlib.Data.Nat.Basic\n"
    assert gates.parse_imports(text) == [
        "Mathlib.Tactic.Common", "Mathlib.Data.Nat.Basic",
    ]


def test_parse_ignores_non_import_lines():
    text = "-- import Faux.Comment\nopen Real\ntheorem t : True := trivial\n"
    assert gates.parse_imports(text) == []


# ---------------------------------------------------------------------
# check_import_closure_text
# ---------------------------------------------------------------------

def test_clean_library_file_passes():
    text = (
        "import Mathlib.Analysis.InnerProductSpace.Spectrum\n"
        "import Library.LinearAlgebra.jordan_basis\n"
        "theorem t : True := trivial\n"
    )
    res = gates.check_import_closure_text(text)
    assert res.ok
    assert res.issues == []
    assert bool(res) is True


def test_problems_import_rejected():
    text = (
        "import Mathlib\n"
        "import Problems.LinearAlgebra.jordan_normal_form.Defs\n"
        "theorem t : True := trivial\n"
    )
    res = gates.check_import_closure_text(text)
    assert not res.ok
    assert any("Problems.LinearAlgebra.jordan_normal_form.Defs" in i
               for i in res.issues)


def test_bare_defs_style_import_rejected():
    """A relative/odd import whose root isn't allowed is caught."""
    text = "import Foo.Bar\ntheorem t : True := trivial\n"
    res = gates.check_import_closure_text(text)
    assert not res.ok
    assert any("Foo.Bar" in i for i in res.issues)


def test_init_std_allowed():
    """Init/Std/Batteries/Lean roots are fine (they're below Mathlib)."""
    text = "import Init.Data.List\nimport Batteries.Data.List.Basic\n"
    res = gates.check_import_closure_text(text)
    assert res.ok, res.issues


def test_multiple_violations_all_reported():
    text = (
        "import Mathlib\n"
        "import Problems.A.Defs\n"
        "import Problems.B.proofs.L_x\n"
        "import Library.ok\n"
    )
    res = gates.check_import_closure_text(text)
    assert not res.ok
    assert len(res.issues) == 2  # both Problems imports, not the clean ones


# ---------------------------------------------------------------------
# check_import_closure (on disk, pure-text path)
# ---------------------------------------------------------------------

def test_file_on_disk_clean(tmp_path: Path):
    f = tmp_path / "good.lean"
    f.write_text("import Mathlib\ntheorem t : True := trivial\n",
                 encoding="utf-8")
    res = gates.check_import_closure(f)
    assert res.ok


def test_file_on_disk_violation(tmp_path: Path):
    f = tmp_path / "bad.lean"
    f.write_text("import Problems.X.Defs\n", encoding="utf-8")
    res = gates.check_import_closure(f)
    assert not res.ok


def test_missing_file_flagged(tmp_path: Path):
    res = gates.check_import_closure(tmp_path / "nope.lean")
    assert not res.ok
    assert any("does not exist" in i for i in res.issues)


# ---------------------------------------------------------------------
# check_dir_import_closure
# ---------------------------------------------------------------------

def test_dir_aggregates_violations(tmp_path: Path):
    (tmp_path / "a.lean").write_text("import Mathlib\n", encoding="utf-8")
    (tmp_path / "b.lean").write_text("import Problems.X.Defs\n",
                                     encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.lean").write_text("import Problems.Y.proofs.L_z\n",
                                encoding="utf-8")
    res = gates.check_dir_import_closure(tmp_path)
    assert not res.ok
    assert len(res.issues) == 2  # b.lean + sub/c.lean


def test_dir_all_clean_passes(tmp_path: Path):
    (tmp_path / "a.lean").write_text(
        "import Mathlib\nimport Library.foo\n", encoding="utf-8")
    res = gates.check_dir_import_closure(tmp_path)
    assert res.ok
