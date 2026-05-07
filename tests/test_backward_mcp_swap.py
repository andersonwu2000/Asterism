"""Phase 2 LSP swap — Backward pipeline integration tests.

Verifies that:
  - `agent.spawn_llm` receives a `mcp_config_path` kwarg pointing at
    a freshly-written JSON config that boots `Tooling.lsp_mcp_server`
    with target=goal_lean.
  - Backward backs up goal_lean BEFORE the agent runs, restores it on
    parse failure (e.g. malformed output → no lake build).
  - The OUTER try/finally guard restores goal_lean even when the
    agent's spawn fails before parse is reached (spawn timeout, agent
    crash). Without this, goal_lean would leak the agent's apply_edit
    state into the next dispatch.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from Tooling import agent, db, manifest, pipeline


def _seed_root_goal(tmp_path: Path, conn: sqlite3.Connection) -> int:
    problem = "p"
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n## Statement\nTrue\n", encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        (problem, str(pdir / "Manifest.md"), db.now()))
    conn.commit()
    root = pdir / "Root.lean"
    root.write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem main : True := by sorry\n"
        "end Problems.p\n",
        encoding="utf-8")
    rel = root.relative_to(tmp_path).as_posix()
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path=rel,
        statement="True", origin="root", depth=0,
    )


def _mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="True")


def test_spawn_passes_mcp_config_path(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spawn_llm gets a mcp_config_path pointing at a freshly-written
    JSON config for Tooling.lsp_mcp_server. The config carries
    ASTERISM_WORKSPACE / ASTERISM_TARGET (target = goal_lean)."""
    gid = _seed_root_goal(tmp_path, conn)
    captured: dict = {}

    def fake_spawn(**kw):
        captured.update(kw)
        return 124  # bail via timeout, we only care about call args

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=_mfst(), pipeline_id="pid-bw-mcp")

    cfg = captured.get("mcp_config_path")
    assert cfg is not None, "mcp_config_path should be set"
    assert Path(cfg).exists()
    data = json.loads(Path(cfg).read_text(encoding="utf-8"))
    server = data["mcpServers"]["lsp"]
    assert server["command"] == sys.executable
    assert server["args"] == ["-m", "Tooling.lsp_mcp_server"]
    env = server["env"]
    assert env["ASTERISM_WORKSPACE"] == str(tmp_path)
    assert env["ASTERISM_TARGET"].endswith("Root.lean")


def test_restores_goal_lean_after_spawn_timeout(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spawn rc != 0 paths skip parse_fn, so the parse-side
    `_restore_backup` doesn't fire. The outer try/finally in
    `_run_backward_inner` (after `run_with_session_retries` returns)
    must catch this and restore goal_lean. Otherwise the agent's
    apply_edit state leaks across dispatches."""
    gid = _seed_root_goal(tmp_path, conn)
    goal_row = db.get_goal(conn, gid)
    goal_lean = tmp_path / goal_row["lean_path"]
    original = goal_lean.read_text(encoding="utf-8")

    def fake_spawn(**kw):
        # Simulate the agent making an LSP-driven edit to goal_lean...
        if not kw.get("is_postmortem"):
            goal_lean.write_text(
                "-- agent's exploratory LSP edit\nbroken garbage\n",
                encoding="utf-8")
        # ...then the spawn times out (rc=124). Parse never runs.
        return 124

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=_mfst(), pipeline_id="pid-bw-timeout-restore")

    restored = goal_lean.read_text(encoding="utf-8")
    assert restored == original, (
        "goal_lean must restore to pre-spawn state even when spawn "
        "exits with rc != 0 and parse_fn never runs"
    )


def test_restores_goal_lean_when_parse_fails(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spawn returns rc=0 (agent claims success) but writes neither
    patch.lean nor new_*.lean — parse_fn fails with parse_proposal_fail.
    goal_lean must still be restored from backup."""
    gid = _seed_root_goal(tmp_path, conn)
    goal_row = db.get_goal(conn, gid)
    goal_lean = tmp_path / goal_row["lean_path"]
    original = goal_lean.read_text(encoding="utf-8")

    def fake_spawn(**kw):
        # Agent edits goal_lean but produces no patch / new_*.lean
        # (simulates agent confusion or output-protocol violation).
        goal_lean.write_text(
            "-- agent's stray LSP edit, no real outputs\n"
            "import Mathlib\n",
            encoding="utf-8")
        return 0  # rc 0 → parse runs

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=_mfst(), pipeline_id="pid-bw-parse-restore")

    restored = goal_lean.read_text(encoding="utf-8")
    assert restored == original, (
        "goal_lean must restore on parse failure path too"
    )
