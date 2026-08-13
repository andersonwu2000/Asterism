"""One door, one predicate, and the two refusals stay different.

Every dispatch in the system goes through a single `pool.submit`. That
made the pop loop the natural place for an admission check, and it is
where one lived — alongside a second copy in `bfs_refill` and a third
answer to the same question in the quota branch's queue flush. The
per-target half was in refill only, which is how ten spawn_fast_fails
landed 51 seconds apart against a 30s brake on 2026-08-13 and reached
the daemon-exit breaker before the quota ledger's 60s cache could
notice the subscription window had closed.

`admission()` is now that predicate's only body. These tests defend the
three properties that make it worth having, because each of them is
something a later, reasonable-looking edit would take away.
"""
from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest

from Tooling.core import dispatcher
from Tooling.core.admission import (
    ADMIT, DENY_KIND_COOLED, DENY_TARGET_COOLED, admission)

SRC = Path(dispatcher.__file__).read_text(encoding="utf-8")


# ─── the predicate itself ─────────────────────────────────────────────

def test_an_uncooled_pair_is_admitted():
    assert admission("g1", "Formalizer", cooldown_until={},
                     quota_cooldown_kind={}, now=100.0) == ADMIT


def test_a_kind_wide_hold_denies_by_kind():
    assert admission(
        "g1", "Formalizer", cooldown_until={},
        quota_cooldown_kind={"Formalizer": 200.0},
        now=100.0) == DENY_KIND_COOLED


def test_a_per_target_backoff_denies_by_target():
    assert admission(
        "g1", "Formalizer", cooldown_until={("g1", "Formalizer"): 200.0},
        quota_cooldown_kind={}, now=100.0) == DENY_TARGET_COOLED


def test_a_cooldown_on_a_different_target_does_not_leak():
    assert admission(
        "g1", "Formalizer", cooldown_until={("g2", "Formalizer"): 200.0},
        quota_cooldown_kind={}, now=100.0) == ADMIT


def test_an_expired_cooldown_admits():
    """#103's original point: a past epoch in the map is not a hold."""
    assert admission(
        "g1", "Formalizer",
        cooldown_until={("g1", "Formalizer"): 50.0},
        quota_cooldown_kind={"Formalizer": 50.0},
        now=100.0) == ADMIT


def test_absent_maps_mean_no_cooldown_anywhere():
    """`bfs_refill` is called with neither map in most tests and in the
    `--once` paths; None must not read as "everything is cooled"."""
    assert admission("g1", "Formalizer", cooldown_until=None,
                     quota_cooldown_kind=None, now=100.0) == ADMIT


def test_the_kind_hold_wins_when_both_apply():
    """Order matters at the call site: the kind verdict DROPS the row
    and the target verdict PUTS IT BACK, so a row under both must take
    the drop — refill re-derives it, and keeping a lease on a parked
    kind would block refill's dedup for the length of the quota hold."""
    assert admission(
        "g1", "Formalizer",
        cooldown_until={("g1", "Formalizer"): 200.0},
        quota_cooldown_kind={"Formalizer": 200.0},
        now=100.0) == DENY_KIND_COOLED


# ─── the properties a later edit would quietly remove ─────────────────

def test_there_is_exactly_one_door() -> None:
    """The predicate governs every dispatch only while `pool.submit`
    has one call site. A second one would silently demote `admission`
    from "the door" to "one of the checkpoints", which is the state it
    was just rescued from — and nothing else in the tree would notice."""
    tree = ast.parse(SRC)
    doors = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == "submit"]
    assert len(doors) == 1, (
        f"dispatch is supposed to have a single spawn site; found "
        f"{len(doors)} at lines {doors}. Route the new one through "
        f"`admission` or this file's guarantee is void.")


def _get_calls_on_cooldown_maps(tree: ast.AST):
    """`<something with 'cooldown' in the name>.get(...)` nodes."""
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"):
            continue
        target = node.func.value
        name = ""
        if isinstance(target, ast.Attribute):
            name = target.attr
        elif isinstance(target, ast.Name):
            name = target.id
        elif isinstance(target, ast.BoolOp):      # `(x or {}).get(...)`
            for v in target.values:
                if isinstance(v, ast.Name):
                    name = v.id
                elif isinstance(v, ast.Attribute):
                    name = v.attr
                if "cooldown" in name:
                    break
        if "cooldown" in name:
            out.append(node)
    return out


def test_the_dispatcher_never_reads_a_cooldown_map_itself() -> None:
    """The duplication was not two functions with the same NAME — it was
    two places doing `map.get(key, 0.0) > now`. So that comparison, not
    a helper name, is what is pinned. With the predicate in its own
    module the assertion gets to be absolute: ZERO such reads in the
    dispatcher, so a third copy has nowhere to hide."""
    outside = _get_calls_on_cooldown_maps(ast.parse(SRC))
    assert not outside, (
        "these read a cooldown map directly instead of asking "
        "`admission`: lines "
        + ", ".join(str(c.lineno) for c in outside))


def test_both_callers_ask_the_predicate() -> None:
    """Deleting a caller's question is as bad as duplicating it — and
    much quieter, since the result is simply more dispatch."""
    tree = ast.parse(SRC)
    askers = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "admission"):
                askers.add(fn.name)
    assert "bfs_refill" in askers, "refill stopped asking the door"
    assert "run" in askers, "the pop loop stopped asking the door"


def test_the_two_refusals_are_not_the_same_string() -> None:
    """They mean different things to the row — drop vs put back — and a
    tidy-up that unified them would resurrect the bug in the form where
    a retry-enqueued row gets deleted and never re-derived."""
    assert DENY_KIND_COOLED != DENY_TARGET_COOLED
    assert ADMIT not in (DENY_KIND_COOLED, DENY_TARGET_COOLED)
    assert not ADMIT, "the admitted verdict must be falsy-empty"


@pytest.mark.parametrize("const,handler", [
    ("DENY_KIND_COOLED", "complete_queue_row"),
    ("DENY_TARGET_COOLED", "deferred_rows.append"),
])
def test_the_pop_loop_still_handles_each_verdict_its_own_way(
    const: str, handler: str,
) -> None:
    """Pins the pairing itself: a row under a kind hold is deleted (the
    kind is parked; refill re-derives), a row under a target back-off is
    unclaimed (this row is still wanted and refill may never have known
    about it)."""
    marker = f"_verdict == {const}"
    assert marker in SRC, f"the pop loop no longer branches on {const}"
    block = SRC.split(marker, 1)[1][:400]
    assert handler in block, (
        f"{const} no longer routes to {handler} — the two refusals "
        f"have started to converge")


def test_the_predicate_agrees_with_a_live_scheduler_state() -> None:
    """End-to-end on the real state object, so a field rename cannot
    leave the predicate reading a map nobody writes any more."""
    st = dispatcher.SchedulerState()
    now = time.time()
    st.cooldown_until[("g9", "Formalizer")] = now + 60
    st.quota_cooldown_kind["Strategist"] = now + 60
    ask = dict(cooldown_until=st.cooldown_until,
               quota_cooldown_kind=st.quota_cooldown_kind, now=now)
    assert admission("g9", "Formalizer", **ask) == DENY_TARGET_COOLED
    assert admission("g9", "Strategist", **ask) == DENY_KIND_COOLED
    assert admission("g8", "Formalizer", **ask) == ADMIT
