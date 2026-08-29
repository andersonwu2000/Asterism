"""Owner design 2026-08-29: the gateway computes to completion or hits an
elaboration wall (worker killed, slot re-warmed, hard failure) — never an
"elaborating, 0 diagnostics" limbo — and `native_decide` is billed before
the write (resend-to-confirm), not discovered at the commit axiom gate
after minutes of native compilation. The wall is measured in the worker's
CPU seconds (a crowded machine must not fail a converging proof), with a
loose wall-clock net for a worker that never runs."""
from __future__ import annotations

from types import SimpleNamespace

from Tooling.lsp.gateway import rpc, state, wall
from Tooling.llm import codex_cli


def _meta(tmp_path, **kw):
    m = state.SessionMetadata(
        pipeline_id="pipe-w", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None, file_content="")
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _fast(monkeypatch, wall_s=0.05, heavy=0.15, slice_s=0.005, factor=4.0):
    monkeypatch.setattr(wall, "ELAB_WALL_SEC", wall_s)
    monkeypatch.setattr(wall, "ELAB_WALL_HEAVY_SEC", heavy)
    monkeypatch.setattr(wall, "ELAB_WALL_SLICE_SEC", slice_s)
    monkeypatch.setattr(wall, "ELAB_WALL_CLOCK_FACTOR", factor)


# ---------------------------------------------------------------- walls

def test_default_wall_and_heavy_wall_follow_the_declared_budget(tmp_path):
    assert wall._elab_wall_for(_meta(tmp_path)) == wall.ELAB_WALL_SEC
    assert wall._elab_wall_for(_meta(tmp_path, hb_limit=200_000)) == wall.ELAB_WALL_SEC
    assert wall._elab_wall_for(_meta(tmp_path, hb_limit=4_000_000)) == wall.ELAB_WALL_HEAVY_SEC
    assert wall._elab_wall_for(_meta(tmp_path, hb_limit=0)) == wall.ELAB_WALL_HEAVY_SEC


def test_walls_sit_under_the_client_timeouts_and_wedge_watchdog():
    from Tooling.lsp.gateway import backend as _b
    assert wall.ELAB_WALL_SEC < wall.ELAB_WALL_HEAVY_SEC < _b._BACKEND_WEDGE_SEC
    assert wall.ELAB_WALL_HEAVY_SEC + 300 <= 1500  # codex tool_timeout_sec


class _Backend:
    def __init__(self, converge: bool):
        self.converge = converge
        self.calls: list = []

    def wait_for_diagnostics(self, uri, version, timeout):
        self.calls.append(("wait", uri, version, timeout))
        if not self.converge:
            raise TimeoutError("still elaborating")

    def did_close(self, path):
        self.calls.append(("close", path))

    def did_open(self, path, content):
        self.calls.append(("open", path, content))

    def wait_for_file_done(self, uri, timeout):
        self.calls.append(("warm", uri, timeout))


def _slot():
    return SimpleNamespace(slot_uri="file:///s/0.lean", slot_path="/s/0.lean",
                           slot_id=0, file_version=7,
                           content_pipeline_id="pipe-w", line_map=[1])


def test_converged_elaboration_returns_final_and_touches_nothing(
        tmp_path, monkeypatch):
    monkeypatch.setattr(wall, "_worker_meter", lambda uri: None)
    b = _Backend(converge=True)
    s = _slot()
    assert wall._await_elaboration(b, s, _meta(tmp_path)) == (True, None)
    assert b.calls[0][:3] == ("wait", s.slot_uri, 7)
    assert s.content_pipeline_id == "pipe-w"


def test_clock_mode_when_no_worker_meter(tmp_path, monkeypatch):
    """No worker to meter (frozen slot, foreign backend) → the budget is
    wall-clock, as before."""
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch)
    monkeypatch.setattr(wall, "_worker_meter", lambda uri: None)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: False)
    b = _Backend(converge=False)
    s = _slot()
    ok, info = wall._await_elaboration(b, s, _meta(tmp_path))
    assert ok is False and info["mode"] == "clock"
    assert info["elapsed_s"] >= 0.05 - 0.01
    assert info["worker_reclaimed"] is True, "a slot with no worker still re-warms"
    assert ("open", s.slot_path, state.WARMUP_CONTENT) in b.calls
    assert s.content_pipeline_id is None and s.line_map is None
    assert "FAILURE" in info["teaching"]


