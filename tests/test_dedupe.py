"""dedupe library: normalize, equivalence, canonical lookup, alias build."""
from __future__ import annotations

import sqlite3

import pytest

from Tooling import db, dedupe


def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()),
    )


def _seed_goal(conn: sqlite3.Connection, *, problem: str = "p",
               slug: str, statement: str, origin: str = "backward",
               status: str = "open", lean_path: str | None = None,
               depth: int = 1) -> int:
    gid = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=lean_path or f"Problems/{problem}/proofs/L_{slug}.lean",
        statement=statement, origin=origin, difficulty=2, depth=depth,
    )
    if status != "open":
        db.update_goal_status(conn, gid, status)
    return gid


# ---------------------------------------------------------------------
# normalize / equivalence
# ---------------------------------------------------------------------

def test_normalize_collapses_whitespace() -> None:
    assert dedupe._normalize_statement("a   b\nc") == "a b c"
    assert dedupe._normalize_statement("  x  ") == "x"
    assert dedupe._normalize_statement("x\t\ty") == "x y"


def test_statements_equivalent_whitespace_invariant() -> None:
    assert dedupe._statements_equivalent("∀ p, P p", "∀ p,  P p")
    assert dedupe._statements_equivalent("a\nb", "a b")
    assert not dedupe._statements_equivalent("∀ p, P p", "∀ q, P q")


# ---------------------------------------------------------------------
# find_canonical — selection rules
# ---------------------------------------------------------------------

def test_find_canonical_finds_proved_match(conn: sqlite3.Connection) -> None:
    _seed_problem(conn)
    # Need a root for reachability path; seed it but the proved goal is
    # itself a root → reachability trivially OK
    gid = _seed_goal(conn, slug="canonical", statement="P", origin="root",
                     depth=0, status="proved",
                     lean_path="Problems/p/proofs/L_canonical.lean")
    assert dedupe.find_canonical(conn, "p", "P") == gid
    assert dedupe.find_canonical(conn, "p", "Q") is None


def test_find_canonical_prefers_proved_over_open(
    conn: sqlite3.Connection,
) -> None:
    """If multiple goals match, 'proved' beats 'open' / 'attempting'."""
    _seed_problem(conn)
    root = _seed_goal(conn, slug="root", statement="ROOT", origin="root",
                     depth=0, lean_path="Problems/p/Root.lean")
    # Need a proposed strategy from root for sub-goal reachability
    s = db.insert_strategy(conn, goal_id=root,
                           lean_path="Problems/p/Root.lean",
                           created_by="pid")
    open_g = _seed_goal(conn, slug="open_match", statement="X", status="open")
    db.link_subgoal(conn, strategy_id=s, subgoal_id=open_g, position=0)
    proved_g = _seed_goal(conn, slug="proved_match", statement="X",
                          status="proved")
    db.link_subgoal(conn, strategy_id=s, subgoal_id=proved_g, position=1)

    assert dedupe.find_canonical(conn, "p", "X") == proved_g


def test_find_canonical_skips_orphan_chain(conn: sqlite3.Connection) -> None:
    """A matching goal whose lineage passes through a 'superseded' or
    'dead' strategy is unreachable — must not be selected as canonical
    (its proof might never land)."""
    _seed_problem(conn)
    root = _seed_goal(conn, slug="root", statement="ROOT", origin="root",
                     depth=0, lean_path="Problems/p/Root.lean")
    s_dead = db.insert_strategy(conn, goal_id=root,
                                 lean_path="Problems/p/Root.lean",
                                 created_by="pid-d")
    db.update_strategy_status(conn, s_dead, "superseded")
    orphan = _seed_goal(conn, slug="orphan_match", statement="Y",
                        status="open")
    db.link_subgoal(conn, strategy_id=s_dead, subgoal_id=orphan, position=0)

    assert dedupe.find_canonical(conn, "p", "Y") is None


def test_find_canonical_root_always_eligible(conn: sqlite3.Connection) -> None:
    """A root goal is always in the alive set, regardless of strategies."""
    _seed_problem(conn)
    root = _seed_goal(conn, slug="root", statement="THM", origin="root",
                     depth=0, lean_path="Problems/p/Root.lean",
                     status="open")
    assert dedupe.find_canonical(conn, "p", "THM") == root


def test_find_canonical_skips_shelved(conn: sqlite3.Connection) -> None:
    _seed_problem(conn)
    _seed_goal(conn, slug="shelved_one", statement="Z",
               origin="root", depth=0,
               lean_path="Problems/p/Root.lean", status="shelved")
    assert dedupe.find_canonical(conn, "p", "Z") is None


def test_find_canonical_empty_statement_returns_none(
    conn: sqlite3.Connection,
) -> None:
    _seed_problem(conn)
    _seed_goal(conn, slug="root", statement="A", origin="root", depth=0,
               lean_path="Problems/p/Root.lean")
    assert dedupe.find_canonical(conn, "p", "") is None
    assert dedupe.find_canonical(conn, "p", "   ") is None


def test_find_canonical_problem_scoped(conn: sqlite3.Connection) -> None:
    """Match within problem only — cross-problem dedupe is deferred."""
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('p','p/m.md',?)", (db.now(),))
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('q','q/m.md',?)", (db.now(),))
    p_root = _seed_goal(conn, problem="p", slug="root", statement="STMT",
                        origin="root", depth=0,
                        lean_path="Problems/p/Root.lean")
    q_root = _seed_goal(conn, problem="q", slug="root", statement="STMT",
                        origin="root", depth=0,
                        lean_path="Problems/q/Root.lean")
    assert dedupe.find_canonical(conn, "p", "STMT") == p_root
    assert dedupe.find_canonical(conn, "q", "STMT") == q_root
    # Sanity: same statement but different problem → no cross-leak
    assert dedupe.find_canonical(conn, "p", "STMT") != q_root


# ---------------------------------------------------------------------
# build_alias_content
# ---------------------------------------------------------------------

def test_build_alias_includes_canonical_import_and_alias() -> None:
    out = dedupe.build_alias_content(
        problem="wilson", new_slug="s7_main_sub_1", statement="∀ p, P p",
        canonical_slug="s3_main_sub_1",
        canonical_module="Problems.wilson.proofs.L_s3_main_sub_1",
        defs_imported=True,
    )
    assert "import Mathlib" in out
    assert "import Problems.wilson.Defs" in out
    assert "import Problems.wilson.proofs.L_s3_main_sub_1" in out
    assert "namespace Problems.wilson" in out
    assert "theorem s7_main_sub_1 : ∀ p, P p := s3_main_sub_1" in out


def test_build_alias_skips_defs_when_absent() -> None:
    out = dedupe.build_alias_content(
        problem="cantor", new_slug="x", statement="T",
        canonical_slug="y",
        canonical_module="Problems.cantor.proofs.L_y",
        defs_imported=False,
    )
    assert "import Problems.cantor.Defs" not in out
