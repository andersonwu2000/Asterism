"""Shared `lake env lean` probe primitive — 3-state classification + subprocess
boilerplate (CLAUDE.md rule 6: the helper that unifies the cleanup/dedup probe
sites gets its own test, esp. the ok / error / infra split that batch_defeq's
timeout-observability fix relies on)."""
from __future__ import annotations

import subprocess
import types

from Tooling.quality import lake_probe as lp
from Tooling.quality.lake_probe import LeanRun, run_lean_source


# --- LeanRun classification (pure) ---

def test_leanrun_ok() -> None:
    r = LeanRun(0, "all good\n", False)
    assert r.ok and not r.infra and r.error_lines == frozenset()


def test_leanrun_error_lines() -> None:
    r = LeanRun(1, "Foo.lean:12:0: error: boom\nFoo.lean:30:4: error: bad", False)
    assert not r.ok and not r.infra
    assert r.error_lines == frozenset({12, 30})


def test_leanrun_infra_rc_nonzero_no_error_line() -> None:
    # rc≠0 with no attributable Lean error line = broken env, not a verdict.
    r = LeanRun(1, "lake: build failed, no lean error here", False)
    assert not r.ok and r.infra and r.error_lines == frozenset()


def test_leanrun_infra_timeout() -> None:
    r = LeanRun(None, "timeout after 240s", True)
    assert not r.ok and r.infra and r.timed_out


def test_leanrun_ok_with_warning_only() -> None:
    r = LeanRun(0, "Foo.lean:3:0: warning: unused variable", False)
    assert r.ok and not r.infra        # a warning is not an error


# --- run_lean_source (subprocess mocked) ---

def _fake_run(monkeypatch, *, returncode=0, stdout="", stderr="", raise_exc=None):
    def _run(cmd, **kw):
        _run.cmd = cmd
        if raise_exc is not None:
            raise raise_exc
        return types.SimpleNamespace(returncode=returncode, stdout=stdout,
                                     stderr=stderr)
    _run.cmd = None
    monkeypatch.setattr(lp.subprocess, "run", _run)
    return _run


def test_run_lean_source_ok_and_cleans_up(tmp_path, monkeypatch) -> None:
    _fake_run(monkeypatch, returncode=0, stdout="ok\n")
    r = run_lean_source(tmp_path, "theorem t : True := trivial", prefix="_t")
    assert r.ok and r.returncode == 0 and "ok" in r.output
    assert not list((tmp_path / ".attempts").glob("_t_*.lean"))   # temp removed


def test_run_lean_source_error(tmp_path, monkeypatch) -> None:
    _fake_run(monkeypatch, returncode=1, stderr="X.lean:5:0: error: nope")
    r = run_lean_source(tmp_path, "bad", prefix="_t")
    assert not r.ok and not r.infra and r.error_lines == frozenset({5})


def test_run_lean_source_timeout_is_infra(tmp_path, monkeypatch) -> None:
    _fake_run(monkeypatch, raise_exc=subprocess.TimeoutExpired("lake", 240))
    r = run_lean_source(tmp_path, "x", prefix="_t", timeout=240)
    assert r.infra and r.timed_out and r.returncode is None
    assert not list((tmp_path / ".attempts").glob("_t_*.lean"))   # cleaned on timeout


def test_run_lean_source_oserror_is_infra(tmp_path, monkeypatch) -> None:
    _fake_run(monkeypatch, raise_exc=OSError("no lake on PATH"))
    r = run_lean_source(tmp_path, "x", prefix="_t")
    assert r.infra and not r.timed_out and r.returncode is None


def test_run_lean_source_json_flag(tmp_path, monkeypatch) -> None:
    fake = _fake_run(monkeypatch, returncode=0)
    run_lean_source(tmp_path, "x", prefix="_t", json=True)
    assert "--json" in fake.cmd
