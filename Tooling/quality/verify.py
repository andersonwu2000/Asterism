"""Strategy verification (verify-collapse design).

Per-level verify_strategy is now purely mechanical: rewrite the parent
goal file as an alias to the winning strategy's scratch theorem. No
Lean elaboration, no axiom probe. The integrity gate is a single
root-level `axiom_probe(Root.lean)` inside `library.maybe_promote`.

Why this is safe:

  - Builder leaf proofs are axiom-checked at Builder commit
    (`pipeline/builder.py` with `axioms_for=fq_name`).
  - Backward leaf-bypass proofs are axiom-checked at acceptance gate
    (`pipeline/backward.py:624-670` with `axioms_for=fq_name`).
  - Non-leaf strategy patches are compile-checked at Backward submit
    (`pipeline/backward.py:851` with `write_olean=True`). Axiom check
    at submit can't isolate strategy-own sorry from sorry-stub
    imports, so it's deferred to root verify after sub-goals alias-in.
  - `promote_to_alias` is pure mechanical string-template rewrite;
    the signature lock at Backward submit guarantees type compatibility.

Failure path: if root `axiom_probe` returns `rogue: [sorryAx]`, the
sole remaining sorry source is a non-leaf strategy patch. The dispatcher
hands off to `bisect_sorryax_source` (linear scan of 'succeeded'
strategies, deepest first, running `#print axioms` on each scratch
theorem) followed by `rollback_cascade_chain` which walks from culprit
to root, restoring each alias from its backup and reverting DB state.

Empirical justification: 0 cascade-level verify failures observed
across the collapse-design rollout's 26 runs + SG #19 (10 strategies)
+ PN run after refactor (5 strategies). The single-point gate matches
the actual failure rate without paying per-level Lean elaboration cost.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Literal

from ..state import db, manifest, tree
from ..pipeline._lake import lean_path_to_module
from ..pipeline._skeleton import (
    promote_to_alias, rollback_promote, verify_backup_path,
)


def verify_strategy(
    conn: sqlite3.Connection, *, workspace: Path, strategy_id: int,
    manifests: dict[str, manifest.Manifest] | None = None,
) -> Literal["proved", "dead", "superseded", "retry"]:
    """Mechanical promote — rewrite parent goal file as alias to the
    winning strategy's scratch theorem. No Lean elaboration; no axiom
    probe. Integrity is gated at root via `library.maybe_promote`.

    `manifests` is accepted for backward signature compatibility but
    unused here (axiom check moved to root).

    Returns:
      - "proved" on successful alias rewrite
      - "superseded" when the strategy was already settled
      - "dead" when scratch file is missing
      - "retry" no longer produced (kept in signature for forward-compat)
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

    # Rewrite parent stub as a re-export alias. Pure string
    # substitution; type correctness guaranteed by Backward's
    # submit-time signature lock. Backup retained on disk (keyed by
    # sid_token via `verify_backup_path`) — cleaned up at root verify
    # success in `cleanup_cascade_backups`, or consumed by rollback
    # on root verify failure in `rollback_cascade_chain`.
    parent_abs = workspace / s["lean_path"]
    sid_token = f"s{strategy_id}"
    scratch_module = lean_path_to_module(workspace, scratch_abs)
    annotation = (s["proposal_md"] or "")
    if annotation and not annotation.endswith("\n"):
        annotation += "\n"
    promote_to_alias(
        parent_abs,
        namespace=f"Problems.{s['goal_problem']}",
        slug=s["goal_slug"],
        sid_token=sid_token,
        scratch_module=scratch_module,
        annotation=annotation,
    )
    return "proved"


