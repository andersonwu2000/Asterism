"""F56 — strategy verification as dispatcher housekeeping.

Replaces the legacy `worker_kind="Verify"` pipeline. Verifying a
strategy (lake-build the assembled patch, write alias to parent stub,
build parent) is a pure framework operation — no LLM, no sandbox.
Running it as a worker_kind held a pool slot for ~60s per strategy
without proportional benefit. Housekeeping runs it inline on the
dispatcher tick, in a recursive chain when one verify frees another
(parent goal proved → sub-goal of higher strategy → that strategy
becomes ready in the same sweep).

Failure mode: if any lake_build step fails (rare; F52's signature
lock + Backward's sorry-stub pre-build catch most errors at
strategy-commit time), the strategy is marked dead and falls into
the existing cascade machinery (re-open goal → re-Backward). The
prior F41 "LLM repair the strategy patch" path was retired alongside
Verify-as-pipeline since 26 verifies across cantor + proj_nonexpansive
runs showed 0 Step-1 failures — the recovery path was insurance for
an event that does not occur in practice. Re-introduce only if real
runs start showing repeated drift failures.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal

from . import db
from .pipeline._lake import lake_build, lean_path_to_module
from .pipeline._skeleton import promote_to_alias, rollback_promote


def verify_strategy(
    conn: sqlite3.Connection, *, workspace: Path, strategy_id: int,
) -> Literal["proved", "dead", "superseded"]:
    """Pure framework verify: lake build strategy, write alias to
    parent, lake build parent. Returns the terminal outcome only —
    state transitions (mark goal proved / mark strategy succeeded /
    cascade-shelve etc) are the caller's job (see `verify_housekeeping`).
    """
    s = conn.execute(
        "SELECT s.*, g.status AS goal_status, g.slug AS goal_slug,"
        "       g.statement AS goal_statement, g.problem AS goal_problem"
        " FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE s.id = ?",
        (strategy_id,),
    ).fetchone()
    if s is None:
        return "superseded"
    if s["status"] == "superseded" or s["goal_status"] == "proved":
        return "superseded"
    if not s["scratch_path"]:
        return "dead"
    scratch_abs = workspace / s["scratch_path"]
    if not scratch_abs.exists():
        return "dead"

    # Step 1: build the strategy patch against now-real sub-goal proofs.
    ok, _err = lake_build(workspace, scratch_abs)
    if not ok:
        return "dead"

    # Step 2: rewrite parent stub as a `def <slug> := @<ns>.s<id>`
    # alias. Lean copies the type from the strategy theorem at
    # elaboration, so binders + conclusion transfer exactly (F52).
    parent_abs = workspace / s["lean_path"]
    sid_token = f"s{strategy_id}"
    scratch_module = lean_path_to_module(workspace, scratch_abs)
    parent_backup = promote_to_alias(
        parent_abs,
        namespace=f"Problems.{s['goal_problem']}",
        slug=s["goal_slug"],
        sid_token=sid_token,
        scratch_module=scratch_module,
    )

    # Step 3: build the alias-form parent.
    ok, _err = lake_build(workspace, parent_abs)
    if not ok:
        rollback_promote(parent_abs, parent_backup)
        return "dead"

    if parent_backup is not None and parent_backup.exists():
        parent_backup.unlink()
    return "proved"


def verify_housekeeping(
    conn: sqlite3.Connection, *, workspace: Path, max_iters: int = 8,
) -> dict[str, int]:
    """Run inline at the end of each dispatcher tick. Polls strategies
    in `ready_for_verify` state, runs `verify_strategy` on each, and
    applies state transitions (mirrors what the legacy `cascade_one`
    Verify branch did). When a goal becomes proved its parent strategy
    may itself become ready — loops up to `max_iters` chain depth.

    Returns counts: {proved, dead, superseded}. The dispatcher logs
    these for parity with the prior `[cascade] Verify Strategy=N → ...`
    lines.

    Single-threaded by design — running serially within the dispatcher
    main loop sidesteps the OR-parallel race the legacy pipeline path
    fenced via `busy_parents`. Each strategy's full transition commits
    before the next is processed.
    """
    # Local imports break the dispatcher → verify cycle (dispatcher
    # imports verify; we need a couple of dispatcher-side helpers).
    from . import dispatcher, playbook
    counts = {"proved": 0, "dead": 0, "superseded": 0}
    for _ in range(max_iters):
        ready = db.strategies_ready_for_verify(conn)
        if not ready:
            break
        for s in ready:
            sid = int(s["id"])
            goal_id = int(s["goal_id"])
            outcome = verify_strategy(
                conn, workspace=workspace, strategy_id=sid,
            )
            if outcome == "proved":
                db.update_strategy_status(conn, sid, "succeeded")
                db.update_goal_status(conn, goal_id, "proved")
                # Mark sibling strategies superseded — defensive against
                # an OR-race that already left a 'proposed' sibling on
                # this goal alongside the winner.
                db.mark_other_strategies_superseded(
                    conn, goal_id=goal_id, winner_id=sid,
                )
                # F22 playbook idiom capture. Best-effort; LLM call
                # failures must not abort housekeeping.
                try:
                    playbook.maybe_record_idiom(sid, conn, workspace)
                except Exception:  # noqa: BLE001
                    pass
                conn.commit()
                counts["proved"] += 1
                print(f"[verify] Strategy={sid} → proved", flush=True)
            elif outcome == "dead":
                db.update_strategy_status(conn, sid, "dead")
                n = db.increment_goal_attempts(conn, goal_id)
                if n >= dispatcher.SHELVE_THRESHOLD:
                    db.update_goal_status(conn, goal_id, "shelved")
                    dispatcher._propagate_shelve(conn, goal_id)
                else:
                    # Re-open the goal if no live strategy remains, so
                    # bfs_refill can dispatch a fresh Backward attempt.
                    has_live = conn.execute(
                        "SELECT 1 FROM strategies WHERE goal_id = ?"
                        " AND status = 'proposed' LIMIT 1",
                        (goal_id,),
                    ).fetchone()
                    if has_live is None:
                        db.update_goal_status(conn, goal_id, "open")
                conn.commit()
                counts["dead"] += 1
                print(f"[verify] Strategy={sid} → dead", flush=True)
            else:  # "superseded"
                counts["superseded"] += 1
    return counts
