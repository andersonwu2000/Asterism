"""Unit tests for `Tooling.pipeline.events` projection layer.

Focus: behaviors not already covered by `test_agent.py` /
`test_context_files.py` end-to-end via `compile_context`:

  - `_NON_AGENT_REASONS` filter excludes infra noise + framework errors
    + cross-goal-projected reasons from `direct_attempts`.
  - `infeasible_subs` cross-goal projection (new in step 2; current
    `compile_context` doesn't render it yet, so end-to-end coverage is
    absent).
  - `dead_strategies` `exclude_strategy_ids` parameter (used by
    `compile_context` to dedupe against verify_failure when both render).
"""
from __future__ import annotations

import sqlite3

from Tooling import db
from Tooling.pipeline import events


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()),
    )


def _seed_goal(conn: sqlite3.Connection, *, problem: str = "p",
               slug: str = "g", origin: str = "root") -> int:
    return db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/{slug}.lean",
        statement="T", origin=origin,
    )


def _seed_strategy(conn: sqlite3.Connection, goal_id: int, *,
                   status: str = "proposed",
                   proposal_md: str = "decompose into A, B") -> int:
    sid = db.insert_strategy(
        conn, goal_id=goal_id,
        lean_path=f"Problems/p/strat-{goal_id}.lean",
        created_by="test", proposal_md=proposal_md, scratch_path="",
    )
    if status != "proposed":
        db.update_strategy_status(conn, sid, status)
    return sid


def _record_dead_attempt(conn: sqlite3.Connection, *, target_id: int,
                         target_kind: str = "Goal", reason: str,
                         pipeline_id: str = "pid-test",
                         proposal_md: str = "") -> None:
    """Insert a finished pipeline + dead_attempt row pair."""
    conn.execute(
        "INSERT OR IGNORE INTO pipelines (id, kind, target_id, "
        "target_kind, status, outcome, started_at, finished_at) "
        "VALUES (?, 'Builder', ?, ?, 'failed', 'failed', ?, ?)",
        (pipeline_id, str(target_id), target_kind, db.now(), db.now()),
    )
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id, "
        "failure_reason, failure_detail, proposal_md, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (target_id, target_kind, pipeline_id, reason,
         f"detail for {reason}", proposal_md, db.now()),
    )
    conn.commit()


# ---------------------------------------------------------------------
# direct_attempts — _NON_AGENT_REASONS filter
# ---------------------------------------------------------------------

def test_direct_attempts_excludes_spawn_fast_fail(
    conn: sqlite3.Connection,
) -> None:
    """spawn_fast_fail rows exist (legacy DB / tracking) but must not
    surface as direct_attempts (would pollute Context.md with infra
    noise the agent can't act on)."""
    _seed_problem(conn)
    gid = _seed_goal(conn)
    _record_dead_attempt(conn, target_id=gid, reason="spawn_fast_fail",
                         pipeline_id="pid-fast")
    _record_dead_attempt(conn, target_id=gid, reason="lake_build_error",
                         pipeline_id="pid-lake")
    out = events.direct_attempts(conn, gid)
    assert len(out) == 1
    assert out[0]["failure_reason"] == "lake_build_error"


def test_direct_attempts_excludes_agent_infeasible(
    conn: sqlite3.Connection,
) -> None:
    """`agent_infeasible` is cross-goal projected via infeasible_subs;
    the row exists in the failed sub's dead_attempts but should NOT
    appear in that sub's own direct_attempts (the sub is shelved
    anyway and won't be re-dispatched)."""
    _seed_problem(conn)
    gid = _seed_goal(conn)
    _record_dead_attempt(conn, target_id=gid, reason="agent_infeasible",
                         pipeline_id="pid-inf")
    assert events.direct_attempts(conn, gid) == []


def test_direct_attempts_excludes_framework_reasons(
    conn: sqlite3.Connection,
) -> None:
    """All 6 framework / DB / FS race reasons are filtered (operator
    forensics in dead_attempts, but not agent-actionable)."""
    _seed_problem(conn)
    gid = _seed_goal(conn)
    framework = [
        "goal_not_found", "lean_file_missing", "missing_parent_stub",
        "parent_stub_not_decomposable", "goal_no_longer_open",
        "unknown_kind",
    ]
    for i, reason in enumerate(framework):
        _record_dead_attempt(conn, target_id=gid, reason=reason,
                             pipeline_id=f"pid-{i}")
    # Plus one agent-actionable so the result isn't trivially empty
    _record_dead_attempt(conn, target_id=gid, reason="forbidden_lemma",
                         pipeline_id="pid-real")
    out = events.direct_attempts(conn, gid)
    assert len(out) == 1
    assert out[0]["failure_reason"] == "forbidden_lemma"


# ---------------------------------------------------------------------
# infeasible_subs — cross-goal projection
# ---------------------------------------------------------------------

