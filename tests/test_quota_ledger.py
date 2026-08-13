"""The quota ledger: who cannot spawn, per (provider, model).

2026-08-06 is the incident this exists for. `Fable`'s weekly cap hit
100% while the shared five-hour window sat at 1% and the weekly total at
58%; the framework held one boolean, paused every pipeline, and threw
away eleven finished proposals — on a run whose formalizer was on Gemini
and whose judge could have moved to Opus.
"""
import time

import pytest

from Tooling.core import quota
from Tooling.core.quota import Block, Ledger


@pytest.fixture
def ledger(monkeypatch):
    """A ledger over a scripted set of blocks, with a frozen clock."""
    box = {"blocks": []}
    monkeypatch.setattr(quota, "_PROBES", {"t": lambda: list(box["blocks"])})
    led = Ledger(ttl=0.0, clock=lambda: 1_000.0)
    return led, box


def _seats(**over):
    seats = {
        "strategist": ("claude", "claude-opus-5"),
        "adversary": ("claude", "claude-opus-5"),
        "formalizer": ("antigravity", "gemini-3.6-flash-high"),
        "presearch": ("claude", "claude-sonnet-5"),
    }
    seats.update(over)
    return seats


def test_a_scoped_cap_blocks_only_the_model_it_names(ledger):
    """The 08-06 shape: Fable's weekly cap is blown, everything else is
    fine. A run with nothing on Fable must not notice."""
    led, box = ledger
    box["blocks"] = [Block("claude", "Fable", None, "weekly cap")]
    assert led.blocked("claude", "claude-fable-5") is not None
    assert led.blocked("claude", "claude-opus-5") is None
    assert led.blocked("antigravity", "gemini-3.6-flash-high") is None
    assert led.blocked_kinds(_seats()) == {}


def test_a_global_window_blocks_every_model_on_that_provider(ledger):
    led, box = ledger
    box["blocks"] = [Block("claude", None, None, "five_hour")]
    assert led.blocked("claude", "claude-opus-5") is not None
    assert led.blocked("claude", "anything") is not None
    # ...and nobody else's
    assert led.blocked("antigravity", "gemini-3.6-flash-high") is None


def test_the_author_and_the_judge_stop_together(ledger):
    """A proposal with no judge is not partial progress — it is what
    gets discarded. Blocking the judge's seat must stop the author."""
    led, box = ledger
    box["blocks"] = [Block("claude", "Fable", None, "weekly cap")]
    seats = _seats(adversary=("claude", "claude-fable-5"))
    blocked = led.blocked_kinds(seats)
    assert set(blocked) == {"adversary", "strategist"}
    # the other pair is untouched — that is the whole point
    assert "formalizer" not in blocked and "presearch" not in blocked


def test_the_search_and_the_work_turn_stop_together(ledger):
    """Pre-search is a station of the formalizer chain; a search whose
    work turn cannot run is paid for and thrown away."""
    led, box = ledger
    box["blocks"] = [Block("antigravity", None, None, "provider down")]
    blocked = led.blocked_kinds(_seats())
    assert set(blocked) == {"formalizer", "presearch"}
    assert "strategist" not in blocked


def test_an_expired_block_stops_blocking(ledger):
    led, box = ledger
    box["blocks"] = [Block("claude", None, 999.0, "old window")]
    assert led.blocked("claude", "claude-opus-5") is None
    box["blocks"] = [Block("claude", None, 1_001.0, "live window")]
    assert led.blocked("claude", "claude-opus-5") is not None


def test_a_broken_probe_never_halts_the_framework(monkeypatch):
    """Unreachable is 'cannot confirm', not 'blocked'. A probe that
    throws must not be able to stop every pipeline."""
    def boom():
        raise RuntimeError("endpoint down")
    monkeypatch.setattr(quota, "_PROBES",
                        {"bad": boom,
                         "ok": lambda: [Block("claude", "Fable")]})
    led = Ledger(ttl=0.0)
    assert led.blocked("claude", "claude-fable-5") is not None
    assert led.blocked("claude", "claude-opus-5") is None


def test_display_names_match_configured_model_ids():
    """The endpoint says 'Fable'; the config says 'claude-fable-5'."""
    b = Block("claude", "Fable")
    assert b.covers("claude", "claude-fable-5")
    assert not b.covers("claude", "claude-opus-5")
    assert not b.covers("antigravity", "claude-fable-5")


def test_a_provider_without_a_usage_api_reports_nothing(monkeypatch):
    """Silence, not a guess: agy has no endpoint, and its exhaustion is
    inferred elsewhere (the dispatcher's spawn-failure breaker).

    `None`, not `[]` — "nobody answered" must not be spendable as "the
    seat is clear" (see `_PROBES`)."""
    assert quota._no_endpoint() is None


