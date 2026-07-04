"""Centralised goal/strategy state-transition gateway (framework backlog #11).

Single source of truth for

  1. the canonical goal.status / strategy.status vocabularies (mirrors the
     CHECK enums in `db.SCHEMA`, bound to them by `test_transitions.py`), and
  2. the *legal* (from -> to) edge set, and
  3. the ONLY sanctioned mutators of those two columns:
     `apply_goal_transition` / `apply_strategy_transition`.

Why this module exists
----------------------
Before #11, goal/strategy status was mutated from ~32 call sites spread over
six modules (dispatcher / verify / strategist / backward / forward / db), each
encoding its own (event -> transition) rule. An audit (2026-06-22) found the
*current* behaviour consistent — but only because every past patch was made
carefully under a feature freeze. As new features land, an unchecked write is
one careless edit away from an illegal edge that no test would catch.

Routing every status write through one validated chokepoint converts
"scattered, hope-it-stays-consistent" into "centralised, test-enforced": an
edge that is not declared in `GOAL_EDGES` / `STRATEGY_EDGES` trips the
exhaustiveness sweep in CI (strict mode) and is logged loudly at runtime.

Strict vs. lenient
------------------
- Tests / CI set `ASTERISM_STRICT_TRANSITIONS=1`: an undeclared edge raises
  `IllegalTransition`, so the full suite (which exercises every cascade /
  verify branch) proves the registry is complete and that no code path emits
  an edge outside it.
- Production (daemon) defaults to lenient: an undeclared edge is logged with a
  `[transition-violation]` marker but the write still happens. Rationale —
  the registry is proven complete by CI, so this "can't fire" in practice; if
  some untested path ever sneaks one through, a loud log beats crashing the
  daemon mid-cascade and leaving the DB half-mutated (CLAUDE.md rule 5: loud
  signal, not a hard stop on a live proof run).

This module imports only `db` (a leaf) — it must stay free of `core` /
`pipeline` imports so it can be imported from anywhere without a cycle.
"""

from __future__ import annotations

import os
import sqlite3

from . import db

# ---------------------------------------------------------------------------
# Canonical state vocabularies (SoT — schema CHECK enums are bound to these by
# test_transitions.py::test_schema_enums_match_canonical_states).
# ---------------------------------------------------------------------------

GOAL_STATES: frozenset[str] = frozenset({
    "open",
    "attempting",
    "proved",
    "shelved",
    "pending_strategist_review",
    "disproved",
    "frozen",
    "dead",
})

STRATEGY_STATES: frozenset[str] = frozenset({
    "proposed",
    "succeeded",
    "dead",
    "superseded",
    "stalled",
})

# Terminal classes (referenced by cascade/propagation guards). A *hard*
# terminal is never downgraded to a softer one (`proved` is a finished proof;
# `disproved`/`dead` are stronger negatives than `shelved`).
GOAL_HARD_TERMINALS: frozenset[str] = frozenset({"proved", "disproved", "dead"})
GOAL_TERMINALS: frozenset[str] = GOAL_HARD_TERMINALS | {"shelved"}
STRATEGY_TERMINALS: frozenset[str] = frozenset({"succeeded", "dead", "superseded"})

# ---------------------------------------------------------------------------
# Legal (from -> to) edge registry.
#
# Idempotent self-edges (from == to) are ALWAYS allowed and are not listed.
# Each edge is grouped by the semantic event that drives it; the inline tag is
# the canonical `event=` label callers pass to the apply_* mutators.
# ---------------------------------------------------------------------------

GOAL_EDGES: frozenset[tuple[str, str]] = frozenset({
    # --- goal proved (Builder/Backward/Forward success, verify promote) ---
    ("open", "proved"),                       # forward lemma / backward sorry-free
    ("attempting", "proved"),                 # verify promote / builder proved
    ("shelved", "proved"),                    # G1 shelved-alias revival
    ("pending_strategist_review", "proved"),  # revival while awaiting review

    # --- goal dispatched (worker picked up / backward decomposed) ---
    ("open", "attempting"),                   # bfs_refill / backward success has_live
    ("pending_strategist_review", "attempting"),

    # --- goal reopened (reset for a fresh attempt; no terminal reached) ---
    ("attempting", "open"),                   # strategy died, not exhausted
    ("shelved", "open"),                      # backward-revive / forward-reuse / strategist reopen
    ("pending_strategist_review", "open"),    # strategist Reopen / reconcile
    ("frozen", "open"),                       # strategist reopen of a frozen root
    ("proved", "open"),                       # rollback: culprit chain reverted
    ("proved", "attempting"),                 # rollback: non-culprit pre-verify state

    # --- goal soft-shelved (threshold / descendant cascade / drift park) ---
    ("open", "shelved"),
    ("attempting", "shelved"),
    ("pending_strategist_review", "shelved"),  # orphan-chain guard / ConfirmShelve

    # --- goal handed to Strategist (transitional, agent_shelved / exhausted) ---
    ("open", "pending_strategist_review"),
    ("attempting", "pending_strategist_review"),

    # --- goal hard-terminal (counterexample / wrong-context subtree) ---
    ("attempting", "disproved"),
    ("attempting", "dead"),
    ("open", "disproved"),
    ("open", "dead"),

    # --- bootstrap: root statement seeded but Defs not yet initialised ---
    ("open", "frozen"),
})

