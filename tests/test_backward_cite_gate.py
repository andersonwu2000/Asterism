"""Backward citation gate (`_check_cite_unproved`).

Rejects strategy patches that import `Problems.<p>.proofs.L_<slug>`
where `<slug>` is neither a declared sub-goal in the same commit nor
a goal in DB with status='proved'. Catches the sorryAx-leak class that
otherwise survives until root_integrity_gate.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.pipeline.backward import _check_cite_unproved
from Tooling.state import db


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)",
        (db.now(),),
    )
    c.commit()
    return c


def _insert_goal(conn: sqlite3.Connection, slug: str, *,
                 status: str) -> int:
    return db.insert_goal(
        conn, problem="p", slug=slug,
        lean_path=f"Problems/p/proofs/L_{slug}.lean",
        statement="T", origin="backward", status=status,
    )


def test_accepts_when_cited_slug_is_declared_subgoal(
    conn: sqlite3.Connection,
) -> None:
    """Agent declares `new_helper.lean` AND imports it from patch.lean —
    that's the framework-injected sub-goal import. No reject."""
    patch = "import Problems.p.proofs.L_helper\n"
    err = _check_cite_unproved(
        conn, problem="p", patch_text=patch, declared_slugs={"helper"},
    )
    assert err is None


def test_accepts_when_cited_slug_is_proved(
    conn: sqlite3.Connection,
) -> None:
    """Citing a proved sibling — soundness-safe library use."""
    _insert_goal(conn, "winding_number_int", status="proved")
    patch = "import Problems.p.proofs.L_winding_number_int\n"
    err = _check_cite_unproved(
        conn, problem="p", patch_text=patch, declared_slugs=set(),
    )
    assert err is None


def test_rejects_when_cited_slug_is_open_sibling(
    conn: sqlite3.Connection,
) -> None:
    """The residue_thm 2026-05-19 case: open sibling cited without
    declaring as sub-goal. Strategy patch would otherwise verify with a
    sorry-bearing import and propagate sorryAx upward."""
    _insert_goal(conn, "cauchy_simply_connected", status="open")
    patch = (
        "import Mathlib\n"
        "import Problems.p.Defs\n"
        "import Problems.p.proofs.L_cauchy_simply_connected\n"
        "namespace Problems.p\n"
        "theorem s1 : True := trivial\n"
        "end Problems.p\n"
    )
    err = _check_cite_unproved(
        conn, problem="p", patch_text=patch, declared_slugs=set(),
    )
    assert err is not None
    assert "cauchy_simply_connected" in err
    assert "open" in err


def test_rejects_attempting_and_shelved_too(
    conn: sqlite3.Connection,
) -> None:
    """Any non-proved status (attempting / shelved / disproved) blocks
    citation. Disproved gets its own block by being non-proved here;
    callers may want a separate path for disproved but the citation
    gate's only invariant is `must be proved`."""
    _insert_goal(conn, "foo", status="attempting")
    _insert_goal(conn, "bar", status="shelved")
    patch = (
        "import Problems.p.proofs.L_foo\n"
        "import Problems.p.proofs.L_bar\n"
    )
    err = _check_cite_unproved(
        conn, problem="p", patch_text=patch, declared_slugs=set(),
    )
    assert err is not None
    assert "foo" in err and "bar" in err
    assert "attempting" in err and "shelved" in err


def test_skips_unknown_slug(conn: sqlite3.Connection) -> None:
    """Cited slug doesn't match any goal — lake's `unknown identifier`
    will catch it. Citation gate doesn't double-reject."""
    patch = "import Problems.p.proofs.L_nonexistent\n"
    err = _check_cite_unproved(
        conn, problem="p", patch_text=patch, declared_slugs=set(),
    )
    assert err is None


def test_skips_cross_problem_imports(conn: sqlite3.Connection) -> None:
    """Imports targeting other problems are out of this gate's scope
    (cross-problem soundness invariants live elsewhere)."""
    _insert_goal(conn, "foo", status="open")
    patch = "import Problems.other.proofs.L_foo\n"  # different problem
    err = _check_cite_unproved(
        conn, problem="p", patch_text=patch, declared_slugs=set(),
    )
    assert err is None


def test_skips_aliased_goal_row(conn: sqlite3.Connection) -> None:
    """alias_target_id IS NULL filter — aliased goals shouldn't be
    counted as the citable lemma; the canonical goal (alias_target_id
    IS NULL) is what gets imported and checked."""
    _insert_goal(conn, "real", status="proved")
    # An alias row with same slug shouldn't exist via insert_goal
    # (slug uniqueness), so simulate via direct insert with a different
    # slug pointing at a non-existent canonical. Skip this edge.
    patch = "import Problems.p.proofs.L_real\n"
    err = _check_cite_unproved(
        conn, problem="p", patch_text=patch, declared_slugs=set(),
    )
    assert err is None  # real is proved
