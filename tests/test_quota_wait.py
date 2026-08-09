"""Quota-wait: sleep-to-reset instead of exiting when the subscription
window is CONFIRMED exhausted (dispatch.quota_wait, 2026-07-14).

Three layers:
  - `core/usage_quota.exhausted_until` — pure parsing of the oauth/usage
    payload into (exhausted, deadline).
  - dispatcher helpers — probe confirmation (`_confirmed_quota_deadline`),
    enter/extend (`_maybe_enter_quota_wait`), the per-tick state machine
    (`_quota_wait_tick`), and the budget-clock exclusion
    (`_quota_paused_total`).
  - wiring pins — the breaker consults the probe before rc=2, and the
    pop loop gates on `quota_waiting`.
"""
from __future__ import annotations

import inspect
import time

from Tooling.core import dispatcher, quota_wait, usage_quota
from Tooling.core.dispatcher import SchedulerState


def _iso(epoch: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------- parsing

def test_exhausted_until_no_payload():
    assert usage_quota.exhausted_until(None) == (False, None)
    assert usage_quota.exhausted_until({}) == (False, None)


def test_exhausted_until_healthy_windows():
    raw = {"five_hour": {"utilization": 27.0, "resets_at": _iso(1e9)},
           "seven_day": {"utilization": 31.0, "resets_at": _iso(2e9)}}
    assert usage_quota.exhausted_until(raw) == (False, None)


def test_exhausted_until_five_hour_exhausted():
    raw = {"five_hour": {"utilization": 100.0, "resets_at": _iso(1e9)},
           "seven_day": {"utilization": 31.0, "resets_at": _iso(2e9)}}
    exhausted, deadline = usage_quota.exhausted_until(raw)
    assert exhausted and deadline == 1e9


def test_exhausted_until_takes_latest_exhausted_reset():
    # Both windows exhausted → quota is only usable once BOTH reset.
    raw = {"five_hour": {"utilization": 99.5, "resets_at": _iso(1e9)},
           "seven_day": {"utilization": 100.0, "resets_at": _iso(2e9)}}
    assert usage_quota.exhausted_until(raw) == (True, 2e9)


def test_exhausted_until_scoped_active_counts():
    raw = {"five_hour": {"utilization": 12.0, "resets_at": _iso(1e9)},
           "limits": [{"kind": "weekly_scoped", "is_active": True,
                       "percent": 100.0, "resets_at": _iso(3e9)}]}
    assert usage_quota.exhausted_until(raw) == (True, 3e9)


def test_exhausted_until_scoped_inactive_ignored():
    raw = {"limits": [{"kind": "weekly_scoped", "is_active": False,
                       "percent": 100.0, "resets_at": _iso(3e9)}]}
    assert usage_quota.exhausted_until(raw) == (False, None)


def test_exhausted_until_missing_reset_is_none_deadline():
    raw = {"five_hour": {"utilization": 100.0, "resets_at": None}}
    assert usage_quota.exhausted_until(raw) == (True, None)


def test_exhausted_until_unparseable_reset_is_none_deadline():
    raw = {"five_hour": {"utilization": 100.0, "resets_at": "not-a-date"}}
    assert usage_quota.exhausted_until(raw) == (True, None)


# ------------------------------------------------------- probe confirmation

def test_confirmed_deadline_endpoint_error_is_none(monkeypatch):
    def boom():
        raise OSError("offline")
    monkeypatch.setattr(usage_quota, "fetch_usage", boom)
    assert quota_wait.confirmed_quota_deadline(1000.0) is None


def test_confirmed_deadline_retries_transient_fetch(monkeypatch):
    """#115: fetch failures (the endpoint's own 429 at the moment quota
    dies) retry within the attempts budget instead of reading as
    'cannot confirm' — two daemon exits were convicted on that misread."""
    calls = {"n": 0}
    # Future epoch: a retry refreshes `now` to real wall time, so a
    # past-epoch reset would fall into the fallback branch.
    reset = float(round(time.time()) + 3600)

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("HTTP 429")
        return {"five_hour": {"utilization": 100.0,
                              "resets_at": _iso(reset)}}
    monkeypatch.setattr(usage_quota, "fetch_usage", flaky)
    monkeypatch.setattr(quota_wait.time, "sleep", lambda s: None)
    assert quota_wait.confirmed_quota_deadline(
        time.time(), attempts=4) == (
        reset + quota_wait.QUOTA_WAIT_JITTER_SEC)
    assert calls["n"] == 3


def test_confirmed_deadline_healthy_answer_is_final(monkeypatch):
    """A reachable endpoint saying 'not exhausted' ends the probe at
    once — that IS the broken-exe signal the breaker exists for; the
    retry budget covers only fetch failures."""
    calls = {"n": 0}

    def healthy():
        calls["n"] += 1
        return {"five_hour": {"utilization": 40.0,
                              "resets_at": _iso(9000.0)}}
    monkeypatch.setattr(usage_quota, "fetch_usage", healthy)
    monkeypatch.setattr(quota_wait.time, "sleep", lambda s: None)
    assert quota_wait.confirmed_quota_deadline(1000.0, attempts=4) is None
    assert calls["n"] == 1


def test_confirmed_deadline_exhausted_retry_budget(monkeypatch):
    """All attempts failing still returns None — a genuinely dead
    endpoint keeps the breaker's exit."""
    calls = {"n": 0}

    def down():
        calls["n"] += 1
        raise OSError("HTTP 429")
    monkeypatch.setattr(usage_quota, "fetch_usage", down)
    monkeypatch.setattr(quota_wait.time, "sleep", lambda s: None)
    assert quota_wait.confirmed_quota_deadline(1000.0, attempts=4) is None
    assert calls["n"] == 4


def test_breaker_passes_probe_retry_budget():
    src = inspect.getsource(dispatcher.run)
    tail = src[src.index("CONSEC_SPAWN_FAIL_LIMIT"):]
    assert "QUOTA_CONFIRM_ATTEMPTS" in tail.split("return 2")[0], (
        "fast-fail breaker must give the quota probe its transient-"
        "failure retry budget (#115)")


def test_confirmed_deadline_healthy_is_none(monkeypatch):
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 40.0, "resets_at": _iso(2000.0)}})
    assert quota_wait.confirmed_quota_deadline(1000.0) is None


