"""The silent-degradation ledger (`Tooling/core/degraded.py`): best-effort
steps that fail must land in `daemon status`'s `degraded` field, not only
in a log line. Born 2026-08-29 — dedupe's defeq probe had fail-opened for
days on WinError 206 and the only trace was `(non-fatal)` in the log."""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

from Tooling.core import degraded
from Tooling.pipeline import _lake
from Tooling.quality import dedupe, dedupe_probe

# conftest's autouse fixture stubs `_batch_provable_via_apply` per test;
# bind the genuine function at import (collection runs before fixtures).
_REAL_APPLY = dedupe._batch_provable_via_apply

_PAIRS = [("∀ n : Nat, n = n", "Problems.X.proofs.L_a", "Problems.X.a")]


def test_record_counts_and_keeps_last_detail(tmp_path):
    degraded.record(tmp_path, "k", "first   detail")
    degraded.record(tmp_path, "k", "x" * 500)
    snap = degraded.snapshot(tmp_path)
    assert snap["k"]["count"] == 2
    assert len(snap["k"]["last_detail"]) == 200
    assert snap["k"]["last_at"].endswith("+00:00")
    on_disk = json.loads(degraded.ledger_path(tmp_path).read_text(encoding="utf-8"))
    assert on_disk == snap


def test_snapshot_empty_when_nothing_recorded(tmp_path):
    assert degraded.snapshot(tmp_path) == {}


def test_reset_clears_the_ledger_and_is_idempotent(tmp_path):
    degraded.record(tmp_path, "k", "d")
    degraded.reset(tmp_path)
    assert degraded.snapshot(tmp_path) == {}
    degraded.reset(tmp_path)


def test_record_never_raises(tmp_path, monkeypatch):
    def broken_store(*a, **k):
        raise OSError("disk gone")
    monkeypatch.setattr(degraded, "_store", broken_store)
    degraded.record(tmp_path, "k", "d")  # must swallow


def test_dedupe_preflight_failure_lands_in_ledger(tmp_path, monkeypatch):
    def boom(workspace, modules):
        raise OSError("[WinError 206] filename or extension too long")
    monkeypatch.setattr(_lake, "lake_build_modules", boom)
    monkeypatch.setattr(dedupe_probe.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0,
                                                        stdout="", stderr=""))
    assert _REAL_APPLY(tmp_path, "X", _PAIRS) == [True]
    entry = degraded.snapshot(tmp_path)["dedupe_preflight_build"]
    assert entry["count"] == 1
    assert "WinError 206" in entry["last_detail"]


def test_dedupe_probe_timeout_lands_in_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(_lake, "lake_build_modules", lambda ws, mods: (True, ""))

    def timed_out(*a, **k):
        raise subprocess.TimeoutExpired(cmd="lake", timeout=1)
    monkeypatch.setattr(dedupe_probe.subprocess, "run", timed_out)
    assert _REAL_APPLY(tmp_path, "X", _PAIRS) == [None]
    assert degraded.snapshot(tmp_path)["dedupe_probe_timeout"]["count"] == 1


def test_dedupe_global_error_lands_in_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(_lake, "lake_build_modules", lambda ws, mods: (True, ""))
    # an error on line 1 (the `import Mathlib` line) is outside every
    # pair's range → global → all pairs refused
    monkeypatch.setattr(dedupe_probe.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(
                            returncode=1, stdout="",
                            stderr="x.lean:1:0: error: object file does not exist"))
    assert _REAL_APPLY(tmp_path, "X", _PAIRS) == [False]
    entry = degraded.snapshot(tmp_path)["dedupe_probe_global_error"]
    assert entry["count"] == 1
    assert "object file" in entry["last_detail"]


def test_daemon_status_carries_degraded(tmp_path):
    from Tooling.core.cli import daemon_status
    assert daemon_status(tmp_path)["degraded"] == {}
    degraded.record(tmp_path, "dedupe_probe_global_error", "import missing")
    assert daemon_status(tmp_path)["degraded"][
        "dedupe_probe_global_error"]["count"] == 1
