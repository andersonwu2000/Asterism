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

from . import db, manifest
from .pipeline._lake import lean_path_to_module
from .pipeline._skeleton import promote_to_alias, rollback_promote


def verify_strategy(
    conn: sqlite3.Connection, *, workspace: Path, strategy_id: int,
    manifests: dict[str, manifest.Manifest] | None = None,
) -> Literal["proved", "dead", "superseded"]:
    """Pure framework verify: rewrite parent as alias, then build the
    strategy patch + alias parent in one batched lake invocation.
    Returns the terminal outcome only — state transitions (mark goal
    proved / mark strategy succeeded / cascade-shelve etc) are the
    caller's job (see `verify_housekeeping`).

    The promote-then-batch ordering replaces the prior 2-invocation
    approach (build strategy → rewrite alias → build parent). lake's
    internal scheduler resolves the parent-imports-strategy dependency
    and builds in order within one process, halving the lake-startup
    overhead per verify level. Rollback semantics unchanged: any build
    failure restores the parent file from backup and returns 'dead'.
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

    # Promote parent stub to `def <slug> := @<ns>.s<id>` alias. Lean
    # copies the type from the strategy theorem at elaboration, so
    # binders + conclusion transfer exactly (F52). The winning
    # strategy's `proposal_md` is the raw `--` comment block the
    # Backward agent wrote at the top of patch.lean; we prepend it
    # verbatim above the alias for grep + readability. Lean-inert, so
    # the alias build is unaffected.
    parent_abs = workspace / s["lean_path"]
    sid_token = f"s{strategy_id}"
    scratch_module = lean_path_to_module(workspace, scratch_abs)
    annotation = (s["proposal_md"] or "")
    if annotation and not annotation.endswith("\n"):
        annotation += "\n"
    parent_backup = promote_to_alias(
        parent_abs,
        namespace=f"Problems.{s['goal_problem']}",
        slug=s["goal_slug"],
        sid_token=sid_token,
        scratch_module=scratch_module,
        annotation=annotation,
    )

    # Verify-unification: sequential per-file verify through the
    # gateway worker pool. We can't concat (parent imports the strategy
    # module by name; that needs an olean on disk), so we rely on the
    # write_olean side-effect: verify the strategy first → its olean
    # lands at .lake/build/lib/lean/<scratch-module>.olean → parent's
    # `import <scratch-module>` resolves on the next verify_file call.
    # See docs/dev/verify_unification.md §3.
    from . import gateway_lifecycle
    v_strategy = gateway_lifecycle.verify_file(
        scratch_abs, write_olean=True, workspace=workspace,
    )
    if "error" in v_strategy:
        rollback_promote(parent_abs, parent_backup)
        print(f"[verify] strategy={strategy_id} infra error: "
              f"{v_strategy['error']}", flush=True)
        return "dead"
    if not v_strategy.get("ok"):
        rollback_promote(parent_abs, parent_backup)
        return "dead"

    # Now verify the parent file (alias). Its `import <scratch-module>`
    # resolves through the olean we just wrote. Also probes axioms in
    # the same call. `manifests=None` skips the axiom check — used by
    # tests that don't ship a Manifest.md fixture; production callers
    # (verify_housekeeping) always pass the dispatcher's manifests
    # dict.
    fq_name = f"Problems.{s['goal_problem']}.{s['goal_slug']}"
    axioms_for: str | None = None
    whitelist: list[str] = []
    if manifests is not None:
        mfst = manifests.get(s["goal_problem"]) or manifest.parse(
            workspace / "Problems" / s["goal_problem"] / "Manifest.md"
        )
        whitelist = list(mfst.axioms_whitelist)
        if whitelist:
            axioms_for = fq_name

    v_parent = gateway_lifecycle.verify_file(
        parent_abs, write_olean=True, axioms_for=axioms_for,
        workspace=workspace,
    )
    if "error" in v_parent:
        rollback_promote(parent_abs, parent_backup)
        print(f"[verify] strategy={strategy_id} parent infra error: "
              f"{v_parent['error']}", flush=True)
        return "dead"
    if not v_parent.get("ok"):
        rollback_promote(parent_abs, parent_backup)
        return "dead"

    if axioms_for and whitelist:
        if v_parent.get("axiom_error"):
            rollback_promote(parent_abs, parent_backup)
            print(f"[verify] axiom_violation strategy={strategy_id}: "
                  f"{v_parent['axiom_error']}", flush=True)
            return "dead"
        used = set(v_parent.get("axioms") or [])
        rogue = used - set(whitelist)
        if rogue:
            rollback_promote(parent_abs, parent_backup)
            print(f"[verify] axiom_violation strategy={strategy_id}: "
                  f"rogue axioms: {sorted(rogue)}", flush=True)
            return "dead"

    if parent_backup is not None and parent_backup.exists():
        parent_backup.unlink()
    return "proved"


def verify_housekeeping(
    conn: sqlite3.Connection, *, workspace: Path, max_iters: int = 8,
    manifests: dict[str, manifest.Manifest] | None = None,
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
    # Local import breaks the dispatcher → verify cycle (dispatcher
    # imports verify; we need a couple of dispatcher-side helpers).
    from . import dispatcher
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
                manifests=manifests,
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
                # The proved goal's source is annotated with the
                # winning strategy's `proposal_md` (Backward agent's
                # rationale) by `verify_strategy` → `promote_to_alias`.
                # Future agents read it via grep, replacing the prior
                # F22 playbook extract+curate flow.
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
