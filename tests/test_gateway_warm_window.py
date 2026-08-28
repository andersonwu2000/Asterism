"""The warm window: HTTP serves during it, Lean refuses fast inside it.

`core/warmup` dispatches Strategist and Scholar the moment the daemon
starts, on purpose — a cold slot-0 warm was measured at 300s+, once at
seven minutes, and the NL layer needs no Lean. But `compute` lives in
the gateway process, which used to open HTTP only after the pool
warmed: the calculator was missing for exactly the minutes the NL layer
is the only thing running (2026-08-12).

Serving during the warm is only safe if nothing about the warm can end
up on the serving thread. That is what most of this file is about.
"""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

from Tooling.lsp import gateway, lifecycle


class _Req:
    """The only thing these routes ask of a Request."""

    def __init__(self, body: dict) -> None:
        self._body = body

    async def json(self):
        return self._body


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch):
    """Never leak warm state between tests — it is process-global."""
    monkeypatch.setattr(gateway._state, "first_warm_done", False)
    monkeypatch.setattr(gateway._state, "warm_failed", None)
    monkeypatch.setattr(gateway._state, "http_server", None)


# ─────────────────────── the load-bearing one ───────────────────────

def test_compute_answers_while_a_lean_route_waits_on_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/compute` must not be serialised behind Lean readiness.

    `/verify` is an async route that calls the readiness gate INLINE —
    its own docstring explains that the heavy work goes to
    `asyncio.to_thread` precisely so the loop is never frozen, which is
    the one thing a blocking gate on that line would undo. So: make
    readiness block on an Event, put a `/verify` on the loop, and
    demand `/compute` come back anyway.

    A weaker test — POST `/compute` at a freshly started process —
    passes even when the loop is wedged, because nothing is holding it
    yet. This one fails.
    """
    # The warm, simulated where it actually blocks: `_await_backend` is
    # the primitive that waits for the pool. Nothing else is stubbed —
    # if `_ensure_backend_ready` ever waits through the FIRST warm
    # again, `/verify` reaches this Event and takes the loop with it.
    warming = threading.Event()
    monkeypatch.setattr(gateway.backend, "_await_backend",
                        lambda timeout: warming.wait(60) and "too late")
    monkeypatch.setattr("Tooling.sandbox.run",
                        lambda code: gateway_result("4"))
    target = tmp_path / "T.lean"
    target.write_text("theorem t : True := trivial\n", encoding="utf-8")

    out: dict = {}

    async def drive() -> None:
        lean = asyncio.ensure_future(
            gateway.verify(_Req({"target_path": str(target)})))
        await asyncio.sleep(0)          # hand the loop to /verify
        resp = await asyncio.wait_for(
            gateway.compute_endpoint(_Req({"code": "print(2+2)"})),
            timeout=10)
        out["compute"] = json.loads(bytes(resp.body).decode())
        try:
            out["lean_status"] = (await lean).status_code
        except Exception:               # noqa: BLE001 — not what we assert
            pass

    runner = threading.Thread(
        target=lambda: asyncio.new_event_loop().run_until_complete(drive()),
        daemon=True)
    runner.start()
    runner.join(15)
    warming.set()                       # never leave the thread parked
    assert not runner.is_alive(), (
        "the event loop was still blocked — a Lean route waiting out the "
        "warm froze /compute with it")
    assert out["compute"]["output"] == "4"
    assert out["lean_status"] == 503, "the Lean route should refuse, not wait"


def gateway_result(text: str):
    from Tooling.sandbox import ComputeResult
    return ComputeResult(rc=0, output=text, seconds=0.01)


# ───────────────── first warm vs. a wedge re-warm ─────────────────

def test_the_first_warm_refuses_lean_immediately(monkeypatch) -> None:
    """No waiting: the answer is known and the caller has nothing in
    flight to protect."""
    gateway._state.ready_event.clear()
    err = gateway._ensure_backend_ready(timeout=30.0)
    assert err == gateway.WARMING_MSG


def test_a_wedge_rewarm_is_still_waited_out(monkeypatch) -> None:
    """The distinction that makes the fast refusal safe. The wedge
    watchdog clears `ready_event` to swap a hung backend, and a caller
    blocked on THAT has real work in flight — refusing it would turn
    every backend restart into a wave of failed verifies. Gate on
    `first_warm_done`, never on `ready_event` alone."""
    monkeypatch.setattr(gateway._state, "first_warm_done", True)
    gateway._state.ready_event.clear()
    waited: list = []
    monkeypatch.setattr(gateway.backend, "_await_backend",
                        lambda t: waited.append(t) or "still restarting")
    assert gateway._ensure_backend_ready(timeout=7.0) == "still restarting"
    assert waited == [7.0], "a re-warm must be waited out, not refused"


def test_the_warming_message_says_what_still_works() -> None:
    """A gate message carries the way out (07-31). Naming `compute`
    matters most in the window where compute is the ONLY thing an agent
    has."""
    assert "warming" in gateway.WARMING_MSG
    assert "compute" in gateway.WARMING_MSG
    assert "not a problem with the request" in gateway.WARMING_MSG


# ──────────────────────── /health stays honest ────────────────────────

def test_health_is_503_while_warming() -> None:
    resp = asyncio.new_event_loop().run_until_complete(
        gateway.health_route(None))
    assert resp.status_code == 503
    assert json.loads(bytes(resp.body).decode())["warming"] is True


def test_ping_health_reads_a_503_as_absent(monkeypatch) -> None:
    """The whole reuse protocol rests on this. `_ping_health` returning
    None is what keeps a warming gateway invisible, exactly as the old
    connection refusal did.

    It holds for free today — `HTTPError` is an `URLError` is an
    `OSError` — so this pins the BEHAVIOUR, not a fragile clause: the
    day `_ping_health` grows a status check and starts reporting a 503
    as a live gateway, a second daemon stops waiting on the marker and
    spawns a rival into an occupied port."""
    import urllib.error
    import urllib.request

    def boom(*a, **kw):
        raise urllib.error.HTTPError(
            "http://127.0.0.1:8765/health", 503, "warming", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert lifecycle._ping_health(timeout=0.1) is None


# ─────────────────── the marker outlives HTTP-open ───────────────────

def test_the_marker_is_dropped_at_warm_end_not_at_http_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_wait_for_starting_gateway` reads the marker's disappearance as
    "that gateway is up and answering". HTTP now opens minutes before
    that is true, so dropping the marker there would send a second
    daemon to spawn a rival into a bound port — the seven-minute
    2026-07-07 collision, reintroduced."""
    marker = tmp_path / "gateway-starting.txt"
    marker.write_text("123", encoding="utf-8")
    monkeypatch.setattr(gateway.backend, "_await_backend", lambda budget: None)
    gateway._watch_initial_warm(1.0, marker)
    assert gateway._state.first_warm_done is True
    assert not marker.exists()


def test_a_failed_warm_still_kills_the_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fatal is fatal. A gateway that served 503s forever would hang
    every retry behind a process that can never do Lean work, and the
    daemon's rc-3 handling would never fire."""
    marker = tmp_path / "gateway-starting.txt"
    marker.write_text("123", encoding="utf-8")
    monkeypatch.setattr(gateway.backend, "_await_backend", lambda budget: "no pool")

    class _Srv:
        should_exit = False

    srv = _Srv()
    monkeypatch.setattr(gateway._state, "http_server", srv)
    gateway._watch_initial_warm(1.0, marker)
    assert gateway._state.warm_failed == "no pool"
    assert srv.should_exit is True
    assert gateway._state.first_warm_done is False
    assert marker.exists(), "a gateway that never warmed is not 'up'"