def test_infeasible_subs_finds_subs_under_parent_strategies(
    conn: sqlite3.Connection,
) -> None:
    """Sub-goal under one of parent's strategies has agent_infeasible →
    surfaces in parent's infeasible_subs."""
    _seed_problem(conn)
    parent = _seed_goal(conn, slug="parent")
    sid = _seed_strategy(conn, parent)
    sub = _seed_goal(conn, slug="sub", origin="backward")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub, position=0)
    _record_dead_attempt(
        conn, target_id=sub, reason="agent_infeasible",
        pipeline_id="pid-sub-inf",
        proposal_md="## Counterexample\nset {} ...\n## Root cause\n"
                    "the type is unprovable: empty set has no element.",
    )
    out = events.infeasible_subs(conn, parent)
    assert len(out) == 1
    e = out[0]
    assert e.type == "infeasible_sub"
    assert e.target_goal_id == parent
    assert e["sub_slug"] == "sub"
    assert "empty set has no element" in e["root_cause"]


def test_infeasible_subs_skips_unrelated_goal(
    conn: sqlite3.Connection,
) -> None:
    """An infeasible sub under SOMEONE ELSE's strategy must not leak
    into this parent's projection."""
    _seed_problem(conn)
    parent_a = _seed_goal(conn, slug="parent_a")
    parent_b = _seed_goal(conn, slug="parent_b")
    sid_b = _seed_strategy(conn, parent_b)
    sub_under_b = _seed_goal(conn, slug="sub_under_b", origin="backward")
    db.link_subgoal(conn, strategy_id=sid_b, subgoal_id=sub_under_b,
                    position=0)
    _record_dead_attempt(
        conn, target_id=sub_under_b, reason="agent_infeasible",
        pipeline_id="pid-x",
    )
    assert events.infeasible_subs(conn, parent_a) == []
    assert len(events.infeasible_subs(conn, parent_b)) == 1


# ---------------------------------------------------------------------
# dead_strategies — exclude_strategy_ids parameter
# ---------------------------------------------------------------------

def test_dead_strategies_excludes_listed_ids(
    conn: sqlite3.Connection,
) -> None:
    """Caller passes verify-failed strategy ids → those are excluded
    so the same strategy doesn't render in both verify_failure and
    dead_strategy buckets."""
    _seed_problem(conn)
    gid = _seed_goal(conn)
    sid_dead_a = _seed_strategy(conn, gid, status="dead",
                                proposal_md="proposal A")
    sid_dead_b = _seed_strategy(conn, gid, status="dead",
                                proposal_md="proposal B")
    # Need at least one linked sub-goal for each (filter requirement)
    sub_a = _seed_goal(conn, slug="sub_a", origin="backward")
    sub_b = _seed_goal(conn, slug="sub_b", origin="backward")
    db.link_subgoal(conn, strategy_id=sid_dead_a, subgoal_id=sub_a, position=0)
    db.link_subgoal(conn, strategy_id=sid_dead_b, subgoal_id=sub_b, position=0)

    # Without exclusion: both surface
    assert len(events.dead_strategies(conn, gid)) == 2
    # With sid_dead_a excluded: only B
    out = events.dead_strategies(conn, gid,
                                 exclude_strategy_ids={sid_dead_a})
    assert len(out) == 1
    assert out[0]["id"] == sid_dead_b


def test_dead_strategies_skips_empty_proposal_or_no_subs(
    conn: sqlite3.Connection,
) -> None:
    """Half-baked recovery cleanups (status='dead' + empty proposal_md)
    or strategies without linked sub-goals must NOT appear — they
    carry no actionable signal."""
    _seed_problem(conn)
    gid = _seed_goal(conn)
    # Empty proposal
    _seed_strategy(conn, gid, status="dead", proposal_md="")
    # Non-empty proposal but no sub-goals linked
    _seed_strategy(conn, gid, status="dead", proposal_md="orphan")
    # Valid: proposal + sub
    sid_ok = _seed_strategy(conn, gid, status="dead", proposal_md="ok")
    sub = _seed_goal(conn, slug="sub", origin="backward")
    db.link_subgoal(conn, strategy_id=sid_ok, subgoal_id=sub, position=0)

    out = events.dead_strategies(conn, gid)
    assert len(out) == 1
    assert out[0]["id"] == sid_ok


# ---------------------------------------------------------------------
# Event __getitem__ / .get
# ---------------------------------------------------------------------

def test_event_dict_like_access(conn: sqlite3.Connection) -> None:
    """Event supports legacy `event["key"]` / `event.get("key")` access
    so renderers written for `sqlite3.Row` work unchanged."""
    _seed_problem(conn)
    gid = _seed_goal(conn)
    _record_dead_attempt(conn, target_id=gid, reason="lake_build_error")
    e = events.direct_attempts(conn, gid)[0]
    assert e["failure_reason"] == "lake_build_error"
    assert e.get("failure_reason") == "lake_build_error"
    assert e.get("nonexistent_key") is None
    assert e.get("nonexistent_key", "fallback") == "fallback"
