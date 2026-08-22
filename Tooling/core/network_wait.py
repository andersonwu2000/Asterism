"""Network-wait — park dispatch while the network is down instead of
feeding the unclassified breaker (user-approved 2026-08-18).

The 08-17/18 outage: a dead wired WAN turned every codex spawn into
`stream disconnected` rc=1, twelve of them tripped the consecutive-
unclassified breaker, and the daemon exited rc=2 — correct for an
unnamed fault, wrong for a nameable one, and it needs an operator on
site to restart. A network drop is a *park*, exactly like quota: the
end is knowable (the probe answers), nothing is anyone's fault, and
dispatch should resume by itself.

Discipline mirrors `quota_wait`:
  * Only a NEGATIVE probe parks — a reachable endpoint means the drop
    was a blip, and the caller keeps its ordinary cooldown path.
  * Only a POSITIVE probe resumes — an unreachable probe keeps parking.
  * No park cap (owner ruling: park is not a terminal state; the
    machine never self-stops), but a heartbeat line keeps it audible.

State lives on the dispatcher's `SchedulerState` (`net_wait_*` fields)
— this module is the behavior, not the storage.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request

#: Re-probe cadence while parked, and how often the heartbeat logs.
NETWORK_PROBE_INTERVAL_SEC = 60.0
NETWORK_WAIT_LOG_EVERY_SEC = 600.0
#: Per-host probe timeout. Short on purpose: a working network answers
#: a TLS HEAD in well under this; a hung SYN eats the whole budget.
PROBE_TIMEOUT_SEC = 10.0

#: Fallback probe targets when the seated provider declares no
#: `api_host` — reachability of ANY of these is read as "the network is
#: back". The two live provider backends plus one neutral anchor.
FALLBACK_PROBE_HOSTS: "tuple[str, ...]" = (
    "api.anthropic.com", "chatgpt.com", "www.google.com")


#: The zen flavor rides a LOCAL translation shim, and its liveness is a
#: channel fact the host probes cannot see: when the shim died
#: (2026-08-22) every anchor still answered, so nothing parked, and the
#: daemon dispatched into the dead channel for 40 minutes — five
#: agent_timeouts and one goal charged to exhaustion for what was a
#: transport fault. The channel probe closes that gap: seated-on-zen ⇒
#: the shim must answer, or dispatch parks exactly like a network drop.
CHANNEL_PROBE_INTERVAL_SEC = 30.0

#: The seat kinds whose provider choice can arm the channel probe —
#: the yaml seat table's own vocabulary.
_SEAT_KINDS = ("strategist", "adversary", "formalizer", "presearch",
               "librarian")


def channel_url_for(kind: "str | None" = None) -> "str | None":
    """The local channel to probe, or None when no seat rides one.

    With a `kind`, answers for that seat alone (failure-entry path);
    with None, answers if ANY seat is on zen (the pre-dispatch tick,
    which has no failing kind in hand — the channel is one process
    shared by every zen seat)."""
    try:
        from ..llm import capabilities as _caps
        kinds = (kind,) if kind else _SEAT_KINDS
        if not any(_caps.provider_for_kind(k) == "zen" for k in kinds):
            return None
        from . import config
        return str(config.get("zen.base_url",
                              env_var="ASTERISM_ZEN_BASE_URL",
                              default="http://127.0.0.1:8898/v1"))
    except Exception:  # noqa: BLE001 — a probe list must never raise
        return None


def probe_channel(url: str, *,
                  timeout: float = PROBE_TIMEOUT_SEC) -> bool:
    """True iff the local channel answers HTTP at all — any status
    (the shim's 501 on GET included) proves the process is there."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:  # noqa: BLE001 — refused/timeout = down
        return False


def probe_hosts_for(kind: "str | None") -> "tuple[str, ...]":
    """The probe targets for a failure on this pipeline kind: the seated
    provider's declared `api_host` first, then the fallback anchors —
    the provider host answers "can MY backend be reached", the anchors
    answer "is there a network at all", and both count as recovery
    because the park's trigger was a transport-level failure."""
    hosts: "list[str]" = []
    try:
        from ..llm import capabilities as _caps
        declared = _caps.for_kind(kind).api_host
        if declared:
            hosts.append(declared)
    except Exception:  # noqa: BLE001 — a probe list must never raise
        pass
    for h in FALLBACK_PROBE_HOSTS:
        if h not in hosts:
            hosts.append(h)
    return tuple(hosts)


def probe_connectivity(hosts: "tuple[str, ...]",
                       *, timeout: float = PROBE_TIMEOUT_SEC) -> bool:
    """True iff ANY host answers an HTTPS request with an HTTP response.

    Positive-answer discipline: a status code — any status code, 403
    and 404 included — proves a TCP+TLS+HTTP round trip, which is the
    fact in question. Exceptions (DNS failure, unreachable, timeout,
    reset) are "no answer", never "answered no"."""
    for host in hosts:
        req = urllib.request.Request(f"https://{host}/", method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=timeout):
                return True
        except urllib.error.HTTPError:
            return True  # the server ANSWERED — network is up
        except Exception:  # noqa: BLE001 — URLError/timeout/reset = down
            continue
    return False


def _log_hosts(hosts: "tuple[str, ...]") -> str:
    return ", ".join(hosts)


def maybe_enter(st, *, kind: "str | None", source: str) -> bool:
    """Enter (or extend) the network park if the probe confirms the
    network is down. True = parked (caller stands down: no breaker
    bump, no escalation); False = probe says reachable, the failure was
    a blip — the caller keeps its ordinary cooldown path."""
    ch = channel_url_for(kind)
    if ch is not None and not probe_channel(ch):
        # The channel is the FIRST hop; a dead shim with a healthy
        # internet must park, so this check precedes (and overrides)
        # the any-anchor-answers rule below.
        now = time.time()
        if not st.net_wait_down:
            st.net_wait_down = True
            st.net_wait_entered = now
            st.net_wait_logged_at = now
            print(f"[network-wait] {source} — the local channel does "
                  f"not answer ({ch}); all dispatch paused until it "
                  f"returns (probing every "
                  f"{NETWORK_PROBE_INTERVAL_SEC:.0f}s, no attempts "
                  f"charged)", flush=True)
        st.net_wait_channel = ch
        st.net_wait_probed_at = now
        return True
    hosts = probe_hosts_for(kind)
    if probe_connectivity(hosts):
        if st.net_wait_down:
            # A parked state discovering health here is fine too.
            setattr(st, "net_wait_channel", None)
            _resume(st, time.time(), reason="entry probe answered")
        return False
    now = time.time()
    if not st.net_wait_down:
        st.net_wait_down = True
        st.net_wait_entered = now
        st.net_wait_logged_at = now
        print(f"[network-wait] {source} — no probe target answers "
              f"({_log_hosts(hosts)}); all dispatch paused until the "
              f"network returns (probing every "
              f"{NETWORK_PROBE_INTERVAL_SEC:.0f}s, no attempts charged)",
              flush=True)
    st.net_wait_hosts = hosts
    st.net_wait_probed_at = now
    return True


def _resume(st, now: float, *, reason: str) -> None:
    st.net_wait_paused += now - st.net_wait_entered
    st.net_wait_down = False
    st.net_wait_logged_at = 0.0
    print(f"[network-wait] connectivity restored ({reason}) — resuming "
          f"dispatch after {(now - st.net_wait_entered) / 60:.0f}min "
          f"parked", flush=True)


def tick(st, now: float) -> bool:
    """Per-tick network-wait state machine. True = dispatch stays
    paused this tick; probes at `NETWORK_PROBE_INTERVAL_SEC` cadence
    and resumes on the first positive answer."""
    if not st.net_wait_down:
        # Channel watch while healthy: a shim that dies BETWEEN spawn
        # failures must not need a casualty to be noticed — the park
        # exists precisely so nothing is charged for a dead channel.
        if now - getattr(st, "net_chan_checked_at", 0.0) \
                >= CHANNEL_PROBE_INTERVAL_SEC:
            st.net_chan_checked_at = now
            ch = channel_url_for(None)
            if ch is not None and not probe_channel(ch):
                st.net_wait_down = True
                st.net_wait_entered = now
                st.net_wait_logged_at = now
                st.net_wait_channel = ch
                st.net_wait_probed_at = now
                print(f"[network-wait] channel watch — the local "
                      f"channel does not answer ({ch}); all dispatch "
                      f"paused until it returns (probing every "
                      f"{NETWORK_PROBE_INTERVAL_SEC:.0f}s, no attempts "
                      f"charged)", flush=True)
                return True
        return False
    if now - st.net_wait_probed_at >= NETWORK_PROBE_INTERVAL_SEC:
        st.net_wait_probed_at = now
        ch = getattr(st, "net_wait_channel", None)
        if ch is not None:
            if probe_channel(ch):
                st.net_wait_channel = None
                _resume(st, now, reason="channel answered")
                return False
        else:
            hosts = (getattr(st, "net_wait_hosts", None)
                     or FALLBACK_PROBE_HOSTS)
            if probe_connectivity(hosts):
                _resume(st, now, reason="re-probe answered")
                return False
    if now - st.net_wait_logged_at >= NETWORK_WAIT_LOG_EVERY_SEC:
        st.net_wait_logged_at = now
        print(f"[network-wait] dispatch paused — network down for "
              f"{(now - st.net_wait_entered) / 60:.0f}min; still probing",
              flush=True)
    return True


def paused_total(st, now: float) -> float:
    """Seconds the budget clock must ignore: closed pauses plus the
    currently-open one — same contract as `quota_wait.paused_total`."""
    total = st.net_wait_paused
    if st.net_wait_down:
        total += now - st.net_wait_entered
    return total