def test_cpu_mode_spends_the_budget_in_cpu_seconds_not_wall_clock(
        tmp_path, monkeypatch):
    """A starved worker (crowded lanes) burns little CPU per wall-clock
    second: the wall must not fire on wall-clock alone before the clock
    cap, and it fires once the CPU budget is consumed."""
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch, wall_s=0.05, factor=100.0)   # clock cap far away
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    cpu = {"t": 100.0}
    calls = {"n": 0}

    def meter(uri):
        calls["n"] += 1
        # every meter read after the first adds 0.02 CPU-s: budget 0.05
        # is crossed on the 4th read regardless of the wall-clock spent
        if calls["n"] > 1:
            cpu["t"] += 0.02
        return (4242, cpu["t"], 0)
    monkeypatch.setattr(wall, "_worker_meter", meter)
    b = _Backend(converge=False)
    ok, info = wall._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is False and info["mode"] == "cpu"
    assert info["cpu_s"] >= 0.05
    assert "CPU-seconds consumed" in info["reason"]


def test_cpu_mode_clock_cap_catches_a_worker_that_never_runs(
        tmp_path, monkeypatch):
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch, wall_s=1000.0, slice_s=0.005, factor=0.0001)  # cap ~0.1s
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    monkeypatch.setattr(wall, "_worker_meter", lambda uri: (4242, 5.0, 0))  # no CPU progress
    b = _Backend(converge=False)
    ok, info = wall._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is False and info["mode"] == "cpu"
    assert "starved or hung" in info["reason"]
    assert info["cpu_s"] == 0.0


def test_wall_hit_with_rewarm_failure_reports_not_reclaimed(tmp_path, monkeypatch):
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch)
    monkeypatch.setattr(wall, "_worker_meter", lambda uri: None)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    b = _Backend(converge=False)

    def broken_open(path, content):
        raise RuntimeError("no lean")
    b.did_open = broken_open
    ok, info = wall._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is False and info["worker_reclaimed"] is False


# ------------------------------------------------------- native_decide

def test_native_decide_gate_asks_once_then_the_resend_passes(tmp_path):
    m = _meta(tmp_path)
    body = "theorem t : (3 : Nat) < 5 := by native_decide"
    first = rpc._native_decide_gate(m, body)
    assert first and "Resend this identical write" in first
    assert "decide" in first and "cannot land" in first
    assert rpc._native_decide_gate(m, body) is None, "resend must pass"


def test_native_decide_gate_reasks_on_changed_content(tmp_path):
    m = _meta(tmp_path)
    assert rpc._native_decide_gate(m, "by native_decide") is not None
    assert rpc._native_decide_gate(m, "by native_decide -- v2") is not None


def test_native_decide_gate_stays_silent_otherwise(tmp_path):
    m = _meta(tmp_path)
    assert rpc._native_decide_gate(m, "theorem t : True := by decide") is None
    assert rpc._native_decide_gate(m, "-- native_decidex is not the tactic") is None
    assert rpc._native_decide_gate(m, "exact Lean.ofReduceBool _ _ rfl") is not None


# ------------------------------------------------ client-side timeouts

def test_codex_toml_carries_a_tool_timeout_above_the_heavy_wall(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text('{"mcpServers": {"lsp": {"url": "http://127.0.0.1:1/mcp"}}}',
                   encoding="utf-8")
    toml = codex_cli._mcp_servers_toml(cfg)
    assert "tool_timeout_sec = 1500" in toml


def test_cpu_mode_rebases_on_a_replacement_worker_and_survives_a_respawn_gap(
        tmp_path, monkeypatch):
    """The lean server replaces the file worker on a header change: the
    new pid's CPU clock starts at zero. Subtracting the old baseline
    would make the budget unreachable (only the clock cap could ever
    fire). A None reading in between (respawn gap) is grace, not a
    verdict."""
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch, wall_s=0.05, factor=100.0)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    readings = iter([(1, 300.0, 0),       # old worker, big baseline
                     None,                # respawn gap: one slice of grace
                     (2, 0.02, 0), (2, 0.04, 0), (2, 0.06, 0), (2, 0.08, 0)])
    monkeypatch.setattr(wall, "_worker_meter",
                        lambda uri: next(readings, (2, 0.5, 0)))
    b = _Backend(converge=False)
    ok, info = wall._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is False and info["mode"] == "cpu"
    assert "CPU-seconds consumed" in info["reason"]
    assert 0.05 <= info["cpu_s"] < 1.0, "rebased on the new pid, not 300-off"


def test_cpu_mode_gives_up_when_the_worker_stays_gone(tmp_path, monkeypatch):
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch, wall_s=1000.0, factor=100.0)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    readings = iter([(1, 1.0, 0)])
    monkeypatch.setattr(wall, "_worker_meter",
                        lambda uri: next(readings, None))
    b = _Backend(converge=False)
    ok, info = wall._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is False and info["reason"] == "worker gone"
    assert info["worker_reclaimed"] is True