def test_confirmed_deadline_adds_jitter(monkeypatch):
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 100.0, "resets_at": _iso(5000.0)}})
    assert quota_wait.confirmed_quota_deadline(1000.0) == (
        5000.0 + quota_wait.QUOTA_WAIT_JITTER_SEC)


def test_confirmed_deadline_fallback_when_reset_missing(monkeypatch):
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 100.0, "resets_at": None}})
    assert quota_wait.confirmed_quota_deadline(1000.0) == (
        1000.0 + quota_wait.QUOTA_WAIT_FALLBACK_SEC)


def test_confirmed_deadline_fallback_when_reset_in_past(monkeypatch):
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 100.0, "resets_at": _iso(500.0)}})
    assert quota_wait.confirmed_quota_deadline(1000.0) == (
        1000.0 + quota_wait.QUOTA_WAIT_FALLBACK_SEC)


# ------------------------------------------------------------ enter / extend

def test_maybe_enter_disabled_never_probes(monkeypatch):
    def forbidden():
        raise AssertionError("probe must not fire when disabled")
    monkeypatch.setattr(usage_quota, "fetch_usage", forbidden)
    st = SchedulerState()
    assert quota_wait.maybe_enter(
        st, enabled=False, source="test") is False
    assert st.quota_wait_until == 0.0


def test_maybe_enter_unconfirmed_is_false(monkeypatch):
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 10.0, "resets_at": None}})
    st = SchedulerState()
    assert quota_wait.maybe_enter(
        st, enabled=True, source="test") is False
    assert st.quota_wait_until == 0.0


def test_maybe_enter_confirmed_sets_wait(monkeypatch):
    # Integral epoch: the ISO round-trip truncates sub-microsecond bits.
    reset = float(round(time.time()) + 3600)
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 100.0, "resets_at": _iso(reset)}})
    st = SchedulerState()
    before = time.time()
    assert quota_wait.maybe_enter(
        st, enabled=True, source="test") is True
    assert st.quota_wait_until == reset + quota_wait.QUOTA_WAIT_JITTER_SEC
    assert before <= st.quota_wait_entered <= time.time()


def test_maybe_enter_extends_never_shrinks(monkeypatch):
    far = time.time() + 7200
    st = SchedulerState()
    st.quota_wait_until = far
    st.quota_wait_entered = time.time() - 10
    near = time.time() + 60
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 100.0, "resets_at": _iso(near)}})
    entered_before = st.quota_wait_entered
    assert quota_wait.maybe_enter(
        st, enabled=True, source="test") is True
    assert st.quota_wait_until == far  # max() kept the later deadline
    assert st.quota_wait_entered == entered_before  # pause window intact


