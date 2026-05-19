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
        "briefs": ["## Need\nFoo"],
    })
    d, err = strategist.parse_decision(text)
    assert err == ""
    assert d is not None
    assert d.kind == "Inject"
    assert d.payload.get("pipeline") == "Forward"
    assert d.payload.get("briefs") == ["## Need\nFoo"]


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
        "kind": "Inject", "pipeline": "Backward", "briefs": ["x"],
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "Forward" in err


def test_verify_inject_requires_briefs_field(
    conn: sqlite3.Connection,
) -> None:
    """Unified schema (Phase 2.5) requires `briefs: list[str]`. An Inject
    with no briefs field is rejected even if some other payload key is
    set."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "briefs" in err.lower()


def test_verify_inject_rejects_empty_brief_in_list(
    conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward", "briefs": ["  "],
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "[0]" in err and "non-empty" in err.lower()


def test_verify_inject_rejects_legacy_brief_field(
    conn: sqlite3.Connection,
) -> None:
    """`brief` (singular, str) was the pre-unification field. Reject
    with a migration hint pointing at `briefs` list."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "brief": "legacy single brief",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    # Either "missing briefs" or "legacy brief" path; both should
    # mention briefs as the correct field.
    assert "briefs" in err.lower()


def test_verify_inject_ok_single_brief_in_list(
    conn: sqlite3.Connection,
) -> None:
    """N=1 is valid — the degenerate single-Forward case under the
    unified schema."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "briefs": ["## Need\nfoo"],
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""


def test_verify_inject_ok_multi_briefs(conn: sqlite3.Connection) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "briefs": ["a", "b", "c"],
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


def test_commit_inject_single_brief_enqueues_forward_with_decision_id(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """N=1 Inject (unified Phase 2.5) — one Forward enqueue, decision
    row carries batch_id (every Inject is a batch, N=1 is degenerate)."""
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "briefs": ["## Need\nfoo"],
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
    # The audit row carries the batch_id even though N=1.
    row = conn.execute(
        "SELECT batch_id, brief FROM strategist_decisions WHERE id = ?",
        (outcome.decision_row_id,),
    ).fetchone()
    assert row["batch_id"] == outcome.batch_id
    assert row["brief"] == "## Need\nfoo"


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

def test_verify_inject_rejects_oversized_batch(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    cap = strategist.inject_batch_max()
    too_many = [f"lemma {i}" for i in range(cap + 1)]
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "briefs": too_many,
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
            "briefs": ["a", "b", "c"],
        }))
        assert strategist.verify_decision(d_ok, conn, problem="p") == ""
        d_bad, _ = strategist.parse_decision(json.dumps({
            "kind": "Inject", "pipeline": "Forward",
            "briefs": ["a", "b", "c", "d"],
        }))
        err = strategist.verify_decision(d_bad, conn, problem="p")
        assert "too large" in err
        assert "max 3" in err
    finally:
        config._reset_cache()


def test_commit_inject_batch_inserts_n_rows_and_n_enqueues(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    _insert_root(conn)
    briefs = ["land lineThrough", "land perpFoot", "land perpDistSq"]
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "briefs": briefs,
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


def test_commit_inject_n1_is_degenerate_batch(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """N=1 Inject under the unified schema goes through the same batch
    helper as N>1: one audit row, one Forward enqueue, batch_id set."""
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "briefs": ["solo brief"],
    }))
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    assert outcome.batch_id is not None
    assert len(outcome.batch_decision_row_ids) == 1
    rows = list(conn.execute(
        "SELECT brief, batch_id, payload FROM strategist_decisions"
        " WHERE problem='p' AND decision_kind='Inject'"
    ))
    assert len(rows) == 1
    assert rows[0]["batch_id"] == outcome.batch_id
    assert rows[0]["brief"] == "solo brief"
    p = json.loads(rows[0]["payload"])
    assert p["step_index"] == 0
    assert p["batch_size"] == 1
    # Queue: one Forward enqueue
    q_rows = list(conn.execute(
        "SELECT decision_id FROM queue WHERE kind='Forward'"
    ))
    assert len(q_rows) == 1
    assert q_rows[0]["decision_id"] == outcome.decision_row_id


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
