"""Librarian M1 — Step 0 inventory (mechanical).

Builds a small in-memory proof forest (same DB read-path as the TREE
renderer) and asserts the inventory captures proved decls, decomposition
deps, root identification, Defs.lean decl scan, and the markdown view.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.state import db
from Tooling.quality.librarian import inventory as inv


@pytest.fixture
def conn(tmp_path):
    c = db.connect(":memory:")
    db.init_schema(c)
    # goals.problem has a FK to problems(name); register the test
    # problem first so insert_goal doesn't trip the constraint.
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at, "
        "bootstrap_done) VALUES ('p', '', ?, 1)", (db.now(),))
    c.commit()
    return c


def _add_goal(conn, slug, status, *, problem="p", kind="theorem",
              origin="backward", lean_path=None):
    gid = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=lean_path or f"proofs/L_{slug}.lean",
        statement="True", origin=origin, depth=0, kind=kind,
    )
    if status != "open":
        conn.execute("UPDATE goals SET status = ? WHERE id = ?",
                     (status, gid))
    conn.commit()
    return gid


def _add_strategy(conn, goal_id, status):
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status, "
        "proposal_md, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
        (goal_id, "", "", status, "", "pid", db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _add_subgoal(conn, strategy_id, subgoal_id, position):
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position) "
        "VALUES (?,?,?)",
        (strategy_id, subgoal_id, position),
    )
    conn.commit()


# ---------------------------------------------------------------------
# Core: proved-decl listing + decomposition deps
# ---------------------------------------------------------------------

def test_inventory_lists_proved_decls_with_deps(conn):
    """root main decomposes (via succeeded strategy) into two proved
    children; deps capture that edge, ordered."""
    root = _add_goal(conn, "main", "proved", kind="theorem", origin="root",
                     lean_path="Problems/p/Root.lean")
    c1 = _add_goal(conn, "lemma_a", "proved", lean_path="proofs/L_lemma_a.lean")
    c2 = _add_goal(conn, "lemma_b", "proved", lean_path="proofs/L_lemma_b.lean")
    s = _add_strategy(conn, root, "succeeded")
    _add_subgoal(conn, s, c1, 0)
    _add_subgoal(conn, s, c2, 1)

    out = inv.build_inventory(conn, Path("/ws"), "p")
    slugs = {d.slug for d in out.decls}
    assert slugs == {"main", "lemma_a", "lemma_b"}
    root_decl = out.root
    assert root_decl is not None and root_decl.slug == "main"
    assert root_decl.deps == ["lemma_a", "lemma_b"]  # ordinal order


def test_inventory_excludes_non_proved(conn):
    """Only proved goals are Library candidates; non-proved nodes
    (shelved / disproved / open) are excluded entirely. (Valid goal
    statuses per schema: open/attempting/proved/shelved/
    pending_strategist_review/disproved/frozen — 'dead' is a strategy
    status, not a goal status.)"""
    _add_goal(conn, "main", "proved", kind="theorem", origin="root")
    _add_goal(conn, "shelved_one", "shelved")
    _add_goal(conn, "disproved_one", "disproved")
    _add_goal(conn, "open_one", "open")

    out = inv.build_inventory(conn, Path("/ws"), "p")
    assert {d.slug for d in out.decls} == {"main"}


def test_deps_drop_unproved_children(conn):
    """A winning strategy may list a child that ended up dead/shelved on
    a different branch; deps include only proved children."""
    root = _add_goal(conn, "main", "proved", kind="theorem", origin="root")
    good = _add_goal(conn, "good", "proved")
    bad = _add_goal(conn, "bad", "shelved")
    s = _add_strategy(conn, root, "succeeded")
    _add_subgoal(conn, s, good, 0)
    _add_subgoal(conn, s, bad, 1)

    out = inv.build_inventory(conn, Path("/ws"), "p")
    root_decl = out.root
    assert root_decl.deps == ["good"]


def test_only_succeeded_strategy_defines_deps(conn):
    """A dead/superseded strategy's subgoals must NOT become deps —
    only the winning (succeeded) strategy's children count."""
    root = _add_goal(conn, "main", "proved", kind="theorem", origin="root")
    via_dead = _add_goal(conn, "abandoned", "proved")
    via_win = _add_goal(conn, "kept", "proved")
    s_dead = _add_strategy(conn, root, "dead")
    _add_subgoal(conn, s_dead, via_dead, 0)
    s_win = _add_strategy(conn, root, "succeeded")
    _add_subgoal(conn, s_win, via_win, 0)

    out = inv.build_inventory(conn, Path("/ws"), "p")
    assert out.root.deps == ["kept"]


