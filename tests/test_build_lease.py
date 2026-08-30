"""Build leases on the gateway's elaboration gate (owner ruling 2026-08-30).

One CPU budget, two consumers. The flagship (16 OCPU / 125 GB) ran a
queue of 69 at 00:00Z: 13 daemon-side `lake build`s, each fanning out
6.8 GB `lean` compiles across every core, beside the 14 elaboration
lanes the gate DID bound. The batch builds were a second tenant with
no ticket. Now a build BORROWS lanes from the same semaphore the
elaborations queue on: the sum can never exceed the lane count, a
build gets what is free (partially, down to one lane), and a dead
daemon's lease expires by TTL so the lanes come back on their own.
"""
from __future__ import annotations

import threading as _th

import pytest

from Tooling.lsp import gateway as lsp_gateway
from Tooling.lsp.gateway import elab


@pytest.fixture
def gate(monkeypatch):
    monkeypatch.setattr(elab, "_ELAB_SEM", _th.BoundedSemaphore(4))
    monkeypatch.setattr(elab, "_ELAB_CONCURRENCY", 4)
    monkeypatch.setattr(elab, "_BUILD_LANES_MAX", 3)
    monkeypatch.setattr(elab, "_BUILD_LEASE_TTL_SEC", 100.0)
    monkeypatch.setattr(elab, "_ELAB_QUEUE_TIMEOUT_SEC", 30.0)
    elab._BUILD_LEASES.clear()
    yield
    for tok in list(elab._BUILD_LEASES):
        elab.build_lease_release(tok)


def test_build_lease_borrows_lanes_from_the_elab_semaphore(gate):
    lease = elab.build_lease_acquire(threads=3, owner="daemon-1",
                                     hint="dedupe pre-flight")
    assert lease is not None
    assert lease["threads"] == 3
    st = lsp_gateway.elab_gate_stats()
    assert st["build_busy"] == 3
    assert st["elab_cap"] == 4
    assert [l["owner"] for l in st["build_leases"]] == ["daemon-1"]
    # one lane is left for elaboration; a second elaboration must queue
    entered, release = _th.Event(), _th.Event()

    def holder():
        with lsp_gateway._elab_gate():
            entered.set()
            release.wait(timeout=10)
    t = _th.Thread(target=holder)
    t.start()
    assert entered.wait(timeout=5)
    assert elab._ELAB_SEM.acquire(blocking=False) is False, \
        "3 build + 1 elab = the whole gate"
    release.set()
    t.join(timeout=5)
    assert elab.build_lease_release(lease["token"]) is True
    assert lsp_gateway.elab_gate_stats()["build_busy"] == 0
    assert elab.build_lease_release(lease["token"]) is False, "idempotent"


def test_build_lease_is_partial_down_to_one_lane_and_none_at_zero(gate):
    held = [elab._ELAB_SEM.acquire(blocking=False) for _ in range(3)]
    assert all(held)
    try:
        lease = elab.build_lease_acquire(threads=3, owner="d")
        assert lease is not None and lease["threads"] == 1, \
            "one lane free: the build takes one, not none"
        assert elab.build_lease_acquire(threads=2, owner="d") is None, \
            "nothing free: no lease, the caller retries"
        elab.build_lease_release(lease["token"])
    finally:
        for _ in held:
            elab._ELAB_SEM.release()


def test_build_lease_never_exceeds_the_build_share(gate):
    """A build may not take every lane even when every lane is free:
    `_BUILD_LANES_MAX` keeps elaboration alive beside a long build."""
    lease = elab.build_lease_acquire(threads=99, owner="d")
    assert lease["threads"] == 3
    elab.build_lease_release(lease["token"])


def test_build_lease_expires_by_ttl_and_renew_extends(gate, monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(elab.time, "monotonic", lambda: now["t"])
    lease = elab.build_lease_acquire(threads=2, owner="d")
    assert lsp_gateway.elab_gate_stats()["build_busy"] == 2
    now["t"] += 60.0
    assert elab.build_lease_renew(lease["token"]) is True
    now["t"] += 60.0            # 120 s after issue, 60 s after renew
    elab.sweep_build_leases()
    assert lsp_gateway.elab_gate_stats()["build_busy"] == 2, "renewed: alive"
    now["t"] += 50.0            # 110 s after the renew: past the TTL
    elab.sweep_build_leases()
    assert lsp_gateway.elab_gate_stats()["build_busy"] == 0, \
        "a dead daemon's lease returns its lanes by itself"
    assert elab.build_lease_renew(lease["token"]) is False


def test_build_lease_stats_carry_age_and_hint(gate, monkeypatch):
    now = {"t": 5.0}
    monkeypatch.setattr(elab.time, "monotonic", lambda: now["t"])
    elab.build_lease_acquire(threads=1, owner="daemon-7", hint="commit g42")
    now["t"] = 17.0
    (row,) = lsp_gateway.elab_gate_stats()["build_leases"]
    assert row["hint"] == "commit g42"
    assert row["age_s"] == pytest.approx(12.0)
    assert row["threads"] == 1


def test_build_lease_routes(gate):
    """The REST shape the daemon polls: 200 with a token, 409 with a
    retry hint when nothing is free, 404 on a dead token."""
    import asyncio

    class _Req:
        def __init__(self, body=None, **params):
            self._body = body
            self.path_params = params

        async def json(self):
            return self._body

    def run(coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    import json as _json
    r = run(lsp_gateway.build_lease_route(
        _Req({"threads": 2, "owner": "daemon-1", "hint": "x"})))
    assert r.status_code == 200
    body = _json.loads(r.body)
    assert body["threads"] == 2 and body["token"]
    held = [elab._ELAB_SEM.acquire(blocking=False) for _ in range(2)]
    assert all(held)
    try:
        r2 = run(lsp_gateway.build_lease_route(
            _Req({"threads": 1, "owner": "daemon-2"})))
        assert r2.status_code == 409
        b2 = _json.loads(r2.body)
        assert b2["retry_after_s"] > 0 and b2["build_busy"] == 2
    finally:
        for _ in held:
            elab._ELAB_SEM.release()
    r3 = run(lsp_gateway.build_lease_renew_route(_Req(token=body["token"])))
    assert r3.status_code == 200
    r4 = run(lsp_gateway.build_lease_release_route(_Req(token=body["token"])))
    assert r4.status_code == 200
    r5 = run(lsp_gateway.build_lease_renew_route(_Req(token=body["token"])))
    assert r5.status_code == 404
