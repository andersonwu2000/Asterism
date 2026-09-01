"""Promotion cold-build gate (owner ruling 2026-08-30, task #231).

`verify_strategy` promotes a parent goal file to `def <slug> := @s<N>` by
pure string rewrite — no elaboration. The status flip to `proved` used to
follow at once, and the only build was a best-effort background warm of
the alias module whose failures went to one truncated log line (15 on
the workstation, 7 on the flagship, none surfaced). The 2026-08-30 full
cold build then found bricks that do not compile: an alias whose own
elaboration blows maxRecDepth (A), and consumers of a sub-goal that
cited helper decls the promotion dropped from the stub (B, a cascade of
seven at one promotion).

Now the promotion is a GATE: the alias module AND every strategy that
imports the promoted goal are cold-built (through the lake build lease)
before anything flips. The build runs off the main thread; housekeeping
submits, and flips or rolls back when the result comes back. The failing
MODULE names the culprit — the alias itself → this promotion is undone
(strategy dead, goal open); a consumer strategy → that consumer is rolled
back through `rollback_cascade_chain`, and this promotion is retried
without it. Every failure lands in the degraded ledger with its full
build output on disk.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from Tooling.pipeline import _lake
from Tooling.pipeline import _olean_warm as warm
from Tooling.quality import verify
from Tooling.state import db


def _seed_problem(conn, name="p"):
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done) "
                 "VALUES (?, ?, 1)", (name, db.now()))
    conn.commit()


def _seed_goal(conn, slug, *, problem="p", origin="backward", depth=1):
    return db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/proofs/L_{slug}.lean",
        statement="True", origin=origin, depth=depth)


def _seed_strategy(conn, *, goal_id, sid_slug, lean_path, subs=()):
    sid = db.insert_strategy(
        conn, goal_id=goal_id, lean_path=lean_path, created_by="pid",
        scratch_path=f"Problems/p/proofs/_strategy_{sid_slug}.lean")
    for i, sub in enumerate(subs):
        db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub, position=i)
    return sid


def _write(ws: Path, rel: str, text: str = "import Mathlib\n") -> Path:
    p = ws / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# ───────────────────────── pure parts ─────────────────────────

def test_failing_modules_are_read_from_lake_output(tmp_path):
    out = (
        "⚠ [12/40] Replayed Problems.p.proofs.L_a\n"
        "error: Problems/p/proofs/L_fin15.lean:9:31: maximum recursion depth has been reached\n"
        "error: Lean exited with code 1\n"
        "error: build cycle detected:\n"
        "error: Problems/p/proofs/_strategy_s24568.lean: bad import 'Problems.p.proofs.L_row_mask'\n"
        "error: Problems/p/proofs/_strategy_s26149.lean:13:6: Function expected at\n"
    )
    mods = verify.failing_modules_from_build_output(out)
    assert mods == ["Problems.p.proofs.L_fin15",
                    "Problems.p.proofs._strategy_s24568",
                    "Problems.p.proofs._strategy_s26149"]


def test_promotion_modules_are_the_alias_plus_its_live_consumers(conn, tmp_path):
    """The set the gate builds: the promoted goal's own module and every
    live strategy that lists it as a sub-goal (those import it). Dead
    and superseded consumers are not built — they are not on record."""
    _seed_problem(conn)
    sub = _seed_goal(conn, "sub")
    win = _seed_strategy(conn, goal_id=sub, sid_slug="win",
                         lean_path="Problems/p/proofs/L_sub.lean")
    parent = _seed_goal(conn, "parent", depth=0)
    live = _seed_strategy(conn, goal_id=parent, sid_slug="live",
                          lean_path="Problems/p/proofs/L_parent.lean",
                          subs=(sub,))
    other = _seed_goal(conn, "other", depth=0)
    dead = _seed_strategy(conn, goal_id=other, sid_slug="dead",
                          lean_path="Problems/p/proofs/L_other.lean",
                          subs=(sub,))
    db.update_strategy_status(conn, dead, "dead")
    mods = verify.promotion_modules(conn, tmp_path, strategy_id=win)
    assert mods == ["Problems.p.proofs.L_sub",
                    "Problems.p.proofs._strategy_live"]
    assert "_strategy_dead" not in " ".join(mods)


# ───────────────────────── the gate worker ─────────────────────────

@pytest.fixture
def gate():
    g = warm.PromotionGate(Path("."), enabled=True)
    yield g
    g.shutdown(wait=True, timeout=5)


def test_gate_builds_off_thread_and_reports_the_result(tmp_path, gate, monkeypatch):
    seen = {}

    def fake_build(ws, mods):
        seen["thread"] = threading.current_thread().name
        seen["mods"] = list(mods)
        return True, "ok"
    monkeypatch.setattr(_lake, "lake_build_modules", fake_build)
    gate._workspace = tmp_path
    gate.submit(7, ["Problems.p.proofs.L_a", "Problems.p.proofs._strategy_x"])
    assert gate.pending(7)
    res = gate.wait_result(7, timeout=5)
    assert res.ok is True and res.failing_modules == []
    assert seen["thread"] != threading.current_thread().name, "never on the caller's thread"
    assert seen["mods"] == ["Problems.p.proofs.L_a", "Problems.p.proofs._strategy_x"]
    assert not gate.pending(7)


def test_gate_failure_lands_in_degraded_and_keeps_the_full_output(
        tmp_path, gate, monkeypatch):
    from Tooling.core import degraded
    long_out = ("⚠ [1/2] Replayed Problems.p.proofs.L_a\n" * 3
                + "error: Problems/p/proofs/L_a.lean:9:31: maximum recursion depth has been reached\n"
                + "x" * 500)
    monkeypatch.setattr(_lake, "lake_build_modules", lambda ws, m: (False, long_out))
    recorded = []
    monkeypatch.setattr(degraded, "record",
                        lambda ws, kind, detail="": recorded.append((kind, detail)))
    gate._workspace = tmp_path
    gate.submit(9, ["Problems.p.proofs.L_a"])
    res = gate.wait_result(9, timeout=5)
    assert res.ok is False
    assert res.failing_modules == ["Problems.p.proofs.L_a"]
    assert recorded and recorded[0][0] == "promotion_build"
    assert "L_a" in recorded[0][1] and "maximum recursion depth" in recorded[0][1]
    log = tmp_path / ".asterism" / "logs" / "promotion_gate" / "s9.txt"
    assert log.exists() and log.read_text(encoding="utf-8").endswith("x" * 500), \
        "the whole build output is on disk, not a 160-char prefix"


# ───────────────────────── housekeeping with the gate ─────────────────────────

class _SyncGate:
    """A gate whose builds are scripted per strategy id and complete
    instantly — housekeeping's contract is what these tests pin."""

    def __init__(self, verdicts):
        self.verdicts = verdicts     # sid -> (ok, failing_modules)
        self.submitted = []
        self._results = {}

    def submit(self, sid, modules, **kw):
        self.submitted.append((sid, list(modules)))
        ok, failing = self.verdicts[sid]
        self._results[sid] = warm.BuildResult(sid, ok, list(failing), "detail")

    def pending(self, sid):
        return sid in self._results and not self._results[sid].delivered

    def drain_results(self):
        out = [r for r in self._results.values() if not r.delivered]
        for r in out:
            r.delivered = True
        return out


