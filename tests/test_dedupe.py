"""dedupe library: signature parser + ancestor-scoped canonical lookup +
tactic-based alias body."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import db, dedupe


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()),
    )


def _seed_root(conn: sqlite3.Connection, *, problem: str = "p",
               slug: str = "main", statement: str = "T",
               status: str = "open",
               lean_path: str | None = None) -> int:
    gid = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=lean_path or f"Problems/{problem}/Root.lean",
        statement=statement, origin="root", difficulty=4,
    )
    if status != "open":
        db.update_goal_status(conn, gid, status)
    return gid


def _seed_sub(conn: sqlite3.Connection, *, problem: str = "p",
              slug: str, statement: str, depth: int = 1,
              status: str = "open") -> int:
    gid = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/proofs/L_{slug}.lean",
        statement=statement, origin="backward", difficulty=2, depth=depth,
    )
    if status != "open":
        db.update_goal_status(conn, gid, status)
    return gid


def _link(conn: sqlite3.Connection, parent_id: int, sub_ids: list[int],
          *, problem: str = "p", status: str = "proposed") -> int:
    sid = db.insert_strategy(
        conn, goal_id=parent_id,
        lean_path=f"Problems/{problem}/Root.lean",
        scratch_path=f"Problems/{problem}/proofs/_strategy_s{parent_id}.lean",
        created_by="pid",
    )
    if status != "proposed":
        db.update_strategy_status(conn, sid, status)
    for pos, gid in enumerate(sub_ids):
        db.link_subgoal(conn, strategy_id=sid, subgoal_id=gid, position=pos)
    return sid


def _write_lean(workspace: Path, problem: str, slug: str,
                content: str, *, root: bool = False) -> Path:
    pdir = workspace / "Problems" / problem
    if root:
        path = pdir / "Root.lean"
    else:
        path = pdir / "proofs" / f"L_{slug}.lean"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------
# _normalize_statement
# ---------------------------------------------------------------------

def test_normalize_collapses_whitespace() -> None:
    assert dedupe._normalize_statement("a   b\nc") == "a b c"
    assert dedupe._normalize_statement("  x  ") == "x"
    assert dedupe._normalize_statement("x\t\ty") == "x y"


# ---------------------------------------------------------------------
# _signature_binder_count
# ---------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("theorem foo : T := by sorry", 0),
    ("theorem foo (x : Nat) : T := by sorry", 1),
    ("theorem foo (M) (hM) (hMax) : Sat M := by sorry", 3),
    ("theorem foo {α : Type} (x : α) : x = x := by rfl", 2),
    ("theorem foo {α} [Inhabited α] (x : α) : True := by trivial", 3),
    ("theorem foo (h : x ≥ 0) (hy : y > 0) : x + y > 0 := by sorry", 2),
])
def test_signature_binder_count(text: str, expected: int) -> None:
    assert dedupe._signature_binder_count(text) == expected


def test_signature_binder_count_no_theorem() -> None:
    assert dedupe._signature_binder_count("def foo := 1") == 0


# ---------------------------------------------------------------------
# find_canonical: ancestor scoping
# ---------------------------------------------------------------------

def test_find_canonical_excludes_immediate_parent(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """parent_goal_id (the goal currently being decomposed) must NOT be
    a candidate. Aliasing back to the immediate parent is circular —
    the candidate is one of parent's sub-goals supposed to help prove
    parent, so it cannot be discharged via parent's own proof. At lake
    level this manifests as an import cycle when Verify rewrites
    parent.lean_path."""
    _seed_problem(conn)
    root = _seed_root(conn, statement="ROOT_T")
    parent = _seed_sub(conn, slug="parent_match", statement="X")
    _link(conn, root, [parent])
    _write_lean(tmp_path, "p", "parent_match",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem parent_match (a : T) : X := by sorry\nend Problems.p\n")
    cand_text = (
        "import Mathlib\nnamespace Problems.p\n"
        "theorem cand (a : T) (b : T) : X := by sorry\n"
        "end Problems.p\n"
    )
    # Candidate's parent_goal_id is parent itself — must not match
    assert dedupe.find_canonical(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidate_full_text=cand_text,
        candidate_conclusion="X",
    ) is None


def test_find_canonical_finds_strict_ancestor_with_fewer_binders(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Valid case: candidate at depth 3 has same conclusion as a depth-1
    ancestor goal (the grandparent in DAG terms). Strict ancestor
    means parent_goal_id itself is excluded, but the grandparent is
    eligible."""
    _seed_problem(conn)
    root = _seed_root(conn, statement="ROOT_T")
    grandparent = _seed_sub(conn, slug="grand_match", statement="Sat M",
                             depth=1)
    _link(conn, root, [grandparent])
    # parent of candidate (depth 2) — different conclusion than match
    parent = _seed_sub(conn, slug="parent_no_match",
                       statement="OTHER_T", depth=2)
    _link(conn, grandparent, [parent])
    # canonical (grandparent's lean file): 3 binders
    _write_lean(tmp_path, "p", "grand_match",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem grand_match (M : T) (hM : T) (hMax : T) : Sat M := by sorry\n"
        "end Problems.p\n")
    # parent's lean file (different conclusion, irrelevant)
    _write_lean(tmp_path, "p", "parent_no_match",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem parent_no_match : OTHER_T := by sorry\n"
        "end Problems.p\n")
    # candidate (would be sub of strategy on parent — so parent_goal_id=parent)
    # has 6 binders, conclusion matches grandparent's "Sat M"
    cand_text = (
        "import Mathlib\nnamespace Problems.p\n"
        "theorem cand (M : T) (hM : T) (hMax : T) "
        "(hComp : T) (hCons : T) (hConj : T) : Sat M := by sorry\n"
        "end Problems.p\n"
    )
    assert dedupe.find_canonical(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidate_full_text=cand_text,
        candidate_conclusion="Sat M",
    ) == grandparent


