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


# ---------------------------------------------------------------------
# Gate B — root re-derivation (M3)
# `prober` is injected (no live gateway needed); these isolate the
# import-closure + one-liner-budget logic. Real 秒殺 is verified manually
# against the full reshaped Jordan Library.
# ---------------------------------------------------------------------

def _ok_prober(*a, **k):
    return (True, "axioms ok: []")


def _fail_prober(msg):
    def _p(*a, **k):
        return (False, msg)
    return _p


def _bridge(tmp_path: Path, body: str, imports: str = "import Library.X") -> Path:
    p = tmp_path / "Root.lean"
    p.write_text(f"{imports}\ntheorem main := {body}\n", encoding="utf-8")
    return p


def test_gateB_clean_oneliner_passes(tmp_path):
    p = _bridge(tmp_path, "Library.X.keystone h1 h2")
    res = gates.check_root_rederivation(
        p, fq_name="m", module="Root", whitelist=["propext"],
        workspace=tmp_path, prober=_ok_prober)
    assert res.ok, res.issues


def test_gateB_problems_import_rejected(tmp_path):
    """A bridge that still imports Problems is not Defs-free."""
    p = _bridge(tmp_path, "Library.X.keystone",
                imports="import Library.X\nimport Problems.P.Defs")
    res = gates.check_root_rederivation(
        p, fq_name="m", module="Root", whitelist=["propext"],
        workspace=tmp_path, prober=_ok_prober)
    assert not res.ok
    assert any("Problems.P.Defs" in i for i in res.issues)


def test_gateB_axiom_failure_rejected(tmp_path):
    """sorryAx / rogue axiom in the re-derivation chain → reject."""
    p = _bridge(tmp_path, "Library.X.keystone")
    res = gates.check_root_rederivation(
        p, fq_name="m", module="Root", whitelist=["propext"],
        workspace=tmp_path, prober=_fail_prober("rogue axioms: ['sorryAx']"))
    assert not res.ok
    assert any("sorryAx" in i for i in res.issues)


def test_gateB_long_proof_flags_missing_keystone(tmp_path):
    """A long re-derivation body = Library missing a keystone (the
    completeness half of Gate B). Build may pass but the soft signal
    fires."""
    long_body = "by\n  " + " ".join(f"step{i}" for i in range(60))
    p = _bridge(tmp_path, long_body)
    res = gates.check_root_rederivation(
        p, fq_name="m", module="Root", whitelist=["propext"],
        workspace=tmp_path, prober=_ok_prober)
    assert not res.ok
    assert any("missing a keystone" in i for i in res.issues)


def test_gateB_missing_bridge_file(tmp_path):
    res = gates.check_root_rederivation(
        tmp_path / "nope.lean", fq_name="m", module="Root",
        whitelist=["propext"], workspace=tmp_path, prober=_ok_prober)
    assert not res.ok
    assert any("does not exist" in i for i in res.issues)
