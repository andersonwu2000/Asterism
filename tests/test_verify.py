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

from Tooling.state import db
from Tooling.core import dispatcher
from Tooling.quality import verify


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
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
        statement="True", origin="root", depth=0,
    )


def _seed_strategy_with_proved_subs(
    conn: sqlite3.Connection, *, goal_id: int, sub_count: int = 1,
    scratch_path: str | None = None,
    lean_path: str = "Problems/p/proofs/L_main.lean",
    proposal_md: str = "",
) -> int:
    sid = db.insert_strategy(
        conn, goal_id=goal_id, lean_path=lean_path, created_by="pid",
        scratch_path=scratch_path or f"Problems/p/proofs/_strategy_s.lean",
        proposal_md=proposal_md,
    )
    for i in range(sub_count):
        sub = db.insert_goal(
            conn, problem="p", slug=f"sub_{sid}_{i}",
            lean_path=f"Problems/p/proofs/L_sub_{sid}_{i}.lean",
            statement="T", origin="backward", depth=1,
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

    # conftest's autouse stub already returns ok for verify_file;
    # this is a no-op override, but kept explicit so the test reads
    # as "this path expects the gateway to say ok".
    pass  # verify_file stubbed via conftest._stub_axiom_probe_by_default
    monkeypatch.setattr(verify, "lean_path_to_module",
                        lambda *a, **kw: "Problems.p.proofs._strategy_s")
    monkeypatch.setattr(verify, "promote_to_alias",
                        lambda *a, **kw: None)
    monkeypatch.setattr(verify, "rollback_promote",
                        lambda *a, **kw: None)

    out = verify.verify_strategy(conn, workspace=tmp_path, strategy_id=sid)
    assert out == "proved"


def test_verify_strategy_propagates_proposal_md_as_annotation(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a strategy wins Verify, its `proposal_md` (already a raw
    Lean line-comment block — Backward parse extracted the leading
    comments from patch.lean directly under Phase 6) propagates into
    the parent goal's `.lean` source verbatim via promote_to_alias's
    `annotation` keyword."""
    gid = _seed_goal(conn, slug="parent_main")
    sid = _seed_strategy_with_proved_subs(
        conn, goal_id=gid,
        proposal_md="-- parent_main: split into A + B via "
                     "cross-product Lagrange\n",
    )
    scratch_abs = tmp_path / "Problems/p/proofs/_strategy_s.lean"
    scratch_abs.parent.mkdir(parents=True)
    scratch_abs.write_text("-- stub", encoding="utf-8")

    captured: dict[str, str] = {}

    def fake_promote(*a, **kw):
        captured["annotation"] = kw.get("annotation", "")
        return None
    # conftest's autouse stub already returns ok for verify_file;
    # this is a no-op override, but kept explicit so the test reads
    # as "this path expects the gateway to say ok".
    pass  # verify_file stubbed via conftest._stub_axiom_probe_by_default
    monkeypatch.setattr(verify, "lean_path_to_module",
                        lambda *a, **kw: "Problems.p.proofs._strategy_s")
    monkeypatch.setattr(verify, "promote_to_alias", fake_promote)
    monkeypatch.setattr(verify, "rollback_promote",
                        lambda *a, **kw: None)

    out = verify.verify_strategy(conn, workspace=tmp_path, strategy_id=sid)
    assert out == "proved"
    assert captured["annotation"].startswith(
        "-- parent_main: split into A + B via cross-product Lagrange"
    )


def test_verify_strategy_empty_proposal_yields_empty_annotation(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A strategy with empty `proposal_md` propagates an empty
    annotation — `promote_to_alias` writes the alias without any
    comment block. (Backward emits `agent_no_annotation` upstream so
    this case is rare in practice, but the verify path stays defensive
    against legacy / pre-Phase-2 strategies.)"""
    gid = _seed_goal(conn, slug="parent_main")
    sid = _seed_strategy_with_proved_subs(
        conn, goal_id=gid, proposal_md="",
    )
    scratch_abs = tmp_path / "Problems/p/proofs/_strategy_s.lean"
    scratch_abs.parent.mkdir(parents=True)
    scratch_abs.write_text("-- stub", encoding="utf-8")

    captured: dict[str, str] = {}

    def fake_promote(*a, **kw):
        captured["annotation"] = kw.get("annotation", "")
        return None
    # conftest's autouse stub already returns ok for verify_file;
    # this is a no-op override, but kept explicit so the test reads
    # as "this path expects the gateway to say ok".
    pass  # verify_file stubbed via conftest._stub_axiom_probe_by_default
    monkeypatch.setattr(verify, "lean_path_to_module",
                        lambda *a, **kw: "Problems.p.proofs._strategy_s")
    monkeypatch.setattr(verify, "promote_to_alias", fake_promote)
    monkeypatch.setattr(verify, "rollback_promote",
                        lambda *a, **kw: None)

    out = verify.verify_strategy(conn, workspace=tmp_path, strategy_id=sid)
    assert out == "proved"
    assert captured["annotation"] == ""


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


def test_housekeeping_retry_leaves_strategy_in_ready_state(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transient infra failure: outcome 'retry' does NOT mutate strategy
    or goal state — strategy stays ready_for_verify, attempts unchanged,
    goal status unchanged. Housekeeping breaks out of its inner loop to
    defer to the next dispatcher tick rather than busy-spin."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "attempting")
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    starting_attempts = db.get_goal(conn, gid)["attempts"]
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "retry")

    counts = verify.verify_housekeeping(conn, workspace=tmp_path)
    assert counts["retry"] == 1
    assert counts["dead"] == 0
    assert counts["proved"] == 0
    # Strategy stays 'proposed' (the on-disk status for "ready_for_verify")
    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sid,)).fetchone()
    assert s["status"] == "proposed"
    # Goal unchanged
    g = db.get_goal(conn, gid)
    assert g["status"] == "attempting"
    assert g["attempts"] == starting_attempts


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


