"""Phase 2 — Strategist pipeline framework-side logic (Step 6 scaffold).

Tests parse_decision / verify_decision / commit_decision. Agent stage
(actual LLM spawn) is not yet implemented; those tests will be added
when run_strategist is fleshed out.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.pipeline import strategist
from Tooling.state import db


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n## Statement\nT\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


def _insert_root(conn: sqlite3.Connection) -> int:
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/Root.lean", statement="T",
        origin="root", depth=0, entry_kind="Backward",
    )


# ---------------------------------------------------------------------
# parse_decision
# ---------------------------------------------------------------------

def test_parse_inject_decision() -> None:
    text = json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "brief": "## Need\nFoo",
    })
    d, err = strategist.parse_decision(text)
    assert err == ""
    assert d is not None
    assert d.kind == "Inject"
    assert d.payload.get("pipeline") == "Forward"
    assert d.brief == "## Need\nFoo"


def test_parse_confirmshelve_decision() -> None:
    text = json.dumps({
        "kind": "ConfirmShelve", "target_goal_id": 42,
        "reason": "dead end",
    })
    d, err = strategist.parse_decision(text)
    assert err == ""
    assert d.kind == "ConfirmShelve"
    assert d.target_id == 42
    assert d.reason == "dead end"


def test_parse_reopen_with_directive() -> None:
    text = json.dumps({
        "kind": "Reopen", "target_goal_id": 7,
        "reason": "retry with hint",
        "directive": "Prefer L_x",
    })
    d, err = strategist.parse_decision(text)
    assert err == ""
    assert d.kind == "Reopen"
    assert d.payload.get("directive") == "Prefer L_x"


def test_parse_emitdirective() -> None:
    text = json.dumps({
        "kind": "EmitDirective",
        "scope": "problem:p", "body": "use L_x",
        "reason": "tools shifted",
    })
    d, err = strategist.parse_decision(text)
    assert err == ""
    assert d.payload["scope"] == "problem:p"
    assert d.payload["body"] == "use L_x"


def test_parse_request_user_amend() -> None:
    text = json.dumps({
        "kind": "RequestUserAmend", "problem": "p",
        "file": "Defs.lean",
        "proposed_body": "import Mathlib\nopen Real\n",
        "question": "OK?", "reason": "missing open",
    })
    d, err = strategist.parse_decision(text)
    assert err == ""
    assert d.payload["file"] == "Defs.lean"


def test_parse_noop() -> None:
    text = json.dumps({"kind": "Noop", "reason": "wait for BFS"})
    d, err = strategist.parse_decision(text)
    assert err == ""
    assert d.kind == "Noop"


def test_parse_rejects_unknown_kind() -> None:
    text = json.dumps({"kind": "Telekinesis", "reason": "?"})
    d, err = strategist.parse_decision(text)
    assert d is None
    assert "unknown" in err.lower()


def test_parse_rejects_non_json() -> None:
    d, err = strategist.parse_decision("not json")
    assert d is None


# ---------------------------------------------------------------------
# verify_decision
# ---------------------------------------------------------------------

def test_verify_inject_rejects_unknown_pipeline(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6 widens Inject.pipeline to Forward/Backward/Builder. An
    unknown value (legacy 'Reflection' etc.) is rejected."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Reflection", "briefs": ["x"],
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "Forward" in err or "Reflection" in err


def test_verify_inject_requires_brief_field(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: Inject requires top-level `brief: str`. Missing brief
    is rejected."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "brief" in err.lower()


def test_verify_inject_rejects_empty_brief(
    conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward", "brief": "  ",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "non-empty" in err.lower() or "brief" in err.lower()


def test_verify_inject_rejects_legacy_briefs_list(
    conn: sqlite3.Connection,
) -> None:
    """`briefs: list` was the Phase 2.5 schema; Phase 6 uses single
    `brief`. Reject with a hint pointing at the new schema."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "briefs": ["legacy multi-brief"],
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "brief" in err.lower()


