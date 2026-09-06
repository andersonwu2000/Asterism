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

Terminal vocabulary (owner ruling 2026-09-04)
---------------------------------------------
A goal is a STATEMENT, and only the kernel settles a statement, so the
terminal goal statuses are exactly the two kernel-checked verdicts:
`proved` (carries a ProvedReceipt) and `disproved` (reachable only
through `_disprove.run_disproof_gate`). Every other way a goal stops —
threshold exhaustion, ConfirmShelve, a descendant cascade, a group
retiring, a wrong-context decline — is a PARK (`shelved`), told apart
by its `goal_events` event, and revivable. The retired `dead` status
said "the parent's decomposition was wrong", which is a fact about the
STRATEGY: strategies keep their own `dead`, and the sub-goal is parked
with `event='wrong_context_park'`.

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

#: Owner ruling 2026-09-04 — a goal is a STATEMENT, and only the kernel
#: settles a statement, so the TERMINAL goal statuses are exactly the two
#: kernel-checked verdicts (`proved` / `disproved`). The retired `dead`
#: said "the parent's decomposition was wrong", which is a fact about the
#: STRATEGY (strategies keep their own `dead`) — the sub-goal is PARKED
#: (`shelved`, event `wrong_context_park`), from where a citation, an
#: Inject or a Delegate can revive it in a context that fits.
GOAL_STATES: frozenset[str] = frozenset({
    "open",
    "attempting",
    "proved",
    "shelved",
    "pending_strategist_review",
    "disproved",
    "frozen",
})

STRATEGY_STATES: frozenset[str] = frozenset({
    "proposed",
    "succeeded",
    "dead",
    "superseded",
    "stalled",
})

# Terminal classes (referenced by cascade/propagation guards). A *hard*
# terminal is never downgraded to a softer one (`proved` is a finished
# proof; `disproved` is a kernel-certified refutation, a stronger
# negative than `shelved`).
#: These two are the KERNEL-checked verdicts and nothing else qualifies
#: (2026-09-04): `proved` carries a ProvedReceipt, `disproved` is only
#: reachable through `_disprove.run_disproof_gate`. Every other way a
#: goal stops is a PARK — reopenable by whoever finds the way back.
GOAL_HARD_TERMINALS: frozenset[str] = frozenset({"proved", "disproved"})
GOAL_TERMINALS: frozenset[str] = GOAL_HARD_TERMINALS | {"shelved"}
#: Hard-settled AND failed: never citable, never revived by a proof —
#: the cite-gate / ancestor-walk / `failed:<status>` predicate. A
#: one-element set today; it stays NAMED because the four modules that
#: read it are asking "is this settled against us?", not "is this
#: disproved?", and a kernel-witnessed second verdict would join it.
GOAL_FAILED_TERMINALS: frozenset[str] = GOAL_HARD_TERMINALS - {"proved"}
STRATEGY_TERMINALS: frozenset[str] = frozenset({"succeeded", "dead", "superseded"})

# ---------------------------------------------------------------------------
# Problem FSM (v29, problem_fsm_design.md §2) — the explicit lifecycle
# the wake machinery / gates previously derived from scattered carriers
# (awaiting_human rows, ingested_at, ingest_signoff_pending). 'stalled'
# is deliberately NOT a state: it is a derived guard on 'active' — the
# forced-advance philosophy keeps grinding active problems; the only
# sanctioned pauses are human-owned (awaiting_human / ingest_signoff /
# revoked) or terminal (ingested).
# ---------------------------------------------------------------------------

PROBLEM_STATES: frozenset[str] = frozenset({
    "active",
    "awaiting_human",
    "ingest_signoff",
    "ingested",
    "revoked",
    # 2026-08-30: the root was kernel-disproved and the Strategist
    # Ingested — the conjecture is settled negatively. Terminal like
    # `ingested`; the operator's `revive` is the only way back.
    "refuted",
})

PROBLEM_EDGES: frozenset[tuple[str, str]] = frozenset({
    ("active", "awaiting_human"),      # amend_requested
    ("awaiting_human", "active"),      # amend_resolved (accept or reject)
    ("active", "ingest_signoff"),      # ingest_committed (signoff on)
    ("active", "ingested"),            # ingest_direct (signoff off)
    ("ingest_signoff", "ingested"),    # signoff_approved
    ("ingest_signoff", "active"),      # signoff_rejected
    # Post-Ingest un-prove: "announce the incident" automatically (seal
    # torn, quarantined), "what next" waits for the operator.
    ("ingested", "revoked"),           # unprove_revoked
    ("ingest_signoff", "revoked"),     # unprove_revoked (during the pause)
    ("revoked", "active"),             # operator_revived (asterism revive)
    ("active", "refuted"),             # ingest_refuted (root disproved)
    ("refuted", "active"),             # operator_revived (asterism revive)
})

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
    # v35 rescue shape: a `Delegate` with a target promotes that goal to
    # the new group's anchor. "This goal keeps failing — give it a
    # group" is the documented entry point, and the states it starts
    # from are exactly the parked ones.
    ("shelved", "attempting"),
    ("frozen", "attempting"),

    # --- goal reopened (reset for a fresh attempt; no terminal reached) ---
    ("attempting", "open"),                   # strategy died, not exhausted
    ("shelved", "open"),                      # backward-revive / forward-reuse / strategist reopen
    ("pending_strategist_review", "open"),    # strategist Reopen / reconcile
    ("frozen", "open"),                       # strategist reopen of a frozen root
    # 2026-09-04 (owner ruling): the disproof gate landed, so a
    # `disproved` mark IS a kernel-certified refutation and the
    # strategist may not overturn one by fiat (`verify_decision` refuses
    # the Inject and names the way out: a different statement). The edge
    # survives for OPERATOR repair only — a person who finds the gate
    # itself was wrong. It opened in 2026-08-18, when the mark was still
    # a prose claim and 8/8 of union_closed's disproved goals were
    # prose-flipped `sorry` files (g8014 was kernel-proven TRUE after
    # the flip); that hole is closed on the WRITE side now.
    ("disproved", "open"),                    # operator repair only
    ("proved", "open"),                       # rollback: culprit chain reverted
    ("proved", "attempting"),                 # rollback: non-culprit pre-verify state

    # --- goal soft-shelved (threshold / descendant cascade / drift park) ---
    ("open", "shelved"),
    ("attempting", "shelved"),
    ("pending_strategist_review", "shelved"),  # orphan-chain guard / ConfirmShelve

    # --- goal handed to Strategist (transitional, agent_shelved / exhausted) ---
    ("open", "pending_strategist_review"),
    ("attempting", "pending_strategist_review"),

    # --- goal hard-terminal (kernel-certified counterexample) ---
    # The wrong-context case has no edge of its own: `parent_needs_fix`
    # parks the sub-goal on the ordinary shelve edges above (event
    # `wrong_context_park`) — see `_propagate_wrong_context`.
    ("attempting", "disproved"),
    ("open", "disproved"),

    # --- bootstrap: root statement seeded but Defs not yet initialised ---
    ("open", "frozen"),
})

