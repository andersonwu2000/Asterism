"""Per-Problem AND/OR proof tree renderer (Tooling/tree.py).

Tests cover render correctness (root-only, single strategy, OR multi-
strategy, recursion, cycle defense) + atomic file write side-effects."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, tree


def _seed_root(conn: sqlite3.Connection, problem: str = "p",
               slug: str = "main") -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, '', ?, 1)", (problem, db.now()))
    return db.insert_goal(
        conn, problem=problem, slug=slug, lean_path=f"P/{slug}.lean",
        statement="True", origin="root", depth=0,
    )


def _seed_strategy(conn, goal_id: int, status: str = "proposed") -> int:
    cur = conn.execute(
        "INSERT INTO strategies "
        "(goal_id, lean_path, scratch_path, status, proposal_md, created_by, created_at) "
        "VALUES (?, '', '', ?, '', 'pid', ?)",
        (goal_id, status, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_subgoal(conn, parent_strategy_id: int, slug: str,
                  problem: str = "p", depth: int = 1,
                  status: str = "open", attempts: int = 0,
                  position: int = 0) -> int:
    gid = db.insert_goal(
        conn, problem=problem, slug=slug, lean_path=f"P/{slug}.lean",
        statement="True", origin="backward", depth=depth,
    )
    if status != "open" or attempts:
        conn.execute(
            "UPDATE goals SET status = ?, attempts = ? WHERE id = ?",
            (status, attempts, gid))
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position) "
        "VALUES (?, ?, ?)",
        (parent_strategy_id, gid, position))
    conn.commit()
    return gid


# ---------------------------------------------------------------------
# render() — content correctness
# ---------------------------------------------------------------------

def test_render_no_problem_returns_init_hint(conn) -> None:
    out = tree.render(conn, "ghost")
    assert "no root goal" in out
    assert "ghost" in out


def test_render_root_only(conn) -> None:
    _seed_root(conn)
    out = tree.render(conn, "p")
    assert "main  (open)" in out
    assert "**Counters:** 1 open" in out


def test_render_root_with_single_strategy_and_subgoals(conn) -> None:
    root_id = _seed_root(conn)
    sid = _seed_strategy(conn, root_id, status="proposed")
    _seed_subgoal(conn, sid, "s1_sub_1", status="proved", position=0)
    _seed_subgoal(conn, sid, "s1_sub_2", status="open",
                  attempts=2, position=1)
    out = tree.render(conn, "p")
    # Strategy line uses `via sNN`
    assert f"via s{sid}" in out
    assert "(proposed)" in out
    # Sub-goal labels
    assert "s1_sub_1  (proved)" in out
    assert "s1_sub_2  (open, attempts=2)" in out
    # Tree connectors present (2-char indent style, see _BRANCH_* in
    # tree.py — keeps deep trees readable for descriptive slugs).
    assert "├─" in out
    assert "└─" in out


def test_render_dead_strategy_shows_subgoal_shelved_cause(conn) -> None:
    """Strategy.dead with a shelved sub-goal → '(dead — sub-goal shelved)'."""
    root_id = _seed_root(conn)
    sid = _seed_strategy(conn, root_id, status="dead")
    _seed_subgoal(conn, sid, "s1_sub_1", status="shelved",
                  attempts=8, position=0)
    out = tree.render(conn, "p")
    assert "dead — sub-goal shelved" in out


def test_render_dead_strategy_shows_verify_cause(conn) -> None:
    """Strategy.dead with no shelved sub-goals + a Verify dead_attempt
    on it → '(dead — verify failed)'. Tests the cause-detection
    fallback ordering."""
    root_id = _seed_root(conn)
    sid = _seed_strategy(conn, root_id, status="dead")
    # A still-OK sub-goal — no shelve.
    _seed_subgoal(conn, sid, "s1_sub_1", status="proved", position=0)
    # Insert a fake pipeline + dead_attempt on this strategy.
    conn.execute(
        "INSERT INTO pipelines "
        "(id, kind, target_id, target_kind, status, outcome, "
        " started_at, finished_at) "
        "VALUES ('pid-v', 'Verify', ?, 'Strategy', 'failed', 'failed', ?, ?)",
        (str(sid), db.now(), db.now()))
    conn.execute(
        "INSERT INTO dead_attempts "
        "(target_id, target_kind, pipeline_id, failure_reason, ts) "
        "VALUES (?, 'Strategy', 'pid-v', 'lake_build_error', ?)",
        (sid, db.now()))
    conn.commit()
    out = tree.render(conn, "p")
    assert "dead — verify failed" in out


def test_render_dead_strategy_falls_back_to_bare_dead(conn) -> None:
    """Strategy.dead with neither shelved sub-goals nor any dead_attempts
    on it → '(dead)' (no em-dash + cause clause). Avoids the awkward
    'dead — dead' literal."""
    root_id = _seed_root(conn)
    sid = _seed_strategy(conn, root_id, status="dead")
    out = tree.render(conn, "p")
    assert f"via s{sid}  (dead)" in out
    assert "dead — dead" not in out


def test_render_or_alternative_strategies_siblings(conn) -> None:
    """Two strategies on the same goal render as siblings (OR) — each
    on its own line under the parent goal."""
    root_id = _seed_root(conn)
    s1 = _seed_strategy(conn, root_id, status="dead")
    s2 = _seed_strategy(conn, root_id, status="proposed")
    out = tree.render(conn, "p")
    assert f"via s{s1}" in out
    assert f"via s{s2}" in out
    # s2 should come AFTER s1 (ORDER BY id), and use the └── final
    # connector; s1 uses the ├── intermediate.
    s1_pos = out.find(f"via s{s1}")
    s2_pos = out.find(f"via s{s2}")
    assert s1_pos < s2_pos


def test_render_recursive_two_levels(conn) -> None:
    """Goal → Strategy → Goal → Strategy → Goal walks correctly."""
    root_id = _seed_root(conn)
    s_root = _seed_strategy(conn, root_id)
    g_mid = _seed_subgoal(conn, s_root, "s1_sub_1", depth=1, position=0)
    s_mid = _seed_strategy(conn, g_mid)
    _seed_subgoal(conn, s_mid, "s2_sub_1", depth=2, status="proved",
                  position=0)
    out = tree.render(conn, "p")
    assert "main  " in out
    assert f"via s{s_root}" in out
    assert "s1_sub_1  " in out
    assert f"via s{s_mid}" in out
    assert "s2_sub_1  (proved)" in out


def test_render_cycle_defense_via_visited_set(conn) -> None:
    """Defensive: schema permits a goal to appear as sub-goal of two
    strategies. The walker's visited set should prevent infinite
    recursion — second appearance becomes a 'shown above' marker."""
    root_id = _seed_root(conn)
    s1 = _seed_strategy(conn, root_id)
    g_shared = _seed_subgoal(conn, s1, "s1_sub_1", position=0)
    s2 = _seed_strategy(conn, root_id, status="proposed")
    # Manually link g_shared as a sub-goal of s2 too (rare in
    # practice; walker must still terminate).
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position) "
        "VALUES (?, ?, 0)", (s2, g_shared))
    conn.commit()
    out = tree.render(conn, "p")
    assert "already shown above" in out


def test_render_keeps_full_slug_even_when_long(conn) -> None:
    """Long descriptive slugs render in FULL — the Strategist agent
    reads TREE.md inline (`phase2_context._section_tree_inline`) and
    needs the unambiguous slug to cross-reference with the
    active_goals_sidecar + Manifest hints. Display-side truncation
    would silently break that lookup. Tree width is managed via the
    2-char indent style, not via slug clipping."""
    root_id = _seed_root(conn)
    s = _seed_strategy(conn, root_id)
    long_slug = "e_pow_finset_sum_eq_scalar_v_variant_3"   # 38 chars
    _seed_subgoal(conn, s, long_slug, status="proved", position=0)
    out = tree.render(conn, "p")
    assert long_slug in out
    assert "…" not in out


def test_render_forward_goals_get_their_own_section(conn) -> None:
    """Forward-origin goals are independent lemmas — they render as
    sub-trees under a separate `## Forward` header (not connected to
    main's strategy tree). Backward sub-goals attached below a Forward
    goal walk through the same `_walk_goal`."""
    _seed_root(conn)
    # Forward-produced lemma at top level (no parent strategy edge).
    fwd_id = db.insert_goal(
        conn, problem="p", slug="contour_lemma", lean_path="P/L.lean",
        statement="True", origin="forward", depth=0,
    )
    # Backward later attacks the Forward lemma → its own strategy chain.
    s_fwd = _seed_strategy(conn, fwd_id, status="proposed")
    _seed_subgoal(conn, s_fwd, "contour_sub_1", status="proved", position=0)
    out = tree.render(conn, "p")
    # Main tree present (root)
    assert "main  " in out
    # Forward section header + lemma + its sub-tree
    assert "## Forward" in out
    assert "contour_lemma" in out
    assert f"via s{s_fwd}" in out
    assert "contour_sub_1  (proved)" in out


def test_render_no_forward_section_when_no_forward_goals(conn) -> None:
    """If a problem has no `origin='forward'` goals, the `## Forward`
    header doesn't appear (keeps the tree clean for the common case)."""
    _seed_root(conn)
    out = tree.render(conn, "p")
    assert "## Forward" not in out


def test_render_counters_aggregate_all_statuses(conn) -> None:
    root_id = _seed_root(conn)
    s = _seed_strategy(conn, root_id)
    _seed_subgoal(conn, s, "s1_sub_1", status="proved", position=0)
    _seed_subgoal(conn, s, "s1_sub_2", status="proved", position=1)
    _seed_subgoal(conn, s, "s1_sub_3", status="shelved", attempts=8,
                  position=2)
    out = tree.render(conn, "p")
    # 4 goals: root (open) + 3 subs (2 proved, 1 shelved)
    assert "2 proved" in out
    assert "1 shelved" in out
    assert "1 open" in out


# ---------------------------------------------------------------------
# write() — atomic filesystem side-effects
# ---------------------------------------------------------------------

def test_write_returns_none_when_problem_dir_missing(
    conn, tmp_path: Path,
) -> None:
    _seed_root(conn)  # DB has problem, but no Problems/p/ on disk
    out = tree.write(conn, tmp_path, "p")
    assert out is None


def test_write_creates_tree_md_in_problem_dir(
    conn, tmp_path: Path,
) -> None:
    _seed_root(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    out = tree.write(conn, tmp_path, "p")
    assert out == pdir / "TREE.md"
    content = out.read_text(encoding="utf-8")
    assert "main  (open)" in content
    assert "**Counters:**" in content


def test_write_overwrites_existing(conn, tmp_path: Path) -> None:
    """Subsequent writes replace (not append). Crucial because cascade
    fires many times per run; if writes appended we'd grow unbounded."""
    _seed_root(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "TREE.md").write_text("OLD CONTENT\n", encoding="utf-8")
    tree.write(conn, tmp_path, "p")
    content = (pdir / "TREE.md").read_text(encoding="utf-8")
    assert "OLD CONTENT" not in content
    assert "main  (open)" in content


def test_write_atomic_no_partial_file_on_inner_error(
    conn, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the write encounters an exception mid-flight, no partial
    TREE.md should be left behind (the temp file must be cleaned up
    and the destination not replaced)."""
    _seed_root(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "TREE.md").write_text("OLD\n", encoding="utf-8")

    real_replace = os.replace

    def boom(*a, **kw):
        raise OSError("disk full simulated")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError):
        tree.write(conn, tmp_path, "p")
    # Original file untouched
    assert (pdir / "TREE.md").read_text(encoding="utf-8") == "OLD\n"
    # No leftover *.tmp* in pdir
    assert not list(pdir.glob("TREE.*.tmp"))


# ---------------------------------------------------------------------
# write_for_target() — dispatcher hook convenience
# ---------------------------------------------------------------------

def test_write_for_target_resolves_goal(conn, tmp_path: Path) -> None:
    """target_kind='Goal' → look up problem via goals.id, write tree."""
    root_id = _seed_root(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    out = tree.write_for_target(conn, tmp_path, str(root_id), "Goal")
    assert out == pdir / "TREE.md"


def test_write_for_target_resolves_strategy(conn, tmp_path: Path) -> None:
    """target_kind='Strategy' → look up problem via strategies.goal_id."""
    root_id = _seed_root(conn)
    sid = _seed_strategy(conn, root_id)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    out = tree.write_for_target(conn, tmp_path, str(sid), "Strategy")
    assert out == pdir / "TREE.md"


def test_write_for_target_unknown_target_returns_none(
    conn, tmp_path: Path,
) -> None:
    """A target_id that doesn't exist in DB shouldn't crash — return None."""
    out = tree.write_for_target(conn, tmp_path, "999999", "Goal")
    assert out is None


def test_write_for_target_problem_target_kind(
    conn, tmp_path: Path,
) -> None:
    """target_kind='Problem' (Forward pipelines) uses target_id as the
    problem name directly — no int() cast. Regression guard for an SG
    run 2026-05-17 incident where the dispatcher logged
    `[tree] write skipped: invalid literal for int() with base 10:
    'sylvester_gallai'` after every Forward cascade because the
    previous Goal/Strategy branches were the only ones handled."""
    _seed_root(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    out = tree.write_for_target(conn, tmp_path, "p", "Problem")
    assert out == pdir / "TREE.md"
    assert out.read_text(encoding="utf-8").startswith("# p — TREE")


def test_write_for_target_swallows_exceptions(
    conn, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Tree-write failure must NEVER bubble up — would crash dispatcher."""
    root_id = _seed_root(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)

    def boom(*a, **kw):
        raise RuntimeError("simulated")

    monkeypatch.setattr(tree, "write", boom)
    out = tree.write_for_target(conn, tmp_path, str(root_id), "Goal")
    assert out is None
    err = capsys.readouterr().out
    assert "tree" in err and "skipped" in err
