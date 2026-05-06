"""Event projections for Context.md goal-history rendering.

Per `docs/dev/goal_history_unified.md` step 2 — projection layer that
turns DB rows into typed `Event` objects, ready to be filtered /
rendered by Context.md sections without each section having to write
its own SQL.

Five projections currently live here:

  - `direct_attempts(goal_id)`  — failure on this goal itself,
                                  filtered to agent-actionable reasons
                                  (see `_NON_AGENT_REASONS` for what's
                                  excluded).
  - `verify_failures(goal_id)`  — strategy-level dead_attempts on this
                                  goal's strategies (legacy F56; not
                                  produced by new pipelines but
                                  retained for historical DB rows).
  - `dead_strategies(goal_id)`  — strategies for this goal that died
                                  (cascade-shelve / F16 inward kill).
                                  Built-in dedupe against `verify_failures`
                                  so the same strategy id doesn't
                                  appear in both buckets.
  - `builder_declines(goal_id)` — F48 subset of `direct_attempts` where
                                  the Builder agent invoked the
                                  decline channel (PROPOSAL.md without
                                  patch.lean + `decline_reason: too_hard`).
  - `infeasible_subs(parent_goal_id)` — cross-goal projection: a
                                  sub-goal under one of `parent_goal_id`'s
                                  strategies reported `agent_infeasible`.
                                  The DB row lives in the failed sub's
                                  dead_attempts, but the actionable
                                  signal is in the parent's next
                                  Backward retry (avoid re-proposing
                                  the same type-infeasible decomposition).

The single source of truth for which `failure_reason` values are
agent-actionable is `_NON_AGENT_REASONS` — see `docs/failure_modes.md`
§3 for the rationale on each excluded reason.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------
# Reason filter set
# ---------------------------------------------------------------------

# Reasons NOT projected as `direct_attempt`. Three sub-categories:
#   1. infra noise (agent has no way to act on it):
#        - spawn_fast_fail (rc≠0 wall<10s; F46)
#   2. cross-goal projected (handled by a different event_type):
#        - agent_infeasible → projected to parent via `infeasible_subs`
#   3. framework / DB / FS race (operator concern, not agent's):
#        - goal_not_found, lean_file_missing, missing_parent_stub,
#          parent_stub_not_decomposable, goal_no_longer_open, unknown_kind
# Rows for these reasons still exist in dead_attempts (forensic + cooldown
# / race-tracking signals), they just don't surface in the agent's
# Context.md.
_NON_AGENT_REASONS: frozenset[str] = frozenset({
    "spawn_fast_fail",
    "agent_infeasible",
    "goal_not_found",
    "lean_file_missing",
    "missing_parent_stub",
    "parent_stub_not_decomposable",
    "goal_no_longer_open",
    "unknown_kind",
})


# ---------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------

@dataclass
class Event:
    """A single projected goal-history event ready for rendering.

    Thin wrapper: `payload` carries the underlying DB row(s) verbatim
    (as a dict, so both new code and legacy renderers using
    `event["key"]` access work), while `type` / `target_goal_id` /
    `ts` are explicit fields for filter / sort / dispatch decisions
    without dict lookups.

    `__getitem__` / `get` delegate to `payload`, keeping callers that
    were written against `sqlite3.Row` working unchanged.
    """
    type: str           # 'direct_attempt' | 'verify_failure' | 'dead_strategy' | 'infeasible_sub'
    target_goal_id: int  # goal whose Context.md should see this event
    payload: dict[str, Any] = field(default_factory=dict)
    ts: str = ""

    def __getitem__(self, key: str) -> Any:
        return self.payload[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """sqlite3.Row → plain dict (for Event.payload).

    sqlite3.Row supports both index and key access but `dict(row)`
    needs `row.keys()` + iteration to materialize. We always copy
    so payload is independent of the connection lifecycle.
    """
    return {k: row[k] for k in row.keys()}


# ---------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------

def direct_attempts(conn: sqlite3.Connection,
                    goal_id: int, *, k: int = 5) -> list[Event]:
    """Latest k dead_attempts targeted at this goal that the agent can
    act on (excludes infra noise, framework errors, and cross-goal
    `agent_infeasible` projections — see `_NON_AGENT_REASONS`)."""
    placeholders = ",".join(["?"] * len(_NON_AGENT_REASONS))
    rows = conn.execute(
        f"SELECT id, target_id, target_kind, pipeline_id, failure_reason, "
        f"       failure_detail, proposal_md, ts "
        f"FROM dead_attempts "
        f"WHERE target_kind = 'Goal' AND target_id = ? "
        f"  AND failure_reason NOT IN ({placeholders}) "
        f"ORDER BY id DESC LIMIT ?",
        (goal_id, *_NON_AGENT_REASONS, k),
    ).fetchall()
    return [
        Event(type="direct_attempt",
              target_goal_id=goal_id,
              payload=_row_to_dict(r),
              ts=r["ts"] or "")
        for r in rows
    ]


def verify_failures(conn: sqlite3.Connection,
                    goal_id: int, *, k: int = 5) -> list[Event]:
    """Strategy-level dead_attempts on this goal's strategies. F56
    removed Verify as a worker_kind so new pipelines don't write these
    rows; this projection still surfaces historical rows from pre-F56
    runs of the same DB."""
    rows = conn.execute(
        "SELECT da.id, da.target_id, da.failure_reason, da.failure_detail, "
        "       da.pipeline_id, da.ts, "
        "       s.proposal_md AS strategy_proposal "
        "FROM dead_attempts da "
        "JOIN strategies s ON s.id = da.target_id "
        "WHERE da.target_kind = 'Strategy' AND s.goal_id = ? "
        "ORDER BY da.id DESC LIMIT ?",
        (goal_id, k),
    ).fetchall()
    return [
        Event(type="verify_failure",
              target_goal_id=goal_id,
              payload=_row_to_dict(r),
              ts=r["ts"] or "")
        for r in rows
    ]


def dead_strategies(conn: sqlite3.Connection,
                    goal_id: int, *, k: int = 5,
                    exclude_strategy_ids: set[int] | None = None,
                    ) -> list[Event]:
    """Strategies that were proposed for this goal and later died
    (cascade-shelve / F16 inward kill / verify-housekeeping mark dead).
    Filtered to non-empty proposal_md AND ≥ 1 linked sub-goal (drops
    half-baked recovery cleanups).

    `exclude_strategy_ids` lets the caller dedupe against the
    `verify_failure` projection — same strategy id may appear in both
    buckets, and verify_failure carries more informative content
    (lake stderr). The caller knows whether verify_failure is being
    rendered for this audience (P0-#4: Builder kind suppresses
    verify_failure but should still see dead_strategy intact).

    Each event's `payload['subs']` is the list of sub-goals the strategy
    spawned, with shelved subs annotated by `root_cause` excerpt + full
    counterexample text from the latest `agent_infeasible` decline."""
    exclude = set(exclude_strategy_ids) if exclude_strategy_ids else set()

    rows = conn.execute(
        "SELECT s.id, s.proposal_md FROM strategies s "
        "WHERE s.goal_id = ? AND s.status = 'dead' "
        "  AND s.proposal_md != '' "
        "  AND EXISTS (SELECT 1 FROM strategy_subgoals ss "
        "              WHERE ss.strategy_id = s.id) "
        "ORDER BY s.id DESC LIMIT ?",
        (goal_id, k),
    ).fetchall()

    out: list[Event] = []
    for r in rows:
        sid = int(r["id"])
        if sid in exclude:
            continue
        subs = conn.execute(
            "SELECT g.id, g.slug, g.statement, g.status "
            "FROM strategy_subgoals ss "
            "JOIN goals g ON g.id = ss.subgoal_id "
            "WHERE ss.strategy_id = ? ORDER BY ss.position ASC",
            (sid,),
        ).fetchall()
        sub_list: list[dict] = []
        for sub in subs:
            root_cause = ""
            counterexample_full = ""
            if sub["status"] == "shelved":
                d = conn.execute(
                    "SELECT proposal_md FROM dead_attempts "
                    "WHERE target_id = ? AND target_kind = 'Goal' "
                    "  AND failure_reason = 'agent_infeasible' "
                    "  AND COALESCE(proposal_md, '') != '' "
                    "ORDER BY id DESC LIMIT 1",
                    (int(sub["id"]),),
                ).fetchone()
                if d and d["proposal_md"]:
                    counterexample_full = d["proposal_md"]
                    root_cause = _extract_root_cause(d["proposal_md"])
            sub_list.append({
                "slug": sub["slug"],
                "statement": sub["statement"],
                "status": sub["status"],
                "root_cause": root_cause,
                "counterexample_full": counterexample_full,
            })
        out.append(Event(
            type="dead_strategy",
            target_goal_id=goal_id,
            payload={"id": sid, "proposal_md": r["proposal_md"],
                     "subs": sub_list},
        ))
    return out


def builder_declines(conn: sqlite3.Connection,
                     goal_id: int, *, k: int = 3) -> list[Event]:
    """F48 — direct_attempts subset where the Builder agent invoked the
    decline hatch (`failure_reason='agent_declined'`, PROPOSAL.md text
    explaining what's hard). Surfaced as its own section in the current
    Context.md layout (`## Why Builder declined this goal`); step 4
    of the goal_history refactor merges this back into
    `direct_attempts` with a subtype prefix."""
    rows = conn.execute(
        "SELECT id, pipeline_id, proposal_md, ts "
        "FROM dead_attempts "
        "WHERE target_id = ? AND target_kind = 'Goal' "
        "  AND failure_reason = 'agent_declined' "
        "  AND COALESCE(proposal_md, '') != '' "
        "ORDER BY id DESC LIMIT ?",
        (goal_id, k),
    ).fetchall()
    return [
        Event(type="direct_attempt",  # subtype carries the decline distinction
              target_goal_id=goal_id,
              payload=_row_to_dict(r),
              ts=r["ts"] or "")
        for r in rows
    ]


def infeasible_subs(conn: sqlite3.Connection,
                    parent_goal_id: int, *, k: int = 5) -> list[Event]:
    """Cross-goal projection: sub-goals of `parent_goal_id`'s strategies
    that reported `agent_infeasible`. The DB row lives in the failed
    sub's dead_attempts (target_kind='Goal'), but it surfaces here on
    the parent's Context.md so the parent's next Backward avoids
    re-proposing a decomposition built around the same type-infeasible
    sub-goal.

    SQL JOIN walks: dead_attempts → goals (the failed sub) →
    strategy_subgoals → strategies → filter `s.goal_id = parent_goal_id`.

    Same sub may link to multiple strategies via dedupe alias; the
    JOIN expands one row per (sub, parent strategy), but since we
    filter on a single `parent_goal_id` we get at most one row per
    failed-sub-on-this-parent — the natural unit.

    NOT YET WIRED into `compile_context` — the `## Goal history`
    umbrella section in step 3 of the refactor introduces a new
    sub-section to render these. Until then, declared but unused.
    """
    rows = conn.execute(
        "SELECT da.id, da.target_id AS sub_goal_id, da.pipeline_id, "
        "       da.failure_reason, da.failure_detail, da.proposal_md, "
        "       da.ts, sub.slug AS sub_slug, sub.statement AS sub_statement "
        "FROM dead_attempts da "
        "JOIN goals sub ON sub.id = da.target_id "
        "JOIN strategy_subgoals ss ON ss.subgoal_id = sub.id "
        "JOIN strategies s ON s.id = ss.strategy_id "
        "WHERE da.failure_reason = 'agent_infeasible' "
        "  AND da.target_kind = 'Goal' "
        "  AND s.goal_id = ? "
        "ORDER BY da.id DESC LIMIT ?",
        (parent_goal_id, k),
    ).fetchall()
    out: list[Event] = []
    for r in rows:
        payload = _row_to_dict(r)
        # Pre-compute root-cause excerpt so the renderer doesn't have
        # to import _extract_root_cause.
        payload["root_cause"] = _extract_root_cause(r["proposal_md"] or "")
        out.append(Event(
            type="infeasible_sub",
            target_goal_id=parent_goal_id,
            payload=payload,
            ts=r["ts"] or "",
        ))
    return out


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _extract_root_cause(proposal_md: str, *, max_chars: int = 400) -> str:
    """Pull the agent-written root-cause one-paragraph excerpt out of
    an `agent_infeasible` decline's PROPOSAL.md. Prefers a `## Root cause`
    section; falls back to the last non-heading paragraph (agents often
    put the conclusion at the end of `## Counterexample`).

    Moved here from `Tooling.context` so events.py is self-contained
    (avoid import cycle: context imports events, events would import
    context for this helper)."""
    if not proposal_md:
        return ""
    text = proposal_md
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            text = text[end + 3:].lstrip()
    m = re.search(r"^##\s*Root cause\s*$", text,
                  re.MULTILINE | re.IGNORECASE)
    if m:
        rest = text[m.end():]
        nxt = re.search(r"^##\s", rest, re.MULTILINE)
        excerpt = (rest[:nxt.start()] if nxt else rest).strip()
    else:
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        paras = [p for p in paras if not p.lstrip().startswith("#")]
        excerpt = paras[-1] if paras else ""
    excerpt = " ".join(excerpt.split())
    if len(excerpt) > max_chars:
        excerpt = excerpt[:max_chars].rsplit(" ", 1)[0] + " ..."
    return excerpt