# ------------------------------------------------------------- tick machine

def test_tick_inactive_is_false():
    st = SchedulerState()
    assert quota_wait.tick(
        st, time.time(), enabled=True) is False


def test_tick_active_pauses():
    st = SchedulerState()
    st.quota_wait_until = time.time() + 600
    st.quota_wait_entered = time.time()
    assert quota_wait.tick(
        st, time.time(), enabled=True) is True


def test_tick_expiry_resumes_and_accumulates_pause(monkeypatch):
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 5.0, "resets_at": None}})
    st = SchedulerState()
    st.quota_wait_entered = 1000.0
    st.quota_wait_until = 1500.0
    st.consec_quota_per_kind["Forward"] = 3
    st.quota_cooldown_kind["Forward"] = 2000.0
    assert quota_wait.tick(st, 1600.0, enabled=True) is False
    assert st.quota_wait_until == 0.0
    assert st.quota_wait_paused == 600.0  # 1600 - entered(1000)
    assert st.consec_quota_per_kind == {}  # fresh start
    assert st.quota_cooldown_kind == {}


def test_tick_expiry_rearms_when_still_exhausted(monkeypatch):
    later = float(round(time.time()) + 86400)  # seven_day still standing
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "seven_day": {"utilization": 100.0, "resets_at": _iso(later)}})
    st = SchedulerState()
    st.quota_wait_entered = 1000.0
    st.quota_wait_until = 1500.0
    assert quota_wait.tick(st, 1600.0, enabled=True) is True
    assert st.quota_wait_until == later + quota_wait.QUOTA_WAIT_JITTER_SEC
    assert st.quota_wait_paused == 600.0  # first pause window closed


# ------------------------------------------------------------- budget clock

def test_paused_total_closed_plus_open():
    st = SchedulerState()
    st.quota_wait_paused = 300.0
    assert quota_wait.paused_total(st, 5000.0) == 300.0
    st.quota_wait_until = 9000.0  # currently waiting…
    st.quota_wait_entered = 4000.0  # …since 4000
    assert quota_wait.paused_total(st, 5000.0) == 1300.0


# ------------------------------------------------------------- wiring pins

def test_breaker_consults_probe_before_exit():
    src = inspect.getsource(dispatcher.run)
    breaker = src.split("consecutive spawn_fast_fails")[0]
    tail = src[src.index("CONSEC_SPAWN_FAIL_LIMIT"):]
    assert "quota_wait.maybe_enter" in tail.split("return 2")[0], (
        "fast-fail breaker must consult the quota probe before exiting")


def test_pop_loop_and_refill_gate_on_quota_wait():
    src = inspect.getsource(dispatcher.run)
    assert "quota_waiting = quota_wait.tick" in src
    # The gate must sit BETWEEN the section comment and the call. The
    # earlier form took the text before the comment (never contains the
    # gate — it is always false) and carried an `or <whole source>`
    # fallback, so this assertion could not fail in either direction.
    before_call = src.split("bfs_refill(")[0]
    assert "if not quota_waiting:" in before_call.rsplit(
        "# Refill queue", 1)[-1], (
        "bfs_refill must be gated on quota_waiting")
    assert "stopping or drifting or quota_waiting" in src, (
        "pop loop must not spawn during quota-wait")


def test_budget_check_excludes_paused_time():
    src = inspect.getsource(dispatcher.run)
    assert "quota_wait.paused_total(st, _now) > budget_sec" in src, (
        "budget clock must subtract quota-wait pauses")


def test_once_runs_never_quota_wait():
    src = inspect.getsource(dispatcher.run)
    assert "quota_wait_enabled and not once" in src


def test_serve_meter_delegates_to_shared_fetch():
    from Tooling.serve import run as serve_run
    assert serve_run._fetch_oauth_usage.__module__ == "Tooling.serve.run"
    src = inspect.getsource(serve_run._fetch_oauth_usage)
    assert "usage_quota.fetch_usage" in src


