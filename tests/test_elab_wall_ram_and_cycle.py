"""Owner rulings 2026-08-30 (local health check of the union_closed run):

* The elaboration wall gets a second meter — the worker's RAM growth
  WITHIN this one elaboration. Priority rule: a worker that is fat
  because it grew slowly across earlier calls is the mid-lease rewarm's
  business (it is re-warmed and handed back); only a single elaboration
  that inflates the worker past its budget is killed, and the agent is
  told that computing harder will not pass — split, bound, or return
  the goal to NL.
* Content that already hit the wall is refused on resend before any
  elaboration (slot 2 hit the CPU wall four times on one session).
* A file that names one of its own STRICT ANCESTORS is refused at the
  editing tools, not at commit (five spawns died at commit for this in
  one afternoon, ~16 min each).
* A worker crash carries the Lean server's stderr tail so the cause is
  evidence, not a guess.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from Tooling.lsp import lifecycle as _lifecycle
from Tooling.lsp.gateway import gates, state, wall
from Tooling.state import db

# captured at import: the default run stubs the gateway client functions
# per test (conftest cold-lake stub), and the stub has its own signature
_REAL_VERIFY_IN_SESSION = _lifecycle.verify_in_session

MB = 1024 * 1024


def _meta(tmp_path, **kw):
    m = state.SessionMetadata(
        pipeline_id="pipe-w", target_path=tmp_path / "x.lean",
        problem="p", workspace=tmp_path, log_path=None, file_content="")
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _fast(monkeypatch, wall_s=0.05, slice_s=0.005, factor=100.0):
    monkeypatch.setattr(wall, "ELAB_WALL_SEC", wall_s)
    monkeypatch.setattr(wall, "ELAB_WALL_HEAVY_SEC", wall_s * 3)
    monkeypatch.setattr(wall, "ELAB_WALL_SLICE_SEC", slice_s)
    monkeypatch.setattr(wall, "ELAB_WALL_CLOCK_FACTOR", factor)


class _Backend:
    def __init__(self, converge_after: "int | None" = None):
        self.converge_after = converge_after
        self.calls: list = []
        self.tail = ""

    def wait_for_diagnostics(self, uri, version, timeout):
        self.calls.append(("wait", uri, version, timeout))
        n = sum(1 for c in self.calls if c[0] == "wait")
        if self.converge_after is not None and n >= self.converge_after:
            return
        raise TimeoutError("still elaborating")

    def did_close(self, path):
        self.calls.append(("close", path))

    def did_open(self, path, content):
        self.calls.append(("open", path, content))

    def wait_for_file_done(self, uri, timeout):
        self.calls.append(("warm", uri, timeout))

    def stderr_tail(self, limit=4000):
        return self.tail


def _slot():
    return SimpleNamespace(slot_uri="file:///s/0.lean", slot_path="/s/0.lean",
                           slot_id=0, file_version=7,
                           content_pipeline_id="pipe-w", line_map=[1])


# ---------------------------------------------------------------- RAM wall

def test_a_fat_but_flat_worker_is_not_the_walls_business(tmp_path, monkeypatch):
    """Priority rule: absolute size never kills. An 8 GB worker that
    does not grow during this elaboration converges normally — the
    residue is the mid-lease rewarm's to reclaim at the next boundary."""
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch)
    monkeypatch.setattr(wall, "_ram_wall_bytes", lambda: 100 * MB)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    monkeypatch.setattr(wall, "_worker_meter",
                        lambda uri: (4242, 1.0, 8000 * MB))   # fat, flat
    b = _Backend(converge_after=3)
    ok, info = wall._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is True and info is None
    assert not any(c[0] == "close" for c in b.calls), "no kill for size alone"


