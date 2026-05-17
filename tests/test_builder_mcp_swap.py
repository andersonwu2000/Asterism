"""LSP MCP wiring — Builder pipeline integration tests.

Verifies that:
  - `agent.spawn_llm` receives a `mcp_config_path` kwarg pointing at
    a freshly-written JSON config that connects to the long-living
    `Tooling.lsp_gateway` HTTP server.
  - The MCP `target` is the sandbox `attempts_dir/patch.lean`, NOT
    `goal_lean` — agent's apply_edit write-through stays inside the
    spawn dir; workspace is touched exactly once at commit time inside
    `builder_parse`. Mirrors the Backward refactor (backward.py:316-321).
  - On a post-commit verify failure, `goal_lean` is restored from the
    pre-spawn snapshot the pipeline keeps in a closure variable.
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


def test_mcp_target_is_sandbox_patch(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sandbox-model contract: the MCP gateway's `target_path` is
    `attempts_dir/patch.lean`, NOT `goal_lean`. Agent apply_edit
    write-through stays inside the spawn dir. Regression guard against
    reverting to the workspace-target design (which created a dirty
    workspace mid-spawn + needed SpawnWorkspace snapshot/restore)."""
    captured: dict = {}
    real_urlopen = None

    def fake_urlopen(req, *, timeout=None):
        # Capture /register body. Other endpoints (/release) pass through
        # to the conftest stub.
        try:
            url = req.full_url if hasattr(req, "full_url") else req.get_full_url()
        except Exception:
            url = ""
        if "/register" in url:
            try:
                body = req.data.decode("utf-8")
                captured["register_body"] = json.loads(body)
            except Exception:
                pass
        # Defer to whatever the conftest already installed.
        return real_urlopen(req, timeout=timeout)

    import urllib.request as _u
    real_urlopen = _u.urlopen
    monkeypatch.setattr(_u, "urlopen", fake_urlopen)

    gid = _seed_problem(conn, tmp_path)

    def fake_spawn(**kw):
        # Real agent writes patch.lean inside attempts_dir. We mimic.
        (kw["attempts_dir"] / "patch.lean").write_text(
            "-- main: ok\nimport Mathlib\ntheorem main : True := trivial\n",
            encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build", lambda ws, t: (True, ""))

    r = pipeline.run_builder(conn, goal_id=gid, workspace=tmp_path,
                              mfst=_mfst(), pipeline_id="pid-mcp-target")
    assert r.outcome == "proved"
    reg = captured.get("register_body") or {}
    target = Path(reg.get("target_path", ""))
    # target_path must point inside attempts_dir, not goal_lean.
    assert ".attempts" in target.as_posix(), (
        f"MCP target should be the sandbox patch.lean, got {target}"
    )
    assert target.name == "patch.lean"


def test_restores_goal_lean_when_lake_build_fails(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the agent's patch.lean lake-builds with errors, the
    post-verify failure path inside `builder_parse` restores
    `goal_lean` from the in-closure snapshot taken before the commit.
    Without restore, the next retry / cascade would see the agent's
    broken patch committed."""
    gid = _seed_problem(conn, tmp_path, initial_body="  sorry")
    goal_row = db.get_goal(conn, gid)
    goal_lean = tmp_path / goal_row["lean_path"]
    original = goal_lean.read_text(encoding="utf-8")

    def fake_spawn(**kw):
        # Sandbox model: agent writes to patch.lean only — never
        # goal_lean. The agent's patch will lake-build-reject below.
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


def test_goal_lean_untouched_on_spawn_timeout(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sandbox-model contract: spawn rc != 0 paths skip parse_fn, so
    no commit happens — goal_lean stays untouched the whole time.
    Regression guard for the workspace-target era's bug where agent's
    mid-session apply_edit leaked broken state into goal_lean even
    when the spawn timed out (cantor_xi g94 incident)."""
    gid = _seed_problem(conn, tmp_path, initial_body="  sorry")
    goal_row = db.get_goal(conn, gid)
    goal_lean = tmp_path / goal_row["lean_path"]
    original = goal_lean.read_text(encoding="utf-8")

    def fake_spawn(**kw):
        # Spawn times out before flushing any patch.lean. Sandbox is
        # empty — the salvage path sees no parseable output and returns
        # `agent_no_output`, parse never enters the commit window.
        return 124

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    pipeline.run_builder(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=_mfst(), pipeline_id="pid-builder-timeout-untouched")

    assert goal_lean.read_text(encoding="utf-8") == original, (
        "Builder sandbox model: goal_lean must stay at pre-spawn "
        "content when spawn rc != 0 and parse never commits"
    )