def _promotable(conn, tmp_path, monkeypatch, *, slug="main"):
    _seed_problem(conn)
    gid = _seed_goal(conn, slug, depth=0, origin="root")
    sub = _seed_goal(conn, "sub")
    db.update_goal_status(conn, sub, "proved")
    sid = _seed_strategy(conn, goal_id=gid, sid_slug="s",
                         lean_path=f"Problems/p/proofs/L_{slug}.lean", subs=(sub,))
    g = db.get_goal(conn, gid)
    parent = _write(tmp_path, g["lean_path"], "-- alias\nimport Mathlib\n")
    backup = verify.verify_backup_path(parent, f"s{sid}")
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("-- stub\nimport Mathlib\ntheorem main : True := by sorry\n",
                      encoding="utf-8")
    monkeypatch.setattr(verify, "verify_strategy", lambda *a, **kw: "proved")
    return gid, sid, parent, backup


def test_housekeeping_flips_only_after_the_gate_passes(conn, tmp_path, monkeypatch):
    gid, sid, parent, _ = _promotable(conn, tmp_path, monkeypatch)
    gate = _SyncGate({sid: (True, [])})
    # tick 1: the alias is written and submitted; nothing flips yet
    monkeypatch.setattr(gate, "drain_results", lambda: [])
    counts = verify.verify_housekeeping(conn, workspace=tmp_path, promotion_gate=gate)
    assert counts["pending"] == 1 and counts["proved"] == 0
    assert db.get_goal(conn, gid)["status"] != "proved"
    assert gate.submitted and gate.submitted[0][0] == sid
    assert gate.submitted[0][1][0] == "Problems.p.proofs.L_main"
    # tick 2: the result is in — now it flips
    monkeypatch.delattr(gate, "drain_results")
    counts = verify.verify_housekeeping(conn, workspace=tmp_path, promotion_gate=gate)
    assert counts["proved"] == 1
    assert db.get_goal(conn, gid)["status"] == "proved"
    assert conn.execute("SELECT status FROM strategies WHERE id=?",
                        (sid,)).fetchone()["status"] == "succeeded"


