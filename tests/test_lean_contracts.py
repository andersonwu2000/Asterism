"""Framework⇄Lean contract suite (task #12).

Fingerprint/stamp logic is unit-tested Lean-free; the contracts themselves
are `real_lake`-marked wrappers over the SAME functions the daemon runs at
startup when the toolchain fingerprint changes (Tooling/quality/
lean_contracts.py) — one implementation, two consumers.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.quality import lean_contracts as lc

# Captured at import time — the conftest autouse gate-skip stub replaces
# lc.check_on_startup for every test (so dispatcher e2es don't run real
# contracts against verify stubs); tests of the REAL function restore it
# (same pattern as test_gateway_lifecycle's real-fn restore).
_REAL_CHECK_ON_STARTUP = lc.check_on_startup


def _ws(tmp_path: Path, toolchain="leanprover/lean4:v9.9.9",
        manifest='{"packages": []}') -> Path:
    (tmp_path / "lean-toolchain").write_text(toolchain, encoding="utf-8")
    (tmp_path / "lake-manifest.json").write_text(manifest, encoding="utf-8")
    return tmp_path


def test_fingerprint_changes_with_toolchain(tmp_path):
    ws = _ws(tmp_path)
    fp1 = lc.toolchain_fingerprint(ws)
    assert fp1 == lc.toolchain_fingerprint(ws)          # stable
    (ws / "lean-toolchain").write_text("leanprover/lean4:v10.0.0",
                                       encoding="utf-8")
    assert lc.toolchain_fingerprint(ws) != fp1
    fp2 = lc.toolchain_fingerprint(ws)
    (ws / "lake-manifest.json").write_text('{"packages": ["x"]}',
                                           encoding="utf-8")
    assert lc.toolchain_fingerprint(ws) != fp2          # manifest counts too


def test_check_on_startup_skips_when_stamped(tmp_path, monkeypatch):
    monkeypatch.setattr(lc, "check_on_startup", _REAL_CHECK_ON_STARTUP)
    ws = _ws(tmp_path)
    calls = {"n": 0}

    def fake_run_all(w):
        calls["n"] += 1
        return [("c", True, "")]
    monkeypatch.setattr(lc, "run_all", fake_run_all)
    assert lc.check_on_startup(ws)          # no stamp → runs + stamps
    assert calls["n"] == 1
    assert lc.check_on_startup(ws)          # unchanged → skips
    assert calls["n"] == 1
    (ws / "lean-toolchain").write_text("leanprover/lean4:v10.0.0",
                                       encoding="utf-8")
    assert lc.check_on_startup(ws)          # changed → runs again
    assert calls["n"] == 2


def test_check_on_startup_refuses_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(lc, "check_on_startup", _REAL_CHECK_ON_STARTUP)
    ws = _ws(tmp_path)
    monkeypatch.setattr(lc, "run_all",
                        lambda w: [("good", True, ""),
                                   ("bad", False, "parse drift")])
    assert lc.check_on_startup(ws) is False
    # a FAILED run must NOT stamp — next startup re-runs
    assert lc._read_stamp(ws) is None
    # emergency override
    monkeypatch.setenv("ASTERISM_SKIP_LEAN_CONTRACTS", "1")
    assert lc.check_on_startup(ws) is True


# ---------------------------------------------------------------------
# The real contracts — opt-in (ASTERISM_REAL_LAKE=1), shared warm gateway.
# ---------------------------------------------------------------------

@pytest.mark.real_lake
@pytest.mark.parametrize("name,fn", lc.CONTRACTS, ids=[n for n, _ in lc.CONTRACTS])
def test_lean_contract(name, fn):
    workspace = Path(__file__).resolve().parents[1]
    ok, detail = fn(workspace)
    assert ok, f"{name}: {detail}"