def test_find_canonical_rejects_when_candidate_has_fewer_binders(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Reverse direction: candidate has FEWER binders than canonical.
    Aliasing would lack hypotheses canonical needs — must reject.
    (Uses grandparent setup so candidate's parent is excluded by
    strict ancestor.)"""
    _seed_problem(conn)
    root = _seed_root(conn)
    grandparent = _seed_sub(conn, slug="canonical_with_many",
                             statement="Sat M", depth=1)
    _link(conn, root, [grandparent])
    parent = _seed_sub(conn, slug="parent_dec",
                       statement="OTHER_T", depth=2)
    _link(conn, grandparent, [parent])
    # grandparent has 5 binders
    _write_lean(tmp_path, "p", "canonical_with_many",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem canonical_with_many (M : T) (h1 : T) (h2 : T) "
        "(h3 : T) (h4 : T) : Sat M := by sorry\nend Problems.p\n")
    _write_lean(tmp_path, "p", "parent_dec",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem parent_dec : OTHER_T := by sorry\nend Problems.p\n")
    # candidate has 3 binders, conclusion matches grandparent
    cand_text = (
        "import Mathlib\nnamespace Problems.p\n"
        "theorem cand (M : T) (h1 : T) (h2 : T) : Sat M := by sorry\n"
        "end Problems.p\n"
    )
    assert dedupe.find_canonical(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidate_full_text=cand_text,
        candidate_conclusion="Sat M",
    ) is None


def test_find_canonical_rejects_non_ancestor(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """OR-sibling goals are NOT ancestors and must not be candidates.
    Aliasing across OR siblings can break when one of them dies later."""
    _seed_problem(conn)
    root = _seed_root(conn, statement="ROOT_T")
    # Two OR-sibling strategies under root
    s2 = _link(conn, root, [])
    s4 = _link(conn, root, [])
    # s2's sub-goal (potential 'canonical') with matching conclusion
    other_sub = _seed_sub(conn, slug="s2_sub_1", statement="X")
    db.link_subgoal(conn, strategy_id=s2, subgoal_id=other_sub, position=0)
    _write_lean(tmp_path, "p", "s2_sub_1",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem s2_sub_1 (a : T) : X := by sorry\nend Problems.p\n")
    # candidate is being inserted under s4 (parent_goal_id = ?
    # well, parent_goal of s4 is root; s4's sub is being decomposed.
    # We simulate decomposing s4's first sub-goal that doesn't exist
    # yet — use root as parent_goal_id for the candidate's strategy)
    cand_text = (
        "import Mathlib\nnamespace Problems.p\n"
        "theorem cand (a : T) : X := by sorry\nend Problems.p\n"
    )
    # Looking for canonical from root's tree — s2_sub_1 is in s2's tree
    # but not on the ancestor chain of root itself. Wait: s2_sub_1's
    # ancestor is root. Walking ancestors from root: just {root}.
    # Walking from s4's parent (= root): {root}. So s2_sub_1 is not in
    # ancestors of root.
    result = dedupe.find_canonical(
        conn, tmp_path, problem="p", parent_goal_id=root,
        candidate_full_text=cand_text,
        candidate_conclusion="X",
    )
    # root.statement is "ROOT_T", not "X" → no match. s2_sub_1 not in
    # ancestors of root → excluded. Result: None.
    assert result is None


def test_find_canonical_skips_orphan_chain(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A matching strict ancestor on a 'superseded' path must not be
    picked. Uses 3-deep DAG so parent_goal_id has a strict ancestor to
    test against."""
    _seed_problem(conn)
    root = _seed_root(conn, statement="ROOT_T")
    grandparent = _seed_sub(conn, slug="grand", statement="X", depth=1)
    s_dead = db.insert_strategy(
        conn, goal_id=root, lean_path="Problems/p/Root.lean",
        created_by="pid",
        scratch_path="Problems/p/proofs/_strategy_dead.lean",
    )
    db.update_strategy_status(conn, s_dead, "superseded")
    db.link_subgoal(conn, strategy_id=s_dead, subgoal_id=grandparent, position=0)
    parent = _seed_sub(conn, slug="parent_dec",
                       statement="OTHER_T", depth=2)
    _link(conn, grandparent, [parent])
    _write_lean(tmp_path, "p", "grand",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem grand : X := by sorry\nend Problems.p\n")
    _write_lean(tmp_path, "p", "parent_dec",
        "import Mathlib\nnamespace Problems.p\n"
        "theorem parent_dec : OTHER_T := by sorry\nend Problems.p\n")
    cand_text = (
        "import Mathlib\nnamespace Problems.p\n"
        "theorem cand (a : T) : X := by sorry\nend Problems.p\n"
    )
    # grandparent is on a superseded chain — alive set excludes it
    assert dedupe.find_canonical(
        conn, tmp_path, problem="p", parent_goal_id=parent,
        candidate_full_text=cand_text,
        candidate_conclusion="X",
    ) is None


def test_find_canonical_problem_scoped(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Match within problem only — no cross-problem leak."""
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('p','p/m.md',?)", (db.now(),))
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('q','q/m.md',?)", (db.now(),))
    p_root = _seed_root(conn, problem="p", statement="STMT")
    _seed_root(conn, problem="q", statement="STMT")
    # Sub-goal of p_root that will be the candidate's parent (so p_root
    # is a strict ancestor and matches as canonical)
    p_parent = _seed_sub(conn, problem="p", slug="p_parent",
                         statement="OTHER_T", depth=1)
    _link(conn, p_root, [p_parent], problem="p")
    _write_lean(tmp_path, "p", "main",
        "import Mathlib\ntheorem main : STMT := by sorry\n", root=True)
    _write_lean(tmp_path, "p", "p_parent",
        "import Mathlib\ntheorem p_parent : OTHER_T := by sorry\n")
    _write_lean(tmp_path, "q", "main",
        "import Mathlib\ntheorem main : STMT := by sorry\n", root=True)
    cand_text = "import Mathlib\ntheorem cand : STMT := by sorry\n"
    assert dedupe.find_canonical(
        conn, tmp_path, problem="p", parent_goal_id=p_parent,
        candidate_full_text=cand_text,
        candidate_conclusion="STMT",
    ) == p_root


def test_find_canonical_empty_returns_none(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    assert dedupe.find_canonical(
        conn, tmp_path, problem="p", parent_goal_id=root,
        candidate_full_text="",
        candidate_conclusion="",
    ) is None


# ---------------------------------------------------------------------
# build_alias_content
# ---------------------------------------------------------------------

def test_build_alias_replaces_sorry_with_apply_assumption() -> None:
    original = (
        "import Mathlib\n"
        "import Problems.p.Defs\n\n"
        "namespace Problems.p\n\n"
        "theorem cand (M : T) (h : T) : Sat M := by sorry\n\n"
        "end Problems.p\n"
    )
    out = dedupe.build_alias_content(
        original_content=original,
        canonical_module="Problems.p.proofs.L_canonical",
        canonical_slug="canonical",
    )
    assert "import Problems.p.proofs.L_canonical" in out
    assert ":= by apply canonical <;> assumption" in out
    assert ":= by sorry" not in out
    # Original signature preserved verbatim
    assert "theorem cand (M : T) (h : T) : Sat M" in out
    # Original imports preserved
    assert "import Mathlib" in out
    assert "import Problems.p.Defs" in out


def test_build_alias_does_not_duplicate_existing_import() -> None:
    """If canonical import is already present (rare), don't add twice."""
    original = (
        "import Mathlib\n"
        "import Problems.p.proofs.L_canonical\n\n"
        "theorem cand : T := by sorry\n"
    )
    out = dedupe.build_alias_content(
        original_content=original,
        canonical_module="Problems.p.proofs.L_canonical",
        canonical_slug="canonical",
    )
    assert out.count("import Problems.p.proofs.L_canonical") == 1


def test_build_alias_handles_no_imports() -> None:
    original = "theorem cand : T := by sorry\n"
    out = dedupe.build_alias_content(
        original_content=original,
        canonical_module="Problems.p.proofs.L_c",
        canonical_slug="c",
    )
    assert out.startswith("import Problems.p.proofs.L_c")
    assert ":= by apply c <;> assumption" in out
