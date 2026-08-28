"""The serialized pressure-release outlet and its escort fixes (owner
design 2026-08-27). The ledger's open-loop integrator (2 GB per hot
tick, −1 per calm tick) wound up on release lag — 27 pause/clear
cycles, 579 sheds / 597 warms in 7 h on the 32 GB co-tenant box, many
"warms" mere reattaches of not-yet-dead workers. Now: hot kills ONE
fresh-weighed worker per governor pass with its death confirmed; calm
forgives one debt step once the pool converged; the weight watchdog
weighs its candidate fresh before the knife; /health serves a governor
snapshot; the reuse gate treats an occupied port as an occupied port;
daemon_status asks /health once, not twice."""
from __future__ import annotations

import threading
import types
from pathlib import Path

import pytest


@pytest.fixture
def gw(monkeypatch):
    from Tooling.lsp import gateway
    monkeypatch.setattr(gateway._state, "first_warm_done", True)
    monkeypatch.setattr(gateway._state, "ram_budget_gb", 20.0)
    monkeypatch.setattr(gateway._state, "warm_target", 10)
    monkeypatch.setattr(gateway.governor, "_await_worker_exit",
                        lambda *_a, **_k: True)
    monkeypatch.setattr(gateway.governor, "_kill_worker_for_uri",
                        lambda *_a: True)
    monkeypatch.setattr(gateway.governor, "_machine_gb", lambda: 32.0)
    monkeypatch.setattr(gateway.governor, "_kick_warm_converger",
                        lambda: None)
    monkeypatch.setattr(gateway.governor, "_PRESSURE_DEBT", 0)
    return gateway


def _slot(gw, slot_id=0, claimed=None):
    s = gw.WorkerSlot(slot_id=slot_id,
                      slot_path=Path(f"s{slot_id}.lean"),
                      slot_uri=f"file:///s{slot_id}.lean")
    s.lock = threading.Lock()
    s.claimed_by = claimed
    return s


def _backend(gw, monkeypatch, calls):
    monkeypatch.setattr(gw._state, "backend", types.SimpleNamespace(
        did_close=lambda *_a: calls.append("close"),
        did_open=lambda _p, txt: calls.append(("open", txt)),
        wait_for_file_done=lambda *_a, **_k: None))


def _readings(gw, monkeypatch, cached, fresh=None):
    monkeypatch.setattr(gw.governor, "_slot_private_mb_cached",
                        lambda: dict(cached))
    monkeypatch.setattr(
        gw.governor, "_slot_private_mb_fresh",
        lambda s: (fresh or cached).get(s.slot_id))


def _axes(gw, monkeypatch, avail, cgroup=None):
    from Tooling.core import ram_ledger as rl
    monkeypatch.setattr(rl, "available_gb", lambda: avail)
    monkeypatch.setattr(rl, "framework_current_gb", lambda: cgroup)


def test_hot_kills_exactly_one_fresh_weighed_fattest_per_step(
        gw, monkeypatch, capsys):
    calls: list = []
    _backend(gw, monkeypatch, calls)
    _axes(gw, monkeypatch, avail=1.0)         # under pressure_low(32)
    slots = [_slot(gw, i) for i in range(3)]
    monkeypatch.setattr(gw._state, "workers", slots)
    # the cache nominates slot 0; the scale elects slot 1
    _readings(gw, monkeypatch,
              cached={0: 5000, 1: 4000, 2: 300},
              fresh={0: 1200, 1: 6100, 2: 280})
    assert gw._pressure_outlet_step() is True
    assert slots[1].closed is True, "the fresh reading elects the kill"
    assert slots[0].closed is False and slots[2].closed is False, \
        "one measured kill per step — never a batch"
    assert gw._pressure_debt() == 1
    assert "pressure shed" in capsys.readouterr().err
    # the NEXT step (a fresh pass, still hot) may take the next one
    assert gw._pressure_outlet_step() is True
    assert gw._pressure_debt() == 2


def test_the_outlet_never_takes_the_last_open_worker(gw, monkeypatch):
    calls: list = []
    _backend(gw, monkeypatch, calls)
    _axes(gw, monkeypatch, avail=1.0)
    only = _slot(gw, 0)
    monkeypatch.setattr(gw._state, "workers", [only])
    _readings(gw, monkeypatch, cached={0: 9000})
    assert gw._pressure_outlet_step() is False
    assert only.closed is False


def test_effective_target_subtracts_the_debt_everywhere(
        gw, monkeypatch):
    import inspect
    monkeypatch.setattr(gw.governor, "_PRESSURE_DEBT", 3)
    assert gw._effective_target() == 7
    # every pool-sizing consumer reads the effective allowance — a raw
    # read would re-warm the outlet's kills while hot
    for fn in (gw._shed_slot_if_over_target, gw._warm_converger_run):
        assert "_effective_target()" in inspect.getsource(fn)


