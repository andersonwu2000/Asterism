"""F56 — strategy verification as dispatcher housekeeping.

Replaces `worker_kind="Verify"` with an inline framework operation:
`verify.verify_strategy` (lake build + alias write + lake build), and
the orchestrator `verify.verify_housekeeping` that polls
`strategies_ready_for_verify`, runs verify_strategy on each, applies
the state transitions previously living in `cascade_one(kind="Verify")`,
and recurses to follow chain-promotions within a single dispatcher tick.

These tests cover:
  - `verify_strategy` per-outcome (proved / dead / superseded)
  - `verify_housekeeping` state transitions (mirror legacy cascade behavior)
  - Chain follow-up (parent proved → upper strategy ready → handled in
    the same housekeeping call)
  - Sibling supersede on win
  - Cascade-shelve on dead with attempts >= SHELVE_THRESHOLD
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import db, dispatcher, verify


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()),
    )
    conn.commit()


def _seed_goal(conn: sqlite3.Connection, *, slug: str = "main",
               problem: str = "p", lean_path: str | None = None) -> int:
    if conn.execute(
            "SELECT 1 FROM problems WHERE name = ?", (problem,)
    ).fetchone() is None:
        _seed_problem(conn, problem)
    return db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=lean_path or f"Problems/{problem}/proofs/L_{slug}.lean",
        statement="True", origin="root", difficulty=2, depth=0,
    )


def _seed_strategy_with_proved_subs(
    conn: sqlite3.Connection, *, goal_id: int, sub_count: int = 1,
    scratch_path: str | None = None,
    lean_path: str = "Problems/p/proofs/L_main.lean",
) -> int:
    sid = db.insert_strategy(
        conn, goal_id=goal_id, lean_path=lean_path, created_by="pid",
        scratch_path=scratch_path or f"Problems/p/proofs/_strategy_s.lean",
    )
    for i in range(sub_count):
        sub = db.insert_goal(
            conn, problem="p", slug=f"sub_{sid}_{i}",
            lean_path=f"Problems/p/proofs/L_sub_{sid}_{i}.lean",
            statement="T", origin="backward", difficulty=1, depth=1,
        )
        db.update_goal_status(conn, sub, "proved")
        db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub, position=i)
    return sid


# ---------------------------------------------------------------------
# verify_strategy — per-outcome
# ---------------------------------------------------------------------

def test_verify_strategy_proved_when_lake_builds(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both lake builds pass + alias write succeeds → 'proved'."""
    gid = _seed_goal(conn)
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)

    # Pretend the on-disk files exist (verify_strategy probes scratch
    # via Path.exists). Stub lake_build + promote_to_alias so we don't
    # actually invoke lake / touch files.
    scratch_abs = tmp_path / "Problems/p/proofs/_strategy_s.lean"
    scratch_abs.parent.mkdir(parents=True)
    scratch_abs.write_text("-- stub", encoding="utf-8")

    monkeypatch.setattr(verify, "lake_build", lambda *a, **kw: (True, ""))
    monkeypatch.setattr(verify, "lean_path_to_module",
                        lambda *a, **kw: "Problems.p.proofs._strategy_s")
    monkeypatch.setattr(verify, "promote_to_alias",
                        lambda *a, **kw: None)
    monkeypatch.setattr(verify, "rollback_promote",
                        lambda *a, **kw: None)

    out = verify.verify_strategy(conn, workspace=tmp_path, strategy_id=sid)
    assert out == "proved"