def test_verify_inject_ok_single_brief(
    conn: sqlite3.Connection,
) -> None:
    """Forward Inject: one brief per decision (multi-Inject lands as
    multiple decisions in the future multi-decision schema)."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "brief": "## Need\nfoo",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""


def test_verify_confirmshelve_target_must_exist(
    conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "ConfirmShelve", "target_goal_id": 999,
        "reason": "x",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "not found" in err.lower()


def test_parse_target_id_accepts_slug_string(
    conn: sqlite3.Connection,
) -> None:
    """parse_decision keeps a string target_id; verify_decision looks it
    up by (problem, slug) and rewrites to int. Tolerates the agent
    emitting `target_goal_id="main"` (slug) instead of the integer id."""
    root = _insert_root(conn)
    d, err = strategist.parse_decision(json.dumps({
        "kind": "Reopen", "target_goal_id": "main", "reason": "ready",
    }))
    assert err == ""
    assert d.target_id == "main"  # not yet normalized
    assert strategist.verify_decision(d, conn, problem="p") == ""
    assert d.target_id == root  # verify_decision rewrote it


def test_verify_unknown_slug_rejected(
    conn: sqlite3.Connection,
) -> None:
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Reopen", "target_goal_id": "nonexistent",
        "reason": "x",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "slug" in err.lower() and "not found" in err.lower()


def test_parse_target_id_int_string_coerces(
    conn: sqlite3.Connection,
) -> None:
    """`"2019"` (digit string) coerces to int 2019 at parse-time so it
    doesn't hit the slug-lookup path unnecessarily."""
    d, err = strategist.parse_decision(json.dumps({
        "kind": "Reopen", "target_goal_id": "2019", "reason": "x",
    }))
    assert err == ""
    assert d.target_id == 2019  # coerced to int


def test_parse_target_id_rejects_non_str_non_int(
    conn: sqlite3.Connection,
) -> None:
    d, err = strategist.parse_decision(json.dumps({
        "kind": "Reopen", "target_goal_id": [1, 2], "reason": "x",
    }))
    assert d is None
    assert "int, slug" in err.lower() or "list" in err.lower()


def test_verify_reopen_rejected_when_ancestor_disproved(
    conn: sqlite3.Connection,
) -> None:
    root = _insert_root(conn)
    # Make root disproved, sub under it
    db.update_goal_status(conn, root, "disproved")
    sub = db.insert_goal(
        conn, problem="p", slug="sub",
        lean_path="Problems/p/proofs/L_sub.lean", statement="T",
        origin="backward",
    )
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'proposed', '', 'test', ?)",
        (root, db.now()))
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (cur.lastrowid, sub))
    conn.commit()

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Reopen", "target_goal_id": sub,
        "reason": "retry",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "disproved" in err.lower()


def test_verify_reopen_rejected_when_ancestor_dead(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: `dead` ancestor also blocks Reopen on descendants
    (parent strategy was wrong, descendant exists only in that
    abandoned context). Same treatment as disproved; only `shelved`
    is reopenable via auto-detach."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "dead")
    sub = db.insert_goal(
        conn, problem="p", slug="sub_under_dead",
        lean_path="Problems/p/proofs/L_sub_dead.lean", statement="T",
        origin="backward",
    )
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'proposed', '', 'test', ?)",
        (root, db.now()))
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (cur.lastrowid, sub))
    conn.commit()

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Reopen", "target_goal_id": sub, "reason": "salvage",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "dead" in err.lower()
    # Hint suggests the right alternative
    assert "Inject(Backward" in err or "different decomposition" in err.lower()


def test_verify_reopen_ok_with_shelved_ancestor(
    conn: sqlite3.Connection,
) -> None:
    """Phase 2 — `shelved` ancestor doesn't block Reopen (framework
    auto-detaches the descendant)."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "shelved")
    sub = db.insert_goal(
        conn, problem="p", slug="sub",
        lean_path="Problems/p/proofs/L_sub.lean", statement="T",
        origin="backward",
    )
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'proposed', '', 'test', ?)",
        (root, db.now()))
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (cur.lastrowid, sub))
    conn.commit()

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Reopen", "target_goal_id": sub, "reason": "x",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""


def test_verify_request_user_amend_file_check(
    conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "RequestUserAmend", "problem": "p",
        "file": "Root.lean", "proposed_body": "x", "question": "?",
        "reason": "x",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "Defs.lean" in err and "Manifest.md" in err


def test_verify_request_user_amend_blocks_second_awaiting(
    conn: sqlite3.Connection,
) -> None:
    """Only one outstanding awaiting_human row per problem."""
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome,"
        " created_at, updated_at)"
        " VALUES ('p', 1, 'routine', 'RequestUserAmend',"
        " '{}', 'awaiting_human', ?, ?)", (db.now(), db.now()),
    )
    conn.commit()

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "RequestUserAmend", "problem": "p",
        "file": "Defs.lean", "proposed_body": "x", "question": "?",
        "reason": "x",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "awaiting_human" in err.lower()


# ---------------------------------------------------------------------
# Phase 6 — Inject(Backward / Builder) redispatch
# ---------------------------------------------------------------------

def test_verify_inject_backward_requires_target_goal_id(
    conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "brief": "try angle X", "reason": "retry",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "target_goal_id" in err


def test_verify_inject_backward_rejects_terminal_target(
    conn: sqlite3.Connection,
) -> None:
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "proved")
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "brief": "try again",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "terminal" in err.lower() or "proved" in err.lower()


def test_verify_inject_backward_rejects_dead_target(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: `dead` is a hard terminal (parent_needs_fix), not
    reopenable. Inject(Backward) on a dead goal must be rejected at
    verify time."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "dead")
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "brief": "try again",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "dead" in err.lower() or "terminal" in err.lower()


def test_verify_inject_forward_rejects_target_goal_id(
    conn: sqlite3.Connection,
) -> None:
    """Forward Inject targets the problem and produces a new goal;
    setting target_goal_id is a category error (agent confused Forward
    with Backward/Builder). Reject with a hint."""
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "target_goal_id": root, "brief": "## Need\nfoo",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "target_goal_id" in err.lower() or "forward" in err.lower()


def test_verify_inject_rejects_legacy_briefs_or_directive_on_backward(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: legacy `briefs: list` / `directive` fields rejected for
    all pipelines. Single `brief` is the unified field."""
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "brief": "try X", "briefs": ["x"],
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "brief" in err.lower()


