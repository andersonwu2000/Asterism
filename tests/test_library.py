"""Library hint parsing + the agent's "Library available" Context section.

The old whole-root promotion (`library.promote` / `maybe_promote`) is retired
— Library-ization now goes through the Librarian pipeline — so those tests are
gone. What remains:

1. Manifest parser populates lemma_hints / mathlib_hints separately and
   exposes a unified all_hints view.
2. `topics_from_hints` dedups + preserves order.
3. `context._section_library_available` renders the right INDEX entries.
"""
from __future__ import annotations

from pathlib import Path

from Tooling.state import manifest
from Tooling.quality import library


# ---------------------------------------------------------------------
# 1. Manifest parser — lemma_hints / mathlib_hints / all_hints
# ---------------------------------------------------------------------

def _write_manifest(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "Manifest.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_manifest_reads_lemma_hints_section(tmp_path: Path) -> None:
    """`## Lemma hints` populates lemma_hints; mathlib_hints stays []
    when no `## Mathlib hints` section is present."""
    p = _write_manifest(tmp_path,
        "---\nproblem: foo\n---\n"
        "## Statement\nT\n## Difficulty\n3\n"
        "## Lemma hints\n- Mathlib.NumberTheory.ZMod.Basic\n"
        "- Library.NumberTheory.wilson\n")
    m = manifest.parse(p)
    assert m.lemma_hints == [
        "Mathlib.NumberTheory.ZMod.Basic", "Library.NumberTheory.wilson"]
    assert m.mathlib_hints == []
    assert m.all_hints == m.lemma_hints


def test_manifest_legacy_mathlib_hints_still_works(tmp_path: Path) -> None:
    """Pre-F49 manifests with only `## Mathlib hints` keep working;
    those entries flow into all_hints unchanged."""
    p = _write_manifest(tmp_path,
        "---\nproblem: legacy\n---\n"
        "## Statement\nT\n## Difficulty\n3\n"
        "## Mathlib hints\n- Mathlib.Data.Nat.Basic\n")
    m = manifest.parse(p)
    assert m.lemma_hints == []
    assert m.mathlib_hints == ["Mathlib.Data.Nat.Basic"]
    assert m.all_hints == ["Mathlib.Data.Nat.Basic"]


def test_manifest_both_sections_dedup(tmp_path: Path) -> None:
    """If both sections list the same hint, all_hints dedups it."""
    p = _write_manifest(tmp_path,
        "---\nproblem: dup\n---\n"
        "## Statement\nT\n## Difficulty\n3\n"
        "## Lemma hints\n- Mathlib.A\n- Mathlib.B\n"
        "## Mathlib hints\n- Mathlib.A\n- Mathlib.C\n")
    m = manifest.parse(p)
    assert m.all_hints == ["Mathlib.A", "Mathlib.B", "Mathlib.C"]


# ---------------------------------------------------------------------
# 2. Topic inference
# ---------------------------------------------------------------------

def test_topics_from_hints_dedups_and_preserves_order() -> None:
    assert library.topics_from_hints([
        "Library.NumberTheory.a",
        "Mathlib.X.Y",
        "Library.Algebra.b",
        "Library.NumberTheory.c",  # duplicate topic, drop
    ]) == ["NumberTheory", "Algebra"]


# ---------------------------------------------------------------------
# 3. Context section — Library available
# ---------------------------------------------------------------------

def test_library_section_renders_topic_entries(tmp_path: Path) -> None:
    """When lemma_hints include Library.<Topic>.* and that Topic's
    INDEX.md exists, the section appears with that topic's entries."""
    from Tooling.agent import context
    (tmp_path / "Library" / "NumberTheory").mkdir(parents=True)
    (tmp_path / "Library" / "NumberTheory" / "INDEX.md").write_text(
        "# Library/NumberTheory — INDEX\n\n"
        "- `wilson` — ∀ p, Nat.Prime p → ...\n",
        encoding="utf-8",
    )
    mfst = manifest.Manifest(
        problem="newprob", statement="T",
        lemma_hints=["Library.NumberTheory.wilson"],
    )
    section = context._section_library_available(mfst, tmp_path)
    body = "\n".join(section)
    assert "## Library available" in body
    assert "### NumberTheory" in body
    assert "`wilson`" in body


def test_library_section_empty_when_no_library_hints(tmp_path: Path) -> None:
    """Manifest with only Mathlib hints → empty section (no clutter)."""
    from Tooling.agent import context
    mfst = manifest.Manifest(
        problem="x", statement="T",
        lemma_hints=["Mathlib.Data.Nat.Basic"],
    )
    assert context._section_library_available(mfst, tmp_path) == []


def test_library_section_skips_topics_with_no_index(tmp_path: Path) -> None:
    """lemma_hints reference a topic whose INDEX.md doesn't exist yet
    (first promotion not happened) → don't dangle a header."""
    from Tooling.agent import context
    mfst = manifest.Manifest(
        problem="x", statement="T",
        lemma_hints=["Library.Algebra.unknown"],
    )
    assert context._section_library_available(mfst, tmp_path) == []
