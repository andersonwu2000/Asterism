"""LSP MCP wiring — Backward pipeline integration tests.

Verifies that:
  - `agent.spawn_llm` receives a `mcp_config_path` kwarg pointing at
    a freshly-written JSON config that connects to the long-living
    `Tooling.lsp_gateway` HTTP server with target=goal_lean.
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
    JSON config that addresses the long-living Tooling.lsp_gateway
    via HTTP, with the session token in X-Asterism-Session."""
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
    # Phase 1 gateway: HTTP MCP config (was stdio command in pre-Phase-1).
    assert server["type"] == "http"
    assert server["url"].endswith("/mcp")
    assert server["headers"]["X-Asterism-Session"] == "test-stub-token"


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


def test_no_contamination_across_retries(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: each backward_spawn must restore goal_lean from a
    PRISTINE snapshot taken once before the retry loop. The earlier
    impl re-snapshotted at the top of every spawn — so iter N's
    snapshot captured iter N-1's apply_edit contamination, and outer
    finally's restore brought goal_lean back to a contaminated baseline
    instead of the pre-pipeline original. Symptom (SG g217): each
    retry's agent saw the prior retry's broken partial proof and built
    on it, deepening the contamination per iter (e.g. accumulated
    `intro p q r` lines).

    Test simulates: agent writes a unique line per attempt + returns
    rc=128 (STUCK_THINKING), helper rescues with rc=124 (TIMEOUT),
    which buffers a stuck-thinking failure and continues to next iter.
    After the budget exhausts, goal_lean must equal original — not
    accumulate iteration tags."""
    from Tooling.llm.base import SpawnRC
    gid = _seed_root_goal(tmp_path, conn)
    goal_row = db.get_goal(conn, gid)
    goal_lean = tmp_path / goal_row["lean_path"]
    original = goal_lean.read_text(encoding="utf-8")

    call_counter = {"n": 0}

    def fake_spawn(**kw):
        if kw.get("is_postmortem"):
            return 0
        call_counter["n"] += 1
        # Each spawn appends a unique iteration tag, mimicking the
        # agent's apply_edit accretion across retries. With the bug,
        # outer finally's restore would leave ALL these tags in place.
        prior = goal_lean.read_text(encoding="utf-8")
        goal_lean.write_text(
            prior + f"-- iter {call_counter['n']} contamination\n",
            encoding="utf-8")
        # Rescue path (is_rescue=True) — return TIMEOUT to fall through
        # to next iter. Main path — return STUCK_THINKING to enter the
        # rescue branch.
        if kw.get("is_rescue"):
            return int(SpawnRC.TIMEOUT)
        return int(SpawnRC.STUCK_THINKING)

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=_mfst(), pipeline_id="pid-bw-no-contam")

    restored = goal_lean.read_text(encoding="utf-8")
    assert restored == original, (
        f"goal_lean accumulated contamination across {call_counter['n']} "
        f"spawn calls — expected pristine, got:\n{restored}"
    )
    # Sanity: ensure the helper actually retried more than once (else
    # the test passes trivially).
    assert call_counter["n"] >= 2, (
        f"helper only called spawn {call_counter['n']} time(s); test "
        f"needs >=2 iters to exercise the contamination path"
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