# ─────────── which silence is it: still coming, or gone ───────────

def test_warming_pid_needs_a_live_pid_not_just_the_file(
    tmp_path: Path,
) -> None:
    """The marker is a file: an abnormal death leaves it behind. Present
    + dead pid means "nothing is running", which is the opposite
    instruction to "wait"."""
    import os

    marker = tmp_path / ".asterism" / "gateway-starting.txt"
    marker.parent.mkdir(parents=True)
    marker.write_text(str(os.getpid()), encoding="utf-8")
    assert lifecycle.warming_pid(tmp_path) == os.getpid()

    marker.write_text("999999", encoding="utf-8")
    assert lifecycle.warming_pid(tmp_path) is None

    marker.unlink()
    assert lifecycle.warming_pid(tmp_path) is None


def test_compute_tells_the_two_silences_apart(monkeypatch) -> None:
    """"Wait a moment" and "report this and move on" are opposite
    instructions; one sentence covering both makes the agent guess."""
    from Tooling.knowledge import mcp_tools

    monkeypatch.setattr(lifecycle, "warming_pid", lambda ws: 4321)
    coming = mcp_tools._gateway_silence_hint()
    assert "4321" in coming and "starting up" in coming
    assert "framework feedback" not in coming

    monkeypatch.setattr(lifecycle, "warming_pid", lambda ws: None)
    gone = mcp_tools._gateway_silence_hint()
    assert "framework fault" in gone and "framework feedback" in gone
