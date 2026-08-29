"""Owner design 2026-08-29: the gateway computes to completion or hits an
elaboration wall (worker killed, slot re-warmed, hard failure) — never an
"elaborating, 0 diagnostics" limbo — and `native_decide` is billed before
the write (resend-to-confirm), not discovered at the commit axiom gate
after minutes of native compilation."""
from __future__ import annotations

from types import SimpleNamespace

from Tooling.lsp.gateway import rpc, state
from Tooling.llm import codex_cli


def _meta(tmp_path, **kw):
    m = state.SessionMetadata(
        pipeline_id="pipe-w", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None, file_content="")
    for k, v in kw.items():
        setattr(m, k, v)
    return m


# ---------------------------------------------------------------- walls

def test_default_wall_and_heavy_wall_follow_the_declared_budget(tmp_path):
    assert rpc._elab_wall_for(_meta(tmp_path)) == rpc.ELAB_WALL_SEC
    assert rpc._elab_wall_for(_meta(tmp_path, hb_limit=200_000)) == rpc.ELAB_WALL_SEC
    assert rpc._elab_wall_for(_meta(tmp_path, hb_limit=4_000_000)) == rpc.ELAB_WALL_HEAVY_SEC
    assert rpc._elab_wall_for(_meta(tmp_path, hb_limit=0)) == rpc.ELAB_WALL_HEAVY_SEC


def test_walls_sit_under_the_client_timeouts_and_wedge_watchdog():
    from Tooling.lsp.gateway import backend as _b
    assert rpc.ELAB_WALL_SEC < rpc.ELAB_WALL_HEAVY_SEC < _b._BACKEND_WEDGE_SEC
    assert rpc.ELAB_WALL_HEAVY_SEC + 300 <= 1500  # codex tool_timeout_sec


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


def test_converged_elaboration_returns_final_and_touches_nothing(tmp_path):
    b = _Backend(converge=True)
    s = _slot()
    assert rpc._await_elaboration(b, s, _meta(tmp_path)) == (True, None)
    assert b.calls == [("wait", s.slot_uri, 7, rpc.ELAB_WALL_SEC)]
    assert s.content_pipeline_id == "pipe-w"


def test_wall_hit_kills_the_worker_rewarms_the_slot_and_fails_hard(
        tmp_path, monkeypatch):
    from Tooling.lsp.gateway import governor
    killed: list = []
    monkeypatch.setattr(governor, "_kill_worker_for_uri",
                        lambda uri: killed.append(uri) or True)
    b = _Backend(converge=False)
    s = _slot()
    ok, info = rpc._await_elaboration(b, s, _meta(tmp_path, hb_limit=4_000_000))
    assert ok is False
    assert killed == [s.slot_uri]
    assert ("open", s.slot_path, state.WARMUP_CONTENT) in b.calls
    assert any(c[0] == "warm" for c in b.calls)
    assert s.content_pipeline_id is None and s.line_map is None
    assert info["wall_s"] == rpc.ELAB_WALL_HEAVY_SEC
    assert info["worker_reclaimed"] is True
    assert "FAILURE" in info["teaching"]


def test_wall_hit_with_rewarm_failure_still_fails_hard(tmp_path, monkeypatch):
    from Tooling.lsp.gateway import governor
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    b = _Backend(converge=False)

    def broken_open(path, content):
        raise RuntimeError("no lean")
    b.did_open = broken_open
    ok, info = rpc._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is False and info["worker_reclaimed"] is False


def test_no_elaborating_limbo_left_in_rpc():
    import inspect
    src = inspect.getsource(rpc)
    assert "_ELABORATING_WARNING" not in src
    assert '"elaborating"' not in src


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
