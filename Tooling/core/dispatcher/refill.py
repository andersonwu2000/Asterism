"""BFS queue refill — targets to worker dispatch specs.

Carved move-only from the dispatcher monolith (B4, 2026-08-29); bodies are
verbatim — see git history of core/dispatcher.py for provenance.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import os
import typing as _typing
import shutil
import sqlite3
from dataclasses import dataclass, field
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime
from pathlib import Path

from ... import agent, pipeline
from .. import config, fsutil, gateway_health, network_wait, quota, quota_wait
from ..admission import (ADMIT, DENY_KIND_BACKOFF, DENY_QUOTA,
                         DENY_TARGET_COOLED, admission)
from ..librarian_sched import _lib_decode  # noqa: E402
from ...state import db, thresholds, transitions, tree
from ...state import intent as intent_mod
from ...state import failures as _failures
from ...state import groups as _groups
from ...quality import prune, verify


# ---------------------------------------------------------------------
# BFS queue refill
# ---------------------------------------------------------------------

def _problem_of_target(conn: sqlite3.Connection, target_id: str,
                       target_kind: str) -> str | None:
    """Resolve the Asterism problem name for a dispatch target.
    Forward targets the problem directly (target_kind='Problem',
    target_id=problem name); everything else targets a goal whose
    `problem` column we look up."""
    if target_kind == "Problem":
        # Strip a Librarian per-file suffix (problem\x1ffile); a plain
        # problem (Forward / phase-step Librarian) is returned unchanged.
        return _lib_decode(target_id)[0]
    if target_kind == "Group":
        # v35 — a Strategist row carries a GROUP id. Falling through to
        # the goal lookup below would read it as a goal id and hand back
        # whatever problem THAT goal belongs to, scoping an infra retry
        # to an unrelated problem.
        row = conn.execute("SELECT problem FROM groups WHERE id = ?",
                           (int(target_id),)).fetchone()
        return str(row["problem"]) if row is not None else None
    try:
        g = db.get_goal(conn, int(target_id))
    except (TypeError, ValueError):
        return None
    return g["problem"] if g else None


def env_blocked_kinds() -> "set[str]":
    """Operator hold on dispatch kinds (2026-08-30): `ASTERISM_BLOCKED_KINDS`
    is a comma list of queue kinds (`Formalizer`, `Strategist`,
    `Librarian`, case-insensitive) the daemon must not dispatch — the
    same lever the quota ledger pulls when a seat is out of quota, by
    hand. Lets an experiment run one kind alone on a live tree (a
    routine audit without a formalizer quota burn). Unknown names are
    ignored, so a typo holds nothing rather than everything."""
    from ..quota import DISPATCH_KIND
    raw = os.environ.get("ASTERISM_BLOCKED_KINDS") or ""
    canon = {v.lower(): v for v in DISPATCH_KIND.values()}
    out: "set[str]" = set()
    for tok in raw.split(","):
        k = canon.get(tok.strip().lower())
        if k:
            out.add(k)
    return out


def _verify_problem(workspace: Path, problem: str) -> "bool | None":
    """Lake-build the problem's Defs.lean + Root.lean — whichever exist.
    Present files must type-check cleanly. Phase 6: both files are
    OPTIONAL (pure-NL problems ship neither; Root-only and Defs-only
    are valid shapes), so a missing file is simply skipped and a
    problem with neither passes vacuously. Lazy verification gate: run
    on first dispatch for the problem this daemon run; cached in-memory
    thereafter.

    Why lazy (vs at-startup): wide-scope daemons (e.g. miniF2F=244
    problems) would pay 30-60min upfront. Lazy pays only for problems
    that actually get dispatched (BFS may never touch a problem whose
    parent is dead/shelved). Per-problem ~5-15s amortizes over a long
    run. None = no verdict: the OS memory fence stopped the build for
    lack of room (`BuildOutcome.capped`, 2026-09-02) — not cached, the
    problem is asked again on its next dispatch.
    """
    pdir = db.problem_dir(workspace, problem)
    defs_path = pdir / "Defs.lean"
    root_path = pdir / "Root.lean"
    present = [p for p in (defs_path, root_path) if p.exists()]
    if not present:
        print(f"[verify] {problem}: OK (pure-NL — no Defs/Root)",
              flush=True)
        return True
    from ...pipeline._lake import lake_build_modules, lean_path_to_module
    modules = [lean_path_to_module(workspace, p) for p in present]
    res = lake_build_modules(workspace, modules)
    ok, msg = res
    if getattr(res, "capped", False):
        print(f"[verify] {problem}: no room to build yet — asked again next dispatch", flush=True)
        return None
    if not ok:
        snippet = (msg or "")[:500]
        print(f"[verify] {problem}: FAILED\n{snippet}", flush=True)
    else:
        print(f"[verify] {problem}: OK", flush=True)
    return ok


def _dispatch_is_duplicate(running: "set[tuple]", target_id: str,
                           kind: str, decision_id: int | None) -> bool:
    """Dispatch-time dedup at the single pop-loop chokepoint every source
    funnels through (organic bfs_refill, Strategist Inject, recovery /
    `null_inject_redispatch_specs`). An exact (target, kind, decision_id)
    match is always a duplicate.

    Builder additionally caps at ONE per goal regardless of decision_id:
    it proves IN PLACE, writing the goal's single `proofs/L_<slug>.lean`
    directly (builder.py commit window) — unlike Backward, whose parallel
    OR-node decompositions each write an isolated `_strategy_<sid>.lean`
    and are intentionally allowed to run in parallel (distinct
    decision_id). Two Builders on one goal race that single file: a loser
    that fails *after* the winner committed restores its start-of-run
    sorry-stub snapshot over the winner's proof (`_restore_goal_lean`),
    leaving DB='proved' but file=stub — the Jordan-5/25 drift class, only
    caught end-of-run by axiom_probe. The (target, kind, decision_id) key
    misses this because an organic Builder (decision_id=None) and a
    routine/recovery-injected Builder (decision_id set) are distinct keys;
    collapse Builder to (target, 'Builder') so the second never spawns."""
    if (target_id, kind, decision_id) in running:
        return True
    if kind == "Builder" and any(
            r[0] == target_id and r[1] == "Builder" for r in running):
        return True
    return False


def bfs_refill(conn: sqlite3.Connection,
               running: set[tuple[str, str]],
               cooldown_until: dict[tuple[str, str], float] | None = None,
               *,
               scope: str | None = None,
               kind_backoff: dict[str, float] | None = None,
               blocked_kinds: "set[str] | None" = None,
               verified_problems: dict[str, bool] | None = None,
               ) -> None:
    """Enqueue dispatchable tasks. `running` is the in-memory live set
    of (target_id, kind) pairs currently executing in this daemon.
    Passive trigger: cap = 1 per (target_id, kind) — a goal has at most
    one Builder OR one Backward in flight at a time, and a strategy at
    most one Verify. Daemon crash → set vanishes; pipelines table only
    holds finished rows so restart is clean.

    `cooldown_until` carries (target_id, kind) → epoch seconds until
    which dispatch is suppressed. Pairs whose cooldown is in the future
    are skipped this tick. Set after a spawn_fast_fail cascade so
    transient claude / network failures don't burst-retry at 2s/call.

    The two kind-wide inputs are separate on purpose, and used to be one
    map: quota is provider-level, not target-level — gating one
    (tid, kind) leaves 243 other Backwards free to burn through the cap.

    `blocked_kinds` is the quota ledger's answer for this tick, handed
    in by the caller rather than stored anywhere. `kind_backoff` is the
    rc=126 exponential rate brake, which the dispatcher does own. Both
    suppress a whole kind; only one of them is a fact about the outside
    world, and mixing them is what made the release direction
    unwritable (see `core/admission.py`).

    `scope` (optional SQL LIKE pattern): when set, only enqueue goals
    whose problem matches. Lets a daemon run be restricted to a
    benchmark batch (e.g. `minif2f_%`) without disturbing unrelated
    problems sitting in the same workspace.
    """
    now = time.time()
    cd = cooldown_until or {}
    kb = kind_backoff or {}
    blocked = blocked_kinds or set()

    def in_flight(tid: str, kind: str) -> int:
        # Phase 2.5 — running key is (target_id, kind, decision_id);
        # batch Inject can have multiple entries with same (tid, kind)
        # but distinct decision_id. Sum across all matching entries.
        running_n = sum(1 for r in running if r[0] == tid and r[1] == kind)
        return running_n + db.queue_count(conn, target_id=tid, kind=kind)

    def goal_has_any_pipeline(tid: str) -> bool:
        # 2026-05-28: any queued or running pipeline (of any kind) on
        # the same goal blocks bfs_refill from enqueueing another.
        # Strategist Inject(Backward|Builder) already enqueues a row at
        # commit time; without this guard bfs_refill would still pick
        # up the goal on the next tick and enqueue an organic-routing
        # pipeline of a different kind, racing the Inject (LU lu_step_
        # assembly 2026-05-28 — Strategist Inject(Builder) + bfs_refill
        # parallel Backward).
        #
        # Inject's OR-fanout semantic isn't lost: a Strategist batch can
        # still emit multiple Injects on the same target by emitting
        # them itself; bfs_refill's job is organic routing, and organic
        # routing should defer to whatever Strategist already authored.
        if any(r[0] == tid for r in running):
            return True
        row = conn.execute(
            "SELECT 1 FROM queue WHERE target_id = ? LIMIT 1", (tid,),
        ).fetchone()
        return row is not None

    def admits(tid: str, kind: str) -> str:
        """The shared door predicate — see `admission`. Local copies of
        these two comparisons lived here and in the pop loop until
        2026-08-13, when the pop loop's absence of the per-target half
        let ten fast-fails land in 51 seconds."""
        return admission(tid, kind, cooldown_until=cd, kind_backoff=kb,
                         blocked_kinds=blocked, now=now)

    # Strategies ready for verify are no longer enqueued as Verify
    # pipelines. They're processed inline in `verify_housekeeping` at
    # the end of each tick.

    # Phase 2 — awaiting_human gate: cache per-problem to avoid N+1
    # queries (one per open goal). A problem with an unresolved
    # RequestUserAmend pauses all dispatch on it until operator
    # resolves the strategist_decisions row.
    awaiting_cache: dict[str, bool] = {}

    def problem_paused(problem: str) -> bool:
        if problem not in awaiting_cache:
            # Bench (2026-08-31) rides the same skip: a benched problem
            # takes no dispatch, no state touched.
            awaiting_cache[problem] = (
                db.problem_has_awaiting_human(conn, problem)
                or db.problem_benched(conn, problem))
        return awaiting_cache[problem]

    # Open goals → enqueue if no in-flight or queued attempt exists.
    # Phase 2 — `pending_strategist_review` goals are excluded from
    # `open_goals` (status='open' filter). `goals.detached=1` goals
    # are included via the CTE seed change in db.open_goals.
    vp = verified_problems if verified_problems is not None else {}
    for g in db.open_goals(conn, scope=scope):
        problem = str(g["problem"])
        # Lazy-verify quarantine: a problem whose Defs.lean / Root.lean
        # failed a prior dispatch's verify is skipped here (and at the
        # pop site, defense in depth) so worker spawns don't burn quota
        # on a broken spec. `True` and `unset` both fall through; only
        # explicit `False` triggers the skip.
        if vp.get(problem, True) is False:
            continue
        if problem_paused(problem):
            continue
        gid = str(g["id"])
        # Strategist Inject (or a prior bfs_refill enqueue of any kind)
        # already covers this goal — defer organic routing this tick.
        if goal_has_any_pipeline(gid):
            continue
        # Organic budget guard: an OPEN goal at/over SHELVE_THRESHOLD has
        # no organic budget left (the retry pre-loop would moot it with
        # budget<=0 and leave it open → re-enqueued next tick → hot moot
        # loop; putnam_2025_b6 2026-07-09, 4,317 moot pipelines). Such a
        # goal exists only via non-cascade paths (Inject force-reopen
        # keeps attempts; recovery reopen) — cascade itself routes to
        # review AT the threshold crossing. Send it to the same T2
        # review instead of dispatching: over-threshold means "the
        # Strategist decides", whichever door the goal came through.
        if int(g["attempts"]) >= thresholds.SHELVE_THRESHOLD:
            # One review per attempts value: if the Strategist already
            # answered a review for this goal since its last attempt
            # (e.g. Reopen — keep alive, nothing bfs-visible changes),
            # re-escalating every tick pumps a Strategist wake loop
            # (b6 2026-07-10). The goal holds quietly until an Inject
            # (which bypasses bfs) mints a new attempt.
            if db.goal_reviewed_at_current_attempts(conn, int(g["id"])):
                continue
            print(f"[bfs] g{gid} open with attempts={g['attempts']} >= "
                  f"shelve_threshold={thresholds.SHELVE_THRESHOLD} — "
                  f"routing to strategist review, not dispatch",
                  flush=True)
            transitions._enqueue_strategist_review(conn, int(g["id"]))
            continue
        kind = "Formalizer"
        if admits(gid, kind) != ADMIT:
            continue
        if in_flight(gid, kind) == 0:
            db.enqueue(conn, kind=kind, target_id=gid, priority=2,
                       problem=str(g["problem"]))


