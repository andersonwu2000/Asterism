"""lean-asterism-server exe freshness guard (2026-07-10).

`lake build Asterism` rebuilds the library but not the custom server
executable; stale-exe workers silently drop new RPC fields. The guard:
build-before-launch (refuse on build failure), warn-only on the
warm-gateway reuse path. Staleness predicate is pure (fed mtimes);
the build call is injected — the side-effect fence blocks real lake.

2026-09-07: an ABSENT exe goes down the same build path as a stale one.
It used to read "not stale, fall back to stock workers"; that fallback
is not a degradation — the lean interface-contract gate refuses a
gateway whose workers lack the Asterism RPCs, so absence cost a fresh
workspace ~40 s of warm-up and a Strategist wake before failing hard.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from Tooling.lsp import lifecycle


# ── pure predicate ─────────────────────────────────────────────────

def test_staleness_predicate_pure() -> None:
    f = lifecycle.server_exe_staleness
    assert f(None, [100.0]) is True         # absent exe must be built
    assert f(None, []) is True              # absent, no inputs: built
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


def test_absent_exe_needs_a_build(tmp_path: Path) -> None:
    """A fresh workspace (only `.lake/packages` junctioned in) has no
    exe. That is a build, not a fallback."""
    ws = _mk_workspace(tmp_path)
    lifecycle.server_exe_path(ws).unlink()
    needs_build, why = lifecycle.check_server_exe_freshness(ws)
    assert needs_build is True
    assert "not built" in why


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


# ── ensure: an ABSENT exe is built, not fallen back from (2026-09-07) ─

def test_ensure_builds_when_exe_absent(tmp_path: Path) -> None:
    """Fresh workspace: no exe at all → build it once, then proceed."""
    ws = _mk_workspace(tmp_path)
    exe = lifecycle.server_exe_path(ws)
    exe.unlink()
    calls: list[Path] = []

    def fake_build(w: Path):
        calls.append(w)
        exe.write_bytes(b"built")      # a real lake build leaves the exe
        return True, "ok"

    lifecycle.ensure_server_exe_fresh(ws, _build=fake_build)
    assert calls == [ws]
    assert exe.exists()


def test_ensure_refuses_when_absent_and_build_fails(tmp_path: Path) -> None:
    """Refusal carries lake's output — the daemon log is where this is
    diagnosed, and "gateway won't start" alone names no cause."""
    ws = _mk_workspace(tmp_path)
    lifecycle.server_exe_path(ws).unlink()
    with pytest.raises(RuntimeError, match="refusing to launch") as ei:
        lifecycle.ensure_server_exe_fresh(
            ws, _build=lambda w: (False, "unknown target: server"))
    assert "unknown target: server" in str(ei.value)


def test_ensure_refuses_when_build_leaves_no_exe(tmp_path: Path) -> None:
    """No silent fallback left: a build that returns 0 without producing
    the binary is an error, not a stock-worker launch."""
    ws = _mk_workspace(tmp_path)
    lifecycle.server_exe_path(ws).unlink()
    with pytest.raises(RuntimeError, match="still missing") as ei:
        lifecycle.ensure_server_exe_fresh(
            ws, _build=lambda w: (True, "warning: nothing to do"))
    assert "warning: nothing to do" in str(ei.value)


# ── client.start: the stock-worker fallback is gone ────────────────

def test_client_start_runs_the_build_gate(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`LspClient.start` used to probe the exe and silently fall back to
    stock workers; it now goes through the same build gate as the
    daemon's launch path (gate raising = no `lake serve` spawn)."""
    from Tooling.lsp.client import LspClient
    ws = _mk_workspace(tmp_path)
    calls: list[Path] = []

    def _gate(w: Path, **kw):
        calls.append(w)
        raise RuntimeError("build gate ran")

    monkeypatch.setattr(lifecycle, "ensure_server_exe_fresh", _gate)
    c = LspClient.__new__(LspClient)     # skip __init__'s thread/queue setup
    c.workspace = ws
    with pytest.raises(RuntimeError, match="build gate ran"):
        c.start()
    assert calls == [ws]


def test_client_start_refuses_when_exe_still_missing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Backstop: gate satisfied but no binary → refuse, never launch
    stock workers (they fail the lean interface-contract gate anyway)."""
    from Tooling.lsp.client import LspClient
    ws = _mk_workspace(tmp_path)
    lifecycle.server_exe_path(ws).unlink()
    monkeypatch.setattr(lifecycle, "ensure_server_exe_fresh",
                        lambda w, **kw: None)
    c = LspClient.__new__(LspClient)
    c.workspace = ws
    with pytest.raises(RuntimeError, match="lean-asterism-server is missing"):
        c.start()