def test_verify_inject_backward_accepts_slug_target(
    conn: sqlite3.Connection,
) -> None:
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": "main", "brief": "switch angle",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert err == ""
    # Slug normalized to int (lifted to Decision.target_id by parse)
    assert d.target_id == root


def test_commit_inject_backward_enqueues_with_directive(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Inject(Backward, target, directive) writes a single batch row
    with directive in the brief column, enqueues Backward on the goal,
    and force-reopens if currently shelved."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "shelved")
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "brief": "try the contour deformation angle",
        "reason": "previous decomp went through wrong primitive existence",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="pending_review",
        workspace=workspace,
    )
    # Single-row batch
    assert outcome.batch_id is not None
    assert len(outcome.batch_decision_row_ids) == 1
    # Decision row carries directive in brief + produced_goal_id linked
    row = conn.execute(
        "SELECT brief, produced_goal_id FROM strategist_decisions WHERE id=?",
        (outcome.decision_row_id,),
    ).fetchone()
    assert "contour deformation" in row["brief"]
    assert row["produced_goal_id"] == root
    # Target force-reopened
    assert db.get_goal(conn, root)["status"] == "open"
    # Backward enqueued on the goal
    q = conn.execute(
        "SELECT kind, target_id, decision_id FROM queue WHERE kind='Backward'"
    ).fetchone()
    assert q is not None
    assert int(q["target_id"]) == root
    assert q["decision_id"] == outcome.decision_row_id


def test_commit_inject_builder_works_similarly(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Inject(Builder) mirrors Backward — same redispatch semantic,
    different pipeline target."""
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Builder",
        "target_goal_id": root, "brief": "try linarith + Mathlib.Algebra.foo",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="pending_review",
        workspace=workspace,
    )
    q = conn.execute(
        "SELECT kind FROM queue WHERE decision_id=?",
        (outcome.decision_row_id,),
    ).fetchone()
    assert q["kind"] == "Builder"


# ---------------------------------------------------------------------
# commit_decision — side effects
# ---------------------------------------------------------------------

def test_commit_noop_inserts_audit_row(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Noop", "reason": "waiting",
    }))
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    rows = conn.execute(
        "SELECT decision_kind, reason FROM strategist_decisions"
        " WHERE problem='p'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["decision_kind"] == "Noop"
    # bootstrap_done set
    p = conn.execute(
        "SELECT bootstrap_done, last_strategist_at FROM problems"
        " WHERE name='p'"
    ).fetchone()
    assert p["bootstrap_done"] == 1
    assert p["last_strategist_at"] is not None


def test_commit_emitdirective_writes_problem_directive(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "EmitDirective", "scope": "problem:p",
        "body": "Prefer L_x", "reason": "shift",
    }))
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    p = conn.execute(
        "SELECT strategist_directive FROM problems WHERE name='p'"
    ).fetchone()
    assert p["strategist_directive"] == "Prefer L_x"


def test_commit_inject_forward_enqueues_with_decision_id(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Phase 6: one Inject(Forward) = one decision = one row + one
    Forward enqueue. batch_id is set on the audit row so future
    multi-decision support can group them under one Strategist call."""
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "brief": "## Need\nfoo",
    }))
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    assert outcome.enqueued_forward is True
    assert outcome.batch_id is not None
    assert len(outcome.batch_decision_row_ids) == 1
    q = conn.execute(
        "SELECT kind, target_id, target_kind, decision_id FROM queue"
        " WHERE kind='Forward'"
    ).fetchone()
    assert q is not None
    assert q["target_id"] == "p"
    assert q["target_kind"] == "Problem"
    assert q["decision_id"] == outcome.decision_row_id
    row = conn.execute(
        "SELECT batch_id, brief FROM strategist_decisions WHERE id = ?",
        (outcome.decision_row_id,),
    ).fetchone()
    assert row["batch_id"] == outcome.batch_id
    assert row["brief"] == "## Need\nfoo"


