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

`resolve_fatal` then decides what a fatal gateway means: ONE bounded
self-heal (owner ruling 2026-08-14) for the case a relaunch can
actually fix, a loud rc=2 for everything else. A repeating machinery
fault must reach the operator — an unbounded relaunch loop warms for
five minutes, dies, and repeats all night while looking like patience.

POLICY LIVES IN THE CALLER. The numbers (how long to cool, how many
consecutive failures, how long to hold, how long a relaunch must
survive) stay in `core.dispatcher` with the rest of the scheduler's
constants and are passed in; this module owns the mechanism only.
Nothing here exits the daemon either: the functions return a verdict
and the dispatcher acts on it, so the one place that can end a run
stays the one place that could before.
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

    Holding is all this does. The bounded self-heal that may follow it
    is `resolve_fatal`'s (one credit, owner ruling 2026-08-14); this
    only stops us buying spawns for a process we can see is not there.
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


#: The gateway came up and then failed its own gate — relaunching
#: repeats the same failure, so this ending is always final.
FATAL_WARM = "warm"
#: The gateway was serving and then stopped answering. A process can
#: die once for reasons that do not recur, which is the only case a
#: relaunch can help.
FATAL_GONE = "gone"


def fatal_reason(st, *, warm_failed: "str | None", holding: bool,
                 now: float, grace_sec: float) -> "tuple[str, str] | None":
    """The gateway's two fatal endings, asked as one question.

    Both mean the gateway is not usable, and both take the same action:
    drain the in-flight NL work (its commits are durable), release the
    leases, exit rc=2. They were written as two blocks, which is how the
    second one nearly shipped without draining.

    Returns `(kind, message)` or None. The KIND matters because only one
    of them can be healed by trying again.
    """
    if warm_failed:
        return FATAL_WARM, f"warm-up failed: {warm_failed}"
    if holding and down_expired(st, now, grace_sec):
        return FATAL_GONE, (
            f"/health silent for {grace_sec:.0f}s — the gateway is gone")
    return None


def may_relaunch(st, now: float, budget_sec: float) -> bool:
    """Is a self-heal credit available?

    ONE relaunch, and the credit comes back only once the new gateway
    has shown the relaunch was worth it. Two ways to show it, whichever
    lands first:

      * a pipeline completed successfully — the direct evidence, cleared
        by the dispatcher's own success branch (`gateway_relaunched_at`
        back to None);
      * `budget_sec` elapsed — `dispatch.spawn_timeout_sec`, this
        system's definition of one work unit's worth of time. This is
        the empty-queue case, where nothing could have succeeded because
        nothing was asked.

    Dying before either is a CRASH LOOP, and the loud exit is correct
    for it: a gateway that dies from something structural (a worker
    eating the box's memory, an olean that will not load) would
    otherwise relaunch, warm for five minutes, die, and repeat all
    night while looking exactly like patience. Single accidents the
    machine absorbs; repeating machinery faults go to the operator —
    the standing ruling from the `unclassified_spawn_failure` breaker
    (2026-08-08), for the same reason.

    A plain "did it live long enough" timer would NOT do: a gateway that
    lives twenty minutes serving nothing and then dies is the same crash
    loop with a longer fuse. That is why the primary evidence is work
    done, and the clock is only the fallback for when no work was asked.
    """
    if st.gateway_relaunched_at is None:
        return True
    return now - st.gateway_relaunched_at >= budget_sec


def relaunch(st, workspace) -> dict:
    """Spend the credit: kill whatever is left, start a fresh gateway in
    the background, and hand back the new warm state.

    Same path the daemon uses at startup, so the semantics that already
    exist carry over unchanged — Lean kinds stay queued while
    `ready` is False and NL kinds keep dispatching through the warm.
    `kill_current_gateway` is a no-op when nothing answers, which is the
    usual case here; `start_gateway` owns the rest (it waits for a
    gateway that is mid-warm rather than racing it for the port).
    """
    from ..lsp import lifecycle
    from . import warmup
    st.gateway_relaunched_at = time.time()
    st.consec_gateway_unreachable = 0
    st.gateway_down_since = None
    print("[gateway] gone — spending the one self-heal credit: killing "
          "any remnant and warming a fresh gateway. If this one dies "
          "before it finishes a pipeline, that is a crash loop and the "
          "daemon exits instead of trying again.", flush=True)
    lifecycle.kill_current_gateway()
    return warmup.start_background(workspace)


def resolve_fatal(st, workspace, *, warm_failed: "str | None",
                  holding: bool, now: float, grace_sec: float,
                  budget_sec: float) -> "tuple[dict | None, str | None]":
    """The whole "gateway is unusable" decision: `(new_warm, message)`.

    Exactly one is ever non-None. A new warm state means we healed and
    the run continues; a message means this run is over.
    """
    fatal = fatal_reason(st, warm_failed=warm_failed, holding=holding,
                         now=now, grace_sec=grace_sec)
    if fatal is None:
        return None, None
    kind, message = fatal
    if kind == FATAL_GONE and may_relaunch(st, now, budget_sec):
        return relaunch(st, workspace), None
    if kind == FATAL_GONE and st.gateway_relaunched_at is not None:
        message += (" again, and the self-heal credit is already spent "
                    "— this is a crash loop, not an accident")
    return None, (
        f"{message}. Restart the daemon (it relaunches the gateway) and "
        f"read .asterism/logs/gateway.log for the underlying crash")


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
