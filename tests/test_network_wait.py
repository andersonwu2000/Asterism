"""Network park (`core/network_wait`, 2026-08-18) — a transport-level
spawn death parks dispatch behind a connectivity probe instead of
feeding the unclassified breaker.

Discipline under test (mirrors quota_wait's):
  * only a NEGATIVE probe parks (a reachable endpoint = blip);
  * only a POSITIVE probe resumes (silence keeps parking);
  * the pause is excluded from the budget clock;
  * the seated provider's declared `api_host` leads the probe list.
"""
from __future__ import annotations

import pytest

from Tooling.core import network_wait
from Tooling.core.dispatcher import SchedulerState
from Tooling.state import failures


# ------------------------------------------------- classification SoT

def test_network_prose_is_recognised() -> None:
    assert failures.is_network_failure(
        "stream disconnected before completion: error sending request")
    assert failures.is_network_failure("getaddrinfo ENOTFOUND chatgpt.com")
    assert not failures.is_network_failure("")
    assert not failures.is_network_failure(None)
    # An HTTP-level refusal is the provider ANSWERING — the opposite fact.
    assert not failures.is_network_failure("HTTP 429 Too Many Requests")


def test_provider_network_is_registered_no_charge() -> None:
    t = failures.REGISTRY["provider_network"]
    assert t.origin == "provider_infra", "must never burn a goal attempt"
    assert not t.agent_visible, "no lesson for the agent in a dead NIC"


# ------------------------------------------------- park / resume

def test_a_reachable_probe_declines_to_park(monkeypatch) -> None:
    st = SchedulerState()
    monkeypatch.setattr(network_wait, "probe_connectivity",
                        lambda hosts, **kw: True)
    assert network_wait.maybe_enter(
        st, kind="formalizer", source="test") is False
    assert st.net_wait_down is False


def test_an_unreachable_probe_parks_and_only_a_positive_resumes(
        monkeypatch) -> None:
    st = SchedulerState()
    monkeypatch.setattr(network_wait, "probe_connectivity",
                        lambda hosts, **kw: False)
    assert network_wait.maybe_enter(
        st, kind="formalizer", source="test") is True
    assert st.net_wait_down is True

    # Silence keeps parking…
    t = st.net_wait_probed_at
    assert network_wait.tick(
        st, t + network_wait.NETWORK_PROBE_INTERVAL_SEC + 1) is True
    assert st.net_wait_down is True

    # …a positive answer resumes.
    monkeypatch.setattr(network_wait, "probe_connectivity",
                        lambda hosts, **kw: True)
    t = st.net_wait_probed_at
    assert network_wait.tick(
        st, t + network_wait.NETWORK_PROBE_INTERVAL_SEC + 1) is False
    assert st.net_wait_down is False
    assert st.net_wait_paused > 0.0


def test_paused_time_is_excluded_from_the_budget_clock(
        monkeypatch) -> None:
    st = SchedulerState()
    monkeypatch.setattr(network_wait, "probe_connectivity",
                        lambda hosts, **kw: False)
    network_wait.maybe_enter(st, kind=None, source="test")
    now = st.net_wait_entered + 120.0
    assert network_wait.paused_total(st, now) == pytest.approx(120.0)


# ------------------------------------------------- probe targets

def test_declared_api_host_leads_the_probe_list() -> None:
    hosts = network_wait.probe_hosts_for("formalizer")
    # Whatever provider is seated, the list is non-empty and ends with
    # the generic anchors; a declared api_host must come first.
    assert hosts, "probe list must never be empty"
    from Tooling.llm import capabilities as caps
    declared = caps.for_kind("formalizer").api_host
    if declared:
        assert hosts[0] == declared
    for anchor in network_wait.FALLBACK_PROBE_HOSTS:
        assert anchor in hosts


def test_live_providers_declare_their_api_host() -> None:
    """The two backends verified in the 08-17/18 outage carry the fact;
    a future seat change must not silently lose the park's first probe
    target."""
    from Tooling.llm import capabilities as caps
    assert caps.CAPABILITIES["claude"].api_host == "api.anthropic.com"
    assert caps.CAPABILITIES["codex"].api_host == "chatgpt.com"
