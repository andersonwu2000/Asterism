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


class IllegalTransition(RuntimeError):
    """Raised (strict mode only) when a (from, to) edge is not declared in the
    registry. In lenient/production mode the same condition is logged with a
    `[transition-violation]` marker and the write proceeds."""


def _strict() -> bool:
    return os.environ.get("ASTERISM_STRICT_TRANSITIONS") == "1"


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
                          *, event: str = "", reason: str = "") -> None:
    """The single sanctioned mutator of `goals.status`.

    Reads the current status, validates `(current -> to_state)` against
    `GOAL_EDGES`, then performs the write via `db.update_goal_status` (which
    also clears `integrity_verified` for any non-'proved' target).

    `event` is a short forensic label for the driving event (e.g.
    'builder_proved', 'strategist_reopen'); it is used in violation logs and,
    later (#11 Phase 3), as the key of the (state, event) exhaustiveness table.
    `reason` carries an optional failure_reason for richer logging.
    """
    assert to_state in GOAL_STATES, f"unknown goal state {to_state!r}"
    row = conn.execute(
        "SELECT status FROM goals WHERE id = ?", (goal_id,),
    ).fetchone()
    frm = str(row["status"]) if row is not None else None
    _check("goal", frm, to_state, GOAL_EDGES, event)
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
