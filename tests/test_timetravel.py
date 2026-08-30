"""`Tooling.experiments.timetravel` — rewind a problem's DB state to a
cutoff instant so a historical wake can be replayed with today's
prompts (experiments 2/3, 2026-08-30: "would the NL layer mint the
fin10 table brick again?").

The rewind is an APPROXIMATION and says so: rows created after the
cutoff are deleted, goal statuses are read back from `goal_events`,
strategies whose goal is no longer proved fall back to `proposed`,
groups touched after the cutoff go back to `active`. It runs on a COPY;
the live DB is never opened for writing.
"""
from __future__ import annotations

import sqlite3

from Tooling.experiments import timetravel as tt
from Tooling.state import db

CUT = "2026-08-26T04:11:05+00:00"
BEFORE = "2026-08-25T12:00:00+00:00"
AFTER = "2026-08-27T00:00:00+00:00"


def _seed(conn: sqlite3.Connection):
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done) VALUES (?, ?, 1)",
                 ("p", BEFORE))
    old = db.insert_goal(conn, problem="p", slug="old", lean_path="Problems/p/proofs/L_old.lean",
                         statement="T", origin="backward", depth=1)
    new = db.insert_goal(conn, problem="p", slug="new", lean_path="Problems/p/proofs/L_new.lean",
                         statement="T", origin="backward", depth=1)
    conn.execute("UPDATE goals SET created_at=? WHERE id=?", (BEFORE, old))
    conn.execute("UPDATE goals SET created_at=? WHERE id=?", (AFTER, new))
    # old goal: open before the cutoff, proved after it
    conn.execute("INSERT INTO goal_events (goal_id, problem, from_status, to_status, event, reason, at)"
                 " VALUES (?,?,?,?,?,?,?)", (old, "p", "open", "attempting", "backward_decomposed", "", BEFORE))
    conn.execute("INSERT INTO goal_events (goal_id, problem, from_status, to_status, event, reason, at)"
                 " VALUES (?,?,?,?,?,?,?)", (old, "p", "attempting", "proved", "set_terminal", "", AFTER))
    db.update_goal_status(conn, old, "proved")
    s_old = db.insert_strategy(conn, goal_id=old, lean_path="Problems/p/proofs/L_old.lean",
                               scratch_path="Problems/p/proofs/_strategy_s1.lean", created_by="x")
    db.update_strategy_status(conn, s_old, "succeeded")
    conn.execute("UPDATE strategies SET created_at=? WHERE id=?", (BEFORE, s_old))
    s_new = db.insert_strategy(conn, goal_id=old, lean_path="Problems/p/proofs/L_old.lean",
                               scratch_path="Problems/p/proofs/_strategy_s2.lean", created_by="x")
    conn.execute("UPDATE strategies SET created_at=? WHERE id=?", (AFTER, s_new))
    db.link_subgoal(conn, strategy_id=s_new, subgoal_id=new, position=0)
    conn.execute("INSERT INTO strategist_decisions (problem, triggered_at_tick, trigger_kind, decision_kind,"
                 " created_at, updated_at) VALUES (?,?,?,?,?,?)", ("p", 1, "routine", "Noop", BEFORE, BEFORE))
    conn.execute("INSERT INTO strategist_decisions (problem, triggered_at_tick, trigger_kind, decision_kind,"
                 " created_at, updated_at) VALUES (?,?,?,?,?,?)", ("p", 2, "routine", "Noop", AFTER, AFTER))
    conn.execute("INSERT INTO programme_revisions (problem, rev, body, status, verdict, dialogue, rounds, created_at)"
                 " VALUES (?,?,?,?,?,?,?,?)", ("p", 1, "b1", "passed", "{}", "[]", 0, BEFORE))
    conn.execute("INSERT INTO programme_revisions (problem, rev, body, status, verdict, dialogue, rounds, created_at)"
                 " VALUES (?,?,?,?,?,?,?,?)", ("p", 2, "b2", "passed", "{}", "[]", 0, AFTER))
    conn.commit()
    return old, new, s_old, s_new


