"""LSP MCP wiring — Backward pipeline integration tests.

Verifies that:
  - `agent.spawn_llm` receives a `mcp_config_path` kwarg pointing at
    a freshly-written JSON config that connects to the long-living
    `Tooling.lsp_gateway` HTTP server.
  - The MCP target is `attempts_dir/patch.lean` (sandboxed), NOT
    `goal_lean`. This is the architectural fix that eliminates the
    worker/main race where the worker's _restore_backup could stomp
    on a concurrently-written promote_to_alias alias on goal_lean.
  - Backward never mutates `goal_lean` (Root.lean) — promote_to_alias
    in main thread is the single writer of goal_lean.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling import agent, pipeline
from Tooling.state import db, intent


def _seed_root_goal(tmp_path: Path, conn: sqlite3.Connection) -> int:
    problem = "p"
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True)
    (pdir / "problem.json").write_text(
        json.dumps({"problem": "p", "charter": "Statement: True"}),
        encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done) "
        "VALUES (?, ?, 1)",
        (problem, db.now()))
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


def _intent() -> intent.ProblemIntent:
    return intent.ProblemIntent(problem="p", charter="True")


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

    db.record_pipeline_start(conn, pipeline_id="pid-bw-mcp",
                             kind="Formalizer", target_id=str(gid),
                             target_kind="Goal")  # v38 FK for eager writes
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        intent=_intent(), pipeline_id="pid-bw-mcp")

    cfg = captured.get("mcp_config_path")
    assert cfg is not None, "mcp_config_path should be set"
    assert Path(cfg).exists()
    data = json.loads(Path(cfg).read_text(encoding="utf-8"))
    server = data["mcpServers"]["lsp"]
    # Phase 1 gateway: HTTP MCP config (was stdio command in pre-Phase-1).
    assert server["type"] == "http"
    assert server["url"].endswith("/mcp")
    assert server["headers"]["X-Asterism-Session"] == "test-stub-token"


def test_mcp_target_is_patch_lean_not_goal_lean(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Architectural invariant: MCP target must be attempts_dir/patch.lean,
    NOT goal_lean (Root.lean). This is enforced via the /register body
    sent by `_write_mcp_config`. If apply_edit targeted goal_lean, the
    agent's edits would race with promote_to_alias (verify housekeeping) —
    see the v4 pilot bug where 4/8 proved goals ended up with Root.lean
    reverted to sorry stub because worker's _restore_backup stomped the
    alias write.
    """
    import io
    import urllib.request

    gid = _seed_root_goal(tmp_path, conn)
    captured: dict = {}

    class _FakeResp:
        def __init__(self, body): self._body = body
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self._body

    def _capturing_urlopen(req, timeout=None):
        url = getattr(req, "full_url", str(req))
        if url.endswith("/register"):
            body = json.loads(req.data.decode("utf-8"))
            captured["target_path"] = Path(body["target_path"])
            return _FakeResp(b'{"session_token": "test-stub-token"}')
        if "/release/" in url:
            return _FakeResp(b'{"ok": true}')
        raise urllib.error.URLError("(test) unexpected url " + url)

    monkeypatch.setattr(urllib.request, "urlopen", _capturing_urlopen)

    def fake_spawn(**kw):
        return 124

    db.record_pipeline_start(conn, pipeline_id="pid-bw-target-check",
                             kind="Formalizer", target_id=str(gid),
                             target_kind="Goal")  # v38 FK for eager writes
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        intent=_intent(), pipeline_id="pid-bw-target-check")

    target = captured.get("target_path")
    assert target is not None, "/register should have been called"
    # Target must be patch.lean in attempts_dir, not Root.lean.
    assert target.name == "patch.lean", (
        f"MCP target must be patch.lean (sandbox), got {target.name!r}"
    )
    assert ".attempts" in target.parts, (
        f"MCP target must live under .attempts/, got {target}"
    )


def test_goal_lean_untouched_by_backward(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backward pipeline must NEVER write to goal_lean (Root.lean).
    The agent's apply_edit targets patch.lean (sandboxed); framework
    code paths (skeleton build, parse, etc.) only READ goal_lean.
    promote_to_alias in verify housekeeping is the single writer.

    Tests: even on failure paths (spawn timeout, parse fail), goal_lean's
    pre-spawn bytes are preserved without any restore mechanism.
    """
    gid = _seed_root_goal(tmp_path, conn)
    goal_row = db.get_goal(conn, gid)
    goal_lean = tmp_path / goal_row["lean_path"]
    original = goal_lean.read_text(encoding="utf-8")

    def fake_spawn(**kw):
        # Well-behaved agent: writes ONLY to attempts_dir/patch.lean
        # (would happen via apply_edit; here simulated as direct write).
        attempts_dir = Path(kw["attempts_dir"])
        (attempts_dir / "patch.lean").write_text(
            "-- exploratory edit, no commit\n",
            encoding="utf-8")
        return 124  # timeout; parse never runs

    db.record_pipeline_start(conn, pipeline_id="pid-bw-untouched",
                             kind="Formalizer", target_id=str(gid),
                             target_kind="Goal")  # v38 FK for eager writes
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        intent=_intent(), pipeline_id="pid-bw-untouched")

    after = goal_lean.read_text(encoding="utf-8")
    assert after == original, (
        "goal_lean (Root.lean) must be byte-identical to pre-spawn state — "
        "Backward pipeline writes only to attempts_dir."
    )
