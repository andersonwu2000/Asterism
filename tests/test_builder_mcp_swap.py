"""LSP MCP wiring — Builder pipeline integration tests.

Verifies that:
  - `agent.spawn_llm` receives a `mcp_config_path` kwarg pointing at
    a freshly-written JSON config that connects to the long-living
    `Tooling.lsp_gateway` HTTP server.
  - Builder backs up `goal_lean` BEFORE the agent runs (since the
    agent now edits goal_lean in-session via LSP) and restores it on
    a lake-build failure.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from Tooling import agent, pipeline
from Tooling.state import db, manifest


def _seed_problem(conn: sqlite3.Connection, tmp_path: Path,
                  initial_body: str = "  sorry") -> int:
    """Minimal workspace + DB row, parameterized initial proof body."""
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
        f"theorem main : True := by\n{initial_body}\n"
        "end Problems.p\n",
        encoding="utf-8")
    rel = root.relative_to(tmp_path).as_posix()
    gid = db.insert_goal(
        conn, problem=problem, slug="main", lean_path=rel,
        statement="True", origin="root", depth=0,
    )
    db.increment_goal_attempts(conn, gid)  # skip Phase 1 tactic_try
    return gid


def _mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="True")


def test_spawn_passes_mcp_config_path(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spawn_llm gets a mcp_config_path pointing at a freshly-written
    JSON config. The config references our MCP server module and
    carries ASTERISM_WORKSPACE / ASTERISM_TARGET envs."""
    gid = _seed_problem(conn, tmp_path)
    captured: dict = {}

    def fake_spawn(**kw):
        captured.update(kw)
        (kw["attempts_dir"] / "patch.lean").write_text(
            "-- main: ok\nimport Mathlib\ntheorem main : True := trivial\n",
            encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build",
                        lambda ws, t: (True, ""))

    r = pipeline.run_builder(conn, goal_id=gid, workspace=tmp_path,
                              mfst=_mfst(), pipeline_id="pid-lsp-on")
    assert r.outcome == "proved"

    cfg = captured.get("mcp_config_path")
    assert cfg is not None, "mcp_config_path should be set when LSP on"
    assert Path(cfg).exists(), "MCP config file should have been written"

    data = json.loads(Path(cfg).read_text(encoding="utf-8"))
    assert "lsp" in data["mcpServers"]
    server = data["mcpServers"]["lsp"]
    # Phase 1 gateway: HTTP MCP config. Token comes from the conftest
    # urlopen stub (test-stub-token).
    assert server["type"] == "http"
    assert server["url"].endswith("/mcp")
    assert server["headers"]["X-Asterism-Session"] == "test-stub-token"


def test_restores_goal_lean_when_lake_build_fails(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the agent (simulated) edits goal_lean via LSP and writes a
    bad patch.lean, the lake-build failure must restore the original
    sorry-stub from the pre-spawn backup. Otherwise the next retry
    iteration would see the agent's broken intermediate state."""
    gid = _seed_problem(conn, tmp_path, initial_body="  sorry")
    goal_row = db.get_goal(conn, gid)
    goal_lean = tmp_path / goal_row["lean_path"]
    original = goal_lean.read_text(encoding="utf-8")

    def fake_spawn(**kw):
        # Simulate agent's LSP edit polluting goal_lean...
        goal_lean.write_text(
            "-- agent's bad LSP edit\nbroken garbage\n",
            encoding="utf-8")
        # ...and writing a patch.lean that lake build will reject.
        (kw["attempts_dir"] / "patch.lean").write_text(
            "-- main: this will fail\n"
            "import Mathlib\ntheorem main : True := nonsense_tactic\n",
            encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    # Verify-unification: Builder Phase 2 verify goes through
    # gateway_lifecycle.verify_file now. Stub a failing elaborate.
    from Tooling.lsp import lifecycle as gateway_lifecycle
    monkeypatch.setattr(gateway_lifecycle, "verify_file",
        lambda path, **kw: {
            "ok": False,
            "diagnostics": [{"line": 1, "col": 0, "severity": "error",
                              "message": "error: nonsense_tactic"}],
            "diagnostic_count": 1,
            "olean_written": False, "olean_path": None,
            "axioms": None, "axiom_error": None,
        })

    r = pipeline.run_builder(conn, goal_id=gid, workspace=tmp_path,
                              mfst=_mfst(), pipeline_id="pid-restore")
    # Outcome is a terminal failure (failed / exhausted depending on
    # retry budget) — the assertion of interest is restoration, not
    # the specific outcome label.
    assert r.outcome in ("failed", "exhausted")
    restored = goal_lean.read_text(encoding="utf-8")
    assert restored == original, (
        "goal_lean must restore to pre-spawn state on lake fail"
    )


def test_restores_goal_lean_after_spawn_timeout(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spawn rc != 0 paths skip parse_fn, so the parse-side
    `_restore_backup` doesn't fire. The outer try/finally around
    `run_with_session_retries` must catch this and restore goal_lean.
    Otherwise the agent's mid-session apply_edit state leaks into the
    next retry as a broken baseline (observed cantor_xi g94)."""
    gid = _seed_problem(conn, tmp_path, initial_body="  sorry")
    goal_row = db.get_goal(conn, gid)
    goal_lean = tmp_path / goal_row["lean_path"]
    original = goal_lean.read_text(encoding="utf-8")

    def fake_spawn(**kw):
        # Simulate agent's LSP edit polluting goal_lean...
        if not kw.get("is_postmortem"):
            goal_lean.write_text(
                "-- agent's mid-session LSP edit (incomplete)\n"
                "broken garbage\n",
                encoding="utf-8")
        # ...then spawn times out (rc=124). Parse never runs.
        return 124

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=_mfst(), pipeline_id="pid-builder-timeout-restore")

    restored = goal_lean.read_text(encoding="utf-8")
    assert restored == original, (
        "Builder must restore goal_lean even when spawn rc != 0 "
        "and parse_fn never runs"
    )
