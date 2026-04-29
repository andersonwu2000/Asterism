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


def _decode_blocked(raw: str | None) -> tuple[list[str], str | None]:
    """Returns (blocked_list, error_msg).

    R3 fix (audit_c49_c50_c51.md M4): formerly silent — returned `[]` on
    JSON corruption which BYPASSED blocked_pipelines filtering. Now returns
    an error so the caller can reject the decision rather than silently
    inject a pipeline that should have been blocked.
    """
    if not raw:
        return [], None
    try:
        v = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [], f"blocked_pipelines JSON corrupt: {exc}"
    if not isinstance(v, list):
        return [], f"blocked_pipelines not a list: {type(v).__name__}"
    return [str(x) for x in v], None


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
    """Apply Strategist decisions to queue + goals.

    R3 fix (audit_c49_c50_c51.md HIGH-2): each decision now runs in its OWN
    `with conn:` transaction. The previous single-TX design meant a single
    INSERT failure (BUSY/LOCKED, FK, schema drift) would silently rollback
    the entire batch while DemuxResult.enqueued / shelved still reported
    them as landed — silent partial commit.

    Validation order (R3 audit_c49_c50_c51.md HIGH-3): shape → exists →
    same-Problem → commit_state. cross-Problem check moves BEFORE
    commit_state because a pending Goal in the wrong Problem should report
    "wrong Problem" (the agent's actionable bug) rather than "pending"
    (an internal state the agent has no view into).

    Decisions failing validation OR raising during INSERT/UPDATE are
    recorded under `rejected` rather than propagating exceptions.
    """
    result = DemuxResult()
    now = _now()

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
        # R3 HIGH-3: check Problem match BEFORE commit_state so error
        # message points to the agent's real mistake.
        if goal["problem"] != problem:
            result.rejected.append({
                "decision": dec,
                "reason": (f"Goal id {target} is in problem "
                           f"{goal['problem']!r}, not {problem!r}"),
            })
            continue
        if goal["commit_state"] != "live":
            result.rejected.append({
                "decision": dec,
                "reason": f"Goal id {target} commit_state != live",
            })
            continue

        # Shelve: UPDATE goal + cancel still-running pipelines.
        if kind == _SHELVE_KIND:
            try:
                with conn:
                    conn.execute(
                        "UPDATE goals SET status = 'shelved', "
                        "status_changed_at = ?, updated_at = ? "
                        "WHERE id = ?",
                        (now, now, target),
                    )
                    from Tooling.cascade import cancel_running_for_goal
                    cancel_running_for_goal(conn, target)
                result.shelved.append(target)
            except sqlite3.Error as exc:
                result.rejected.append({
                    "decision": dec,
                    "reason": f"Shelve UPDATE failed: {exc}",
                })
            continue

        # Inject path: blocked_pipelines filter (R3 M4: surface JSON corruption
        # as a per-decision rejection rather than silently bypassing the filter).
        blocked, blocked_err = _decode_blocked(goal["blocked_pipelines"])
        if blocked_err:
            result.rejected.append({
                "decision": dec,
                "reason": blocked_err,
            })
            continue
        if kind in blocked:
            result.rejected.append({
                "decision": dec,
                "reason": (f"pipeline kind {kind!r} is in "
                           f"blocked_pipelines for Goal {target}"),
            })
            continue

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
        try:
            with conn:
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
        except sqlite3.Error as exc:
            result.rejected.append({
                "decision": dec,
                "reason": f"queue INSERT failed: {exc}",
            })

    return result
