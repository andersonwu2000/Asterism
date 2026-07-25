"""Quota-wait — sleep to the subscription reset instead of exiting
(`dispatch.quota_wait`, 2026-07-14, user-approved).

The dispatcher's two quota escalation points call in here:
  - the `quota_exhausted` (rc=126) cooldown branch, to upgrade a blind
    exponential backoff into a sleep-to-`resets_at`;
  - the consecutive-spawn_fast_fail circuit breaker, to convert a trip
    into a wait — but ONLY on positive confirmation from the usage
    endpoint. A broken claude.exe must never read as "waiting on
    quota"; unconfirmed keeps the breaker's exit.

State lives on the dispatcher's SchedulerState (`quota_wait_until`,
`quota_wait_entered`, `quota_wait_logged_at`, `quota_wait_paused`) —
this module is the behavior, not the storage.
"""
from __future__ import annotations

import time

from . import usage_quota

# Jitter pads the provider's resets_at (clock skew + eager 429s on the
# boundary); the fallback covers "exhausted but no parseable resets_at".
QUOTA_WAIT_JITTER_SEC = 120.0
QUOTA_WAIT_FALLBACK_SEC = 1800.0
QUOTA_WAIT_LOG_EVERY_SEC = 600.0
# Early-recovery re-probe cadence while paused (B5, 2026-07-24): the
# sleep target is the OLD window's resets_at — an account switch (or a
# plan change) makes quota available early and a blind sleep misses it
# (26 min lost to a manual restart, 2026-07-20). Only a positive
# "not exhausted" from the endpoint resumes early; unreachable keeps
# sleeping (symmetric with the entry discipline).
QUOTA_WAIT_RECHECK_SEC = 300.0
# Breaker-path confirmation retries (#115, 2026-07-25): at the moment a
# window dies every client hammers the usage endpoint, so its own 429
# is EXPECTED congestion, not evidence of a broken exe — two daemon
# exits were convicted on exactly this misread. Only fetch FAILURES
# retry; a positive "not exhausted" answer is final (that IS the
# broken-exe signal the breaker exists for).
QUOTA_CONFIRM_ATTEMPTS = 4
QUOTA_CONFIRM_RETRY_SEC = 30.0


def _fmt_epoch(t: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC")


def confirmed_quota_deadline(now: float, *,
                             attempts: int = 1) -> "float | None":
    """Probe the subscription usage endpoint; return the epoch to sleep
    until IFF a window is verifiably exhausted. None = not confirmably
    quota (offline, not logged in, or utilization below the bar) —
    callers keep their old failure path.

    `attempts` > 1 retries ONLY fetch failures (429 / offline), spaced
    `QUOTA_CONFIRM_RETRY_SEC` apart — the breaker call site uses this
    so endpoint congestion at the moment quota dies cannot fake a
    broken exe. A reachable endpoint's answer is final either way."""
    for i in range(max(1, attempts)):
        if i:
            time.sleep(QUOTA_CONFIRM_RETRY_SEC)
            now = time.time()
        try:
            raw = usage_quota.fetch_usage()
        except Exception:  # noqa: BLE001 — transient: retry if budget left
            continue
        exhausted, deadline = usage_quota.exhausted_until(raw)
        if not exhausted:
            return None
        if deadline is None or deadline <= now:
            return now + QUOTA_WAIT_FALLBACK_SEC
        return deadline + QUOTA_WAIT_JITTER_SEC
    return None


def _confirmed_available() -> bool:
    """True only on a positive endpoint answer that no window is
    exhausted. Unreachable/unparseable ≠ recovered — keep sleeping."""
    try:
        raw = usage_quota.fetch_usage()
    except Exception:  # noqa: BLE001
        return False
    exhausted, _ = usage_quota.exhausted_until(raw)
    return not exhausted


def maybe_enter(st, *, enabled: bool, source: str,
                probe_attempts: int = 1) -> bool:
    """Enter (or extend) the global quota-wait if the usage endpoint
    confirms exhaustion. True = caller should treat the failure as
    "waiting on quota" instead of escalating (breaker exit / blind
    backoff only). `probe_attempts` forwards to the confirmation
    probe's transient-failure retry budget."""
    if not enabled:
        return False
    now = time.time()
    deadline = confirmed_quota_deadline(now, attempts=probe_attempts)
    if deadline is None:
        return False
    if st.quota_wait_until <= now:
        st.quota_wait_entered = now  # opening a fresh pause window
        st.quota_wait_rechecked_at = now
    st.quota_wait_until = max(st.quota_wait_until, deadline)
    print(f"[quota-wait] {source} — usage endpoint confirms the "
          f"subscription window is exhausted; all dispatch paused "
          f"until {_fmt_epoch(st.quota_wait_until)} "
          f"({(st.quota_wait_until - now) / 60:.0f} min), then "
          f"resuming automatically (dispatch.quota_wait=false restores "
          f"exit-on-quota)", flush=True)
    return True


def tick(st, now: float, *, enabled: bool) -> bool:
    """Per-tick quota-wait state machine. True = dispatch stays paused
    this tick. On deadline expiry, closes the budget-clock pause and
    re-probes: a longer window (seven_day / weekly scoped) may still be
    exhausted, in which case re-arm instead of resuming."""
    if st.quota_wait_until <= 0.0:
        return False
    if now < st.quota_wait_until:
        if now - st.quota_wait_rechecked_at >= QUOTA_WAIT_RECHECK_SEC:
            st.quota_wait_rechecked_at = now
            if _confirmed_available():
                st.quota_wait_paused += now - st.quota_wait_entered
                st.quota_wait_until = 0.0
                st.quota_wait_logged_at = 0.0
                st.consec_quota_per_kind.clear()
                st.quota_cooldown_kind.clear()
                print("[quota-wait] usage endpoint reports quota "
                      "available before the sleep target (account "
                      "switch / window change) — resuming dispatch "
                      "early", flush=True)
                return False
        if now - st.quota_wait_logged_at >= QUOTA_WAIT_LOG_EVERY_SEC:
            st.quota_wait_logged_at = now
            print(f"[quota-wait] dispatch paused — "
                  f"{(st.quota_wait_until - now) / 60:.0f} min until "
                  f"the subscription window resets", flush=True)
        return True
    st.quota_wait_paused += now - st.quota_wait_entered
    st.quota_wait_until = 0.0
    st.quota_wait_logged_at = 0.0
    if maybe_enter(st, enabled=enabled, source="reset-time re-probe"):
        return True
    # Confirmed clear (or endpoint unreachable — spawns will re-raise
    # the evidence if quota is in fact still gone): fresh start.
    st.consec_quota_per_kind.clear()
    st.quota_cooldown_kind.clear()
    print("[quota-wait] subscription window reset — resuming dispatch",
          flush=True)
    return False


def paused_total(st, now: float) -> float:
    """Seconds the budget clock must ignore: closed pauses plus the
    currently-open one (a wait longer than budget_sec must not read as
    budget exhaustion — that would be exit-on-quota with extra steps)."""
    total = st.quota_wait_paused
    if st.quota_wait_until > now:
        total += now - st.quota_wait_entered
    return total