def test_housekeeping_dead_at_threshold_defers_when_sibling_alive(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """verify dead at threshold MUST defer terminal when a sibling
    strategy is still in-flight (e.g. Strategist parallel inject):
    killing the goal here would kill that working sibling. Attempts
    still records the failure; deferred terminal fires later when the
    sibling resolves naturally.
    """
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "attempting")
    sid = _seed_strategy_with_proved_subs(conn, goal_id=gid)
    # In-flight sibling: has an unproved sub-goal so it's NOT
    # ready_for_verify yet (won't be picked up by housekeeping in this
    # tick); represents a parallel-inject worker still computing.
    sibling = db.insert_strategy(
        conn, goal_id=gid,
        lean_path="Problems/p/proofs/L_g0.lean",
        scratch_path="Problems/p/proofs/_strategy_sibling.lean",
        created_by="pid_sib",
    )
    pending_sub = db.insert_goal(
        conn, problem="p", slug="pending_sub_for_sibling",
        lean_path="Problems/p/proofs/L_pending.lean",
        statement="T", origin="backward", depth=1,
    )
    db.link_subgoal(conn, strategy_id=sibling, subgoal_id=pending_sub, position=0)
    for _ in range(dispatcher.SHELVE_THRESHOLD - 1):
        db.increment_goal_attempts(conn, gid)
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "dead")

    verify.verify_housekeeping(conn, workspace=tmp_path)
    grand_row = db.get_goal(conn, gid)
    assert grand_row["status"] == "attempting"  # NOT shelved
    assert grand_row["attempts"] == dispatcher.SHELVE_THRESHOLD
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sibling,),
    ).fetchone()["status"] == "proposed"  # sibling untouched


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
        statement="T", origin="backward", depth=1,
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

    counts = verify.verify_housekeeping(conn, workspace=tmp_path)
    assert counts["proved"] == 2  # parent_sid + grand_sid in one call
    assert db.get_goal(conn, parent_gid)["status"] == "proved"
    assert db.get_goal(conn, grand_gid)["status"] == "proved"


def test_housekeeping_no_op_when_nothing_ready(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """No strategies ready → return zero counts, no DB mutations."""
    counts = verify.verify_housekeeping(conn, workspace=tmp_path)
    assert counts == {"proved": 0, "dead": 0, "superseded": 0,
                       "retry": 0, "revived": 0}


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
        statement="T", origin="backward", depth=1,
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

    counts = verify.verify_housekeeping(
        conn, workspace=tmp_path, max_iters=1)
    # Only the bottom strategy gets processed in 1 iter; the freed
    # grandparent strategy waits for the next call.
    assert counts["proved"] == 1
    assert db.get_goal(conn, grand_gid)["status"] != "proved"


# ---------------------------------------------------------------------
# G1 — shelved-revival pass
# ---------------------------------------------------------------------

def _seed_shelved_aliased_to_proved_forward(
    conn: sqlite3.Connection, tmp_path: Path, *,
    parent_status: str = "attempting",
) -> tuple[int, int, int]:
    """Build the brouwer-shape minimal scenario:
      root → parent_strategy → shelved sub-goal S (status='shelved',
                              aliased to X)
      detached Forward output X (status='proved') with a small lean file

    Returns (root_id, shelved_id, forward_id).
    Lean files exist so `build_alias_content` can rewrite S in place.
    """
    _seed_problem(conn)
    root = _seed_goal(conn)
    db.update_goal_status(conn, root, "attempting")
    # Backward sub-goal (shelved) under root's strategy
    parent_sid = db.insert_strategy(
        conn, goal_id=root,
        lean_path="Problems/p/proofs/L_main.lean",
        scratch_path="Problems/p/proofs/_strategy_root.lean",
        created_by="pid")
    shelved = db.insert_goal(
        conn, problem="p", slug="shelved_s",
        lean_path="Problems/p/proofs/L_shelved_s.lean",
        statement="X", origin="backward", depth=1,
    )
    db.update_goal_status(conn, shelved, "shelved")
    db.link_subgoal(conn, strategy_id=parent_sid, subgoal_id=shelved,
                    position=0)
    # Forward output (proved, detached)
    forward = db.insert_goal(
        conn, problem="p", slug="forward_x",
        lean_path="Problems/p/proofs/L_forward_x.lean",
        statement="X", origin="forward", depth=0,
    )
    db.set_goal_detached(conn, forward, True)
    db.update_goal_status(conn, forward, "proved")
    db.set_alias_target(conn, shelved, forward)
    # Write on-disk lean files (S has the sorry stub; X is a one-liner)
    pdir = tmp_path / "Problems" / "p" / "proofs"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "L_shelved_s.lean").write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem shelved_s : True := by sorry\n"
        "end Problems.p\n", encoding="utf-8")
    (pdir / "L_forward_x.lean").write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem forward_x : True := by trivial\n"
        "end Problems.p\n", encoding="utf-8")
    return root, shelved, forward