def test_rewind_deletes_post_cutoff_rows_and_rewinds_statuses(conn):
    old, new, s_old, s_new = _seed(conn)
    rep = tt.rewind(conn, problem="p", cutoff=CUT)
    assert db.get_goal(conn, new) is None, "a goal born after the cutoff is gone"
    assert db.get_goal(conn, old)["status"] == "attempting", "read back from goal_events"
    assert conn.execute("SELECT status FROM strategies WHERE id=?", (s_old,)).fetchone()["status"] == "proposed", \
        "its goal is no longer proved, so the win is not yet won"
    assert conn.execute("SELECT COUNT(*) FROM strategies WHERE id=?", (s_new,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM strategy_subgoals WHERE strategy_id=?", (s_new,)).fetchone()[0] == 0
    assert [r["rev"] for r in conn.execute("SELECT rev FROM programme_revisions WHERE problem='p'")] == [1]
    assert conn.execute("SELECT COUNT(*) FROM strategist_decisions WHERE problem='p'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM goal_events WHERE at > ?", (CUT,)).fetchone()[0] == 0
    assert rep["goals_deleted"] == 1 and rep["strategies_deleted"] == 1 and rep["goals_rewound"] == 1


def test_rewind_refuses_the_live_database(tmp_path, monkeypatch):
    """The rewind mutates: only a copy may be opened."""
    import pytest
    live = tmp_path / "asterism.db"
    live.write_text("", encoding="utf-8")
    monkeypatch.setattr(tt, "_looks_live", lambda p: True)
    with pytest.raises(RuntimeError, match="live"):
        tt.open_copy_for_rewind(live)


def test_rewind_clamps_group_clocks_to_the_last_surviving_commit(conn):
    """The trigger derivation reads `groups.last_strategist_at` as the
    batch-acknowledgement ratchet. Clamping it to the cutoff instant
    makes the batch resolved just before look acknowledged, and the
    replay derives `routine` instead of the `inject_batch_done` the
    original wake had. The clock goes back to the last SURVIVING
    strategist commit of that group."""
    _seed(conn)
    conn.execute("INSERT INTO groups (problem, charter, status, created_at, updated_at,"
                 " last_routine_at, last_strategist_at) VALUES (?,?,?,?,?,?,?)",
                 ("p", "c", "active", BEFORE, AFTER, AFTER, AFTER))
    gid = conn.execute("SELECT id FROM groups WHERE problem='p'").fetchone()["id"]
    conn.execute("UPDATE strategist_decisions SET group_id=? WHERE problem='p'", (gid,))
    conn.commit()
    tt.rewind(conn, problem="p", cutoff=CUT)
    g = conn.execute("SELECT last_strategist_at, last_routine_at FROM groups WHERE id=?", (gid,)).fetchone()
    assert g["last_strategist_at"] == BEFORE, "the surviving decision's created_at, not the cutoff"
    assert g["last_routine_at"] <= BEFORE


def test_prune_proof_files_removes_files_of_deleted_rows(tmp_path, conn):
    """Files on disk must match the rewound DB: a brick or strategy
    file born after the cutoff would still show in CATALOG / inspect."""
    import shutil
    old, new, s_old, s_new = _seed(conn)
    snap = tmp_path / "snap.db"
    snap_conn = sqlite3.connect(snap)
    conn.backup(snap_conn); snap_conn.close()
    proofs = tmp_path / "ws" / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    for name in ("L_old.lean", "L_new.lean", "_strategy_s1.lean", "_strategy_s2.lean", "L_unrelated.lean"):
        (proofs / name).write_text("x", encoding="utf-8")
    tt.rewind(conn, problem="p", cutoff=CUT)
    removed = tt.prune_proof_files(conn, snapshot_db=snap, workspace=tmp_path / "ws", problem="p")
    assert sorted(removed) == ["L_new.lean", "_strategy_s2.lean"]
    assert (proofs / "L_old.lean").exists() and (proofs / "_strategy_s1.lean").exists()
    assert (proofs / "L_unrelated.lean").exists(), "files the DB never knew are left alone"


def test_refresh_derived_files_rewrites_tree_without_the_deleted_goals(tmp_path, conn):
    """Experiment 3, first run (2026-08-30): the scratch DB was rewound
    but `Problems/<p>/TREE.md` was the snapshot's file — it still listed
    the goal the replayed proposal was about to mint, and the judge's
    projection copies TREE.md verbatim, so the judge rebutted the
    proposal as 'duplicate work'. The rendered files are derived from
    the DB and must be re-derived after the rewind."""
    old, new, s_old, s_new = _seed(conn)
    pdir = tmp_path / "ws" / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "TREE.md").write_text("- new [g%d] — stale\n- old [g%d]\n" % (new, old),
                                  encoding="utf-8")
    tt.rewind(conn, problem="p", cutoff=CUT)
    written = tt.refresh_derived_files(conn, workspace=tmp_path / "ws", problem="p")
    tree = (pdir / "TREE.md").read_text(encoding="utf-8")
    assert f"[g{new}]" not in tree and "stale" not in tree
    assert f"[g{old}]" in tree
    assert any(p.name == "TREE.md" for p in written)