def test_commit_confirmshelve_cascades_shelved_to_descendants(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """ConfirmShelve flips the target goal to 'shelved' and cascades
    'shelved' down the strategy_subgoals chain so DB status is the
    single source of truth for "is this dispatchable". No
    cascade_shelved or dormant intermediate — `shelved` regardless of
    how the goal got there (own decline, parent_needs_fix, descendant
    cascade), and uniformly Reopenable."""
    root = _insert_root(conn)
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'proposed', '', 'test', ?)",
        (root, db.now()))
    sid = int(cur.lastrowid)
    sub = db.insert_goal(
        conn, problem="p", slug="sub",
        lean_path="Problems/p/proofs/L_sub.lean", statement="T",
        origin="backward",
    )
    db.update_goal_status(conn, sub, "open")
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, sub))
    conn.commit()

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "ConfirmShelve", "target_goal_id": root,
        "reason": "dead",
    }))
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="pending_review",
        workspace=workspace,
    )
    assert db.get_goal(conn, root)["status"] == "shelved"
    assert db.get_goal(conn, sub)["status"] == "shelved"


def test_commit_reopen_with_broken_chain_sets_detached(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    root = _insert_root(conn)
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'dead', '', 'test', ?)",
        (root, db.now()))
    sid = int(cur.lastrowid)
    sub = db.insert_goal(
        conn, problem="p", slug="sub",
        lean_path="Problems/p/proofs/L_sub.lean", statement="T",
        origin="backward",
    )
    db.update_goal_status(conn, sub, "shelved")
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, sub))
    conn.commit()

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Reopen", "target_goal_id": sub,
        "reason": "try again",
    }))
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    g = db.get_goal(conn, sub)
    # Reopen sets 'open' (not 'attempting') so bfs_refill — which filters
    # `status='open'` — can dispatch the goal on the next tick.
    assert g["status"] == "open"
    assert g["detached"] == 1
    # Regression guard: open_goals (the BFS dispatch source) returns it
    # via the detached=1 seed even though no live ancestor strategy exists.
    open_ids = {int(r["id"]) for r in db.open_goals(conn)}
    assert sub in open_ids


