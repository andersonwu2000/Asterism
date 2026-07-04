"""Library hint parsing + the agent's "Library available" Context section.

The old whole-root promotion (`library.promote` / `maybe_promote`) is retired
— Library-ization now goes through the Librarian pipeline — so those tests are
gone. What remains:

1. Manifest parser populates lemma_hints / mathlib_hints separately and
   exposes a unified all_hints view.
2. `context._section_library_available` renders the right DB-index
   entries (v18: `db.bridged_library_index`, was INDEX.md).
"""
from __future__ import annotations

from pathlib import Path

from Tooling.state import manifest


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
# 2. Context section — Library available
# ---------------------------------------------------------------------

def _seed_index(conn) -> None:
    """DB successor of the old INDEX.md fixture: two bridged problems,
    one LinearAlgebra (with a `.main` keystone) and one Geometry."""
    from Tooling.state import db
    entries = {
        "LinearAlgebra.schur_triangularization": [
            "Library.LinearAlgebra.SchurTriangularization.Triangularization.main",
            "Library.LinearAlgebra.SchurTriangularization.FlagBasis.foo",
        ],
        "Geometry.banach_tarski": [
            "Library.Geometry.BanachTarski.Equidecomp.bar",
        ],
    }
    for prob, fqns in entries.items():
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at,"
            " bootstrap_done) VALUES (?, ?, ?, 1)",
            (prob, f"Problems/{prob}/Manifest.md", db.now()))
        for i, fqn in enumerate(fqns):
            slug = fqn.rsplit(".", 1)[-1]
            db.upsert_library_decl(conn, problem=prob, slug=slug,
                                   source_goal_id=None)
            db.set_library_verdict(conn, problem=prob, slug=slug,
                                   verdict="keep")
            db.set_library_classification(
                conn, problem=prob, slug=slug,
                target_file=f"Library/{prob}/{slug}.lean",
                target_name=fqn, file_order=i)
            db.mark_library_migrated(conn, problem=prob, slug=slug)
        db.mark_library_bridged(conn, prob)


def _mem():
    from Tooling.state import db
    conn = db.connect(":memory:")
    db.init_schema(conn)
    return conn


def test_library_section_domain_menu(tmp_path: Path) -> None:
    """Same-domain bridged problems appear as a compact menu (with keystone
    tag); other domains are excluded. (Manifest `## Lemma hints`
    highlighting was retired in favour of target-1 pre-search.)"""
    from Tooling.agent import context
    conn = _mem()
    _seed_index(conn)
    mfst = manifest.Manifest(
        problem="LinearAlgebra.normal_diagonalization", statement="T")
    body = "\n".join(context._section_library_available(conn, mfst))
    assert "## Library available" in body
    # same-domain (LinearAlgebra) listed with keystone
    assert "LinearAlgebra.schur_triangularization" in body
    assert "keystone" in body and ".Triangularization.main" in body
    # cross-domain (Geometry) NOT in the domain menu
    assert "banach_tarski" not in body


def test_library_section_empty_when_nothing_bridged(tmp_path: Path) -> None:
    """Empty DB index -> empty section (no clutter); conn=None (bare brief
    render) likewise."""
    from Tooling.agent import context
    conn = _mem()
    mfst = manifest.Manifest(
        problem="x", statement="T",
        lemma_hints=["Mathlib.Data.Nat.Basic"],
    )
    assert context._section_library_available(conn, mfst) == []
    assert context._section_library_available(None, mfst) == []


def test_library_section_skips_other_domains_only(tmp_path: Path) -> None:
    """Bridged problems exist but none in this problem's domain -> empty
    section (don't dangle a header)."""
    from Tooling.agent import context
    conn = _mem()
    _seed_index(conn)
    mfst = manifest.Manifest(problem="NumberTheory.x", statement="T")
    assert context._section_library_available(conn, mfst) == []
