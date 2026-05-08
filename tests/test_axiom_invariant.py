"""Axiom probe invariant — single gate for `goals.status='proved'`.

These tests enforce: every "mark proved" path runs `axiom_probe_file`
on the candidate proof, and rejects (via outcome='failed' or 'dead')
when the probe returns False.

Why it matters: `lake build` accepts files whose imports contain
`sorry` (sorry'd module compiles fine; sorryAx propagates through
definitions but lake returns rc=0). Only `#print axioms` walks the
kernel dependency graph and reports every axiom touched. Without the
probe, a strategy whose body is sorry-free but imports a shelved-
sub-goal stub gets marked 'proved' wrongly — exactly the SG s64 case
that motivated this layer.

Pipelines covered:
  - `verify_strategy` (`Tooling/verify.py`) — strategy assembly path
    used by both regular Backward decomposition AND Phase 6.5
    leaf-bypass salvage.
  - Builder Phase 1 (`pipeline/builder.py`, hint winner) — fresh
    sorry-stub closed by `:= by <tac>`.
  - Builder Phase 2 (`pipeline/builder.py`, LLM patch) — agent's
    patch.lean overwriting goal_lean.
  - `_try_promote_sorry_free` (`pipeline/backward.py`) — sub-goal
    stub auto-promote when agent inlines a complete proof.

The conftest autouse fixture `_stub_axiom_probe_by_default` neutralises
the probe to (True, …) for non-axiom unit tests; tests here override
it locally to a False stub to exercise the rejection path.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import agent, db, manifest, pipeline, verify
from Tooling.pipeline import _axiom


# ---------------------------------------------------------------------
# Local fixture — point the probe to a False-returning stub for these
# tests, regardless of the global True stub from conftest.
# ---------------------------------------------------------------------

@pytest.fixture
def _reject_probe(monkeypatch: pytest.MonkeyPatch):
    """Replace the axiom-probing surface everywhere with a False-
    returning stub mirroring the SG s64 case (leaf-bypass sat on a
    shelved sibling's sorry stub).

    After verify-unification, axiom probing goes through TWO paths:
      1. `_axiom.axiom_probe(_file)` — direct callers (Builder
         Phase 1 hint, library.promote, etc.).
      2. `gateway_lifecycle.verify_file(..., axioms_for=...)` —
         verify_strategy / Builder Phase 2 verify use this. Reject
         via the `axioms` field returning a sorryAx; the rogue
         check happens client-side.
    """
    def _stub_reject(*args, **kwargs):
        return False, "rogue axioms: ['sorryAx']"
    monkeypatch.setattr(_axiom, "axiom_probe_file", _stub_reject)
    monkeypatch.setattr(_axiom, "axiom_probe", _stub_reject)

    from Tooling import gateway_lifecycle as _gl
    def _stub_verify_with_rogue(target_path, *, write_olean=True,
                                  axioms_for=None, timeout=120.0,
                                  workspace=None):
        return {
            "ok": True,
            "diagnostic_count": 0,
            "diagnostics": [],
            "olean_written": write_olean,
            "olean_path": str(target_path),
            # Always include sorryAx so the client-side whitelist
            # check rejects regardless of which whitelist tests pass.
            "axioms": ["sorryAx"] if axioms_for else None,
            "axiom_error": None,
        }
    monkeypatch.setattr(_gl, "verify_file", _stub_verify_with_rogue)
    return _stub_reject


# ---------------------------------------------------------------------
# verify_strategy — rejects axiom-violation
# ---------------------------------------------------------------------

def _seed_goal_with_strategy(conn, tmp_path):
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    gid = db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/proofs/L_main.lean",
        statement="True", origin="root", depth=0,
    )
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/proofs/L_main.lean",
        created_by="pid",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        proposal_md="-- main: leaf direct proof\n",
    )
    sub = db.insert_goal(
        conn, problem="p", slug="sub", origin="backward", depth=1,
        lean_path="Problems/p/proofs/L_sub.lean", statement="True",
    )
    db.update_goal_status(conn, sub, "proved")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub, position=0)
    scratch = tmp_path / "Problems/p/proofs/_strategy_s.lean"
    scratch.parent.mkdir(parents=True)
    scratch.write_text("-- stub", encoding="utf-8")
    return gid, sid


def test_verify_strategy_dead_on_axiom_violation(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _reject_probe,
) -> None:
    """SG s64 reproducer: lake build passes (strategy file + alias both
    elaborate; the imported sorry'd L_*.lean is legal Lean), but the
    axiom probe finds sorryAx in the strategy's transitive closure.
    Without the probe, the strategy would have been marked 'proved' and
    the parent goal cascaded up to root_proved. With the probe, the
    strategy is killed at verify time → 'dead'."""
    _, sid = _seed_goal_with_strategy(conn, tmp_path)
    # `_reject_probe` already stubbed `verify_file` to return ok+sorryAx.
    monkeypatch.setattr(verify, "lean_path_to_module",
                        lambda *a, **kw: "Problems.p.proofs._strategy_s")
    monkeypatch.setattr(verify, "promote_to_alias",
                        lambda *a, **kw: None)
    monkeypatch.setattr(verify, "rollback_promote",
                        lambda *a, **kw: None)

    mfst = manifest.Manifest(problem="p", statement="True",
                              axioms_whitelist=["propext"])
    out = verify.verify_strategy(
        conn, workspace=tmp_path, strategy_id=sid,
        manifests={"p": mfst},
    )
    assert out == "dead"


def test_verify_strategy_rolls_back_parent_on_axiom_violation(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _reject_probe,
) -> None:
    """When the axiom probe rejects after `promote_to_alias` has
    already rewritten the parent file, `rollback_promote` MUST run so
    the parent doesn't stay aliased to a tainted strategy."""
    _, sid = _seed_goal_with_strategy(conn, tmp_path)
    calls = {"rollback": 0}
    # `_reject_probe` already stubbed `verify_file` to return ok+sorryAx.
    monkeypatch.setattr(verify, "lean_path_to_module",
                        lambda *a, **kw: "Problems.p.proofs._strategy_s")
    monkeypatch.setattr(verify, "promote_to_alias",
                        lambda *a, **kw: tmp_path / "backup")

    def fake_rollback(*a, **kw):
        calls["rollback"] += 1
    monkeypatch.setattr(verify, "rollback_promote", fake_rollback)

    mfst = manifest.Manifest(problem="p", statement="True",
                              axioms_whitelist=["propext"])
    out = verify.verify_strategy(
        conn, workspace=tmp_path, strategy_id=sid,
        manifests={"p": mfst},
    )
    assert out == "dead"
    assert calls["rollback"] == 1


def test_verify_housekeeping_does_not_skip_probe_with_no_manifests(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`verify_strategy(manifests=None)` MUST be a test-only escape
    hatch — production callers (verify_housekeeping called from
    dispatcher) always pass the dispatcher's manifests dict. This test
    enforces that contract: when housekeeping receives a manifests dict,
    verify_strategy receives it too (probe is exercised)."""
    _, sid = _seed_goal_with_strategy(conn, tmp_path)
    received_manifests = {}

    def spy_verify(conn, *, workspace, strategy_id, manifests=None):
        received_manifests["v"] = manifests
        return "superseded"
    monkeypatch.setattr(verify, "verify_strategy", spy_verify)

    mfst = manifest.Manifest(problem="p", statement="True",
                              axioms_whitelist=["propext"])
    verify.verify_housekeeping(
        conn, workspace=tmp_path, manifests={"p": mfst},
    )
    assert received_manifests["v"] == {"p": mfst}


# ---------------------------------------------------------------------
# Builder — rejects axiom-violation in both Phase 1 and Phase 2
# ---------------------------------------------------------------------

def _seed_builder_problem(conn, tmp_path) -> int:
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n## Statement\nTrue\n", encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        ("p", str(pdir / "Manifest.md"), db.now()))
    conn.commit()
    root = pdir / "Root.lean"
    root.write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem main : True := by sorry\n"
        "end Problems.p\n",
        encoding="utf-8")
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path=root.relative_to(tmp_path).as_posix(),
        statement="True", origin="root", depth=0,
    )


def test_builder_phase1_axiom_violation_returns_failed(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _reject_probe,
) -> None:
    """Phase 1 hint succeeds, lake build passes, but axiom probe
    rejects (transitive sorryAx via imported sibling). Builder must
    NOT mark proved — outcome='failed' with reason='axiom_violation'.
    goal_lean is restored to the original sorry stub."""
    gid = _seed_builder_problem(conn, tmp_path)
    # The `_reject_probe` fixture has already replaced verify_file
    # with one that returns axioms = ['sorryAx'] when axioms_for is
    # given. We additionally need the Phase 1 hint probe path to
    # surface a Try-these info diagnostic so a winner is parsed.
    from Tooling import gateway_lifecycle
    def stub(target_path, *, write_olean=True, axioms_for=None, **kw):
        if not write_olean:
            return {
                "ok": True,
                "diagnostics": [{
                    "line": 1, "col": 0, "severity": "info",
                    "message": "Try these:\n  [apply] 🎉️ trivial\n",
                }],
                "diagnostic_count": 1,
                "olean_written": False, "olean_path": None,
                "axioms": None, "axiom_error": None,
            }
        return {
            "ok": True,
            "diagnostics": [],
            "diagnostic_count": 0,
            "olean_written": True,
            "olean_path": str(target_path),
            # Trigger the rogue-axiom rejection on the confirm call.
            "axioms": ["sorryAx"] if axioms_for else None,
            "axiom_error": None,
        }
    monkeypatch.setattr(gateway_lifecycle, "verify_file", stub)
    monkeypatch.setattr(agent, "spawn_llm",
                        lambda **kw: pytest.fail("LLM spawn unexpected"))

    mfst = manifest.Manifest(
        problem="p", statement="True", axioms_whitelist=["propext"])
    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=mfst,
        pipeline_id="pid-axiom-p1")
    assert r.outcome == "failed"
    assert r.failure_reason == "axiom_violation"
    # goal_lean restored
    goal = db.get_goal(conn, gid)
    text = (tmp_path / goal["lean_path"]).read_text(encoding="utf-8")
    assert ":= by sorry" in text


def test_builder_phase2_axiom_violation_returns_failed(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _reject_probe,
) -> None:
    """Phase 2 LLM patch lake-builds clean, but axiom probe finds
    sorryAx in transitive closure. Pipeline must reject — file restored
    to backup, outcome='exhausted' (helper retries until budget out
    treating axiom_violation as non-terminal, mirroring lake_build_error)."""
    gid = _seed_builder_problem(conn, tmp_path)
    db.increment_goal_attempts(conn, gid)  # bypass Phase 1
    goal = db.get_goal(conn, gid)
    original = (tmp_path / goal["lean_path"]).read_text(encoding="utf-8")

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "patch.lean").write_text(
            "-- main: trivially closed via imported sibling\n"
            "import Mathlib\ntheorem main : True := trivial\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: (True, ""))

    mfst = manifest.Manifest(
        problem="p", statement="True", axioms_whitelist=["propext"])
    r = pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path, mfst=mfst,
        pipeline_id="pid-axiom-p2")
    # Budget exhausted via repeated axiom_violation retries → 'exhausted'
    # carrying the last failure_reason.
    assert r.outcome == "exhausted"
    assert r.failure_reason == "axiom_violation"
    # goal_lean restored on every failed retry
    assert (tmp_path / goal["lean_path"]).read_text(
        encoding="utf-8") == original


