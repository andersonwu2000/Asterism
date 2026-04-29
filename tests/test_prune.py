"""prune library: winning_chain walk + prune_problem behavior."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import db, prune


def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()),
    )


def _seed_root(conn: sqlite3.Connection, name: str = "p",
               status: str = "proved") -> int:
    gid = db.insert_goal(
        conn, problem=name, slug="main",
        lean_path=f"Problems/{name}/Root.lean",
        statement="T", origin="root", difficulty=4,
    )
    db.update_goal_status(conn, gid, status)
    return gid


def _seed_strategy(conn: sqlite3.Connection, *, goal_id: int, sid_label: str,
                   problem: str = "p", status: str = "succeeded") -> int:
    sid = db.insert_strategy(
        conn, goal_id=goal_id,
        lean_path=f"Problems/{problem}/Root.lean",
        scratch_path=f"Problems/{problem}/proofs/_strategy_{sid_label}.lean",
        created_by="pid-x",
    )
    if status != "proposed":
        db.update_strategy_status(conn, sid, status)
    return sid


def _seed_subgoal(conn: sqlite3.Connection, *, problem: str, slug: str,
                  status: str = "proved") -> int:
    sub = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/proofs/L_{slug}.lean",
        statement="T", origin="backward", difficulty=3, depth=1,
    )
    if status != "open":
        db.update_goal_status(conn, sub, status)
    return sub


# ---------------------------------------------------------------------
# winning_chain
# ---------------------------------------------------------------------

def test_winning_chain_one_strategy(conn: sqlite3.Connection) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub1 = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    sub2 = _seed_subgoal(conn, problem="p", slug="s1_main_sub_2")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub1, position=0)
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub2, position=1)

    keep = prune.winning_chain(conn, "p")
    assert keep == {
        "Problems/p/Root.lean",
        "Problems/p/proofs/_strategy_s1.lean",
        "Problems/p/proofs/L_s1_main_sub_1.lean",
        "Problems/p/proofs/L_s1_main_sub_2.lean",
    }


def test_winning_chain_skips_superseded_strategies(
    conn: sqlite3.Connection,
) -> None:
    """Only the 'succeeded' strategy of a goal contributes to the chain;
    'superseded' / 'dead' OR siblings and their sub-goals are excluded."""
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1", status="succeeded")
    loser = _seed_strategy(conn, goal_id=root, sid_label="s2",
                           status="superseded")
    win_sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    loser_sub = _seed_subgoal(conn, problem="p", slug="s2_main_sub_1",
                              status="open")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=win_sub, position=0)
    db.link_subgoal(conn, strategy_id=loser, subgoal_id=loser_sub, position=0)

    keep = prune.winning_chain(conn, "p")
    assert "Problems/p/proofs/_strategy_s1.lean" in keep
    assert "Problems/p/proofs/L_s1_main_sub_1.lean" in keep
    assert "Problems/p/proofs/_strategy_s2.lean" not in keep
    assert "Problems/p/proofs/L_s2_main_sub_1.lean" not in keep


def test_winning_chain_recursive_through_nested_strategies(
    conn: sqlite3.Connection,
) -> None:
    """Sub-goal proved via its own succeeded sub-strategy is included."""
    _seed_problem(conn)
    root = _seed_root(conn)
    s_root = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=s_root, subgoal_id=sub, position=0)

    s_sub = _seed_strategy(conn, goal_id=sub, sid_label="s5", problem="p")
    leaf = _seed_subgoal(conn, problem="p", slug="s5_s1_main_sub_1_sub_1")
    db.link_subgoal(conn, strategy_id=s_sub, subgoal_id=leaf, position=0)

    keep = prune.winning_chain(conn, "p")
    assert "Problems/p/proofs/_strategy_s5.lean" in keep
    assert "Problems/p/proofs/L_s5_s1_main_sub_1_sub_1.lean" in keep


def test_winning_chain_empty_when_root_not_proved(
    conn: sqlite3.Connection,
) -> None:
    _seed_problem(conn)
    _seed_root(conn, status="open")
    assert prune.winning_chain(conn, "p") == set()


# ---------------------------------------------------------------------
# prune_problem
# ---------------------------------------------------------------------

def _build_proofs_tree(workspace: Path, problem: str,
                       filenames: list[str]) -> dict[str, Path]:
    proofs = workspace / "Problems" / problem / "proofs"
    proofs.mkdir(parents=True, exist_ok=True)
    paths = {}
    for fn in filenames:
        p = proofs / fn
        p.write_text("-- placeholder\n", encoding="utf-8")
        paths[fn] = p
    # Also seed Root.lean and Defs.lean above proofs/, to confirm prune
    # never touches them.
    (workspace / "Problems" / problem / "Root.lean").write_text(
        "-- root\n", encoding="utf-8")
    (workspace / "Problems" / problem / "Defs.lean").write_text(
        "-- defs\n", encoding="utf-8")
    return paths


def test_prune_problem_removes_orphans_keeps_winners(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)

    files = _build_proofs_tree(tmp_path, "p", [
        "_strategy_s1.lean",          # winner scratch
        "L_s1_main_sub_1.lean",       # winner sub-goal
        "_strategy_s2.lean",          # orphan (no row in DB at all)
        "L_orphan_sub.lean",          # orphan
    ])

    removed = prune.prune_problem(conn, tmp_path, "p")
    removed_names = {p.name for p in removed}
    assert removed_names == {"_strategy_s2.lean", "L_orphan_sub.lean"}
    assert files["_strategy_s1.lean"].exists()
    assert files["L_s1_main_sub_1.lean"].exists()
    assert not files["_strategy_s2.lean"].exists()
    # Defs.lean and Root.lean (above proofs/) are untouched
    assert (tmp_path / "Problems/p/Root.lean").exists()
    assert (tmp_path / "Problems/p/Defs.lean").exists()


def test_prune_problem_idempotent(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)
    _build_proofs_tree(tmp_path, "p",
                       ["_strategy_s1.lean", "L_s1_main_sub_1.lean",
                        "_strategy_s2.lean"])

    first = prune.prune_problem(conn, tmp_path, "p")
    second = prune.prune_problem(conn, tmp_path, "p")
    assert len(first) == 1
    assert second == []


def test_prune_problem_noop_when_root_not_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    _seed_root(conn, status="attempting")
    _build_proofs_tree(tmp_path, "p", ["L_anything.lean"])

    removed = prune.prune_problem(conn, tmp_path, "p")
    assert removed == []
    assert (tmp_path / "Problems/p/proofs/L_anything.lean").exists()


def test_prune_problem_dry_run_does_not_delete(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)
    files = _build_proofs_tree(tmp_path, "p",
                               ["_strategy_s1.lean", "L_s1_main_sub_1.lean",
                                "_strategy_s99.lean"])

    removed = prune.prune_problem(conn, tmp_path, "p", dry_run=True)
    assert {p.name for p in removed} == {"_strategy_s99.lean"}
    # File still on disk after dry-run
    assert files["_strategy_s99.lean"].exists()


# ---------------------------------------------------------------------
# reconcile_proved_goals (E6: file/DB drift repair)
# ---------------------------------------------------------------------

def _seed_drifted_subgoal(conn: sqlite3.Connection, *, problem: str,
                           parent_slug: str, win_sid: int, lose_sid: int,
                           statement: str = "T") -> Path:
    """Seed a sub-goal whose lean_path imports BOTH the winning and the
    losing strategies' scratch (last-write-wins from a Verify race).
    Returns the absolute parent file path (caller has tmp_path)."""
    raise NotImplementedError  # placeholder (test uses inline construction)


def test_reconcile_repairs_drifted_parent_lean_path(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Simulate the compactness goal-4 race: parent file imports both
    s7 and s14 and aliases to s14, but DB says s7 is the succeeded
    strategy. Reconcile must rewrite to canonical s7-only form."""
    _seed_problem(conn)
    parent_gid = _seed_root(conn)
    # Two strategies, only s7 is succeeded
    sid7 = _seed_strategy(conn, goal_id=parent_gid, sid_label="s7",
                           status="succeeded")
    sid14 = _seed_strategy(conn, goal_id=parent_gid, sid_label="s14",
                            status="superseded")
    # Override scratch_path to use the actual sid for the canonical form
    db.update_strategy_scratch_path(
        conn, sid7,
        f"Problems/p/proofs/_strategy_s{sid7}.lean")
    db.update_strategy_scratch_path(
        conn, sid14,
        f"Problems/p/proofs/_strategy_s{sid14}.lean")

    # Build the proofs tree with both scratch files present
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / f"_strategy_s{sid7}.lean").write_text("-- winner\n")
    (proofs / f"_strategy_s{sid14}.lean").write_text("-- loser\n")

    # The parent file is at "Problems/p/Root.lean" per _seed_root;
    # write the drifted content imitating last-write-wins from s14.
    parent = tmp_path / "Problems/p/Root.lean"
    parent.parent.mkdir(parents=True, exist_ok=True)
    drifted = (
        f"import Mathlib\n"
        f"import Problems.p.proofs._strategy_s{sid7}\n"
        f"import Problems.p.proofs._strategy_s{sid14}\n\n"
        f"namespace Problems.p\n\n"
        f"theorem main : T := s{sid14}_main\n\n"
        f"end Problems.p\n"
    )
    parent.write_text(drifted, encoding="utf-8")

    repaired = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert parent in repaired

    new_content = parent.read_text(encoding="utf-8")
    assert f"import Problems.p.proofs._strategy_s{sid7}" in new_content
    assert f"import Problems.p.proofs._strategy_s{sid14}" not in new_content
    assert f"theorem main : T := s{sid7}_main" in new_content


