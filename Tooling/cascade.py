"""Cascade dispatch table (P3 C25 — minimal extraction; P4 C30 extended).

phase3_cache.md §任務序列 #11: "Cascade dispatch 表重構（Tooling/cascade.py）：
覆蓋直接 effect; cascade upward 仍走 BFS 偵測機制".

This module exposes the central (pipeline_kind, outcome) → action mapping
that the scheduler consults. P3 keeps the scheduler's existing
`_cascade_backward` / `_cascade_builder` methods as the dispatch points —
they look up the action here rather than embedding a hard-coded if/else
chain. The full action-execution refactor (handlers as Python functions
in this module) lands when P4 conjecture / P5 construction add silver →
gold / twin / refuter actions and the inline if/else would not scale.

P4 C30 extends the table with Refuter outcomes:
  - (Refuter, success): ¬G goal already inserted by Refuter.commit; cascade
    is a no-op acknowledgement (BFS picks up the new goal next cycle).
  - (Refuter, exhausted): record dead_attempts + archive_check (mirrors
    Backward exhausted handling).

The actual ¬G-proved → twin-G-refuted cascade fires on Builder.proved
when the proved goal has origin='refuter_negation' + twin_of != NULL —
that branch lives in scheduler._cascade_twin_to_refuted, dispatched via
existing (Builder, proved) entry, not via a separate Refuter table key.
Spec arch.md §6 line 330 字面 'Builder/Backward 鏈成功 → twin (若有)
status=refuted'.

CASCADE_FAULT env hook (P4 acceptance #9): set to 'dual_proved' to force
the dual-proved invariant violation path during twin cascade — emits
fatal + halts. 'unique_violation' / 'fk_invalid' modes reserved (raise
on any cascade UPDATE) but not yet wired to specific simulation points.

Cascade upward propagation (sub-Goal proved → next cycle structural refill
→ enqueue Builder for parent strategy) is NOT in this table — it is an
implicit chain handled by `_run_structural_refill` BFS, per phase3 spec
(§Cascade rules dispatch 表覆蓋範圍明確).

Public API:
    DISPATCH_TABLE: dict[(pipeline_kind, outcome), CascadeAction]
    get_action(pipeline_kind, outcome) -> CascadeAction | None
    check_cascade_fault(mode) -> None  -- raises if CASCADE_FAULT matches
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CascadeAction:
    """Description of what cascade should do for a (pipeline_kind, outcome).

    Currently descriptive metadata only; scheduler matches on `name` to
    pick a handler. P4/P5 will turn `handler` into a callable when the
    table grows beyond the hand-written branches.

    `target_ids` is forward-compat for P4 twin propagation — P3 actions are
    all single-target and leave it as `()`; P4 Refuter / Counterexample
    cancel cascades will populate (G.id, ¬G.id) tuples per spec §In line 44.
    """
    name: str
    description: str
    handler: str = ""  # Reactor method name; empty = no handler (P4+ wiring)
    side_effects: tuple[str, ...] = field(default_factory=tuple)
    target_ids: tuple[int, ...] = ()  # forward-compat: P4 twin propagation


# (pipeline_kind, outcome) → CascadeAction
DISPATCH_TABLE: dict[tuple[str, str], CascadeAction] = {
    ("Builder", "proved"): CascadeAction(
        name="builder_proved",
        description="Trust set construct + accept rule + UPDATE goal proved.",
        handler="_cascade",
        side_effects=("update_strategy_succeeded", "update_goal_proved",
                       "build_trust_set", "invalidate_cache"),
    ),
    ("Builder", "exhausted"): CascadeAction(
        name="builder_dead",
        description="Mark strategy dead; if all strategies dead → shelve goal.",
        handler="_mark_strategy_dead",
        side_effects=("update_strategy_dead", "maybe_shelve_goal",
                       "archive_check_builder"),
    ),
    ("Builder", "hasSorry"): CascadeAction(
        name="builder_dead",
        description="Same as exhausted (sorry detection).",
        handler="_mark_strategy_dead",
        side_effects=("update_strategy_dead", "maybe_shelve_goal",
                       "archive_check_builder"),
    ),
    ("Backward", "success"): CascadeAction(
        name="backward_success",
        description="Sub-goals + strategy committed by Backward.run; "
                    "leaf-strategy success enqueues Builder inline.",
        handler="_cascade_backward",
        side_effects=("maybe_enqueue_leaf_builder",),
    ),
    ("Backward", "exhausted"): CascadeAction(
        name="backward_failure",
        description="INSERT dead_attempts + archive_check + IH-trap check.",
        handler="_cascade_backward",
        side_effects=("record_backward_failure", "archive_check_backward",
                       "archive_ih_trap"),
    ),
    ("Backward", "unproductive"): CascadeAction(
        name="backward_failure",
        description="Same as exhausted (no useful decomposition produced).",
        handler="_cascade_backward",
        side_effects=("record_backward_failure", "archive_check_backward",
                       "archive_ih_trap"),
    ),
    ("Refuter", "success"): CascadeAction(
        name="refuter_success",
        description="¬G already inserted by Refuter.commit; structural "
                    "refill picks it up next cycle. No direct cascade.",
        handler="_cascade_refuter",
        side_effects=("acknowledge_negation_goal",),
    ),
    ("Refuter", "exhausted"): CascadeAction(
        name="refuter_failure",
        description="INSERT dead_attempts + archive_check on G "
                    "(Refuter retry budget mirrors Backward).",
        handler="_cascade_refuter",
        side_effects=("record_refuter_failure", "archive_check_refuter"),
    ),
    # ── P7 entries (C52-C54) ──────────────────────────────────────
    # Forward / Generalizer produce orphan Goals; structural refill BFS
    # picks them up the next cycle. No direct cascade.
    ("Forward", "success"): CascadeAction(
        name="forward_success",
        description="Forward.commit inserted new orphan Goals; "
                    "BFS handles refill (cascade is explicit no-op).",
        handler="_cascade_forward",
    ),
    ("Forward", "no_novel"): CascadeAction(
        name="forward_no_novel",
        description="All candidates were dups; explicit no-op.",
        handler="_cascade_forward",
    ),
    ("Forward", "exhausted"): CascadeAction(
        name="forward_failure",
        description="Agent gave up; _cascade_forward records dead_attempt "
                    "(target_kind='forward').",
        handler="_cascade_forward",
        side_effects=("record_forward_failure",),
    ),
    ("Generalizer", "success"): CascadeAction(
        name="generalizer_success",
        description="G* inserted as new tree root; "
                    "BFS picks it up (cascade is explicit no-op).",
        handler="_cascade_generalizer",
    ),
    ("Generalizer", "no_novel"): CascadeAction(
        name="generalizer_no_novel",
        description="G* matched an existing entry; explicit no-op.",
        handler="_cascade_generalizer",
    ),
    ("Generalizer", "unproductive"): CascadeAction(
        name="generalizer_unproductive",
        description="Agent self-reports G already maximal; "
                    "_cascade_generalizer records dead_attempt (target_kind='Goal'). "
                    "Spec §8: do NOT update goals.blocked_pipelines.",
        handler="_cascade_generalizer",
        side_effects=("record_generalizer_failure",),
    ),
    ("Generalizer", "exhausted"): CascadeAction(
        name="generalizer_failure",
        description="self_verify retry exhausted; "
                    "_cascade_generalizer records dead_attempt (target_kind='Goal').",
        handler="_cascade_generalizer",
        side_effects=("record_generalizer_failure",),
    ),
    # P7 演習 refactor (路線 1): Solver = 1-shot direct proof attempt
    # spun out of Backward's old Path A. success enqueues Builder for the
    # committed leaf strategy; exhausted records a Goal-scoped dead_attempt
    # so subsequent BFS opens the Backward fallback gate.
    ("Solver", "success"): CascadeAction(
        name="solver_success",
        description="Solver committed a leaf strategy; "
                    "_cascade_solver enqueues Builder to verify.",
        handler="_cascade_solver",
        side_effects=("enqueue_builder",),
    ),
    ("Solver", "exhausted"): CascadeAction(
        name="solver_failure",
        description="Solver agent couldn't produce a verifiable 1-shot "
                    "proof; record dead_attempt so Backward fallback "
                    "gate opens on next BFS tick.",
        handler="_cascade_solver",
        side_effects=("record_solver_failure",),
    ),
    # Strategist itself: success commits decisions; demux already ran inside
    # Strategist.run. Cascade is an explicit no-op acknowledgement.
    ("Strategist", "success"): CascadeAction(
        name="strategist_success",
        description="Strategist commit + demux already landed inside .run; "
                    "explicit no-op acknowledgement.",
        handler="",
    ),
    ("Strategist", "exhausted"): CascadeAction(
        name="strategist_failure",
        description="Strategist agent failed to produce valid JSON within "
                    "max_retries; explicit no-op (no dead_attempts written).",
        handler="",
    ),
}


# ---------------------------------------------------------------------------
# Shelve cancel helper (P7 C54)
# ---------------------------------------------------------------------------


def cancel_running_for_goal(conn, goal_id: int) -> int:
    """Mark all in-flight pipelines and queued tasks for `goal_id` as cancelled.

    Used by Strategist demux when a Goal is shelved (architecture v3 §6
    cancellation row 6). Returns the number of pipelines + queue rows
    affected. Pipelines status='running' move to 'failed' with
    outcome='cancelled'; queue entries for the Goal are deleted.
    """
    now = os.environ.get("ASTERISM_NOW") or _now_iso()
    with conn:
        cur = conn.execute(
            "UPDATE pipelines SET status = 'failed', outcome = 'cancelled', "
            "finished_at = ? "
            "WHERE target_id = ? AND status = 'running'",
            (now, str(goal_id)),
        )
        cancelled = cur.rowcount or 0
        cur = conn.execute(
            "DELETE FROM queue WHERE target_id = ?",
            (str(goal_id),),
        )
        cancelled += cur.rowcount or 0
    return cancelled


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# Module-level helper used by scheduler. Defined here so all CASCADE_FAULT
# semantics live in one file.
class CascadeFault(Exception):
    """Raised by check_cascade_fault to simulate cascade SQL / invariant
    failure paths in tests (acceptance #9 family)."""


def check_cascade_fault(mode: str) -> None:
    """If CASCADE_FAULT env var equals `mode`, raise CascadeFault.

    Modes (P4 acceptance #9):
      'dual_proved'      — simulate G + ¬G both proved invariant violation
      'unique_violation' — simulate SQLite UNIQUE constraint failure
      'fk_invalid'       — simulate FK reference invalid

    Caller catches CascadeFault, emits fatal event + raises FatalError.
    Modes other than 'dual_proved' are reserved names (no production
    trigger sites yet); the wiring lands when those specific cascade
    failure paths get exercised by test cases.
    """
    fault = os.environ.get("CASCADE_FAULT")
    if fault and fault == mode:
        raise CascadeFault(
            f"CASCADE_FAULT={mode} simulated invariant violation"
        )


def get_action(
    pipeline_kind: str,
    outcome: str,
) -> CascadeAction | None:
    """Return the CascadeAction for (pipeline_kind, outcome) or None.

    Unknown combinations (e.g. P4 Refuter outcomes before P4 lands) return
    None; scheduler treats this as "no cascade" and emits a diagnostic
    event so the gap is observable.
    """
    return DISPATCH_TABLE.get((pipeline_kind, outcome))