def test_pending_shelved_revivals_finds_proved_canonical_links(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """_pending_shelved_revivals returns (shelved, canonical) where
    shelved.alias_target_id = canonical AND canonical.status='proved'."""
    _, shelved, forward = _seed_shelved_aliased_to_proved_forward(
        conn, tmp_path)
    pairs = verify._pending_shelved_revivals(conn)
    assert pairs == [(shelved, forward)]


def test_pending_shelved_revivals_excludes_unproved_canonical(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """If the canonical is still 'open', the link is pending; revival
    pass must NOT trigger yet."""
    _, shelved, forward = _seed_shelved_aliased_to_proved_forward(
        conn, tmp_path)
    # Flip canonical back to open
    db.update_goal_status(conn, forward, "open")
    pairs = verify._pending_shelved_revivals(conn)
    assert pairs == []


def test_pending_shelved_revivals_excludes_already_revived(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Once S has flipped to 'proved' the link is consumed — no
    re-revival on subsequent ticks."""
    _, shelved, _ = _seed_shelved_aliased_to_proved_forward(
        conn, tmp_path)
    db.update_goal_status(conn, shelved, "proved")
    pairs = verify._pending_shelved_revivals(conn)
    assert pairs == []


def test_revive_shelved_alias_writes_alias_body_and_flips_status(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """`_revive_shelved_alias` rewrites S.lean_path with the
    `apply <canonical> <;> assumption` body and transitions S to
    'proved' via the centralized terminal hook."""
    _, shelved, forward = _seed_shelved_aliased_to_proved_forward(
        conn, tmp_path)
    ok = verify._revive_shelved_alias(
        conn, tmp_path, shelved_id=shelved, canonical_id=forward)
    assert ok is True
    body = (tmp_path / "Problems/p/proofs/L_shelved_s.lean").read_text(
        encoding="utf-8")
    assert "apply forward_x" in body
    assert "import Problems.p.proofs.L_forward_x" in body
    assert db.get_goal(conn, shelved)["status"] == "proved"


def test_revive_shelved_alias_refuses_when_sorry_stub_missing(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """If S's lean file body doesn't carry `:= by sorry` (manual edit /
    partial proof), refuse to overwrite. Link stays for operator
    inspection; status untouched."""
    _, shelved, forward = _seed_shelved_aliased_to_proved_forward(
        conn, tmp_path)
    (tmp_path / "Problems/p/proofs/L_shelved_s.lean").write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem shelved_s : True := by trivial\n"
        "end Problems.p\n", encoding="utf-8")
    ok = verify._revive_shelved_alias(
        conn, tmp_path, shelved_id=shelved, canonical_id=forward)
    assert ok is False
    assert db.get_goal(conn, shelved)["status"] == "shelved"


def test_housekeeping_revives_shelved_then_chains_parent_strategy(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: shelved S aliased to proved X gets revived. S → proved
    makes parent strategy's all-subs-proved gate fire on the next loop
    iteration; verify_strategy (stubbed 'proved') closes parent goal."""
    root, shelved, forward = _seed_shelved_aliased_to_proved_forward(
        conn, tmp_path)
    # Make scratch file exist so verify_strategy's pre-check passes if
    # the parent strategy gets re-evaluated.
    scratch = tmp_path / "Problems/p/proofs/_strategy_root.lean"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_text("-- stub", encoding="utf-8")
    # Stub verify_strategy so we don't shell out to lake.
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "proved")

    counts = verify.verify_housekeeping(conn, workspace=tmp_path)
    assert counts["revived"] >= 1
    assert db.get_goal(conn, shelved)["status"] == "proved"
    # Parent strategy fired in a later iteration (root proved).
    assert db.get_goal(conn, root)["status"] == "proved"
    assert forward  # silence unused


def test_housekeeping_no_revivals_when_canonical_unproved(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Link exists but canonical X is still open → revival pass quiet,
    S stays shelved, no chain to parent."""
    root, shelved, forward = _seed_shelved_aliased_to_proved_forward(
        conn, tmp_path)
    db.update_goal_status(conn, forward, "open")
    monkeypatch.setattr(verify, "verify_strategy",
                        lambda *a, **kw: "proved")

    counts = verify.verify_housekeeping(conn, workspace=tmp_path)
    assert counts["revived"] == 0
    assert db.get_goal(conn, shelved)["status"] == "shelved"
    assert db.get_goal(conn, root)["status"] in ("open", "attempting")


