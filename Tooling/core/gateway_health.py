"""Is the Lean gateway there, and what does the daemon do when it is not?

One concern, one home. It used to be a single function inside the
2,900-line dispatcher, and the half that was missing — ASK the gateway
before buying another spawn against it — is the kind of thing nobody
adds to a file that size.

The two mechanisms here are not redundant and neither covers the other:

  `unreachable_backoff`  counts spawns that came back saying the gateway
                         was unreachable. It is the only witness when
                         the gateway ANSWERS `/health` and yet every
                         pipeline against it fails.
  `liveness_gate`        asks `/health` directly. It is the only witness
                         when the process is simply gone — and it costs
                         a local HTTP GET rather than a spawn.

POLICY LIVES IN THE CALLER. The numbers (how long to cool, how many
consecutive failures, how long to hold) stay in `core.dispatcher` with
the rest of the scheduler's constants and are passed in; this module
owns the mechanism only. Nothing here exits the daemon either: the
functions return a verdict and the dispatcher acts on it, so the one
place that can end a run stays the one place that could before.
"""
from __future__ import annotations

import time


def liveness_gate(st) -> bool:
    """Once a spawn has reported the gateway unreachable, ASK the
    gateway before paying for another one. True means hold dispatch.

    The old sequence was: spawn (tens of thousands of tokens) → die →
    cool 30s → spawn again → die … eight times, then exit. Whether the
    gateway is alive is a local HTTP GET that costs nothing, and the
    answer was never asked for. 2026-08-13 measured the bill for one
    such episode at 11 spawns / 196,013 output tokens — 89% of that
    run's entire output.

    Deliberately dormant until the first failure: probing before every
    dispatch would ask a healthy system a question it has already
    answered, and during a warm `/health` says 503, which this cannot
    distinguish from death (`_ping_health` catches `HTTPError` with the
    rest of `URLError`). In the failure state that ambiguity is
    harmless — waiting out a warm is exactly right.

    This does NOT relaunch the gateway. Self-healing changes what the
    daemon does to a run in flight and is the owner's call (#203);
    holding is not — it only stops us buying spawns for a process we
    can see is not there.
    """
    if st.consec_gateway_unreachable <= 0:
        return False
    from ..lsp.lifecycle import _ping_health
    if _ping_health(timeout=2.0) is not None:
        if st.gateway_down_since is not None:
            print("[gateway] /health answers again — resuming dispatch",
                  flush=True)
        # Evidence that the gateway is up ends the streak; a stale count
        # would otherwise sit one failure short of tripping a breaker
        # about a healthy process.
        st.consec_gateway_unreachable = 0
        st.gateway_down_since = None
        return False
    if st.gateway_down_since is None:
        st.gateway_down_since = time.time()
        print("[gateway] a spawn reported the gateway unreachable and "
              "/health does not answer — holding dispatch (no spawn is "
              "worth buying against a dead gateway).", flush=True)
    return True


def down_expired(st, now: float, grace_sec: float) -> bool:
    """Has the hold outlived its grace? Then the gateway is not coming
    back on its own and the daemon should end the run loudly — the same
    ending the spawn-counting breaker gives, at the same moment, having
    bought nothing on the way there.

    `None` is "not holding" and never expires: a hold that never started
    must not read as one that ran out."""
    return (st.gateway_down_since is not None
            and now - st.gateway_down_since >= grace_sec)


def fatal_reason(st, *, warm_failed: "str | None", holding: bool,
                 now: float, grace_sec: float) -> "str | None":
    """The gateway's two fatal endings, asked as one question.

    Both mean the same thing — the gateway is not usable and will not
    become usable — and both take the same action: drain the in-flight
    NL work (its commits are durable), release the leases, exit rc=2.
    They were written as two blocks, which is how the second one nearly
    shipped without draining.

    Returns the reason to print, or None to keep running.
    """
    if warm_failed:
        return f"warm-up failed: {warm_failed}"
    if holding and down_expired(st, now, grace_sec):
        return (f"/health silent for {grace_sec:.0f}s — the gateway is "
                f"gone and is not coming back on its own. Restart the "
                f"daemon (it relaunches the gateway) and read "
                f".asterism/logs/gateway.log for the underlying crash")
    return None


def unreachable_backoff(st, *, kind: str, tk: str, tid: str,
                        cooldown_sec: float, limit: int) -> bool:
    """Shared gateway-unreachable back-off + circuit breaker (task #9 —
    formerly two verbatim copies in the normal-result and worker-
    exception cascade paths; editing the breaker rule meant editing
    both). True when the breaker trips; the CALLER exits the daemon."""
    st.cooldown_until[(tid, kind)] = time.time() + cooldown_sec
    st.consec_gateway_unreachable += 1
    print(f"[cooldown] {kind} {tk}={tid} cooled {cooldown_sec:.0f}s after "
          f"gateway_unreachable "
          f"(consec={st.consec_gateway_unreachable})", flush=True)
    if st.consec_gateway_unreachable >= limit:
        print(f"[dispatcher] {st.consec_gateway_unreachable} consecutive "
              f"gateway_unreachable — gateway appears permanently dead; "
              f"exiting. Restart daemon (gateway will be re-launched) and "
              f"inspect .asterism/logs/gateway.log for the underlying "
              f"crash.", flush=True)
        return True
    return False