STRATEGY_EDGES: frozenset[tuple[str, str]] = frozenset({
    # --- strategy proved out (verify success) ---
    ("proposed", "succeeded"),
    # --- strategy killed (skeleton fail / agent fail / cascade inward+upward) ---
    ("proposed", "dead"),
    # --- OR-race: a sibling won, sideline this one ---
    ("proposed", "superseded"),
    # --- soft-park: all sub-goals settled, no hard-terminal sibling ---
    ("proposed", "stalled"),
    ("proposed", "succeeded"),  # batch reconcile resolve (db.reconcile_inject_outcomes)
    # --- revival: stalled/superseded strategy reactivated ---
    ("stalled", "proposed"),       # _commit_inject_redispatch un-stall parent
    ("superseded", "proposed"),    # rollback un-supersede sibling
    # --- axiom-probe rollback of a wrongly-promoted alias chain ---
    ("succeeded", "dead"),         # culprit strategy that leaked sorryAx
    ("succeeded", "proposed"),     # upstream strategy reverted for re-verify
})

# ---------------------------------------------------------------------------
# Checked mutators
# ---------------------------------------------------------------------------


# Event taxonomy — the SoT of the `event=` labels every apply_*_transition
# call passes. Grouped by the pipeline / mechanism that fires them. A test
# (test_transitions.py::test_event_labels_are_registered) scans the source and
# asserts the set of labels actually used equals this set, so introducing a new
# event is a single-point change here that CI enforces.
EVENTS: frozenset[str] = frozenset({
    # cascade_one (worker-result adapter) + propagation cluster
    "set_terminal", "descendant_cascade", "enqueue_review",
    "reopen_after_cascade", "reopen_after_strategy_loss",
    "backward_decomposed", "inward_kill", "parent_stall", "upward_kill",
    "sibling_won", "parent_shelved_race",
    # backward pipeline
    "skeleton_failed", "moot_retain", "agent_failed",
    "backward_alias_proved", "backward_sorryfree_proved", "backward_revive",
    # forward pipeline
    "forward_lemma_proved", "forward_alias_proved", "forward_reuse_revive",
    # strategist
    "strategist_reopen", "strategist_unstall",
    # verify housekeeping + axiom-probe rollback
    "verify_proved", "verify_dead", "verify_reopen", "assembly_sorry_gate",
    "rollback_culprit", "rollback_upstream", "rollback_unsupersede",
    # startup recovery — interrupted-cascade repair (task #11:
    # consistency.repair_unambiguous finishes the sibling sweep a crashed
    # cascade owed its live `proposed` strategies)
    "startup_terminal_parent_reconcile",
})


def has_live_sibling(conn: sqlite3.Connection, goal_id: int, *,
                     statuses: "tuple[str, ...]" = ("proposed",)) -> bool:
    """True iff `goal_id` has any strategy whose status is in `statuses`
    (default: a still-'proposed' strategy).

    Single definition of the "is a strategy still in flight for this goal"
    guard. Previously this exact `SELECT 1 ... LIMIT 1` probe was inlined in
    four places with subtly different status sets — verify_housekeeping's dead
    branch, cascade_one's Backward-success branch, `_kill_upward_chain` and
    `_reconcile_goal_after_strategy_loss` — with cross-referencing comments
    ("mirrors verify.py:218-224"). Centralising it removes that drift risk:
    the Backward-success branch passes `("proposed", "succeeded")` (a live OR a
    just-won strategy); everyone else takes the default.
    """
    placeholders = ",".join("?" * len(statuses))
    row = conn.execute(
        f"SELECT 1 FROM strategies WHERE goal_id = ?"
        f" AND status IN ({placeholders}) LIMIT 1",
        (goal_id, *statuses),
    ).fetchone()
    return row is not None


