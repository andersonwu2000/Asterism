"""manifest.parse — best-effort YAML frontmatter + markdown sections."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling import manifest


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

## Difficulty
4

## Mathlib hints
- ZMod.val_natCast
- ZMod.val_neg_one

## Strategic notes
free-form text
""")
    m = manifest.parse(p)
    assert m.problem == "wilson"
    assert m.statement == "∀ p : ℕ, p.Prime → True"
    assert m.difficulty == 4
    assert m.axioms_whitelist == ["propext", "Quot.sound"]
    assert m.forbidden_lemmas == ["ZMod.wilsons_lemma"]
    assert m.mathlib_hints == ["ZMod.val_natCast", "ZMod.val_neg_one"]
    assert "free-form" in m.strategic_notes


def test_missing_difficulty_defaults(tmp_path: Path) -> None:
    p = write(tmp_path / "p", "Manifest.md", """---
problem: p
---

## Statement
T
""")
    m = manifest.parse(p)
    assert m.difficulty == 4


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
