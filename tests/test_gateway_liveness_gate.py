"""Ask the gateway before buying a spawn against it (#203).

A gateway that is genuinely gone used to cost eight full spawns before
the daemon gave up: dispatch, die on `gateway_unreachable`, cool 30s,
dispatch again. Whether the process is alive is a local HTTP GET, and
nothing in that sequence ever asked.

The gate holds dispatch instead, and the ending does not move — the
grace is the same wall clock the spawn-counting breaker would have
spent — so what changes is only the bill.
"""
from __future__ import annotations

import pytest

from Tooling.core import dispatcher, gateway_health
from Tooling.lsp import lifecycle


@pytest.fixture
def st() -> dispatcher.SchedulerState:
    return dispatcher.SchedulerState()


def _health(monkeypatch: pytest.MonkeyPatch, answer, *,
            calls: "list | None" = None):
    def _ping(timeout: float = 2.0):
        if calls is not None:
            calls.append(timeout)
        return answer

    monkeypatch.setattr(lifecycle, "_ping_health", _ping)


def test_the_gate_is_dormant_until_a_spawn_has_already_failed(
    st: dispatcher.SchedulerState, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not "probe before every dispatch". A healthy system would be
    answering a question it has already answered, and during a warm
    `/health` returns 503 — indistinguishable from death here, because
    `_ping_health` catches `HTTPError` along with the rest of
    `URLError`. Dormant costs nothing and cannot misfire."""
    calls: list = []
    _health(monkeypatch, None, calls=calls)
    assert gateway_health.liveness_gate(st) is False
    assert calls == [], "probed a gateway nobody had complained about"


def test_a_silent_gateway_holds_dispatch_and_starts_the_clock(
    st: dispatcher.SchedulerState, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _health(monkeypatch, None)
    st.consec_gateway_unreachable = 1
    assert gateway_health.liveness_gate(st) is True
    assert st.gateway_down_since is not None
    first = st.gateway_down_since
    # The clock starts once; a second silent tick must not push it out,
    # or the grace never expires and the loud exit never happens.
    assert gateway_health.liveness_gate(st) is True
    assert st.gateway_down_since == first


def test_an_answering_gateway_lifts_the_hold_and_clears_the_streak(
    st: dispatcher.SchedulerState, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The streak counts CONSECUTIVE failures, so evidence that the
    gateway is up ends it — otherwise a stale count sits one failure
    away from tripping a breaker about a healthy process."""
    _health(monkeypatch, None)
    st.consec_gateway_unreachable = 3
    assert gateway_health.liveness_gate(st) is True

    _health(monkeypatch, {"status": "ok"})
    assert gateway_health.liveness_gate(st) is False
    assert st.consec_gateway_unreachable == 0
    assert st.gateway_down_since is None


def test_the_grace_expires_and_only_then(
    st: dispatcher.SchedulerState,
) -> None:
    grace = dispatcher.GATEWAY_DOWN_GRACE_SEC
    st.gateway_down_since = 1000.0
    assert not gateway_health.down_expired(st, 1000.0, grace)
    assert not gateway_health.down_expired(st, 1000.0 + grace - 1, grace)
    assert gateway_health.down_expired(st, 1000.0 + grace, grace)


def test_a_hold_that_never_started_never_expires(
    st: dispatcher.SchedulerState,
) -> None:
    """`None` is "not holding", and a huge `now` must not read as "the
    grace ran out" — that would exit a daemon whose gateway is fine."""
    assert st.gateway_down_since is None
    assert not gateway_health.down_expired(
        st, 1e12, dispatcher.GATEWAY_DOWN_GRACE_SEC)


def test_the_two_fatal_endings_are_one_question(
    st: dispatcher.SchedulerState,
) -> None:
    """Warm-up failure and a gateway that stopped answering mean the
    same thing and take the same action. They were two blocks doing the
    same three things (drain, release leases, rc=2), which is how the
    second one nearly shipped without the drain."""
    grace = dispatcher.GATEWAY_DOWN_GRACE_SEC
    ask = lambda **kw: gateway_health.fatal_reason(  # noqa: E731
        st, now=kw.pop("now", 0.0), grace_sec=grace, **kw)

    assert ask(warm_failed=None, holding=False) is None
    assert "warm-up failed" in ask(
        warm_failed="lean interface-contract gate red", holding=False)
    # Holding is not yet fatal — that is the whole point of the grace.
    st.gateway_down_since = 100.0
    assert ask(warm_failed=None, holding=True, now=100.0) is None
    reason = ask(warm_failed=None, holding=True, now=100.0 + grace)
    assert reason is not None and "gateway.log" in reason


def test_the_grace_is_derived_from_the_breaker_it_replaces() -> None:
    """Pin the RELATION, not the number. Both constants have been tuned
    before, and the 900s-recycle / 780s-suicide pair is the standing
    lesson about what happens when two clocks that must stay in step
    stop being compared: the cure never got to run."""
    assert dispatcher.GATEWAY_DOWN_GRACE_SEC == (
        dispatcher.CONSEC_GATEWAY_UNREACHABLE_LIMIT
        * dispatcher.SPAWN_COOLDOWN_SEC)
