"""Tree-level consistency sweep + interrupted-cascade repair (task #11).

The crash-window audit's executable half: each sweep category corresponds
to a documented window in failure_modes.md §4; repair_unambiguous finishes
the sibling sweep a crashed cascade owed its live `proposed` strategies.
"""
from __future__ import annotations

import sqlite3

import pytest

from Tooling.state import consistency, db, transitions


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at) "
              "VALUES ('p',datetime('now'))")
    yield c
    c.close()


def _goal(c, slug, status="open", origin="backward", detached=0):
    g = db.insert_goal(c, problem="p", slug=slug,
                       lean_path=f"Problems/p/proofs/L_{slug}.lean",
                       statement="T", origin=origin, kind="theorem")
    c.execute("UPDATE goals SET status=?, detached=? WHERE id=?",
              (status, detached, g))
    c.commit()
    return g


def _strategy(c, goal_id, status="proposed"):
    sid = db.insert_strategy(c, goal_id=goal_id, lean_path="x.lean",
                             created_by="test")
    c.execute("UPDATE strategies SET status=? WHERE id=?", (status, sid))
    c.commit()
    return sid


def _link(c, sid, gid):
    c.execute("INSERT INTO strategy_subgoals (strategy_id, subgoal_id, "
              "position) VALUES (?,?,0)", (sid, gid))
    c.commit()


def test_sweep_clean_on_healthy_tree(conn):
    root = _goal(conn, "main", status="open", origin="root")
    s = _strategy(conn, root)
    sub = _goal(conn, "sub", status="open")
    _link(conn, s, sub)
    conn.execute("UPDATE goals SET status='attempting' WHERE id=?", (root,))
    conn.commit()
    sweep = consistency.consistency_sweep(conn)
    assert all(not rows for rows in sweep.values()), sweep


def test_sweep_flags_each_window(conn):
    root = _goal(conn, "main", status="proved", origin="root")
    # A2: succeeded strategy under unproved goal
    g_a2 = _goal(conn, "a2", status="attempting")
    _strategy(conn, g_a2, status="succeeded")
    # A3/F3: live proposed strategy under terminal goal
    g_a3 = _goal(conn, "a3", status="proved")
    _strategy(conn, g_a3, status="proposed")
    # open goal with proposed strategy (recovery predicate as assertion)
    g_op = _goal(conn, "op", status="open")
    _strategy(conn, g_op, status="proposed")
    # attempting goal with no live strategy
    g_att = _goal(conn, "att", status="attempting")
    # unreachable zombie: open, not detached, no live chain to a root
    g_zombie = _goal(conn, "zombie", status="open")
    # revival pending: shelved goal whose alias target is proved
    g_x = _goal(conn, "canon", status="proved")
    g_sh = _goal(conn, "sh", status="shelved")
    conn.execute("UPDATE goals SET alias_target_id=? WHERE id=?",
                 (g_x, g_sh))
    conn.commit()

    sweep = consistency.consistency_sweep(conn)
    assert [r["goal_id"] for r in
            sweep["succeeded_strategy_unproved_goal"]] == [g_a2]
    assert [r["goal_id"] for r in
            sweep["live_strategy_terminal_goal"]] == [g_a3]
    assert [r["goal_id"] for r in
            sweep["open_with_proposed_strategy"]] == [g_op]
    # 'att' only: g_a2 is attempting too but owns a succeeded strategy.
    assert [r["goal_id"] for r in
            sweep["attempting_without_live_strategy"]] == [g_att]
    # Every alive (open/attempting), non-root, non-detached goal with no
    # live chain to a root — exact, so a predicate that over-reports (e.g.
    # stops excluding detached seeds or terminal goals) fails here.
    zombies = {r["goal_id"] for r in sweep["unreachable_alive_goal"]}
    assert zombies == {g_a2, g_op, g_att, g_zombie}
    assert [r["goal_id"] for r in sweep["revival_pending"]] == [g_sh]


def test_repair_unambiguous_finishes_the_owed_sweep(conn, monkeypatch):
    monkeypatch.setenv("ASTERISM_STRICT_TRANSITIONS", "1")
    # proved parent → losing sibling gets superseded
    g_won = _goal(conn, "won", status="proved")
    s_lose = _strategy(conn, g_won, status="proposed")
    # shelved parent → inward-kill it owed → dead
    g_shelved = _goal(conn, "sh2", status="shelved")
    s_dead = _strategy(conn, g_shelved, status="proposed")
    # stalled under terminal: report-only, must NOT be touched
    g_dead = _goal(conn, "gd", status="dead")
    s_stall = _strategy(conn, g_dead, status="stalled")
    # healthy live strategy under attempting goal: untouched
    g_live = _goal(conn, "live", status="attempting")
    s_live = _strategy(conn, g_live, status="proposed")

    fixed = consistency.repair_unambiguous(conn)
    assert fixed == {"superseded": 1, "dead": 1}

    def stat(sid):
        return conn.execute("SELECT status FROM strategies WHERE id=?",
                            (sid,)).fetchone()["status"]
    assert stat(s_lose) == "superseded"
    assert stat(s_dead) == "dead"
    assert stat(s_stall) == "stalled"     # no legal edge — report-only
    assert stat(s_live) == "proposed"
    # sweep: the proposed-under-terminal rows are gone; stalled remains
    sweep = consistency.consistency_sweep(conn)
    left = [(r["strategy_id"], r["strategy_status"])
            for r in sweep["live_strategy_terminal_goal"]]
    assert left == [(s_stall, "stalled")]


def test_revival_resume_recognizes_own_alias(tmp_path, conn, monkeypatch):
    """B1 root fix: a crashed revival's own half-write (file already the
    exact alias for THIS canonical) is resumed, not refused; foreign
    content is still refused."""
    from Tooling.quality import verify as qverify
    from Tooling.lsp import lifecycle as gl
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    canon = _goal(conn, "canon2", status="proved")
    (proofs / "L_canon2.lean").write_text(
        "import Mathlib\ntheorem canon2 : T := by trivial\n",
        encoding="utf-8")
    sh = _goal(conn, "sh3", status="shelved")
    conn.execute("UPDATE goals SET alias_target_id=? WHERE id=?",
                 (canon, sh))
    conn.commit()
    alias_body = ("import Mathlib\n"
                  "import Problems.p.proofs.L_canon2\n"
                  "theorem sh3 : T := by apply canon2 <;> assumption\n")
    (proofs / "L_sh3.lean").write_text(alias_body, encoding="utf-8")
    monkeypatch.setattr(gl, "verify_file",
                        lambda *a, **k: {"ok": True, "diagnostics": []})
    ok = qverify._revive_shelved_alias(
        conn, tmp_path, shelved_id=sh, canonical_id=canon)
    assert ok
    assert conn.execute("SELECT status FROM goals WHERE id=?",
                        (sh,)).fetchone()["status"] == "proved"
    # foreign content (a manual partial proof) → still refused
    sh2 = _goal(conn, "sh4", status="shelved")
    conn.execute("UPDATE goals SET alias_target_id=? WHERE id=?",
                 (canon, sh2))
    conn.commit()
    (proofs / "L_sh4.lean").write_text(
        "import Mathlib\ntheorem sh4 : T := by exact my_own_proof\n",
        encoding="utf-8")
    assert not qverify._revive_shelved_alias(
        conn, tmp_path, shelved_id=sh2, canonical_id=canon)
