"""lean-asterism-server exe freshness guard (2026-07-10).

`lake build Asterism` rebuilds the library but not the custom server
executable; stale-exe workers silently drop new RPC fields. The guard:
rebuild-before-launch (refuse on build failure), warn-only on the
warm-gateway reuse path. Staleness predicate is pure (fed mtimes);
the rebuild call is injected — the side-effect fence blocks real lake.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from Tooling.lsp import lifecycle


# ── pure predicate ─────────────────────────────────────────────────

def test_staleness_predicate_pure() -> None:
    f = lifecycle.server_exe_staleness
    assert f(None, [100.0]) is False        # absent exe = visible fallback, not stale
    assert f(100.0, []) is False            # no inputs
    assert f(100.0, [50.0, 99.0]) is False  # exe newest
    assert f(100.0, [50.0, 100.5]) is True  # an input newer


# ── mtime gatherer over a fake workspace ───────────────────────────

def _mk_workspace(tmp_path: Path) -> Path:
    (tmp_path / "Asterism").mkdir()
    (tmp_path / "Asterism" / "GatewayRpc.lean").write_text("-- rpc")
    (tmp_path / "lakefile.lean").write_text("-- lake")
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v0")
    exe = lifecycle.server_exe_path(tmp_path)
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"exe")
    return tmp_path


def test_freshness_check_orders_by_mtime(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    exe = lifecycle.server_exe_path(ws)
    rpc = ws / "Asterism" / "GatewayRpc.lean"
    # exe newer than everything → fresh
    os.utime(rpc, (1000, 1000))
    os.utime(ws / "lakefile.lean", (1000, 1000))
    os.utime(ws / "lean-toolchain", (1000, 1000))
    os.utime(exe, (2000, 2000))
    stale, _ = lifecycle.check_server_exe_freshness(ws)
    assert stale is False
    # touch the RPC source → stale, and the culprit is named
    os.utime(rpc, (3000, 3000))
    stale, why = lifecycle.check_server_exe_freshness(ws)
    assert stale is True
    assert "GatewayRpc.lean" in why
    # toolchain bump also counts (real-lean.yml trigger parity)
    os.utime(rpc, (1000, 1000))
    os.utime(ws / "lean-toolchain", (3000, 3000))
    stale, why = lifecycle.check_server_exe_freshness(ws)
    assert stale is True
    assert "lean-toolchain" in why


def test_absent_exe_is_not_stale(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    lifecycle.server_exe_path(ws).unlink()
    stale, _ = lifecycle.check_server_exe_freshness(ws)
    assert stale is False


# ── ensure: rebuild / refuse policy (build injected) ───────────────

def test_ensure_rebuilds_when_stale(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    os.utime(lifecycle.server_exe_path(ws), (1000, 1000))
    os.utime(ws / "Asterism" / "GatewayRpc.lean", (2000, 2000))
    calls: list[Path] = []

    def fake_build(w: Path):
        calls.append(w)
        return True, "ok"

    lifecycle.ensure_server_exe_fresh(ws, _build=fake_build)
    assert calls == [ws]


def test_ensure_refuses_on_build_failure(tmp_path: Path) -> None:
    """Policy: the exe feeds soundness-adjacent RPCs and fails by
    silently missing fields — a failed rebuild refuses to launch."""
    ws = _mk_workspace(tmp_path)
    os.utime(lifecycle.server_exe_path(ws), (1000, 1000))
    os.utime(ws / "Asterism" / "GatewayRpc.lean", (2000, 2000))
    with pytest.raises(RuntimeError, match="refusing to launch"):
        lifecycle.ensure_server_exe_fresh(
            ws, _build=lambda w: (False, "linker exploded"))


def test_ensure_noop_when_fresh(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    for p in (ws / "Asterism" / "GatewayRpc.lean", ws / "lakefile.lean",
              ws / "lean-toolchain"):
        os.utime(p, (1000, 1000))
    os.utime(lifecycle.server_exe_path(ws), (2000, 2000))

    def boom(w: Path):
        raise AssertionError("build must not be called when fresh")

    lifecycle.ensure_server_exe_fresh(ws, _build=boom)