def test_tick_early_recovery_resumes(monkeypatch):
    """B5 (2026-07-24): quota came back before the sleep target (account
    switch) -- a positive endpoint answer resumes early and closes the
    budget-clock pause; the 2026-07-20 incident cost 26 min + a manual
    restart."""
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 10.0, "resets_at": None}})
    st = SchedulerState()
    st.quota_wait_until = 5000.0
    st.quota_wait_entered = 1000.0
    st.quota_wait_rechecked_at = 1000.0
    st.consec_quota_per_kind["backward"] = 3
    now = 1000.0 + quota_wait.QUOTA_WAIT_RECHECK_SEC
    assert quota_wait.tick(st, now, enabled=True) is False
    assert st.quota_wait_until == 0.0
    assert abs(st.quota_wait_paused - (now - 1000.0)) < 1e-6
    assert st.consec_quota_per_kind == {}


def test_tick_early_recovery_needs_positive_answer(monkeypatch):
    """Unreachable endpoint != recovered -- keep sleeping (symmetric
    with the entry discipline)."""
    def down():
        raise OSError("endpoint down")
    monkeypatch.setattr(usage_quota, "fetch_usage", down)
    st = SchedulerState()
    st.quota_wait_until = 5000.0
    st.quota_wait_entered = 1000.0
    st.quota_wait_rechecked_at = 1000.0
    now = 1000.0 + quota_wait.QUOTA_WAIT_RECHECK_SEC
    assert quota_wait.tick(st, now, enabled=True) is True
    assert st.quota_wait_until == 5000.0


def test_tick_recheck_respects_cadence(monkeypatch):
    """No probe before QUOTA_WAIT_RECHECK_SEC has elapsed."""
    def forbidden():
        raise AssertionError("probe fired before the recheck cadence")
    monkeypatch.setattr(usage_quota, "fetch_usage", forbidden)
    st = SchedulerState()
    st.quota_wait_until = 5000.0
    st.quota_wait_entered = 1000.0
    st.quota_wait_rechecked_at = 1000.0
    assert quota_wait.tick(
        st, 1000.0 + quota_wait.QUOTA_WAIT_RECHECK_SEC - 1.0,
        enabled=True) is True


# ---------------------------------------------------------------------
# In-pipeline park (2026-08-08)
# ---------------------------------------------------------------------

def test_park_sleeps_to_a_confirmed_reset(monkeypatch):
    """The whole point: an 8-round debate whose provider window expires
    mid-revision waits it out instead of being discarded. The endpoint
    publishes the end time; 2×15s of blind retry did not."""
    now = time.time()
    monkeypatch.setattr(quota_wait, "confirmed_quota_deadline",
                        lambda n, attempts=1: now + 900)
    slept = []
    assert quota_wait.park_in_pipeline(
        "p revision round 8", budget_sec=3600,
        sleep_fn=slept.append) is True
    assert slept and 880 < slept[0] <= 900


def test_park_declines_when_the_endpoint_says_healthy(monkeypatch):
    """Confirmation-gated, mirroring the breaker's discipline: a broken
    exe must still fail fast. The 2026-08-07 incident's rc was 1, not
    126 — so callers probe on ANY infra rc and the ENDPOINT decides,
    which is also why keying on 126 would have missed it."""
    monkeypatch.setattr(quota_wait, "confirmed_quota_deadline",
                        lambda n, attempts=1: None)
    slept = []
    assert quota_wait.park_in_pipeline(
        "p judge round 3", budget_sec=3600, sleep_fn=slept.append) is False
    assert not slept


def test_park_declines_beyond_the_caller_budget(monkeypatch):
    """`release_expired_leases` un-claims a queue row on AGE alone even
    with this thread alive (TTL 6h), so a park past the caller's window
    invites a second Strategist onto the same group. A weekly-scoped
    cap days out must decline, not sleep a pool thread."""
    now = time.time()
    monkeypatch.setattr(quota_wait, "confirmed_quota_deadline",
                        lambda n, attempts=1: now + 3 * 86400)
    slept = []
    assert quota_wait.park_in_pipeline(
        "p revision round 2", budget_sec=2 * 3600,
        sleep_fn=slept.append) is False
    assert not slept


def test_park_declines_on_exhausted_budget(monkeypatch):
    """A wake already at its lease horizon parks for nothing — and must
    not even probe."""
    probed = []
    monkeypatch.setattr(
        quota_wait, "confirmed_quota_deadline",
        lambda n, attempts=1: probed.append(1) or (time.time() + 60))
    assert quota_wait.park_in_pipeline(
        "p", budget_sec=0, sleep_fn=lambda _: None) is False
    assert not probed
