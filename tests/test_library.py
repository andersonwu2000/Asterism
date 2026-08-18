"""Library hint parsing + the agent's "Library available" Context section.

The old whole-root promotion (`library.promote` / `maybe_promote`) is retired
— Library-ization now goes through the Librarian pipeline — so those tests are
gone. What remains:

1. `context._section_library_available` renders the right DB-index
   entries (v18: `db.bridged_library_index`, was INDEX.md).
"""
from __future__ import annotations

from pathlib import Path

from Tooling.state import intent


# ---------------------------------------------------------------------
# Context section — Library available
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
            "INSERT INTO problems (name, created_at,"
            " bootstrap_done) VALUES (?, ?, 1)",
            (prob, db.now()))
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
    tag); other domains are excluded."""
    from Tooling.agent import context
    conn = _mem()
    _seed_index(conn)
    pi = intent.ProblemIntent(
        problem="LinearAlgebra.normal_diagonalization", charter="T")
    body = "\n".join(context._section_library_available(conn, pi))
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
    pi = intent.ProblemIntent(problem="x", charter="T")
    assert context._section_library_available(conn, pi) == []
    assert context._section_library_available(None, pi) == []


def test_library_section_skips_other_domains_only(tmp_path: Path) -> None:
    """Bridged problems exist but none in this problem's domain -> empty
    section (don't dangle a header)."""
    from Tooling.agent import context
    conn = _mem()
    _seed_index(conn)
    pi = intent.ProblemIntent(problem="NumberTheory.x", charter="T")
    assert context._section_library_available(conn, pi) == []
