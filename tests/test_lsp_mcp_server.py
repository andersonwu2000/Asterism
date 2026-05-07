"""Smoke tests for Tooling/lsp_mcp_server.py.

Phase 1 LSP swap: verify the module loads, registers the expected
tools, and respects its env-var contract. Doesn't spawn a real
`lake serve` — that's integration-level and lives outside the unit
test suite (pre-cutover verification step in builder_lsp_swap.md §5).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def _import_server(monkeypatch: pytest.MonkeyPatch,
                   workspace: Path, target: Path,
                   log_path: Path | None = None):
    """Import (or reload) lsp_mcp_server with required env set.

    The module reads ASTERISM_WORKSPACE / ASTERISM_TARGET / optional
    ASTERISM_MCP_LOG at import time. Forcing a fresh evaluation of
    the module body requires both popping sys.modules AND clearing
    the attribute on the parent package — `from Tooling import
    lsp_mcp_server` checks the package's namespace first."""
    monkeypatch.setenv("ASTERISM_WORKSPACE", str(workspace))
    monkeypatch.setenv("ASTERISM_TARGET", str(target))
    if log_path is not None:
        monkeypatch.setenv("ASTERISM_MCP_LOG", str(log_path))
    else:
        monkeypatch.delenv("ASTERISM_MCP_LOG", raising=False)

    import Tooling
    sys.modules.pop("Tooling.lsp_mcp_server", None)
    if hasattr(Tooling, "lsp_mcp_server"):
        delattr(Tooling, "lsp_mcp_server")
    from Tooling import lsp_mcp_server
    return lsp_mcp_server


def test_module_loads_with_required_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "Main.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")
    mod = _import_server(monkeypatch, workspace=tmp_path, target=target)
    assert mod.WORKSPACE == tmp_path.resolve()
    assert mod.TARGET_PATH == target.resolve()
    assert mod.LOG_PATH is None  # ASTERISM_MCP_LOG was cleared


def test_three_tools_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "Main.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")
    mod = _import_server(monkeypatch, workspace=tmp_path, target=target)
    tool_names = {t.name for t in mod.mcp._tool_manager.list_tools()}
    assert tool_names == {"apply_edit", "goal_at", "errors_at"}


def test_log_path_picked_up_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "Main.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")
    log_path = tmp_path / "mcp.jsonl"
    mod = _import_server(monkeypatch, workspace=tmp_path, target=target,
                          log_path=log_path)
    assert mod.LOG_PATH == log_path.resolve()


def test_lsp_client_does_not_start_at_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LSP cold start is heavy (mathlib load). Module-level import
    must NOT trigger it — only `main()` does, in a background thread.
    Tests need to import without spawning lake serve."""
    target = tmp_path / "Main.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")
    mod = _import_server(monkeypatch, workspace=tmp_path, target=target)
    # The global client/event must reflect "not started" state.
    assert mod._lsp_client is None
    assert not mod._lsp_ready_event.is_set()


def test_format_diag_normalizes_lsp_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LSP-wire format: 0-indexed line/col + numeric severity. Our
    format normalizes to 1-indexed line + named severity for readable
    forensic + agent-friendly output."""
    target = tmp_path / "Main.lean"
    target.write_text("import Mathlib\n", encoding="utf-8")
    mod = _import_server(monkeypatch, workspace=tmp_path, target=target)
    raw = {
        "range": {"start": {"line": 5, "character": 12}},
        "severity": 1,
        "message": "boom",
    }
    formatted = mod._format_diag(raw)
    assert formatted == {"line": 6, "col": 12, "severity": "error",
                         "message": "boom"}
