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
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)",
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
    assert d.brief == "## Need\nFoo"
    assert d.payload.get("pipeline") == "Forward"


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


def test_parse_initialize_defs() -> None:
    text = json.dumps({
        "kind": "InitializeDefs", "problem": "p",
        "lean_body": "import Mathlib\n",
        "reason": "scaffold",
    })
    d, err = strategist.parse_decision(text)
    assert err == ""
    assert d.payload["lean_body"] == "import Mathlib\n"


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

def test_verify_inject_requires_forward_pipeline(
    conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward", "brief": "x",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "Forward" in err


def test_verify_inject_requires_brief(conn: sqlite3.Connection) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward", "brief": "  ",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "brief" in err.lower()


def test_verify_inject_ok(conn: sqlite3.Connection) -> None:
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


def test_commit_inject_enqueues_forward_with_decision_id(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
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
    q = conn.execute(
        "SELECT kind, target_id, target_kind, decision_id FROM queue"
        " WHERE kind='Forward'"
    ).fetchone()
    assert q is not None
    assert q["target_id"] == "p"
    assert q["target_kind"] == "Problem"
    assert q["decision_id"] == outcome.decision_row_id


def test_commit_initialize_defs_writes_file(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "InitializeDefs", "problem": "p",
        "lean_body": "import Mathlib\nopen Real\n",
        "reason": "scaffold",
    }))
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="first_launch",
        workspace=workspace,
    )
    defs_path = workspace / "Problems" / "p" / "Defs.lean"
    assert defs_path.exists()
    assert "open Real" in defs_path.read_text(encoding="utf-8")


def test_commit_confirmshelve_cascades_descendants(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
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
# Phase 2.5 — Inject(chain_briefs=[...]) batch path
# ---------------------------------------------------------------------

def test_verify_inject_chain_briefs_accepted(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "chain_briefs": ["land lemma 1", "land lemma 2", "land lemma 3"],
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""


def test_verify_inject_rejects_brief_and_chain_briefs_together(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "brief": "solo",
        "chain_briefs": ["a", "b"],
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "brief" in err and "chain_briefs" in err


def test_verify_inject_rejects_single_chain_brief(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "chain_briefs": ["only one"],
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert ">= 2" in err


def test_verify_inject_rejects_oversized_batch(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    cap = strategist.inject_batch_max()
    too_many = [f"lemma {i}" for i in range(cap + 1)]
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "chain_briefs": too_many,
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "too large" in err


def test_inject_batch_max_honours_env_override(
    workspace: Path, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """env / yaml override raises (or lowers) the batch cap without code
    edit. Reads through the standard config.get chain at verify time."""
    from Tooling.core import config
    monkeypatch.setenv("ASTERISM_INJECT_BATCH_MAX", "3")
    config._reset_cache()
    try:
        assert strategist.inject_batch_max() == 3
        # Exactly 3 is OK, 4 is rejected
        d_ok, _ = strategist.parse_decision(json.dumps({
            "kind": "Inject", "pipeline": "Forward",
            "chain_briefs": ["a", "b", "c"],
        }))
        assert strategist.verify_decision(d_ok, conn, problem="p") == ""
        d_bad, _ = strategist.parse_decision(json.dumps({
            "kind": "Inject", "pipeline": "Forward",
            "chain_briefs": ["a", "b", "c", "d"],
        }))
        err = strategist.verify_decision(d_bad, conn, problem="p")
        assert "too large" in err
        assert "max 3" in err
    finally:
        config._reset_cache()


def test_verify_inject_rejects_empty_brief_in_chain(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "chain_briefs": ["valid", "   "],
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "[1]" in err and "non-empty" in err


def test_commit_inject_batch_inserts_n_rows_and_n_enqueues(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    _insert_root(conn)
    briefs = ["land lineThrough", "land perpFoot", "land perpDistSq"]
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "chain_briefs": briefs,
    }))
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="pending_review",
        workspace=workspace,
    )
    assert outcome.batch_id is not None
    assert outcome.enqueued_forward is True
    assert len(outcome.batch_decision_row_ids) == len(briefs)
    # Each row INSERTed with same batch_id, step_index 0..N-1
    rows = list(conn.execute(
        "SELECT id, brief, batch_id, payload, outcome FROM strategist_decisions"
        " WHERE problem='p' AND decision_kind='Inject'"
        " ORDER BY id"
    ))
    assert len(rows) == len(briefs)
    assert {r["batch_id"] for r in rows} == {outcome.batch_id}
    for i, (r, expected_brief) in enumerate(zip(rows, briefs)):
        assert r["brief"] == expected_brief
        assert r["outcome"] is None  # filled by cascade later
        p = json.loads(r["payload"])
        assert p["pipeline"] == "Forward"
        assert p["step_index"] == i
        assert p["batch_size"] == len(briefs)
    # N Forward enqueues, each tagged with the matching decision_id
    q_rows = list(conn.execute(
        "SELECT target_id, target_kind, decision_id FROM queue"
        " WHERE kind='Forward' ORDER BY id"
    ))
    assert len(q_rows) == len(briefs)
    assert [int(r["decision_id"]) for r in q_rows] == \
        outcome.batch_decision_row_ids
    for r in q_rows:
        assert r["target_id"] == "p"
        assert r["target_kind"] == "Problem"


def test_inject_solo_path_still_uses_brief_field(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Regression — solo Inject (brief field) must keep working
    unchanged; the batch detection short-circuits on chain_briefs only."""
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "brief": "solo brief",
    }))
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    assert outcome.batch_id is None
    assert outcome.batch_decision_row_ids == []
    rows = list(conn.execute(
        "SELECT brief, batch_id FROM strategist_decisions WHERE problem='p'"
    ))
    assert len(rows) == 1
    assert rows[0]["batch_id"] is None
    assert rows[0]["brief"] == "solo brief"