def test_housekeeping_does_not_resubmit_a_pending_promotion(conn, tmp_path, monkeypatch):
    gid, sid, parent, _ = _promotable(conn, tmp_path, monkeypatch)
    gate = _SyncGate({sid: (True, [])})
    monkeypatch.setattr(gate, "drain_results", lambda: [])
    verify.verify_housekeeping(conn, workspace=tmp_path, promotion_gate=gate)
    verify.verify_housekeeping(conn, workspace=tmp_path, promotion_gate=gate)
    assert len(gate.submitted) == 1, "one build per promotion while it is in flight"


def test_alias_build_failure_undoes_the_promotion(conn, tmp_path, monkeypatch):
    """Class A: the alias module itself does not elaborate. The parent
    file goes back to its stub, the strategy dies, the goal reopens —
    exactly the `dead` branch, with the reason on record."""
    gid, sid, parent, backup = _promotable(conn, tmp_path, monkeypatch)
    gate = _SyncGate({sid: (False, ["Problems.p.proofs.L_main"])})
    verify.verify_housekeeping(conn, workspace=tmp_path, promotion_gate=gate)  # submit
    counts = verify.verify_housekeeping(conn, workspace=tmp_path, promotion_gate=gate)
    assert counts["dead"] == 1 and counts["proved"] == 0
    assert parent.read_text(encoding="utf-8").startswith("-- stub"), "alias rolled back"
    assert conn.execute("SELECT status FROM strategies WHERE id=?",
                        (sid,)).fetchone()["status"] == "dead"
    assert db.get_goal(conn, gid)["status"] == "open"
    ev = conn.execute("SELECT event FROM goal_events WHERE goal_id=? ORDER BY id DESC LIMIT 1",
                      (gid,)).fetchone()["event"]
    assert ev == "promotion_build_failed"


def test_consumer_build_failure_rolls_back_the_consumer_not_the_promotion(
        conn, tmp_path, monkeypatch):
    """Class B: the promoted alias is fine; a parent strategy that cited
    a helper from the old stub no longer compiles. THAT strategy is the
    culprit: `rollback_cascade_chain` on it (dead, its goal open); the
    promotion stays pending and is retried without the dead consumer."""
    gid, sid, parent, _ = _promotable(conn, tmp_path, monkeypatch)
    grand = _seed_goal(conn, "grand", depth=0, origin="root")
    consumer = _seed_strategy(conn, goal_id=grand, sid_slug="consumer",
                              lean_path="Problems/p/proofs/L_grand.lean", subs=(gid,))
    db.update_goal_status(conn, grand, "attempting")
    rolled = []
    monkeypatch.setattr(verify, "rollback_cascade_chain",
                        lambda c, ws, culprit: rolled.append(culprit) or 1)
    gate = _SyncGate({sid: (False, ["Problems.p.proofs._strategy_consumer"])})
    verify.verify_housekeeping(conn, workspace=tmp_path, promotion_gate=gate)  # submit
    counts = verify.verify_housekeeping(conn, workspace=tmp_path, promotion_gate=gate)
    assert rolled == [consumer]
    assert counts["dead"] == 0, "this promotion is not the culprit"
    assert parent.read_text(encoding="utf-8").startswith("-- alias"), "alias kept"
    assert conn.execute("SELECT status FROM strategies WHERE id=?",
                        (sid,)).fetchone()["status"] != "dead"
    # retried: a second submission goes out (the consumer set is recomputed)
    assert len(gate.submitted) == 2


# ───────────────────────── capped ≠ failed (2026-09-02) ─────────────────────────

def test_a_capped_promotion_build_is_requeued_not_delivered_as_failure(
        tmp_path, gate, monkeypatch):
    """`capped` = the OS fence stopped the build for lack of room. The
    promotion is neither flipped nor rolled back: the gate queues the
    same job again and housekeeping keeps seeing it as pending."""
    calls = []

    def fake_build(ws, mods):
        calls.append(list(mods))
        if len(calls) == 1:
            r = _lake.BuildOutcome(False, "build capped — waited 100s for room above 1.5G")
            r.capped = True
            return r
        return _lake.BuildOutcome(True, "Build completed")
    monkeypatch.setattr(_lake, "lake_build_modules", fake_build)
    monkeypatch.setattr(warm, "REQUEUE_PAUSE_SEC", 0.01)
    gate._workspace = tmp_path
    gate.submit(11, ["Problems.p.proofs.L_a"])
    res = gate.wait_result(11, timeout=10)
    assert res.ok is True
    assert calls == [["Problems.p.proofs.L_a"]] * 2, "the same job ran again"
    log = tmp_path / ".asterism" / "logs" / "promotion_gate" / "s11.txt"
    assert not log.exists(), "a capped build is not a failure record"
