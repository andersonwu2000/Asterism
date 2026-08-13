"""Quota-wait — sleep to the subscription reset instead of exiting
(`dispatch.quota_wait`, 2026-07-14, user-approved).

The dispatcher's two quota escalation points call in here:
  - the `quota_exhausted` (rc=126) cooldown branch, to upgrade a blind
    exponential backoff into a sleep-to-`resets_at`;
  - the consecutive-spawn_fast_fail circuit breaker, to convert a trip
    into a wait. A broken claude.exe must never read as "waiting on
    quota", so a CONFIRMED-healthy endpoint keeps the exit — but an
    endpoint that will not answer is a third state, not the second one
    (2026-08-13: four failed probes were spent as a verdict of health),
    and it buys a bounded hold instead.

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
# …and when even those four go unanswered (2026-08-13), silence is not
# a verdict. Hold this long, up to this many times, before the breaker's
# exit stands. Bounded on purpose: an unbounded hold turns "we cannot
# tell" into a daemon that waits forever on a fault nobody can see.
UNCONFIRMED_HOLD_SEC = 900.0
UNCONFIRMED_TRIP_LIMIT = 3


def _fmt_epoch(t: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC")


#: The three answers the endpoint can give. `UNKNOWN` is the one that
#: had no name before 2026-08-13: every probe failing was folded into
#: the same `None` as "the endpoint says you are fine", so the breaker
#: read four network errors as a verdict of health and exited.
EXHAUSTED = "exhausted"
HEALTHY = "healthy"
UNKNOWN = "unknown"


class QuotaProbe:
    """A probe result that still reads as a boolean.

    `bool(probe)` is "did this park / should the caller stand down",
    exactly what the three existing call sites already test, so adding
    the verdict cannot silently change any of them. `.verdict` is the
    part that was being thrown away."""

    __slots__ = ("parked", "verdict", "deadline")

    def __init__(self, parked: bool, verdict: str,
                 deadline: "float | None" = None) -> None:
        self.parked = parked
        self.verdict = verdict
        self.deadline = deadline

    def __bool__(self) -> bool:
        return self.parked

    def __repr__(self) -> str:      # pragma: no cover — diagnostics only
        return (f"QuotaProbe(parked={self.parked}, "
                f"verdict={self.verdict!r}, deadline={self.deadline!r})")


def probe_quota(now: float, *, attempts: int = 1) -> QuotaProbe:
    """Ask the subscription usage endpoint what state the window is in.

    Three outcomes, and keeping them apart is the whole point:
      * EXHAUSTED — a window is verifiably spent; `.deadline` is the
        epoch to sleep to.
      * HEALTHY  — the endpoint answered and nothing is exhausted. For
        the breaker this is the positive signal it exists for: the exe
        really is broken.
      * UNKNOWN  — every attempt failed. Says nothing in either
        direction, and callers must not spend it as if it did.

    `attempts` > 1 retries ONLY fetch failures (429 / offline), spaced
    `QUOTA_CONFIRM_RETRY_SEC` apart — the breaker call site uses this
    so endpoint congestion at the moment quota dies cannot fake a
    broken exe. A reachable endpoint's answer is final either way.

    Failures are PRINTED. They used to be swallowed whole, so a
    post-mortem could establish that four probes failed and nothing
    about why — 429 congestion and a credentials-file race look
    identical from the outside, and they need different fixes."""
    last: "Exception | None" = None
    for i in range(max(1, attempts)):
        if i:
            time.sleep(QUOTA_CONFIRM_RETRY_SEC)
            now = time.time()
        try:
            raw = usage_quota.fetch_usage()
        except Exception as exc:  # noqa: BLE001 — transient: retry if budget
            last = exc
            print(f"[quota] usage endpoint probe {i + 1}/{max(1, attempts)} "
                  f"failed: {type(exc).__name__}: {exc}", flush=True)
            continue
        exhausted, deadline = usage_quota.exhausted_until(raw)
        if not exhausted:
            return QuotaProbe(False, HEALTHY)
        if deadline is None or deadline <= now:
            return QuotaProbe(False, EXHAUSTED,
                              now + QUOTA_WAIT_FALLBACK_SEC)
        return QuotaProbe(False, EXHAUSTED, deadline + QUOTA_WAIT_JITTER_SEC)
    if last is not None:
        print(f"[quota] usage endpoint did not answer in "
              f"{max(1, attempts)} attempt(s) — quota state is UNKNOWN, "
              f"which is not the same as healthy", flush=True)
    return QuotaProbe(False, UNKNOWN)


def confirmed_quota_deadline(now: float, *,
                             attempts: int = 1) -> "float | None":
    """The epoch to sleep to IFF a window is verifiably exhausted, else
    None. Thin wrapper over `probe_quota` for the callers that genuinely
    only need "park or don't" — `park_in_pipeline` declines on both
    HEALTHY and UNKNOWN, and for an in-flight worker thread that is the
    right call either way (it has a spawn to retry and a budget to keep;
    it is not deciding whether the daemon lives)."""
    probe = probe_quota(now, attempts=attempts)
    return probe.deadline if probe.verdict == EXHAUSTED else None


def park_in_pipeline(label: str, *, budget_sec: float,
                     sleep_fn=time.sleep) -> bool:
    """Sleep an IN-FLIGHT pipeline thread to a confirmed quota reset.

    The dispatcher's quota-wait holds FUTURE dispatch; it cannot save a
    debate already running inside the worker pool. So the author↔judge
    loop needs its own park: 2026-08-07, an 8-round Programme debate
    (~2.5h) died at round 8 because the subscription window expired
    mid-revision and the retry policy was 2×15s against a 1.5h outage.
    The end time was knowable the whole time — the usage endpoint
    publishes `resets_at` — and the ledger sat one import away.

    Discipline mirrors `maybe_enter`'s: only a POSITIVE endpoint answer
    parks. The incident's rc was 1, not 126 (quota death wearing
    `spawn_fast_fail`'s clothes), so callers must probe on ANY infra
    rc rather than keying on 126 — and a genuinely broken exe still
    fails fast because the endpoint answers "healthy".

    `budget_sec` is the caller's own ceiling, and it is a correctness
    parameter, not a comfort one: `release_expired_leases` un-claims a
    queue row on AGE ALONE even when the owner is alive (db.py, TTL
    `LEASE_TTL_SEC` = 6h), so a park that pushes wake-elapsed past the
    TTL invites a second Strategist onto the same group. Callers pass
    what is left of their safe window; a reset beyond it declines to
    park (weekly-scoped caps can be days out — sleeping a pool thread
    that long is absurd) and the caller keeps its old failure path.

    Returns True iff it parked and the caller should retry the spawn.
    """
    if budget_sec <= 0:
        return False
    now = time.time()
    deadline = confirmed_quota_deadline(now, attempts=QUOTA_CONFIRM_ATTEMPTS)
    if deadline is None:
        return False
    wait = deadline - now
    if wait > budget_sec:
        print(f"[quota-park] {label}: window resets {_fmt_epoch(deadline)} "
              f"({wait / 60:.0f}min) — beyond this wake's {budget_sec / 60:.0f}"
              f"min budget; not parking", flush=True)
        return False
    print(f"[quota-park] {label}: sleeping {wait / 60:.0f}min to "
          f"{_fmt_epoch(deadline)}; the proposal stays alive", flush=True)
    sleep_fn(max(0.0, wait))
    return True


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
                probe_attempts: int = 1) -> QuotaProbe:
    """Enter (or extend) the global quota-wait if the usage endpoint
    confirms exhaustion.

    Truthy = caller should treat the failure as "waiting on quota"
    instead of escalating (breaker exit / blind backoff only), which is
    what every call site already tested. `.verdict` additionally says
    WHY it did not park, because HEALTHY and UNKNOWN license completely
    different escalations and used to be the same `False`.
    `probe_attempts` forwards to the probe's transient-failure retry
    budget."""
    if not enabled:
        return QuotaProbe(False, UNKNOWN)
    now = time.time()
    probe = probe_quota(now, attempts=probe_attempts)
    deadline = probe.deadline
    if probe.verdict != EXHAUSTED or deadline is None:
        return probe
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
    return QuotaProbe(True, EXHAUSTED, st.quota_wait_until)


def hold_unconfirmed(st, *, source: str) -> bool:
    """The breaker tripped and the endpoint would not say why. Hold,
    briefly, instead of declaring the provider dead. True = held; False
    = held too many times already, so the caller should exit.

    2026-08-13 is the case this exists for. A five-hour window died,
    every client on the account queried the usage endpoint in the same
    seconds, four consecutive probes failed, and "cannot confirm" was
    spent as if it were "confirmed healthy": the daemon exited claiming
    claude.exe was broken while another thread in the SAME PROCESS was
    successfully parking to that window's real reset time.

    A bounded hold, not an open one. The breaker's original discipline
    was right about the danger it named — a genuinely broken exe must
    never read as "waiting on quota", because a daemon that waits
    forever on a fault nobody can see is worse than one that stops and
    says so. So silence buys a wait, and it buys it only
    `UNCONFIRMED_TRIP_LIMIT` times; after that the exit stands, with a
    message that names what actually happened instead of guessing at
    the exe."""
    st.consec_unconfirmed_trips += 1
    if st.consec_unconfirmed_trips > UNCONFIRMED_TRIP_LIMIT:
        return False
    now = time.time()
    if st.quota_wait_until <= now:
        st.quota_wait_entered = now
        st.quota_wait_rechecked_at = now
    st.quota_wait_until = max(st.quota_wait_until,
                              now + UNCONFIRMED_HOLD_SEC)
    print(f"[quota-wait] {source}, and the usage endpoint did not "
          f"answer — holding dispatch {UNCONFIRMED_HOLD_SEC / 60:.0f}min "
          f"rather than calling the provider broken on evidence nobody "
          f"gave us (hold {st.consec_unconfirmed_trips}/"
          f"{UNCONFIRMED_TRIP_LIMIT}; the next probe decides)", flush=True)
    return True


# `sync_quota_holds` lived here until 2026-08-13. It mirrored
# `Ledger.blocked_kinds` into `SchedulerState.quota_cooldown_kind` and
# popped entries back out on `clear_kinds` — a reconciler, which is to
# say the standing proof that one fact had two homes. Its own docstring
# recorded what that cost: the per-seat half shipped (2026-08-07) with a
# hold and no working unblock, and a Fable weekly cap held the
# Strategist for eight hours across the account switch that had already
# lifted it (2026-08-11).
#
# The release direction was unwritable for a concrete reason, also in
# that docstring: the map mixed quota FACTS with the rc=126 rate brake,
# and clearing it would have released a live brake. Two meanings, one
# table, so neither could be cleared safely.
#
# `core/dispatcher.run` now asks the ledger directly, once per tick, and
# hands the answer to `core/admission.admission`. There is no mirrored
# state, so there is no release path to get wrong — the hold simply
# stops being reported. The brake kept its own map
# (`SchedulerState.kind_backoff_until`) and its own release, which was
# never the broken half.


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
                st.kind_backoff_until.clear()
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
    st.kind_backoff_until.clear()
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