def test_an_elaboration_that_inflates_past_its_budget_is_walled(
        tmp_path, monkeypatch):
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch)
    monkeypatch.setattr(wall, "_ram_wall_bytes", lambda: 100 * MB)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    priv = {"b": 1000 * MB}

    def meter(uri):
        priv["b"] += 60 * MB          # +60 MB per read: crosses 100 MB on read 3
        return (4242, 0.001, priv["b"])
    monkeypatch.setattr(wall, "_worker_meter", meter)
    b = _Backend(converge_after=None)
    ok, info = wall._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is False
    assert info["mode"] == "cpu"
    assert "grew" in info["reason"] and "RAM" in info["reason"]
    assert info["ram_growth_mb"] >= 100
    assert info["worker_reclaimed"] is True
    t = info["teaching"]
    assert "split" in t.lower() and "NL" in t, \
        "the way out is named: split / bound / return the goal to NL"


def test_ram_budget_derives_from_the_machine_not_a_pinned_gb(monkeypatch):
    """No per-provider or per-task constant: the per-elaboration RAM
    allowance is the ledger budget divided by the warm target, times
    the wall factor; with no budget the RAM meter is off (None)."""
    monkeypatch.setattr(wall._state, "ram_budget_gb", 26.0)
    monkeypatch.setattr(wall._state, "warm_target", 13)
    assert wall._ram_wall_bytes() == pytest.approx(
        26.0 / 13 * wall.ELAB_RAM_WALL_FACTOR * 1024 ** 3)
    monkeypatch.setattr(wall._state, "ram_budget_gb", None)
    assert wall._ram_wall_bytes() is None


def test_ram_growth_rebases_on_a_replacement_worker(tmp_path, monkeypatch):
    """A header-change respawn starts a new pid at a fresh baseline —
    its first reading is not "growth"."""
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch)
    monkeypatch.setattr(wall, "_ram_wall_bytes", lambda: 100 * MB)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    readings = iter([(1, 0.0, 500 * MB), (2, 0.0, 2000 * MB),
                     (2, 0.0, 2010 * MB)])
    monkeypatch.setattr(wall, "_worker_meter",
                        lambda uri: next(readings, (2, 0.0, 2010 * MB)))
    b = _Backend(converge_after=4)
    ok, _ = wall._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is True, "the 1.5 GB jump is a new pid's baseline, not growth"


# ------------------------------------------------------- walled resend

def test_walled_content_is_refused_on_resend_before_any_elaboration(
        tmp_path, monkeypatch):
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    monkeypatch.setattr(wall, "_worker_meter", lambda uri: None)  # clock mode
    m = _meta(tmp_path)
    body = "theorem t : (3 : Nat) < 5 := by decide"
    assert wall._walled_gate(m, body) is None, "first time: nothing to refuse"
    ok, info = wall._await_elaboration(_Backend(), _slot(), m, content=body)
    assert ok is False
    refusal = wall._walled_gate(m, body)
    assert refusal is not None and "already hit" in refusal
    assert "split" in refusal.lower() and "NL" in refusal
    assert wall._walled_gate(m, body + "\n-- reworked") is None, \
        "a changed file gets its elaboration"


def test_apply_edit_refuses_walled_content(monkeypatch, tmp_path):
    from Tooling.lsp import gateway as lsp_gateway
    from tests.test_lsp_gateway import _DiagBackend, _setup_validate_session
    content = "theorem t : True := by\n  sorry\nend Problems.p\n"
    (tmp_path / "x.lean").write_text(content, encoding="utf-8")
    ctx = _setup_validate_session(monkeypatch, tmp_path, _DiagBackend())
    meta = lsp_gateway._state.sessions["tok-A"]
    meta.file_content = content
    walled = content.replace("sorry", "decide")
    meta.walled.add(hashlib.sha256(walled.encode("utf-8")).hexdigest())
    try:
        out = json.loads(asyncio.run(lsp_gateway.apply_edit(
            [{"replace": "sorry", "with": "decide"}])))
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        lsp_gateway._state.sessions.pop("tok-A", None)
    assert out["edit"].startswith("held") or out["edit"].startswith("rejected")
    assert "already hit" in out["elab_wall"]
    assert (tmp_path / "x.lean").read_text(encoding="utf-8") == content