class IllegalTransition(RuntimeError):
    """Raised (strict mode only) when a (from, to) edge is not declared in the
    registry. In lenient/production mode the same condition is logged with a
    `[transition-violation]` marker and the write proceeds."""


# ---------------------------------------------------------------------------
# Proved-flip receipts — the soundness boundary lives HERE, not in pipeline
# discipline.
#
# "status='proved' iff the proof passed the axiom gate" is THE soundness
# invariant. Before receipts it was a calling CONVENTION (each pipeline
# remembers to run `_axiom.axiom_gate` before flipping) guarded by one
# structural test over the known paths — the exact shape under which Forward
# once shipped ungated. A transition INTO 'proved' now must carry a receipt
# naming which of the three sanctioned soundness arguments applies; a new
# code path that flips 'proved' without one trips strict mode (CI) or logs
# `[receipt-violation]` loudly in production — same dial, same rationale as
# the edge registry above.
# ---------------------------------------------------------------------------

PROVED_RECEIPT_KINDS: frozenset[str] = frozenset({
    # This goal's OWN proof was elaborated and its transitive axiom set
    # checked (sorryAx tripwire + whitelist) — `_axiom.axiom_gate` /
    # `axiom_probe` returned ok.
    "axiom_gate",
    # This goal is an alias (dedupe / Forward proved-alias / G1 revival) to
    # a canonical that carried its own receipt when IT flipped proved; the
    # alias body itself is build-verified. Soundness by induction on the
    # canonical — this receipt makes that induction step auditable.
    "alias_induction",
    # Mechanical verify-collapse promote: every sub-goal of the winning
    # strategy is proved (each with its own receipt); assembly is a pure
    # alias rewrite guarded by the assembly sorry gate, and the root
    # integrity gate re-elaborates the whole chain at the top. Deliberately
    # NOT re-probed per level (verify-collapse design, architecture.md §10).
    "verify_collapse",
})


class ProvedReceipt:
    """Evidence tag for a transition into 'proved'. `kind` names the
    sanctioned soundness argument (PROVED_RECEIPT_KINDS); `source` is a
    short forensic string (gate fq_name / canonical goal id / strategy id)
    for the violation log and post-mortems. Frozen tuple-style value."""
    __slots__ = ("kind", "source")

    def __init__(self, kind: str, source: str = "") -> None:
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "source", source)

    def __setattr__(self, *_a):  # pragma: no cover - immutability guard
        raise AttributeError("ProvedReceipt is immutable")

    def __repr__(self) -> str:
        return f"ProvedReceipt({self.kind!r}, {self.source!r})"


def _check_receipt(goal_id: int, frm: "str | None",
                   receipt: "ProvedReceipt | None", event: str) -> None:
    """Enforce the receipt requirement for a non-idempotent flip INTO
    'proved'. Missing or unregistered-kind receipts violate; row-absent and
    proved→proved self-edges are exempt (mirrors `_check`)."""
    if frm is None or frm == "proved":
        return
    if receipt is None:
        msg = (f"[receipt-violation] goal {goal_id} -> 'proved' "
               f"(event={event or '?'}) carries NO ProvedReceipt — every "
               "proved-flip must name its soundness argument "
               "(transitions.PROVED_RECEIPT_KINDS)")
    elif receipt.kind not in PROVED_RECEIPT_KINDS:
        msg = (f"[receipt-violation] goal {goal_id} -> 'proved' "
               f"(event={event or '?'}) carries unregistered receipt kind "
               f"{receipt.kind!r} — register it in PROVED_RECEIPT_KINDS "
               "with its soundness argument")
    else:
        return
    if _strict():
        raise IllegalTransition(msg)
    print(msg, flush=True)


def _strict() -> bool:
    return os.environ.get("ASTERISM_STRICT_TRANSITIONS") == "1"


def assert_main_thread(caller: str) -> None:
    """Cascade PROPAGATION is main-thread-only — the concurrency discipline
    that kills the OR-race class. Worker threads legitimately apply commit-
    time transitions on their OWN target through the checked mutators
    (forward's lemma landing, backward's sub-goal placement, …); what they
    must never do is run the PROPAGATION entrypoints (`cascade_one`,
    `verify_housekeeping`), which walk and mutate OTHER goals/strategies.
    Until 2026-07-03 this was a convention held by code review; this guard
    makes it a mechanism. Strict (CI) raises; lenient (production) logs
    loudly and proceeds — same split, same rationale as the edge check."""
    import threading
    if threading.current_thread() is threading.main_thread():
        return
    msg = (f"[transition-violation] {caller} called from worker thread "
           f"'{threading.current_thread().name}' — cascade propagation is "
           "main-thread-only (architecture.md invariants)")
    if _strict():
        raise IllegalTransition(msg)
    print(msg, flush=True)


