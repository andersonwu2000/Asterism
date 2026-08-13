"""Quota death must never be mistaken for a broken provider.

2026-08-13: a five-hour window closed mid-run. Three defences that
should each have turned that into "pause and wait" failed in sequence,
and the daemon exited claiming `claude.exe or provider appears broken`
while another thread in the same process was successfully parking to
that window's real reset time.

The corpus below is the real refusal, copied from
`.attempts/9006e09d-…/_spawn.stderr` of that run — the prose exactly as
the CLI wrote it, "session" and all. Inventing a sample would have
reproduced the original mistake: the markers were written in May from
prose observed in May, and nothing ever compared them to what the CLI
was saying afterwards.
"""
from __future__ import annotations

import json

import pytest

from Tooling.core import quota_wait
from Tooling.llm import claude_cli


# The two shapes that arrived together on 2026-08-13. Either alone is
# enough to convict; the framework saw both and recognised neither.
REJECTED_EVENT = json.dumps({
    "type": "rate_limit_event",
    "rate_limit_info": {
        "status": "rejected", "resetsAt": 1786618800,
        "rateLimitType": "five_hour", "overageStatus": "rejected",
        "overageDisabledReason": "org_level_disabled",
        "isUsingOverage": False,
    },
    "session_id": "dd6bf285-bf5a-42d6-bde1-6b7417c12060",
})
REFUSAL_PROSE = "You've hit your session limit · resets 7pm (Asia/Taipei)"


def test_the_structured_rejection_is_recognised_with_its_reset_time():
    spent, resets_at = claude_cli._quota_refusal(REJECTED_EVENT, "")
    assert spent
    assert resets_at == 1786618800.0, (
        "the reset epoch is the point — it is what lets the framework "
        "sleep to the reopening without asking the usage endpoint, which "
        "is exactly what failed on the day this was written")


def test_the_prose_survives_a_new_word_in_the_middle():
    """`session` is the word that cost a run. The sentence names WHICH
    limit was hit, and which one it is was never what we were asking."""
    spent, _ = claude_cli._quota_refusal(REFUSAL_PROSE, "")
    assert spent


@pytest.mark.parametrize("sentence", [
    "You've hit your limit · resets 8am",          # the May wording
    "You've hit your session limit · resets 7pm",  # 2026-07-03 onward
    "You've hit your weekly limit · resets Monday",
    "Usage limit reached",
])
def test_every_wording_of_the_same_sentence_counts(sentence):
    spent, _ = claude_cli._quota_refusal(sentence, "")
    assert spent, f"missed: {sentence!r}"


def test_a_rate_limit_warning_is_not_a_refusal():
    """The same event type rides along while requests are still being
    served. A substring scan for `rate_limit` would convict a healthy
    spawn — which is why the prose list is never taught the underscore
    spelling and the structured path checks `status`."""
    warning = json.dumps({
        "type": "rate_limit_event",
        "rate_limit_info": {"status": "allowed", "resetsAt": 1786618800},
    })
    spent, _ = claude_cli._quota_refusal(warning, "")
    assert not spent


def test_an_agent_merely_discussing_rate_limits_is_not_a_refusal():
    spent, _ = claude_cli._quota_refusal(
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text",
             "text": "The proof needs no rate_limit_event handling."}]}}), "")
    assert not spent


def test_the_reset_time_reaches_the_ledger_through_the_declaration(
    monkeypatch: pytest.MonkeyPatch,
):
    """`core.quota.reset_epoch` asks the capability declaration, never
    the provider's name — and claude now declares that it states one."""
    from Tooling.core import quota
    from Tooling.llm import capabilities
    assert capabilities.capabilities_for("claude").states_quota_reset
    monkeypatch.setattr(claude_cli, "_last_quota_reset", 1786618800.0)
    assert quota.reset_epoch("claude") == 1786618800.0
    # Consumed once, so a stale epoch cannot be replayed onto a later
    # block — the same rule agy and codex follow.
    assert quota.reset_epoch("claude") is None


# ─── "cannot confirm" is not "confirmed healthy" ───────────────────


def _probe_raising(monkeypatch, exc=OSError("connection reset")):
    def _boom():
        raise exc
    monkeypatch.setattr(quota_wait.usage_quota, "fetch_usage", _boom)
    monkeypatch.setattr(quota_wait, "QUOTA_CONFIRM_RETRY_SEC", 0.0)


def test_an_endpoint_that_never_answers_reads_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
):
    """The bug, in one assertion. Four failed probes used to collapse
    into the same `None` as a positive all-clear, and the breaker spent
    that silence as a verdict of health."""
    _probe_raising(monkeypatch)
    probe = quota_wait.probe_quota(0.0, attempts=4)
    assert probe.verdict == quota_wait.UNKNOWN
    assert not probe


def test_a_healthy_endpoint_still_reads_as_healthy(
    monkeypatch: pytest.MonkeyPatch,
):
    """The breaker's real job must survive the fix: when the endpoint
    says quota is fine, a spawn that keeps dying IS the provider."""
    monkeypatch.setattr(quota_wait.usage_quota, "fetch_usage", lambda: {})
    monkeypatch.setattr(quota_wait.usage_quota, "exhausted_until",
                        lambda raw: (False, None))
    probe = quota_wait.probe_quota(0.0, attempts=1)
    assert probe.verdict == quota_wait.HEALTHY
    assert not probe


def test_probe_failures_are_printed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
):
    """They were swallowed whole, so the post-mortem could establish
    that four probes failed and nothing about why — 429 congestion and a
    credentials race look identical from outside and want different
    fixes."""
    _probe_raising(monkeypatch, OSError("429 Too Many Requests"))
    quota_wait.probe_quota(0.0, attempts=2)
    out = capsys.readouterr().out
    assert "429 Too Many Requests" in out
    assert "UNKNOWN" in out


class _St:
    """The scheduler fields quota_wait touches."""
    quota_wait_until = 0.0
    quota_wait_entered = 0.0
    quota_wait_rechecked_at = 0.0
    consec_unconfirmed_trips = 0


def test_silence_buys_a_hold_not_an_exit(capsys: pytest.CaptureFixture):
    st = _St()
    assert quota_wait.hold_unconfirmed(st, source="10 fast-fails")
    assert st.quota_wait_until > 0.0, "dispatch must actually be paused"
    assert "holding dispatch" in capsys.readouterr().out


def test_but_the_hold_is_bounded():
    """An unbounded hold turns "we cannot tell" into a daemon that waits
    forever on a fault nobody can see — the exact failure the breaker's
    original discipline was right to fear."""
    st = _St()
    held = [quota_wait.hold_unconfirmed(st, source="s")
            for _ in range(quota_wait.UNCONFIRMED_TRIP_LIMIT + 1)]
    assert all(held[:quota_wait.UNCONFIRMED_TRIP_LIMIT])
    assert held[-1] is False, "the exit must eventually stand"
