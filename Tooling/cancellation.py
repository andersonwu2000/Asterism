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


_ALL_PIPELINE_KINDS: tuple[str, ...] = (
    "Builder", "Backward", "Refuter", "Forward",
    "Generalizer", "Counterexample", "ConstructionSearch", "Strategist",
)

# Per-condition kind sets (architecture.md §6).
_COND1_KINDS: tuple[str, ...] = _ALL_PIPELINE_KINDS  # cancel any kind on G
_COND2_KINDS: tuple[str, ...] = _ALL_PIPELINE_KINDS  # cancel any kind on G + ¬G
_COND3_KINDS: tuple[str, ...] = (
    # Counterexample silver: cancel Builder/Backward + other Counterexample;
    # Refuter kept (silver→gold upgrade path).
    "Builder", "Backward", "Counterexample",
)
_COND4_KINDS: tuple[str, ...] = ("Builder", "Backward")


@dataclass
class CancellationVerdict:
    """A cascade verdict that triggers cancellation per the white-list.

    `kind` ∈ {'goal_proved', 'twin_refuted', 'counterexample_silver',
              'strategy_dead'}.

    Required fields per kind:
      goal_proved             — goal_id
      twin_refuted            — goal_id (G), twin_id (¬G)
      counterexample_silver   — goal_id (G)        [DEFERRED in C31]
      strategy_dead           — strategy_id
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
        return _select(conn, target_ids=[str(verdict.goal_id)],
                       kinds=_COND1_KINDS, target_kind="Goal")

    if verdict.kind == "twin_refuted":
        if verdict.goal_id is None or verdict.twin_id is None:
            raise ValueError(
                "twin_refuted verdict requires both goal_id (G) and twin_id (¬G)"
            )
        return _select(
            conn,
            target_ids=[str(verdict.goal_id), str(verdict.twin_id)],
            kinds=_COND2_KINDS, target_kind="Goal",
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