def _check(entity: str, frm: str | None, to: str,
           edges: "frozenset[tuple[str, str]]", event: str) -> None:
    if frm is None or frm == to:
        # Row absent (caller will no-op the write anyway) or idempotent
        # self-edge — always permitted.
        return
    if (frm, to) not in edges:
        msg = (f"[transition-violation] {entity} {frm!r} -> {to!r} "
               f"(event={event or '?'}) is not a declared edge in "
               f"transitions.{'GOAL' if entity == 'goal' else 'STRATEGY'}_EDGES")
        if _strict():
            raise IllegalTransition(msg)
        print(msg, flush=True)


def apply_goal_transition(conn: sqlite3.Connection, goal_id: int, to_state: str,
                          *, event: str = "", reason: str = "",
                          receipt: "ProvedReceipt | None" = None) -> None:
    """The single sanctioned mutator of `goals.status`.

    Reads the current status, validates `(current -> to_state)` against
    `GOAL_EDGES`, then performs the write via `db.update_goal_status` (which
    also clears `integrity_verified` for any non-'proved' target).

    `event` is a short forensic label for the driving event (e.g.
    'builder_proved', 'strategist_reopen'); it is used in violation logs and,
    later (#11 Phase 3), as the key of the (state, event) exhaustiveness table.
    `reason` carries an optional failure_reason for richer logging.

    `receipt` is REQUIRED for a transition into 'proved' (see the
    ProvedReceipt block above): the soundness boundary is enforced at this
    chokepoint, not by pipeline calling discipline. Non-'proved' targets
    ignore it.
    """
    assert to_state in GOAL_STATES, f"unknown goal state {to_state!r}"
    row = conn.execute(
        "SELECT status FROM goals WHERE id = ?", (goal_id,),
    ).fetchone()
    frm = str(row["status"]) if row is not None else None
    _check("goal", frm, to_state, GOAL_EDGES, event)
    if to_state == "proved":
        _check_receipt(goal_id, frm, receipt, event)
    db.update_goal_status(conn, goal_id, to_state)


def apply_strategy_transition(conn: sqlite3.Connection, strategy_id: int,
                              to_state: str, *, event: str = "",
                              reason: str = "") -> None:
    """The single sanctioned mutator of `strategies.status`.

    Reads the current status, validates `(current -> to_state)` against
    `STRATEGY_EDGES`, then performs the write via `db.update_strategy_status`
    (which fires the inject-outcome propagation hook)."""
    assert to_state in STRATEGY_STATES, f"unknown strategy state {to_state!r}"
    row = conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (strategy_id,),
    ).fetchone()
    frm = str(row["status"]) if row is not None else None
    _check("strategy", frm, to_state, STRATEGY_EDGES, event)
    db.update_strategy_status(conn, strategy_id, to_state)


def _shelve_threshold() -> int:
    """Live SHELVE_THRESHOLD value. Thresholds remain owned by the
    dispatcher (config-overridden in `dispatcher.run`); the relocated
    cascade/propagation code reads the live value via this lazy proxy so
    transitions.py keeps no module-load dependency on core.dispatcher."""
    from ..core import dispatcher
    return dispatcher.SHELVE_THRESHOLD


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
                apply_goal_transition(
                    conn, sub_id, "shelved", event="descendant_cascade")
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
    receipt: "ProvedReceipt | None" = None,
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
    apply_goal_transition(
        conn, goal_id, status, event="set_terminal", receipt=receipt)
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