def test_commit_reopen_makes_goal_dispatchable_via_bfs(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Regression — take-5 failure: Reopen used to set status='attempting'
    and skip enqueue, so `db.open_goals` (filters status='open') hid the
    goal and bfs_refill never dispatched it → daemon idle-exited with
    root in attempting limbo. After fix: status='open' makes the root
    immediately visible to BFS without auto-detach (root is its own seed).
    """
    root = _insert_root(conn)
    # Simulate the pre-Reopen state: root was marked
    # pending_strategist_review (or attempting) and not dispatchable.
    db.update_goal_status(conn, root, "pending_strategist_review")
    assert root not in {int(r["id"]) for r in db.open_goals(conn)}

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Reopen", "target_goal_id": root,
        "reason": "retry",
    }))
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )

    g = db.get_goal(conn, root)
    assert g["status"] == "open"
    # detached=0 because root is its own dispatch seed; no broken chain.
    assert g["detached"] == 0
    open_ids = {int(r["id"]) for r in db.open_goals(conn)}
    assert root in open_ids


def test_commit_request_user_amend_writes_proposed_file_atomically(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "RequestUserAmend", "problem": "p",
        "file": "Manifest.md",
        "proposed_body": "## New Manifest body",
        "question": "Accept?", "reason": "x",
    }))
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    proposed = workspace / "Problems" / "p" / ".proposed_Manifest.md"
    assert proposed.exists()
    assert "New Manifest body" in proposed.read_text(encoding="utf-8")
    # Outcome marks awaiting_human
    row = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (outcome.decision_row_id,),
    ).fetchone()
    assert row["outcome"] == "awaiting_human"


# ---------------------------------------------------------------------
# Phase 2.5 (unified) — Inject(briefs=[...]) batch path
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# residue_thm 2026-05-19 — Inject decision outcome semantics
# ---------------------------------------------------------------------
# Pre-fix: cascade_one filled decision.outcome as soon as the Forward
# agent finished writing (sorry-bearing or not). inject_batch_done
# could fire while produced lemmas were still `:= by sorry`, leading
# Strategist to Reopen parent goals whose new deps were unproven and
# Backward to leaf-bypass-cite them → axiom_probe rollback.
#
# Post-fix: when Forward commits a sorry-bearing lemma, it links the
# decision via `set_inject_decision_produced_goal`. cascade_one then
# defers filling `outcome` until the produced goal reaches a terminal
# status (proved / shelved / disproved), via
# `propagate_inject_outcome_from_goal`.

def test_propagate_inject_outcome_proved(
    conn: sqlite3.Connection,
) -> None:
    """Goal flips to 'proved' → decision.outcome becomes 'success'."""
    root = _insert_root(conn)
    forward_goal = db.insert_goal(
        conn, problem="p", slug="fwd_lemma",
        lean_path="Problems/p/proofs/L_fwd_lemma.lean",
        statement="T", origin="forward",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-1", step_index=0,
        batch_size=1, brief="## Need\nX",
    )
    db.set_inject_decision_produced_goal(conn, decision_id, forward_goal)

    assert _decision_outcome(conn, decision_id) is None

    db.update_goal_status(conn, forward_goal, "proved")
    affected = db.propagate_inject_outcome_from_goal(conn, forward_goal)
    assert affected == decision_id
    assert _decision_outcome(conn, decision_id) == "success"


def test_propagate_inject_outcome_shelved(
    conn: sqlite3.Connection,
) -> None:
    """Goal flips to 'shelved' → decision.outcome becomes
    'failed:shelved' (lemma dead, Strategist must know)."""
    _insert_root(conn)
    fwd = db.insert_goal(
        conn, problem="p", slug="fwd",
        lean_path="Problems/p/proofs/L_fwd.lean",
        statement="T", origin="forward",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-2", step_index=0,
        batch_size=1, brief="## Need\nY",
    )
    db.set_inject_decision_produced_goal(conn, decision_id, fwd)

    db.update_goal_status(conn, fwd, "shelved")
    affected = db.propagate_inject_outcome_from_goal(conn, fwd)
    assert affected == decision_id
    assert _decision_outcome(conn, decision_id) == "failed:shelved"


def test_propagate_inject_outcome_noop_on_intermediate_status(
    conn: sqlite3.Connection,
) -> None:
    """Non-terminal status flips (open/attempting) must not fill the
    decision outcome — the lemma is still being worked on."""
    _insert_root(conn)
    fwd = db.insert_goal(
        conn, problem="p", slug="fwd",
        lean_path="Problems/p/proofs/L_fwd.lean",
        statement="T", origin="forward",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-3", step_index=0,
        batch_size=1, brief="## Need\nZ",
    )
    db.set_inject_decision_produced_goal(conn, decision_id, fwd)

    db.update_goal_status(conn, fwd, "attempting")
    affected = db.propagate_inject_outcome_from_goal(conn, fwd)
    assert affected is None
    assert _decision_outcome(conn, decision_id) is None


def test_propagate_inject_outcome_idempotent(
    conn: sqlite3.Connection,
) -> None:
    """Re-running propagate on an already-filled decision is a no-op
    (the `outcome IS NULL` guard)."""
    _insert_root(conn)
    fwd = db.insert_goal(
        conn, problem="p", slug="fwd",
        lean_path="Problems/p/proofs/L_fwd.lean",
        statement="T", origin="forward",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-4", step_index=0,
        batch_size=1, brief="## Need\nQ",
    )
    db.set_inject_decision_produced_goal(conn, decision_id, fwd)

    db.update_goal_status(conn, fwd, "proved")
    first = db.propagate_inject_outcome_from_goal(conn, fwd)
    second = db.propagate_inject_outcome_from_goal(conn, fwd)
    assert first == decision_id
    assert second is None  # already filled
    assert _decision_outcome(conn, decision_id) == "success"


def _insert_inject_decision(conn: sqlite3.Connection, *, problem: str,
                            batch_id: str, step_index: int,
                            batch_size: int, brief: str) -> int:
    payload = json.dumps({
        "pipeline": "Forward", "step_index": step_index,
        "batch_size": batch_size,
    })
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason,"
        " payload, batch_id, outcome, created_at, updated_at)"
        " VALUES (?, 0, 'pending_review', 'Inject', NULL, ?, NULL, ?,"
        " ?, NULL, ?, ?)",
        (problem, brief, payload, batch_id, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def _decision_outcome(conn: sqlite3.Connection, decision_id: int) -> str | None:
    row = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (decision_id,),
    ).fetchone()
    return None if row is None or row["outcome"] is None else str(row["outcome"])