STRATEGY_EDGES: frozenset[tuple[str, str]] = frozenset({
    # --- strategy proved out (verify success) ---
    # `verify._flip_proved` is the SOLE writer of this edge (2026-09-07):
    # the reconcile backstop used to emit it too, off "still proposed and
    # every sub-goal proved" — a shape the async promotion gate turned
    # into "promotion in flight", so the backstop settled the batch under
    # a goal that had not been proved yet.
    ("proposed", "succeeded"),
    # --- strategy killed (skeleton fail / agent fail / cascade inward+upward) ---
    ("proposed", "dead"),
    # --- OR-race: a sibling won, sideline this one ---
    ("proposed", "superseded"),
    # --- soft-park: all sub-goals settled, no hard-terminal sibling ---
    ("proposed", "stalled"),
    # --- revival: stalled/superseded strategy reactivated ---
    ("stalled", "proposed"),       # _commit_inject_redispatch un-stall parent
    ("superseded", "proposed"),    # rollback un-supersede sibling
    # --- axiom-probe rollback of a wrongly-promoted alias chain ---
    ("succeeded", "dead"),         # culprit strategy that leaked sorryAx
    ("succeeded", "proposed"),     # upstream strategy reverted for re-verify,
                                   # and recovery's un-settled promotion
})

GROUP_EDGES: frozenset[tuple[str, str]] = frozenset({
    # A group leaves `active` exactly once, by one of the three verbs, and
    # never comes back: `reconcile_settled_inject_outcomes` reads every
    # non-'active' status as settled, and reaching one fills the opening
    # `Delegate`'s outcome and wakes the parent. A resurrection would leave
    # a parent already woken while its child runs on — which is the class
    # this table exists to make unrepresentable.
    ("active", "delivered"),   # sub-group Ingest — bricks are the parent's
    ("active", "returned"),    # ReturnToParent (refuted / amend / exhausted)
    ("active", "closed"),      # the parent retired it (CloseGroup)
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
    # `parent_needs_fix` — the worker says the DECOMPOSITION was wrong,
    # not the statement (2026-09-04). The strategy dies; the sub-goal is
    # parked under its own event so a park for a wrong context is
    # distinguishable in `goal_events` from a threshold shelve or a
    # ConfirmShelve, and so a later reader knows the statement itself
    # was never judged.
    "wrong_context_park",
    # backward pipeline
    "skeleton_failed", "moot_retain", "agent_failed",
    "backward_alias_proved", "backward_sorryfree_proved", "backward_revive",
    # forward pipeline
    "forward_lemma_proved", "forward_alias_proved", "forward_reuse_revive",
    # strategist
    "strategist_reopen", "strategist_unstall",
    # cited-wait conduction (owner design 2026-08-25): shelving a goal
    # returns each CITING strategy's own goal to its group's review.
    "cited_dependency_parked",
    # discussion groups (v35) — a `Delegate` with a target promotes that
    # goal to the new group's anchor and parks it `attempting`: alive
    # (so the parent's wait is legal) but not dispatchable by BFS.
    "delegate_anchor",
    # ... the three verbs that retire one (`groups.set_status`), plus
    # the descendant's edge when one of them takes its sub-projects
    # with it — and the startup sweep for pre-cascade trees.
    "group_delivered", "group_returned", "group_closed",
    "ancestor_retired", "ancestor_retired_before_cascade",
    # verify housekeeping + axiom-probe rollback
    "verify_proved", "verify_dead", "verify_reopen", "assembly_sorry_gate",
    "rollback_culprit", "rollback_upstream", "rollback_unsupersede",
    # promotion cold-build gate + catalog cold-build audit (2026-08-30, #231)
    "promotion_build_failed", "catalog_verify_unbuildable",
    # startup recovery — interrupted-cascade repair (task #11:
    # consistency.repair_unambiguous finishes the sibling sweep a crashed
    # cascade owed its live `proposed` strategies)
    "startup_terminal_parent_reconcile",
    # startup recovery — the open↔attempting resync passes, routed
    # through the chokepoint since 2026-08-18 (frankl_core: the bulk
    # reopen silently un-parked a live group's anchor on every restart,
    # and left no goal_events row to say which restart did it).
    "recovery_reopen", "recovery_attempting_fixup",
    "recovery_anchor_repark",
    # startup recovery — a promotion whose settle never landed: the
    # alias was on disk with its backup, the strategy already read
    # 'succeeded', and the goal never flipped. The file goes back to its
    # stub and the strategy back to 'proposed', so verify re-promotes
    # and re-gates it (2026-09-07).
    "recovery_unsettled_promotion",
    # operator verbs (`asterism reject`) — a person retiring a
    # framework-generated node. Not a kernel verdict, so it is a park;
    # the event is what says a PERSON wanted this one gone.
    "human_rejected",
    # problem FSM (v29) — apply_problem_transition call sites
    "amend_requested", "amend_resolved",
    "ingest_committed", "ingest_direct", "ingest_refuted",
    "signoff_approved", "signoff_rejected",
    "unprove_revoked", "operator_revived",
})


def predicted_batch_delta(conn: sqlite3.Connection, decisions) -> int:
    """How many state transitions / new dispatches a Strategist decision
    batch would commit (problem FSM design §2.3, 2026-07-12). This is
    the mechanical currency of the stall-advance gate: a self-edge
    (re-confirming a shelved goal, shelving a hard-terminal goal,
    re-marking a marked deliverable) is legal but moves nothing, so it
    counts ZERO — the pump generations (EmitDirective-only, junk
    Inject, re-confirm ConfirmShelve, Noop) all shared the property
    'commit succeeds, no state moves', and enumerating decision KINDS
    kept missing the next token. Counting transitions closes the class.

    `decisions` are duck-typed (`.kind`, `.target_id`) so the pipeline
    layer's Decision objects work without importing them here (this
    module stays a `db`-only leaf)."""
    n = 0
    for d in decisions:
        k = getattr(d, "kind", None)
        if k in ("Inject", "FetchPaper", "Ingest",
                 "RequestUserAmend", "Delegate", "ReturnToParent",
                 "CloseGroup",
                 # Handing the wall to the theory layer IS a change of
                 # state: a request goes out, a pipeline runs, and the
                 # answer comes back as this batch's outcome. A stalled
                 # group whose honest next move is "the mathematics is
                 # not there yet" must be able to say so.
                 "Theorize"):
            # New dispatch (Inject/FetchPaper/Delegate — a delegated
            # burden is work handed to a new group, not a self-edge),
            # or a lifecycle edge (active→ingest_signoff
            # / awaiting_human / a group reaching a terminal status).
            n += 1
            continue
        gid = getattr(d, "target_id", None)
        if gid is None or not isinstance(gid, int):
            continue
        if k == "ConfirmShelve":
            row = conn.execute(
                "SELECT status FROM goals WHERE id = ?", (gid,)).fetchone()
            # Real edge only from a LIVE status; shelved→shelved is a
            # self-edge and proved/disproved are silently no-op'd
            # at commit (BT 2026-05-29 guard) — zero delta either way.
            if row is not None and str(row["status"]) in (
                    "open", "attempting", "pending_strategist_review",
                    "frozen"):
                n += 1
        elif k == "MarkDeliverable":
            row = conn.execute(
                "SELECT status, is_deliverable FROM goals WHERE id = ?",
                (gid,)).fetchone()
            if (row is not None and str(row["status"]) == "proved"
                    and not int(row["is_deliverable"] or 0)):
                n += 1
    return n


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