def test_reconcile_idempotent(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Already-canonical parent file is left untouched on second call."""
    _seed_problem(conn)
    root = _seed_root(conn)
    sid = _seed_strategy(conn, goal_id=root, sid_label="s1",
                         status="succeeded")
    db.update_strategy_scratch_path(
        conn, sid, f"Problems/p/proofs/_strategy_s{sid}.lean")

    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / f"_strategy_s{sid}.lean").write_text("-- ok\n")
    parent = tmp_path / "Problems/p/Root.lean"
    parent.parent.mkdir(parents=True, exist_ok=True)
    # Pre-seed a drifted parent (extra import) to verify first-pass repair.
    parent.write_text(
        f"import Mathlib\nimport Problems.p.proofs._strategy_s{sid}\n"
        f"import Problems.p.proofs._strategy_s99\n\n"
        f"namespace Problems.p\n\n"
        f"theorem main : T := s{sid}_main\n\n"
        f"end Problems.p\n",
        encoding="utf-8",
    )

    first = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert parent in first

    second = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert second == []  # already canonical


def test_reconcile_skips_goals_proved_by_builder(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A goal proved directly by Builder has no 'succeeded' strategy;
    reconcile must skip it (no scratch to alias from)."""
    _seed_problem(conn)
    _seed_root(conn)  # root proved, but no strategy
    repaired = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert repaired == []
