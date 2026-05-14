"""F49 — Library promotion: re-export proved roots into Library/<Topic>/.

Five contracts:

1. Manifest parser populates lemma_hints / mathlib_hints separately and
   exposes a unified all_hints view.
2. Topic inference picks first Library.<Topic>.* hint, falls back to
   Misc, and dedups the topics list.
3. Promotion writes the re-export file + INDEX entry, is idempotent on
   repeat calls, and updates the entry when the statement changes.
4. Promotion is gated by axiom whitelist (subset check).
5. Backward-compatible cascade hook: maybe_promote no-ops when root
   isn't proved.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from Tooling import db, library, manifest


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

def test_topic_from_hints_picks_first_library_hint() -> None:
    assert library.topic_from_hints([
        "Mathlib.NumberTheory.ZMod.Basic",
        "Library.NumberTheory.wilson",
        "Library.Algebra.something",
    ]) == "NumberTheory"


def test_topic_from_hints_fallback_misc_when_no_library() -> None:
    """All Mathlib, no Library hint → Misc fallback so promotion always
    has a home directory."""
    assert library.topic_from_hints([
        "Mathlib.Data.Nat.Basic", "Mathlib.Topology.Basic",
    ]) == "Misc"


def test_topic_from_hints_empty_input() -> None:
    assert library.topic_from_hints([]) == "Misc"


def test_topics_from_hints_dedups_and_preserves_order() -> None:
    assert library.topics_from_hints([
        "Library.NumberTheory.a",
        "Mathlib.X.Y",
        "Library.Algebra.b",
        "Library.NumberTheory.c",  # duplicate topic, drop
    ]) == ["NumberTheory", "Algebra"]


# ---------------------------------------------------------------------
# 3. Promotion — file + INDEX + idempotency
# ---------------------------------------------------------------------

def _bypass_axiom_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real axiom check requires a working lake build; tests mock it
    out unless we want to exercise the gate explicitly. library now
    delegates to the shared `_axiom.axiom_probe`; patch the symbol
    library imported at module load."""
    monkeypatch.setattr(library, "axiom_probe",
                        lambda *a, **kw: (True, "(test bypass)"))


def test_promote_writes_re_export_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bypass_axiom_check(monkeypatch)
    mfst = manifest.Manifest(
        problem="foo", statement="T",
        lemma_hints=["Library.NumberTheory.wilson"],
    )
    promoted, msg = library.promote(tmp_path, "foo", mfst,
                                     "∀ p, Prime p → ...")
    assert promoted is True
    target = tmp_path / "Library" / "NumberTheory" / "foo.lean"
    assert target.exists()
    body = target.read_text(encoding="utf-8")
    assert "import Problems.foo.Root" in body
    assert "theorem foo := Problems.foo.main" in body


def test_promote_appends_index_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bypass_axiom_check(monkeypatch)
    mfst = manifest.Manifest(
        problem="cantor", statement="¬∃ f : Set α → α, Function.Surjective f",
        lemma_hints=["Library.SetTheory.cantor"],
    )
    library.promote(tmp_path, "cantor", mfst, mfst.statement)
    idx = tmp_path / "Library" / "SetTheory" / "INDEX.md"
    assert idx.exists()
    body = idx.read_text(encoding="utf-8")
    assert "# Library/SetTheory — INDEX" in body
    assert "- `cantor`" in body
    assert "Surjective" in body  # truncated statement excerpt


def test_promote_misc_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Library.* hint → Misc/."""
    _bypass_axiom_check(monkeypatch)
    mfst = manifest.Manifest(
        problem="orphan", statement="T",
        lemma_hints=["Mathlib.Data.Nat.Basic"],
    )
    library.promote(tmp_path, "orphan", mfst, mfst.statement)
    assert (tmp_path / "Library" / "Misc" / "orphan.lean").exists()


def test_promote_idempotent_when_already_correct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second promote with identical state → no-op (returns False).
    Avoids needless writes that would dirty git status on every daemon
    exit after the problem is proved."""
    _bypass_axiom_check(monkeypatch)
    mfst = manifest.Manifest(
        problem="foo", statement="T",
        lemma_hints=["Library.Algebra.foo"],
    )
    p1, _ = library.promote(tmp_path, "foo", mfst, "T")
    p2, msg = library.promote(tmp_path, "foo", mfst, "T")
    assert p1 is True
    assert p2 is False
    assert "idempotent skip" in msg or "up-to-date" in msg