# ------------------------------------------------------ ancestor cycle

def _tree(tmp_path: Path) -> tuple[sqlite3.Connection, int, int, int]:
    """root ← child ← grandchild; `sibling` under root; returns
    (conn, root_id, grandchild_id, sibling_id)."""
    from tests.test_dedupe import _link, _seed_problem, _seed_root, _seed_sub
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    _seed_problem(conn)
    root = _seed_root(conn, slug="second_mask_bound_table", statement="R")
    child = _seed_sub(conn, slug="mask_step", statement="C")
    sibling = _seed_sub(conn, slug="fin10_cert", statement="S")
    _link(conn, root, [child, sibling])
    grand = _seed_sub(conn, slug="mask_leaf", statement="G", depth=2)
    _link(conn, child, [grand])
    conn.commit()
    return conn, root, grand, sibling


def test_ancestor_cycle_gate_names_the_ancestor_and_spares_siblings(tmp_path):
    conn, root, grand, sibling = _tree(tmp_path)
    m = _meta(tmp_path, goal_id=grand)
    hit = gates._ancestor_cycle(
        "theorem mask_leaf : G := by\n  exact second_mask_bound_table.mp h\n", m)
    assert hit is not None and hit["ok"] is False
    assert hit["ancestors"] == ["second_mask_bound_table"]
    assert "ancestor" in hit["teaching"] and "cycle" in hit["teaching"].lower()
    # the parent is an ancestor too; a sibling and the file's own name are not
    assert gates._ancestor_cycle("exact mask_step\n", m)["ancestors"] == ["mask_step"]
    assert gates._ancestor_cycle("exact fin10_cert\n", m) is None
    assert gates._ancestor_cycle("theorem mask_leaf : G := by sorry\n", m) is None
    # a mention inside a comment is not a citation
    assert gates._ancestor_cycle("-- see second_mask_bound_table\nexact h\n", m) is None
    # no goal identity → nothing to check (register without goal_id)
    assert gates._ancestor_cycle("exact second_mask_bound_table\n",
                                 _meta(tmp_path)) is None


def test_apply_edit_rejects_an_ancestor_citation_and_validate_mirrors_it(
        monkeypatch, tmp_path):
    from Tooling.lsp import gateway as lsp_gateway
    from tests.test_lsp_gateway import _DiagBackend, _setup_validate_session
    conn, root, grand, _sib = _tree(tmp_path)
    content = "theorem mask_leaf : G := by\n  sorry\nend Problems.p\n"
    (tmp_path / "x.lean").write_text(content, encoding="utf-8")
    ctx = _setup_validate_session(monkeypatch, tmp_path, _DiagBackend(diags=[]))
    meta = lsp_gateway._state.sessions["tok-A"]
    meta.file_content = content
    meta.goal_id = grand
    try:
        out = json.loads(asyncio.run(lsp_gateway.apply_edit(
            [{"replace": "sorry", "with": "exact second_mask_bound_table"}])))
        assert out["edit"].startswith("rejected")
        assert out["ancestor_cycle"]["ancestors"] == ["second_mask_bound_table"]
        assert (tmp_path / "x.lean").read_text(encoding="utf-8") == content
        # validate on a file that already carries the citation (written
        # outside apply_edit) mirrors the same verdict
        (tmp_path / "x.lean").write_text(
            content.replace("sorry", "exact second_mask_bound_table"),
            encoding="utf-8")
        v = json.loads(asyncio.run(lsp_gateway.validate_file()))
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        lsp_gateway._state.sessions.pop("tok-A", None)
    assert v["submission"]["ancestor_cycle"]["ok"] is False
    assert "ancestor_cycle" in v["commit_will_reject"]


# ---------------------------------------------------------- crash tail