def test_the_claude_probe_keeps_the_per_model_dimension(monkeypatch):
    """The exact payload shape from 2026-08-06."""
    from Tooling.core import usage_quota
    monkeypatch.setattr(usage_quota, "fetch_usage", lambda: {
        "five_hour": {"utilization": 1.0, "resets_at": None},
        "seven_day": {"utilization": 58.0, "resets_at": None},
        "limits": [
            {"kind": "weekly_scoped", "is_active": True, "percent": 100,
             "resets_at": "2026-08-10T00:00:00+00:00",
             "scope": {"model": {"display_name": "Fable"}}},
            {"kind": "weekly_all", "is_active": False, "percent": 58},
        ],
    })
    blocks = quota._claude_blocks()
    assert len(blocks) == 1
    assert blocks[0].provider == "claude" and blocks[0].model == "Fable"
    assert blocks[0].until is not None


def test_the_dispatcher_holds_only_the_blocked_seats(monkeypatch):
    """End of the wire: a scoped cap on ONE model must leave the other
    pipelines dispatchable. This is the 2026-08-06 shape — the run had
    formalizer on Gemini and could have kept proving."""
    from Tooling.core import dispatcher

    monkeypatch.setattr(quota, "_PROBES",
                        {"t": lambda: [Block("claude", "Fable", 9e9, "cap")]})
    monkeypatch.setattr(dispatcher, "_quota_ledger", Ledger(ttl=0.0))
    monkeypatch.setattr(dispatcher, "_pipeline_seats", lambda: {
        "strategist": ("claude", "claude-fable-5"),
        "adversary": ("claude", "claude-fable-5"),
        "formalizer": ("antigravity", "gemini-3.6-flash-high"),
        "presearch": ("claude", "claude-sonnet-5"),
    })
    blocked = dispatcher._quota_ledger.blocked_kinds(
        dispatcher._pipeline_seats())
    assert set(blocked) == {"strategist", "adversary"}


def test_every_spawning_pipeline_has_a_seat():
    """A pipeline missing from the seat list is invisible to the ledger
    — it would spawn into an exhausted window and nobody would know."""
    from Tooling.core import dispatcher
    for kind in ("strategist", "adversary", "formalizer", "presearch",
                 "scholar"):
        assert kind in dispatcher._QUOTA_SEATS


def test_a_refused_spawn_teaches_the_ledger(monkeypatch):
    """The only channel a provider without a usage API has. agy carries
    no quota subcommand (probed 2026-08-07) but it does classify its own
    refusals into rc=126 — before this, that signal cooled one kind and
    the seat BOUND to it kept manufacturing work."""
    monkeypatch.setattr(quota, "_PROBES", {})
    led = Ledger(ttl=0.0, clock=lambda: 1_000.0)
    assert led.blocked_kinds(_seats()) == {}

    led.observe("antigravity", "gemini-3.6-flash-high",
                detail="formalizer spawn refused on quota")
    blocked = led.blocked_kinds(_seats())
    assert set(blocked) == {"formalizer", "presearch"}


def test_an_observed_block_expires_on_its_own(monkeypatch):
    """No reset time from the provider means 'not now', never 'forever':
    a misread must cost one wait, not the rest of the run."""
    monkeypatch.setattr(quota, "_PROBES", {})
    now = {"t": 1_000.0}
    led = Ledger(ttl=0.0, clock=lambda: now["t"])
    led.observe("antigravity", None)
    assert led.blocked("antigravity", "gemini-3.6-flash-high") is not None
    now["t"] += Ledger.OBSERVED_TTL_SEC + 1
    assert led.blocked("antigravity", "gemini-3.6-flash-high") is None


def test_probed_and_observed_blocks_coexist(monkeypatch):
    monkeypatch.setattr(quota, "_PROBES",
                        {"t": lambda: [Block("claude", "Fable", 9e9)]})
    led = Ledger(ttl=0.0, clock=lambda: 1_000.0)
    led.observe("antigravity", None)
    assert led.blocked("claude", "claude-fable-5") is not None
    assert led.blocked("antigravity", "gemini-3.6-flash-high") is not None
    assert led.blocked("claude", "claude-opus-5") is None


