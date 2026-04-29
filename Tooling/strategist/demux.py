"""Strategist decision demux (P7 C50).

Translates a Strategist agent's `decisions` list into concrete side effects:
  - inject pipelines (Backward / Refuter / Forward / Generalizer / etc.)
    enqueue into `queue` with priority=high (left-end push, modeled here
    as priority=10 — scheduler reads ORDER BY priority DESC, id ASC).
  - `Shelve`: directly UPDATE goals.status='shelved'.

Filtering rules (phase7_smarts.md §Strategist 行為 #6):
  - blocked_pipelines: skip inject if the target Goal's
    goals.blocked_pipelines JSON list contains the proposed kind.
  - target Goal must exist + be commit_state='live' + same Problem as the
    Strategist run (cross-Problem inject is rejected; we accept the
    Strategist may know about another Problem from the global top-N
    section but it is the framework round-robin that picks Problems).
  - For Shelve, target only needs to exist + be live (no kind filter).

Payload overrides (phase7_smarts.md #6a/6b/6c):
  - `model`: copied to queue.payload as `{"model": ...}` for the spawning
    pipeline to pass to ModelResolver.
  - `provider`: rejected if not in `agent.providers` config (we accept
    a list passed in by the caller; demux itself does not query SQLite
    config).
  - `budget`: copied verbatim — currently ConstructionSearch consumes it
    (deferred), but storing it now keeps the override path live.

Public API:
    apply_decisions(conn, problem, decisions, allowed_providers=None)
        -> DemuxResult

DemuxResult:
    enqueued        — list of (kind, target_id, payload_dict)
    shelved         — list of target_ids
    rejected        — list of {decision: <orig>, reason: <str>}
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


_INJECT_KINDS = {
    "Backward", "Refuter", "Forward", "Generalizer",
    "Counterexample", "ConstructionSearch",
}
_SHELVE_KIND = "Shelve"
_VALID_DECISION_KINDS = _INJECT_KINDS | {_SHELVE_KIND}

# scheduler treats higher priority = first; align with Backward/Builder
# default priority=0, push Strategist injects ahead by priority=10
# (left-end push approximation).
_INJECT_PRIORITY = 10


@dataclass
class DemuxResult:
    enqueued: list[dict[str, Any]] = field(default_factory=list)
    shelved: list[int] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_goal(conn: sqlite3.Connection, goal_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, problem, slug, status, commit_state, blocked_pipelines "
        "FROM goals WHERE id = ?",
        (goal_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "problem": row[1],
        "slug": row[2],
        "status": row[3],
        "commit_state": row[4],
        "blocked_pipelines": row[5],
    }


def _decode_blocked(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(v, list):
        return []
    return [str(x) for x in v]


def _build_payload(decision: dict[str, Any]) -> dict[str, Any]:
    """Carry over override keys (model / provider / budget / range /
    mutation_operators) into queue.payload."""
    payload: dict[str, Any] = {}
    for key in ("model", "provider", "budget", "range", "mutation_operators"):
        if key in decision and decision[key] is not None:
            payload[key] = decision[key]
    return payload


def _validate_decision_shape(d: Any) -> str | None:
    """Return error string when shape is wrong, None when OK."""
    if not isinstance(d, dict):
        return "decision must be an object"
    kind = d.get("kind")
    if kind not in _VALID_DECISION_KINDS:
        return f"unknown decision kind: {kind!r}"
    target = d.get("target")
    if not isinstance(target, int):
        # Strategist prompt v1 spec says target must be Goal id (int).
        return "decision.target must be an integer Goal id"
    return None


def apply_decisions(
    conn: sqlite3.Connection,
    problem: str,
    decisions: list[dict[str, Any]],
    *,
    allowed_providers: list[str] | None = None,
) -> DemuxResult:
    """Apply Strategist decisions, atomically writing queue inserts and
    Goal status updates inside a single transaction.

    Decisions failing validation are recorded under `rejected` rather than
    raising — Strategist commit step expects partial success (some
    decisions ride, others are skipped with a logged reason).
    """
    result = DemuxResult()
    now = _now()

    with conn:
        for dec in decisions:
            shape_err = _validate_decision_shape(dec)
            if shape_err:
                result.rejected.append({"decision": dec, "reason": shape_err})
                continue

            kind = dec["kind"]
            target = dec["target"]
            goal = _load_goal(conn, target)
            if goal is None:
                result.rejected.append({
                    "decision": dec,
                    "reason": f"Goal id {target} not found",
                })
                continue
            if goal["commit_state"] != "live":
                result.rejected.append({
                    "decision": dec,
                    "reason": f"Goal id {target} commit_state != live",
                })
                continue
            if goal["problem"] != problem:
                result.rejected.append({
                    "decision": dec,
                    "reason": (f"Goal id {target} is in problem "
                               f"{goal['problem']!r}, not {problem!r}"),
                })
                continue

            # Shelve: UPDATE goal + cancel still-running pipelines on it
            # (architecture v3 §6 cancellation row 6).
            if kind == _SHELVE_KIND:
                conn.execute(
                    "UPDATE goals SET status = 'shelved', "
                    "status_changed_at = ?, updated_at = ? "
                    "WHERE id = ?",
                    (now, now, target),
                )
                result.shelved.append(target)
                # Cancel cascade — separate atomic txn within the same `with`.
                from Tooling.cascade import cancel_running_for_goal
                cancel_running_for_goal(conn, target)
                continue

            # Inject path: blocked_pipelines filter.
            blocked = _decode_blocked(goal["blocked_pipelines"])
            if kind in blocked:
                result.rejected.append({
                    "decision": dec,
                    "reason": (f"pipeline kind {kind!r} is in "
                               f"blocked_pipelines for Goal {target}"),
                })
                continue

            # Provider override gate (decisions may set provider, but it
            # must be in the caller-supplied allowed_providers list).
            payload = _build_payload(dec)
            if "provider" in payload and allowed_providers is not None:
                if payload["provider"] not in allowed_providers:
                    result.rejected.append({
                        "decision": dec,
                        "reason": (f"provider {payload['provider']!r} not in "
                                   f"allowed list {allowed_providers!r}"),
                    })
                    continue

            payload_json = json.dumps(payload) if payload else None
            conn.execute(
                "INSERT INTO queue (kind, target_id, priority, payload, "
                "created_at) VALUES (?, ?, ?, ?, ?)",
                (kind, str(target), _INJECT_PRIORITY, payload_json, now),
            )
            result.enqueued.append({
                "kind": kind,
                "target_id": target,
                "payload": payload,
            })

    return result
