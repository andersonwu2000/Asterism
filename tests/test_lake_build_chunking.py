"""`lake_build_modules` must never hand the OS a command line longer than
the budget (WinError 206, 2026-08-29: the dedupe pre-flight passed a few
hundred proof modules in one `lake build`, Windows refused, and the whole
defeq probe silently fail-opened for days). Every module must still be
built exactly once, in order, and the aggregate verdict must be the
conjunction of the chunk verdicts."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from Tooling.pipeline import _lake

# conftest's autouse fixture stubs `_lake.lake_build_modules` per test;
# bind the genuine function at import (collection runs before fixtures).
# These tests replace `_lake.run_fenced` (the door's one subprocess
# seam since 2026-09-02), so no real `lake` ever spawns.
_REAL_BUILD = _lake.lake_build_modules


@pytest.fixture(autouse=True)
def _room(monkeypatch):
    """The fence is sized from the live machine; pin it so a full CI box
    never turns a chunking test into a 900s wait for room."""
    monkeypatch.setattr(_lake, "fence_gb_now", lambda inflight=1: 4.0)


def _mods(n: int, width: int = 69) -> list[str]:
    stem = "Problems.Combinatorics.union_closed.proofs.L_"
    return [(stem + f"m{i:04d}_").ljust(width, "x") for i in range(n)]


def test_chunker_respects_budget_and_covers_everything():
    mods = _mods(600)
    chunks = _lake.chunk_modules_for_cmdline(mods)
    assert len(chunks) > 1, "600 modules of ~69 chars must not fit one call"
    for c in chunks:
        assert len(" ".join(["lake", "build", *c])) <= _lake.LAKE_CMDLINE_BUDGET
    flat = [m for c in chunks for m in c]
    assert flat == mods, "order preserved, each module exactly once"


def test_chunker_small_list_is_one_chunk():
    mods = _mods(5)
    assert _lake.chunk_modules_for_cmdline(mods) == [mods]


def test_chunker_oversized_single_module_gets_own_chunk():
    huge = "M." + "x" * (_lake.LAKE_CMDLINE_BUDGET + 10)
    assert _lake.chunk_modules_for_cmdline(["A", huge, "B"]) == [["A"], [huge], ["B"]]


def _fake_run_factory(calls: list[list[str]], fail_on: str | None = None):
    def fake_run(argv, fence_gb=None, **kw):
        calls.append(list(argv))
        line = " ".join(argv)
        assert len(line) <= _lake.LAKE_CMDLINE_BUDGET, (
            f"command line {len(line)} chars exceeds budget")
        if fail_on is not None and fail_on in argv:
            return SimpleNamespace(returncode=1, stdout="", stderr="error: boom",
                                   capped=False, peak_gb=None, fence_gb=None)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="",
                               capped=False, peak_gb=None, fence_gb=None)
    return fake_run


def test_lake_build_modules_chunks_and_aggregates(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    monkeypatch.setattr(_lake, "run_fenced", _fake_run_factory(calls))
    mods = _mods(600)
    ok, out = _REAL_BUILD(tmp_path, mods)
    assert ok is True
    assert len(calls) > 1
    assert all(c[:2] == ["lake", "build"] for c in calls)
    built = [m for c in calls for m in c[2:]]
    assert built == mods
    assert "ok" in out


def test_lake_build_modules_any_failing_chunk_fails_the_whole(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    mods = _mods(600)
    victim = mods[-1]  # lands in the LAST chunk — earlier chunks succeed
    monkeypatch.setattr(_lake, "run_fenced",
                        _fake_run_factory(calls, fail_on=victim))
    ok, out = _REAL_BUILD(tmp_path, mods)
    assert ok is False
    assert "error: boom" in out
    built = [m for c in calls for m in c[2:]]
    assert built == mods, "a late failure must not skip earlier chunks"


def test_lake_build_modules_timeout_reports_the_chunk(monkeypatch, tmp_path):
    def fake_run(argv, fence_gb=None, **kw):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=600)
    monkeypatch.setattr(_lake, "run_fenced", fake_run)
    ok, out = _REAL_BUILD(tmp_path, ["A.B", "C.D"])
    assert ok is False
    assert "timed out" in out


def test_lake_build_modules_empty_keeps_bare_build(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    monkeypatch.setattr(_lake, "run_fenced", _fake_run_factory(calls))
    ok, _ = _REAL_BUILD(tmp_path, [])
    assert ok is True
    assert calls == [["lake", "build"]], "historical shape: one bare lake build"


def test_budget_is_well_below_windows_limit():
    assert _lake.LAKE_CMDLINE_BUDGET < 32767 // 2