#: Self-edges that are NOT idempotent, because ARRIVING is the event.
#: Reaching a terminal group status fills the opening `Delegate`'s
#: outcome and wakes the parent (`groups.set_status`), so a second
#: arrival wakes the parent a second time about a delivery it already
#: consumed — the exact "parent already woken while its child runs on"
#: that `GROUP_EDGES` says it exists to make unrepresentable. It was
#: representable: `_check` waved every `frm == to` through without
#: consulting the table, and groups 381 and 383 each delivered twice on
#: 2026-08-13/14.
NON_IDEMPOTENT_SELF: "frozenset[tuple[str, str]]" = frozenset(
    ("group", s) for s in ("delivered", "returned", "closed"))


def _check(entity: str, frm: str | None, to: str,
           edges: "frozenset[tuple[str, str]]", event: str) -> None:
    if frm is not None and frm == to and (entity, to) in NON_IDEMPOTENT_SELF:
        msg = (f"[transition-violation] {entity} {frm!r} -> {to!r} "
               f"(event={event or '?'}) REPEATS a terminal arrival — the "
               f"first one already notified upstream")
        if _strict():
            raise IllegalTransition(msg)
        print(msg, flush=True)
        return
    if frm is None or frm == to:
        # Row absent (caller will no-op the write anyway) or idempotent
        # self-edge — permitted unless arriving is itself the event
        # (`NON_IDEMPOTENT_SELF`). `goal proved -> proved` is the case
        # this exemption was written for and keeps.
        return
    if (frm, to) not in edges:
        msg = (f"[transition-violation] {entity} {frm!r} -> {to!r} "
               f"(event={event or '?'}) is not a declared edge in "
               f"transitions.{entity.upper()}_EDGES")
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
    db.update_goal_status(conn, goal_id, to_state,
                          event=event, reason=reason)


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


# Wake legality matrix (FSM P3, problem_fsm_design.md §4): which
# Strategist trigger kinds may fire in which problem state. The enqueue
# sources (T1/T1.5/T4/T2/reconcile) consult this ONE table, so a wake
# arriving in a state with no legal work is a design-time contradiction
# visible here — not a runtime pump. Only 'active' accepts wakes: every
# other state is human-owned (awaiting_human / ingest_signoff /
# revoked) or terminal (ingested).
WAKE_LEGALITY: "dict[str, frozenset[str]]" = {
    "active": frozenset({"routine", "inject_batch_done",
                         "pending_review"}),
    "awaiting_human": frozenset(),
    "ingest_signoff": frozenset(),
    "ingested": frozenset(),
    "revoked": frozenset(),
    "refuted": frozenset(),
}


def problem_accepts_wake(conn: sqlite3.Connection, problem: str,
                         trigger: "str | None" = None) -> bool:
    """Enqueue-side WAKE_LEGALITY lookup. `trigger=None` asks "any wake
    at all?" (what the seat sources need); a specific trigger narrows
    to that row. Unknown problem → False (nothing to wake)."""
    row = conn.execute(
        "SELECT state FROM problems WHERE name = ?", (problem,),
    ).fetchone()
    if row is None:
        return False
    allowed = WAKE_LEGALITY.get(str(row["state"] or "active"), frozenset())
    return bool(allowed) if trigger is None else (trigger in allowed)


def apply_problem_transition(conn: sqlite3.Connection, problem: str,
                             to_state: str, *, event: str = "") -> None:
    """The single sanctioned mutator of `problems.state` (v29,
    problem_fsm_design.md §2.2). Reads the current state, validates the
    edge against `PROBLEM_EDGES` (strict/lenient split identical to the
    goal machine), writes the column. The legacy carriers
    (ingested_at / ingest_signoff_pending / awaiting rows) stay owned
    by their existing setters at the same call sites — this chokepoint
    is the FSM's SoT, the carriers remain the liveness predicates'
    physical inputs until P3 swaps the readers."""
    assert to_state in PROBLEM_STATES, f"unknown problem state {to_state!r}"
    row = conn.execute(
        "SELECT state FROM problems WHERE name = ?", (problem,),
    ).fetchone()
    frm = str(row["state"] or "active") if row is not None else None
    _check("problem", frm, to_state, PROBLEM_EDGES, event)
    conn.execute("UPDATE problems SET state = ? WHERE name = ?",
                 (to_state, problem))
    conn.commit()


def _shelve_threshold() -> int:
    """Live SHELVE_THRESHOLD (task #10(d): read from the leaf
    `state.thresholds` — the old lazy core.dispatcher proxy was the
    state→core arm of the repo's only dependency cycle)."""
    from . import thresholds
    return thresholds.SHELVE_THRESHOLD


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

def shelve_cascade_targets(
    conn: sqlite3.Connection, goal_id: int,
) -> "list[int]":
    """The descendants a shelve of `goal_id` would take with it, in walk
    order. READ-ONLY: this is the cascade's own reasoning, extracted so
    that the confirm-window preview (`state/commands.preview`, HID §1.3)
    and the cascade itself cannot disagree about what is about to close.

    See `_cascade_shelve_descendants` — its only caller — for why the
    walk spares goals with an independent live path, walks PAST proved
    descendants, and skips `pending_strategist_review`.
    """
    grow = conn.execute(
        "SELECT problem FROM goals WHERE id = ?", (goal_id,)).fetchone()
    saved = (
        db.goals_reachable_excluding(
            conn, problem=str(grow["problem"]), exclude_goal_id=goal_id)
        if grow is not None else set()
    )
    targets: "list[int]" = []
    picked: "set[int]" = set()
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
                if sub_id in saved or sub_id in picked:
                    continue
                if sub_status in ("proved", "shelved", "disproved",
                                  "pending_strategist_review"):
                    if sub_status == "proved":
                        next_frontier.append(sub_id)
                    continue
                picked.add(sub_id)
                targets.append(sub_id)
                next_frontier.append(sub_id)
        frontier = next_frontier
    return targets


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
    # The walk itself is `shelve_cascade_targets` (read-only, above);
    # this is the write half. Splitting them is what lets the confirm
    # window (`state/commands.preview`) name exactly what the apply will
    # take, from the same reasoning rather than a second copy of it.
    #
    # Spared: a descendant with an independent live path to root — not
    # orphaned by this death. Walked PAST: proved descendants, whose own
    # subtrees may still hold active goals. Skipped:
    # `pending_strategist_review` (the Strategist decides its fate;
    # cascading would race).
    transitioned = 0
    for sub_id in shelve_cascade_targets(conn, goal_id):
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
    return transitioned