def test_every_dispatchable_seat_maps_to_its_queue_kind():
    """The bug this pins, found in production within an hour of shipping
    (2026-08-07): the ledger answers in SEAT names (config keys,
    lowercase) and the dispatcher asks in QUEUE kinds ('Formalizer').
    The mismatch disabled both halves silently — `observe()` looked up
    'Formalizer' in a lowercase table and got None, and the hold wrote
    'formalizer' into a cooldown map read as 'Formalizer'. agy's quota
    died and the framework kept spawning into it."""
    from Tooling.core import dispatcher
    for seat, kind in quota.DISPATCH_KIND.items():
        assert seat in dispatcher._QUOTA_SEATS, f"{seat} is not a seat"
        assert kind == seat.replace("_", " ").title().replace(" ", "_"), (
            f"{seat} -> {kind} is not the queue spelling")
    # every seat that can be dispatched has a mapping; stations do not
    assert "presearch" not in quota.DISPATCH_KIND
    assert set(quota.DISPATCH_KIND) <= set(dispatcher._QUOTA_SEATS)


def test_agy_refusal_carries_its_own_reset_time():
    """agy has no usage API, but says when it comes back. Dropping that
    left the backoff probing a 3-hour wall every few minutes."""
    import time as _t
    from Tooling.llm import antigravity_cli as agy
    agy._record_quota_reset(
        "individual quota reached. please upgrade your subscription "
        "to increase your limits. resets in 2h46m25s.")
    v = agy.take_quota_reset()
    assert v is not None and 9900 < v - _t.time() < 10050
    # consumed once — a stale reset must not silence a later refusal
    assert agy.take_quota_reset() is None


def test_a_refusal_without_a_reset_time_says_nothing():
    from Tooling.llm import antigravity_cli as agy
    agy._record_quota_reset("individual quota reached.")
    assert agy.take_quota_reset() is None


# --- the release side (2026-08-11) ------------------------------------
#
# Every test above pins the BLOCK direction. That asymmetry is the bug:
# splitting the global quota boolean into a per-seat ledger (2026-08-07)
# carried the block over and left the unblock behind, so a Fable weekly
# cap held the Strategist for eight hours across the account switch that
# had already fixed it. Block and release are one relation; pinning one
# end of it is what let this through.


def test_answered_and_unanswered_are_different_answers(monkeypatch):
    """`blocked() is None` means two incompatible things. Only one of
    them may lift a hold."""
    monkeypatch.setattr(quota, "_PROBES", {"claude": lambda: []})
    assert Ledger(ttl=0.0).confirmed_clear("claude", "claude-opus-5")

    for silent in (lambda: None, _boom):
        monkeypatch.setattr(quota, "_PROBES", {"claude": silent})
        led = Ledger(ttl=0.0)
        # not blocked...
        assert led.blocked("claude", "claude-opus-5") is None
        # ...but nobody said so, so it cannot buy a release
        assert not led.confirmed_clear("claude", "claude-opus-5")


def _boom():
    raise RuntimeError("endpoint down")


def test_a_capped_seat_is_not_confirmed_clear(monkeypatch):
    monkeypatch.setattr(quota, "_PROBES",
                        {"claude": lambda: [Block("claude", "Fable", 9e9)]})
    led = Ledger(ttl=0.0)
    assert not led.confirmed_clear("claude", "claude-fable-5")
    assert led.confirmed_clear("claude", "claude-opus-5")


def test_a_bound_group_is_released_only_as_a_whole(monkeypatch):
    """The mirror of `test_the_author_and_the_judge_stop_together`:
    releasing the author while the judge is still capped just
    re-manufactures the proposals that get discarded."""
    monkeypatch.setattr(quota, "_PROBES",
                        {"claude": lambda: [Block("claude", "Fable", 9e9)],
                         "antigravity": lambda: None})
    led = Ledger(ttl=0.0)
    seats = _seats(adversary=("claude", "claude-fable-5"))
    clear = led.clear_kinds(seats)
    assert "strategist" not in clear and "adversary" not in clear
    # agy never answers ⇒ its group is never confirmed either
    assert "formalizer" not in clear and "presearch" not in clear

    # judge's cap lifts ⇒ the pair comes back together
    monkeypatch.setattr(quota, "_PROBES", {"claude": lambda: []})
    clear = Ledger(ttl=0.0).clear_kinds(seats)
    assert {"strategist", "adversary"} <= clear


# ---------------------------------------------------------------------
# Hold and release, through the dispatch path (2026-08-06 / 08-11)
# ---------------------------------------------------------------------
#
# These used to drive `quota_wait.sync_quota_holds`, a reconciler that
# mirrored the ledger into `SchedulerState.quota_cooldown_kind`. It is
# gone (2026-08-13): the dispatcher asks the ledger once per tick and
# hands the answer to `admission`, so there is no mirrored state.
#
# The tests kept their subjects. The release direction in particular is
# worth more now than it was, because it has become a claim about
# STRUCTURE rather than about code that runs: nothing holds the fact, so
# nothing can fail to let go of it.

