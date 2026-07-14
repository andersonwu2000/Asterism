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
    assert "if not quota_waiting:" in src.split("bfs_refill(")[0].rsplit(
        "# Refill queue", 1)[0] or "if not quota_waiting:" in src, (
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
