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

Empirical justification (as of the rollout): 0 cascade-level verify
failures observed across the collapse-design rollout's 26 runs + SG #19
(10 strategies) + PN run after refactor (5 strategies).

2026-08-30 (owner ruling, task #231): that justification did not
survive union_closed's first full cold build — 4,828 proved bricks, of
which an alias's own elaboration blew maxRecDepth and several
strategies cited helper decls a promotion had dropped from a sub-goal
stub (seven consumers at one promotion), plus one import cycle a
promotion closed. Per-level promotion is therefore a GATE now: the
alias module and every live strategy importing the promoted goal are
cold-built (`PromotionGate`, off the main thread, through the lake
build lease) before the status flips; the failing module names the
culprit (alias → this promotion is undone; consumer → that consumer
rolls back via `rollback_cascade_chain`). `asterism catalog-verify`
is the standing full cold build; `assemble.extra_decls` keeps helper
decls out of stubs at Backward commit.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path
from typing import Literal, TYPE_CHECKING

from ..state import db, proof_store, thresholds, transitions, tree
from ..state import intent as intent_mod
from ..pipeline._lake import lean_path_to_module

if TYPE_CHECKING:
    from ..pipeline._olean_warm import OleanWarmer
from ..pipeline._skeleton import (
    promote_to_alias, rollback_promote, verify_backup_path,
)


def verify_strategy(
    conn: sqlite3.Connection, *, workspace: Path, strategy_id: int,
    intents: dict[str, intent_mod.ProblemIntent] | None = None,
) -> Literal["proved", "dead", "superseded", "retry"]:
    """Mechanical promote — rewrite parent goal file as alias to the
    winning strategy's scratch theorem. No Lean elaboration; no axiom
    probe. Integrity is gated at root via `library.maybe_promote`.

    `intents` is accepted for backward signature compatibility but
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

    # Second-line sorry tripwire (2026-05-26, post-Jordan): even though
    # Backward's submit-time `assembly_gate_check_sorry` already rejects
    # sorry-bearing patches, the strategy file may be subsequently
    # rewritten (by operator recovery scripts, by manual edit, by a
    # future framework path). Re-checking here means mechanical promote
    # is never invoked on a sorry-bearing source — the contract that
    # `promote_to_alias` produces an alias to a real proof stays intact.
    # On hit, mark the strategy dead so the parent goal re-enters the
    # dispatch loop (rather than silently aliasing to a stub).
    from ..pipeline._assembly import assembly_gate_check_sorry
    ok, msg = assembly_gate_check_sorry(scratch_abs)
    if not ok:
        transitions.apply_strategy_transition(
            conn, strategy_id, "dead", event="assembly_sorry_gate")
        conn.commit()
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
    try:
        scratch_text = scratch_abs.read_text(encoding="utf-8")
    except OSError:
        scratch_text = ""
    promote_to_alias(
        parent_abs,
        namespace=f"Problems.{s['goal_problem']}",
        slug=s["goal_slug"],
        sid_token=sid_token,
        scratch_module=scratch_module,
        annotation=annotation,
        # BUG4 residual: the strategy decl is the `noncomputable`
        # authority — a stub the agent forgot to mark must not produce
        # a cold-broken alias (sphere suspension iso, 2026-07-04).
        scratch_text=scratch_text,
    )
    return "proved"


# ── the promotion cold-build gate (owner ruling 2026-08-30, task #231) ──
#
# `verify_strategy` is a string rewrite; nothing elaborates the alias or
# the strategies that import the promoted goal. The 2026-08-30 full cold
# build found both failing: an alias whose own elaboration blows
# maxRecDepth, and consumers of a sub-goal whose stub helpers the rewrite
# dropped (seven at one promotion). The status flip now waits for a cold
# `lake build` of the alias module plus every live consumer strategy —
# run off the main thread by `PromotionGate` — and the failing MODULE
# names the culprit: the alias → this promotion is undone; a consumer →
# that consumer is rolled back and the promotion retried without it.

_BUILD_ERROR_PATH_RE = re.compile(r"^error:\s+(\S+?\.lean)(?::\d+:\d+)?:", re.MULTILINE)


def failing_modules_from_build_output(output: str) -> list[str]:
    """Module names of every `error: <path>.lean…` line in lake output,
    in first-seen order (an import-cycle line names the module too)."""
    seen: list[str] = []
    for m in _BUILD_ERROR_PATH_RE.finditer(output or ""):
        rel = m.group(1).replace("\\", "/")
        mod = rel[:-len(".lean")].replace("/", ".")
        if mod not in seen:
            seen.append(mod)
    return seen


def promotion_modules(conn: sqlite3.Connection, workspace: Path, *,
                      strategy_id: int) -> list[str]:
    """What the gate builds for a promotion: the promoted goal's own
    module (the alias) and the scratch module of every LIVE strategy that
    lists that goal as a sub-goal — those files import it."""
    s = conn.execute(
        "SELECT s.goal_id, s.lean_path FROM strategies s WHERE s.id = ?",
        (int(strategy_id),)).fetchone()
    if s is None:
        return []
    mods = [lean_path_to_module(workspace, workspace / s["lean_path"])]
    for r in conn.execute(
            "SELECT c.scratch_path FROM strategy_subgoals ss"
            " JOIN strategies c ON c.id = ss.strategy_id"
            " WHERE ss.subgoal_id = ? AND c.scratch_path IS NOT NULL"
            "   AND c.status IN ('proposed', 'ready_for_verify', 'succeeded')"
            " ORDER BY c.id", (int(s["goal_id"]),)):
        mod = lean_path_to_module(workspace, workspace / r["scratch_path"])
        if mod not in mods:
            mods.append(mod)
    return mods


def _strategy_for_module(conn: sqlite3.Connection, module: str) -> "int | None":
    rel = module.replace(".", "/") + ".lean"
    r = conn.execute("SELECT id FROM strategies WHERE scratch_path = ?"
                     " ORDER BY id DESC LIMIT 1", (rel,)).fetchone()
    return int(r["id"]) if r else None


def _flip_proved(conn: sqlite3.Connection, *, sid: int, goal_id: int,
                 counts: dict, touched_goals: set) -> None:
    from ..core import dispatcher
    transitions.apply_strategy_transition(
        conn, sid, "succeeded", event="verify_proved")
    dispatcher._set_goal_terminal_and_propagate(
        conn, goal_id, "proved",
        receipt=transitions.ProvedReceipt(
            "verify_collapse", f"strategy s{sid} all-subs-proved"))
    db.mark_other_strategies_superseded(conn, goal_id=goal_id, winner_id=sid)
    conn.commit()
    counts["proved"] += 1
    touched_goals.add(goal_id)
    print(f"[verify] Strategy={sid} → proved", flush=True)


def _strategy_dead(conn: sqlite3.Connection, *, sid: int, goal_id: int,
                   counts: dict, touched_goals: set,
                   promotion: bool = False) -> None:
    """The `dead` outcome: strategy dead; the goal reopens unless a live
    sibling still runs or the attempt threshold hands it to review.
    `promotion=True` is the cold-build gate's verdict (its own event
    labels — the literal calls below are what the taxonomy scan reads)."""
    from ..core import dispatcher
    if promotion:
        transitions.apply_strategy_transition(
            conn, sid, "dead", event="promotion_build_failed")
    else:
        transitions.apply_strategy_transition(
            conn, sid, "dead", event="verify_dead")
    n = db.increment_goal_attempts(conn, goal_id)
    if transitions.has_live_sibling(conn, goal_id):
        pass
    elif n >= thresholds.SHELVE_THRESHOLD:
        dispatcher._enqueue_strategist_review(conn, goal_id)
    elif promotion:
        transitions.apply_goal_transition(
            conn, goal_id, "open", event="promotion_build_failed")
    else:
        transitions.apply_goal_transition(
            conn, goal_id, "open", event="verify_reopen")
    conn.commit()
    counts["dead"] += 1
    touched_goals.add(goal_id)


def _settle_promotion(conn: sqlite3.Connection, workspace: Path, res,
                      *, counts: dict, touched_goals: set) -> None:
    """Consume one gate result on the main thread."""
    s = conn.execute(
        "SELECT s.id, s.goal_id, s.lean_path, s.status FROM strategies s"
        " WHERE s.id = ?", (int(res.strategy_id),)).fetchone()
    # Readiness is DERIVED (`db.strategies_ready_for_verify`: all subs
    # proved, parent alive) — the row itself still says 'proposed'.
    if s is None or s["status"] not in ("proposed", "ready_for_verify"):
        return  # settled by another path meanwhile (superseded / rolled back)
    sid, goal_id = int(s["id"]), int(s["goal_id"])
    if res.ok:
        _flip_proved(conn, sid=sid, goal_id=goal_id, counts=counts,
                     touched_goals=touched_goals)
        return
    alias_mod = lean_path_to_module(workspace, workspace / s["lean_path"])
    culprits = list(res.failing_modules or [])
    consumer_culprits = [m for m in culprits if m != alias_mod]
    for mod in consumer_culprits:
        cid = _strategy_for_module(conn, mod)
        if cid is not None and cid != sid:
            print(f"[verify] promotion gate: consumer {mod} no longer builds "
                  f"→ rollback_cascade_chain(s{cid})", flush=True)
            rollback_cascade_chain(conn, workspace, cid)
            touched_goals.add(goal_id)
    if alias_mod in culprits or not culprits:
        parent_abs = workspace / s["lean_path"]
        backup = verify_backup_path(parent_abs, f"s{sid}")
        if backup.exists():
            rollback_promote(parent_abs, backup)
        print(f"[verify] Strategy={sid} → dead (promotion gate: "
              f"{alias_mod} does not build)", flush=True)
        _strategy_dead(conn, sid=sid, goal_id=goal_id, counts=counts,
                       touched_goals=touched_goals, promotion=True)
    # consumers-only failure: this promotion stands and is re-verified
    # (re-submitted) by the loop below without the rolled-back consumer


def verify_housekeeping(
    conn: sqlite3.Connection, *, workspace: Path, max_iters: int = 8,
    intents: dict[str, intent_mod.ProblemIntent] | None = None,
    olean_warmer: "OleanWarmer | None" = None,
    promotion_gate=None,
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
    cascade-shelve on a disproof or a wrong-context park) never reach
    TREE.md — only
    cascade_one writes the tree, and verify-driven transitions don't
    pass through cascade_one. Strategist reads TREE.md inline into
    its Context.md; a stale TREE.md misled Strategist #115 (residue_thm
    2026-05-20) into emitting Noop while the homotopy subtree had
    already proved, contributing to a daemon idle-exit.
    """
    from ..core import dispatcher
    transitions.assert_main_thread("verify_housekeeping")
    gate = promotion_gate if promotion_gate is not None else olean_warmer
    counts = {"proved": 0, "dead": 0, "superseded": 0, "retry": 0,
              "revived": 0, "pending": 0}
    touched_goals: set[int] = set()
    # Gate results first (2026-08-30): a promotion submitted on an earlier
    # tick flips or rolls back here, on the main thread.
    if gate is not None:
        for res in gate.drain_results():
            _settle_promotion(conn, workspace, res, counts=counts,
                              touched_goals=touched_goals)
    for _ in range(max_iters):
        ready = [s for s in db.strategies_ready_for_verify(conn)
                 if gate is None or not gate.pending(int(s["id"]))]
        revivals = _pending_shelved_revivals(conn)
        if not ready and not revivals:
            break
        for s in ready:
            sid = int(s["id"])
            goal_id = int(s["goal_id"])
            outcome = verify_strategy(
                conn, workspace=workspace, strategy_id=sid,
                intents=intents,
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
                if gate is None:
                    # No gate (unit tests / in-process callers): the
                    # pre-2026-08-30 immediate flip.
                    _flip_proved(conn, sid=sid, goal_id=goal_id,
                                 counts=counts, touched_goals=touched_goals)
                else:
                    # The alias is on disk; the status waits for the cold
                    # build of it and its consumers. Off the main thread
                    # (the #64 lesson: a 10-strategy cascade × 30-60 s
                    # inline build blocked the dispatcher for ~10 min);
                    # the result lands on a later tick via drain_results.
                    mods = promotion_modules(conn, workspace, strategy_id=sid)
                    gate.submit(sid, mods)
                    counts["pending"] += 1
                    print(f"[verify] Strategy={sid} → promotion gate "
                          f"({len(mods)} module(s))", flush=True)
            elif outcome == "dead":
                # Sibling strategy still in flight (e.g. Strategist
                # parallel inject): `_strategy_dead` defers the terminal
                # so we don't kill working work mid-flight — mirrors
                # `_kill_upward_chain`'s deferred-terminal branch.
                _strategy_dead(conn, sid=sid, goal_id=goal_id,
                               counts=counts, touched_goals=touched_goals)
                print(f"[verify] Strategy={sid} → dead", flush=True)
            else:  # "superseded"
                counts["superseded"] += 1
        # G1 shelved-revival pass (post-strategy housekeeping). Forward
        # commit links a shelved goal S to a newly-produced Forward
        # output X via `S.alias_target_id = X`. Once X transitions to
        # 'proved' (via the strategy pass above, or via a prior
        # iteration / pipeline), generate S's alias body, rewrite its
        # lean file, and flip S → proved. The outer loop's next
        # iteration picks up parent strategies whose remaining sub-goal
        # constraint was the now-revived S, chaining naturally up the
        # tree. Without this, S sits shelved forever even after a
        # functionally-identical lemma proves (brouwer 2026-05-22
        # G1 incident).
        for s_id, x_id in revivals:
            ok = _revive_shelved_alias(
                conn, workspace,
                shelved_id=s_id, canonical_id=x_id,
            )
            if ok:
                counts["revived"] += 1
                touched_goals.add(s_id)
                print(f"[verify] shelved-revival: g{s_id} ← g{x_id}",
                      flush=True)
    _refresh_trees(conn, workspace, touched_goals)
    return counts


def _pending_shelved_revivals(
    conn: sqlite3.Connection,
) -> list[tuple[int, int]]:
    """Return (shelved_goal_id, canonical_goal_id) pairs where the
    shelved goal aliases to an already-proved canonical and hasn't been
    revived yet. Ordered by shelved goal id for determinism.
    """
    rows = conn.execute(
        "SELECT s.id AS s_id, s.alias_target_id AS x_id"
        " FROM goals s"
        " JOIN goals x ON x.id = s.alias_target_id"
        " WHERE s.status = 'shelved'"
        "   AND s.alias_target_id IS NOT NULL"
        "   AND x.status = 'proved'"
        " ORDER BY s.id"
    ).fetchall()
    return [(int(r["s_id"]), int(r["x_id"])) for r in rows]


def _revive_shelved_alias(
    conn: sqlite3.Connection, workspace: Path, *,
    shelved_id: int, canonical_id: int,
) -> bool:
    """Generate the alias body for shelved goal S delegating to
    canonical goal X, write it to S.lean_path, and flip S → proved.

    Returns True on successful revival, False if any pre-condition fails
    (S or X missing, X has no extractable theorem name, S.lean_path
    unreadable, etc.) — fail-open so a malformed link never blocks the
    rest of housekeeping.
    """
    from . import dedupe as _dedupe
    from ..core import dispatcher
    s_row = conn.execute(
        "SELECT lean_path FROM goals WHERE id = ?", (shelved_id,),
    ).fetchone()
    x_row = conn.execute(
        "SELECT lean_path FROM goals WHERE id = ?", (canonical_id,),
    ).fetchone()
    if s_row is None or x_row is None:
        return False
    s_abs = workspace / s_row["lean_path"]
    x_abs = workspace / x_row["lean_path"]
    try:
        s_text = s_abs.read_text(encoding="utf-8")
        x_text = x_abs.read_text(encoding="utf-8")
    except OSError:
        return False
    x_thm = _dedupe._extract_theorem_name(x_text)
    if not x_thm:
        return False
    try:
        x_module = lean_path_to_module(workspace, x_abs)
    except (ValueError, OSError):
        return False
    if not _dedupe._SORRY_BODY_RE.search(s_text):
        # S's body isn't a fresh `:= by sorry` stub. Two cases (task #11
        # crash-window audit, B1):
        #   1. The file already IS this revival's own alias — the exact
        #      delegation + import `build_alias_content` emits for THIS
        #      canonical. That is our own half-write: a prior revival
        #      crashed between the file write and the proved flip, and the
        #      old blanket refusal turned the crash window into a PERMANENT
        #      wedge (goal stuck shelved, parent strategy never ready, the
        #      revival re-scanned and re-refused every tick). Resume
        #      idempotently: skip the (identical) rewrite and fall through
        #      to the same build-verify + flip every fresh revival runs —
        #      the soundness gates are unchanged.
        #   2. Anything else (manual edit, partial proof, already
        #      promoted): refuse to overwrite arbitrary content; the link
        #      stays so an operator can inspect.
        is_own_alias = (
            f"import {x_module}" in s_text
            and f":= by apply {x_thm} <;> assumption" in s_text
        )
        if not is_own_alias:
            return False
        print(f"[verify] shelved-revival g{shelved_id} ← g{canonical_id}: "
              f"file already carries this revival's alias (crashed prior "
              f"attempt) — resuming build-verify + flip", flush=True)
        new_text = s_text
    else:
        new_text = _dedupe.build_alias_content(
            original_content=s_text,
            canonical_module=x_module,
            canonical_slug=x_thm,
        )
        if new_text == s_text:
            return False
    try:
        # Through the chokepoint: atomic (torn-write-safe) + ownership-guarded.
        # S owns its own lean_path so the guard passes by construction; a
        # ClobberError here means the DB says otherwise — real drift, refuse.
        proof_store.place_proof(conn, workspace, goal_id=shelved_id,
                                rel_path=s_row["lean_path"], content=new_text)
    except (OSError, proof_store.ClobberError) as e:
        print(f"[verify] shelved-revival g{shelved_id} ← g{canonical_id} "
              f"write refused: {e}", flush=True)
        return False
    # Build-verify the revived alias before flipping S to 'proved'. Same
    # rationale as the Backward alias-placement site: the dedupe probe
    # (`_batch_provable_via_apply`) elaborates in a `dedupe_check`
    # namespace without the problem's namespace/opens, so its verdict can
    # diverge from the real build (BT 2026-05-29). Trusting the probe here
    # wrote 9 invalid g3322 aliases that were flipped 'proved' but didn't
    # build. Restore the sorry-stub and keep S shelved on failure so the
    # link can be retried / inspected rather than recording a false proof.
    from ..lsp import lifecycle as gateway_lifecycle
    av = gateway_lifecycle.verify_file(
        s_abs, write_olean=True, workspace=workspace)
    if not (av.get("ok") and not av.get("error")):
        why = av.get("error") or "; ".join(
            d.get("message", "")
            for d in (av.get("diagnostics") or [])
            if d.get("severity") == "error"
        ) or "alias body failed to build"
        print(f"[verify] shelved-revival g{shelved_id} ← g{canonical_id} "
              f"REJECTED — build-verify failed ({why[:160]}); "
              f"restoring stub, staying shelved", flush=True)
        try:
            proof_store.place_proof(conn, workspace, goal_id=shelved_id,
                                    rel_path=s_row["lean_path"],
                                    content=s_text)
        except (OSError, proof_store.ClobberError):
            pass
        return False
    dispatcher._set_goal_terminal_and_propagate(
        conn, shelved_id, "proved",
        receipt=transitions.ProvedReceipt(
            "alias_induction",
            f"G1 revival: canonical g{canonical_id} proved+receipted; "
            f"alias body build-verified"))
    conn.commit()
    # .olean materialization deferred to dedupe site (see strategy-pass
    # comment above for rationale).
    return True


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
            transitions.apply_strategy_transition(
                conn, s["id"], "dead", event="rollback_culprit")
            transitions.apply_goal_transition(
                conn, s["g_id"], "open", event="rollback_culprit")
        else:
            transitions.apply_strategy_transition(
                conn, s["id"], "proposed", event="rollback_upstream")
            transitions.apply_goal_transition(
                conn, s["g_id"], "attempting", event="rollback_upstream")
        # Un-supersede siblings on this goal (they were sidelined when
        # this strategy claimed the win; with the win revoked, they're
        # back in play).
        for sib in conn.execute(
            "SELECT id FROM strategies"
            " WHERE goal_id = ? AND status = 'superseded' AND id != ?",
            (s["g_id"], s["id"]),
        ).fetchall():
            transitions.apply_strategy_transition(
                conn, int(sib["id"]), "proposed", event="rollback_unsupersede")
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
    # Problem FSM §2.1 `revoked` (2026-07-12, splits the old auto edge):
    # post-Ingest un-prove ANNOUNCES the incident automatically — tear
    # the seal, un-harvest, quarantine — but re-entering the grind is
    # the OPERATOR's call (`asterism revive`), not the machine's:
    # `ingested_at` stays SET so every liveness reader (stall/T4/exit/
    # stale-row drop) keeps the problem quiet, and the machine never
    # silently resumes burning quota over a torn human signature.
    if (touched_problem is not None
            and db.problem_ingested(conn, touched_problem)):
        db.set_ingest_signoff_pending(conn, touched_problem, False)
        # the signature sealed content whose proof just un-proved — a
        # revoked judgment must not keep wearing its seal (v27)
        db.set_ingest_signoff(conn, touched_problem, None)
        from ..state import transitions as _transitions
        _transitions.apply_problem_transition(
            conn, touched_problem, "revoked", event="unprove_revoked")
        print(f"[rollback] {touched_problem}: Ingest REVOKED "
              f"(post-Ingest un-prove) — seal torn, Library un-harvested, "
              f"problem QUARANTINED. Re-enter with "
              f"`asterism revive {touched_problem}` after adjudicating.",
              flush=True)
        from ..pipeline.librarian import un_harvest as _un_harvest
        _un_harvest(conn, workspace, touched_problem)
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


# SoT moved to state/intent.py (the intent owns whitelist semantics);
# re-exported here for the existing importers (dispatcher, tests).
FRAMEWORK_DEFAULT_AXIOMS = intent_mod.FRAMEWORK_DEFAULT_AXIOMS


def _root_statement_pin_ok(
    conn: sqlite3.Connection, problem: str, root_row,
    current: str, base_body: str,
) -> tuple[bool, str]:
    """Task #120: Root.lean legitimately changes when the framework
    lands the root proof — Builder writes the assembled proof onto the
    root's lean_path, Verify promote / prune reconcile write the
    def-alias form. The USER contract is the `theorem main` statement,
    not the file bytes, so a changed Root.lean is accepted iff the
    pinned statement provably still governs what was proved:

      1. the pinned baseline parses as the hand-authored stub shape and
         `goals.statement` (the text every prover commit gate locked
         signatures against) still equals its statement; AND
      2. the current file is one of the sanctioned proof shapes bound
         to that statement — a `theorem main : <pinned stmt> :=`
         declaration carrying the statement byte-for-byte, or a
         def-alias `def main := @Problems.<p>.s<N>` whose s<N> is this
         root's own 'succeeded' strategy (its decl signature was locked
         to goals.statement at commit, so the alias copies exactly that
         type at elaboration).

    Everything else — statement text edited, an alias citing a foreign
    strategy, a sketch baseline — stays a violation (fail-closed; the
    operator escape hatch remains `asterism repin`). Defs.lean has no
    sanctioned framework writer and keeps the whole-file pin."""
    base_stmt = intent_mod.extract_root_statement(base_body)
    if base_stmt is None:
        return False, ("baseline is not the `theorem main : <stmt> := "
                       "by sorry` shape, so only byte-identity can "
                       "certify it")
    if str(root_row["statement"]).strip() != base_stmt:
        return False, ("goals.statement no longer matches the pinned "
                       "baseline statement")
    if re.search(r"theorem\s+main\s*:\s*" + re.escape(base_stmt)
                 + r"\s*:=", current):
        return True, ""
    m = re.search(r"def\s+main\s*:=\s*@Problems\." + re.escape(problem)
                  + r"\.s(\d+)\b", current)
    if m:
        sid = int(m.group(1))
        srow = conn.execute(
            "SELECT goal_id, status FROM strategies WHERE id = ?",
            (sid,)).fetchone()
        if (srow is not None
                and int(srow["goal_id"]) == int(root_row["id"])
                and str(srow["status"]) == "succeeded"):
            return True, ""
        return False, (f"def-alias cites s{sid}, which is not this "
                       f"root's succeeded strategy")
    return False, ("the rewritten file carries neither the pinned "
                   "statement nor a sanctioned def-alias")


def root_integrity_gate(
    conn: sqlite3.Connection, workspace: Path, problem: str,
    intent: intent_mod.ProblemIntent,
) -> None:
    """Single integrity gate that runs after a problem's root flips to
    'proved'. Under verify-collapse, per-level `verify_strategy` is
    mechanical (no Lean elaboration); the actual proof validation lives
    here. The probe ALWAYS runs once a root reaches 'proved' — framework
    behavior must not depend on whether the problem sets
    `axioms_whitelist`. When the setting is absent, fall back to
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
        "SELECT id, statement FROM goals "
        "WHERE problem = ? AND origin = 'root' AND status = 'proved' "
        "LIMIT 1",
        (problem,),
    ).fetchone()
    if row is None:
        return
    # User-file baseline pin (self-audit 2026-07-12 §3-3): a proved root
    # verifies only if Root.lean / Defs.lean still match their first-load
    # baseline (or the latest operator `asterism repin`). This is the
    # mechanical equality between "proved" and the ORIGINAL contract —
    # the write-deny blocks the honest tool path, this catches every
    # other channel (Bash, operator forgetting to re-init after an
    # edit). Cheap sha compare, runs BEFORE the 15-min axiom probe, so a
    # tampered root re-warns each tick at near-zero cost and never
    # flips integrity_verified. Root.lean additionally gets the task-#120
    # statement pin (`_root_statement_pin_ok`): the framework's own
    # proof-landing writers rewrite the proof BODY of the root file, and
    # the user contract is the statement, not the file bytes.
    pdir = db.problem_dir(workspace, problem)
    for fname in ("Root.lean", "Defs.lean"):
        fpath = pdir / fname
        if not fpath.is_file():
            continue
        base = intent_mod.user_file_baseline_row(conn, problem, fname)
        if base is None:
            print(f"[integrity] {problem}: no baseline recorded for "
                  f"{fname} (pre-v28 run) — statement pin skipped",
                  flush=True)
            continue
        pin = str(base["sha"])
        try:
            text = fpath.read_text(encoding="utf-8")
        except OSError as e:
            print(f"[integrity] {problem}: {fname} unreadable ({e}) — "
                  f"root NOT verified", flush=True, file=sys.stderr)
            return
        cur = intent_mod._content_sha(text)
        if cur == pin:
            continue
        why = "the proved root does not certify the original statement"
        if fname == "Root.lean":
            ok, why = _root_statement_pin_ok(
                conn, problem, row, text, str(base["body"]))
            if ok:
                continue
        print(f"[integrity] {problem}: {fname} content differs from "
              f"its baseline (pin {pin}, now {cur}) — {why}. Root "
              f"stays UNVERIFIED. If the change is yours: re-init, "
              f"or acknowledge with `asterism repin {problem}`.",
              flush=True, file=sys.stderr)
        return
    whitelist = intent_mod.effective_axioms(intent, problem=problem)
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
        # Phase 6 — the root-proved-auto Librarian trigger that lived here
        # is RETIRED: harvest is strictly Ingest-driven now (the Strategist
        # commits the terminal judgment; sign-off gates the enqueue). A
        # proved root merely makes the problem stall-when-idle, which wakes
        # the Strategist to judge the charter and commit Ingest.
    print(f"[integrity] {problem}: root axioms ok {axiom_msg}", flush=True)
    n = cleanup_cascade_backups(conn, workspace, problem)
    if n:
        print(f"[integrity] {problem}: cleaned {n} cascade backup(s)",
              flush=True)