def verify_housekeeping(
    conn: sqlite3.Connection, *, workspace: Path, max_iters: int = 8,
    manifests: dict[str, manifest.Manifest] | None = None,
) -> dict[str, int]:
    """Run inline at the end of each dispatcher tick. Polls strategies
    in `ready_for_verify` state, runs `verify_strategy` on each, and
    applies state transitions. When a goal becomes proved its parent
    strategy may itself become ready — loops up to `max_iters` chain
    depth.

    Single-threaded by design — running serially within the dispatcher
    main loop sidesteps the OR-parallel race the legacy pipeline path
    fenced via `busy_parents`. Each strategy's full transition commits
    before the next is processed.

    After the loop, each problem whose goal/strategy state changed gets
    one TREE.md refresh. Without this, verify-side status flips
    (attempting→proved via _set_goal_terminal_and_propagate, downward
    cascade-shelve on disprove/dead) never reach TREE.md — only
    cascade_one writes the tree, and verify-driven transitions don't
    pass through cascade_one. Strategist reads TREE.md inline into
    its Context.md; a stale TREE.md misled Strategist #115 (residue_thm
    2026-05-20) into emitting Noop while the homotopy subtree had
    already proved, contributing to a daemon idle-exit.
    """
    from ..core import dispatcher
    counts = {"proved": 0, "dead": 0, "superseded": 0, "retry": 0}
    touched_goals: set[int] = set()
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
            # 'retry' is no longer produced (verify_strategy doesn't
            # hit the gateway). Kept for forward-compat in case a
            # future change reintroduces transient infra failures.
            if outcome == "retry":
                counts["retry"] += 1
                print(f"[verify] Strategy={sid} → retry (transient infra)",
                      flush=True)
                _refresh_trees(conn, workspace, touched_goals)
                return counts
            if outcome == "proved":
                db.update_strategy_status(conn, sid, "succeeded")
                dispatcher._set_goal_terminal_and_propagate(
                    conn, goal_id, "proved")
                db.mark_other_strategies_superseded(
                    conn, goal_id=goal_id, winner_id=sid,
                )
                conn.commit()
                counts["proved"] += 1
                touched_goals.add(goal_id)
                print(f"[verify] Strategy={sid} → proved", flush=True)
            elif outcome == "dead":
                db.update_strategy_status(conn, sid, "dead")
                n = db.increment_goal_attempts(conn, goal_id)
                if n >= dispatcher.SHELVE_THRESHOLD:
                    dispatcher._set_goal_terminal_and_propagate(
                        conn, goal_id, "shelved")
                    dispatcher._propagate_shelve(conn, goal_id)
                else:
                    has_live = conn.execute(
                        "SELECT 1 FROM strategies WHERE goal_id = ?"
                        " AND status = 'proposed' LIMIT 1",
                        (goal_id,),
                    ).fetchone()
                    if has_live is None:
                        db.update_goal_status(conn, goal_id, "open")
                conn.commit()
                counts["dead"] += 1
                touched_goals.add(goal_id)
                print(f"[verify] Strategy={sid} → dead", flush=True)
            else:  # "superseded"
                counts["superseded"] += 1
    _refresh_trees(conn, workspace, touched_goals)
    return counts


def _refresh_trees(conn: sqlite3.Connection, workspace: Path,
                   touched_goals: set[int]) -> None:
    """Write one TREE.md per problem whose state was touched by this
    housekeeping pass. Multiple touched goals in the same problem
    collapse to a single write (last-write-wins; the renderer reads
    fresh DB state). Errors swallowed inside `write_for_target`.
    """
    if not touched_goals:
        return
    placeholders = ",".join("?" * len(touched_goals))
    rows = conn.execute(
        f"SELECT DISTINCT problem FROM goals WHERE id IN ({placeholders})",
        list(touched_goals),
    ).fetchall()
    for r in rows:
        tree.write_for_target(conn, workspace, str(r["problem"]), "Problem")


def bisect_sorryax_source(
    conn: sqlite3.Connection, workspace: Path, problem: str,
) -> dict | None:
    """Root `axiom_probe` saw sorryAx in main's transitive closure. Walk
    the problem's 'succeeded' strategies (deepest goal first — leaves
    were already axiom-checked at their proof time so culprits live
    at non-leaf depths first) and run `#print axioms` on each scratch
    theorem to find the strategy whose own patch leaked sorryAx.

    Returns the strategy row as dict, or None if no culprit found
    (shouldn't happen if root probe reported sorryAx; if it does,
    indicates either a transient infra failure during bisect or a
    deeper framework bug).
    """
    from ..lsp import lifecycle as gateway_lifecycle
    strategies = conn.execute(
        "SELECT s.*, g.depth AS goal_depth, g.problem AS goal_problem,"
        "       g.slug AS goal_slug"
        " FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE g.problem = ? AND s.status = 'succeeded'"
        " ORDER BY g.depth DESC, s.id DESC",
        (problem,),
    ).fetchall()
    for s in strategies:
        scratch_path = s["scratch_path"]
        if not scratch_path:
            continue
        scratch_abs = workspace / scratch_path
        if not scratch_abs.exists():
            continue
        scratch_fq = f"Problems.{s['goal_problem']}.s{s['id']}"
        r = gateway_lifecycle.verify_file(
            scratch_abs, write_olean=False,
            axioms_for=scratch_fq, workspace=workspace,
        )
        if "error" in r:
            # Transient infra error during bisect — log + continue
            # rather than abort. Bisect can tolerate gaps.
            print(f"[bisect] strategy={s['id']} probe error: "
                  f"{r['error']}", flush=True)
            continue
        used = set(r.get("axioms") or [])
        if "sorryAx" in used:
            return dict(s)
    return None