def test_verify_strategy_dead_when_step1_fails(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 1 lake_build fail → 'dead' (no F41 retry; F56 retired it)."""
    gid = _seed_goal(conn)
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    scratch_abs = tmp_path / "Problems/p/proofs/_strategy_s.lean"
    scratch_abs.parent.mkdir(parents=True)
    scratch_abs.write_text("-- stub", encoding="utf-8")
    monkeypatch.setattr(verify, "lake_build",
                        lambda *a, **kw: (False, "elaboration drift"))
    out = verify.verify_strategy(conn, workspace=tmp_path, strategy_id=sid)
    assert out == "dead"


def test_verify_strategy_dead_when_step3_fails(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 3 (alias-form parent build) fails → 'dead', and rollback
    is invoked to restore the parent stub."""
    gid = _seed_goal(conn)
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    scratch_abs = tmp_path / "Problems/p/proofs/_strategy_s.lean"
    scratch_abs.parent.mkdir(parents=True)
    scratch_abs.write_text("-- stub", encoding="utf-8")
    calls = {"lake": 0, "rollback": 0}

    def fake_lake(*a, **kw):
        calls["lake"] += 1
        # First call (Step 1) passes; second (Step 3) fails
        return (True, "") if calls["lake"] == 1 else (False, "parent fail")
    monkeypatch.setattr(verify, "lake_build", fake_lake)
    monkeypatch.setattr(verify, "lean_path_to_module",
                        lambda *a, **kw: "Problems.p.proofs._strategy_s")
    monkeypatch.setattr(verify, "promote_to_alias",
                        lambda *a, **kw: None)
    monkeypatch.setattr(verify, "rollback_promote",
                        lambda *a, **kw: calls.__setitem__("rollback", 1))

    out = verify.verify_strategy(conn, workspace=tmp_path, strategy_id=sid)
    assert out == "dead"
    assert calls["rollback"] == 1


def test_verify_strategy_superseded_when_goal_already_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """An OR-sibling already won → goal proved, this strategy moot."""
    gid = _seed_goal(conn)
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    db.update_goal_status(conn, gid, "proved")
    out = verify.verify_strategy(conn, workspace=tmp_path, strategy_id=sid)
    assert out == "superseded"


def test_verify_strategy_superseded_when_strategy_marked_superseded(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    gid = _seed_goal(conn)
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    conn.execute("UPDATE strategies SET status='superseded' WHERE id=?",
                 (sid,))
    conn.commit()
    out = verify.verify_strategy(conn, workspace=tmp_path, strategy_id=sid)
    assert out == "superseded"


def test_verify_strategy_dead_when_scratch_file_missing(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """scratch_path recorded but file vanished (manual edit / disk
    gremlin) → 'dead' rather than crashing."""
    gid = _seed_goal(conn)
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    # Don't create the scratch file
    out = verify.verify_strategy(conn, workspace=tmp_path, strategy_id=sid)
    assert out == "dead"


# ---------------------------------------------------------------------
# verify_housekeeping — state transitions
# ---------------------------------------------------------------------

def test_housekeeping_proved_marks_strategy_and_goal(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """proved outcome: strategy → succeeded, goal → proved (mirrors the
    legacy cascade_one Verify=proved branch)."""
    gid = _seed_goal(conn)
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "proved")
    # Block the F22 playbook hook (LLM call) — irrelevant to this test
    from Tooling import playbook
    monkeypatch.setattr(playbook, "maybe_record_idiom",
                        lambda *a, **kw: None)

    counts = verify.verify_housekeeping(conn, workspace=tmp_path)
    assert counts["proved"] == 1
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sid,),
    ).fetchone()["status"] == "succeeded"
    assert db.get_goal(conn, gid)["status"] == "proved"


def test_housekeeping_proved_supersedes_siblings(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Winner strategy proves → sibling strategies on same goal go
    'superseded'. Mirrors `mark_other_strategies_superseded` previously
    called in cascade_one Verify branch."""
    gid = _seed_goal(conn)
    s_winner = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    s_loser = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid_l")
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "proved")
    from Tooling import playbook
    monkeypatch.setattr(playbook, "maybe_record_idiom",
                        lambda *a, **kw: None)

    verify.verify_housekeeping(conn, workspace=tmp_path)
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s_loser,),
    ).fetchone()["status"] == "superseded"


def test_housekeeping_dead_marks_strategy_and_increments_attempts(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dead outcome: strategy → dead, goal attempts++ (mirrors cascade
    Verify=failed branch). Goal stays open since no other live strategy."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "attempting")
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "dead")

    verify.verify_housekeeping(conn, workspace=tmp_path)
    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sid,)).fetchone()
    g = db.get_goal(conn, gid)
    assert s["status"] == "dead"
    assert g["attempts"] == 1
    assert g["status"] == "open"  # reopened (no other live strategy)


def test_housekeeping_dead_keeps_attempting_when_other_strategy_live(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sibling 'proposed' strategy still alive → goal stays 'attempting'."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "attempting")
    sid_dying = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid_alt")
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "dead")

    verify.verify_housekeeping(conn, workspace=tmp_path)
    assert db.get_goal(conn, gid)["status"] == "attempting"


def test_housekeeping_dead_shelves_at_threshold(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When goal attempts hit SHELVE_THRESHOLD on the dead transition,
    the goal shelves and `_propagate_shelve` runs."""
    gid = _seed_goal(conn)
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    # Push attempts to threshold-1 so this dead transition triggers shelve
    for _ in range(dispatcher.SHELVE_THRESHOLD - 1):
        db.increment_goal_attempts(conn, gid)
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "dead")

    verify.verify_housekeeping(conn, workspace=tmp_path)
    assert db.get_goal(conn, gid)["status"] == "shelved"


def test_housekeeping_chain_promotes_through_layers(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two-level chain: leaf strategy proved → its parent goal becomes
    proved → grandparent strategy now ready_for_verify (was blocked
    because that leaf was its only unproved sub) → housekeeping should
    handle BOTH in the same call.
    """
    # Grandparent goal + strategy whose only sub-goal is `parent_gid`
    grand_gid = _seed_goal(conn, slug="grand")
    grand_sid = db.insert_strategy(
        conn, goal_id=grand_gid,
        lean_path="Problems/p/proofs/L_grand.lean",
        scratch_path="Problems/p/proofs/_strategy_grand.lean",
        created_by="pid_grand",
    )
    # Parent goal + strategy whose sub-goal is already 'proved'
    parent_gid = db.insert_goal(
        conn, problem="p", slug="parent",
        lean_path="Problems/p/proofs/L_parent.lean",
        statement="T", origin="backward", difficulty=2, depth=1,
    )
    db.link_subgoal(
        conn, strategy_id=grand_sid, subgoal_id=parent_gid, position=0)
    parent_sid = _seed_strategy_with_proved_subs(
        conn, goal_id=parent_gid,
        lean_path="Problems/p/proofs/L_parent.lean",
        scratch_path="Problems/p/proofs/_strategy_parent.lean",
    )

    # Stub verify_strategy to always return "proved"
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "proved")
    from Tooling import playbook
    monkeypatch.setattr(playbook, "maybe_record_idiom",
                        lambda *a, **kw: None)

    counts = verify.verify_housekeeping(conn, workspace=tmp_path)
    assert counts["proved"] == 2  # parent_sid + grand_sid in one call
    assert db.get_goal(conn, parent_gid)["status"] == "proved"
    assert db.get_goal(conn, grand_gid)["status"] == "proved"


def test_housekeeping_no_op_when_nothing_ready(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """No strategies ready → return zero counts, no DB mutations."""
    counts = verify.verify_housekeeping(conn, workspace=tmp_path)
    assert counts == {"proved": 0, "dead": 0, "superseded": 0}


def test_housekeeping_caps_iterations(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`max_iters` bounds chain depth so a pathological cascade can't
    monopolize the dispatcher tick. Strategies left over wait for the
    next tick."""
    # Build a 3-level chain but cap to 1 iter
    grand_gid = _seed_goal(conn, slug="grand")
    grand_sid = db.insert_strategy(
        conn, goal_id=grand_gid,
        lean_path="Problems/p/proofs/L_grand.lean",
        scratch_path="Problems/p/proofs/_strategy_grand.lean",
        created_by="pid_g")
    parent_gid = db.insert_goal(
        conn, problem="p", slug="parent",
        lean_path="Problems/p/proofs/L_parent.lean",
        statement="T", origin="backward", difficulty=2, depth=1,
    )
    db.link_subgoal(
        conn, strategy_id=grand_sid, subgoal_id=parent_gid, position=0)
    _seed_strategy_with_proved_subs(
        conn, goal_id=parent_gid,
        lean_path="Problems/p/proofs/L_parent.lean",
        scratch_path="Problems/p/proofs/_strategy_parent.lean",
    )

    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "proved")
    from Tooling import playbook
    monkeypatch.setattr(playbook, "maybe_record_idiom",
                        lambda *a, **kw: None)

    counts = verify.verify_housekeeping(
        conn, workspace=tmp_path, max_iters=1)
    # Only the bottom strategy gets processed in 1 iter; the freed
    # grandparent strategy waits for the next call.
    assert counts["proved"] == 1
    assert db.get_goal(conn, grand_gid)["status"] != "proved"


def test_housekeeping_playbook_failure_does_not_abort(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """playbook.maybe_record_idiom is best-effort — its exception must
    not prevent housekeeping from continuing through subsequent ready
    strategies."""
    gid_a = _seed_goal(conn, slug="a")
    sid_a = _seed_strategy_with_proved_subs(
        conn, goal_id=gid_a,
        lean_path="Problems/p/proofs/L_a.lean",
        scratch_path="Problems/p/proofs/_strategy_a.lean")
    gid_b = _seed_goal(conn, slug="b")
    sid_b = _seed_strategy_with_proved_subs(
        conn, goal_id=gid_b,
        lean_path="Problems/p/proofs/L_b.lean",
        scratch_path="Problems/p/proofs/_strategy_b.lean")

    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "proved")
    from Tooling import playbook

    def boom(*a, **kw):
        raise RuntimeError("LLM unavailable")
    monkeypatch.setattr(playbook, "maybe_record_idiom", boom)

    counts = verify.verify_housekeeping(conn, workspace=tmp_path)
    assert counts["proved"] == 2  # both processed despite playbook errors