def test_calm_forgives_one_step_only_once_the_pool_converged(
        gw, monkeypatch, capsys):
    calls: list = []
    _backend(gw, monkeypatch, calls)
    _axes(gw, monkeypatch, avail=30.0)        # calm on both axes
    monkeypatch.setattr(gw.governor, "_PRESSURE_DEBT", 2)
    slots = [_slot(gw, i) for i in range(8)]  # open 8 = target 10 - 2
    monkeypatch.setattr(gw._state, "workers", slots)
    _readings(gw, monkeypatch, cached={})
    assert gw._pressure_outlet_step() is True
    assert gw._pressure_debt() == 1
    assert "debt forgiven" in capsys.readouterr().err
    # previous warm NOT landed (open 8 < allowance 9): hold
    assert gw._pressure_outlet_step() is False
    assert gw._pressure_debt() == 1


def test_static_mode_and_no_budget_leave_the_outlet_dormant(
        gw, monkeypatch):
    calls: list = []
    _backend(gw, monkeypatch, calls)
    _axes(gw, monkeypatch, avail=1.0)
    monkeypatch.setattr(gw._state, "workers", [_slot(gw, 0), _slot(gw, 1)])
    _readings(gw, monkeypatch, cached={0: 5000, 1: 700})
    monkeypatch.setattr(gw._state, "warm_target", None)
    assert gw._pressure_outlet_step() is False
    monkeypatch.setattr(gw._state, "warm_target", 10)
    monkeypatch.setattr(gw._state, "ram_budget_gb", None)
    assert gw._pressure_outlet_step() is False


def test_weight_kill_weighs_its_candidate_fresh_before_the_knife(
        gw, monkeypatch, capsys):
    """A 36 GB worker slid past the 8 GB cap on a stale cache reading
    (flagship 2026-08-26) — and the mirror image, a kill on a stale
    fat number for a now-thin worker, must be spared."""
    calls: list = []
    _backend(gw, monkeypatch, calls)
    s = _slot(gw, 0)
    monkeypatch.setattr(gw._state, "workers", [s])
    _readings(gw, monkeypatch, cached={0: 9000}, fresh={0: 500})
    assert gw._weight_kill_over_cap() == 0
    assert "spared by the fresh reading" in capsys.readouterr().err
    _readings(gw, monkeypatch, cached={0: 9000}, fresh={0: 9100})
    assert gw._weight_kill_over_cap() == 1


def test_health_serves_the_governor_snapshot(gw, monkeypatch):
    import inspect
    src = inspect.getsource(gw.health)
    assert "_HEALTH_SNAPSHOT" in src, \
        "/health must read the snapshot, not walk the pool per request"
    src_gov = inspect.getsource(gw._weight_watchdog_run)
    assert "_refresh_health_snapshot" in src_gov
    assert "_pressure_outlet_step" in src_gov
    # the payload carries the outlet's surface
    monkeypatch.setattr(gw._state, "workers", [])
    monkeypatch.setattr(gw._state, "backend", None)
    payload = gw._health_payload()
    assert "pressure_debt" in payload


def test_reuse_gate_refuses_a_rival_on_an_occupied_silent_port(
        monkeypatch, tmp_path):
    """Flagship 2026-08-26: a saturated gateway answers /health minutes
    late while holding the port with 73 warm workers. A 1 s probe read
    it as absent, and both downstream branches were disasters (rival
    spawn / full-pool relaunch). TCP-occupied must veto the spawn."""
    from Tooling.lsp import lifecycle
    monkeypatch.setattr(lifecycle, "_ping_health", lambda **_k: None)
    monkeypatch.setattr(lifecycle, "_wait_for_starting_gateway",
                        lambda *_a, **_k: None)
    monkeypatch.setattr(lifecycle, "_port_occupied", lambda **_k: True)
    monkeypatch.setattr(lifecycle, "_OCCUPIED_HEALTH_PATIENCE_SEC", 0.1)
    with pytest.raises(RuntimeError, match="refusing to spawn a rival"):
        lifecycle.start_gateway(tmp_path, ready_timeout=0.1)


def test_daemon_status_asks_health_exactly_once(monkeypatch, tmp_path):
    """The old phase/slots helper pair fetched the same /health twice
    per status poll — pure double load on a drowning accept queue."""
    import io
    import json
    import urllib.request
    from Tooling.core import cli
    calls = {"n": 0}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _Resp(json.dumps(
            {"backend_ready": True, "warm_target": 5,
             "workers_open": 5, "workers_free": 2}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    phase, slots = cli._gateway_status_once(tmp_path)
    assert calls["n"] == 1
    assert phase == "ready"
    assert slots == {"target": 5, "open": 5, "free": 2}
    import inspect
    src = inspect.getsource(cli.daemon_status)
    assert "_gateway_status_once" in src
    assert "_gateway_slots_safe" not in src