def rollback_cascade_chain(
    conn: sqlite3.Connection, workspace: Path, culprit_strategy_id: int,
) -> int:
    """Bisect identified a strategy that leaked sorryAx. Walk the
    alias chain from culprit upward to root, restoring each parent
    file from its backup and reverting strategy/goal DB state.

    State transitions:
      - Culprit strategy → 'dead' (its proof was tainted; framework
        will re-Backward this goal on next dispatcher tick)
      - Culprit goal → 'open' (eligible for fresh Backward dispatch)
      - Each upstream strategy → 'proposed' (still alive, will re-verify
        once its sub-goals re-prove cleanly)
      - Each upstream goal → 'attempting' (its active strategy still
        exists, just needs verify again)
      - Siblings of any rolled-back strategy that were marked
        'superseded' → reverted to 'proposed' (alternatives back in play)

    Returns count of strategies rolled back.
    """
    rolled = 0
    visited: set[int] = set()
    cursor_strategy_id: int | None = culprit_strategy_id
    is_culprit = True
    touched_problem: str | None = None
    while cursor_strategy_id is not None and cursor_strategy_id not in visited:
        visited.add(cursor_strategy_id)
        s = conn.execute(
            "SELECT s.*, g.id AS g_id, g.problem AS problem,"
            "       g.slug AS slug"
            " FROM strategies s JOIN goals g ON g.id = s.goal_id"
            " WHERE s.id = ?", (cursor_strategy_id,)
        ).fetchone()
        if s is None:
            break
        touched_problem = str(s["problem"])
        # Restore parent file from this strategy's backup, if any
        parent_abs = workspace / s["lean_path"]
        sid_token = f"s{s['id']}"
        backup = verify_backup_path(parent_abs, sid_token)
        if backup.exists():
            rollback_promote(parent_abs, backup)
        # Revert state. Culprit goes dead; upstream goes back to
        # ready-for-verify (status='proposed' with sub-goals reverted
        # to attempting/open).
        if is_culprit:
            db.update_strategy_status(conn, s["id"], "dead")
            db.update_goal_status(conn, s["g_id"], "open")
        else:
            db.update_strategy_status(conn, s["id"], "proposed")
            db.update_goal_status(conn, s["g_id"], "attempting")
        # Un-supersede siblings on this goal (they were sidelined when
        # this strategy claimed the win; with the win revoked, they're
        # back in play).
        conn.execute(
            "UPDATE strategies SET status = 'proposed'"
            " WHERE goal_id = ? AND status = 'superseded' AND id != ?",
            (s["g_id"], s["id"]),
        )
        rolled += 1
        # Walk upward: find the strategy whose sub-goal is this
        # strategy's goal. There's at most one parent strategy per
        # goal (the active one); strategy_subgoals encodes this.
        parent_row = conn.execute(
            "SELECT strategy_id FROM strategy_subgoals"
            " WHERE subgoal_id = ?", (s["g_id"],)
        ).fetchone()
        if parent_row is None:
            break  # reached root
        cursor_strategy_id = int(parent_row["strategy_id"])
        is_culprit = False
    conn.commit()
    # TREE refresh — rollback walked one parent chain (all in the same
    # problem), so one write covers every touched goal. Caller's
    # subsequent re-Backward dispatch will overwrite this if it
    # advances state, but a fresh snapshot in between keeps any
    # operator status check / Strategist context inline-read honest.
    if touched_problem is not None:
        tree.write_for_target(conn, workspace, touched_problem, "Problem")
    return rolled


def cleanup_cascade_backups(
    conn: sqlite3.Connection, workspace: Path, problem: str,
) -> int:
    """Root verify succeeded — unlink all per-strategy backup files
    accumulated during cascade promotion. Returns count deleted."""
    rows = conn.execute(
        "SELECT s.id, s.lean_path FROM strategies s"
        " JOIN goals g ON g.id = s.goal_id"
        " WHERE g.problem = ? AND s.status = 'succeeded'",
        (problem,),
    ).fetchall()
    n = 0
    for r in rows:
        parent_abs = workspace / r["lean_path"]
        sid_token = f"s{r['id']}"
        backup = verify_backup_path(parent_abs, sid_token)
        if backup.exists():
            try:
                backup.unlink()
                n += 1
            except OSError:
                pass
    return n


FRAMEWORK_DEFAULT_AXIOMS: tuple[str, ...] = (
    "Classical.choice", "propext", "Quot.sound",
)
"""The three Lean kernel axioms accepted by default when a Manifest
does not set `axioms_whitelist`. sorryAx is deliberately excluded —
catching it is the entire reason this gate exists. Operators who
need additional axioms (e.g. `native_decide`, `Lean.ofReduceBool`)
must add them explicitly in the Manifest."""


