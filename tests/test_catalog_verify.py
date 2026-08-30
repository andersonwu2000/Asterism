"""`asterism catalog-verify` — the standing full cold build (owner ruling
2026-08-30, task #231 fix 4; the first stage of the kernel-replay
end-game gate).

The 2026-08-30 flagship olean rebuild was the first time union_closed's
4,828 proved bricks were cold-built together; it found bricks that do
not compile, and the framework had no surface that would ever have
said so. This command builds every proof module of a problem through
the lake build lease, maps each failing module back to its strategy or
goal, reports, and — on `--rollback` — hands each to the existing
`rollback_cascade_chain` (no new state: the culprit dies, its goal
reopens, upstream re-verifies). It refuses to write while a daemon
owns the database.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.core.cli import catalog_verify as cv
from Tooling.state import db


def _seed(conn, tmp_path):
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done) "
                 "VALUES (?, ?, 1)", ("p", db.now()))
    ok = db.insert_goal(conn, problem="p", slug="fine",
                        lean_path="Problems/p/proofs/L_fine.lean",
                        statement="T", origin="backward", depth=1)
    bad = db.insert_goal(conn, problem="p", slug="bad_alias",
                         lean_path="Problems/p/proofs/L_bad_alias.lean",
                         statement="T", origin="backward", depth=1)
    fwd = db.insert_goal(conn, problem="p", slug="bad_forward",
                         lean_path="Problems/p/proofs/L_bad_forward.lean",
                         statement="T", origin="forward", depth=1)
    for g in (ok, bad, fwd):
        db.update_goal_status(conn, g, "proved")
    sid = db.insert_strategy(conn, goal_id=bad,
                             lean_path="Problems/p/proofs/L_bad_alias.lean",
                             scratch_path="Problems/p/proofs/_strategy_s77.lean",
                             created_by="pid")
    db.update_strategy_status(conn, sid, "succeeded")
    sid2 = db.insert_strategy(conn, goal_id=ok,
                              lean_path="Problems/p/proofs/L_fine.lean",
                              scratch_path="Problems/p/proofs/_strategy_s78.lean",
                              created_by="pid")
    db.update_strategy_status(conn, sid2, "succeeded")
    conn.commit()
    for rel in ("L_fine", "L_bad_alias", "L_bad_forward", "_strategy_s77", "_strategy_s78"):
        p = tmp_path / "Problems" / "p" / "proofs" / f"{rel}.lean"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("import Mathlib\n", encoding="utf-8")
    return ok, bad, fwd, sid, sid2


_OUT = (
    "error: Problems/p/proofs/L_bad_alias.lean:9:31: maximum recursion depth has been reached\n"
    "error: Problems/p/proofs/_strategy_s78.lean:13:6: Function expected at\n"
    "error: Problems/p/proofs/L_bad_forward.lean:4:0: unknown identifier 'x'\n"
)


def test_audit_maps_failing_modules_to_strategies_and_goals(conn, tmp_path, monkeypatch):
    ok, bad, fwd, sid, sid2 = _seed(conn, tmp_path)
    built = []
    monkeypatch.setattr(cv, "_build", lambda ws, mods: (built.append(list(mods)), (False, _OUT))[1])
    rep = cv.audit(conn, tmp_path, problem="p")
    assert sorted(m for m in built[0]) == sorted([
        "Problems.p.proofs.L_bad_alias", "Problems.p.proofs.L_bad_forward",
        "Problems.p.proofs.L_fine", "Problems.p.proofs._strategy_s77",
        "Problems.p.proofs._strategy_s78"]), "every proof module of the problem"
    assert rep.total == 5
    assert {r.module for r in rep.failures} == {
        "Problems.p.proofs.L_bad_alias", "Problems.p.proofs._strategy_s78",
        "Problems.p.proofs.L_bad_forward"}
    by_mod = {r.module: r for r in rep.failures}
    # an alias goal with a succeeded strategy → that strategy is the culprit
    assert by_mod["Problems.p.proofs.L_bad_alias"].strategy_id == sid
    assert by_mod["Problems.p.proofs.L_bad_alias"].goal_id == bad
    # a strategy scratch file names its own strategy (and goal)
    assert by_mod["Problems.p.proofs._strategy_s78"].strategy_id == sid2
    assert by_mod["Problems.p.proofs._strategy_s78"].goal_id == ok
    # a forward brick has no strategy — only the goal
    assert by_mod["Problems.p.proofs.L_bad_forward"].strategy_id is None
    assert by_mod["Problems.p.proofs.L_bad_forward"].goal_id == fwd


def test_audit_all_green_reports_zero_failures(conn, tmp_path, monkeypatch):
    _seed(conn, tmp_path)
    monkeypatch.setattr(cv, "_build", lambda ws, mods: (True, "ok"))
    rep = cv.audit(conn, tmp_path, problem="p")
    assert rep.failures == [] and rep.total == 5


def test_rollback_hands_strategies_to_the_cascade_and_reopens_strategy_less_goals(
        conn, tmp_path, monkeypatch):
    ok, bad, fwd, sid, sid2 = _seed(conn, tmp_path)
    monkeypatch.setattr(cv, "_build", lambda ws, mods: (False, _OUT))
    rolled = []
    monkeypatch.setattr(cv, "_rollback_cascade_chain",
                        lambda c, ws, culprit: rolled.append(culprit) or 1)
    rep = cv.audit(conn, tmp_path, problem="p")
    n = cv.rollback(conn, tmp_path, rep)
    assert sorted(rolled) == sorted([sid, sid2]), "one cascade per culprit strategy"
    assert db.get_goal(conn, fwd)["status"] == "open", "a forward brick reopens directly"
    ev = conn.execute("SELECT event FROM goal_events WHERE goal_id=? ORDER BY id DESC LIMIT 1",
                      (fwd,)).fetchone()["event"]
    assert ev == "catalog_verify_unbuildable"
    assert n == 3


def test_rollback_refuses_while_a_daemon_owns_the_database(conn, tmp_path, monkeypatch):
    _seed(conn, tmp_path)
    monkeypatch.setattr(cv, "_build", lambda ws, mods: (False, _OUT))
    monkeypatch.setattr(cv, "_daemon_alive", lambda ws: 4242)
    rep = cv.audit(conn, tmp_path, problem="p")
    with pytest.raises(RuntimeError, match="daemon"):
        cv.rollback(conn, tmp_path, rep)


def test_audit_records_the_verdict_in_the_degraded_ledger(conn, tmp_path, monkeypatch):
    from Tooling.core import degraded
    _seed(conn, tmp_path)
    monkeypatch.setattr(cv, "_build", lambda ws, mods: (False, _OUT))
    seen = []
    monkeypatch.setattr(degraded, "record", lambda ws, kind, detail="": seen.append((kind, detail)))
    cv.audit(conn, tmp_path, problem="p")
    assert seen and seen[0][0] == "catalog_verify" and "3" in seen[0][1]
