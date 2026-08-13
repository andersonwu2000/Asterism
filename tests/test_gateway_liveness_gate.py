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
    assert ask(warm_failed="lean interface-contract gate red",
               holding=False) == (
        gateway_health.FATAL_WARM,
        "warm-up failed: lean interface-contract gate red")
    # Holding is not yet fatal — that is the whole point of the grace.
    st.gateway_down_since = 100.0
    assert ask(warm_failed=None, holding=True, now=100.0) is None
    kind, _ = ask(warm_failed=None, holding=True, now=100.0 + grace)
    # The KINDS differ because only one of them can be healed by
    # trying again: a gateway that failed its own gate will fail it
    # again, a process that died may have died of something passing.
    assert kind == gateway_health.FATAL_GONE


# ---------------------------------------------------------------------
# The one self-heal credit (owner ruling 2026-08-14)
# ---------------------------------------------------------------------

BUDGET = 1800.0  # `dispatch.spawn_timeout_sec` — one work unit's time


def test_the_first_death_is_healed_and_the_second_is_not(
    st: dispatcher.SchedulerState, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gateway may die once of something passing. Dying again before
    it has done anything is a crash loop, and relaunching a crash loop
    all night looks exactly like patience."""
    started: list = []
    monkeypatch.setattr(gateway_health, "relaunch",
                        lambda _st, _ws: started.append(_ws) or {"ready": 0})
    st.gateway_down_since = 0.0
    ask = lambda now: gateway_health.resolve_fatal(  # noqa: E731
        st, "WS", warm_failed=None, holding=True, now=now,
        grace_sec=dispatcher.GATEWAY_DOWN_GRACE_SEC, budget_sec=BUDGET)

    healed, fatal = ask(dispatcher.GATEWAY_DOWN_GRACE_SEC)
    assert healed is not None and fatal is None and started == ["WS"]

    # Second death, credit spent (the real `relaunch` sets this; the
    # stub cannot, so state it explicitly).
    st.gateway_relaunched_at = 10.0
    healed, fatal = ask(10.0 + BUDGET - 1)
    assert healed is None and fatal is not None
    assert "crash loop" in fatal and "gateway.log" in fatal


def test_a_finished_pipeline_buys_the_credit_back(
    st: dispatcher.SchedulerState,
) -> None:
    """The primary evidence is WORK DONE, not time survived: a gateway
    that lives twenty minutes serving nothing and dies is the same
    crash loop with a longer fuse. The dispatcher's success branch is
    what clears the mark."""
    st.gateway_relaunched_at = 10.0
    assert not gateway_health.may_relaunch(st, 20.0, BUDGET)
    st.gateway_relaunched_at = None       # ← a pipeline succeeded
    assert gateway_health.may_relaunch(st, 20.0, BUDGET)


def test_the_clock_only_covers_the_case_where_nothing_was_asked(
    st: dispatcher.SchedulerState,
) -> None:
    """The fallback for an empty queue, where nothing could have
    succeeded because nothing was requested. One work unit of survival,
    then the next death counts as new."""
    st.gateway_relaunched_at = 10.0
    assert not gateway_health.may_relaunch(st, 10.0 + BUDGET - 1, BUDGET)
    assert gateway_health.may_relaunch(st, 10.0 + BUDGET, BUDGET)


def test_a_warm_failure_is_never_healed(
    st: dispatcher.SchedulerState, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relaunching repeats it. The gate that failed is the same gate the
    new gateway will face, and its usual verdict is that the warm
    workers themselves are what the red contract indicts."""
    monkeypatch.setattr(gateway_health, "relaunch",
                        lambda *_a: pytest.fail("relaunched a warm failure"))
    healed, fatal = gateway_health.resolve_fatal(
        st, "WS", warm_failed="lean interface-contract gate red",
        holding=False, now=0.0,
        grace_sec=dispatcher.GATEWAY_DOWN_GRACE_SEC, budget_sec=BUDGET)
    assert healed is None and "warm-up failed" in fatal


def test_the_credit_survives_nothing_being_wrong(
    st: dispatcher.SchedulerState,
) -> None:
    """No fatal condition means no verdict at all — neither half of the
    answer may be filled in, or the caller would exit a healthy run."""
    assert gateway_health.resolve_fatal(
        st, "WS", warm_failed=None, holding=False, now=0.0,
        grace_sec=dispatcher.GATEWAY_DOWN_GRACE_SEC,
        budget_sec=BUDGET) == (None, None)


def test_the_credit_window_is_the_spawn_budget_not_a_new_number(
) -> None:
    """The window is `dispatch.spawn_timeout_sec` — this system's
    definition of one work unit's worth of time — read from config by
    the dispatcher, never a constant invented here."""
    import inspect
    src = inspect.getsource(dispatcher.run)
    assert "dispatch.spawn_timeout_sec" in src
    assert "budget_sec=spawn_budget_sec" in src


def test_the_grace_is_derived_from_the_breaker_it_replaces() -> None:
    """Pin the RELATION, not the number. Both constants have been tuned
    before, and the 900s-recycle / 780s-suicide pair is the standing
    lesson about what happens when two clocks that must stay in step
    stop being compared: the cure never got to run."""
    assert dispatcher.GATEWAY_DOWN_GRACE_SEC == (
        dispatcher.CONSEC_GATEWAY_UNREACHABLE_LIMIT
        * dispatcher.SPAWN_COOLDOWN_SEC)
