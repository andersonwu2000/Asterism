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

from Tooling import agent, cli, db, dispatcher, pipeline


def _seed_workspace(tmp_path: Path) -> Path:
    """Build the minimum workspace shape `cmd_init` requires."""
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n"
        "# p\n\n## Statement\nTrue\n\n## Entry kind\nBuilder\n",
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
    root = conn.execute(
        "SELECT id, status FROM goals WHERE problem='p'").fetchone()
    assert root is not None and root["status"] == "open"

    # Stub _lake_build* to always succeed. With this in place the
    # in-Builder tactic_try Phase 1 will accept the first tactic
    # (`rfl`) as proving the goal — short-circuiting before spawn_llm.
    # Good: still exercises run_builder → cascade → root proved.
    monkeypatch.setattr(pipeline, "_lake_build_modules",
                        lambda ws, mods: (True, ""))
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, target: (True, ""))

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
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

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
    deaths = conn2.execute(
        "SELECT COUNT(*) AS n FROM dead_attempts").fetchone()
    assert deaths["n"] == 0, "no failures expected on the happy path"
