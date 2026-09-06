"""The compiled lakefile configuration is established ONCE, up front.

2026-09-06, a fresh lab workspace (`.lake/` holding only the `packages`
junction): the daemon launched the gateway and ran its first `lake
build` in the same second, both lake front-ends compiled
`lakefile.lean` into `.lake/config/`, and the loser died with `error:
compiled configuration is invalid; run with '-R' to reconfigure` →
`[verify] Lab.even_sum_subsets: FAILED` → `--once and queue empty,
exit`. Every later `lake build` in that workspace failed the same way
until a single `lake -R env lean --version` (3.7s, builds nothing)
repaired it.

The fix is a preflight, not `-R` on every build. These tests fake
`subprocess` throughout — no real lake ever spawns.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from Tooling.pipeline import _lake

# conftest's autouse fixture stubs the cold-lake seams — the build door
# and, since 2026-09-07, the preflight itself. Bind the genuine
# functions at import time (collection runs before fixtures); these
# tests fake `subprocess` instead, so no real lake spawns either way.
_REAL_BUILD = _lake.lake_build_modules
_REAL_PREFLIGHT = _lake.preflight_lake_config
_REAL_RECONFIGURE = _lake.lake_reconfigure

STALE = ("error: compiled configuration is invalid; "
         "run with '-R' to reconfigure")


def _fake_subprocess(results, calls):
    """A `subprocess.run` that answers from `results` (one entry per
    call) and records the argv + cwd it was handed."""
    def run(argv, **kw):
        calls.append((list(argv), kw.get("cwd")))
        rc, out = results[min(len(calls) - 1, len(results) - 1)]
        return SimpleNamespace(returncode=rc, stdout=out, stderr="")
    return run


# ---------------------------------------------------------------------
# the preflight
# ---------------------------------------------------------------------

def test_a_valid_configuration_costs_one_call_and_never_reconfigures(
        monkeypatch, tmp_path):
    """The warm case is the common one — every restart on a workspace
    that has already been built in. `-R` there would recompile the
    configuration on every daemon start and re-open the very race this
    exists to close."""
    calls: list = []
    monkeypatch.setattr(_lake.subprocess, "run",
                        _fake_subprocess([(0, "Lean (version 4.24.0)")], calls))
    ok, out = _REAL_PREFLIGHT(tmp_path)
    assert ok is True
    assert "4.24.0" in out
    assert len(calls) == 1
    argv, cwd = calls[0]
    assert argv == ["lake", "env", "lean", "--version"]
    assert "-R" not in argv
    assert cwd == str(tmp_path)


def test_an_invalid_configuration_is_reconfigured_exactly_once(
        monkeypatch, tmp_path):
    calls: list = []
    monkeypatch.setattr(_lake.subprocess, "run", _fake_subprocess(
        [(1, STALE), (0, "Lean (version 4.24.0)")], calls))
    ok, out = _REAL_PREFLIGHT(tmp_path)
    assert ok is True
    assert "4.24.0" in out
    assert len(calls) == 2, "one probe, one repair — never a loop"
    assert calls[0][0] == ["lake", "env", "lean", "--version"]
    assert calls[1][0] == ["lake", "-R", "env", "lean", "--version"]
    assert calls[1][1] == str(tmp_path)


def test_a_reconfigure_that_also_fails_refuses_and_keeps_lakes_output(
        monkeypatch, tmp_path):
    """Both halves of what lake said survive: a caller that refuses to
    start has nothing else to show the operator."""
    calls: list = []
    monkeypatch.setattr(_lake.subprocess, "run", _fake_subprocess(
        [(1, STALE), (1, "error: no such file or directory (lakefile.lean)")],
        calls))
    ok, out = _REAL_PREFLIGHT(tmp_path)
    assert ok is False
    assert len(calls) == 2
    assert "compiled configuration is invalid" in out
    assert "lakefile.lean" in out


def test_a_failure_lake_did_not_blame_on_the_config_is_not_reconfigured(
        monkeypatch, tmp_path):
    """`-R` repairs a configuration; it does not conjure a toolchain.
    A failure that says something else comes straight back, unrepaired,
    with one call spent."""
    calls: list = []
    monkeypatch.setattr(_lake.subprocess, "run", _fake_subprocess(
        [(1, "error: unknown executable 'lean'")], calls))
    ok, out = _REAL_PREFLIGHT(tmp_path)
    assert ok is False
    assert len(calls) == 1
    assert "unknown executable" in out


def test_a_lake_that_cannot_be_spawned_is_a_refusal_not_a_crash(
        monkeypatch, tmp_path):
    def boom(argv, **kw):
        raise FileNotFoundError(2, "The system cannot find the file specified")
    monkeypatch.setattr(_lake.subprocess, "run", boom)
    ok, out = _REAL_PREFLIGHT(tmp_path)
    assert ok is False
    assert "FileNotFoundError" in out


def test_reconfigure_is_unconditional_R(monkeypatch, tmp_path):
    """The lab's call: it ESTABLISHES the configuration in a workspace
    nobody has built in, so there is nothing to preserve."""
    calls: list = []
    monkeypatch.setattr(_lake.subprocess, "run",
                        _fake_subprocess([(0, "Lean (version 4.24.0)")], calls))
    ok, _ = _REAL_RECONFIGURE(tmp_path)
    assert ok is True
    assert calls[0][0] == ["lake", "-R", "env", "lean", "--version"]


# ---------------------------------------------------------------------
# the build site says what it is looking at
# ---------------------------------------------------------------------

@pytest.fixture
def _room(monkeypatch):
    """The fence is sized from the live machine; pin it so a full box
    never turns this into a 900s wait for room."""
    monkeypatch.setattr(_lake, "fence_gb_now", lambda inflight=1: 4.0)


def test_a_build_that_hits_a_stale_configuration_names_the_repair(
        monkeypatch, tmp_path, _room):
    """The build never runs `-R` itself — it may be one of several in
    flight, and reconfiguring under them is how the breakage arose. It
    says which single command repairs the workspace instead."""
    def fake_run(argv, fence_gb=None, **kw):
        return SimpleNamespace(returncode=1, stdout="", stderr=STALE,
                               capped=False, peak_gb=None, fence_gb=None)
    monkeypatch.setattr(_lake, "run_fenced", fake_run)
    ok, detail = _REAL_BUILD(tmp_path, ["Problems.Lab.even_sum_subsets.Defs"])
    assert ok is False
    assert detail.startswith(_lake.STALE_CONFIG_HINT)
    assert "lake -R env lean --version" in detail
    assert "compiled configuration is invalid" in detail, "lake's own words stay"


def test_an_ordinary_build_failure_is_left_alone(monkeypatch, tmp_path, _room):
    def fake_run(argv, fence_gb=None, **kw):
        return SimpleNamespace(returncode=1, stdout="",
                               stderr="error: unknown identifier 'foo'",
                               capped=False, peak_gb=None, fence_gb=None)
    monkeypatch.setattr(_lake, "run_fenced", fake_run)
    ok, detail = _REAL_BUILD(tmp_path, ["A.B"])
    assert ok is False
    assert not detail.startswith(_lake.STALE_CONFIG_HINT)
    assert detail.strip() == "error: unknown identifier 'foo'"


def test_the_routine_build_never_passes_R(monkeypatch, tmp_path, _room):
    """The preflight is the single fix point. `-R` on the build path
    would recompile the configuration on every invocation and race the
    other builds in flight."""
    calls: list[list[str]] = []

    def fake_run(argv, fence_gb=None, **kw):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="",
                               capped=False, peak_gb=None, fence_gb=None)
    monkeypatch.setattr(_lake, "run_fenced", fake_run)
    _REAL_BUILD(tmp_path, ["A.B", "C.D"])
    assert calls and all("-R" not in c for c in calls)


# ---------------------------------------------------------------------
# the daemon refuses to start on a workspace lake cannot configure
# ---------------------------------------------------------------------

def test_the_dispatcher_preflights_before_it_warms_the_gateway():
    """Source-level pin: the preflight call must stand ABOVE the
    gateway warm in `dispatcher.run`. Below it, the two front-ends are
    concurrent again and the bug is back — and the ordering is exactly
    what no runtime assertion can observe cheaply."""
    src = (Path(__file__).resolve().parents[1] / "Tooling" / "core"
           / "dispatcher" / "loop.py").read_text(encoding="utf-8")
    pre = src.index("preflight_lake_config(workspace)")
    warm = src.index("_warmup.start_background(workspace)")
    assert pre < warm, "the configuration is compiled before the gateway warms"