def test_leaf_has_empty_deps(conn):
    """A Builder-proved leaf (no succeeded decomposition) → empty deps."""
    _add_goal(conn, "main", "proved", kind="theorem", origin="root")
    out = inv.build_inventory(conn, Path("/ws"), "p")
    assert out.root.deps == []


# ---------------------------------------------------------------------
# reference: statement stays by-reference (lean_path), never inlined
# ---------------------------------------------------------------------

def test_reference_is_lean_path_not_statement(conn):
    """Inventory carries goal_id + lean_path as the reference; it must
    NOT pull the full statement inline (plan §7 — by-reference only)."""
    _add_goal(conn, "main", "proved", kind="theorem", origin="root",
              lean_path="Problems/p/Root.lean")
    out = inv.build_inventory(conn, Path("/ws"), "p")
    d = out.root
    assert d.goal_id > 0
    assert d.lean_path == "Problems/p/Root.lean"
    assert not hasattr(d, "statement")


# ---------------------------------------------------------------------
# Defs.lean declaration scan
# ---------------------------------------------------------------------

def test_defs_decls_scans_declarations(tmp_path):
    pdir = tmp_path / "Problems" / "demo"
    pdir.mkdir(parents=True)
    (pdir / "Defs.lean").write_text(
        "import Mathlib\n\n"
        "namespace Demo\n\n"
        "def MyThing := Nat\n"
        "structure Widget where\n  x : Nat\n"
        "noncomputable def Gadget := Real\n"
        "class Doohickey (a : Type) where\n  f : a\n"
        "end Demo\n",
        encoding="utf-8",
    )
    names = inv.defs_decls(tmp_path, "demo")
    assert names == ["MyThing", "Widget", "Gadget", "Doohickey"]


def test_defs_decls_empty_when_no_defs(tmp_path):
    (tmp_path / "Problems" / "demo").mkdir(parents=True)
    assert inv.defs_decls(tmp_path, "demo") == []


def test_defs_decls_empty_for_comment_only_defs(tmp_path):
    """SVD-shape Defs.lean: namespace + comment, no real declarations →
    empty (so root re-derivation is trivially Defs-free, plan §2 B)."""
    pdir = tmp_path / "Problems" / "demo"
    pdir.mkdir(parents=True)
    (pdir / "Defs.lean").write_text(
        "import Mathlib\n\nnamespace Demo\n\n"
        "-- def Foo := Bar  (commented out)\n"
        "end Demo\n",
        encoding="utf-8",
    )
    assert inv.defs_decls(tmp_path, "demo") == []


# ---------------------------------------------------------------------
# Markdown view
# ---------------------------------------------------------------------

def test_render_view_shows_slugs_not_statements(conn):
    root = _add_goal(conn, "main", "proved", kind="theorem", origin="root")
    c1 = _add_goal(conn, "lemma_a", "proved")
    s = _add_strategy(conn, root, "succeeded")
    _add_subgoal(conn, s, c1, 0)

    out = inv.build_inventory(conn, Path("/ws"), "p")
    view = inv.render_view(out)
    assert "main" in view and "lemma_a" in view
    assert "2 proved declaration" in view
    assert "Defs-free" in view  # no Defs decls in this fixture