def _set_goal_terminal_and_propagate(
    conn: sqlite3.Connection, goal_id: int, status: str,
    receipt: "ProvedReceipt | None" = None,
    *, event: str = "set_terminal", reason: str = "",
) -> None:
    """Flip a goal to a terminal status and:

      1. If the goal was Inject-produced (Forward output of a
         Strategist Inject decision), fill the originating decision's
         `outcome` column and fire `inject_batch_done` when its
         batch is fully terminal.
      2. For non-recoverable terminals (`shelved` / `disproved`),
         cascade `shelved` to every still-active descendant via
         `_cascade_shelve_descendants`. Display and Strategist
         context view then converge on the same source of truth.

    Centralises the sequence (`update_goal_status` →
    `propagate_inject_outcome_from_goal` →
    `_maybe_enqueue_inject_batch_done` → optional descendant
    cascade) so every terminal flip site applies them uniformly.

    `status` ∈ {'proved','shelved','disproved'}. `event` / `reason`
    name the driving cause in `goal_events` — the shelve sites that
    have a specific one (`wrong_context_park`) pass it so a later
    reader can tell a wrong-context park from a threshold shelve.

    Instrument: every terminal flip prints a caller-trace line so we
    can attribute unexpected shelves (polar 2026-05-23: `square_root_
    of_positive` shelved at attempts=5 < SHELVE_THRESHOLD=8 via a
    path none of the documented cascade rules explain). The 1-line
    trace pulls the immediate caller's filename+line+function from
    the Python stack — enough to disambiguate the cascade entry
    point on next reproduction.

    Guard (BT 2026-05-29 g3380): never DOWNGRADE a goal that is already
    a hard terminal (`proved` / `disproved`) to `shelved`.
    `proved` is a completed proof — shelving it regresses a true theorem
    and breaks the invariant `proved ⟺ some strategy's subs all proved`;
    `disproved` is a kernel-certified refutation, a stronger negative
    terminal than `shelved`.
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
            "proved", "disproved",
        ):
            print(f"[goal-terminal] g{goal_id} shelve SKIPPED — already "
                  f"{cur['status']!r} (no downgrade of a terminal goal)",
                  flush=True)
            return
    if status in ("shelved", "disproved"):
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
        conn, goal_id, status, event=event, reason=reason, receipt=receipt)
    d = db.propagate_inject_outcome_from_goal(conn, goal_id)
    if d is not None:
        _maybe_enqueue_inject_batch_done(conn, d)
    if status in ("shelved", "disproved"):
        _cascade_shelve_descendants(conn, goal_id)


def _record_inject_decision_outcome(conn: sqlite3.Connection,
                                    decision_id: int,
                                    outcome: str,
                                    failure_reason: str,
                                    detail: str | None = None,
                                    pipeline_id: str | None = None) -> None:
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
    if detail is None and pipeline_id:
        # An exhausted Forward reached here with `outcome_detail` NULL
        # while its per-retry death causes (lake diagnostics, parse
        # rejections) sat fully spelled out in dead_attempts — the
        # Strategist then read bare `exhausted:forward_no_new_goal` and
        # did archaeology (two feedback entries, Erdős fleet
        # 2026-08-22). The knowledge already has a home keyed by this
        # very pipeline; hand the LAST retry's cause over instead of
        # flattening it away.
        row = conn.execute(
            "SELECT failure_detail FROM dead_attempts"
            " WHERE pipeline_id = ? ORDER BY id DESC LIMIT 1",
            (pipeline_id,)).fetchone()
        if row is not None and row["failure_detail"]:
            detail = str(row["failure_detail"])[:2000]
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


def _enter_pending_review(conn: sqlite3.Connection, goal_id: int, *,
                          event: str) -> None:
    """Move a goal into `pending_strategist_review` and settle whatever
    Inject produced it.

    The ONE spelling for entering review, because the second half is the
    part every site forgot: a brick handed back for a verdict is a
    DELIVERY (owner ruling 2026-09-05), so its step's `outcome` fills
    and the batch it belongs to can complete. There are two roads into
    this state — the review escalation below and a citation whose
    dependency parked — and a road that skipped the fill left its batch
    reading as in-flight forever.

    `_maybe_enqueue_inject_batch_done` fires only when the fill was the
    LAST outcome the batch owed, exactly as every other propagation site
    does: a batch still owing a `Theorize` stays quiet and the review
    reaches its author on that batch's own report.
    """
    apply_goal_transition(conn, goal_id, "pending_strategist_review",
                          event=event)
    d = db.propagate_inject_outcome_from_goal(conn, goal_id)
    if d is not None:
        _maybe_enqueue_inject_batch_done(conn, d)


def _queue_problem_of(conn: sqlite3.Connection, target_id,
                      target_kind: str) -> str:
    """The `problem` a queue row belongs to (v17 scope column). Problem-
    keyed targets carry it verbatim; Goal and Group targets resolve via
    their rows.

    Returning '' is POISON, not merely scope-orphaned (2026-08-03
    post-mortem, SLC 3h20m silent stall): a scoped pop filters
    `problem LIKE scope` so the row can never dispatch, but
    `is_in_queue` matches it anyway, so `_strategist_inflight` reads
    the group as busy and BOTH T1 and T4 skip it forever — and the
    startup sweep the old docstring promised cleared 0 rows. The Group
    branch was missing (v35 made strategist targets Group-keyed; this
    resolver still knew only Problem/Goal). Callers must not enqueue
    on ''."""
    if target_kind == "Problem":
        return str(target_id)
    table = "groups" if target_kind == "Group" else "goals"
    try:
        row = conn.execute(f"SELECT problem FROM {table} WHERE id = ?",
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
    # goal may later be Reopen'd. The producing Inject settles with it
    # (see `_enter_pending_review`) — BEFORE the seat decision below,
    # which reads whether the group's batch is still working.
    _enter_pending_review(conn, goal_id, event="enqueue_review")

    # Phase 6 — Strategist rows are problem-keyed (target_kind='Problem');
    # the old root-goal lookup returned early on pure-NL problems (no
    # root), silently orphaning their reviews.
    problem = str(g["problem"])
    # v35 — route to the group that OWNS this goal, not to the problem:
    # a review is a question for whoever dispatched the work, and a
    # sibling group cannot answer it. `group_for_goal` also skips a
    # group that has already finished (no seat) in favour of its nearest
    # working ancestor.
    from . import groups as _groups
    owner = _groups.group_for_goal(conn, problem, goal_id)
    gid = int(owner["id"]) if owner is not None \
        else _groups.ensure_top_group(conn, problem)

    # In-flight dedup: skip if a Strategist row for this group already
    # sits in the queue. dispatcher's main-loop in-memory `running` set
    # covers active dispatches; this DB check covers queue-pending
    # entries. The problem-keyed probe covers pre-v35 rows.
    if db.is_in_queue(conn, target_id=str(gid), kind="Strategist"):
        return
    if db.is_in_queue(conn, target_id=problem, kind="Strategist"):
        return
    # In-flight BATCH suppression (owner ruling 2026-09-05) — the same
    # rule T0/T1 carry, on the same predicate, narrowed to the group
    # that owes the verdict. A review is a report of the group's own
    # batch, so it rides that batch's `inject_batch_done` wake; seating
    # it separately opened a SECOND batch while the first was still
    # working, and each completion then relayed another wake
    # (union_closed 2026-09-04: five wakes and eight Injects while the
    # group's wall sat with the Theorist). The goal's review status
    # above stands either way — the reconciler re-offers the seat every
    # tick, so the hold ends when the batch does.
    if db.has_active_inflight_inject(conn, problem, group_id=gid):
        return
    # Wake legality (FSM P3): a non-active problem takes no seats. The
    # goal's pending_review status above stands regardless — when the
    # problem re-enters 'active', reconcile_stuck_states re-arms the
    # review seat on the next tick.
    if not problem_accepts_wake(conn, problem, "pending_review"):
        return
    # Priority 20 — above T1/T4 (=10) per pipelines.md §2.1 "T2 > T1".
    # T2 is event-driven (an agent shelved, review needed); T1/T4 are
    # routine/backstop. Without an explicit priority kwarg the default 0
    # would put T2 below Backward (=2) and Builder (=5), inverting the
    # spec.
    db.enqueue(conn, kind="Strategist", target_id=str(gid),
               target_kind="Group", priority=20, problem=problem)


def _has_hard_terminal_ancestor(conn: sqlite3.Connection,
                                goal_id: int) -> tuple[bool, str | None]:
    """Phase 6 — Reopen safety walk.

    Return `(found, status)` where `found` is True iff any ancestor
    goal in the strategy_subgoals chain has a HARD terminal status
    (`disproved`, the only failed one); `status` is which if any.

    A `disproved` ancestor blocks Reopen on descendants: a kernel
    counterexample stands against the parent statement, so the
    descendant's own statement depends on a false hypothesis context
    and proving it is meaningless.

    `shelved` ancestors do NOT count (soft terminal; auto-detach
    handles broken upward chains so the descendant can run standalone
    and may even be revived once the ancestor reopens) — and since
    2026-09-04 a wrong-context park IS a `shelved` ancestor, which is
    the point: the descendant statement was never judged.

    Walks UPWARD via strategy_subgoals.subgoal_id = goal_id → parent
    strategy → strategy.goal_id, recursively — MINTED edges only (v44):
    the rationale above is about the context a goal was CREATED in,
    and a citing strategy is a consumer, not the creator. Crossing a
    cited edge would let a consumer's disproved parent block Reopen on
    an independent shared goal.
    """
    visited: set[int] = set()
    frontier: list[int] = [goal_id]
    while frontier:
        next_frontier: list[int] = []
        for gid in frontier:
            rows = conn.execute(
                "SELECT s.goal_id FROM strategies s"
                " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                " WHERE ss.subgoal_id = ? AND ss.link_kind = 'minted'",
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
                if grow["status"] in GOAL_FAILED_TERMINALS:
                    return True, str(grow["status"])
                next_frontier.append(parent_id)
        frontier = next_frontier
    return False, None


def _has_terminal_disproved_ancestor(conn: sqlite3.Connection,
                                     goal_id: int) -> bool:
    """Legacy alias. New code should call
    `_has_hard_terminal_ancestor` directly for the more informative
    return shape."""
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


def _awaiting_promised_batch(conn: sqlite3.Connection,
                             goal_id: int) -> bool:
    """True iff this shelved goal's own park carries a promise that has
    not come due yet — i.e. the LATEST `ConfirmShelve` on it shares a
    batch with at least one `Inject` still lacking an outcome.

    This is the framework's existing definition of a reopen-promise
    (there is no promise table: a promise IS a ConfirmShelve batched
    with Injects — see `phase2_context._section_pending_reopens`, which
    surfaces exactly the complement: batches whose Injects HAVE all
    resolved). Batch semantics guarantee the continuity: the moment the
    last Inject settles, `maybe_enqueue_inject_batch_done` enqueues the
    Strategist wake that puts the due promise in front of it. So there
    is no window between "helpers in flight" and "wake scheduled", and
    hence no need for an expiry timer here.

    Why it belongs in the aliveness composition (2026-07-30, b6_1):
    `pending_strategist_review` already counts as alive for exactly the
    same reason — something is scheduled to touch that goal. A shelved
    goal awaiting its promised bricks has the same property, and not
    counting it produced a 4-level review cascade: 7134 parked (its own
    batch minting two helpers) → parent's only strategy stalled →
    `_maybe_review_goal_out_of_routes` handed the parent to a review
    wake → the Strategist, asked about a goal that had never failed
    (attempts=0) and whose only blocker was the parked child, answered
    ConfirmShelve → repeat, one level per wake, root included. Four
    full batch cycles (strategist + adversary spawns + a Programme
    revision each), three of them adjudicating a non-question. The
    per-ancestor escalation is redundant while a promise is live: if
    the promise is never honoured, the problem-level stall predicate
    still fires (`db._subtree_has_live_frontier` — an `attempting` node
    contributes no live frontier by itself, the 2026-07-09 fix), which
    wakes the Strategist ONCE for the whole problem instead of once per
    level. Nothing here weakens that guarantee: a shelved sub-goal with
    no live promise still settles the parent exactly as before.
    """
    row = conn.execute(
        "SELECT batch_id, actor FROM strategist_decisions"
        " WHERE decision_kind = 'ConfirmShelve'"
        "   AND target_id = CAST(? AS TEXT)"
        " ORDER BY id DESC LIMIT 1", (goal_id,)).fetchone()
    # v48 (human_interface_design.md §3.2) — a HUMAN park promises
    # nothing. The pairing rule this predicate reads exists because the
    # machine may never stop itself; the human is the one role allowed to
    # simply stop, so their command carries no compensating Inject and no
    # wait that could ever end. The applier files the row under whatever
    # batch the wake committed, so a NULL batch_id is not the defence.
    if (row is None or not row["batch_id"]
            or str(row["actor"] or "") == "human"):
        return False
    # 'Delegate' joined the promise-carrier set 2026-08-06 (v35 seam,
    # live on the Frankl opener): a park waiting on a sub-group's
    # charter is a promise exactly like a park waiting on minted
    # helpers — the group's terminal transition fills the Delegate
    # row's outcome and completes this batch (state.groups.set_status),
    # so the continuity guarantee is the same as the Inject case. With
    # only 'Inject' counted, the mint resolved in minutes, the predicate
    # read "no live promise", and the root was handed to a review wake
    # to adjudicate a non-question — the exact cascade b047b910 killed,
    # resurfacing through kind-enumeration (the failure mode
    # `predicted_batch_delta`'s comment names).
    # …and a promise waits on WORK, not on an empty column. A helper
    # whose own goal got parked keeps `outcome` NULL forever by design
    # (P13 4284, 2026-06-15), so spelling the wait "outcome IS NULL"
    # made such a promise permanently un-due: the parent strategy never
    # stalls, the branch never reaches a review wake, and the line is
    # held open by a step nobody is working on. `db.batch_has_running_
    # step` asks the produced work, the same structured signal the
    # stall predicate's active-check reads (SP7 2026-09-03).
    return db.batch_has_running_step(conn, str(row["batch_id"]))


def _strategy_waits_on_promised_batch(conn: sqlite3.Connection,
                                      strategy_id: int) -> bool:
    """True iff any of this strategy's shelved sub-goals is still
    awaiting its promised helper batch (`_awaiting_promised_batch`)."""
    for r in conn.execute(
        "SELECT g.id FROM strategy_subgoals ss"
        " JOIN goals g ON g.id = ss.subgoal_id"
        " WHERE ss.strategy_id = ? AND g.status = 'shelved'",
        (strategy_id,),
    ).fetchall():
        if _awaiting_promised_batch(conn, int(r["id"])):
            return True
    return False


def _maybe_stall_parent_strategies(conn: sqlite3.Connection,
                                   goal_id: int) -> None:
    """Soft-shelve UPWARD transition — the reopenable counterpart of
    `_kill_upward_chain` (which is hard-terminal only).

    When `goal_id` soft-shelves, any 'proposed' parent strategy (one that
    USES it as a sub-goal) whose sub-goals have now ALL settled — zero
    alive, >=1 soft-shelved, and NO hard-terminal (`disproved`)
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
      - a hard-terminal (`disproved`) sibling → `_kill_upward_chain`
        kills the parent STRATEGY and routes the exhausted parent goal
        to Strategist review;
      - a wrong-context park (`parent_needs_fix`) → the same kill,
        driven by `_propagate_wrong_context`, which deliberately skips
        this stall pass: a strategy about to be killed must not be
        parked as 'stalled' first (a 'stalled' row is invisible to
        `_kill_upward_chain`'s `status = 'proposed'` filter);
      - all sub-goals proved → 'succeeded' (handled at proof time);
      - any alive sibling → genuinely in flight, stays 'proposed';
      - a shelved sub-goal whose promised helper batch is still in
        flight → the promise IS the schedule (see
        `_awaiting_promised_batch`), so the parent keeps waiting.
    """
    parents = conn.execute(
        "SELECT s.id, s.goal_id FROM strategies s"
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
                and comp.get("disproved", 0) == 0):
            if _strategy_waits_on_promised_batch(conn, sid):
                continue
            apply_strategy_transition(
                conn, sid, "stalled", event="parent_stall")
            _maybe_review_goal_out_of_routes(conn, int(p["goal_id"]))


def _maybe_review_goal_out_of_routes(conn: sqlite3.Connection,
                                     goal_id: int) -> None:
    """Escalate a goal whose LAST live route was just parked.

    When `_maybe_stall_parent_strategies` stalls a strategy and its goal
    is left `attempting` with zero 'proposed'/'succeeded' strategies,
    nothing will ever touch that goal again: BFS dispatches only `open`
    goals, and the park machinery's implicit contract ("the Strategist
    will adjudicate") relied on a wake that the stall predicate's
    condition 4 could suppress via this very goal's `attempting` status
    (2026-07-09 putnam_2025_b6 mutual deadlock; fixed on the predicate
    side by `db._subtree_has_live_frontier`). Hand the goal to the T2
    review path — the same `_enqueue_strategist_review` used by the
    shelve-threshold branch — so the Strategist decides Reopen /
    ConfirmShelve / new Inject at the moment the last route parks,
    level by level up the chain (each parent parks only after the
    Strategist settles its child; `pending_strategist_review` counts as
    alive in the sibling composition above)."""
    g = db.get_goal(conn, goal_id)
    if g is None or str(g["status"]) != "attempting":
        return
    live = conn.execute(
        "SELECT 1 FROM strategies WHERE goal_id = ?"
        " AND status IN ('proposed','succeeded') LIMIT 1",
        (goal_id,),
    ).fetchone()
    if live is not None:
        return
    _enqueue_strategist_review(conn, goal_id)


def _propagate_shelve(conn: sqlite3.Connection, goal_id: int) -> None:
    """Inward strategy kill for a goal that just hit a terminal status.

    Phase 6: caller is responsible for the (separate) upward strategy
    kill if the terminal status warrants it (`disproved`, via
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
    _review_cited_waiters(conn, goal_id)


def _review_cited_waiters(conn: sqlite3.Connection, goal_id: int) -> None:
    """Owner design 2026-08-25 — the shelve conducts along WAIT edges
    immediately ("align" for citations). A strategy that CITED this
    goal (link_kind='cited') blocks at verify until it proves; nothing
    ever dispatches a shelved goal, and `_maybe_stall_parent_strategies`
    only notices after every OTHER sub-goal settles — so the waiter
    starved silently, sometimes for days (18 live waiters measured on
    union_closed, 2026-08-25, incl. two strategies hung on one parked
    certificate). Each citing strategy's own goal now returns to ITS
    group's review at shelve time: the owning strategist holds both
    legal moves — re-plan without the parked prerequisite, or revive
    it by Inject with the need spelled out. The machine only escalates
    to review; shelving stays a strategist's verb (no auto-shelve),
    and the citing strategy stays 'proposed' so a revival resumes it
    without ceremony."""
    parked = conn.execute("SELECT status FROM goals WHERE id = ?",
                          (goal_id,)).fetchone()
    if parked is None or str(parked["status"]) != "shelved":
        # Hard terminals (`disproved`) reach here through the
        # composite propagators; their citing strategies are
        # `_kill_upward_chain`'s business — conducting a review first
        # would race the kill's own cascade.
        return
    waiters = conn.execute(
        "SELECT DISTINCT s.goal_id AS wid FROM strategy_subgoals ss"
        " JOIN strategies s ON s.id = ss.strategy_id"
        " WHERE ss.subgoal_id = ? AND ss.link_kind = 'cited'"
        "   AND s.status = 'proposed'",
        (goal_id,),
    ).fetchall()
    for w in waiters:
        wid = int(w["wid"])
        if wid == goal_id:
            continue
        row = conn.execute("SELECT status FROM goals WHERE id = ?",
                           (wid,)).fetchone()
        if row is not None and str(row["status"]) in ("open", "attempting"):
            _enter_pending_review(conn, wid,
                                  event="cited_dependency_parked")


def park_group_anchor(conn: sqlite3.Connection,
                      anchor_goal_id: "int | None") -> None:
    """Shelve a retiring group's anchor goal if it is still alive.

    ONE spelling for every way a group leaves with a live anchor. It
    was inlined in `_commit_close_group` only, so a rescue-shape group
    retired by the ancestor CASCADE (or the startup orphan sweep) left
    its anchor `attempting` — parked-alive under a closed group, never
    dispatched again (BFS skips `attempting`) and with no shelve record
    for citation-revival, where the direct `CloseGroup` path would have
    shelved it (acceptance pass, 2026-08-17). A park, not a verdict:
    the goal itself was not refuted, its group's charter went away —
    exactly what shelve's revivability is for.
    """
    if anchor_goal_id is None:
        return
    from . import db as _db
    g = _db.get_goal(conn, int(anchor_goal_id))
    if g is not None and str(g["status"]) in (
            "open", "attempting", "pending_strategist_review", "frozen"):
        _set_goal_terminal_and_propagate(conn, int(anchor_goal_id),
                                         "shelved")
        _propagate_shelve(conn, int(anchor_goal_id))


def _kill_upward_chain(conn: sqlite3.Connection, goal_id: int) -> None:
    """Phase 6 — kill the strategies USING this goal as a sub-goal,
    then cascade to their parent goals.

    Called for the two verdicts that repudiate a decomposition: a
    kernel `disproved` sub-goal, and a `parent_needs_fix` park (the
    worker's "this decomposition is wrong"). An ordinary `shelved`
    deliberately leaves the upward chain alive so a future Reopen can
    revive it.

    An EXHAUSTED parent (attempts past SHELVE_THRESHOLD via this
    cascade) always goes to `pending_strategist_review` — never to a
    terminal of its own. Until 2026-09-04 the `parent_needs_fix` arm
    passed a `parent_terminal_status='dead'` that killed the parent
    GOAL outright and recursed upward; the owner ruling retires that:
    a parent statement whose child was mis-decomposed was never itself
    judged, so exhaustion is the Strategist's call (ConfirmShelve /
    Reopen / a new Inject), exactly as the disproved cascade already
    treated it.
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
            # Exhaustion is the Strategist's call. Route through
            # pending_strategist_review so it sees the exhausted parent
            # and decides ConfirmShelve / Reopen / Inject. Mirrors the
            # agent_shelved path.
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
    for a disproved goal (kernel counterexample; hard terminal)."""
    _propagate_shelve(conn, goal_id)
    _kill_upward_chain(conn, goal_id)


def _propagate_wrong_context(conn: sqlite3.Connection,
                             goal_id: int) -> None:
    """Composite for a `parent_needs_fix` park: the worker says the
    DECOMPOSITION was wrong, so every strategy that hangs on this goal
    dies — inward (the strategies trying to prove it, now moot) and
    upward (the strategy that minted it into a context that does not
    hold). The goal itself is only PARKED (`shelved`): its statement
    was never judged, and a citation / Inject / Delegate can revive it
    under a context that fits.

    Deliberately NOT `_propagate_shelve`: that helper's
    `_maybe_stall_parent_strategies` pass would park the very parent
    strategies `_kill_upward_chain` is about to kill, and a 'stalled'
    row is invisible to the kill's `status = 'proposed'` filter — the
    upward kill, its sibling-orphan sweep and the parent's attempts++
    would all silently stop happening. Before the retirement of the
    `dead` goal status this was held by the composition guard
    `comp.get("dead", 0) == 0` inside the stall predicate; with the
    sub-goal now `shelved` the guard no longer fires, so the ordering
    is made explicit here instead."""
    _inward_kill_strategies(conn, goal_id)
    _review_cited_waiters(conn, goal_id)
    _kill_upward_chain(conn, goal_id)


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
        # (proved/shelved/disproved), late cascades from in-flight
        # pipelines must not mutate it.
        # Without the 'shelved' guard, a Backward 'success' that races
        # past the shelve transition would unconditionally flip status
        # back to 'attempting' (observed: goal stuck at attempts=N with
        # status='attempting' instead of 'shelved').
        # 'disproved' added with the sibling-orphan cascade
        # (_kill_upward_chain sibling sweep): a worker dispatched on
        # g2 before g2 cascaded-shelved (because its sibling g3 hit a
        # hard terminal and killed their shared parent strategy) must
        # not flip g2 back to attempting.
        if row and row["status"] in ("proved", "shelved", "disproved"):
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
    from .failures import PROVIDER_INFRA_REASONS as _INFRA_REASONS
    is_infra = (outcome == "failed" and failure_reason in _INFRA_REASONS)

    # Phase 7 — `moot` outcome: pipeline detected the goal already
    # terminated (sibling proved / shelved / propagated shelve) before
    # spawning. No state mutation, no attempts++, no dead_attempt write
    # (decision 2). bfs_refill won't re-queue a terminal goal anyway.
    if outcome == "moot":
        return

    if kind == "Theorist":
        # The pipeline settles its own request on every road it
        # controls; a worker that died of an exception controls none of
        # them, and a NULL outcome is what "the theory layer is still
        # working" means everywhere else — it would suppress the group's
        # stall rescue forever and never wake it. This is the backstop,
        # `outcome IS NULL`-guarded, so a normal return costs nothing.
        if decision_id is not None:
            if is_infra:
                # …except when the death was the FRAMEWORK's. An infra
                # cause says nothing about the request, so settling on
                # it hands work back to the Strategist for a fault it
                # cannot act on (union_closed d5922 / d5933, 2026-09-05:
                # two rc=126 deaths settled `failed:quota_exhausted`
                # telling it to re-issue the request itself). Leave the
                # row open — `reconcile_stuck_states`' Theorize arm
                # re-queues an unanswered request every tick, and the
                # kind's own quota backoff is what makes that "after the
                # cooldown". Bounded by the count, so a provider broken
                # for good still reaches the Strategist.
                from ..pipeline.theorist import (INFRA_REDISPATCHES,
                                                 SPAWN_DIED_DETAIL)
                n = db.record_decision_infra_death(conn, int(decision_id))
                if n <= INFRA_REDISPATCHES:
                    print(f"[theorist] d{decision_id} died on "
                          f"{failure_reason} ({n}/{INFRA_REDISPATCHES}) "
                          f"— the request stands, re-queued after the "
                          f"cooldown", flush=True)
                    return
                # Spent: the pipeline's own headline, so the road reads
                # the same whichever half of it ran out first.
                _record_inject_decision_outcome(
                    conn, int(decision_id), "failed", failure_reason,
                    detail=SPAWN_DIED_DETAIL.format(reason=failure_reason))
                _maybe_enqueue_inject_batch_done(conn, int(decision_id))
                return
            _record_inject_decision_outcome(
                conn, int(decision_id), outcome or "failed",
                failure_reason, pipeline_id=pipeline_id)
            _maybe_enqueue_inject_batch_done(conn, int(decision_id))
        return

    if kind in ("Formalizer", "Builder"):
        # Merged worker (update_plan_2026_07 #1): goal jobs ride the
        # Backward cascade arm (the strategy-frame engine — identical
        # outcome shapes), mint jobs the Forward arm. Legacy 'Builder'
        # queue rows also dispatch to the merged engine now, so their
        # results are Backward-shaped too — routing them to the old
        # Builder arm dropped 'success' outcomes on the floor
        # (review 07-27: cascade fall-through → duplicate dispatch).
        kind = "Backward" if target_kind == "Goal" else "Forward"

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
            # Under SHELVE the goal stays open and the next bfs_refill
            # re-enqueues it for the Formalizer — no extra cascade work
            # needed (no session_id column to clear post Phase 7-D).
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
            #   * parent_needs_fix → PARKED 'shelved' with the
            #     `wrong_context_park` event (the decomposition was
            #     wrong, the statement was never judged); every
            #     strategy hanging on it dies, inward and upward.
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
                    conn, int(target_id), "shelved",
                    event="wrong_context_park",
                    reason="parent_needs_fix: the decomposition that "
                           "minted this goal was wrong")
                _propagate_wrong_context(conn, int(target_id))
                return
            if failure_reason == "agent_shelved":
                db.increment_goal_attempts(conn, int(target_id))
                _enqueue_strategist_review(conn, int(target_id))
                return
            # return_to_nl (NL-first 2026-07-25; renamed 2026-08-11 to
            # say its DESTINATION, since one exit now carries three
            # diagnoses): the argument does not settle this goal — same
            # review routing as agent_shelved (transitional, chain
            # stays alive); the Strategist either argues the claim to
            # closure in the Proof or retires it.
            if failure_reason == "return_to_nl":
                db.increment_goal_attempts(conn, int(target_id))
                _enqueue_strategist_review(conn, int(target_id))
                return
            # `needs_decomposition` directive (legacy `too_hard`):
            # Legacy Builder `needs_decomposition` decline (the
            # Formalizer splits in-session, so only pre-merge queue
            # rows reach this): count the attempt; over-threshold goals
            # go to strategist review. The old entry_kind flip is gone
            # with the routing column (v33).
            if failure_reason == "agent_declined":
                n = db.increment_goal_attempts(conn, int(target_id))
                if n >= _shelve_threshold():
                    _enqueue_strategist_review(conn, int(target_id))
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
                _problem = _queue_problem_of(conn, target_id, target_kind)
                if _problem:
                    db.enqueue(conn, kind="Formalizer",
                               target_id=target_id,
                               target_kind=target_kind, priority=20,
                               decision_id=decision_id,
                               problem=_problem)
                    print(f"[forward-retry] re-queued {target_kind}="
                          f"{target_id} decision_id={decision_id} after "
                          f"{failure_reason}", flush=True)
                else:
                    # Same poison-row guard as the Strategist branch.
                    print(f"[forward-retry] SKIPPED re-queue for "
                          f"{target_kind}={target_id}: problem "
                          f"unresolvable", flush=True)
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
                "SELECT produced_goal_id, outcome FROM strategist_decisions"
                " WHERE id = ?", (decision_id,),
            ).fetchone()
            if row is not None and row["produced_goal_id"] is not None:
                # The produced goal owns this decision's outcome now.
                # Two shapes reach here, and only one of them is the
                # sorry-bearing lemma the deferral was written for:
                #
                #  * outcome still NULL — the lemma is `:= by sorry`.
                #    Leave it: `propagate_inject_outcome_from_goal` fills
                #    it when the goal terminates and fires the relay from
                #    there.
                #  * outcome ALREADY filled — the brick landed proved in
                #    one shot (or an alias landed), so forward.py filled
                #    it at commit time and the goal, being terminal, will
                #    never transition again. Nothing has fired the relay
                #    for this row and nothing ever will, so it must fire
                #    HERE or the batch completes in silence: the
                #    Strategist is then woken only by T4's stall backstop
                #    and reads `## Framework stalled` on a batch where
                #    every brick succeeded (SG 2026-08-02). The produced-
                #    goal link became unconditional in e9e55599, which is
                #    when this second shape started arriving.
                if row["outcome"] is not None:
                    _maybe_enqueue_inject_batch_done(conn, decision_id)
            else:
                _record_inject_decision_outcome(
                    conn, decision_id, outcome, failure_reason,
                    pipeline_id=pipeline_id,
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
        # Helper recorded N dead_attempts + N attempts++ (eagerly, v38)
        # for the N failed retries; cascade does status transition only.
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
        # needs_fix → 'shelved' park + propagate; agent_shelved →
        # 'pending_strategist_review' + enqueue, no propagate).
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
                conn, int(target_id), "shelved",
                event="wrong_context_park",
                reason="parent_needs_fix: the decomposition that "
                       "minted this goal was wrong")
            _propagate_wrong_context(conn, int(target_id))
            return
        if failure_reason == "agent_shelved":
            db.increment_goal_attempts(conn, int(target_id))
            _enqueue_strategist_review(conn, int(target_id))
            return
        # return_to_nl (NL-first, 2026-07-25): same review
        # routing as agent_shelved — see the Builder branch above.
        if failure_reason == "return_to_nl":
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
            # the drift loudly. Parked, not settled: the statement is fine,
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
            _problem = _queue_problem_of(conn, target_id, target_kind)
            if _problem:
                db.enqueue(conn, kind="Strategist", target_id=target_id,
                           target_kind=target_kind, priority=20,
                           problem=_problem)
                print(f"[strategist-retry] re-queued "
                      f"{target_kind}={target_id}"
                      f" after {failure_reason}", flush=True)
            else:
                # An empty problem would be a POISON row: unpoppable
                # under a scoped run yet visible to `is_in_queue`, so it
                # suppresses T1/T4 for this target forever (2026-08-03
                # SLC stall). Skip the retry and say so — the T4 stall
                # backstop re-wakes the group within a tick.
                print(f"[strategist-retry] SKIPPED re-queue for "
                      f"{target_kind}={target_id}: problem unresolvable "
                      f"— leaving the wake to the T4 stall backstop",
                      flush=True)
        return

    # Verify removed as a worker_kind. Strategy verification + parent
    # promotion happens in `verify.verify_housekeeping`, called at the
    # end of each dispatcher tick (see `run` below).
