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

WHO OWNS WHAT. The quota half is not stored here or in the scheduler at
all — it is asked of `core.quota.Ledger` once per tick and handed in.
It used to be mirrored into `SchedulerState.quota_cooldown_kind` by a
reconciler (`quota_wait.sync_quota_holds`), which existed only because
one fact had two homes, and whose own docstring recorded the cost: the
release direction shipped without an unblock, and a Fable weekly cap
held the Strategist for eight hours across the account switch that had
already lifted it (2026-08-11). A mirror needs releasing; an answer
does not.
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

#: The seat's provider/model is out of quota — a FACT owned by
#: `core.quota.Ledger` and re-asked every tick, never mirrored here.
#: The row should be DROPPED: `bfs_refill` re-derives it once the block
#: lifts, and holding a lease meanwhile blocks refill's own dedup.
DENY_QUOTA = "quota-blocked"

#: The kind is serving an rc=126 exponential back-off — a rate brake,
#: not a quota fact, and the distinction is the whole reason this is a
#: separate verdict. The two shared one map until 2026-08-13, and that
#: is why releasing was hard: you cannot safely clear a mixed table.
#: `sync_quota_holds` said so itself, refusing to clear the brake while
#: clearing the facts, and a Fable weekly cap consequently held the
#: Strategist for eight hours across the account switch that had
#: already fixed it (2026-08-11). Dropped like a quota block: the whole
#: kind is parked either way.
DENY_KIND_BACKOFF = "kind-backoff"

#: This one (target, kind) is backing off after an infra failure. The
#: row should be PUT BACK, not dropped — it is still wanted, only the
#: clock is wrong, and it may have come from a retry path that refill
#: would never re-derive.
DENY_TARGET_COOLED = "target-cooldown"


def admission(target_id: str, kind: str, *,
              cooldown_until: "dict[tuple[str, str], float] | None",
              kind_backoff: "dict[str, float] | None",
              blocked_kinds: "dict[str, object] | set[str] | None",
              now: float) -> str:
    """`ADMIT`, or the reason not to.

    Three inputs because there are three facts, each with exactly one
    owner:

      `blocked_kinds`   the quota Ledger's answer for THIS tick. Passed
                        in rather than mirrored into scheduler state,
                        which is the point of the whole exercise: state
                        that is never held cannot be forgotten when it
                        is time to release it.
      `kind_backoff`    the dispatcher's own rc=126 rate brake.
      `cooldown_until`  the dispatcher's per-target infra back-off.

    Kind-wide before per-target: a row under both takes the drop,
    because its whole kind is parked and refill will bring it back.

    `None` anywhere means "no restriction of that sort", not "blocked" —
    most `bfs_refill` callers pass none of them.
    """
    if kind in (blocked_kinds or ()):
        return DENY_QUOTA
    if (kind_backoff or {}).get(kind, 0.0) > now:
        return DENY_KIND_BACKOFF
    if (cooldown_until or {}).get((target_id, kind), 0.0) > now:
        return DENY_TARGET_COOLED
    return ADMIT
