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
) -> Literal["proved", "dead", "superseded", "retry"]:
    """Pure framework verify: rewrite parent as alias, then verify the
    strategy patch (which also gates axioms). Returns the terminal
    outcome only — state transitions (mark goal proved / mark strategy
    succeeded / cascade-shelve etc) are the caller's job (see
    `verify_housekeeping`).

    Verify shape: one `verify_file` per level (scratch only) instead
    of the previous two (scratch + parent alias). Rationale:

      * The parent alias file is `def <slug> := @<scratch>.s<id>` —
        a tiny rewrite produced by `promote_to_alias`. Its correctness
        is implied by the scratch theorem's type matching the parent
        goal binders (F52 invariant). Per-level verification of the
        alias was empirically a no-op (F56 doc: 0 failures across 26+
        SG/cantor/proj runs; SG run #19 confirmed).

      * Skipping parent verify omits writeOlean for the parent module.
        That olean would have been needed by the next-level scratch's
        `import <parent-module>`. lake serve handles this by
        elaborating the parent .lean source on demand — the alias is
        tiny so the cost is microseconds, and the scratch olean it
        imports already exists on disk.

      * Axiom check moves from parent (`Problems.<p>.<slug>`) to
        scratch (`Problems.<p>.s<id>`). Both close over the same
        proof — `def slug := @s<id>` is a definitional alias, so
        `#print axioms` walks the same dependency graph either way.
        Checking at scratch level preserves per-strategy attribution
        when a sorryAx leak occurs (the `[verify] axiom_violation
        strategy=<id>` log line still points at the right strategy).

      * Final integrity gate is `library.promote`'s root-level
        `axiom_probe(Root.lean, axioms_for=main_fq)` — that verify
        elaborates the full alias chain in one shot, catches any
        promote_to_alias drift, and applies the manifest whitelist
        at the level where the proof is actually published.

    Rollback semantics unchanged: scratch verify failure (compile or
    axiom) restores the parent file from backup before returning.
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

    # Resolve manifest's axiom whitelist before the verify call.
    # `manifests=None` skips the axiom check — used by tests that
    # don't ship a Manifest.md fixture; production callers
    # (verify_housekeeping) always pass the dispatcher's manifests
    # dict.
    scratch_fq = f"Problems.{s['goal_problem']}.s{strategy_id}"
    axioms_for: str | None = None
    whitelist: list[str] = []
    if manifests is not None:
        mfst = manifests.get(s["goal_problem"]) or manifest.parse(
            workspace / "Problems" / s["goal_problem"] / "Manifest.md"
        )
        whitelist = list(mfst.axioms_whitelist)
        if whitelist:
            axioms_for = scratch_fq

    # Single verify: elaborate the scratch (agent's proof), write its
    # olean for upstream cascade, and run the axiom probe in the same
    # call so sorryAx leaks are attributed to the strategy that
    # introduced them.
    from . import gateway_lifecycle
    v_strategy = gateway_lifecycle.verify_file(
        scratch_abs, write_olean=True, axioms_for=axioms_for,
        workspace=workspace,
    )
    if "error" in v_strategy:
        rollback_promote(parent_abs, parent_backup)
        # Transient infra failure (gateway timeout / unreachable /
        # 5xx after retries) → "retry": leave strategy in
        # ready_for_verify for a later dispatcher tick. Distinguishes
        # from logical errors (4xx / missing target) which still
        # mark the strategy dead.
        transient = bool(v_strategy.get("transient"))
        kind = "transient infra" if transient else "infra"
        print(f"[verify] strategy={strategy_id} {kind} error: "
              f"{v_strategy['error']}", flush=True)
        return "retry" if transient else "dead"
    if not v_strategy.get("ok"):
        rollback_promote(parent_abs, parent_backup)
        return "dead"

    if axioms_for and whitelist:
        if v_strategy.get("axiom_error"):
            rollback_promote(parent_abs, parent_backup)
            print(f"[verify] axiom_violation strategy={strategy_id}: "
                  f"{v_strategy['axiom_error']}", flush=True)
            return "dead"
        used = set(v_strategy.get("axioms") or [])
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
    counts = {"proved": 0, "dead": 0, "superseded": 0, "retry": 0}
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
            if outcome == "retry":
                # Transient gateway failure exhausted in-call retries.
                # Don't mutate state — strategy stays ready_for_verify,
                # next dispatcher tick picks it up. Break out of the
                # housekeeping inner loop so this tick doesn't busy-spin
                # retrying the same strategy (the LSP gateway is likely
                # still under the same load that caused the transient).
                counts["retry"] += 1
                print(f"[verify] Strategy={sid} → retry (transient infra)",
                      flush=True)
                return counts
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
