"""Cancellation white-list (P4 C31).

Replaces P2/P3's "kill all running pipelines on goal_id" simplification
with the verdict-aware white-list per architecture.md §6 (cancellation
table, 4 conditions).

Conditions:
  1. goal_proved (Goal G proved with full classical proof) →
        cancel target_id == G.id pipelines (any kind).
  2. twin_refuted (G refuted via Refuter→Builder ¬G chain) →
        cancel target_id == G.id + target_id == ¬G.id (each side).
        Cascade goes through twin_of FK.
  3. counterexample_silver (Counterexample writes silver verdict on G) →
        cancel G.id Builder / Backward / other Counterexample. Refuter
        kept (so silver→gold upgrade remains reachable).
        ** DEFERRED ** in C31 — Counterexample pipeline is deferred per
        task.md ## 延後 cycles. The case is wired here for forward-compat
        (verdict object + select function recognize the kind) but no
        production caller exists until Counterexample lands.
  4. strategy_dead (Strategy S → all strategies dead, parent shelved) →
        cancel strategy_id == S.id Builder / Backward (same-Strategy
        scope; other strategies on the same Goal can keep running).

Runtime behaviour caveat (carried from C15/P2):
  Thread-pool pipelines cannot be externally SIGTERM'd. C31 does NOT add
  forced thread termination. Instead:
    - Pipeline rows whose target became terminal are marked cancelled by
      the cascade event log (visible to operators).
    - step1_stale_filter (extended in C31 to cover Refuter) drops stale
      pipeline_finished events post-hoc so cascade does not re-act.
    - P5+ subprocess providers can issue real SIGTERM via lake._kill_tree
      (already used by lake harness; not yet wired to cancellation).

Public API:
    CancellationVerdict (dataclass — kind + relevant ids)
    select_pipelines_to_cancel(conn, verdict) -> list[dict]
    cancel_for_verdict(conn, verdict, emit_event) -> int  -- returns count
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable


# Per-condition kind sets — strictly per architecture.md §6 cancellation
# table line 429-433. **Spec L435 字面「新加 pipeline 預設不入白名單（保守）」**
# means we do NOT default to "all kinds"; only the kinds listed in the
# table line. Forward / Generalizer / Strategist are NOT in any condition's
# white-list — when they ship (P7), they must be added explicitly.
_COND1_KINDS: tuple[str, ...] = (
    "Builder", "Backward", "Refuter", "Counterexample", "ConstructionSearch",
)
# spec L430 cond 2「同上」 — same kind set as cond 1.
_COND2_KINDS: tuple[str, ...] = _COND1_KINDS
# Counterexample silver: cancel Builder / Backward / other Counterexample;
# Refuter kept (silver→gold upgrade path).
_COND3_KINDS: tuple[str, ...] = ("Builder", "Backward", "Counterexample")
# Strategy dead: cancel Builder pipelines targeting that Strategy. Backward
# does NOT directly target Strategy in P3+ (Backward.target_kind='Goal'),
# so Backward is post-hoc dropped via step1_stale_filter when the Goal
# eventually shelves; cond 4 only handles Builder targeting Strategy.
# (See C31 R2 MED-3 audit: spec L433 字面 ambiguous, P3+ runtime shape
# settled this way.)
_COND4_KINDS: tuple[str, ...] = ("Builder",)


@dataclass
class CancellationVerdict:
    """A cascade verdict that triggers cancellation per the white-list.

    `kind` ∈ {'goal_proved', 'twin_refuted', 'counterexample_silver',
              'strategy_dead'}.

    Required fields per kind:
      goal_proved             — goal_id
      twin_refuted            — goal_id: G that just became refuted
                                          (status='refuted' via cascade)
                                twin_id: ¬G that is the proved-classical
                                          source driving the refutation
      counterexample_silver   — goal_id (G)        [DEFERRED in C31]
      strategy_dead           — strategy_id

    Naming caveat for twin_refuted (C31 R2 LOW-3): the cancellation
    semantics treat goal_id and twin_id symmetrically — both halves of
    the twin pair are cancelled — so the asymmetric naming is purely
    for audit-trail clarity ("which side became refuted vs which side
    proved"). It does NOT change which pipelines are selected.
    """
    kind: str
    goal_id: int | None = None
    twin_id: int | None = None
    strategy_id: int | None = None


def select_pipelines_to_cancel(
    conn: sqlite3.Connection, verdict: CancellationVerdict,
) -> list[dict]:
    """Return the rows of `pipelines` that should be cancelled for this
    verdict, per the architecture.md §6 white-list.

    Each row dict: {id, kind, target_id, target_kind, status}.
    Only `status='running'` rows are considered (already-finished
    pipelines are immutable; cascade has handled them).

    Unknown verdict kinds raise ValueError — silent-failure red line.
    """
    if verdict.kind == "goal_proved":
        if verdict.goal_id is None:
            raise ValueError("goal_proved verdict requires goal_id")
        return _select_for_goals(conn, [verdict.goal_id], _COND1_KINDS)

    if verdict.kind == "twin_refuted":
        if verdict.goal_id is None or verdict.twin_id is None:
            raise ValueError(
                "twin_refuted verdict requires both goal_id (G) and twin_id (¬G)"
            )
        return _select_for_goals(
            conn, [verdict.goal_id, verdict.twin_id], _COND2_KINDS,
        )

    if verdict.kind == "counterexample_silver":
        # **Deferred** per task.md ## 延後 cycles. Wired so future
        # Counterexample can use the verdict path; raises if invoked
        # before Counterexample ships (caller bug indicator).
        raise NotImplementedError(
            "counterexample_silver cancellation deferred — "
            "Counterexample pipeline is deferred (task.md 延後 cycles)"
        )

    if verdict.kind == "strategy_dead":
        if verdict.strategy_id is None:
            raise ValueError("strategy_dead verdict requires strategy_id")
        return _select(
            conn,
            target_ids=[str(verdict.strategy_id)],
            kinds=_COND4_KINDS, target_kind="Strategy",
        )

    raise ValueError(f"unknown CancellationVerdict.kind: {verdict.kind!r}")


def _select(
    conn: sqlite3.Connection,
    *,
    target_ids: list[str],
    kinds: tuple[str, ...],
    target_kind: str,
) -> list[dict]:
    if not target_ids or not kinds:
        return []
    tid_placeholders = ",".join("?" * len(target_ids))
    kind_placeholders = ",".join("?" * len(kinds))
    cur = conn.execute(
        f"SELECT id, kind, target_id, target_kind, status FROM pipelines "
        f"WHERE status = 'running' "
        f"AND target_id IN ({tid_placeholders}) "
        f"AND target_kind = ? "
        f"AND kind IN ({kind_placeholders})",
        (*target_ids, target_kind, *kinds),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _select_for_goals(
    conn: sqlite3.Connection,
    goal_ids: list[int],
    kinds: tuple[str, ...],
) -> list[dict]:
    """Cond 1 / Cond 2 selector — cancel pipelines spanning two target shapes.

    Spec L429 「Builder...全 cancel」字面要求 cond 1 also cancels Builder
    pipelines belonging to the goal. In P3+ the production shape splits
    by target_kind:
      - Goal-targeted (Backward / Refuter / Counterexample / ConstructionSearch):
          target_kind='Goal', target_id=goal_id
      - Strategy-targeted (Builder):
          target_kind='Strategy', target_id=strategy_id, where the strategy's
          parent goal_id is the relevant Goal.

    This helper unions both shapes so the white-list literal alignment
    holds regardless of which production target_kind a kind uses.
    Caller passes the list of relevant goal ids (one for cond 1, two
    for cond 2) and the kind-set; this function fans out internally.
    """
    if not goal_ids or not kinds:
        return []
    target_ids_str = [str(gid) for gid in goal_ids]
    goal_kinds = tuple(k for k in kinds if k != "Builder")
    rows: list[dict] = []
    if goal_kinds:
        rows.extend(_select(
            conn, target_ids=target_ids_str,
            kinds=goal_kinds, target_kind="Goal",
        ))
    if "Builder" in kinds:
        # Builder pipelines target_kind='Strategy'; resolve via strategies row.
        gid_placeholders = ",".join("?" * len(goal_ids))
        strategy_ids = [
            str(r[0])
            for r in conn.execute(
                f"SELECT id FROM strategies WHERE goal_id IN ({gid_placeholders})",
                tuple(goal_ids),
            ).fetchall()
        ]
        if strategy_ids:
            rows.extend(_select(
                conn, target_ids=strategy_ids,
                kinds=("Builder",), target_kind="Strategy",
            ))
    return rows


def cancel_for_verdict(
    conn: sqlite3.Connection,
    verdict: CancellationVerdict,
    emit_event: Callable[[str, dict], None] | None = None,
) -> int:
    """Apply cancellation for the verdict.

    Logs the white-list selection via emit_event (if provided) — the
    actual signal-to-thread is left as a no-op pending P5+ subprocess
    runtime (see module docstring caveat). Returns the count of pipeline
    rows the white-list matched.

    `emit_event` signature: (kind: str, payload: dict) -> None.
    Caller usually passes scheduler._emit_event so the audit trail lives
    in events table.
    """
    rows = select_pipelines_to_cancel(conn, verdict)
    if emit_event is not None:
        emit_event("cascade", {
            "rule": f"cancellation:{verdict.kind}",
            "verdict": {
                "kind": verdict.kind,
                "goal_id": verdict.goal_id,
                "twin_id": verdict.twin_id,
                "strategy_id": verdict.strategy_id,
            },
            "matched_pipeline_ids": [r["id"] for r in rows],
        })
    return len(rows)
