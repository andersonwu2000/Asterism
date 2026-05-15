"""manifest.parse — best-effort YAML frontmatter + markdown sections."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.state import manifest


def write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_full_manifest(tmp_path: Path) -> None:
    p = write(tmp_path / "wilson", "Manifest.md", """---
problem: wilson
axioms_whitelist:
  - propext
  - Quot.sound
forbidden_lemmas: [ZMod.wilsons_lemma]
---

# wilson

## Statement
∀ p : ℕ, p.Prime → True

## Entry kind
Backward

## Mathlib hints
- ZMod.val_natCast
- ZMod.val_neg_one

## Strategic notes
free-form text
""")
    m = manifest.parse(p)
    assert m.problem == "wilson"
    assert m.statement == "∀ p : ℕ, p.Prime → True"
    assert m.entry_kind == "Backward"
    assert m.axioms_whitelist == ["propext", "Quot.sound"]
    assert m.forbidden_lemmas == ["ZMod.wilsons_lemma"]
    assert m.mathlib_hints == ["ZMod.val_natCast", "ZMod.val_neg_one"]
    assert "free-form" in m.strategic_notes


def test_missing_entry_kind_defaults_to_backward(tmp_path: Path) -> None:
    """A Manifest without `## Entry kind` falls back to 'Backward'.
    Bias toward decomposition is safer than wasting a Builder spawn on
    an un-annotated root statement."""
    p = write(tmp_path / "p", "Manifest.md", """---
problem: p
---

## Statement
T
""")
    m = manifest.parse(p)
    assert m.entry_kind == "Backward"


def test_unrecognized_entry_kind_falls_back_to_backward(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    p = write(tmp_path / "p", "Manifest.md", """---
problem: p
---

## Statement
T

## Entry kind
Strategist
""")
    m = manifest.parse(p)
    assert m.entry_kind == "Backward"
    err = capsys.readouterr().err
    assert "Entry kind unrecognized" in err


def test_entry_kind_builder(tmp_path: Path) -> None:
    """Explicit 'Builder' is honored — for tiny leaf-shaped problems
    where tactic_try might close the whole thing in one shot."""
    p = write(tmp_path / "p", "Manifest.md", """---
problem: p
---

## Statement
True

## Entry kind
Builder
""")
    m = manifest.parse(p)
    assert m.entry_kind == "Builder"


def test_missing_statement_warn(tmp_path: Path, capsys) -> None:
    p = write(tmp_path / "p", "Manifest.md", """---
problem: p
---
""")
    m = manifest.parse(p)
    assert m.statement == ""
    err = capsys.readouterr().err
    assert "missing ## Statement" in err


def test_problem_falls_back_to_dirname(tmp_path: Path) -> None:
    p = write(tmp_path / "wilson", "Manifest.md", """## Statement
T
""")
    m = manifest.parse(p)
    assert m.problem == "wilson"


def test_inline_list_with_quotes(tmp_path: Path) -> None:
    p = write(tmp_path / "p", "Manifest.md", """---
problem: p
axioms_whitelist: ['propext', "Quot.sound"]
---

## Statement
T
""")
    m = manifest.parse(p)
    assert m.axioms_whitelist == ["propext", "Quot.sound"]


# ---------------------------------------------------------------------
# defs_opens + inject_defs_opens — Defs.lean `open` propagation.
# These helpers exist because Lean 4 `import` does NOT propagate `open`
# clauses across files. Without framework-managed injection, every
# agent-authored .lean would have to remember to replay the opens
# itself — a fragile dependency that caused the four miniF2F-Valid
# mid-run repairs (aime_1997_p11, imo_1965_p1, imo_1966_p4,
# imo_1962_p4) in pilot v5.
# ---------------------------------------------------------------------


def _make_problem_dir(tmp_path: Path, problem: str,
                      defs_opens_lines: list[str]) -> Path:
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True)
    body = "import Mathlib\n\n"
    for line in defs_opens_lines:
        body += f"open {line}\n"
    body += f"\nnamespace Problems.{problem}\n\nend Problems.{problem}\n"
    (pdir / "Defs.lean").write_text(body, encoding="utf-8")
    return pdir


def test_defs_opens_returns_top_level_opens(tmp_path: Path) -> None:
    _make_problem_dir(tmp_path, "wilson",
                      ["BigOperators Real Nat", "Topology"])
    assert manifest.defs_opens(tmp_path, "wilson") == [
        "BigOperators Real Nat", "Topology",
    ]


def test_defs_opens_returns_empty_when_no_defs(tmp_path: Path) -> None:
    (tmp_path / "Problems" / "wilson").mkdir(parents=True)
    assert manifest.defs_opens(tmp_path, "wilson") == []


def test_defs_opens_skips_scope_limited_opens(tmp_path: Path) -> None:
    pdir = tmp_path / "Problems" / "wilson"
    pdir.mkdir(parents=True)
    (pdir / "Defs.lean").write_text(
        "import Mathlib\n\n"
        "open Real\n"           # top-level → propagate
        "open Topology in\n"    # scope-limited → DO NOT propagate
        "theorem helper : True := trivial\n",
        encoding="utf-8",
    )
    assert manifest.defs_opens(tmp_path, "wilson") == ["Real"]


def test_inject_defs_opens_adds_missing_opens(tmp_path: Path) -> None:
    _make_problem_dir(tmp_path, "wilson",
                      ["BigOperators Real Nat Topology Rat"])
    content = (
        "import Mathlib\n"
        "import Problems.wilson.Defs\n\n"
        "namespace Problems.wilson\n\n"
        "theorem foo : True := trivial\n\n"
        "end Problems.wilson\n"
    )
    out = manifest.inject_defs_opens(content, problem="wilson",
                                     workspace=tmp_path)
    assert "open BigOperators Real Nat Topology Rat" in out
    assert "import Problems.wilson.Defs" in out
    # Open block should sit between imports and namespace.
    idx_import = out.index("import Problems.wilson.Defs")
    idx_open = out.index("open BigOperators")
    idx_ns = out.index("namespace Problems.wilson")
    assert idx_import < idx_open < idx_ns


def test_inject_defs_opens_idempotent(tmp_path: Path) -> None:
    _make_problem_dir(tmp_path, "wilson", ["Real"])
    content = (
        "import Mathlib\n\n"
        "open Real\n\n"
        "namespace Problems.wilson\n\n"
        "theorem foo : True := trivial\n"
    )
    out = manifest.inject_defs_opens(content, problem="wilson",
                                     workspace=tmp_path)
    # No new open should be inserted; content unchanged.
    assert out == content
    assert out.count("open Real") == 1


def test_inject_defs_opens_no_defs_returns_unchanged(
    tmp_path: Path,
) -> None:
    (tmp_path / "Problems" / "wilson").mkdir(parents=True)
    content = "import Mathlib\n\nnamespace Problems.wilson\n\nend\n"
    assert manifest.inject_defs_opens(content, problem="wilson",
                                      workspace=tmp_path) == content


def test_inject_defs_opens_preserves_existing_subset(
    tmp_path: Path,
) -> None:
    _make_problem_dir(tmp_path, "wilson",
                      ["BigOperators", "Real Nat Topology"])
    content = (
        "import Mathlib\n\n"
        "open BigOperators\n\n"  # already has this one
        "namespace Problems.wilson\n\n"
        "theorem foo : True := trivial\n"
    )
    out = manifest.inject_defs_opens(content, problem="wilson",
                                     workspace=tmp_path)
    # `BigOperators` already present → no duplicate; `Real Nat Topology` added.
    assert out.count("open BigOperators") == 1
    assert "open Real Nat Topology" in out
