"""The door: may this (target, kind) be dispatched right now?

One question, one body. `pool.submit(_run_pipeline …)` in
`core/dispatcher` is the only spawn site in the system, so every
dispatch that will ever happen passes this predicate — including the
next path someone adds that re-enqueues directly and never touches
`bfs_refill`.

It lives in its own module rather than as a helper inside the
dispatcher because that is what "one home for a fact" costs: a pure
function buried in a 2,800-line file is discoverable only by whoever
already knows it is there, and the failure this exists to prevent is
precisely someone not knowing. Nothing here imports from the
dispatcher; the dependency runs one way.

WHY IT COST A RUN. The per-target cooldown was set on every infra
failure and read only by `bfs_refill`. The rows that most needed it do
not come from refill — `strategist-retry` and `forward-retry`
re-enqueue directly — so the pop loop handed them straight back out
6.3 seconds apart against a 30-second brake. Ten spawn_fast_fails in
51 seconds (2026-08-13) outran the quota ledger's own 60-second cache
and tripped the daemon-exit breaker before anything could notice that
the subscription window had simply closed.

Adding the missing comparison to the pop loop would have made three
copies of one question: refill's filter, the pop loop's, and the quota
branch's queue flush. This is the body they share instead.
"""
from __future__ import annotations

#: Why a (target, kind) may not be dispatched. `""` is admitted.
#:
#: A REASON rather than a bool, because the two refusals are not
#: interchangeable at the call site — one deletes the queue row and the
#: other puts it back. Collapsing them into `False` is the same mistake
#: `core.quota_wait.QuotaProbe` was created to undo one layer up, where
#: "the endpoint says you are fine" and "the endpoint never answered"
#: had been sharing a single `None`.
ADMIT = ""

#: The whole KIND is parked (a provider-level quota hold). The row
#: should be DROPPED: `bfs_refill` re-derives it once the hold lifts,
#: and holding a lease meanwhile blocks refill's own dedup.
DENY_KIND_COOLED = "kind-cooldown"

#: This one (target, kind) is backing off after an infra failure. The
#: row should be PUT BACK, not dropped — it is still wanted, only the
#: clock is wrong, and it may have come from a retry path that refill
#: would never re-derive.
DENY_TARGET_COOLED = "target-cooldown"


def admission(target_id: str, kind: str, *,
              cooldown_until: "dict[tuple[str, str], float] | None",
              quota_cooldown_kind: "dict[str, float] | None",
              now: float) -> str:
    """`ADMIT`, or the reason not to.

    Kind before target: a row under both holds takes the drop, because
    its whole kind is parked and refill will bring it back.

    `None` for either map means "no cooldowns of that sort", not "cooled"
    — most `bfs_refill` callers pass neither.
    """
    if (quota_cooldown_kind or {}).get(kind, 0.0) > now:
        return DENY_KIND_COOLED
    if (cooldown_until or {}).get((target_id, kind), 0.0) > now:
        return DENY_TARGET_COOLED
    return ADMIT