def _queue_problem_of(conn: sqlite3.Connection, target_id,
                      target_kind: str) -> str:
    """The `problem` a queue row belongs to (v17 scope column). Problem-
    keyed targets carry it verbatim; Goal targets resolve via their row.
    Empty string on unresolvable ids — such a row is scope-orphaned and
    swept by the next startup like any stale row (never a crash here:
    enqueue happens mid-cascade)."""
    if target_kind == "Problem":
        return str(target_id)
    try:
        row = conn.execute("SELECT problem FROM goals WHERE id = ?",
                           (int(target_id),)).fetchone()
    except (TypeError, ValueError):
        return ""
    return str(row["problem"]) if row else ""


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
    apply_goal_transition(
        conn, goal_id, "pending_strategist_review", event="enqueue_review")

    # Phase 6 — Strategist rows are problem-keyed (target_kind='Problem');
    # the old root-goal lookup returned early on pure-NL problems (no
    # root), silently orphaning their reviews.
    problem = str(g["problem"])

    # Per-problem in-flight dedup: skip if a Strategist row already sits
    # in the queue for this problem. dispatcher's main-loop in-memory
    # `running` set covers active dispatches; this DB check covers
    # queue-pending entries.
    if db.is_in_queue(conn, target_id=problem, kind="Strategist"):
        return
    # Priority 20 — above T1/T4 (=10) per pipelines.md §2.1 "T2 > T1".
    # T2 is event-driven (an agent shelved, review needed); T1/T4 are
    # routine/backstop. Without an explicit priority kwarg the default 0
    # would put T2 below Backward (=2) and Builder (=5), inverting the
    # spec.
    db.enqueue(conn, kind="Strategist", target_id=problem,
               target_kind="Problem", priority=20, problem=problem)


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
        apply_strategy_transition(
            conn, sid, "dead", event="inward_kill")


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
            apply_strategy_transition(
                conn, sid, "stalled", event="parent_stall")


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
        apply_strategy_transition(
            conn, sid, "dead", event="upward_kill")
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
        if has_live_sibling(conn, gid):
            # Sibling still in-flight: count the failure but defer the
            # shelve/reopen decision until the sibling resolves.
            continue
        if n >= _shelve_threshold():
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
            apply_goal_transition(
                conn, gid, "open", event="reopen_after_cascade")


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
    if has_live_sibling(conn, goal_id):
        return
    n = int(row["attempts"])
    if n >= _shelve_threshold():
        _enqueue_strategist_review(conn, goal_id)
    else:
        apply_goal_transition(
            conn, goal_id, "open", event="reopen_after_strategy_loss")


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
    assert_main_thread("cascade_one")
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
                    apply_strategy_transition(
                        conn, int(target_id), "superseded",
                        event="sibling_won")
                return
            if row["goal_status"] == "shelved":
                # Cascade race guard: parent goal was shelved while
                # this strategy's pipeline was in flight. Strategy is
                # moot; mark dead so invariant `proposed → parent alive`
                # holds.
                if row["status"] == "proposed":
                    apply_strategy_transition(
                        conn, int(target_id), "dead",
                        event="parent_shelved_race")
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
            # Builder returns outcome='proved' only after its in-pipeline
            # axiom gate (builder.py Phase 1 + Phase 2, structurally
            # asserted by test_axiom_invariant). The receipt is
            # reconstructed here because only strings cross the
            # worker→cascade boundary (finished-pipeline row).
            _set_goal_terminal_and_propagate(
                conn, int(target_id), "proved",
                receipt=ProvedReceipt(
                    "axiom_gate", f"builder pipeline={pipeline_id}"))
            return
        # Phase 7 — `exhausted` outcome: in-pipeline retry helper
        # consumed its budget without a terminal outcome. Helper has
        # already written N dead_attempts + N attempts++ for the N
        # failed retries (decision 5/6). Cascade does status transition
        # only — no further increment, no dead_attempt write.
        if outcome == "exhausted":
            cur = db.get_goal(conn, int(target_id))
            n = int(cur["attempts"]) if cur else 0
            if n >= _shelve_threshold():
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
            # `docs/archive/design/phase2/pipelines.md` §4.2 Rule 1):
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
                if n >= _shelve_threshold():
                    _enqueue_strategist_review(conn, int(target_id))
                else:
                    db.update_goal_entry_kind(conn, int(target_id),
                                              "Backward")
                return
            n = db.increment_goal_attempts(conn, int(target_id))
            if n >= _shelve_threshold():
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
                           decision_id=decision_id,
                           problem=_queue_problem_of(
                               conn, target_id, target_kind))
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
            if has_live_sibling(
                    conn, int(target_id), statuses=("proposed", "succeeded")):
                apply_goal_transition(
                    conn, int(target_id), "attempting",
                    event="backward_decomposed")
            return
        # Phase 7 — `exhausted` outcome: mirrors Builder branch above.
        # Helper buffered N dead_attempts + N attempts++ for the N
        # failed retries; cascade does status transition only.
        if outcome == "exhausted":
            cur = db.get_goal(conn, int(target_id))
            n = int(cur["attempts"]) if cur else 0
            if n >= _shelve_threshold():
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
        if n >= _shelve_threshold():
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
                       target_kind=target_kind, priority=20,
                       problem=_queue_problem_of(
                           conn, target_id, target_kind))
            print(f"[strategist-retry] re-queued {target_kind}={target_id}"
                  f" after {failure_reason}", flush=True)
        return

    # Verify removed as a worker_kind. Strategy verification + parent
    # promotion happens in `verify.verify_housekeeping`, called at the
    # end of each dispatcher tick (see `run` below).