def test_a_worker_crash_carries_the_servers_stderr_tail(tmp_path, monkeypatch):
    from Tooling.lsp.gateway import governor
    _fast(monkeypatch)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    monkeypatch.setattr(wall, "_worker_meter", lambda uri: None)

    class _Crashing(_Backend):
        def wait_for_diagnostics(self, uri, version, timeout):
            raise RuntimeError("LSP error for textDocument/waitForDiagnostics: "
                               "Server process for file:///s/0.lean crashed, "
                               "likely due to a stack overflow or a bug.")
    b = _Crashing()
    b.tail = "INTERNAL PANIC: stack overflow detected\nlast: decide on Fin 15"
    ok, info = wall._await_elaboration(b, _slot(), _meta(tmp_path))
    assert ok is False
    assert "stack overflow detected" in info["crash_tail"]


def test_lsp_client_keeps_a_bounded_stderr_tail():
    from Tooling.lsp.client import LspClient
    c = LspClient.__new__(LspClient)
    c._init_stderr_tail()
    for i in range(500):
        c._stderr_buf.append(f"line {i}\n".encode())
    tail = c.stderr_tail(limit=200)
    assert tail.endswith("line 499\n") and len(tail) <= 200


# ------------------------------------------------ the commit verify

def test_the_commit_verify_runs_under_the_same_wall(monkeypatch, tmp_path):
    """The framework's own verify of a candidate (`/verify_session`,
    the commit gate's elaboration) used a bare wait with the caller's
    timeout — no CPU or RAM meter, no re-warm, no teaching. The 2026-08-29
    session that hit the CPU wall four times through apply_edit then ran
    its heavy content UNWALLED at commit: the gateway waited, the daemon
    waited on the gateway, and the graceful stop waited 100 minutes on a
    lease that could not end. One wall, every elaboration."""
    from Tooling.lsp import gateway as lsp_gateway
    from Tooling.lsp.gateway import governor
    from tests.test_lsp_gateway import _register_fake_session
    _fast(monkeypatch)
    monkeypatch.setattr(governor, "_kill_worker_for_uri", lambda uri: True)
    monkeypatch.setattr(wall, "_worker_meter", lambda uri: None)
    backend = _Backend(converge_after=None)
    backend.clear_diagnostics = lambda *a: None
    backend.did_change_full = lambda *a, **k: None
    backend.diagnostics_for = lambda uri: []
    monkeypatch.setattr(lsp_gateway._state, "backend", backend)
    slot = _register_fake_session(monkeypatch, tmp_path, pipeline_id="pipe-A",
                                  token="tok-A", content_pipeline_id="pipe-A")
    try:
        r = lsp_gateway._verify_session_sync(
            "tok-A", "theorem t : True := by decide\n",
            write_olean=False, axioms_for=None, rpc_timeout=30,
            wait_timeout=6000)
    finally:
        with lsp_gateway._state.sessions_lock:
            lsp_gateway._state.sessions.pop("tok-A", None)
    assert r["ok"] is False and r["timed_out"] is True
    assert r["status"] == "elab_wall"
    assert "FAILURE" in r["elab_wall"]["teaching"]
    assert ("open", slot.slot_path, state.WARMUP_CONTENT) in backend.calls, \
        "the wall re-warms the slot; the caller's 6000s wait_timeout is not honoured"


def test_the_daemons_verify_client_outlives_the_gateways_wall():
    """The client side must wait longer than the gateway can possibly
    take (the heavy wall's clock cap), or it gives up on a verify the
    gateway is still doing and retries into a slot that is still busy."""
    import inspect
    cap = wall.ELAB_WALL_HEAVY_SEC * wall.ELAB_WALL_CLOCK_FACTOR
    assert _lifecycle.VERIFY_CLIENT_TIMEOUT_SEC > cap
    sig = inspect.signature(_REAL_VERIFY_IN_SESSION)
    assert sig.parameters["timeout"].default == _lifecycle.VERIFY_CLIENT_TIMEOUT_SEC