def root_integrity_gate(
    conn: sqlite3.Connection, workspace: Path, problem: str,
    mfst: manifest.Manifest,
) -> None:
    """Single integrity gate that runs after a problem's root flips to
    'proved'. Under verify-collapse, per-level `verify_strategy` is
    mechanical (no Lean elaboration); the actual proof validation lives
    here. The probe ALWAYS runs once a root reaches 'proved' — framework
    behavior must not depend on whether the Manifest sets
    `axioms_whitelist`. When the Manifest omits it, fall back to
    `FRAMEWORK_DEFAULT_AXIOMS` (the 3 standard Lean axioms) and log a
    warning so the implicit fallback is operator-visible.

    Performs `axiom_probe(Problems.<p>.Root, main)` against the
    effective whitelist. On rogue-axiom failure (sorryAx leaked from a
    non-leaf strategy patch) invokes `bisect_sorryax_source` +
    `rollback_cascade_chain` to revert the cascade — framework cascade
    machinery will then re-Backward the culprit goal on the next
    dispatcher tick.

    Happy path: clean up cascade backups accumulated by
    `verify_strategy` during cascade promotion.

    No-op when root is not 'proved'.
    """
    from ..pipeline._axiom import axiom_probe
    row = conn.execute(
        "SELECT statement FROM goals "
        "WHERE problem = ? AND origin = 'root' AND status = 'proved' "
        "LIMIT 1",
        (problem,),
    ).fetchone()
    if row is None:
        return
    if mfst.axioms_whitelist:
        whitelist = list(mfst.axioms_whitelist)
    else:
        whitelist = list(FRAMEWORK_DEFAULT_AXIOMS)
        print(f"[integrity] {problem}: Manifest didn't set "
              f"axioms_whitelist; using framework default "
              f"{list(FRAMEWORK_DEFAULT_AXIOMS)}",
              flush=True)
    try:
        # 900s (15min) budget. Root.lean's transitive import chain can
        # be deep (SG: 23 sub-proofs, cold `lake env lean Root.lean`
        # takes ~8min), and `reconcile_proved_goals` upstream may have
        # just rewritten a batch of `proofs/L_*.lean` files —
        # invalidating their oleans and forcing Lean to re-elaborate
        # everything from source. Observed 2026-05-19 SG: probe ran
        # at default 180s right after reconcile rewrote 13 files,
        # gateway returned "no terminal snapshot:
        # headerProcessed.result? is none (import failed)" — not a
        # real import error, the worker just hadn't finished header
        # elaboration in 180s. The non-root axiom_probe sites (Builder
        # leaf-bypass, sub-goal stub promotion) keep 180s — their
        # files import the same chain only at depth 1.
        ok, axiom_msg = axiom_probe(
            workspace,
            fq_name=f"Problems.{problem}.main",
            module=f"Problems.{problem}.Root",
            whitelist=whitelist,
            timeout=900,
        )
    except Exception as e:
        print(f"[integrity] {problem}: probe error ({e})",
              flush=True, file=sys.stderr)
        return
    if not ok:
        print(f"[integrity] {problem}: skip — {axiom_msg}", flush=True)
        if "rogue axioms" in axiom_msg or "sorryAx" in axiom_msg:
            culprit = bisect_sorryax_source(conn, workspace, problem)
            if culprit is None:
                print(f"[integrity] {problem}: sorryAx detected at root "
                      f"but bisect found no source — manual investigation "
                      f"required", flush=True, file=sys.stderr)
                return
            rolled = rollback_cascade_chain(
                conn, workspace, int(culprit["id"]))
            print(f"[integrity] {problem}: rolled back {rolled} "
                  f"strategy/goal pair(s) after sorryAx in "
                  f"strategy={culprit['id']} (goal "
                  f"{culprit['goal_slug']})", flush=True)
        return
    # Happy path — mark the root verified so the dispatcher gate skips
    # it on subsequent ticks (without this every loop iteration paid
    # one gateway-driven axiom_probe per proved root → 244 miniF2F
    # benchmark roots stalled dispatch for ~115min on every restart).
    root_id = conn.execute(
        "SELECT id FROM goals"
        " WHERE problem = ? AND origin = 'root' AND status = 'proved'"
        " LIMIT 1",
        (problem,),
    ).fetchone()
    if root_id is not None:
        db.set_integrity_verified(conn, int(root_id["id"]))
    print(f"[integrity] {problem}: root axioms ok {axiom_msg}", flush=True)
    n = cleanup_cascade_backups(conn, workspace, problem)
    if n:
        print(f"[integrity] {problem}: cleaned {n} cascade backup(s)",
              flush=True)