def test_promote_replaces_index_entry_on_statement_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Statement edit + re-promote → INDEX entry is replaced (single
    line per problem, no historical accretion)."""
    _bypass_axiom_check(monkeypatch)
    mfst = manifest.Manifest(
        problem="foo", statement="OLD",
        lemma_hints=["Library.Algebra.foo"],
    )
    library.promote(tmp_path, "foo", mfst, "OLD STATEMENT")
    library.promote(tmp_path, "foo", mfst, "NEW STATEMENT")
    body = (tmp_path / "Library" / "Algebra" / "INDEX.md").read_text(
        encoding="utf-8")
    # Exactly one entry for `foo`
    foo_lines = [ln for ln in body.splitlines() if "`foo`" in ln]
    assert len(foo_lines) == 1
    assert "NEW STATEMENT" in foo_lines[0]
    assert "OLD STATEMENT" not in body


# ---------------------------------------------------------------------
# 4. Axiom-whitelist gate
# ---------------------------------------------------------------------

def test_promote_rejects_axioms_outside_whitelist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When axiom_probe reports a rogue axiom, promote() returns
    (False, msg) and writes nothing."""
    monkeypatch.setattr(library, "axiom_probe",
        lambda *a, **kw: (False, "rogue axioms: ['rogue.X']"))
    mfst = manifest.Manifest(
        problem="bad", statement="T",
        axioms_whitelist=["propext"],
        lemma_hints=["Library.Algebra.bad"],
    )
    promoted, msg = library.promote(tmp_path, "bad", mfst, "T")
    assert promoted is False
    assert "rogue" in msg
    assert not (tmp_path / "Library" / "Algebra" / "bad.lean").exists()


def test_promote_empty_whitelist_accepts_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty axioms_whitelist short-circuits to accept (legacy
    behavior; matches existing manifests with no whitelist field)."""
    # Don't mock _check_axioms — exercise the empty-whitelist branch
    mfst = manifest.Manifest(
        problem="legacy", statement="T",
        axioms_whitelist=[],  # explicit empty
        lemma_hints=["Library.Misc.legacy"],
    )
    promoted, msg = library.promote(tmp_path, "legacy", mfst, "T")
    assert promoted is True
    assert "(no whitelist" in msg


# ---------------------------------------------------------------------
# 5. Cascade hook — maybe_promote
# ---------------------------------------------------------------------

def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()),
    )


def test_maybe_promote_noops_when_root_not_proved(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root status is open → no promotion attempt."""
    _bypass_axiom_check(monkeypatch)
    _seed_problem(conn, "p")
    db.insert_goal(conn, problem="p", slug="main",
                   lean_path="Problems/p/Root.lean",
                   statement="T", origin="root")
    mfst = manifest.Manifest(problem="p", statement="T",
                             lemma_hints=["Library.Algebra.p"])
    library.maybe_promote(conn, tmp_path, "p", mfst)
    assert not (tmp_path / "Library").exists()


def test_maybe_promote_runs_when_root_proved(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root status proved → file appears."""
    _bypass_axiom_check(monkeypatch)
    _seed_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="main",
                         lean_path="Problems/p/Root.lean",
                         statement="T", origin="root")
    db.update_goal_status(conn, gid, "proved")
    mfst = manifest.Manifest(problem="p", statement="T",
                             lemma_hints=["Library.NumberTheory.p"])
    library.maybe_promote(conn, tmp_path, "p", mfst)
    assert (tmp_path / "Library" / "NumberTheory" / "p.lean").exists()


def test_maybe_promote_swallows_exceptions(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bug in promote() must not crash the daemon — the promotion
    is a side effect, not a critical path. Caller logs to stderr and
    moves on."""
    _seed_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="main",
                         lean_path="Problems/p/Root.lean",
                         statement="T", origin="root")
    db.update_goal_status(conn, gid, "proved")

    def _boom(*a, **kw):
        raise RuntimeError("simulated promotion failure")
    monkeypatch.setattr(library, "promote", _boom)

    mfst = manifest.Manifest(problem="p", statement="T")
    # Should not raise
    library.maybe_promote(conn, tmp_path, "p", mfst)


# ---------------------------------------------------------------------
# 6. Context section — Library available
# ---------------------------------------------------------------------

def test_library_section_renders_topic_entries(tmp_path: Path) -> None:
    """When lemma_hints include Library.<Topic>.* and that Topic's
    INDEX.md exists, the section appears with that topic's entries."""
    from Tooling import context
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


def test_library_section_empty_when_no_library_hints(
    tmp_path: Path,
) -> None:
    """Manifest with only Mathlib hints → empty section (no clutter)."""
    from Tooling import context
    mfst = manifest.Manifest(
        problem="x", statement="T",
        lemma_hints=["Mathlib.Data.Nat.Basic"],
    )
    assert context._section_library_available(mfst, tmp_path) == []


def test_library_section_skips_topics_with_no_index(
    tmp_path: Path,
) -> None:
    """lemma_hints reference a topic whose INDEX.md doesn't exist yet
    (first promotion not happened) → don't dangle a header."""
    from Tooling import context
    mfst = manifest.Manifest(
        problem="x", statement="T",
        lemma_hints=["Library.Algebra.unknown"],
    )
    assert context._section_library_available(mfst, tmp_path) == []
