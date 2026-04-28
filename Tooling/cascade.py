"""Cascade dispatch table (P3 C25 — minimal extraction).

phase3_cache.md §任務序列 #11: "Cascade dispatch 表重構（Tooling/cascade.py）：
覆蓋直接 effect; cascade upward 仍走 BFS 偵測機制".

This module exposes the central (pipeline_kind, outcome) → action mapping
that the scheduler consults. P3 keeps the scheduler's existing
`_cascade_backward` / `_cascade_builder` methods as the dispatch points —
they look up the action here rather than embedding a hard-coded if/else
chain. The full action-execution refactor (handlers as Python functions
in this module) lands when P4 conjecture / P5 construction add silver →
gold / twin / refuter actions and the inline if/else would not scale.

Cascade upward propagation (sub-Goal proved → next cycle structural refill
→ enqueue Builder for parent strategy) is NOT in this table — it is an
implicit chain handled by `_run_structural_refill` BFS, per phase3 spec
(§Cascade rules dispatch 表覆蓋範圍明確).

Public API:
    DISPATCH_TABLE: dict[(pipeline_kind, outcome), CascadeAction]
    get_action(pipeline_kind, outcome) -> CascadeAction | None
"""
from __future__ import annotations

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
}


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
