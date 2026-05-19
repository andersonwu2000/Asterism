"""P2-#1 — End-to-end integration test of the dispatcher loop.

The pipeline-pure / cascade / retry suites monkeypatch agent.spawn_llm
and pipeline._lake_build separately, so any handoff between
`dispatcher.run` → `bfs_refill` → `_run_pipeline` → cascade can drift
silently. This file exercises the full chain by:

  1. Building a real Problem on disk in a tmp workspace (Manifest +
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
from pathlib import Path

import pytest

from Tooling import agent, pipeline
from Tooling.core import cli, dispatcher
from Tooling.state import db


def _seed_workspace(tmp_path: Path) -> Path:
    """Build the minimum workspace shape `cmd_init` requires."""
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    # Phase 2: Manifest no longer carries `## Entry kind`. cli init
    # hardwires root.entry_kind='Backward'; this test overrides to
    # 'Builder' below to exercise Builder's leaf-bypass directly.
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n"
        "# p\n\n## Statement\nTrue\n",
        encoding="utf-8")
    (pdir / "Defs.lean").write_text("import Mathlib\n", encoding="utf-8")
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

    # Init Problem (Root.lean + DB row)
    cli_args = argparse.Namespace(problem="p", force=False)
    rc = cli.cmd_init(cli_args)
    assert rc == 0
    conn = db.connect()
    # Phase 2 — cli init hardwires root.entry_kind='Backward'. This e2e
    # test exercises Builder's leaf-bypass on `True := by trivial`;
    # override entry_kind back to 'Builder' so dispatcher routes to
    # Builder first (pre-Phase 2 default for this fixture).
    conn.execute("UPDATE goals SET entry_kind='Builder' WHERE problem='p'")
    conn.commit()
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
            # Phase 2 — Strategist agent drops decision.json. For the
            # e2e happy path we have a trivial Problem that Builder
            # closes on its own; Strategist's T0 firing just needs to
            # commit *something* so bootstrap_done flips and T0 stops
            # re-enqueueing. A Noop decision is the cheapest valid
            # commit (commit_decision still touches last_strategist_at
            # + bootstrap_done for any decision kind).
            import json as _json
            (attempts / "decision.json").write_text(
                _json.dumps({"kind": "Noop", "reason": "let BFS run"}),
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

    # Assert root proved + a Builder pipeline finished + no spurious
    # dead_attempts (cascade should be clean).
    conn2 = db.connect()
    final = conn2.execute(
        "SELECT status FROM goals WHERE problem='p'").fetchone()
    assert final["status"] == "proved", (
        f"expected proved, got {final['status']}")
    finished = conn2.execute(
        "SELECT COUNT(*) AS n FROM pipelines "
        "WHERE outcome='proved' AND kind='Builder'").fetchone()
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
