"""P2-#1 — End-to-end integration test of the dispatcher loop.

The pipeline-pure / cascade / retry suites monkeypatch agent.spawn_llm
and pipeline._lake_build separately, so any handoff between
`dispatcher.run` → `bfs_refill` → `_run_pipeline` → cascade can drift
silently. This file exercises the full chain by:

  1. Building a real Problem on disk in a tmp workspace (problem.json +
     Defs + Root.lean + minimal lakefile/Asterism config).
  2. Initialising the DB via `cli.cmd_init`.
  3. Monkeypatching `agent.spawn_llm` to drop canned patches and
     `pipeline._lake_build_modules` to always pass.
  4. Calling `dispatcher.run(workspace, once=True)` and asserting
     the root goal reaches 'proved' through the actual cascade.

The single happy-path test catches integration drift that the
unit suite cannot — e.g. if a refactor breaks the Builder
success-path's cascade hook, none of the existing tests would
notice but this one will.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest

from Tooling import agent, pipeline
from Tooling.pipeline import adversary as _adversary
from Tooling.core import cli, dispatcher
from Tooling.state import db


def _seed_workspace(tmp_path: Path) -> Path:
    """Build the minimum workspace shape `cmd_init` requires."""
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    import json as _json
    (pdir / "problem.json").write_text(
        _json.dumps({"problem": "p", "charter": "Prove True."}) + "\n",
        encoding="utf-8")
    (pdir / "Defs.lean").write_text("import Mathlib\n", encoding="utf-8")
    # cmd_init requires a hand-written Root.lean (the framework no longer
    # auto-generates it from the seed). Author the canonical-shape
    # stub so init can extract `goals.statement` from the signature.
    (pdir / "Root.lean").write_text(
        "import Mathlib\n"
        "import Problems.p.Defs\n"
        "namespace Problems.p\n"
        "theorem main : True := by sorry\n"
        "end Problems.p\n",
        encoding="utf-8")
    # Asterism.yaml: pool=1 to keep the test deterministic; budget high.
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 1\n  budget_sec: 60\n", encoding="utf-8")
    return pdir


def test_e2e_root_proved_through_dispatcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full dispatcher loop end-to-end on a trivial Problem.

    Builder spawn drops a `patch.lean` echoing the goal lean file
    with a `:= by trivial` body; the lake-build stub greenlights it.
    Cascade should mark root proved and dispatcher.run(once=True)
    exits with all-roots-proved.
    """
    monkeypatch.chdir(tmp_path)
    pdir = _seed_workspace(tmp_path)

    # Stub the real-toolchain lake builds. Two gates added by the
    # "hand-written Root.lean + dual type-check" change run a subprocess
    # `lake build` that needs a lakefile + Lean toolchain this tmp
    # workspace doesn't have:
    #   - cmd_init's dual type-check gate (pipeline._lake.lake_build)
    #   - dispatcher._verify_problem lazy gate (lake_build_modules)
    # Neither is what this e2e exercises (the dispatcher loop is); the
    # gateway-driven verify is already stubbed below. Stub both green.
    from Tooling.pipeline import _lake as _lake_mod
    monkeypatch.setattr(_lake_mod, "lake_build", lambda *a, **k: (True, ""))
    monkeypatch.setattr(_lake_mod, "lake_build_modules",
                        lambda *a, **k: (True, ""))

    # Init Problem (Root.lean + DB row)
    cli_args = argparse.Namespace(problem="p", force=False)
    rc = cli.cmd_init(cli_args)
    assert rc == 0
    conn = db.connect()
    root = conn.execute(
        "SELECT id, status FROM goals WHERE problem='p'").fetchone()
    # Phase 5: cli init creates roots as 'frozen'. This e2e test bypasses
    # Strategist entirely (exercises Builder leaf-bypass + cascade →
    # root_proved), so flip the root to 'open' manually to simulate
    # Strategist's `Reopen(root)`.
    assert root is not None and root["status"] == "frozen"
    db.update_goal_status(conn, int(root["id"]), "open")
    conn.commit()

    # Stub gateway_lifecycle.verify_file so:
    #   - Phase 1 hint probe (write_olean=False) returns ok + a
    #     Try-these info diagnostic → winner parsed
    #   - Phase 1 confirm + Phase 2 verify (write_olean=True) return
    #     ok + empty axioms → proved
    # This short-circuits Phase 1 and exercises the cascade →
    # root_proved path without spawning an LLM.
    from Tooling.lsp import lifecycle as gateway_lifecycle
    def fake_verify(target_path, *, write_olean=True, axioms_for=None, **kw):
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
            "axioms": [] if axioms_for else None,
            "axiom_error": None,
        }
    monkeypatch.setattr(gateway_lifecycle, "verify_file", fake_verify)

    # Mock spawn_llm: write a patch.lean that satisfies Builder's
    # forbidden-lemma scan + delivers a body. The framework's
    # _is_sorry_stub guard accepts any non-sorry patch.
    def fake_spawn(**kw):
        # Regression guard: P2-#1 (commit c398ded) initially broke
        # PROMPT_DIR resolution by relativizing to the new pipeline/
        # package dir; the actual prompts live one level up at
        # Tooling/prompts/. None of the unit tests hit the file system
        # path because they all monkeypatch spawn_llm — so the e2e
        # test asserts the prompt_path the framework computed is real.
        assert kw["prompt_path"].exists(), (
            f"framework passed a non-existent prompt path: "
            f"{kw['prompt_path']}")
        attempts = kw["attempts_dir"]
        kind = kw.get("kind", "builder")
        if kind == "builder":
            (attempts / "patch.lean").write_text(
                "import Mathlib\nnamespace Problems.p\n"
                "theorem main : True := by trivial\n"
                "end Problems.p\n",
                encoding="utf-8")
            (attempts / "PROPOSAL.md").write_text(
                "trivial fact, direct proof", encoding="utf-8")
        elif kind == "strategist":
            # Phase 2 — Strategist agent drops decision.json. The wake
            # fires AFTER Builder proves the root (stall-when-idle =
            # the Ingest driver), and since the stall-advance gate
            # (FSM §3.1, 2026-07-12) a stalled wake must move state —
            # a Noop no longer passes. `Ingest` IS the genuine happy
            # path (Phase 6: the Strategist's terminal judgment), so
            # the stub now models the real protocol end-to-end.
            import json as _json
            (attempts / "decision.json").write_text(
                _json.dumps({"kind": "Ingest",
                             "reason": "root proved; manifest satisfied"}),
                encoding="utf-8")
            # Research mode: an Ingest batch is route-moving, so it
            # carries a Programme proposal (endgame batches are exempt
            # from the ≥1-experiment rule but still adversarially
            # reviewed) — the e2e covers the endgame package path.
            (attempts / "proposal.md").write_text(
                "# Close out\n## Argument\nRoot proved by Builder.\n"
                "## Proof\nManifest satisfied by the proved root.\n"
                "## Roadmap\n1. Ingest.\n",
                encoding="utf-8")
        elif kind == "adversary":
            import json as _json
            (attempts / "verdict.json").write_text(
                _json.dumps({"criteria": {
                    **{str(i): "clear: holds" for i in range(1, 6)},
                    # Read, never written as a literal: the naming
                    # criterion moved 1 → 2 on 2026-08-13.
                    _adversary.NAMING_CRITERION:
                        "clear: the closer entry — nothing stands"},
                             "reservations": []}),
                encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    # Phase 1 gateway: dispatcher.run launches the long-living gateway
    # subprocess at startup (mathlib pre-warm). For e2e test purposes
    # we stub start_gateway to a no-op — the conftest urlopen stub
    # handles per-spawn /register + /release.
    from Tooling.lsp import lifecycle as gateway_lifecycle

    class _NoopGw:
        def poll(self): return None
        def terminate(self): pass
        def wait(self, timeout=None): return 0
    monkeypatch.setattr(gateway_lifecycle, "start_gateway",
                        lambda workspace, **kw: _NoopGw())

    # Run dispatcher; once=True exits when the queue empties.
    dispatcher.run(tmp_path, once=True)

    # dispatcher.run's exit paths call claude_cli.request_shutdown(),
    # which SETs a module-global threading.Event. It is process-global
    # and survives this test — leaving it set makes every later test's
    # claude_cli.spawn() bail early (SpawnRC.SHUTDOWN) before reaching
    # the captured Popen, so e.g. test_llm_provider's `calls[0]` is
    # empty → IndexError. Reset it here (the dedicated test hook) so
    # this e2e doesn't pollute downstream tests via run-order.
    from Tooling.llm import claude_cli
    claude_cli._reset_shutdown_for_tests()

    # Assert root proved + a Formalizer pipeline finished + no spurious
    # dead_attempts (cascade should be clean). The merged worker closes
    # via the strategy frame (leaf-bypass / hint), so the pipeline row's
    # outcome is 'success' (strategy committed), not Builder's 'proved'.
    conn2 = db.connect()
    final = conn2.execute(
        "SELECT status FROM goals WHERE problem='p'").fetchone()
    assert final["status"] == "proved", (
        f"expected proved, got {final['status']}")
    finished = conn2.execute(
        "SELECT COUNT(*) AS n FROM pipelines "
        "WHERE outcome IN ('proved','success')"
        " AND kind='Formalizer'").fetchone()
    assert finished["n"] >= 1
    # Phase 2 — Strategist T0 trigger fires on bootstrap_done=0; the
    # fake_spawn shipped a Noop decision, which commits cleanly but
    # cascade-side maps to failure_reason='strategist_noop' (infra-
    # reason so cascade_one doesn't burn root.attempts). Filter it out
    # when checking for unexpected failures on the Builder happy path.
    deaths = conn2.execute(
        "SELECT COUNT(*) AS n FROM dead_attempts"
        " WHERE failure_reason NOT IN ('strategist_noop',"
        "                              'strategist_unimplemented')"
    ).fetchone()
    assert deaths["n"] == 0, "no failures expected on the happy path"


def test_dispatch_pool_caps_in_flight_even_in_ledger_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`dispatch.pool` is a HARD CEILING on in-flight pipelines of every
    kind — the RAM ledger may admit fewer, never more (owner 2026-09-06).

    The ledger paces RAM, but on a subscription board the binding
    resource is the five-hour quota window: a ledger admitting freely
    ran 2 Strategists + 2 Theorists + 17 Formalizer spawns and burned
    the window out in 3.5h (2026-09-05 20:30Z). This drives the real
    loop with a ledger that never refuses, so only the ceiling can hold.
    """
    import threading

    monkeypatch.chdir(tmp_path)
    _seed_workspace(tmp_path)
    # ram_budget flips the loop into ledger mode; pool=2 is the ceiling.
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 2\n  budget_sec: 60\n  ram_budget: 28G\n",
        encoding="utf-8")

    from Tooling.pipeline import _lake as _lake_mod
    monkeypatch.setattr(_lake_mod, "lake_build", lambda *a, **k: (True, ""))
    monkeypatch.setattr(_lake_mod, "lake_build_modules",
                        lambda *a, **k: (True, ""))
    assert cli.cmd_init(argparse.Namespace(problem="p", force=False)) == 0

    # Three live goals — one more than the pool. Their queue rows are laid
    # down by the refill stub below, because `_recover_at_startup` clears
    # the queue before the first tick.
    conn = db.connect()
    root = conn.execute("SELECT id FROM goals WHERE problem='p'").fetchone()
    db.update_goal_status(conn, int(root["id"]), "open")
    goal_ids = [int(root["id"])]
    for i in (1, 2):
        goal_ids.append(db.insert_goal(
            conn, problem="p", slug=f"sub{i}",
            lean_path=f"Problems/p/Sub{i}.lean", statement="True",
            origin="forward", depth=1))
    conn.commit()

    # A ledger that refuses nothing: admission is then the ceiling's alone.
    from Tooling.core import ram_ledger

    class _FreeLedger:
        budget_gb = 28.0
        dispatch_paused = False
        open_slots = 99
        free_slots = 99
        nl_blocked_by_budget = False

        def __init__(self, budget_gb, machine_gb): pass
        def nl_hard_cap(self): return 8
        def tick(self, **kw): pass
        def nl_admissible(self, nl_in_flight): return True
        def note_nl_admit(self): pass

    monkeypatch.setattr(ram_ledger, "DispatcherLedger", _FreeLedger)

    # Everything downstream of the door is stubbed — this exercises
    # admission WIDTH, not what a pipeline does. The RAM clamp is pinned
    # to identity so the ceiling is 2 on any machine's memory.
    from Tooling.lsp import lifecycle as gateway_lifecycle
    monkeypatch.setattr(gateway_lifecycle, "ram_clamped_pool",
                        lambda pool, slots: (pool, ""))
    from Tooling.core import warmup as _warmup
    monkeypatch.setattr(_warmup, "start_background",
                        lambda ws: {"ready": True, "failed": None})
    from Tooling.core.dispatcher import loop as _loop
    monkeypatch.setattr(_loop, "_verify_problem", lambda *a, **k: True)

    def seed_queue_once(conn_, *a, **k):
        if conn_.execute("SELECT COUNT(*) FROM queue").fetchone()[0]:
            return
        if seeded:
            return
        seeded.append(True)
        for gid in goal_ids:
            db.enqueue(conn_, kind="Formalizer", target_id=str(gid),
                       problem="p")
    seeded: list = []
    monkeypatch.setattr(_loop, "bfs_refill", seed_queue_once)
    monkeypatch.setattr(_loop, "strategist_triggers", lambda *a, **k: None)
    monkeypatch.setattr(_loop, "_librarian_refill", lambda *a, **k: False)
    monkeypatch.setattr(_loop, "cascade_one", lambda *a, **k: None)

    seen = threading.Lock()
    live = {"now": 0, "peak": 0}

    def fake_pipeline(workspace, intents, kind, target_id, target_kind,
                      pipeline_id, decision_id):
        with seen:
            live["now"] += 1
            live["peak"] = max(live["peak"], live["now"])
        # Long enough that a second admission pass overlaps this one.
        time.sleep(0.1)
        with seen:
            live["now"] -= 1
        return _loop.WorkerDone(pipeline_id, kind, target_id, target_kind,
                                "failed", "test_stub")
    monkeypatch.setattr(_loop, "_run_pipeline", fake_pipeline)

    dispatcher.run(tmp_path, once=True)
    from Tooling.llm import claude_cli
    claude_cli._reset_shutdown_for_tests()

    assert live["peak"] <= 2, (
        f"dispatch.pool=2 must cap in-flight pipelines of every kind; "
        f"peaked at {live['peak']}")
    assert live["peak"] == 2, (
        "the three rows should still have filled the pool — a peak of "
        f"{live['peak']} means the harness never exercised the ceiling")
