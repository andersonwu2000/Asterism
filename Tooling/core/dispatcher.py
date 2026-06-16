"""Main dispatcher loop. Cascade in main thread, pipelines in pool.

See architecture.md §7-§8.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path

from .. import agent, pipeline
from . import config
from ..state import db, manifest, tree
from ..quality import prune, verify


# Per-model defaults. Empirically:
#   Sonnet/Opus rarely succeed at attempts ≥3 — 97% of proves happen
#                in ≤3 Builder fails. Use 3/8 — first 3 attempts go to
#                Builder, then Backward retries until attempts hit 8.
#   Haiku       iterates productively across more attempts (its training
#                memory of Mathlib API specifics is thinner; lemma
#                signature lookup + retries lets it converge given enough
#                budget). Use 5/10.
#
# Passive OR=1 means every dead strategy now consumes one goal-attempt
# (added in _propagate_shelve). SHELVE_THRESHOLD was raised (7→8 / 8→10)
# so the goal doesn't shelve before Backward gets enough chances to
# explore alternative strategies.
#
# Semantics:
#   BUILDER_THRESHOLD = N → first N attempts (0..N-1) dispatch Builder,
#                          attempts >= N dispatch Backward.
#   SHELVE_THRESHOLD = M  → goal shelves once attempts hits M.
#
# Resolution chain (see Tooling/config.py): env override
# (ASTERISM_{BUILDER,SHELVE}_THRESHOLD) → Asterism.yaml `dispatch.*`
# → built-in (3, 8) tuned for Sonnet/Opus baseline. Weak-tier models
# (haiku/flash) want roughly (5, 10) — set explicitly in Asterism.yaml.
# Real values resolved in `run()` below per-process.
BUILDER_THRESHOLD = 3
SHELVE_THRESHOLD = 8

# A Librarian chain step (dedup/classify/migrate/bridge) that fails
# after its own internal session-retries is re-enqueued up to this many times
# (the next tick re-derives the same step), then the chain stalls and is left
# for the operator — bounds a genuinely-stuck step from looping forever while
# still surviving a transient gateway/harness failure.
LIBRARIAN_MAX_CHAIN_RETRIES = 2


def _exit_pool_fast(pool: ThreadPoolExecutor) -> None:
    """Shutdown pool from an abort path (budget exceeded / gateway
    permadown / root proved). `pool.shutdown(wait=False)` is not enough
    on its own — when the caller subsequently `return`s from the main
    loop, Python's `concurrent.futures._python_exit` atexit hook joins
    every still-active worker thread regardless of the wait flag, and
    each worker blocks in `proc.wait(timeout=req.timeout_sec)` until
    its claude subprocess hits the per-spawn cap (default 960s). With
    pool_size workers all mid-spawn at abort time, total shutdown wall
    grew to ~16min × pool_size before the bash wrapper saw the daemon
    exit and the harness fired its task-notification (2026-05-27
    Banach-Tarski run: observed ~30min shutdown).

    Fix: kill every in-flight claude subprocess via
    `claude_cli.request_shutdown`. Workers unblock from `proc.wait`,
    return through their normal dead_attempt cleanup paths (per-thread
    DB conns make this concurrent-safe), and on next retry-loop entry
    see the shutdown event and bail with `daemon_shutdown`. Pool joins
    in seconds; atexit cleanup (gateway terminate, pid_lock unlink)
    runs as designed.
    """
    from ..llm import claude_cli
    killed = claude_cli.request_shutdown()
    if killed:
        print(f"[dispatcher] killed {killed} in-flight claude "
              f"subprocess(es) to unblock worker shutdown",
              flush=True)
    pool.shutdown(wait=True, cancel_futures=True)
# Forward retry budget per Inject. Each Inject is a Strategist meta-
# decision; on Forward failure (lake error / parse rejected / dedupe
# blocked) the agent --resume's next attempt sees the failure as
# retry_context and can correct (e.g. missing `import` observed SG run
# 2026-05-17: agent referenced `Collinear` without importing Defs).
# Kept small (mirrors BUILDER_THRESHOLD) because Forward is a single
# lemma write — diminishing returns past 3 retries.
FORWARD_RETRY_BUDGET = 3

TICK_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------
# Startup recovery
# ---------------------------------------------------------------------

# Recovery moved to Tooling/recovery.py. Re-exported here for
# back-compat with existing test imports (`dispatcher._recover_at_startup`,
# `dispatcher._sweep_lean_backups`).
from ..state.recovery import recover_at_startup as _recover_at_startup  # noqa: E402,F401
from ..state.recovery import sweep_lean_backups as _sweep_lean_backups  # noqa: E402,F401


# ---------------------------------------------------------------------
# Phase 2 — pending_strategist_review + reopen_with_detach (used by
# cascade_one Rule 1 and the Strategist pipeline for ConfirmShelve /
# Reopen commits). Downward shelve cascade was removed once shelved
# became reopenable: BFS already skips dead-chain descendants via
# `db.open_goals`'s alive seed, and Strategist's context view filters
# them too, so flipping descendant status added no behavior and
# blocked Reopen flow on the parent (cascade-shelved children stay
# `shelved` and BFS's `status='open'` filter excludes them even after
# a sibling/parent strategy revives the chain).
# ---------------------------------------------------------------------

def _cascade_shelve_descendants(
    conn: sqlite3.Connection, goal_id: int,
) -> int:
    """When `goal_id` flips to a non-recoverable status (`shelved` /
    `disproved`), walk its strategy_subgoals chain downward and mark
    every still-active descendant `shelved`.

    Why all descendants become `shelved` (never `disproved`): a
    descendant inherits inactivity from its ancestor, but it was not
    independently judged with a counterexample. Keeping descendants
    Reopenable preserves the semantics of `disproved` as "this exact
    statement has been shown false" rather than diluting it to
    "anything downstream of a false statement".

    The walk skips:
      - already-terminal descendants (`proved` / `shelved` /
        `disproved`): don't overwrite settled state.
      - `pending_strategist_review` descendants: Strategist will
        decide their fate. Cascading would race.

    Recursive in spirit but iterated with a frontier list to avoid
    Python stack limits on deep proof trees. Idempotent — re-running
    on the same root is a no-op once everything that can transition
    has transitioned.

    Returns the number of descendants transitioned (for forensics /
    test assertions).

    Note: terminology in the codebase reserves the literal status
    string `shelved` regardless of how the goal got there
    (ConfirmShelve, parent_needs_fix, descendant cascade, threshold
    exhaustion). There is no separate `cascade_shelved` state."""
    # DAG-aware guard: spare any descendant that still has an INDEPENDENT
    # live path to root (one that does NOT run through `goal_id`) — a
    # cross-branch cited / auto-linked sibling. Without this, the dying
    # branch would also shelve a goal another live strategy still needs,
    # leaving it un-dispatchable (status='shelved' ∉ open_goals) and that
    # strategy hung. Computed once: saving paths are external to
    # `goal_id`'s subtree, so this cascade never mutates them — the set
    # stays valid throughout. Maintains the invariant `open ⇒ reachable`.
    grow = conn.execute(
        "SELECT problem FROM goals WHERE id = ?", (goal_id,),
    ).fetchone()
    saved = (
        db.goals_reachable_excluding(
            conn, problem=str(grow["problem"]), exclude_goal_id=goal_id)
        if grow is not None else set()
    )
    transitioned = 0
    frontier = [goal_id]
    seen: set[int] = set()
    while frontier:
        next_frontier: list[int] = []
        for gid in frontier:
            if gid in seen:
                continue
            seen.add(gid)
            for r in conn.execute(
                "SELECT g.id, g.status FROM strategies s"
                " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                " JOIN goals g ON g.id = ss.subgoal_id"
                " WHERE s.goal_id = ?",
                (gid,),
            ).fetchall():
                sub_id = int(r["id"])
                sub_status = str(r["status"])
                if sub_id in saved:
                    # Independent live path exists — not orphaned by this
                    # death. Leave it (and its subtree, alive via that
                    # same path) untouched.
                    continue
                if sub_status in ("proved", "shelved", "disproved", "dead",
                                  "pending_strategist_review"):
                    # Walk past proved descendants (their own subtrees
                    # may still contain active goals worth cascading).
                    if sub_status == "proved":
                        next_frontier.append(sub_id)
                    continue
                db.update_goal_status(conn, sub_id, "shelved")
                # Symmetric with `_propagate_shelve`: a cascade-shelved
                # descendant must also stop its own proposed strategies
                # from trying to prove it. Without this, status='shelved'
                # disagrees with the strategy table (proposed strategies
                # still mapped to the just-shelved goal), the alive-DAG
                # CTE keeps walking through them as if alive, and the
                # subtree leaks "active" status into TREE.md / Strategist
                # context. Inward-killing here keeps cascade's effect
                # identical to "direct shelve of every transitioned
                # descendant".
                _inward_kill_strategies(conn, sub_id)
                transitioned += 1
                next_frontier.append(sub_id)
        frontier = next_frontier
    return transitioned


def _set_goal_terminal_and_propagate(
    conn: sqlite3.Connection, goal_id: int, status: str,
) -> None:
    """Flip a goal to a terminal status and:

      1. If the goal was Inject-produced (Forward output of a
         Strategist Inject decision), fill the originating decision's
         `outcome` column and fire `inject_batch_done` when its
         batch is fully terminal.
      2. For non-recoverable terminals (`shelved` / `disproved` /
         `dead`), cascade `shelved` to every still-active descendant
         via `_cascade_shelve_descendants`. Display and Strategist
         context view then converge on the same source of truth.

    Centralises the sequence (`update_goal_status` →
    `propagate_inject_outcome_from_goal` →
    `_maybe_enqueue_inject_batch_done` → optional descendant
    cascade) so every terminal flip site applies them uniformly.

    `status` ∈ {'proved','shelved','disproved','dead'}.

    Instrument: every terminal flip prints a caller-trace line so we
    can attribute unexpected shelves (polar 2026-05-23: `square_root_
    of_positive` shelved at attempts=5 < SHELVE_THRESHOLD=8 via a
    path none of the documented cascade rules explain). The 1-line
    trace pulls the immediate caller's filename+line+function from
    the Python stack — enough to disambiguate the cascade entry
    point on next reproduction.

    Guard (BT 2026-05-29 g3380): never DOWNGRADE a goal that is already
    a hard terminal (`proved` / `disproved` / `dead`) to `shelved`.
    `proved` is a completed proof — shelving it regresses a true theorem
    and breaks the invariant `proved ⟺ some strategy's subs all proved`;
    `disproved`/`dead` are stronger negative terminals than `shelved`.
    The observed trigger was a Strategist ConfirmShelve on a proved-but-
    superseded orphan goal (it had no clean "retire orphan" verb so it
    misused ConfirmShelve). The ConfirmShelve commit path also no-ops
    this case at the decision layer; this is the class-level backstop so
    ANY caller is blocked, not just ConfirmShelve. Idempotent re-flips to
    the same status, and legitimate upgrades to `proved`, still pass."""
    if status == "shelved":
        cur = conn.execute(
            "SELECT status FROM goals WHERE id = ?", (goal_id,),
        ).fetchone()
        if cur is not None and str(cur["status"]) in (
            "proved", "disproved", "dead",
        ):
            print(f"[goal-terminal] g{goal_id} shelve SKIPPED — already "
                  f"{cur['status']!r} (no downgrade of a terminal goal)",
                  flush=True)
            return
    if status in ("shelved", "disproved", "dead"):
        import traceback as _tb
        frames = _tb.extract_stack()[-4:-1]
        caller = ""
        if frames:
            f = frames[-1]
            fname = f.filename.replace("\\", "/").rsplit("/", 1)[-1]
            caller = f"{fname}:{f.lineno}({f.name})"
        try:
            row = conn.execute(
                "SELECT slug, attempts FROM goals WHERE id = ?",
                (goal_id,),
            ).fetchone()
            slug = row["slug"] if row else "?"
            n = int(row["attempts"]) if row else -1
        except sqlite3.OperationalError:
            slug, n = "?", -1
        print(f"[goal-terminal] g{goal_id} ({slug}) → {status} "
              f"attempts={n} caller={caller}",
              flush=True)
    db.update_goal_status(conn, goal_id, status)
    d = db.propagate_inject_outcome_from_goal(conn, goal_id)
    if d is not None:
        _maybe_enqueue_inject_batch_done(conn, d)
    if status in ("shelved", "disproved", "dead"):
        _cascade_shelve_descendants(conn, goal_id)


def _record_inject_decision_outcome(conn: sqlite3.Connection,
                                    decision_id: int,
                                    outcome: str,
                                    failure_reason: str,
                                    detail: str | None = None) -> None:
    """Write the Forward pipeline's terminal outcome back into the
    strategist_decisions row that emitted it.

    Solo + batch Inject both go through this; the row's `outcome` was
    NULL post-commit and gets filled here so failure_replay (Strategist
    self-feedback) shows 'my Inject succeeded / failed because X'.
    `failure_reason` joins outcome via ':' for compactness.

    `detail` (#4): the pipeline's rich `failure_detail` — for a Forward
    decline it carries the agent's `## Why` reasoning. Stored in the
    separate `outcome_detail` column (the coarse `outcome` enum stays
    intact for reconcile / NULL-checks) so the Strategist's next wake
    reads WHY its brief was declined, not just `failed:agent_declined`.
    """
    text = outcome if not failure_reason else f"{outcome}:{failure_reason}"
    # COALESCE: a pipeline may have already stashed `outcome_detail` while
    # `outcome` was NULL (e.g. forward.run_forward writes a decline's
    # `## Why` — see db.set_inject_decision_outcome_detail). Passing
    # detail=None here must NOT wipe that; only override when this call
    # carries its own detail.
    conn.execute(
        "UPDATE strategist_decisions"
        " SET outcome = ?, outcome_detail = COALESCE(?, outcome_detail),"
        "     updated_at = ?"
        " WHERE id = ? AND outcome IS NULL",
        (text, (detail or None), db.now(), decision_id),
    )
    conn.commit()


# Re-export of the helper that now lives in db.py — kept under the
# pre-existing private name so callers and tests referencing it
# continue to work. New code should call db.maybe_enqueue_inject_
# batch_done directly.
_maybe_enqueue_inject_batch_done = db.maybe_enqueue_inject_batch_done


def _enqueue_strategist_review(conn: sqlite3.Connection,
                               goal_id: int) -> None:
    """Phase 2 Rule 1 — agent_shelved branch.

    Set the goal to `pending_strategist_review` (transitional, not
    terminal) and enqueue a Strategist run on this problem's root.
    Strategist later commits one of ConfirmShelve / Reopen / Inject;
    until then the upward strategy chain stays alive.

    Idempotent on duplicate Strategist enqueue: if the queue already
    has a Strategist row for this problem's root, skip the second
    enqueue (per-problem in-flight dedup; see pipelines.md §4.3).
    """
    g = db.get_goal(conn, goal_id)
    if g is None:
        return
    # Orphan-chain guard: if any ancestor strategy is dead / superseded
    # by the time this worker returns, the goal has no live path back to
    # root and Strategist cannot do anything useful with it. Shelve in
    # place and skip the wasted spawn. Observed residue_thm 2026-05-19:
    # Backward on g2107 finished agent_shelved after g2107's grandparent
    # strategy s10285 already died; Strategist still got enqueued, used
    # one full cycle, and committed ConfirmShelve — pure overhead.
    #
    # Skip the guard when the goal is `detached`: Strategist explicitly
    # authorised standalone dispatch (via Reopen + auto-detach or
    # Inject(Backward) + auto-detach), so even if upward strategies are
    # dead, this dispatch is intentional and pending_review still has
    # signal value.
    if not bool(g["detached"]) and _has_dead_strategy_in_chain(conn, goal_id):
        _set_goal_terminal_and_propagate(conn, goal_id, "shelved")
        _propagate_shelve(conn, goal_id)
        return
    # Status transition: pending_strategist_review (not 'shelved').
    # update_goal_status() flips integrity_verified=0 for any
    # non-'proved' transition; we want that for stability since the
    # goal may later be Reopen'd.
    db.update_goal_status(conn, goal_id, "pending_strategist_review")

    # Find this problem's root goal — Strategist queue target.
    root_row = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND origin = 'root'",
        (g["problem"],),
    ).fetchone()
    if root_row is None:
        return
    root_id = str(root_row["id"])

    # Per-problem in-flight dedup: skip if a Strategist row already sits
    # in the queue for this problem's root. dispatcher's main-loop
    # in-memory `running` set covers active dispatches; this DB check
    # covers queue-pending entries.
    if db.is_in_queue(conn, target_id=root_id, kind="Strategist"):
        return
    # Priority 20 — above T0/T1 (=10) per pipelines.md §2.1 "T2 > T0 > T1".
    # T2 is event-driven (an agent shelved, review needed); T0/T1 are
    # routine. Without an explicit priority kwarg the default 0 would put
    # T2 below Backward (=2) and Builder (=5), inverting the spec.
    db.enqueue(conn, kind="Strategist", target_id=root_id,
               target_kind="Goal", priority=20)


def _has_hard_terminal_ancestor(conn: sqlite3.Connection,
                                goal_id: int) -> tuple[bool, str | None]:
    """Phase 6 — Reopen safety walk.

    Return `(found, status)` where `found` is True iff any ancestor
    goal in the strategy_subgoals chain has a HARD terminal status
    (`disproved` or `dead`); `status` is which one if any.

    Both hard terminals block Reopen on descendants:
      - `disproved`: counterexample; descendant's statement depends on
        a false hypothesis context — proving it is meaningless.
      - `dead`: parent strategy was wrong; descendant was created for
        that wrong context. Auto-detach can still salvage independently
        useful lemmas, but the path through this descendant back to
        root is permanently severed.

    `shelved` ancestors do NOT count (soft terminal; auto-detach
    handles broken upward chains so the descendant can run standalone
    and may even be revived once the ancestor reopens).

    Walks UPWARD via strategy_subgoals.subgoal_id = goal_id → parent
    strategy → strategy.goal_id, recursively.
    """
    visited: set[int] = set()
    frontier: list[int] = [goal_id]
    while frontier:
        next_frontier: list[int] = []
        for gid in frontier:
            rows = conn.execute(
                "SELECT s.goal_id FROM strategies s"
                " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                " WHERE ss.subgoal_id = ?",
                (gid,),
            ).fetchall()
            for r in rows:
                parent_id = int(r["goal_id"])
                if parent_id in visited:
                    continue
                visited.add(parent_id)
                grow = conn.execute(
                    "SELECT status FROM goals WHERE id = ?",
                    (parent_id,),
                ).fetchone()
                if grow is None:
                    continue
                if grow["status"] in ("disproved", "dead"):
                    return True, str(grow["status"])
                next_frontier.append(parent_id)
        frontier = next_frontier
    return False, None


def _has_terminal_disproved_ancestor(conn: sqlite3.Connection,
                                     goal_id: int) -> bool:
    """Legacy alias — Phase 6 broadened the safety walk to include
    `dead`. New code should call `_has_hard_terminal_ancestor` directly
    for the more informative return shape."""
    found, _ = _has_hard_terminal_ancestor(conn, goal_id)
    return found


def _has_dead_strategy_in_chain(conn: sqlite3.Connection,
                                goal_id: int) -> bool:
    """Phase 2 Rule 3 — auto-detach trigger detection.

    Return True iff any ancestor strategy in the upward chain has
    status ∈ {'dead', 'superseded'}. If so, Reopen sets `goals.detached
    = 1` so BFS dispatches on the goal standalone (no live parent
    strategy needed to thread the proof back to root).
    """
    visited: set[int] = set()
    frontier: list[int] = [goal_id]
    while frontier:
        next_frontier: list[int] = []
        for gid in frontier:
            rows = conn.execute(
                "SELECT s.id, s.goal_id, s.status FROM strategies s"
                " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                " WHERE ss.subgoal_id = ?",
                (gid,),
            ).fetchall()
            for r in rows:
                if r["status"] in ("dead", "superseded"):
                    return True
                parent_id = int(r["goal_id"])
                if parent_id in visited:
                    continue
                visited.add(parent_id)
                next_frontier.append(parent_id)
        frontier = next_frontier
    return False


def _inward_kill_strategies(conn: sqlite3.Connection,
                            goal_id: int) -> None:
    """Mark every 'proposed' strategy whose `goal_id` equals this goal
    as 'dead'. Shared by `_propagate_shelve` (direct shelve of one
    goal) and `_cascade_shelve_descendants` (sweep of a subtree
    rooted at a just-terminated ancestor).

    Iterates per-row through `update_strategy_status` so the
    inject-outcome propagation hook fires for each strategy a
    Strategist Inject decision had spawned. A bulk UPDATE silently
    bypasses the hook and leaves those decisions un-resolved,
    preventing inject_batch_done from firing.
    """
    sids = [int(r["id"]) for r in conn.execute(
        "SELECT id FROM strategies"
        " WHERE goal_id = ? AND status = 'proposed'",
        (goal_id,),
    ).fetchall()]
    for sid in sids:
        db.update_strategy_status(conn, sid, "dead")


def _maybe_stall_parent_strategies(conn: sqlite3.Connection,
                                   goal_id: int) -> None:
    """Soft-shelve UPWARD transition — the reopenable counterpart of
    `_kill_upward_chain` (which is hard-terminal only).

    When `goal_id` soft-shelves, any 'proposed' parent strategy (one that
    USES it as a sub-goal) whose sub-goals have now ALL settled — zero
    alive, >=1 soft-shelved, and NO hard-terminal (disproved/dead)
    sibling — is PARKED as 'stalled' instead of left 'proposed'.

    Why a distinct status (Phase 11): a 'proposed' strategy with no alive
    sub-goals is the overloaded state that wedged the producing
    Inject(Backward)'s outcome at NULL — root injects never self-terminate
    (`produced_goal_id`=root) and a soft-shelved sub-goal kept the strategy
    'proposed' — so the in-flight-batch clause suppressed T4 forever
    (the reconcile band-aid filled it out-of-band, then over-woke the
    Strategist). 'stalled' fills that outcome via the normal propagation
    (lifting T4 suppression) WITHOUT an unconditional wake, and stays
    reopenable: `_commit_inject_redispatch`'s force-reopen flips it back
    to 'proposed'.

    Skipped cases (left for other paths):
      - a hard-terminal (disproved/dead) sibling → `_kill_upward_chain`
        marks the parent 'dead' (not reopenable);
      - all sub-goals proved → 'succeeded' (handled at proof time);
      - any alive sibling → genuinely in flight, stays 'proposed'.
    """
    parents = conn.execute(
        "SELECT s.id FROM strategies s"
        " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        " WHERE ss.subgoal_id = ? AND s.status = 'proposed'",
        (goal_id,),
    ).fetchall()
    for p in parents:
        sid = int(p["id"])
        comp = {str(r["st"]): int(r["n"]) for r in conn.execute(
            "SELECT g.status AS st, COUNT(*) AS n FROM strategy_subgoals ss"
            " JOIN goals g ON g.id = ss.subgoal_id"
            " WHERE ss.strategy_id = ? GROUP BY g.status",
            (sid,),
        ).fetchall()}
        total = sum(comp.values())
        alive = (comp.get("open", 0) + comp.get("attempting", 0)
                 + comp.get("pending_strategist_review", 0))
        if (total > 0 and alive == 0 and comp.get("shelved", 0) >= 1
                and comp.get("disproved", 0) == 0
                and comp.get("dead", 0) == 0):
            db.update_strategy_status(conn, sid, "stalled")


def _propagate_shelve(conn: sqlite3.Connection, goal_id: int) -> None:
    """Inward strategy kill for a goal that just hit a terminal status.

    Phase 6: caller is responsible for the (separate) upward strategy
    kill if the terminal status warrants it (disproved / dead, via
    `_kill_upward_chain`). `shelved` is soft-terminal: parent strategies
    are not KILLED, but a parent whose sub-goals have all settled is
    PARKED as 'stalled' (reopenable) via `_maybe_stall_parent_strategies`
    so the producing Inject's outcome resolves and T4 sees the collapse.

    The strategies this function kills (status='proposed' AND
    goal_id == the terminal goal) are the ones trying to PROVE the
    just-terminated goal. Their sub-goals (this goal's grandchildren)
    become orphans of the alive-strategy DAG; `db.open_goals` filters
    them out and Strategist's view section converges on the same
    invariant.
    """
    _inward_kill_strategies(conn, goal_id)
    _maybe_stall_parent_strategies(conn, goal_id)


def _kill_upward_chain(conn: sqlite3.Connection, goal_id: int,
                       *, parent_terminal_status: str) -> None:
    """Phase 6 — kill the strategies USING this goal as a sub-goal,
    then cascade to their parent goals.

    Called only for hard terminals (`disproved` / `dead`). Soft
    `shelved` deliberately leaves the upward chain alive so a future
    Reopen can revive it.

    `parent_terminal_status` ∈ {'shelved', 'dead'} — what to flip an
    exhausted parent goal to when its attempts counter hits
    SHELVE_THRESHOLD via this cascade. Disproved subgoals exhaust
    their parents as 'shelved' (the parent could in principle try a
    different decomposition); dead subgoals exhaust their parents as
    'dead' (the whole subtree is in the wrong context).
    """
    parent_strategies = conn.execute(
        "SELECT s.id, s.goal_id FROM strategies s "
        "JOIN strategy_subgoals ss ON ss.strategy_id = s.id "
        "WHERE ss.subgoal_id = ? AND s.status = 'proposed'",
        (goal_id,),
    ).fetchall()

    for s in parent_strategies:
        sid = int(s["id"])
        db.update_strategy_status(conn, sid, "dead")
        # Sibling-orphan sweep: every OTHER subgoal of this just-killed
        # strategy is now an orphan — the strategy whose AND-chain held
        # them together is dead, but the sibling's own status is
        # untouched. Without this sweep the sibling stays `open` /
        # `attempting` / `pending_strategist_review` in the DB while
        # `open_goals`'s CTE filters them out (they're no longer
        # reachable from the alive seed); status disagrees with
        # dispatchability, misleading TREE.md / Strategist context.
        # Soft-shelve siblings (and their downward subtrees via
        # `_set_goal_terminal_and_propagate`) so status converges on
        # the dispatchability invariant. `_propagate_shelve` inward-
        # kills the sibling's own strategies (otherwise they linger
        # 'proposed' on a now-shelved goal). Skip already-terminal
        # siblings (proved is the most common — sub-AND chain partially
        # done before its peer died).
        for sib in conn.execute(
            "SELECT g.id, g.status FROM strategy_subgoals ss"
            " JOIN goals g ON g.id = ss.subgoal_id"
            " WHERE ss.strategy_id = ? AND ss.subgoal_id != ?",
            (sid, goal_id),
        ).fetchall():
            sib_id = int(sib["id"])
            sib_status = str(sib["status"])
            if sib_status in ("open", "attempting",
                              "pending_strategist_review"):
                _set_goal_terminal_and_propagate(conn, sib_id, "shelved")
                _propagate_shelve(conn, sib_id)

    # For each affected parent goal: increment attempts unconditionally.
    # Every cascade reaching this branch is rooted in a strong signal
    # (agent_infeasible / parent_needs_fix) — a descendant actively
    # repudiated the decomposition represented by the just-killed
    # strategy. That repudiation counts as a failed attempt at the
    # parent goal even when sibling strategies remain alive; otherwise
    # SHELVE_THRESHOLD never fires on goals whose strategies keep dying
    # around a stuck-but-still-'proposed' sibling (e.g. an AND-chain
    # with a shelved hole), leaving the goal permanently 'attempting'
    # with no automatic intervention path.
    #
    # Terminal-cascade firing is gated on no-live-sibling: when a
    # sibling strategy is still alive we defer the shelve so we don't
    # cut down a parallel-inject worker mid-flight (the Strategist
    # fan-out case). Attempts accumulate past threshold; when the last
    # sibling itself enters this branch (its own cascade) has_live
    # becomes False and the deferred terminal fires then.
    affected_parent_goals = {int(s["goal_id"]) for s in parent_strategies}
    for gid in affected_parent_goals:
        row = conn.execute(
            "SELECT status FROM goals WHERE id = ?", (gid,),
        ).fetchone()
        if not row or row["status"] != "attempting":
            continue
        n = db.increment_goal_attempts(conn, gid)
        has_live = conn.execute(
            "SELECT 1 FROM strategies WHERE goal_id = ?"
            " AND status = 'proposed' LIMIT 1",
            (gid,),
        ).fetchone()
        if has_live is not None:
            # Sibling still in-flight: count the failure but defer the
            # shelve/reopen decision until the sibling resolves.
            continue
        if n >= SHELVE_THRESHOLD:
            if parent_terminal_status == "dead":
                # Hard terminal (`dead` = structurally wrong subtree):
                # keep direct dead-shelve + upward kill. Not Strategist-
                # actionable.
                _set_goal_terminal_and_propagate(
                    conn, gid, parent_terminal_status)
                _propagate_shelve(conn, gid)
                _kill_upward_chain(
                    conn, gid,
                    parent_terminal_status=parent_terminal_status)
            else:
                # Soft terminal (`shelved` cascade from disproved sub):
                # exhaustion is Strategist's call. Route through
                # pending_strategist_review so Strategist sees the
                # exhausted parent and decides ConfirmShelve / Reopen /
                # Inject. Mirrors the agent_shelved path.
                _enqueue_strategist_review(conn, gid)
        else:
            db.update_goal_status(conn, gid, "open")


def _reconcile_goal_after_strategy_loss(
    conn: sqlite3.Connection, goal_id: int,
) -> None:
    """Reopen / shelve an 'attempting' goal that just lost a strategy
    via a non-cascade path (worker-Exception placeholder deletion in
    backward.py's BaseException handler). Without this, that goal can
    sit 'attempting' with no live strategy until the next daemon
    restart's recovery sweep notices: bfs_refill filters open_goals
    on status='open' so nothing picks it back up, and no cascade
    fires to update status.

    Mirrors `_kill_upward_chain`'s no-sibling branch: if attempts have
    accumulated past SHELVE_THRESHOLD via earlier deferred cascades,
    terminate; otherwise reopen for a fresh Backward attempt. No-op if
    the goal still has any live strategy or is not 'attempting'."""
    row = conn.execute(
        "SELECT status, attempts FROM goals WHERE id = ?", (goal_id,),
    ).fetchone()
    if not row or row["status"] != "attempting":
        return
    has_live = conn.execute(
        "SELECT 1 FROM strategies WHERE goal_id = ?"
        " AND status = 'proposed' LIMIT 1",
        (goal_id,),
    ).fetchone()
    if has_live is not None:
        return
    n = int(row["attempts"])
    if n >= SHELVE_THRESHOLD:
        _enqueue_strategist_review(conn, goal_id)
    else:
        db.update_goal_status(conn, goal_id, "open")


def _propagate_disproved(conn: sqlite3.Connection, goal_id: int) -> None:
    """Composite: inward strategy kill + upward strategy chain kill
    for a disproved goal (counterexample-based hard terminal)."""
    _propagate_shelve(conn, goal_id)
    _kill_upward_chain(conn, goal_id, parent_terminal_status="shelved")


def _propagate_dead(conn: sqlite3.Connection, goal_id: int) -> None:
    """Composite: inward strategy kill + upward strategy chain kill
    for a dead goal (parent_needs_fix; parent strategy was wrong).
    Exhausted parents cascade-die rather than cascade-shelve because
    the entire subtree was in the wrong context."""
    _propagate_shelve(conn, goal_id)
    _kill_upward_chain(conn, goal_id, parent_terminal_status="dead")


def next_worker_kind(goal: sqlite3.Row) -> str:
    """Pure-ish: input goal row → 'Builder' or 'Backward'.

    Routing is `entry_kind`-driven with an attempts-threshold safety net.
    While attempts < `BUILDER_THRESHOLD` we honor the `entry_kind`
    directive (`'Builder'` | `'Backward'`); once attempts reach the
    threshold, escalation to Backward is forced (safety net for an
    entry_kind=Builder directive that turns out wrong).

    `entry_kind` is set by:
      - cli init for the root goal: hardcoded to `'Backward'`. Root
        entry is gated by Strategist's `first_launch` trigger before
        any Builder/Backward dispatch; the `## Entry kind` Manifest
        section was dropped in Phase 2 (see manifest.py module header).
      - Backward agent for each sub-goal it generates, via the
        `-- entry_kind: ...` directive in `new_<slug>.lean`'s docstring;
        framework parses + persists at sub-goal insertion time.

    Earlier iterations gated on a numeric `difficulty` (1-10): a hard
    `>=4 → Backward` rule was unreliable because the agent's estimate
    tracked conceptual complexity, not Builder-tractability. The boolean
    directive is now the only routing signal — `difficulty` was removed
    from both Manifest and the goals table.

    `BUILDER_THRESHOLD` is module-level so test/env overrides are visible
    without re-importing.
    """
    if int(goal["attempts"]) >= BUILDER_THRESHOLD:
        return "Backward"
    if str(goal["entry_kind"]) == "Backward":
        return "Backward"
    return "Builder"


# ---------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------

# Cascade reads `failure_reason` directly from PipelineResult passed in;
# helpers that round-tripped through dead_attempts (`_latest_failure_reason`
# / `_is_*`) were removed — the reason is already in scope, no DB query
# needed. spawn_fast_fail rows are no longer written to dead_attempts at
# all (they were noise: never projected as event, only read by these
# helpers); the reason is a transient signal carried through the future
# result tuple.


def _classify_worker_exception(exc: BaseException) -> str:
    """Map an uncaught worker-thread exception to a framework
    failure_reason. Returns `"gateway_unreachable"` for transport-level
    errors (urllib URLError, socket OSError with conn refused / reset /
    network-name-deleted), `""` otherwise so the default path applies
    (synthesize generic "failed" outcome → attempts++).

    Background — SG run #14 (2026-05-11) had a gateway IOCP-accept
    crash mid-run. After the crash, every Backward dispatch raised
    `urlopen error [WinError 10061]` (connection refused) from the
    daemon's own HTTP POST to the gateway. The legacy worker-exception
    branch wrote outcome=failed with no failure_reason → counted as
    a real attempt against the goal. Five infra refusals later, the
    root goal shelved at SHELVE_THRESHOLD. This classifier returns the
    transport reason so cascade_one routes through the existing
    _INFRA_REASONS short-circuit (no attempts++) AND the dispatcher
    main loop applies a 30s cooldown before re-dispatching to the
    same (target, kind) — giving the gateway time to recover (when
    accompanied by gateway-side fixes like 475c318) or letting the
    operator notice & restart.
    """
    import errno
    import urllib.error

    if isinstance(exc, urllib.error.URLError):
        return "gateway_unreachable"
    if isinstance(exc, OSError):
        # Cross-platform errno values for transport-level loss
        conn_errnos = {errno.ECONNREFUSED, errno.ECONNRESET,
                       errno.ENETUNREACH, errno.EHOSTUNREACH,
                       errno.ETIMEDOUT}
        if exc.errno in conn_errnos:
            return "gateway_unreachable"
        # Windows wraps these as WinError codes (winerror attr) often
        # without setting errno. winerror 10061=ECONNREFUSED-equiv,
        # 10054=ECONNRESET-equiv, 64=NETNAME_DELETED (peer aborted).
        winerror = getattr(exc, "winerror", None)
        if winerror in (10061, 10054, 10060, 10065, 64):
            return "gateway_unreachable"
    # Pipeline-side LSP RPC timeouts (lsp_client.py raises TimeoutError
    # when an `$/lean/rpc/call` doesn't complete within budget).
    # Distinct from gateway_unreachable: gateway IS reachable but
    # contended (e.g. miniF2F pilot's 5 simultaneous Builders vs 3
    # worker slots → 2 spawns time out waiting for slot acquire).
    # Same infra semantics (cooldown + retry, no attempts++), but
    # MUST NOT contribute to the gateway-death circuit breaker —
    # under healthy concurrency, transient_timeouts cluster and
    # would prematurely kill the daemon if treated as gateway death.
    if isinstance(exc, TimeoutError):
        return "transient_timeout"
    # Fallback string scan for wrapped/chained exceptions whose outer
    # type didn't match either isinstance branch above.
    msg = repr(exc)
    if any(s in msg for s in ("WinError 10061", "WinError 10054",
                              "WinError 64",
                              "Connection refused",
                              "Connection reset",
                              "gateway unreachable")):
        return "gateway_unreachable"
    return ""


def cascade_one(conn: sqlite3.Connection, *, pipeline_id: str,
                kind: str, target_id: str, target_kind: str,
                outcome: str, failure_reason: str = "",
                decision_id: int | None = None) -> None:
    """Apply state transitions for one finished pipeline.

    Each worker_kind has a fixed target_kind:
      Builder  → Goal   (fresh sorry-stub closure)
      Backward → Goal   (decompose into sub-goals)

    Strategy verification is no longer a worker_kind. The framework-side
    verify happens inline in the dispatcher tick via
    `verify.verify_housekeeping`, not here.

    No-op entry: if the target's underlying goal is already proved or
    its strategy is already 'superseded', skip the transition. This
    catches loser strategies / orphan sub-goals whose workers finish
    after the goal has been won by a (possibly sequential) sibling
    strategy or after the goal cascade-shelved.
    """
    if target_kind == "Strategy":
        row = conn.execute(
            "SELECT s.status, g.status AS goal_status FROM strategies s"
            " JOIN goals g ON g.id = s.goal_id WHERE s.id = ?",
            (int(target_id),),
        ).fetchone()
        if row:
            if row["status"] == "superseded":
                return
            if row["goal_status"] == "proved":
                # Sibling won the OR race; finalize this strategy as
                # superseded so bfs_refill stops considering it ready.
                if row["status"] == "proposed":
                    db.update_strategy_status(conn, int(target_id),
                                              "superseded")
                return
            if row["goal_status"] == "shelved":
                # Cascade race guard: parent goal was shelved while
                # this strategy's pipeline was in flight. Strategy is
                # moot; mark dead so invariant `proposed → parent alive`
                # holds.
                if row["status"] == "proposed":
                    db.update_strategy_status(conn, int(target_id),
                                              "dead")
                return
    elif target_kind == "Goal":
        row = conn.execute(
            "SELECT status FROM goals WHERE id = ?", (int(target_id),),
        ).fetchone()
        # Cascade race guard: once a goal reaches a terminal state
        # (proved/shelved/disproved/dead), late cascades from in-flight
        # pipelines must not mutate it.
        # Without the 'shelved' guard, a Backward 'success' that races
        # past the shelve transition would unconditionally flip status
        # back to 'attempting' (observed: goal stuck at attempts=N with
        # status='attempting' instead of 'shelved').
        # 'disproved' / 'dead' added with the sibling-orphan cascade
        # (_kill_upward_chain sibling sweep): a worker dispatched on
        # g2 before g2 cascaded-shelved (because its sibling g3 hit a
        # hard terminal and killed their shared parent strategy) must
        # not flip g2 back to attempting.
        if row and row["status"] in ("proved", "shelved",
                                      "disproved", "dead"):
            return

    # Provider/transport infra failures don't burn the goal's attempts
    # cap. Dispatcher main loop applies a per-target cooldown for all
    # four; only spawn_fast_fail contributes to the CONSEC daemon-exit
    # counter.
    #   * spawn_fast_fail      — rc≠0 with wall<10s (claude.exe crash)
    #   * quota_exhausted      — rc=126 (provider rate limit / quota)
    #   * missing_dep          — rc=127 (CLI binary missing)
    #   * gateway_unreachable  — pipeline raised URLError/OSError
    #                            (gateway HTTP transport failed: SG run
    #                            #14 2026-05-11 IOCP accept-loop death
    #                            shelved root goal by counting infra
    #                            refusals against attempts)
    _INFRA_REASONS = ("spawn_fast_fail", "quota_exhausted", "missing_dep",
                      "gateway_unreachable", "transient_timeout")
    is_infra = (outcome == "failed" and failure_reason in _INFRA_REASONS)

    # Phase 7 — `moot` outcome: pipeline detected the goal already
    # terminated (sibling proved / shelved / propagated shelve) before
    # spawning. No state mutation, no attempts++, no dead_attempt write
    # (decision 2). bfs_refill won't re-queue a terminal goal anyway.
    if outcome == "moot":
        return

    if kind == "Builder":
        if outcome == "proved":
            _set_goal_terminal_and_propagate(
                conn, int(target_id), "proved")
            return
        # Phase 7 — `exhausted` outcome: in-pipeline retry helper
        # consumed its budget without a terminal outcome. Helper has
        # already written N dead_attempts + N attempts++ for the N
        # failed retries (decision 5/6). Cascade does status transition
        # only — no further increment, no dead_attempt write.
        if outcome == "exhausted":
            cur = db.get_goal(conn, int(target_id))
            n = int(cur["attempts"]) if cur else 0
            if n >= SHELVE_THRESHOLD:
                _enqueue_strategist_review(conn, int(target_id))
            # If n is at/over BUILDER_THRESHOLD but under SHELVE, the
            # next bfs_refill picks Backward via next_worker_kind
            # — no extra cascade work needed (no session_id column to
            # clear post Phase 7-D).
            return
        if outcome == "failed":
            if is_infra:
                # Leave attempts unchanged; dispatcher will cool this
                # (target,kind) for ~30s before the next dispatch.
                return
            # Phase 2 — decline directives split by intent (see
            # `docs/phase2/pipelines.md` §4.2 Rule 1):
            #   * agent_infeasible (counterexample shown) → 'disproved'
            #     (hard terminal, dedupe blocks future same-shape proposals).
            #   * parent_needs_fix → 'dead' (parent strategy was wrong;
            #     cascade-die rather than cascade-shelve because the
            #     entire subtree was in the wrong context).
            #   * agent_shelved → 'pending_strategist_review'
            #     (transitional; defer judgment to Strategist via T2 trigger).
            # All three increment attempts once (LLM call happened;
            # preserve 1:1 attempts ↔ dead_attempts invariant) but only
            # the first two cascade — agent_shelved leaves the upward
            # strategy chain alive until Strategist commits a verdict.
            if failure_reason == "agent_infeasible":
                db.increment_goal_attempts(conn, int(target_id))
                _set_goal_terminal_and_propagate(
                    conn, int(target_id), "disproved")
                _propagate_disproved(conn, int(target_id))
                return
            if failure_reason == "parent_needs_fix":
                db.increment_goal_attempts(conn, int(target_id))
                _set_goal_terminal_and_propagate(
                    conn, int(target_id), "dead")
                _propagate_dead(conn, int(target_id))
                return
            if failure_reason == "agent_shelved":
                db.increment_goal_attempts(conn, int(target_id))
                _enqueue_strategist_review(conn, int(target_id))
                return
            # `needs_decomposition` directive (legacy `too_hard`):
            # Builder says "this goal needs decomposition first". Route
            # next dispatch to Backward via entry_kind switch instead
            # of inflating attempts to BUILDER_THRESHOLD. Phase 7
            # decision 5: attempts is LLM-call failure count, not a
            # routing knob; entry_kind preserves the 1:1 invariant
            # while still forcing the next dispatch to Backward.
            if failure_reason == "agent_declined":
                n = db.increment_goal_attempts(conn, int(target_id))
                if n >= SHELVE_THRESHOLD:
                    _enqueue_strategist_review(conn, int(target_id))
                else:
                    db.update_goal_entry_kind(conn, int(target_id),
                                              "Backward")
                return
            n = db.increment_goal_attempts(conn, int(target_id))
            if n >= SHELVE_THRESHOLD:
                _enqueue_strategist_review(conn, int(target_id))
            return

    if kind == "Forward":
        # Forward's target is the problem name (target_kind='Problem');
        # no goal row to update. Phase 2.5 unified — every Forward is
        # dispatched from an Inject batch (queue.decision_id always
        # set), so the batch-done hook covers the "give Strategist a
        # chance to re-decide after Forward fails" need that the legacy
        # pending_review re-enqueue used to handle separately.
        #
        # The hook: record this row's outcome, then if every sibling in
        # the batch is now terminal, enqueue a single Strategist with
        # trigger derivation → `inject_batch_done` (via the
        # `unacknowledged_inject_batches` ratchet). Infra and moot
        # outcomes do NOT advance the batch (moot = no real attempt
        # happened; infra = re-enqueued below).
        #
        # Infra failure that escapes the in-pipeline retries would
        # otherwise wedge the whole problem: this queue row is already
        # consumed, outcome stays NULL, so `inject_batch_done` can
        # never fire AND every Strategist wake on the problem is
        # suppressed by the in-flight-batch NOT EXISTS clause (T0 / T1
        # / T4 alike — see `db.problems_needing_t0/_t1` and
        # `db.problems_stalled`). Nothing re-creates the Forward until
        # daemon restart (recovery's NULL-outcome re-enqueue). Mirror
        # the Strategist infra re-enqueue below; the `consec_fast_
        # fails` cap (10) and per-kind quota cooldown bound persistent
        # breakage exactly as they do there. Skip when the decision
        # already linked a produced goal (sorry-bearing lemma landed
        # before the failure): outcome will arrive via `propagate_
        # inject_outcome_from_goal` when the lemma terminates, and
        # re-spawning would mint a second lemma (same guard as
        # recovery's in-flight Inject re-enqueue).
        if decision_id is not None and is_infra:
            row = conn.execute(
                "SELECT produced_goal_id FROM strategist_decisions"
                " WHERE id = ?", (decision_id,),
            ).fetchone()
            if row is not None and row["produced_goal_id"] is None:
                db.enqueue(conn, kind="Forward", target_id=target_id,
                           target_kind=target_kind, priority=20,
                           decision_id=decision_id)
                print(f"[forward-retry] re-queued {target_kind}="
                      f"{target_id} decision_id={decision_id} after "
                      f"{failure_reason}", flush=True)
            return
        if (decision_id is not None
                and not is_infra
                and outcome
                and outcome != "moot"):
            # Phase 2 (revised) — if Forward committed a sorry-bearing
            # lemma it already linked `produced_goal_id` on this
            # decision (see `forward.forward_parse`). In that case we
            # MUST NOT fill `outcome` here: it will be filled when the
            # produced goal reaches terminal (proved / shelved /
            # disproved) via `propagate_inject_outcome_from_goal`.
            # Filling early would fire `inject_batch_done` while the
            # lemma is still `:= by sorry` → Strategist Reopens parent,
            # Backward leaf-bypass-cites the sorry → axiom_probe
            # rollback (the residue_thm 2026-05-19 failure mode).
            row = conn.execute(
                "SELECT produced_goal_id FROM strategist_decisions"
                " WHERE id = ?", (decision_id,),
            ).fetchone()
            if row is not None and row["produced_goal_id"] is not None:
                # Sorry-bearing Forward: defer outcome until the lemma
                # terminates. inject_batch_done will fire at that time.
                pass
            else:
                _record_inject_decision_outcome(
                    conn, decision_id, outcome, failure_reason,
                )
                _maybe_enqueue_inject_batch_done(conn, decision_id)
        return

    if kind == "Backward":
        if outcome == "success":
            # Race guard: when a Backward leaf-bypass commits a strategy
            # that fails axiom probe (e.g. sorry-stub body), verify
            # housekeeping can fire BEFORE this cascade — verify marks
            # the strategy dead and reopens the goal to 'open'. The
            # delay comes from the worker's WorkArea.__exit__ release_
            # session HTTP call (up to 30s under gateway load); during
            # that window the main thread's tick boundary lets verify
            # see the just-committed ready_for_verify strategy and
            # process it before the worker's future is observed done.
            # Without this guard, the late cascade overwrites the
            # verify-reopened 'open' with 'attempting', leaving the
            # goal in a self-inconsistent state (no live strategy yet
            # status='attempting'); bfs_refill's open-only filter then
            # excludes it and the dispatcher idle-exits with budget
            # still available. Mirrors verify.py:218-224's has_live
            # check.
            has_live = conn.execute(
                "SELECT 1 FROM strategies WHERE goal_id = ?"
                " AND status IN ('proposed','succeeded') LIMIT 1",
                (int(target_id),),
            ).fetchone()
            if has_live is not None:
                db.update_goal_status(conn, int(target_id), "attempting")
            return
        # Phase 7 — `exhausted` outcome: mirrors Builder branch above.
        # Helper buffered N dead_attempts + N attempts++ for the N
        # failed retries; cascade does status transition only.
        if outcome == "exhausted":
            cur = db.get_goal(conn, int(target_id))
            n = int(cur["attempts"]) if cur else 0
            if n >= SHELVE_THRESHOLD:
                _enqueue_strategist_review(conn, int(target_id))
            return
        # failed
        if is_infra:
            return  # same skip-increment as Builder above
        # Decline directives mirror the Builder branch above (Phase 2
        # split: agent_infeasible → 'disproved' + propagate; parent_
        # needs_fix → 'dead' + propagate; agent_shelved → 'pending_
        # strategist_review' + enqueue Strategist, no propagate).
        # Backward cannot send `needs_decomposition` (Builder-only); if
        # a typo / unknown directive lands here it falls through to the
        # generic attempts++ branch and eventually shelves at threshold.
        if failure_reason == "agent_infeasible":
            db.increment_goal_attempts(conn, int(target_id))
            _set_goal_terminal_and_propagate(
                conn, int(target_id), "disproved")
            _propagate_disproved(conn, int(target_id))
            return
        if failure_reason == "parent_needs_fix":
            db.increment_goal_attempts(conn, int(target_id))
            _set_goal_terminal_and_propagate(
                conn, int(target_id), "dead")
            _propagate_dead(conn, int(target_id))
            return
        if failure_reason == "agent_shelved":
            db.increment_goal_attempts(conn, int(target_id))
            _enqueue_strategist_review(conn, int(target_id))
            return
        if failure_reason == "missing_parent_stub":
            # The goal's own stub file (goals.lean_path) is gone from disk
            # while the row is still dispatchable — a DB↔file drift (e.g. a
            # sibling slug-collision / stalled OR-branch cleanup removed the
            # `L_<slug>.lean` but left the goal row alive; P13 g4437
            # 2026-06-16). `run_backward` reads the stub BEFORE spawning, so
            # this fails INSTANTLY (no agent, no cooldown) — without a
            # terminal here the goal tight-loops re-dispatch (~20/s) until
            # SHELVE_THRESHOLD (g4437: 4 dead_attempts in 167ms). Retrying
            # re-reads a missing file forever, so park it terminally and log
            # the drift loudly. `shelved` (not `dead`): the statement is fine,
            # only its artifact vanished — restoring the stub (a parent
            # re-decompose) can revive it.
            db.increment_goal_attempts(conn, int(target_id))
            print(f"[drift] Backward g{target_id}: own stub file missing "
                  f"(goals.lean_path absent on disk) — shelving to stop the "
                  f"instant re-dispatch spin; DB↔file inconsistency, inspect "
                  f"why the L_<slug>.lean was removed while the row stayed "
                  f"open", flush=True)
            _set_goal_terminal_and_propagate(conn, int(target_id), "shelved")
            _propagate_shelve(conn, int(target_id))
            return
        n = db.increment_goal_attempts(conn, int(target_id))
        if n >= SHELVE_THRESHOLD:
            _enqueue_strategist_review(conn, int(target_id))
        return

    if kind == "Strategist":
        # Strategist has no equivalent of bfs_refill's auto-pickup —
        # queue rows arrive only from T0/T1/T2 triggers. An infra
        # failure (stuck-thinking / quota / gateway / spawn crash) on
        # a Strategist spawn therefore leaves the originating trigger's
        # intent unfulfilled: for T2 specifically, the goal that hit
        # agent_shelved stays in `pending_strategist_review` until the
        # next T1 routine wake — up to `strategist.interval_min`
        # (default 60min, often 120min) away.
        #
        # Re-enqueue on infra failure so the next tick retries. The
        # existing `consec_fast_fails` cap (10) protects against
        # persistent breakage: after 10 in a row the dispatcher exits
        # with code 2 for operator inspection.
        #
        # Observed: 2026-05-27 Banach-Tarski run, Strategist spawn
        # f0eb5be6 killed by watchdog at 660s (rc=128 stuck_thinking)
        # → failed → g3246 stuck in pending_review with no recovery
        # for 30+ min until the next T1 wake.
        if outcome == "failed" and is_infra:
            db.enqueue(conn, kind="Strategist", target_id=target_id,
                       target_kind=target_kind, priority=20)
            print(f"[strategist-retry] re-queued {target_kind}={target_id}"
                  f" after {failure_reason}", flush=True)
        return

    # Verify removed as a worker_kind. Strategy verification + parent
    # promotion happens in `verify.verify_housekeeping`, called at the
    # end of each dispatcher tick (see `run` below).


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
    try:
        g = db.get_goal(conn, int(target_id))
    except (TypeError, ValueError):
        return None
    return g["problem"] if g else None


def _verify_problem(workspace: Path, problem: str) -> bool:
    """Lake-build the problem's Defs.lean + Root.lean. Both must
    type-check cleanly. Lazy verification gate: run on first dispatch
    for the problem this daemon run; cached in-memory thereafter.

    Why lazy (vs at-startup): wide-scope daemons (e.g. miniF2F=244
    problems) would pay 30-60min upfront. Lazy pays only for problems
    that actually get dispatched (BFS may never touch a problem whose
    parent is dead/shelved). Per-problem ~5-15s amortizes over a long
    run.
    """
    pdir = db.problem_dir(workspace, problem)
    defs_path = pdir / "Defs.lean"
    root_path = pdir / "Root.lean"
    missing = [p.name for p in (defs_path, root_path) if not p.exists()]
    if missing:
        print(f"[verify] {problem}: FAILED — missing {missing}",
              flush=True)
        return False
    from ..pipeline._lake import lake_build_modules, lean_path_to_module
    modules = [
        lean_path_to_module(workspace, defs_path),
        lean_path_to_module(workspace, root_path),
    ]
    ok, msg = lake_build_modules(workspace, modules)
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
               quota_cooldown_kind: dict[str, float] | None = None,
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

    `quota_cooldown_kind` is the kind-wide variant: quota_exhausted is
    provider-level, not target-level — gating one (tid, kind) leaves
    243 other Backwards free to burn through the cap. While a kind is
    cooled here every enqueue of that kind is skipped this tick.

    `scope` (optional SQL LIKE pattern): when set, only enqueue goals
    whose problem matches. Lets a daemon run be restricted to a
    benchmark batch (e.g. `minif2f_%`) without disturbing unrelated
    problems sitting in the same workspace.
    """
    now = time.time()
    cd = cooldown_until or {}
    qcd = quota_cooldown_kind or {}

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

    def cooled(tid: str, kind: str) -> bool:
        return cd.get((tid, kind), 0.0) > now

    def kind_cooled(kind: str) -> bool:
        return qcd.get(kind, 0.0) > now

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
            awaiting_cache[problem] = db.problem_has_awaiting_human(
                conn, problem)
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
        kind = next_worker_kind(g)
        if kind_cooled(kind):
            continue
        if in_flight(gid, kind) == 0 and not cooled(gid, kind):
            priority = 5 if kind == "Builder" else 2
            db.enqueue(conn, kind=kind, target_id=gid, priority=priority)


# ---------------------------------------------------------------------
# Phase 2 — Strategist T0 / T1 triggers
# ---------------------------------------------------------------------

def _strategist_inflight(conn: sqlite3.Connection, root_id_str: str,
                         running: "set[tuple]") -> bool:
    """A Strategist for this root is already running or queued — the
    per-root serialization invariant (one Strategist per problem at a time;
    Strategist mutates problem-global state — `strategist_directive`
    overwrite-on-write, goal/strategy status, cross-decision coherence — so
    concurrent runs would race). Checks BOTH the in-memory `running` set
    (in-flight) AND the DB queue (pending); the cascade-time
    `_enqueue_strategist_review` checked only the queue, which is the gap
    `reconcile_stuck_states` closes.

    Phase 2.5 — running key is (target_id, kind, decision_id); Strategist
    rows always have decision_id=None (never spawned from an Inject), so a
    match by (root, 'Strategist', *) covers the invariant."""
    in_running = any(
        r[0] == root_id_str and r[1] == "Strategist" for r in running
    )
    return (in_running
            or db.is_in_queue(conn, target_id=root_id_str, kind="Strategist"))


def reconcile_stuck_states(conn: sqlite3.Connection,
                           running: "set[tuple]",
                           *, scope: str | None = None) -> None:
    """Per-tick safety net for mid-run stuck states that no other reconciler
    re-triggers and that can persist in a LIVE daemon (not only across a
    crash, which `recover_at_startup` handles).

    Two classes, both confirmed reachable mid-run and unrecoverable without
    this (investigation 2026-06-13):

      1. `pending_strategist_review` goals whose cascade-time Strategist
         enqueue was deduped (L355 queue-only race), lost, or dropped — there
         is no restart recovery for these, so they orphan permanently (P13
         left 2/3 stuck; BT g3246 waited 30+ min for the accidental 120-min
         T1). Enqueue a Strategist; the spawn's `_derive_strategist_trigger`
         sees the pending goal and runs a `pending_review` wake.

      2. NULL-outcome Inject decisions whose worker died on infra failure
         with no artifact — this wedges the WHOLE problem (the in-flight-
         batch clause suppresses T0/T1/T4), recoverable otherwise only at
         restart. Re-enqueue the worker.

    Both are IN-FLIGHT GATED: an item whose worker is live (in `running`) or
    already queued is skipped, so this never double-dispatches. That gating
    is the only thing this adds over the startup-recovery logic it shares
    (`db.null_inject_redispatch_specs`), which runs against a clean slate."""
    # 1 — pending_review: enqueue Strategist (spawn derives the trigger).
    for prob, root_id in db.problems_with_pending_review(conn, scope=scope):
        if db.problem_has_awaiting_human(conn, prob):
            continue
        rid = str(root_id)
        if _strategist_inflight(conn, rid, running):
            continue
        db.enqueue(conn, kind="Strategist", target_id=rid,
                   target_kind="Goal", priority=20)

    # 1.5 — settled NULL-outcome Inject decisions: the produced goal/
    # strategy already terminated (or a Backward inject's strategy is
    # 'proposed' but wedged with zero alive subgoals — a soft-shelved
    # subgoal awaiting a Reopen that this very NULL outcome blocks by
    # suppressing T4). Resolve the outcome so the batch completes, fires
    # inject_batch_done, and stops suppressing the stall trigger.
    # Complements step 2 below (worker died with no artifact → re-dispatch);
    # the two are disjoint by the produced goal/strategy state.
    db.reconcile_settled_inject_outcomes(conn, scope=scope)

    # 2 — NULL-outcome Inject: re-enqueue the worker, in-flight gated.
    for spec in db.null_inject_redispatch_specs(conn, scope=scope):
        did = spec["decision_id"]
        if any(len(r) > 2 and r[2] == did for r in running):
            continue  # a worker for this Inject is live this run
        if db.queue_has_decision(conn, did):
            continue  # already queued (e.g. cascade-time L967 re-enqueue)
        db.enqueue(conn, kind=spec["kind"], target_id=spec["target_id"],
                   target_kind=spec["target_kind"], priority=10,
                   decision_id=did)


# ---------------------------------------------------------------------
# Phase 2 — Strategist T0 / T1 triggers
# ---------------------------------------------------------------------

def strategist_triggers(conn: sqlite3.Connection,
                        running: set[tuple[str, str]],
                        *,
                        scope: str | None = None,
                        interval_min: float = 60.0,
                        daemon_start_iso: str | None = None,
                        ) -> None:
    """T0 (first-launch) + T1 (routine) enqueues for the Strategist pipeline.
    T2 (pending_review) is handled by `_enqueue_strategist_review` at
    cascade-time, not here.

    T0 condition: `problems.bootstrap_done = 0`.
    T1 condition: `last_routine_at` (the routine-only clock, not reset by
                   event-driven triggers) older than `interval_min` minutes of
                   running time (paused/down time excluded via
                   `daemon_start_iso`), AND root not terminal.

    Per-problem dedup: skip enqueue if a Strategist (target=root) is
    already running or already in the queue. The awaiting_human gate
    skips Strategist enqueue for problems whose human-input request
    hasn't been resolved.

    Called from `dispatcher.run` once per tick alongside `bfs_refill`.
    """
    max_age_sec = interval_min * 60.0

    # T0 — first launch (highest urgency among Strategist triggers)
    for prob, root_id in db.problems_needing_t0(conn, scope=scope):
        if db.problem_has_awaiting_human(conn, prob):
            continue
        rid = str(root_id)
        if _strategist_inflight(conn, rid, running):
            continue
        # Higher priority than Backward (2) / Builder (5)? Phase 2 spec
        # says Strategist > Backward/Builder but < Verify housekeeping.
        # Verify is inline (not queued), so queue.priority just needs
        # to put Strategist ahead of Backward/Builder.
        db.enqueue(conn, kind="Strategist", target_id=rid,
                   target_kind="Goal", priority=10)

    # T1 — routine audit (own running-time cadence; see problems_needing_t1)
    for prob, root_id in db.problems_needing_t1(
        conn, scope=scope, max_age_sec=max_age_sec,
        since_iso=daemon_start_iso,
    ):
        if db.problem_has_awaiting_human(conn, prob):
            continue
        rid = str(root_id)
        if _strategist_inflight(conn, rid, running):
            continue
        db.enqueue(conn, kind="Strategist", target_id=rid,
                   target_kind="Goal", priority=10)

    # T4 — structural stall trigger.
    # Fires when a problem has no open goals (BFS has nothing to
    # dispatch), no in-flight Backward/Builder/Forward worker, and
    # the root is not yet proved. Captures the failure mode polar
    # 2026-05-23 hit: a parent strategy with a shelved sub-goal sat
    # 'proposed' forever, parent goal stayed 'attempting' (filtered
    # out of `open_goals`), no spawn fired for 174 min until budget
    # exhaust. Routine T1 (60 min) eventually fires but Strategist
    # Noop'd 4 times because the snapshot ("X proved") didn't change
    # between ticks. T4 is the structural backstop: if we hit this
    # signal we KNOW the framework is deadlocked, so we wake
    # Strategist immediately + surface the stall in Context.md (see
    # `_section_stall_warning` in phase2_context). Strategist prompt
    # has the corresponding rule: don't Noop when stall section is
    # present.
    for prob, root_id in db.problems_stalled(conn, scope=scope,
                                              running=running):
        if db.problem_has_awaiting_human(conn, prob):
            continue
        rid = str(root_id)
        if _strategist_inflight(conn, rid, running):
            continue
        db.enqueue(conn, kind="Strategist", target_id=rid,
                   target_kind="Goal", priority=10)


# ---------------------------------------------------------------------
# Worker thread body
# ---------------------------------------------------------------------

def _derive_strategist_trigger(conn: sqlite3.Connection,
                                problem: str) -> tuple[str, int | None]:
    """Pick `trigger_kind` for a Strategist run on `problem`. Returns
    `(trigger, pending_review_id)` where pending_review_id is non-None
    iff trigger is 'pending_review'.

    Priority order (Phase 2 §2.1 + 2.5 + 5):

      1. `inject_batch_done` — unacknowledged Inject batch resolved.
         A batch completion is the freshest event; Strategist must
         decide follow-up (Reopen / Inject / etc) before any other
         reasoning, even if root happens to be frozen meanwhile.
      2. `pending_review` — at least one goal in pending_strategist_
         review status. A goal explicitly waiting on a verdict is more
         focused than a generic root-status check.
      3. `first_launch` — root is `frozen` AND bootstrap_done=0.
         "Strategist has never committed any decision yet on this
         problem". Once any decision lands, bootstrap_done flips
         (`_commit_one` calls `set_problem_bootstrap_done` on every
         commit), and subsequent wakes on a still-frozen root become
         routine check-ins.

         Pre-fix this branch fired whenever root.status='frozen'
         regardless of bootstrap_done. Observed jordan_normal_form
         2026-05-23: 200+ decisions had landed but root was still
         frozen because Strategist had been injecting prereq bricks
         rather than Reopen(root); manually-injected routine wake-
         ups repeatedly hit first_launch.md ("no decisions recorded
         yet") instead of routine.md's active-audit checklist.
      4. `routine` — default; wall-clock check-in.
    """
    pending_row = conn.execute(
        "SELECT id FROM goals WHERE problem = ?"
        "   AND status = 'pending_strategist_review'"
        " ORDER BY id LIMIT 1",
        (problem,),
    ).fetchone()
    pending_id = int(pending_row["id"]) if pending_row else None
    unack_batches = db.unacknowledged_inject_batches(conn, problem)
    if unack_batches:
        return ("inject_batch_done", pending_id)
    if pending_id is not None:
        return ("pending_review", pending_id)
    root_row = conn.execute(
        "SELECT status FROM goals "
        " WHERE problem = ? AND origin = 'root'",
        (problem,),
    ).fetchone()
    root_frozen = (root_row is not None
                   and str(root_row["status"]) == 'frozen')
    bootstrap_row = conn.execute(
        "SELECT bootstrap_done FROM problems WHERE name = ?",
        (problem,),
    ).fetchone()
    bootstrap_done = bool(bootstrap_row
                          and int(bootstrap_row["bootstrap_done"]))
    if root_frozen and not bootstrap_done:
        return ("first_launch", pending_id)
    return ("routine", pending_id)


def _strategist_row_is_stale(conn: sqlite3.Connection,
                             target_id: str, kind: str) -> bool:
    """A queued Strategist whose root goal is already `proved` has nothing
    left to decide — it would only spawn, Noop, and advance
    `last_strategist_at`. The dispatcher drops such a popped row.

    Safe by construction (see inject_batch_done ack lifecycle): the
    Strategist enqueue is event-driven (`maybe_enqueue_inject_batch_done`
    at cascade + T0/T1 in `strategist_triggers`), never a per-tick poll on
    un-acknowledged batches, so dropping the row doesn't busy-loop. The
    daemon exit check (`root_proved && no librarian`) is independent of
    un-acked batches, so a lingering un-acked batch doesn't block exit.
    And if root later un-proves (rogue-sorryAx rollback), it re-enters the
    queue via the normal triggers — the `last_strategist_at` ratchet still
    sees the batch as unacknowledged.

    `target_id` of a Strategist row is always the root goal id.
    """
    if kind != "Strategist":
        return False
    try:
        g = db.get_goal(conn, int(target_id))
    except (ValueError, TypeError):
        return False
    return g is not None and str(g["status"]) == "proved"


def _librarian_index_has(workspace: Path, problem: str) -> bool:
    """True iff `Library/INDEX.md` already records `problem` — the
    idempotent 'finish done' marker. Reading the file (rather than a DB
    column) keeps the lifecycle state machine at four states
    (candidate→deduped→classified→migrated); INDEX presence is the only
    thing distinguishing 'all migrated, finish pending' from 'finished'."""
    index = workspace / "Library" / "INDEX.md"
    if not index.exists():
        return False
    text = index.read_text(encoding="utf-8", errors="replace")
    # Line-exact match on the section header — a substring test would let
    # problem `p` falsely match section `## pp`. Mirrors the header
    # comparison in librarian._upsert_index_section.
    header = f"## {problem}"
    return any(ln.strip() == header for ln in text.splitlines())


def _librarian_invalidate_index(workspace: Path, problem: str) -> None:
    """Drop `problem`'s stale INDEX section when it is being RE-cleaned (already
    promoted, but its Library is now being rewritten). Without this the stale
    entry reads as 'finished' (`_derive_librarian_work`'s INDEX done-marker) and
    the terminal bridge/Gate B is skipped — the re-cleaned Library would be
    re-exposed without re-verifying it re-derives the root. Clearing it makes
    bridge re-fire + re-promote. Called from the single-threaded tick (no
    concurrent INDEX writer during a problem's cleanup phase — bridge runs only
    once all its decls are cleaned)."""
    from ..pipeline import librarian
    index = workspace / "Library" / "INDEX.md"
    try:
        text = index.read_text(encoding="utf-8")
    except OSError:
        return
    new = librarian._drop_index_section(text, problem)
    if new != text:
        index.write_text(new, encoding="utf-8")
        print(f"[librarian] {problem}: re-clean detected → cleared stale INDEX "
              f"entry (bridge/Gate B will re-verify + re-promote)", flush=True)


# #92 — a Librarian queue row for the parallel phases (migrate/cleanup) encodes
# its target FILE in the target_id as `problem\x1ffile`, so the generic pop /
# running-dedup / submit machinery treats each file as a distinct unit (the
# running key (target_id, kind, decision_id) is naturally per-file) with NO
# change to that machinery. Phase steps (dedup/classify/bridge) stay a plain
# `problem` target_id. Only Librarian-aware code decodes; proving target_ids are
# goal ints and never contain the separator, so they are unaffected.
_LIB_SEP = "\x1f"


def _lib_encode(problem: str, target_file: str) -> str:
    return f"{problem}{_LIB_SEP}{target_file}"


def _lib_decode(target_id: str) -> "tuple[str, str | None]":
    """`problem\\x1ffile` → (problem, file); a plain `problem` → (problem, None)."""
    if _LIB_SEP in target_id:
        problem, target_file = target_id.split(_LIB_SEP, 1)
        return problem, target_file
    return target_id, None


def _derive_librarian_work(
    conn: sqlite3.Connection, problem: str, workspace: Path,
) -> tuple[str | None, str | None]:
    """Derive the next Librarian work_kind from library_decls state
    (plan §5). Pure read. Returns (work_kind, target):

      - no rows                        → ('dedup', None)   [mechanical keep-all]
      - any 'candidate' (un-verdicted) → ('dedup', None)   [defensive]
      - any 'deduped' (kept, unplaced) → ('classify', None)
      - any 'classified'               → ('migrate', <next ready file>)
      - any 'migrated', no INDEX yet   → ('bridge', None)  [v0.3: no cleanup]
      - otherwise (terminal + done)    → (None, None)

    v0.3 (plan §3): `dedup` is the mechanical keep-all (`_run_keepall`, no
    agent); cleanup is removed — `migrated` goes straight to the bridge Gate B
    probe. The `cleaned` lifecycle is no longer produced.

    bridge (Gate B, plan §2) is the terminal step: once every file is
    'migrated' it re-derives the original root from the Library and, on
    success, writes INDEX — so INDEX presence remains the single done-marker
    and a Library that fails to re-derive correctly never 'finishes'.

    migrate's target is a Library FILE, not a slug — the parallel unit is
    the whole file (plan §5 Step 3). `next_migrate_file` picks a file whose
    dependency files are all already migrated (topological order over the
    reconstructed file DAG); the re-enqueue chain advances the rest. bridge
    is gated on the INDEX marker so it fires once, not in a loop."""
    rows = db.library_decls_for(conn, problem)
    if not rows:
        return ("dedup", None)
    by_state: dict[str, list] = {}
    for r in rows:
        by_state.setdefault(str(r["lifecycle"]), []).append(r)
    if by_state.get("candidate"):
        return ("dedup", None)
    if by_state.get("deduped"):
        return ("classify", None)
    if by_state.get("classified"):
        from ..pipeline import librarian
        return ("migrate", librarian.next_migrate_file(
            conn, problem=problem, workspace=workspace))
    # v0.4 (plan §10/§11, §13 3c-2): once all files are migrated, the cleanup-
    # dedup stage runs PER FILE (advances migrated → cleaned/dropped) BEFORE the
    # bridge Gate B probe. Like migrate it is a per-file phase — `_librarian_
    # refill` enqueues ready files (`ready_cleanup_files`) and the plain `problem`
    # row is a no-op; the `None` target signals "per-file phase" here. Bridge
    # then writes INDEX (= promote / done-marker).
    if by_state.get("migrated"):
        return ("cleanup", None)
    if by_state.get("cleaned") and not _librarian_index_has(workspace, problem):
        return ("bridge", None)
    return (None, None)


def _advance_librarian_chain(
    conn: sqlite3.Connection, workspace: Path, target_id: str, *,
    outcome: str, reason: str, fail_counts: dict,
) -> None:
    """Per-unit fail tracking for the Librarian chain (#92).

    Re-enqueue is owned by the tick-level `_librarian_refill` (the DAG
    scheduler) — here we only COUNT failures so a unit that keeps failing is
    skipped (stalled) by the refill instead of looping forever. `target_id` is
    the finished row's queue id: a plain `problem` (serial phase step) or
    `problem\\x1ffile` (per-file migrate/cleanup unit). Mutates `fail_counts`,
    keyed by `target_id` so each file/phase stalls independently. Surviving a
    transient gateway/harness failure: the refill re-enqueues the same unit
    next tick until the count crosses `LIBRARIAN_MAX_CHAIN_RETRIES`."""
    if outcome in ("success", "proved"):
        fail_counts.pop(target_id, None)
        db.clear_librarian_fail_count(conn, target_id=target_id)   # write-through
        return
    if reason == "librarian_file_busy":
        # Transient same-path contention (the lock holder needs minutes, the
        # loser's retries land in seconds) — re-enqueued by the refill, but
        # NOT a strike against the unit: counting it burned the cap before
        # the winner finished (2026-06-11).
        print(f"[librarian] {target_id.split(chr(31))[0]}: unit busy "
              f"(same-path migrate in flight) — will retry, not counted",
              flush=True)
        return
    n = fail_counts.get(target_id, 0) + 1
    fail_counts[target_id] = n
    db.set_librarian_fail_count(conn, target_id=target_id, n=n)    # survives restart
    problem, target_file = _lib_decode(target_id)
    unit = target_file or "chain step"
    if n > LIBRARIAN_MAX_CHAIN_RETRIES:
        print(f"[librarian] {problem}: unit `{unit}` STALLED after {n} "
              f"failures ({reason}) — needs operator", flush=True)
    else:
        print(f"[librarian] {problem}: unit `{unit}` failed ({reason}); "
              f"will retry (attempt {n}/{LIBRARIAN_MAX_CHAIN_RETRIES})",
              flush=True)


def _librarian_selfstart_problems(
    conn: sqlite3.Connection, workspace: Path,
    manifests, *, scope: str | None,
) -> "list[str]":
    """In-scope problems whose Librarian chain should START this run but has
    no durable trigger left (#92 Bug B): opted-in (`Manifest.library`), root
    proved, no INDEX yet, and no `library_decls` rows (chain never began, or
    the library was reset). The verify hook (verify.py) only enqueues `dedup`
    at the instant a root becomes integrity-verified — a historically-proved
    or library-reset problem never re-fires it, and a manual enqueue is wiped
    by `recover_at_startup`'s blanket queue clear. So the refill self-seeds
    `dedup` for these, making the daemon resume Library-ization across a
    restart instead of stranding it. Gated on the per-problem `library: true`
    opt-in (default False), so this never auto-Library-izes a problem the
    operator didn't mark."""
    if scope:
        proved = conn.execute(
            "SELECT DISTINCT problem FROM goals WHERE origin='root' "
            "AND status='proved' AND problem LIKE ?", (scope,)).fetchall()
    else:
        proved = conn.execute(
            "SELECT DISTINCT problem FROM goals WHERE origin='root' "
            "AND status='proved'").fetchall()
    out: list[str] = []
    for (problem,) in proved:
        if problem not in manifests:
            continue
        if not manifests[problem].library:
            continue
        if _librarian_index_has(workspace, problem):
            continue
        if db.library_decls_for(conn, problem):
            continue  # already has rows — driven by the library_decls path
        out.append(problem)
    return out


def _librarian_refill(
    conn: sqlite3.Connection, workspace: Path,
    running: "set[tuple]", manifests, *, scope: str | None = None,
    fail_counts: dict,
) -> bool:
    """Tick-level DAG scheduler for the Librarian chain (#92) — the analogue of
    `bfs_refill` for proving. For every problem whose chain is active:

      - serial phase (dedup/classify/bridge): ensure ONE plain `problem`
        Librarian row is queued.
      - per-file phase (migrate/cleanup): enqueue one `problem\\x1ffile` row per
        READY file (its dep-files are all done, and it is neither in-flight nor
        already queued) so independent files run concurrently in the pool.

    Drives problems that already have `library_decls` rows PLUS opted-in
    proved problems with no chain yet (`_librarian_selfstart_problems`, Bug B)
    — so the daemon (re)starts and resumes Library-ization on its own, not just
    when the verify hook fires at proof time.

    Returns whether any LIVE Librarian work remains in scope (something was
    enqueued this tick, or a unit is in-flight / already queued). The
    workspace-exit gate uses this so the daemon does NOT quit with Library-ization
    pending — proof work alone no longer keeps it alive (Bug A). Units whose
    fail count crossed `LIBRARIAN_MAX_CHAIN_RETRIES` are skipped (stalled — they
    do NOT count as pending, so a fully-stalled chain lets the daemon exit for
    the operator to inspect)."""
    from ..pipeline import librarian
    if scope:
        prob_rows = conn.execute(
            "SELECT DISTINCT problem FROM library_decls WHERE problem LIKE ?",
            (scope,)).fetchall()
    else:
        prob_rows = conn.execute(
            "SELECT DISTINCT problem FROM library_decls").fetchall()
    problems = [p for (p,) in prob_rows]
    seen = set(problems)
    for p in _librarian_selfstart_problems(
            conn, workspace, manifests, scope=scope):
        if p not in seen:
            problems.append(p)
            seen.add(p)

    pending = False
    for problem in problems:
        work_kind, _ = _derive_librarian_work(conn, problem, workspace)
        if work_kind is None:
            continue
        # Re-cleaning an already-promoted problem: its INDEX entry is stale, and
        # `_derive_librarian_work` would read it as "done" after cleanup, skipping
        # the terminal bridge/Gate B. Invalidate it now (single-threaded tick) so
        # bridge re-fires once the rewritten Library is all cleaned.
        if work_kind == "cleanup" and _librarian_index_has(workspace, problem):
            _librarian_invalidate_index(workspace, problem)
        if work_kind in ("migrate", "cleanup"):
            # Both are per-file phases (#92 migrate, §13 3c-2 cleanup): enqueue
            # one `problem\x1ffile` row per READY file so independent files run
            # concurrently. The per-file row's step is resolved at run time by
            # `file_work_kind` (migrate while classified, cleanup once migrated),
            # so the two phases share the same encode/in-flight machinery.
            inflight: set[str] = set()
            for r in running:
                if r[1] != "Librarian":
                    continue
                rp, rf = _lib_decode(r[0])
                if rp == problem and rf is not None:
                    inflight.add(rf)
            queued = set()
            for (qtid,) in conn.execute(
                    "SELECT target_id FROM queue WHERE kind='Librarian'"):
                qp, qf = _lib_decode(str(qtid))
                if qp == problem and qf is not None:
                    queued.add(qf)
            skip = inflight | queued
            if skip:
                pending = True  # a file is mid-flight or already queued
            ready = (librarian.ready_file_work if work_kind == "migrate"
                     else librarian.ready_cleanup_files)
            for _wk, f in ready(
                    conn, problem=problem, workspace=workspace, in_flight=skip):
                tid = _lib_encode(problem, f)
                if fail_counts.get(tid, 0) > LIBRARIAN_MAX_CHAIN_RETRIES:
                    continue  # stalled file — operator
                db.enqueue(conn, kind="Librarian", target_id=tid,
                           target_kind="Problem", priority=0)
                pending = True
        else:
            # Serial phase — a single plain `problem` row.
            if fail_counts.get(problem, 0) > LIBRARIAN_MAX_CHAIN_RETRIES:
                continue  # stalled — not pending, daemon may exit
            if (problem, "Librarian", None) in running:
                pending = True
                continue
            if db.queue_contains(conn, kind="Librarian", target_id=problem):
                pending = True
                continue
            db.enqueue(conn, kind="Librarian", target_id=problem,
                       target_kind="Problem", priority=0)
            pending = True
    return pending


def _run_pipeline(workspace: Path,
                  manifests: "manifest.ManifestCache | dict[str, manifest.Manifest]",
                  task_kind: str, target_id: str, target_kind: str,
                  pipeline_id: str,
                  decision_id: int | None = None,
                  ) -> tuple[str, str, str, str, str]:
    """Run one pipeline in worker thread. Returns (pipeline_id, kind, target_id,
    target_kind, outcome).

    Side effects:
      - INSERT one finished pipeline row (succeeded/failed)
      - On failure: INSERT dead_attempt row with full artifacts JSON
      - Always rmtree .attempts/<pid>/ + .attempts/_backup_<pid>/ via WorkArea

    Phase 2 — `decision_id` carries the strategist_decisions row id
    when the spawning queue entry came from a Strategist Inject
    decision. Passed through to compile_context for the
    `## Strategist brief` section. BFS-auto-dispatched pipelines have
    decision_id=None.

    NB: opens its own DB conn (sqlite3 thread safety)."""
    import json as _json
    conn = db.connect()
    started_at = db.now()
    try:
        with agent.WorkArea(workspace, pipeline_id) as wa:
            attempts_dir = wa.attempts

            # Phase 2 — Strategist + Forward dispatch.
            #   Strategist: target_kind='Goal', target_id=problem.root.id;
            #     pipeline operates problem-level via root's `problem`
            #     column. decision_id is unused (Strategist EMITS decisions).
            #   Forward:    target_kind='Problem', target_id=problem_name;
            #     decision_id is the Strategist Inject row that spawned
            #     this Forward.
            if task_kind == "Strategist":
                goal_id = int(target_id)
                goal = db.get_goal(conn, goal_id)
                if goal is None:
                    db.record_pipeline(
                        conn, pipeline_id=pipeline_id, kind=task_kind,
                        target_id=target_id, target_kind=target_kind,
                        status="failed", outcome="failed",
                        started_at=started_at,
                    )
                    return (pipeline_id, task_kind, target_id, target_kind,
                            "failed", "goal_not_found")
                problem = str(goal["problem"])
                mfst = manifests[problem]
                trigger, pending_id = _derive_strategist_trigger(
                    conn, problem)

                from ..pipeline import strategist
                r = strategist.run_strategist(
                    conn, problem=problem, trigger_kind=trigger,
                    tick=0,  # tick concept TBD; 0 as placeholder for now
                    workspace=workspace, mfst=mfst,
                    pipeline_id=pipeline_id,
                    pending_review_id=pending_id,
                )
                status = ("succeeded" if r.outcome in ("proved", "success")
                          else "failed")
                db.record_pipeline(
                    conn, pipeline_id=pipeline_id, kind=task_kind,
                    target_id=target_id, target_kind=target_kind,
                    status=status, outcome=r.outcome,
                    started_at=started_at,
                )
                if status == "failed":
                    db.record_dead_attempt(
                        conn, target_id=goal_id, target_kind=target_kind,
                        pipeline_id=pipeline_id,
                        failure_reason=str(r.failure_reason or "failed"),
                        failure_detail=str(r.failure_detail or ""),
                    )
                return (pipeline_id, task_kind, target_id, target_kind,
                        r.outcome, str(r.failure_reason or ""))

            if task_kind == "Forward":
                # Forward target = problem name (TEXT); no goal lookup.
                problem = target_id
                if problem not in manifests:
                    db.record_pipeline(
                        conn, pipeline_id=pipeline_id, kind=task_kind,
                        target_id=target_id, target_kind=target_kind,
                        status="failed", outcome="failed",
                        started_at=started_at,
                    )
                    return (pipeline_id, task_kind, target_id, target_kind,
                            "failed", "problem_not_found")
                mfst = manifests[problem]
                from ..pipeline import forward
                r = forward.run_forward(
                    conn, problem=problem, workspace=workspace,
                    mfst=mfst, pipeline_id=pipeline_id,
                    decision_id=decision_id,
                )
                status = ("succeeded" if r.outcome in ("proved", "success")
                          else "failed")
                db.record_pipeline(
                    conn, pipeline_id=pipeline_id, kind=task_kind,
                    target_id=target_id, target_kind=target_kind,
                    status=status, outcome=r.outcome,
                    started_at=started_at,
                )
                # Flush per-retry buffered failures from the retry
                # helper. Phase 2 dead_attempts row for Forward uses
                # target_id=0 + target_kind='Problem' (migration_plan
                # §C option 1: dead_attempts.target_id is INTEGER, so
                # Problem-targeted forensic uses 0 with the audit
                # index living on target_kind + decision_id).
                for pf in r.pending_failures:
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind="Problem",
                        pipeline_id=pipeline_id,
                        failure_reason=pf["reason"],
                        failure_detail=pf["detail"],
                        proposal_md=pf.get("proposal_md", ""),
                        artifacts=(_json.dumps(pf["artifacts"])
                                   if pf.get("artifacts") else ""),
                    )
                # Pipeline-level dead_attempt for the final outcome.
                # Skip when outcome is 'exhausted' — the helper has
                # already buffered the last retry's failure (flushed
                # above); duplicating here would over-count.
                if (status == "failed"
                        and r.outcome != "exhausted"):
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind=target_kind,
                        pipeline_id=pipeline_id,
                        failure_reason=str(r.failure_reason or "failed"),
                        failure_detail=str(r.failure_detail or ""),
                    )
                return (pipeline_id, task_kind, target_id, target_kind,
                        r.outcome, str(r.failure_reason or ""))

            if task_kind == "Librarian":
                # Problem-targeted background harvest (plan §5). Derive
                # the work_kind from library_decls state — work_kind is
                # NOT in the queue row (mirrors strategist deriving its
                # trigger), so a re-enqueued chain step always reflects
                # the latest state.
                # #92 — target_id is `problem\x1ffile` for a per-file
                # migrate/cleanup unit, or a plain `problem` for a serial phase
                # step (dedup/classify/bridge).
                problem, target_file = _lib_decode(target_id)
                if problem not in manifests:
                    db.record_pipeline(
                        conn, pipeline_id=pipeline_id, kind=task_kind,
                        target_id=target_id, target_kind=target_kind,
                        status="failed", outcome="failed",
                        started_at=started_at,
                    )
                    return (pipeline_id, task_kind, target_id, target_kind,
                            "failed", "problem_not_found")
                from ..pipeline import librarian
                if target_file is not None:
                    # Per-file unit: run THIS file's current step.
                    work_kind = librarian.file_work_kind(
                        conn, problem=problem, target_file=target_file)
                    target = target_file
                else:
                    # Serial phase step. If state has advanced to a per-file
                    # phase (migrate/cleanup), `_librarian_refill` owns it —
                    # this plain row is a no-op (the per-file rows do the work).
                    work_kind, target = _derive_librarian_work(
                        conn, problem, workspace)
                    if work_kind in ("migrate", "cleanup"):
                        work_kind = None
                if work_kind is None:
                    # Nothing to do for this row (chain drained, or a stale
                    # plain row whose phase is now per-file). Clean no-op.
                    db.record_pipeline(
                        conn, pipeline_id=pipeline_id, kind=task_kind,
                        target_id=target_id, target_kind=target_kind,
                        status="succeeded", outcome="success",
                        started_at=started_at,
                    )
                    return (pipeline_id, task_kind, target_id, target_kind,
                            "success", "")
                # Per-file axiom check uses the operator's authorized
                # axioms (Manifest `axioms_whitelist`), falling back to
                # the 3 standard axioms — same source + fallback as
                # root_integrity_gate. Only migrate consumes it.
                mfst = manifests[problem]
                whitelist = (list(mfst.axioms_whitelist)
                             if mfst.axioms_whitelist
                             else list(verify.FRAMEWORK_DEFAULT_AXIOMS))
                r = librarian.run_librarian(
                    conn, problem=problem, work_kind=work_kind,
                    workspace=workspace, pipeline_id=pipeline_id,
                    target=target, whitelist=whitelist,
                )
                status = ("succeeded" if r.outcome in ("proved", "success")
                          else "failed")
                db.record_pipeline(
                    conn, pipeline_id=pipeline_id, kind=task_kind,
                    target_id=target_id, target_kind=target_kind,
                    status=status, outcome=r.outcome,
                    started_at=started_at,
                )
                # Problem-targeted forensic uses target_id=0 (mirrors
                # Forward — dead_attempts.target_id is INTEGER). Librarian
                # is background: a failure is logged but never blocks
                # proof work, and the chain does not auto-retry a
                # schema/verify failure (operator inspects).
                if status == "failed":
                    artifacts = pipeline.collect_artifacts(attempts_dir)
                    db.record_dead_attempt(
                        conn, target_id=0, target_kind="Problem",
                        pipeline_id=pipeline_id,
                        failure_reason=str(r.failure_reason or "failed"),
                        failure_detail=str(r.failure_detail or ""),
                        proposal_md=r.proposal_md,
                        artifacts=(_json.dumps(artifacts) if artifacts
                                   else ""),
                    )
                return (pipeline_id, task_kind, target_id, target_kind,
                        r.outcome, str(r.failure_reason or ""))

            # Builder / Backward — Goal-targeted.
            goal_id = int(target_id)
            goal = db.get_goal(conn, goal_id)
            if goal is None:
                db.record_pipeline(
                    conn, pipeline_id=pipeline_id, kind=task_kind,
                    target_id=target_id, target_kind=target_kind,
                    status="failed", outcome="failed",
                    started_at=started_at,
                )
                return (pipeline_id, task_kind, target_id, target_kind,
                        "failed", "goal_not_found")

            mfst = manifests[goal["problem"]]

            if task_kind == "Builder":
                r = pipeline.run_builder(
                    conn, goal_id=goal_id, workspace=workspace,
                    mfst=mfst, pipeline_id=pipeline_id,
                    decision_id=decision_id,
                )
            elif task_kind == "Backward":
                r = pipeline.run_backward(
                    conn, goal_id=goal_id, workspace=workspace,
                    mfst=mfst, pipeline_id=pipeline_id,
                    decision_id=decision_id,
                )
            else:
                r = pipeline.PipelineResult(outcome="failed",
                                            failure_reason="unknown_kind")

            status = "succeeded" if r.outcome in ("proved", "success") else "failed"
            db.record_pipeline(
                conn, pipeline_id=pipeline_id, kind=task_kind,
                target_id=target_id, target_kind=target_kind,
                status=status, outcome=r.outcome,
                started_at=started_at,
            )

            # Phase 7 — flush per-retry buffered failures from the
            # in-pipeline retry helper. The helper writes one
            # `goals.attempts++` eagerly (for live TREE.md visibility)
            # but buffers the paired dead_attempts row here because
            # dead_attempts.pipeline_id FKs the pipelines row we just
            # INSERTed. Flush only writes the dead_attempts rows; the
            # increment already happened in-helper.
            #
            # Skip flush on outcome='moot': decision 2 mandates moot is
            # uniform no-op (no dead_attempts written). Mid-loop moot
            # detection drops any prior-iteration buffered failures —
            # those were real LLM calls but on a goal that's since gone
            # terminal, so their forensic value is curiosity-only. Note
            # the eager attempts++ from those iterations remains in DB
            # (helper already wrote them); strict decision-2 alignment
            # is at the dead_attempts surface, not the attempts column.
            if r.outcome != "moot":
                for pf in r.pending_failures:
                    db.record_dead_attempt(
                        conn, target_id=goal_id, target_kind="Goal",
                        pipeline_id=pipeline_id,
                        failure_reason=pf["reason"],
                        failure_detail=pf["detail"],
                        proposal_md=pf.get("proposal_md", ""),
                        artifacts=(_json.dumps(pf["artifacts"])
                                   if pf.get("artifacts") else ""),
                    )

            # Capture artifacts from .attempts/<pid>/ before WorkArea rmtree.
            # Skip the pipeline-final dead_attempts INSERT for:
            #   - 'exhausted' outcome: helper already buffered the
            #     last retry's failure into pending_failures (flushed
            #     above); duplicating here would violate the 1:1
            #     attempts ↔ dead_attempts invariant.
            #   - 'superseded' (OR race noise, not a real failure).
            #   - infra reasons (spawn_fast_fail / quota_exhausted /
            #     missing_dep): not agent actions; reason carried back
            #     via the future tuple for cooldown, events.py filters
            #     them anyway.
            if (r.outcome != "exhausted"
                    and r.failure_reason
                    and r.failure_reason not in (
                        "superseded",
                        "spawn_fast_fail",
                        "quota_exhausted",
                        "missing_dep",
                    )):
                artifacts = pipeline.collect_artifacts(attempts_dir)
                tk = target_kind
                tid = goal_id if tk == "Goal" else int(target_id)
                db.record_dead_attempt(
                    conn, target_id=tid, target_kind=tk,
                    pipeline_id=pipeline_id,
                    failure_reason=r.failure_reason,
                    failure_detail=r.failure_detail,
                    proposal_md=r.proposal_md,
                    artifacts=_json.dumps(artifacts) if artifacts else "",
                )

            return (pipeline_id, task_kind, target_id, target_kind,
                    r.outcome, r.failure_reason)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    """Cross-platform liveness check. POSIX: os.kill(pid, 0); Windows:
    OpenProcess + GetExitCodeProcess.

    Note: On Windows, os.kill(pid, 0) raises SystemError because sig
    0 isn't a real Windows signal — Python's os.kill on Windows only
    handles termination signals via TerminateProcess.

    Windows kernel keeps the Process object live for any handle holder
    even AFTER the process has terminated, so OpenProcess succeeds on
    a freshly-killed PID. GetExitCodeProcess distinguishes "still
    running" (STILL_ACTIVE=259) from "terminated but handle-zombie".
    Without this check, the singleton lock would refuse new daemons
    for any PID the OS hasn't recycled yet."""
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        try:
            exit_code = ctypes.c_uint32(0)
            ok = kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
            if not ok:
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _proc_start_time(pid: int) -> "float | None":
    """psutil process create-time for `pid` (epoch seconds), or None if the
    process is gone / its start-time is unreadable. Paired with the PID it
    forms a reuse-proof process-instance identity for the singleton lock."""
    try:
        import psutil
        return psutil.Process(pid).create_time()
    except Exception:
        return None


def _cmdline_is_daemon(pid: int) -> "bool | None":
    """True / False iff the live process at `pid` is / isn't an asterism
    dispatcher (`python -m Tooling.core.cli run …` or the `asterism run`
    console script); None if its command line can't be read. The fallback
    identity signal for a legacy pid-only lock that has no recorded
    start-time."""
    try:
        import psutil
    except ImportError:
        return None
    try:
        argv = psutil.Process(pid).cmdline()
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return None
    joined = " ".join(argv)
    if ("Tooling.core.cli" in joined
            or "core/cli" in joined or "core\\cli" in joined):
        return True
    if argv and "run" in argv:
        exe = argv[0].lower().replace("\\", "/").rsplit("/", 1)[-1]
        if exe.startswith("asterism"):
            return True
    return False


def _lock_held_by_live_daemon(pid: int, stored_start: "float | None") -> bool:
    """True iff `pid` is the SAME live daemon instance that wrote the lock —
    NOT merely a live PID. Guards against PID REUSE: after a daemon crashes
    without releasing its lock, the OS can hand its PID to an unrelated live
    process (observed 2026-06-15 — a crashed daemon's PID was reused by the
    editor, so the bare-liveness lock blocked every restart). A (pid,
    start-time) pair identifies a process instance, so a reused PID — alive
    but with a different start-time — reads as stale.

    `stored_start` is the start-time recorded in the lock (None for a legacy
    pid-only lock). When absent or unreadable, fall back to a command-line
    signature; if neither signal can be read, conservatively treat a live PID
    as the daemon so two daemons never share one DB (the disaster the lock
    exists to prevent)."""
    if not _pid_alive(pid):
        return False
    if stored_start is not None:
        live = _proc_start_time(pid)
        if live is not None:
            return abs(live - stored_start) < 1.0
        # start-time unreadable — fall through to the cmdline signal.
    sig = _cmdline_is_daemon(pid)
    if sig is None:
        return True  # can't introspect a live PID — conservative (block)
    return sig


def _acquire_singleton_lock(workspace: Path) -> Path | None:
    """Refuse to start if another daemon is already running on this
    workspace. Two daemons sharing one DB silently dispatch the same
    goal twice, write conflicting strategy rows, and clobber each
    other's verify_strategy state. Caught in the wild when a stray
    `&` background invocation overlapped with a fresh `run`.

    Mechanism: PID file at `.asterism/daemon.pid` holding `pid\\nstart_time`.
    On startup:
      - if file missing → create, return path
      - if it names the SAME live process instance (pid + start-time, or a
        daemon command line for a legacy pid-only lock) → return None
        (caller exits)
      - if it names a dead PID, or a REUSED PID now belonging to a different
        process → stale, overwrite. (Bare liveness alone is fooled by PID
        reuse — 2026-06-15: a crashed daemon's PID became the editor's,
        blocking every restart.)

    Returned path should be `.unlink(missing_ok=True)` at shutdown.
    """
    asterism_dir = workspace / ".asterism"
    asterism_dir.mkdir(parents=True, exist_ok=True)
    pid_file = asterism_dir / "daemon.pid"
    my_pid = os.getpid()

    if pid_file.exists():
        existing = -1
        stored_start: "float | None" = None
        try:
            parts = pid_file.read_text(encoding="utf-8").split("\n")
            existing = int(parts[0].strip())
            if len(parts) > 1 and parts[1].strip():
                stored_start = float(parts[1].strip())
        except (OSError, ValueError):
            existing = -1
        if (existing > 0 and existing != my_pid
                and _lock_held_by_live_daemon(existing, stored_start)):
            print(f"[dispatcher] another daemon (pid={existing}) is "
                  f"already running on this workspace. Kill it or wait "
                  f"for it to exit, then retry. (lock: {pid_file})",
                  file=sys.stderr, flush=True)
            return None

    my_start = _proc_start_time(my_pid)
    pid_file.write_text(
        f"{my_pid}\n{my_start if my_start is not None else ''}",
        encoding="utf-8")
    return pid_file


def run(workspace: Path, *, once: bool = False,
        scope: str | None = None) -> int:
    pid_lock = _acquire_singleton_lock(workspace)
    if pid_lock is None:
        return 1
    import atexit
    atexit.register(lambda: pid_lock.unlink(missing_ok=True))

    global BUILDER_THRESHOLD, SHELVE_THRESHOLD
    pool_size = config.get(
        "dispatch.pool", default=4,
        env_var="ASTERISM_POOL", cast=int, workspace=workspace)
    budget_sec = config.get(
        "dispatch.budget_sec", default=1800,
        env_var="ASTERISM_BUDGET_SEC", cast=int, workspace=workspace)
    # BUILDER_THRESHOLD semantically belongs to the Builder kind
    # (controls Builder→Backward transition based on Builder model
    # strength). Canonical key: `builder.threshold`. Old
    # `dispatch.builder_threshold` is honored as a back-compat fallback
    # so existing Asterism.yaml files keep working unchanged.
    BUILDER_THRESHOLD = config.get(
        "builder.threshold", default=None,
        env_var="ASTERISM_BUILDER_THRESHOLD", cast=int, workspace=workspace)
    if BUILDER_THRESHOLD is None:
        BUILDER_THRESHOLD = config.get(
            "dispatch.builder_threshold", default=3,
            cast=int, workspace=workspace)
    SHELVE_THRESHOLD = config.get(
        "dispatch.shelve_threshold", default=8,
        env_var="ASTERISM_SHELVE_THRESHOLD", cast=int, workspace=workspace)
    # Phase 2 — T1 (wall-clock routine) interval in minutes. Default 60
    # per `docs/phase2/pipelines.md` §5. Picked by `strategist_triggers`
    # each tick. Override via env var or Asterism.yaml for calibration.
    strategist_interval_min = config.get(
        "strategist.interval_min", default=60.0,
        env_var="ASTERISM_STRATEGIST_INTERVAL_MIN", cast=float,
        workspace=workspace,
    )
    if SHELVE_THRESHOLD <= BUILDER_THRESHOLD:
        # An invalid combo would mean Backward never gets a chance —
        # fail loudly rather than silently degrade behavior.
        raise ValueError(
            f"shelve_threshold ({SHELVE_THRESHOLD}) must exceed "
            f"builder_threshold ({BUILDER_THRESHOLD}); otherwise "
            f"the goal shelves before any Backward attempt fires.")
    pool = ThreadPoolExecutor(max_workers=pool_size)
    # Background .olean warmer (#103): after verify_housekeeping promotes
    # a strategy (parent → alias rewrite), the alias spine needs a fresh
    # .olean so the later root integrity probe doesn't pay a cold closure
    # build on this main thread. The warmer runs that `lake build` on its
    # own daemon thread — off the main thread AND off this LLM worker pool
    # (which is gateway-bound, #118). Kill switch: `verify.olean_warm`.
    from ..pipeline._olean_warm import OleanWarmer
    _olean_warm_raw = config.get(
        "verify.olean_warm", default=True,
        env_var="ASTERISM_OLEAN_WARM", workspace=workspace)
    olean_warm_enabled = (
        _olean_warm_raw if isinstance(_olean_warm_raw, bool)
        else str(_olean_warm_raw).strip().lower() in ("true", "1", "yes", "on"))
    olean_warmer = OleanWarmer(workspace, enabled=olean_warm_enabled)
    atexit.register(lambda: olean_warmer.shutdown(wait=False))
    futures: dict[Future, tuple[str, str, str, str]] = {}
    # In-memory live set of (target_id, kind) pairs currently executing in
    # this daemon. Passive trigger means at most one of each kind per
    # target, so the pair is a unique key. Daemon crash → set vanishes →
    # restart sees clean slate.
    running: set[tuple[str, str]] = set()
    # Per-(target_id, kind) cooldown until epoch seconds. Set after
    # a spawn_fast_fail cascade; bfs_refill skips cooled pairs so the
    # daemon doesn't burst-retry a broken claude.exe at 2s/call.
    cooldown_until: dict[tuple[str, str], float] = {}
    # Per-unit consecutive Librarian chain failures (#92 cap). In-memory hot
    # read path, but LOADED from `librarian_fail_counts` after init_schema +
    # write-through on every mutation, so a stuck unit's count survives a daemon
    # restart and STALLs at LIBRARIAN_MAX_CHAIN_RETRIES instead of looping forever.
    librarian_fail_counts: dict[str, int] = {}
    # Lazy verify cache: problem → True (Defs.lean + Root.lean built
    # cleanly) | False (build error; problem is quarantined for this
    # daemon run; restart re-verifies). Filled at first dispatch for
    # the problem; bfs_refill and the pop loop both consult it so a
    # quarantined problem never burns worker spawns.
    verified_problems: dict[str, bool] = {}
    # Global counter of consecutive spawn_fast_fail outcomes (across
    # all targets). Reset by any non-fast-fail cascade. If it crosses
    # CONSEC_SPAWN_FAIL_LIMIT the daemon exits with a clear message —
    # claude.exe is persistently broken and human attention is required.
    consec_fast_fails = 0
    SPAWN_COOLDOWN_SEC = 30.0
    CONSEC_SPAWN_FAIL_LIMIT = 10
    # Independent counter for gateway_unreachable. d2dd861 prevents
    # transient gateway hiccups from charging goal attempts (good),
    # but a PERMANENT gateway death (e.g. accept loop crashed) means
    # every dispatch instantly hits WinError 10061 → 30s cooldown →
    # re-dispatch → new strategy row → infinite loop. Run #17 cut at
    # +52min after 48 strategies piled up on 2 hard goals. The
    # circuit breaker exits when consecutive gateway-unreachable
    # crosses CONSEC_GATEWAY_UNREACHABLE_LIMIT — daemon refuses to
    # busy-loop against a dead gateway and forces operator attention.
    consec_gateway_unreachable = 0
    CONSEC_GATEWAY_UNREACHABLE_LIMIT = 8
    # Per-kind quota backoff (#103). quota_exhausted is provider-level,
    # not target-level — gating one (tid, kind) leaves all other targets
    # of the same kind free to keep hammering. Backoff doubles on each
    # consecutive quota_exhausted for that kind, capped at 600s; any
    # non-quota outcome (success or agent-side failure) resets the
    # counter and clears the per-kind cooldown so dispatch resumes.
    consec_quota_per_kind: dict[str, int] = {}
    quota_cooldown_kind: dict[str, float] = {}
    QUOTA_BACKOFF_BASE_SEC = 30.0
    QUOTA_BACKOFF_CAP_SEC = 600.0

    conn = db.connect()
    # Idempotent — picks up additive migrations on an existing DB
    # without requiring `cli init` / `cli reset`. SCHEMA itself is
    # CREATE TABLE IF NOT EXISTS, and ALTER TABLE ADD COLUMN entries
    # swallow "duplicate column name". Required because the daemon
    # is the long-running consumer of the DB on a workspace that
    # was init'd against an earlier schema version.
    db.init_schema(conn)
    # Restore the Librarian chain fail cap across restarts (#92 B#3): a stuck
    # unit's tally persists so it STALLs instead of looping forever.
    librarian_fail_counts.update(db.librarian_fail_counts_all(conn))
    # ManifestCache hot-reloads on Manifest.md mtime change at each
    # spawn-time access — daemon previously locked in the startup-time
    # parse, so user edits mid-run were invisible until restart. Cache
    # quacks like dict[str, Manifest] for downstream callers.
    manifests = manifest.ManifestCache(workspace)
    for row in conn.execute("SELECT name, manifest_path FROM problems"):
        manifests.load(row["name"], row["manifest_path"])

    _recover_at_startup(conn, workspace, scope=scope)

    # Spawn-sandbox sweep: clean any orphan sandboxes left by SIGKILL'd
    # spawns from a prior daemon run (per docs/archive/spawn_sandbox.md §3.3).
    # Runs after _recover_at_startup so DB state is consistent before
    # filesystem state is reconciled. Sweep skips sandboxes whose owner
    # daemon is alive (guards against concurrent daemons).
    from ..agent import sandbox as _spawn_sandbox
    _sb_counters = _spawn_sandbox.sweep_orphan_sandboxes(workspace)
    if any(_sb_counters[k] for k in
           ("rolled_back", "deleted_committed", "corrupt_manifest",
            "drift_warnings", "skipped_alive_owner")):
        print(f"[sandbox-sweep] startup: {_sb_counters}", flush=True)

    # Refresh BRIEF.md for every registered problem at startup. Covers
    # Manifest edits + Library promotes since the last daemon run
    # (daemon has no hot-reload; startup is the canonical refresh point).
    # Lemma resolution can take ~30s when Manifest hints are dense; only
    # paid once per startup, off the dispatch path.
    from ..state import brief
    brief.write_for_all_problems(conn, workspace, manifests)

    scope_label = f", scope={scope!r}" if scope else ""
    print(f"[dispatcher] start, pool={pool_size}, "
          f"problems={list(manifests)}{scope_label}",
          flush=True)
    start_time = time.time()
    # Daemon start as an ISO timestamp — the T1 routine clock baseline, so
    # paused/down time between runs is excluded from the routine interval.
    from datetime import datetime as _dt, timezone as _tz
    daemon_start_iso = _dt.fromtimestamp(start_time, tz=_tz.utc).isoformat()

    # Surface problems paused on an unresolved RequestUserAmend up front.
    # bfs_refill silently skips these (awaiting_human gate), so without
    # this line a scoped daemon whose only in-scope problem is paused is
    # indistinguishable from a hang — 2026-06-12 a paused P12
    # (stokes_induced_orient) read as a multi-hour gateway/tree-render
    # hang across two sessions. Operator must resolve the amend (apply
    # the proposed Defs.lean/Manifest.md body, clear the decision) then
    # re-run. Cheap: idx_sd_outcome backs the filter.
    _paused_q = ("SELECT DISTINCT problem FROM strategist_decisions "
                 "WHERE outcome = 'awaiting_human'")
    _paused_params: tuple = ()
    if scope:
        _paused_q += " AND problem LIKE ?"
        _paused_params = (scope,)
    _paused_startup = sorted(r[0] for r in conn.execute(_paused_q, _paused_params))
    if _paused_startup:
        print(f"[dispatcher] {len(_paused_startup)} problem(s) PAUSED on "
              f"awaiting_human (unresolved RequestUserAmend); dispatch "
              f"suppressed until resolved: {_paused_startup}", flush=True)

    # Phase 1 gateway: launch long-living LSP HTTP MCP server, wait
    # until backend pre-warm completes (mathlib loaded). Per-spawn MCP
    # config will point at this gateway via HTTP; spawns no longer
    # fork their own lake serve. Cold start ~30-145s amortized once
    # per daemon startup. start_gateway registers an atexit handler so
    # the subprocess dies with the daemon — we don't need to track the
    # Popen ourselves here.
    from ..lsp import lifecycle as gateway_lifecycle
    gateway_lifecycle.start_gateway(workspace)

    # Periodic TREE.md refresh targets. A `--scope X` run only mutates
    # in-scope problems, so refreshing all ~281 problems' trees every tick
    # is pure churn — and with idx_strategies_goal_id the render dropped to
    # ~0.17s/tick, so the loop now cycles fast enough that the rapid
    # atomic-replace of unrelated TREE.md files raised transient WinError 5
    # sharing violations on Windows (caught below, but noise). Computed once
    # — the problem set is fixed for a run. Unscoped runs still refresh all.
    if scope is not None:
        tree_problems = db.scoped_problem_names(conn, scope)
    else:
        tree_problems = list(manifests)

    while True:
        # Cascade for any completed pipelines
        if futures:
            done, _ = wait(list(futures), timeout=0, return_when=FIRST_COMPLETED)
            for fut in done:
                meta = futures.pop(fut)
                # meta = (pipeline_id, kind, target_id, target_kind,
                #        decision_id). Phase 2.5 — running key includes
                # decision_id so batch Inject siblings (same target+kind,
                # different decision_id) don't share a slot.
                running.discard((meta[2], meta[1], meta[4]))
                meta_decision_id = meta[4]
                try:
                    pid, kind, tid, tk, outcome, reason = fut.result()
                    cascade_one(conn, pipeline_id=pid, kind=kind,
                                target_id=tid, target_kind=tk,
                                outcome=outcome, failure_reason=reason,
                                decision_id=meta_decision_id)
                    # Librarian chain advance (#92). Only COUNTS this unit's
                    # outcome (per-target_id fail tracking); re-enqueue is owned
                    # by the tick-level `_librarian_refill` DAG scheduler. A
                    # unit that keeps failing crosses LIBRARIAN_MAX_CHAIN_RETRIES
                    # and the refill then skips it (stalled) instead of looping.
                    if kind == "Librarian":
                        _advance_librarian_chain(
                            conn, workspace, tid, outcome=outcome,
                            reason=reason, fail_counts=librarian_fail_counts)
                    # Back-off + global counter for spawn fast-fails.
                    # Phase 7 — quota_exhausted (rc=126) / missing_dep (rc=127)
                    # also cooldown but do NOT contribute to CONSEC tracking
                    # (quota recovers on its own; missing_dep is operator-fix).
                    # #103 — quota_exhausted is now handled separately with
                    # per-kind exponential backoff: provider rate limit is
                    # provider-level, not target-level, so the per-(tid, kind)
                    # cooldown alone leaves 200+ siblings of the same kind
                    # free to drain the queue and burn the cap.
                    if outcome == "failed" and reason == "quota_exhausted":
                        n = consec_quota_per_kind.get(kind, 0) + 1
                        consec_quota_per_kind[kind] = n
                        backoff = min(
                            QUOTA_BACKOFF_BASE_SEC * (2 ** (n - 1)),
                            QUOTA_BACKOFF_CAP_SEC,
                        )
                        quota_cooldown_kind[kind] = time.time() + backoff
                        # Flush queued entries of this kind so the
                        # pop loop doesn't keep draining the backlog
                        # against an exhausted provider (each pop
                        # would re-fire and bump consec further).
                        flushed = db.flush_queue_kind(conn, kind=kind)
                        print(f"[cooldown] {kind} quota_exhausted "
                              f"(consec={n}, backoff={backoff:.0f}s, "
                              f"flushed={flushed} queued; all {kind} "
                              f"dispatch suspended)", flush=True)
                    elif outcome == "failed" and reason in (
                        "spawn_fast_fail", "missing_dep",
                        "gateway_unreachable", "transient_timeout",
                    ):
                        cooldown_until[(tid, kind)] = (
                            time.time() + SPAWN_COOLDOWN_SEC)
                        if reason == "spawn_fast_fail":
                            consec_fast_fails += 1
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"spawn_fast_fail "
                                  f"(consec={consec_fast_fails})", flush=True)
                            if consec_fast_fails >= CONSEC_SPAWN_FAIL_LIMIT:
                                print(f"[dispatcher] {consec_fast_fails} "
                                      f"consecutive spawn_fast_fails — "
                                      f"claude.exe or provider appears broken; "
                                      f"exiting. Inspect "
                                      f".attempts/<pid>/_spawn.stderr "
                                      f"for the underlying error.", flush=True)
                                _exit_pool_fast(pool)
                                return 2
                        elif reason == "gateway_unreachable":
                            consec_gateway_unreachable += 1
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"gateway_unreachable "
                                  f"(consec={consec_gateway_unreachable})",
                                  flush=True)
                            if (consec_gateway_unreachable
                                    >= CONSEC_GATEWAY_UNREACHABLE_LIMIT):
                                print(f"[dispatcher] "
                                      f"{consec_gateway_unreachable} "
                                      f"consecutive gateway_unreachable — "
                                      f"gateway appears permanently dead; "
                                      f"exiting. Restart daemon (gateway "
                                      f"will be re-launched) and inspect "
                                      f".asterism/logs/gateway.log for the "
                                      f"underlying crash.", flush=True)
                                _exit_pool_fast(pool)
                                return 2
                        else:
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after {reason}",
                                  flush=True)
                    else:
                        consec_fast_fails = 0
                        consec_gateway_unreachable = 0
                        # #103 — any non-quota, non-infra outcome on this
                        # kind proves the provider responded: clear the
                        # per-kind quota backoff so dispatch resumes
                        # fresh. (Other infra reasons above are orthogonal
                        # to quota — handled in their own branch and don't
                        # touch quota state.)
                        if kind in consec_quota_per_kind:
                            consec_quota_per_kind.pop(kind, None)
                            quota_cooldown_kind.pop(kind, None)
                            print(f"[cooldown] {kind} quota state reset "
                                  f"(non-quota outcome confirms provider "
                                  f"responsive)", flush=True)
                    # `strategist_noop` is a non-success outcome but means
                    # "nothing to propose" (often: root already proved by
                    # the time the trigger fired) — not an error. Render it
                    # as `noop` so the log doesn't read as a failure.
                    _disp_outcome = (
                        "noop" if outcome == "failed"
                        and reason == "strategist_noop" else outcome)
                    print(f"[cascade] {kind} {tk}={tid} → {_disp_outcome}",
                          flush=True)
                    tree.write_for_target(conn, workspace, tid, tk)
                except Exception as exc:
                    # Worker thread raised an unhandled exception (e.g.
                    # subprocess launch errno-2, OSError on temp dir, an
                    # internal pipeline bug). Without explicit recovery
                    # the goal stays open, attempts unchanged, and
                    # bfs_refill re-dispatches in an infinite loop.
                    # Synthesize a cascade with outcome='failed' so the
                    # goal advances toward SHELVE_THRESHOLD and forensic
                    # state at least mentions the exception.
                    #
                    # Classify first: transport-level errors (gateway
                    # unreachable / conn refused / network reset) are
                    # infrastructure failures, not the goal's fault.
                    # Route through the _INFRA_REASONS short-circuit so
                    # attempts stay unchanged AND the per-target cooldown
                    # below kicks in.
                    pid, kind, tid, tk, _did = meta
                    infra_reason = _classify_worker_exception(exc)
                    label = (f"{infra_reason} (no attempts++)"
                             if infra_reason else "treating as failed")
                    print(f"[cascade] worker exception on {kind} "
                          f"{tk}={tid}: {exc}; {label}",
                          flush=True)
                    try:
                        cascade_one(conn, pipeline_id=pid, kind=kind,
                                    target_id=tid, target_kind=tk,
                                    outcome="failed",
                                    failure_reason=infra_reason,
                                    decision_id=_did)
                        # Backward's BaseException handler in
                        # `backward.py` deletes the placeholder
                        # strategy when the worker crashed before
                        # writing proposal_md/scratch_path. Combined
                        # with cascade_one's early-return on infra
                        # reasons (no attempts++, no status touch),
                        # the parent goal can be left 'attempting'
                        # with no live strategy — bfs_refill skips it
                        # (open_goals filter) and no cascade re-
                        # checks. Reconcile here so the goal either
                        # reopens for a fresh Backward (under
                        # threshold) or shelves (deferred terminal
                        # from earlier strong-signal cascades).
                        if kind == "Backward" and tk == "Goal":
                            try:
                                _reconcile_goal_after_strategy_loss(
                                    conn, int(tid))
                            except (ValueError, TypeError):
                                pass
                        tree.write_for_target(conn, workspace, tid, tk)
                        # Mirror the normal-result cooldown path so
                        # gateway-unreachable / transient_timeout also
                        # yield a 30s back-off — without this, the same
                        # Backward gets re-dispatched on the next tick
                        # and re-fails.
                        if infra_reason == "transient_timeout":
                            cooldown_until[(tid, kind)] = (
                                time.time() + SPAWN_COOLDOWN_SEC)
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"transient_timeout (slot contention "
                                  f"or RPC budget exceeded; no consec "
                                  f"increment — circuit breaker reserved "
                                  f"for true gateway death)",
                                  flush=True)
                        elif infra_reason == "gateway_unreachable":
                            cooldown_until[(tid, kind)] = (
                                time.time() + SPAWN_COOLDOWN_SEC)
                            consec_gateway_unreachable += 1
                            print(f"[cooldown] {kind} {tk}={tid} cooled "
                                  f"{SPAWN_COOLDOWN_SEC:.0f}s after "
                                  f"gateway_unreachable "
                                  f"(consec={consec_gateway_unreachable})",
                                  flush=True)
                            if (consec_gateway_unreachable
                                    >= CONSEC_GATEWAY_UNREACHABLE_LIMIT):
                                print(f"[dispatcher] "
                                      f"{consec_gateway_unreachable} "
                                      f"consecutive gateway_unreachable — "
                                      f"gateway appears permanently dead; "
                                      f"exiting. Restart daemon (gateway "
                                      f"will be re-launched) and inspect "
                                      f".asterism/logs/gateway.log for the "
                                      f"underlying crash.", flush=True)
                                _exit_pool_fast(pool)
                                return 2
                    except Exception as exc2:
                        # Cascade itself bombing is a deeper bug; log
                        # but don't crash the daemon (other work may
                        # still progress).
                        print(f"[cascade] secondary exception during "
                              f"recovery: {exc2}", flush=True)

        # Strategy verify housekeeping. Runs after cascade so any
        # newly-proved sub-goals from this tick contribute to the
        # `ready_for_verify` poll. Inline + recursive (chain follow-up
        # for multi-layer strategies in one tick).
        verify.verify_housekeeping(conn, workspace=workspace,
                                   manifests=manifests,
                                   olean_warmer=olean_warmer)

        # Per-problem post-proved gate. Only problems whose root just
        # flipped to 'proved' AND haven't yet passed integrity_gate
        # under this DB are visited — `db.unverified_proved_roots`
        # returns at most that subset, dropping to [] once every root
        # is verified. The earlier formulation iterated `manifests`
        # every tick and paid one gateway-driven axiom_probe per
        # proved root every loop iteration (244 miniF2F roots stalled
        # dispatch for ~115min on every restart); the marker in
        # `goals.integrity_verified` is what keeps this O(unverified)
        # instead of O(all proved). Rollback paths flip the marker off
        # transparently via `db.update_goal_status` whenever a goal
        # leaves 'proved', so a once-failed root re-enters this gate
        # on the next tick after cascade rollback.
        for problem_name in db.unverified_proved_roots(conn):
            if problem_name not in manifests:
                # Root proved for a problem we don't have a Manifest
                # for in-process (CLI invoked with a scope filter that
                # excluded it, or DB row outlived its Manifest dir).
                # Skip without flipping the marker — it'll get picked
                # up the next run that loads this Manifest.
                continue
            # Reconcile FILE/DB drift from OR races. Auto-prune was
            # removed 2026-05-26 after Jordan 2026-05-25 incident exposed
            # how easily a single bad keep-set computation wipes a chain;
            # the bugs that caused that wipe were fixed (1660200), but the
            # blast radius of an auto-delete loop is large enough that
            # explicit operator opt-in is the safer default. Manual GC via
            # `asterism prune <problem>` (preferably `--dry-run` first).
            repaired = prune.reconcile_proved_goals(
                conn, workspace, problem_name)
            if repaired:
                print(f"[reconcile] {problem_name}: repaired "
                      f"{len(repaired)} drifted files", flush=True)
            # Root integrity gate — single root-level axiom_probe under
            # verify-collapse. Sets `integrity_verified=1` on success
            # so subsequent ticks skip this problem. On sorryAx
            # detection, rolls back the cascade chain via
            # `verify.rollback_cascade_chain`, which leaves the
            # culprit goal in 'open' state and (via update_goal_status)
            # clears integrity_verified on the root so the gate fires
            # again once a fresh proof cascades back up.
            verify.root_integrity_gate(
                conn, workspace, problem_name, manifests[problem_name])
            # Final TREE.md refresh — the per-cascade write_for_target
            # ran before the verify_housekeeping that cascade-proved
            # the root, leaving TREE.md frozen at root=attempting.
            tree.write(conn, workspace, problem_name)

        # #92 — Librarian DAG scheduler: enqueue every dispatchable file
        # (and the serial phase steps), self-starting opted-in proved
        # problems, so independent files migrate/clean in parallel in the
        # pool, the same way bfs_refill fans out proving goals. Run BEFORE the
        # exit gate so its `pending` return can hold the daemon alive while
        # Library-ization is outstanding (Bug A — proof work alone no longer
        # keeps the daemon up once every root is proved).
        librarian_pending = _librarian_refill(
            conn, workspace, running, manifests, scope=scope,
            fail_counts=librarian_fail_counts)

        # Workspace-wide exit: every problem's root is proved AND no Librarian
        # work remains. `verify.root_integrity_gate` above may have called
        # `rollback_cascade_chain` on sorryAx detection, reverting a root to
        # 'attempting'; in that case this check fails and the dispatcher loop
        # continues for re-Backward.
        # `scope` filter: a `--scope sylvester_gallai` daemon must gate on its
        # scoped problems only — without this filter, unrelated miniF2F roots
        # sitting in the same workspace keep `root_proved` False forever.
        # `librarian_pending`: without it a scoped run over an already-proved
        # problem (or the last root proving in any run) exits before the
        # Library-ization chain — dedup→classify→migrate→bridge→INDEX —
        # has a chance to run, since that chain spans many ticks (Bug A).
        if db.root_proved(conn, scope=scope) and not librarian_pending:
            print("[dispatcher] all roots proved", flush=True)
            _exit_pool_fast(pool)
            return 0

        # Refill queue (uses in-memory `running` for dedup; cooldown_until
        # holds spawn_fast_fail back-offs; quota_cooldown_kind holds the
        # per-kind quota backoff (#103); scope restricts to a benchmark
        # subset like `minif2f_%`).
        bfs_refill(conn, running, cooldown_until, scope=scope,
                   quota_cooldown_kind=quota_cooldown_kind,
                   verified_problems=verified_problems)

        # Phase 2 — Strategist T0/T1 triggers (T2 pending_review fires at
        # cascade time in `cascade_one` as the fast path). Skipped under
        # awaiting_human gate per-problem inside `strategist_triggers`.
        # Defaults to 60-min routine (`strategist.interval_min`).
        strategist_triggers(conn, running, scope=scope,
                            interval_min=strategist_interval_min,
                            daemon_start_iso=daemon_start_iso)

        # Per-tick stuck-state reconciler: the safety net for the two
        # mid-run-reachable stuck states the cascade fast paths can drop —
        # orphaned pending_review goals + NULL-outcome Inject wedges. Runs
        # every tick, in-flight gated, so a dropped wakeup self-heals within
        # one tick instead of waiting for restart / the 120-min routine.
        reconcile_stuck_states(conn, running, scope=scope)

        # Spawn from queue while pool has slots. Skip if a pipeline of
        # the same (target_id, kind) is already in flight in this
        # daemon — bfs_refill caps at 1 but daemon recovery + race
        # corners mean defense-in-depth here is cheap.
        while len(futures) < pool_size:
            row = db.pop_queue(conn)
            if row is None:
                break
            target_id = str(row["target_id"])
            kind = str(row["kind"])
            # Phase 2 — queue.target_kind defaults to 'Goal' (post-
            # migration column), and queue.decision_id is non-NULL when
            # this row was emitted by a Strategist Inject decision.
            # Both default-safe for pre-Phase 2 queue rows (target_kind
            # has DEFAULT 'Goal', decision_id NULL). Decision_id must
            # be read BEFORE the running-dedup check below so the
            # 3-tuple key is complete (Phase 2.5: batch Inject siblings
            # share target+kind but differ by decision_id).
            try:
                target_kind = str(row["target_kind"]) or "Goal"
            except (IndexError, KeyError):
                target_kind = "Goal"
            try:
                _did = row["decision_id"]
                decision_id = int(_did) if _did is not None else None
            except (IndexError, KeyError):
                decision_id = None
            if _dispatch_is_duplicate(running, target_id, kind, decision_id):
                continue
            # #103 — defense-in-depth: even after bfs_refill skips
            # cooled kinds, a race (cooldown set between bfs_refill
            # and pop) could leave a queued row for a now-cooled
            # kind. Drop it; bfs_refill will repopulate post-cooldown.
            if quota_cooldown_kind.get(kind, 0.0) > time.time():
                continue
            # Drop a queued Strategist whose root already proved (e.g. an
            # inject_batch_done that landed just before the proof, or a
            # routine T1 that raced the promotion). It would only spawn +
            # Noop. See `_strategist_row_is_stale` for the safety argument.
            if _strategist_row_is_stale(conn, target_id, kind):
                print(f"[dispatch] skip Strategist Goal={target_id} "
                      f"— root already proved", flush=True)
                continue
            # Lazy verify gate — must hold before any worker spawn.
            # First dispatch for a problem this daemon run pays a one-
            # time `lake build Defs.lean + Root.lean` (~5-15s). Failure
            # quarantines the problem in `verified_problems` so neither
            # the pop loop nor bfs_refill dispatches further on it.
            problem_name = _problem_of_target(conn, target_id, target_kind)
            if problem_name is None:
                # Defensive: unknown target shape (DB drift?). Skip
                # rather than wedge the pop loop.
                continue
            if problem_name not in verified_problems:
                verified_problems[problem_name] = _verify_problem(
                    workspace, problem_name)
            if not verified_problems[problem_name]:
                continue
            pipeline_id = agent.new_pipeline_id()
            running.add((target_id, kind, decision_id))
            fut = pool.submit(_run_pipeline, workspace, manifests,
                              kind, target_id, target_kind, pipeline_id,
                              decision_id)
            futures[fut] = (pipeline_id, kind, target_id, target_kind,
                            decision_id)
            # Librarian per-file rows encode `problem\x1ffile` (#92); the
            # \x1f is non-printing, so render it readably in the log.
            _disp_prob, _disp_file = _lib_decode(target_id)
            _disp_tid = (f"{_disp_prob} file={_disp_file}"
                         if _disp_file else target_id)
            print(f"[dispatch] {kind} {target_kind}={_disp_tid} "
                  f"pid={pipeline_id[:8]}", flush=True)

        if once and not futures and db.pop_queue(conn) is None:
            print("[dispatcher] --once and queue empty, exit")
            pool.shutdown(wait=True)
            return 0

        # Idle exit: nothing in flight, queue empty, and bfs_refill found
        # nothing to dispatch (open_goals filter excludes shelved/orphan).
        # Means we'd just spin until budget — exit instead. Distinct from
        # root_proved exit above: this fires when goals have shelved or
        # all reachable goals are dead.
        #
        # `open_goals` is SCOPED here. The unscoped form let a `--scope X`
        # run livelock forever whenever ANY other problem in the workspace
        # had an open goal (2026-06-12 P12: the only in-scope problem was
        # paused on awaiting_human, but brouwer's unrelated open goal kept
        # this check non-zero, so the daemon never exited and just burned
        # the periodic tree-write each tick). Goals whose problem is paused
        # on awaiting_human are not dispatchable (bfs_refill skips them), so
        # they're excluded from the "dispatchable" set too — and reported,
        # so silence on a paused problem doesn't read as a hang.
        dispatchable_open = db.dispatchable_open_goals(conn, scope=scope)
        if (not futures
                and db.queue_size(conn) == 0
                and len(dispatchable_open) == 0
                and len(db.strategies_ready_for_verify(conn)) == 0):
            paused_probs = sorted({
                str(g["problem"]) for g in db.open_goals(conn, scope=scope)
                if db.problem_has_awaiting_human(conn, str(g["problem"]))})
            if paused_probs:
                print(f"[dispatcher] {len(paused_probs)} problem(s) paused on "
                      f"awaiting_human — resolve the RequestUserAmend then "
                      f"re-run: {paused_probs}", flush=True)
            scoped_proved = db.root_proved(conn, scope=scope)
            print(f"[dispatcher] no dispatchable work, exiting "
                  f"(roots_proved={scoped_proved})", flush=True)
            pool.shutdown(wait=True)
            return 0 if scoped_proved else 1

        # Wait for any completion or tick
        if futures:
            wait(list(futures), timeout=TICK_TIMEOUT,
                 return_when=FIRST_COMPLETED)
        else:
            time.sleep(min(TICK_TIMEOUT, 5))

        # Periodic TREE.md refresh — cascade-only writes leave the tree
        # frozen during long Builder/Backward spawns (5-15min under LSP).
        # Restricted to `tree_problems` (in-scope for a scoped run). Cheap
        # render + atomic replace; failures are swallowed inside
        # tree.write_for_target's caller pattern but tree.write itself
        # raises, so guard here.
        for problem_name in tree_problems:
            try:
                tree.write(conn, workspace, problem_name)
            except Exception as exc:
                print(f"[tree] periodic write skipped for "
                      f"{problem_name}: {exc}", flush=True)

        if time.time() - start_time > budget_sec:
            print(f"[dispatcher] {budget_sec}s budget exceeded; stopping",
                  flush=True)
            _exit_pool_fast(pool)
            return 1