_FABLE_SEATS = {
    "strategist": ("claude", "claude-opus-5"),
    "adversary": ("claude", "claude-fable-5"),
    "formalizer": ("claude", "claude-sonnet-5"),
    "presearch": ("claude", "claude-sonnet-5"),
}


def _admits(kind: str, *, backoff=None) -> str:
    """The dispatcher's own question, asked the dispatcher's own way:
    ledger → `quota.blocked_dispatch_kinds` → `admission`. Going through
    the shared translation is the point — a private seat/kind conversion
    in this file would be the second spelling that broke the first
    version of the hold in production (2026-08-07)."""
    from Tooling.core.admission import admission
    blocked = quota.blocked_dispatch_kinds(Ledger(ttl=0.0), _FABLE_SEATS)
    return admission("g1", kind, cooldown_until={},
                     kind_backoff=backoff or {},
                     blocked_kinds=set(blocked), now=1000.0)


def test_the_hold_lifts_when_the_endpoint_says_the_seat_is_clear(monkeypatch):
    """The 2026-08-11 production shape: a Fable weekly cap held the
    Strategist for eight hours across the account switch that had
    already lifted it.

    There is no longer any code that performs this release — the ledger
    simply stops reporting the block and the next tick admits. The bug
    class died with the state it needed."""
    from Tooling.core.admission import ADMIT
    monkeypatch.setattr(quota, "_PROBES", {"claude": lambda: []})
    assert _admits("Strategist") == ADMIT


def test_the_hold_survives_a_silent_endpoint(monkeypatch):
    """Silence must not read as recovery: releasing on no-answer drops a
    real cap, while holding on no-answer only costs a wait.

    An unanswered probe contributes no blocks, so the ledger reports
    none — and the hold that matters in that case is the rc=126 brake
    the failing spawns themselves set. Pinned together here so the pair
    cannot drift apart."""
    from Tooling.core.admission import DENY_KIND_BACKOFF
    monkeypatch.setattr(quota, "_PROBES", {"claude": _boom})
    assert _admits("Strategist", backoff={"Strategist": 9e9}) \
        == DENY_KIND_BACKOFF


def test_the_hold_survives_while_the_bound_seat_is_still_capped(monkeypatch):
    """BOUND: the author and the judge live or die together. A capped
    Fable judge holds the Opus Strategist, because a proposal nobody can
    review is 25-28k output tokens that get discarded (11 of them,
    2026-08-06)."""
    from Tooling.core.admission import DENY_QUOTA
    monkeypatch.setattr(quota, "_PROBES",
                        {"claude": lambda: [Block("claude", "Fable", 9e9)]})
    assert _admits("Strategist") == DENY_QUOTA


def test_a_clear_ledger_does_not_release_the_rc126_backoff(monkeypatch):
    """The brake is a rate limit, not a quota fact: releasing it because
    the endpoint looks clear would let a refusing provider be hammered
    every tick. It has its own map and its own release, at the dispatch
    site, on the first non-quota outcome.

    This used to require care — the two shared one table, so the
    reconciler had to remember not to clear half of it. Now they are
    different arguments and the care is structural."""
    from Tooling.core.admission import DENY_KIND_BACKOFF
    monkeypatch.setattr(quota, "_PROBES", {"claude": lambda: []})
    assert _admits("Strategist", backoff={"Strategist": 9e9}) \
        == DENY_KIND_BACKOFF


def test_holding_still_works_after_all_this(monkeypatch):
    """The other end of the relation, and the 2026-08-06 lesson: a cap
    naming ONE model must not stop the pipelines seated on a different
    one. Fable's weekly cap holds strategist+adversary; the sonnet-seated
    formalizer keeps running."""
    from Tooling.core.admission import ADMIT, DENY_QUOTA
    monkeypatch.setattr(quota, "_PROBES",
                        {"claude": lambda: [Block("claude", "Fable", 9e9,
                                                  "weekly cap")]})
    assert _admits("Strategist") == DENY_QUOTA
    assert _admits("Formalizer") == ADMIT


def test_the_seat_to_kind_translation_has_one_home(monkeypatch):
    """`blocked_kinds` answers in seat names; the queue speaks dispatch
    kinds. The translation is `quota.blocked_dispatch_kinds` and nowhere
    else — a private copy at a call site is exactly what shipped the
    hold as a silent no-op on 2026-08-07."""
    monkeypatch.setattr(quota, "_PROBES",
                        {"claude": lambda: [Block("claude", "Fable", 9e9)]})
    out = quota.blocked_dispatch_kinds(Ledger(ttl=0.0), _FABLE_SEATS)
    assert set(out) == {"Strategist"}, (
        "expected QUEUE kinds, not seat names — got " + repr(sorted(out)))
    # pre-search is a station: held through its group, never on its own
    assert "presearch" not in out and "Presearch" not in out
