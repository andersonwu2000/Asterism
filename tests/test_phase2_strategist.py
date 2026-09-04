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

from Tooling.pipeline import PROMPT_DIR, strategist
from Tooling.state import db


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done)"
        " VALUES ('p', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


def _insert_root(conn: sqlite3.Connection) -> int:
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/Root.lean", statement="T",
        origin="root", depth=0,
    )


# ---------------------------------------------------------------------
# parse_decision
# ---------------------------------------------------------------------

def test_parse_inject_decision() -> None:
    text = json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "proof": "Theorem. ## Need\nFoo\nProof. as argued.",
    })
    d, err = strategist.parse_decision(text)
    assert err == ""
    assert d is not None
    assert d.kind == "Inject"
    assert d.payload.get("pipeline") == "Forward"
    assert d.brief == "Theorem. ## Need\nFoo\nProof. as argued."


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

def test_verify_inject_ignores_legacy_pipeline_field(
    conn: sqlite3.Connection,
) -> None:
    """Shape-derived Inject (update_plan_2026_07 #1): the legacy
    `pipeline` payload value is ignored — any value, even garbage,
    verifies fine when the SHAPE is valid (no target = mint)."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Reflection", "proof": "Theorem. mint X\nProof. as argued.",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""


def test_verify_inject_requires_brief_field(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: Inject requires top-level `brief: str`. Missing brief
    is rejected."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "proof" in err.lower()


def test_verify_inject_rejects_empty_brief(
    conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward", "proof": "  ",
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
    assert "proof" in err.lower()


def test_verify_inject_ok_single_brief(
    conn: sqlite3.Connection,
) -> None:
    """Forward Inject: one brief per decision (multi-Inject lands as
    multiple decisions in the future multi-decision schema)."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "proof": "Theorem. ## Need\nfoo\nProof. as argued.",
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
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": "main", "proof": "Theorem. ready\nProof. as argued.",
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
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": "nonexistent", "proof": "Theorem. x\nProof. as argued.",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "slug" in err.lower() and "not found" in err.lower()


def test_parse_target_id_int_string_coerces(
    conn: sqlite3.Connection,
) -> None:
    """`"2019"` (digit string) coerces to int 2019 at parse-time so it
    doesn't hit the slug-lookup path unnecessarily."""
    d, err = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": "2019", "proof": "Theorem. x\nProof. as argued.",
    }))
    assert err == ""
    assert d.target_id == 2019  # coerced to int


def test_parse_target_id_rejects_non_str_non_int(
    conn: sqlite3.Connection,
) -> None:
    d, err = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": [1, 2], "proof": "Theorem. x\nProof. as argued.",
    }))
    assert d is None
    assert "int, slug" in err.lower() or "list" in err.lower()


def test_verify_inject_rejected_when_ancestor_disproved(
    conn: sqlite3.Connection,
) -> None:
    """Ancestor safety walk (moved from Reopen to Inject 2026-05-28)."""
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
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": sub, "proof": "Theorem. retry\nProof. as argued.",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "disproved" in err.lower()


def test_verify_inject_rejected_when_ancestor_disproved(
    conn: sqlite3.Connection,
) -> None:
    """A `disproved` ancestor blocks Inject on descendants: the kernel
    checked a counterexample against a parent statement, so the
    descendant is moot while that stands. A PARKED ancestor does not
    block — auto-detach reopens those chains."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "disproved")
    sub = db.insert_goal(
        conn, problem="p", slug="sub_under_disproved",
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
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": sub, "proof": "Theorem. salvage\nProof. as argued.",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "disproved" in err.lower()
    # Hint names a reachable alternative
    assert "new statement" in err.lower() or "confirmshelve" in err.lower()


def test_verify_inject_ok_with_shelved_ancestor(
    conn: sqlite3.Connection,
) -> None:
    """`shelved` ancestor doesn't block Inject (framework auto-detaches
    the descendant)."""
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
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": sub, "proof": "Theorem. x\nProof. as argued.",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""


def test_verify_request_user_amend_file_check(
    conn: sqlite3.Connection,
) -> None:
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "RequestUserAmend", "problem": "p",
        "file": "patch.lean", "proposed_body": "x", "question": "?",
        "reason": "x",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "Defs.lean" in err and "charter" in err
    # Root.lean is amendable since the feature-D livelock fix
    # (a false root claim must be hand-back-able).
    d2, _ = strategist.parse_decision(json.dumps({
        "kind": "RequestUserAmend", "problem": "p",
        "file": "Root.lean", "proposed_body": "x", "question": "?",
        "reason": "x",
    }))
    assert strategist.verify_decision(d2, conn, problem="p") == ""


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

def test_verify_inject_without_target_is_mint_shape(
    conn: sqlite3.Connection,
) -> None:
    """Shape-derived: no `target_goal_id` = mint one new brick — valid
    regardless of any legacy pipeline word in the payload."""
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "proof": "Theorem. try angle X\nProof. as argued.", "reason": "retry",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""


def test_verify_inject_backward_rejects_terminal_target(
    conn: sqlite3.Connection,
) -> None:
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "proved")
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "proof": "Theorem. try again\nProof. as argued.",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "terminal" in err.lower() or "proved" in err.lower()


def test_verify_inject_backward_rejects_disproved_target(
    conn: sqlite3.Connection,
) -> None:
    """`disproved` is a kernel-certified refutation (2026-09-04), so an
    Inject aimed at it is refused at verify time — the way out is a new
    statement, not another argument for the refuted one."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "disproved")
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "proof": "Theorem. try again\nProof. as argued.",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "disproved" in err.lower()


def test_verify_inject_with_target_is_goal_shape(
    conn: sqlite3.Connection,
) -> None:
    """Shape-derived (update_plan_2026_07 #1): `target_goal_id` present
    = work that goal — valid even when a legacy payload says 'Forward'
    (the field is ignored)."""
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "target_goal_id": root, "proof": "Theorem. ## Need foo\nProof. as argued.",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""


def test_verify_inject_rejects_legacy_briefs_or_directive_on_backward(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: legacy `briefs: list` / `directive` fields rejected for
    all pipelines. Single `brief` is the unified field."""
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "proof": "Theorem. try X\nProof. as argued.", "briefs": ["x"],
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "proof" in err.lower()


def test_verify_inject_backward_accepts_slug_target(
    conn: sqlite3.Connection,
) -> None:
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": "main", "proof": "Theorem. switch angle\nProof. as argued.",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert err == ""
    # Slug normalized to int (lifted to Decision.target_id by parse)
    assert d.target_id == root


def test_commit_inject_backward_enqueues_with_directive(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Inject(Backward, target, directive) writes a single decision row
    with directive in the brief column, enqueues Backward on the goal,
    and force-reopens if currently shelved.

    Backward/Builder Inject does NOT carry a batch_id (Strategist need
    not be re-fired when the redispatched goal terminates — normal
    cascade handles propagation). `produced_goal_id=target_id` is kept
    so the decision row's `outcome` still fills via
    `propagate_inject_outcome_from_goal` for failure_replay.
    """
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "shelved")
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "proof": "Theorem. try the contour deformation angle\nProof. as argued.",
        "reason": "previous decomp went through wrong primitive existence",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="pending_review",
        workspace=workspace,
    )
    # Backward/Builder injects now share Forward's batch_id mechanism
    # so `inject_batch_done` fires when the produced strategy (set by
    # the worker via `produced_strategy_id`) or the target goal
    # reaches terminal. Solo commit gets a fresh batch UUID.
    assert outcome.batch_id is not None
    assert len(outcome.batch_decision_row_ids) == 1
    # Decision row: directive in brief, produced_goal_id linked to
    # target for outcome bookkeeping, batch_id present.
    row = conn.execute(
        "SELECT brief, produced_goal_id, batch_id"
        " FROM strategist_decisions WHERE id=?",
        (outcome.decision_row_id,),
    ).fetchone()
    assert "contour deformation" in row["brief"]
    assert row["produced_goal_id"] == root
    assert row["batch_id"] == outcome.batch_id
    # Target force-reopened
    assert db.get_goal(conn, root)["status"] == "open"
    # Formalizer enqueued on the goal (merged worker)
    q = conn.execute(
        "SELECT kind, target_id, decision_id FROM queue"
        " WHERE kind='Formalizer'"
    ).fetchone()
    assert q is not None
    assert int(q["target_id"]) == root
    assert q["decision_id"] == outcome.decision_row_id


def test_commit_inject_backward_unstalls_parent_strategy(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Phase 11: force-reopening a shelved sub-goal un-parks a parent
    strategy that was 'stalled' (this sub-goal was its last settled one)
    back to 'proposed', so the alive-DAG conducts through it again and BFS
    can reach the reopened goal — otherwise it stays orphaned."""
    root = _insert_root(conn)
    g = db.insert_goal(
        conn, problem="p", slug="sub",
        lean_path="Problems/p/proofs/L_sub.lean", statement="T",
        origin="backward", depth=1,
    )
    db.update_goal_status(conn, g, "shelved")
    # Parent strategy on root, PARKED 'stalled', whose only sub-goal is g.
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at)"
        " VALUES (?, '', '', 'stalled', '', 'test', ?)",
        (root, db.now()),
    )
    sid = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, g))
    conn.commit()

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward", "target_goal_id": g,
        "proof": "Theorem. retry sub via a different primitive\nProof. as argued.",
        "reason": "the prior decomposition stalled",
    }))
    assert strategist.verify_decision(d, conn, problem="p") == ""
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="inject_batch_done",
        workspace=workspace,
    )

    assert db.get_goal(conn, g)["status"] == "open"        # force-reopened
    parent = conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sid,)).fetchone()
    assert parent["status"] == "proposed"                  # un-stalled


def test_commit_inject_builder_works_similarly(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Inject(Builder) mirrors Backward — same redispatch semantic,
    different pipeline target."""
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Builder",
        "target_goal_id": root, "proof": "Theorem. try linarith + Mathlib.Algebra.foo\nProof. as argued.",
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
    assert q["kind"] == "Formalizer"


def test_commit_inject_goal_shape_single_queue_kind(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """entry_kind pinning is GONE (v33): consecutive goal-targeted
    Injects — whatever legacy pipeline word they carry — both enqueue
    the single 'Formalizer' kind, so the parallel-pipeline race the old
    pin guarded (LU lu_step_assembly 2026-05-28) is structurally
    impossible."""
    root = _insert_root(conn)
    for tick, legacy in ((1, "Builder"), (2, "Backward")):
        d, _ = strategist.parse_decision(json.dumps({
            "kind": "Inject", "pipeline": legacy,
            "target_goal_id": root, "proof": f"Theorem. angle {tick}\nProof. as argued.",
        }))
        strategist.commit_decision(
            d, conn, problem="p", tick=tick, trigger_kind="pending_review",
            workspace=workspace,
        )
    kinds = {r["kind"] for r in conn.execute(
        "SELECT kind FROM queue WHERE target_id=?", (str(root),))}
    assert kinds == {"Formalizer"}


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
    # last_strategist_at bumped (bootstrap_done is vestigial in Phase 6 —
    # commits no longer touch it)
    p = conn.execute(
        "SELECT last_strategist_at FROM problems WHERE name='p'"
    ).fetchone()
    assert p["last_strategist_at"] is not None


def test_pure_inject_routine_batch_bumps_routine_clock(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Task #119 (b6_1 leg 6, 2026-07-25): the Inject commit paths
    return early and used to skip the shared clock tail — a pure-Inject
    routine batch left `last_routine_at` NULL, so T1 read "never
    routine'd" and pumped a fresh routine wake the instant the previous
    one finished. Clocks are now touched once per batch in
    `commit_decisions`."""
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "proof": "Theorem. re-attack with new plan\nProof. as argued.",
    }))
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    p = conn.execute(
        "SELECT last_strategist_at, last_routine_at FROM problems"
        " WHERE name='p'").fetchone()
    assert p["last_strategist_at"] is not None
    assert p["last_routine_at"] is not None


def test_event_trigger_never_bumps_routine_clock(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The routine clock stays event-immune: a non-routine commit (any
    kind) advances last_strategist_at only."""
    root = _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "proof": "Theorem. batch-done follow-up\nProof. as argued.",
    }))
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="inject_batch_done",
        workspace=workspace,
    )
    p = conn.execute(
        "SELECT last_strategist_at, last_routine_at FROM problems"
        " WHERE name='p'").fetchone()
    assert p["last_strategist_at"] is not None
    assert p["last_routine_at"] is None


def test_emitdirective_is_retired_at_verify_and_fenced_at_commit(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """RS-B (research_mission_design.md §3.1): standing worker guidance
    moved into the Programme's `## Conventions` section. Verify teaches
    the successor; the commit branch is a loud fence, not a writer —
    reaching it means a verify path let the retired kind through."""
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "EmitDirective", "scope": "problem:p",
        "body": "Prefer L_x", "reason": "shift",
    }))
    err = strategist.verify_decision(d, conn, problem="p")
    assert "retired" in err and "## Conventions" in err
    with pytest.raises(RuntimeError, match="retired"):
        strategist.commit_decision(
            d, conn, problem="p", tick=1, trigger_kind="routine",
            workspace=workspace,
        )
    p = conn.execute(
        "SELECT strategist_directive FROM problems WHERE name='p'"
    ).fetchone()
    assert not (p["strategist_directive"] or "")


def test_commit_inject_forward_enqueues_with_decision_id(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Phase 6: one Inject(Forward) = one decision = one row + one
    Forward enqueue. batch_id is set on the audit row so future
    multi-decision support can group them under one Strategist call."""
    _insert_root(conn)
    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "proof": "Theorem. ## Need\nfoo\nProof. as argued.",
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
        " WHERE kind='Formalizer'"
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
    assert row["brief"] == "Theorem. ## Need\nfoo\nProof. as argued."


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


def test_commit_confirmshelve_noop_on_proved_goal(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """ConfirmShelve on an already-proved goal is a silent no-op — it
    must NOT regress proved → shelved. BT 2026-05-29 g3380: a goal whose
    strategy fully succeeded (all subs proved, alias written on disk) got
    ConfirmShelve'd by a Strategist retiring a proved-but-superseded
    orphan; the shelve overrode the completed proof. The command commits
    (no batch bounce) but leaves the goal proved."""
    root = _insert_root(conn)
    proved = db.insert_goal(
        conn, problem="p", slug="proved_orphan",
        lean_path="Problems/p/proofs/L_proved_orphan.lean", statement="T",
        origin="backward",
    )
    db.update_goal_status(conn, proved, "proved")
    conn.commit()

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "ConfirmShelve", "target_goal_id": proved,
        "reason": "superseded orphan; retire",
    }))
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    assert db.get_goal(conn, proved)["status"] == "proved"


def test_set_goal_terminal_refuses_downgrade_of_terminal(
    conn: sqlite3.Connection,
) -> None:
    """Class-level backstop: _set_goal_terminal_and_propagate must refuse
    to flip a proved / disproved goal to shelved (any caller, not just
    ConfirmShelve). Legitimate transitions still pass."""
    from Tooling.core import dispatcher
    for terminal in ("proved", "disproved"):
        g = db.insert_goal(
            conn, problem="p", slug=f"g_{terminal}",
            lean_path=f"Problems/p/proofs/L_{terminal}.lean", statement="T",
            origin="backward",
        )
        db.update_goal_status(conn, g, terminal)
        conn.commit()
        dispatcher._set_goal_terminal_and_propagate(conn, g, "shelved")
        assert db.get_goal(conn, g)["status"] == terminal, (
            f"{terminal} goal was downgraded to shelved")
    # An open goal still shelves normally.
    g_open = db.insert_goal(
        conn, problem="p", slug="g_open",
        lean_path="Problems/p/proofs/L_open.lean", statement="T",
        origin="backward",
    )
    db.update_goal_status(conn, g_open, "open")
    conn.commit()
    dispatcher._set_goal_terminal_and_propagate(conn, g_open, "shelved")
    assert db.get_goal(conn, g_open)["status"] == "shelved"


def test_commit_paired_confirmshelve_shares_inject_batch_id(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """When `[ConfirmShelve(G), Inject(Forward, ...)]` ships in one
    decision array, the ConfirmShelve row must inherit the same
    batch_id as the Inject row(s). _section_pending_reopens relies on
    this link to re-surface G only when the explicit promised batch
    has completed. Pre-fix the ConfirmShelve row's batch_id stayed
    NULL, breaking the linkage (brouwer 2026-05-22: g2771
    ConfirmShelve'd 4x because surfacing fell back to "all shelved"
    when the promise link was missing)."""
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
    db.update_goal_status(conn, sub, "pending_strategist_review")
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, sub))
    conn.commit()

    cs, _ = strategist.parse_decision(json.dumps({
        "kind": "ConfirmShelve", "target_goal_id": sub,
        "reason": "shelving; injected Forward will unblock",
    }))
    ij, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "proof": "Theorem. ## Need\nFollow-up brick to unblock sub\nProof. as argued.",
    }))
    outcomes = strategist.commit_decisions(
        [cs, ij], conn, problem="p", tick=1,
        trigger_kind="pending_review", workspace=workspace,
    )
    # Pull both rows back; ConfirmShelve and Inject must share batch_id.
    cs_row = conn.execute(
        "SELECT batch_id FROM strategist_decisions WHERE id = ?",
        (outcomes[0].decision_row_id,),
    ).fetchone()
    ij_row = conn.execute(
        "SELECT batch_id FROM strategist_decisions WHERE id = ?",
        (outcomes[1].decision_row_id,),
    ).fetchone()
    assert cs_row["batch_id"] is not None
    assert cs_row["batch_id"] == ij_row["batch_id"]


def test_commit_inject_with_broken_chain_sets_detached(
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
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": sub, "proof": "Theorem. try again\nProof. as argued.",
    }))
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    g = db.get_goal(conn, sub)
    # Inject force-reopens to 'open' (not 'attempting') so bfs_refill —
    # which filters `status='open'` — can dispatch on the next tick.
    assert g["status"] == "open"
    assert g["detached"] == 1
    # Regression guard: open_goals (the BFS dispatch source) returns it
    # via the detached=1 seed even though no live ancestor strategy exists.
    open_ids = {int(r["id"]) for r in db.open_goals(conn)}
    assert sub in open_ids


def test_commit_inject_makes_goal_dispatchable_via_bfs(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Inject force-reopens its target to 'open' (not 'attempting'), so
    `db.open_goals` (filters status='open') exposes it to bfs_refill /
    Inject's own enqueued pipeline. Pre-2026-05-28 Reopen-via-attempting
    bug regression preserved with Inject as the unified reactivation.
    """
    root = _insert_root(conn)
    # Simulate the pre-Inject state: root was marked
    # pending_strategist_review and not dispatchable.
    db.update_goal_status(conn, root, "pending_strategist_review")
    assert root not in {int(r["id"]) for r in db.open_goals(conn)}

    d, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Backward",
        "target_goal_id": root, "proof": "Theorem. retry root\nProof. as argued.",
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
        "file": "charter",
        "proposed_body": "## New charter body",
        "question": "Accept?", "reason": "x",
    }))
    outcome = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    proposed = workspace / "Problems" / "p" / ".proposed_charter"
    assert proposed.exists()
    assert "New charter body" in proposed.read_text(encoding="utf-8")
    # Outcome marks awaiting_human
    row = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?",
        (outcome.decision_row_id,),
    ).fetchone()
    assert row["outcome"] == "awaiting_human"


def test_strategist_prompts_cover_all_triggers() -> None:
    """Every TRIGGER_KIND must have a corresponding prompt file under
    Tooling/prompts/strategist/<trigger>.md. `run_strategist` resolves
    prompt path by trigger_kind; a missing file would fail an
    in-flight Strategist pipeline with `strategist_schema_invalid`."""
    prompt_dir = PROMPT_DIR / "strategist"
    assert prompt_dir.is_dir(), f"missing {prompt_dir}"
    # 'stall' deliberately ALIASES inject_batch_done.md (v43 identity
    # split is for the DB record, not a different conversation) — the
    # alias map here mirrors run_strategist's prompt resolution.
    _alias = {"stall": "inject_batch_done", "routine_fired": "inject_batch_done"}
    for tk in strategist.TRIGGER_KINDS:
        p = prompt_dir / f"{_alias.get(tk, tk)}.md"
        assert p.exists(), f"missing prompt file for trigger_kind={tk!r}: {p}"
        text = p.read_text(encoding="utf-8")
        assert text.strip(), f"empty prompt file: {p}"
        # Each prompt must mention its trigger_kind explicitly so
        # human reviewers can grep to find the right file.
        assert tk in text, (
            f"prompt {p} does not mention its trigger_kind {tk!r} in body")


def test_pending_review_wake_reads_the_batch_done_prompt() -> None:
    """`pending_review.md` was a near-mirror of `inject_batch_done.md`,
    so the two conversations drifted apart sentence by sentence. The
    review wake now reads the batch-done prompt, exactly as `stall` and
    `routine_fired` already do; the trigger_kind survives because the
    DB record and the timeline still distinguish WHY the wake fired."""
    assert strategist.prompt_kind("pending_review") == "inject_batch_done"
    assert "pending_review" in strategist.TRIGGER_KINDS
    assert not (PROMPT_DIR / "strategist" / "pending_review.md").exists()


def test_strategist_prompts_share_decision_kind_vocabulary() -> None:
    """Each per-trigger prompt must reference at least the decision
    kinds it can legitimately emit. Catches drift where a prompt
    silently drops a decision kind without removing it from the
    framework verify path (or vice versa). Per-trigger allowed sets
    track what `run_strategist` actually validates downstream.
    """
    # Reopen removed from Strategist prompts 2026-05-28: Inject(Backward|Builder)
    # now handles all "reactivate + dispatch" cases (LU lu_step_assembly bug class).
    # The Reopen decision kind still exists in the framework schema for backward
    # compat with old DB rows + tests; just no longer emitted by the prompts.
    # Noop removed from inject_batch_done.md 2026-07-11 (b6 wake pump): the
    # batch-done wake carries the mandatory-advance rule, so a Noop there was
    # never a legal answer — same retirement pattern as Reopen.
    # EmitDirective retired 2026-08-03 (RS-B/RS-E): standing worker guidance
    # lives in the Programme's `## Conventions` section; no prompt may still
    # offer the kind.
    # routine.md is the AUDIT prompt since 2026-08-30 — it emits no
    # decisions (verdict.json only), so it carries no decision kinds.
    expected_kinds = {
        "pending_review": {"Inject", "ConfirmShelve", "Delegate"},
        "inject_batch_done": {"Inject", "ConfirmShelve", "Delegate"},
    }
    for tk in expected_kinds:
        text = (PROMPT_DIR / "strategist" / f"{tk}.md").read_text(
            encoding="utf-8")
        # AttemptDisproof retired 2026-08-04, same pattern.
        for retired in ("EmitDirective", "AttemptDisproof"):
            assert retired not in text, \
                f"{tk}.md re-offers a retired kind ({retired})"
    prompt_dir = PROMPT_DIR / "strategist"
    for tk, kinds in expected_kinds.items():
        text = (prompt_dir / f"{tk}.md").read_text(encoding="utf-8")
        for k in kinds:
            assert k in text, (
                f"prompt {tk}.md is expected to reference decision kind "
                f"{k!r} but does not")


def test_synchronous_decisions_write_outcome_success_at_commit(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """jordan_normal_form 2026-05-23 regression. Pre-fix `_commit_one`
    wrote `outcome=NULL` for ConfirmShelve/Reopen/EmitDirective/Noop
    (the "committed → NULL" mapping at the INSERT site conflated the
    caller-signal `final_outcome` with the DB row's terminal-state
    column). NULL outcome on a non-Inject row inside a batch with a
    paired Inject made the batch-completion SQL guard
    `WHERE batch_id IS NOT NULL AND outcome IS NULL` see the row as
    "still pending" forever — `maybe_enqueue_inject_batch_done`,
    `problems_needing_t1`, and `problems_stalled` all stayed gated
    even after every Inject in the batch resolved. Jordan stalled
    silently after Brick C landed because Strategist's earlier
    `ConfirmShelve(succ_glue) + Inject(Forward, prereq)` batch could
    never reach "complete".

    Fix: synchronous decisions (whose side effect ran at commit time)
    write `outcome='success'` immediately. Inject keeps NULL (filled
    later by `propagate_inject_outcome_from_goal/strategy`).
    RequestUserAmend keeps its explicit `'awaiting_human'`."""
    _insert_root(conn)
    sub = db.insert_goal(
        conn, problem="p", slug="sub",
        lean_path="Problems/p/proofs/L_sub.lean", statement="T",
        origin="backward",
    )
    db.update_goal_status(conn, sub, "shelved")
    conn.commit()

    # ConfirmShelve + MarkDeliverable + Noop, paired with an Inject so
    # they all carry a shared batch_id (worst-case shape).
    # MarkDeliverable stands where the retired EmitDirective used to
    # (RS-B): a synchronous sibling whose row must not wedge the batch
    # NULL-open.
    proved = db.insert_goal(
        conn, problem="p", slug="done_brick",
        lean_path="Problems/p/proofs/L_done_brick.lean", statement="T",
        origin="forward",
    )
    db.update_goal_status(conn, proved, "proved")
    conn.commit()
    cs, _ = strategist.parse_decision(json.dumps({
        "kind": "ConfirmShelve", "target_goal_id": sub, "reason": "x",
    }))
    ed, _ = strategist.parse_decision(json.dumps({
        "kind": "MarkDeliverable", "target_goal_id": proved,
        "reason": "doc",
    }))
    noop, _ = strategist.parse_decision(json.dumps({
        "kind": "Noop", "reason": "pacing",
    }))
    ij, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "proof": "Theorem. ## Need\nbridge lemma\nProof. as argued.",
    }))
    # Two batches: (CS, Inject) exercises CS's commit-time outcome, then
    # (EmitDirective, Noop, Inject) exercises ED/Noop's commit-time
    # outcome. Each batch independently sets the shared batch_id via
    # the Inject.
    out_a = strategist.commit_decisions(
        [cs, ij], conn, problem="p", tick=1,
        trigger_kind="pending_review", workspace=workspace,
    )
    ij2, _ = strategist.parse_decision(json.dumps({
        "kind": "Inject", "pipeline": "Forward",
        "proof": "Theorem. ## Need\nsecond bridge\nProof. as argued.",
    }))
    out_b = strategist.commit_decisions(
        [ed, noop, ij2], conn, problem="p", tick=2,
        trigger_kind="routine", workspace=workspace,
    )

    def _row(decision_id: int) -> sqlite3.Row:
        return conn.execute(
            "SELECT decision_kind, outcome, batch_id"
            " FROM strategist_decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()

    cs_row = _row(out_a[0].decision_row_id)
    ij_row_a = _row(out_a[1].decision_row_id)
    assert cs_row["decision_kind"] == "ConfirmShelve"
    assert cs_row["outcome"] == "success"
    assert cs_row["batch_id"] is not None  # paired with Inject
    assert ij_row_a["decision_kind"] == "Inject"
    assert ij_row_a["outcome"] is None  # async, filled later
    assert ij_row_a["batch_id"] == cs_row["batch_id"]

    ed_row = _row(out_b[0].decision_row_id)
    noop_row = _row(out_b[1].decision_row_id)
    ij_row_b = _row(out_b[2].decision_row_id)
    for r, kind in ((ed_row, "MarkDeliverable"), (noop_row, "Noop")):
        assert r["decision_kind"] == kind
        assert r["outcome"] == "success", (
            f"{kind} row should write outcome='success' at commit; "
            f"got {r['outcome']!r}. Batch-completion SQL guards key "
            f"off this column.")
        assert r["batch_id"] is not None
    assert ij_row_b["outcome"] is None


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


def test_propagate_inject_outcome_shelved_does_not_settle(
    conn: sqlite3.Connection,
) -> None:
    """Goal flips to 'shelved' (parked, reopenable) → decision.outcome
    stays NULL (NOT settled). Shelved is a soft terminal; settling it
    re-fired the Strategist on every park (the P13 4284 futile spin,
    2026-06-15). Re-engaging a parked brick is T4's call (the active-check),
    not an unconditional inject_batch_done."""
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
    assert affected is None
    assert _decision_outcome(conn, decision_id) is None


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


def test_set_inject_decision_produced_goal_idempotent_same_value(
    conn: sqlite3.Connection,
) -> None:
    """Re-writing the same produced_goal_id is a silent no-op (idempotent
    — pipeline reentry / retry path can safely re-call)."""
    _insert_root(conn)
    fwd = db.insert_goal(
        conn, problem="p", slug="fwd_idem",
        lean_path="Problems/p/proofs/L_fwd_idem.lean",
        statement="T", origin="forward",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-idem", step_index=0,
        batch_size=1, brief="x",
    )
    db.set_inject_decision_produced_goal(conn, decision_id, fwd)
    db.set_inject_decision_produced_goal(conn, decision_id, fwd)  # no-op
    row = conn.execute(
        "SELECT produced_goal_id, produced_strategy_id FROM"
        " strategist_decisions WHERE id=?", (decision_id,),
    ).fetchone()
    assert row["produced_goal_id"] == fwd
    assert row["produced_strategy_id"] is None


def test_set_inject_decision_produced_goal_refuses_overwrite_different(
    conn: sqlite3.Connection, capsys: pytest.CaptureFixture,
) -> None:
    """Writing a DIFFERENT produced_goal_id is rejected — the first
    write owns the decision's audit record. Symptom of a double dispatch
    (recovery 2026-05-21 misroute scenario)."""
    _insert_root(conn)
    g_first = db.insert_goal(
        conn, problem="p", slug="g_first",
        lean_path="Problems/p/proofs/L_g_first.lean",
        statement="T", origin="forward",
    )
    g_second = db.insert_goal(
        conn, problem="p", slug="g_second",
        lean_path="Problems/p/proofs/L_g_second.lean",
        statement="T", origin="forward",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-conflict", step_index=0,
        batch_size=1, brief="x",
    )
    db.set_inject_decision_produced_goal(conn, decision_id, g_first)
    db.set_inject_decision_produced_goal(conn, decision_id, g_second)
    row = conn.execute(
        "SELECT produced_goal_id FROM strategist_decisions WHERE id=?",
        (decision_id,),
    ).fetchone()
    assert row["produced_goal_id"] == g_first  # first write stuck
    captured = capsys.readouterr()
    assert "refusing to overwrite produced_goal_id" in captured.out


def test_set_inject_decision_produced_goal_refuses_when_strategy_set(
    conn: sqlite3.Connection, capsys: pytest.CaptureFixture,
) -> None:
    """Cross-column guard: writing produced_goal_id when
    produced_strategy_id is already set is rejected. This is the exact
    residue_thm 2026-05-21 g2494 / s10559 confusion — a single Inject
    decision row ended up tagged with both kinds of produced artifact
    because recovery re-dispatched a Backward Inject as Forward."""
    _insert_root(conn)
    gid = db.insert_goal(
        conn, problem="p", slug="tgt",
        lean_path="Problems/p/proofs/L_tgt.lean",
        statement="T", origin="backward", depth=1,
    )
    sid = db.insert_strategy(
        conn, goal_id=gid,
        lean_path="Problems/p/proofs/L_tgt.lean",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        created_by="pid",
    )
    fwd_goal = db.insert_goal(
        conn, problem="p", slug="fwd_other",
        lean_path="Problems/p/proofs/L_fwd_other.lean",
        statement="T", origin="forward",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-x", step_index=0,
        batch_size=1, brief="x",
    )
    db.set_inject_decision_produced_strategy(conn, decision_id, sid)
    db.set_inject_decision_produced_goal(conn, decision_id, fwd_goal)
    row = conn.execute(
        "SELECT produced_goal_id, produced_strategy_id FROM"
        " strategist_decisions WHERE id=?", (decision_id,),
    ).fetchone()
    assert row["produced_strategy_id"] == sid
    assert row["produced_goal_id"] is None  # rejected
    captured = capsys.readouterr()
    assert "double-dispatch indicator" in captured.out


def test_set_inject_decision_produced_strategy_refuses_when_goal_set(
    conn: sqlite3.Connection, capsys: pytest.CaptureFixture,
) -> None:
    """Inverse: writing produced_strategy_id when produced_goal_id is
    already set is rejected."""
    _insert_root(conn)
    fwd = db.insert_goal(
        conn, problem="p", slug="fwd",
        lean_path="Problems/p/proofs/L_fwd.lean",
        statement="T", origin="forward",
    )
    bwd_goal = db.insert_goal(
        conn, problem="p", slug="bwd",
        lean_path="Problems/p/proofs/L_bwd.lean",
        statement="T", origin="backward", depth=1,
    )
    sid = db.insert_strategy(
        conn, goal_id=bwd_goal,
        lean_path="Problems/p/proofs/L_bwd.lean",
        scratch_path="Problems/p/proofs/_strategy_b.lean",
        created_by="pid",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-y", step_index=0,
        batch_size=1, brief="x",
    )
    db.set_inject_decision_produced_goal(conn, decision_id, fwd)
    db.set_inject_decision_produced_strategy(conn, decision_id, sid)
    row = conn.execute(
        "SELECT produced_goal_id, produced_strategy_id FROM"
        " strategist_decisions WHERE id=?", (decision_id,),
    ).fetchone()
    assert row["produced_goal_id"] == fwd
    assert row["produced_strategy_id"] is None
    captured = capsys.readouterr()
    assert "double-dispatch indicator" in captured.out


def test_set_inject_decision_dual_set_consistent_backward_inject(
    conn: sqlite3.Connection, capsys: pytest.CaptureFixture,
) -> None:
    """Backward Inject's legitimate dual-set: `_commit_inject_redispatch`
    writes produced_goal_id=target_id at decision INSERT, then the
    Backward worker reserves a strategy on that same goal and calls
    `set_inject_decision_produced_strategy`. Both columns end up set
    and consistent (strategy.goal_id == produced_goal_id).

    Regression: 2026-05-26 Banach-Tarski daemon storm — the cross-column
    guard mis-identified this consistent dual-set as the residue_thm
    misroute and silently refused the strategy write, leaving the
    decision's outcome perpetually NULL while bfs_refill re-enqueued the
    open target goal → 34+ empty `dead` strategies in 4 minutes.
    """
    _insert_root(conn)
    target = db.insert_goal(
        conn, problem="p", slug="tgt",
        lean_path="Problems/p/proofs/L_tgt.lean",
        statement="T", origin="backward", depth=1,
    )
    sid = db.insert_strategy(
        conn, goal_id=target,
        lean_path="Problems/p/proofs/L_tgt.lean",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        created_by="pid",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-z", step_index=0,
        batch_size=1, brief="x",
    )
    # Mirror _commit_inject_redispatch's pre-set at INSERT.
    conn.execute(
        "UPDATE strategist_decisions SET produced_goal_id = ?"
        " WHERE id = ?", (target, decision_id),
    )
    conn.commit()
    db.set_inject_decision_produced_strategy(conn, decision_id, sid)
    row = conn.execute(
        "SELECT produced_goal_id, produced_strategy_id FROM"
        " strategist_decisions WHERE id=?", (decision_id,),
    ).fetchone()
    assert row["produced_goal_id"] == target
    assert row["produced_strategy_id"] == sid  # accepted (consistent)
    captured = capsys.readouterr()
    assert "double-dispatch indicator" not in captured.out


def test_set_inject_decision_produced_goal_dual_set_consistent(
    conn: sqlite3.Connection, capsys: pytest.CaptureFixture,
) -> None:
    """Mirror of the Backward-Inject dual-set case: setting
    produced_goal_id when an existing produced_strategy_id points at a
    strategy whose goal_id matches the new produced_goal_id is allowed.
    Distinguishes consistent dual-set from the residue_thm misroute
    (different goals).
    """
    _insert_root(conn)
    target = db.insert_goal(
        conn, problem="p", slug="tgt",
        lean_path="Problems/p/proofs/L_tgt.lean",
        statement="T", origin="backward", depth=1,
    )
    sid = db.insert_strategy(
        conn, goal_id=target,
        lean_path="Problems/p/proofs/L_tgt.lean",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        created_by="pid",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-w", step_index=0,
        batch_size=1, brief="x",
    )
    db.set_inject_decision_produced_strategy(conn, decision_id, sid)
    # Now setting produced_goal_id on the same target should succeed
    # (strategy.goal_id == target).
    db.set_inject_decision_produced_goal(conn, decision_id, target)
    row = conn.execute(
        "SELECT produced_goal_id, produced_strategy_id FROM"
        " strategist_decisions WHERE id=?", (decision_id,),
    ).fetchone()
    assert row["produced_goal_id"] == target
    assert row["produced_strategy_id"] == sid
    captured = capsys.readouterr()
    assert "double-dispatch indicator" not in captured.out


def test_propagate_inject_outcome_disproved(
    conn: sqlite3.Connection,
) -> None:
    """Goal flips to 'disproved' → decision outcome becomes
    'failed:disproved', which is what lets inject_batch_done fire for a
    batch whose produced lemma turned out false. A PARK never settles an
    inject (it is reopenable), so this is the only failed side."""
    _insert_root(conn)
    fwd = db.insert_goal(
        conn, problem="p", slug="fwd",
        lean_path="Problems/p/proofs/L_fwd.lean",
        statement="T", origin="forward",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-false", step_index=0,
        batch_size=1, brief="## Need\nD",
    )
    db.set_inject_decision_produced_goal(conn, decision_id, fwd)

    db.update_goal_status(conn, fwd, "disproved")
    affected = db.propagate_inject_outcome_from_goal(conn, fwd)
    assert affected == decision_id
    assert _decision_outcome(conn, decision_id) == "failed:disproved"


def test_propagate_inject_outcome_from_strategy_succeeded(
    conn: sqlite3.Connection,
) -> None:
    """Inject(Backward) commits to track the produced strategy: when
    that strategy reaches 'succeeded' (verify proved it), the
    decision's outcome becomes 'success' and the batch can wake
    Strategist. Mirrors the goal-side 'proved' path for Forward."""
    _insert_root(conn)
    gid = db.insert_goal(
        conn, problem="p", slug="tgt",
        lean_path="Problems/p/proofs/L_tgt.lean",
        statement="T", origin="backward", depth=1,
    )
    sid = db.insert_strategy(
        conn, goal_id=gid,
        lean_path="Problems/p/proofs/L_tgt.lean",
        scratch_path="Problems/p/proofs/_strategy_succ.lean",
        created_by="pid",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-bs", step_index=0,
        batch_size=1, brief="hint",
    )
    db.set_inject_decision_produced_strategy(conn, decision_id, sid)

    db.update_strategy_status(conn, sid, "succeeded")
    assert _decision_outcome(conn, decision_id) == "success"


def test_propagate_inject_outcome_from_strategy_dead_fires_batch_done(
    conn: sqlite3.Connection,
) -> None:
    """Backward Inject scenario from session 2026-05-21: s10491 dies
    via cascade with target goal staying 'attempting'. Old framework:
    no propagation, decision outcome stays NULL, Strategist never
    woken. New framework: produced_strategy_id linkage + update_
    strategy_status hook fill outcome on strategy-dead and enqueue
    `inject_batch_done` (visible as a new Strategist queue row)."""
    root = _insert_root(conn)
    gid = db.insert_goal(
        conn, problem="p", slug="bd_target",
        lean_path="Problems/p/proofs/L_bd_target.lean",
        statement="T", origin="backward", depth=1,
    )
    db.update_goal_status(conn, gid, "attempting")
    sid = db.insert_strategy(
        conn, goal_id=gid,
        lean_path="Problems/p/proofs/L_bd_target.lean",
        scratch_path="Problems/p/proofs/_strategy_bd.lean",
        created_by="pid",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-bd", step_index=0,
        batch_size=1, brief="hint",
    )
    db.set_inject_decision_produced_strategy(conn, decision_id, sid)

    db.update_strategy_status(conn, sid, "dead")
    assert _decision_outcome(conn, decision_id) == "failed:dead"
    # And inject_batch_done fired: a problem-keyed Strategist queue row
    # appeared (Phase 6: target_id=<problem name>, target_kind='Problem').
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue"
        " WHERE kind = 'Strategist' AND target_kind = 'Group'"
        "   AND problem = 'p'",
    ).fetchone()
    assert int(q["n"]) == 1
    assert root  # root exists but the wake is problem-keyed


def test_propagate_strategy_death_carries_why_to_outcome_detail(
    conn: sqlite3.Connection,
) -> None:
    """07-18 survey asymmetry: Forward declines push their `## Why`
    prose into `outcome_detail` (rendered as the `why:` line), but a
    dead Backward redispatch surfaced only the bare enum while the
    forensics sat in dead_attempts behind the gated pending_review
    trigger. Propagation now synthesizes the WHY from the freshest
    dead_attempts rows on the strategy's goal/subgoals."""
    _insert_root(conn)
    gid = db.insert_goal(
        conn, problem="p", slug="dw_target",
        lean_path="Problems/p/proofs/L_dw_target.lean",
        statement="T", origin="backward", depth=1,
    )
    sid = db.insert_strategy(
        conn, goal_id=gid,
        lean_path="Problems/p/proofs/L_dw_target.lean",
        scratch_path="Problems/p/proofs/_strategy_dw.lean",
        created_by="pid",
    )
    decision_id = _insert_inject_decision(
        conn, problem="p", batch_id="batch-dw", step_index=0,
        batch_size=1, brief="hint",
    )
    db.set_inject_decision_produced_strategy(conn, decision_id, sid)
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind,"
        " status, outcome, started_at, finished_at) VALUES ('pid-dw',"
        " 'Backward', ?, 'Goal', 'failed', 'agent_declined', ?, ?)",
        (str(gid), db.now(), db.now()))
    conn.commit()
    db.record_dead_attempt(
        conn, target_id=gid, target_kind="Goal", pipeline_id="pid-dw",
        failure_reason="circular_decomposition",
        failure_detail="sub-goal restates ancestor g5 verbatim")

    db.update_strategy_status(conn, sid, "dead")
    row = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (decision_id,)).fetchone()
    assert row["outcome"] == "failed:dead"
    detail = str(row["outcome_detail"] or "")
    assert "circular_decomposition" in detail
    assert "restates ancestor g5" in detail
    assert "dw_target" in detail


def test_inject_batch_done_waits_for_last_kind_in_mixed_batch(
    conn: sqlite3.Connection,
) -> None:
    """Mixed Forward + Backward batch: outcome fills for each
    independently; the batch-done wake-up fires only after BOTH have
    reached terminal — even though Forward terminates via goal and
    Backward via strategy. Closes the user's unified-batch request."""
    root = _insert_root(conn)
    # Forward decision tied to its produced lemma goal.
    fwd_goal = db.insert_goal(
        conn, problem="p", slug="fwd_lem",
        lean_path="Problems/p/proofs/L_fwd_lem.lean",
        statement="T", origin="forward",
    )
    d_fwd = _insert_inject_decision(
        conn, problem="p", batch_id="batch-mix", step_index=0,
        batch_size=2, brief="## Need\nL",
    )
    db.set_inject_decision_produced_goal(conn, d_fwd, fwd_goal)
    # Backward decision tied to its produced strategy.
    bw_goal = db.insert_goal(
        conn, problem="p", slug="bw_target",
        lean_path="Problems/p/proofs/L_bw_target.lean",
        statement="T", origin="backward", depth=1,
    )
    bw_sid = db.insert_strategy(
        conn, goal_id=bw_goal,
        lean_path="Problems/p/proofs/L_bw_target.lean",
        scratch_path="Problems/p/proofs/_strategy_mix.lean",
        created_by="pid",
    )
    d_bw = _insert_inject_decision(
        conn, problem="p", batch_id="batch-mix", step_index=1,
        batch_size=2, brief="hint",
    )
    db.set_inject_decision_produced_strategy(conn, d_bw, bw_sid)

    # Only Backward terminates first: batch not done yet, no wake-up.
    db.update_strategy_status(conn, bw_sid, "dead")
    assert _decision_outcome(conn, d_bw) == "failed:dead"
    assert _decision_outcome(conn, d_fwd) is None
    q1 = conn.execute(
        "SELECT COUNT(*) AS n FROM queue"
        " WHERE kind = 'Strategist' AND target_id = 'p'",
    ).fetchone()
    assert int(q1["n"]) == 0

    # Forward now terminates → batch fully resolved → wake fires
    # (problem-keyed, Phase 6).
    db.update_goal_status(conn, fwd_goal, "proved")
    affected = db.propagate_inject_outcome_from_goal(conn, fwd_goal)
    assert affected == d_fwd
    db.maybe_enqueue_inject_batch_done(conn, d_fwd)
    q2 = conn.execute(
        "SELECT COUNT(*) AS n FROM queue"
        " WHERE kind = 'Strategist' AND target_kind = 'Group'"
        "   AND problem = 'p'",
    ).fetchone()
    assert int(q2["n"]) == 1
    assert root  # root exists but the wake is problem-keyed


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


# ---------------------------------------------------------------------
# Multi-decision schema (parse_decisions / verify_decisions /
# commit_decisions)
# ---------------------------------------------------------------------

def test_parse_decisions_accepts_dict_wraps_to_list() -> None:
    """Backward-compat: a top-level JSON object is wrapped as [obj] so
    agents still emitting a single object continue to work."""
    text = json.dumps({"kind": "Noop", "reason": "wait"})
    ds, err = strategist.parse_decisions(text)
    assert err == ""
    assert ds is not None
    assert len(ds) == 1
    assert ds[0].kind == "Noop"


def test_parse_decisions_accepts_array_of_two() -> None:
    text = json.dumps([
        {"kind": "Inject", "pipeline": "Forward",
         "proof": "Theorem. ## Need\nbridge lemma\nProof. as argued."},
        {"kind": "ConfirmShelve", "target_goal_id": 7, "reason": "drop"},
    ])
    ds, err = strategist.parse_decisions(text)
    assert err == ""
    assert ds is not None and len(ds) == 2
    assert ds[0].kind == "Inject"
    assert ds[1].kind == "ConfirmShelve"
    assert ds[1].target_id == 7


def test_parse_decisions_rejects_empty_array() -> None:
    ds, err = strategist.parse_decisions(json.dumps([]))
    assert ds is None
    assert "empty" in err.lower()


def test_parse_decisions_rejects_scalar() -> None:
    ds, err = strategist.parse_decisions(json.dumps("oops"))
    assert ds is None
    assert "object or array" in err.lower()


def test_parse_decisions_indexes_per_item_error() -> None:
    """Bad item in a multi-decision array reports its position so the
    agent can fix the right one."""
    text = json.dumps([
        {"kind": "Noop", "reason": "wait"},
        {"kind": "Telekinesis", "reason": "?"},
    ])
    ds, err = strategist.parse_decisions(text)
    assert ds is None
    assert "#1" in err and "unknown" in err.lower()


def test_parse_decision_rejects_multi_when_single_expected() -> None:
    """The single-decision wrapper rejects arrays of length != 1 so
    legacy callers can't silently lose decisions."""
    text = json.dumps([
        {"kind": "Noop", "reason": "a"},
        {"kind": "Noop", "reason": "b"},
    ])
    d, err = strategist.parse_decision(text)
    assert d is None
    assert "single decision" in err.lower()


def test_verify_decisions_rejects_noop_alone_when_root_shelved_no_inflight(
    conn: sqlite3.Connection,
) -> None:
    """The residue_thm 2026-05-20 case: Strategist parks root via
    ConfirmShelve while a Forward Inject is in flight, then on
    inject_batch_done re-fires it emits a lone Noop assuming BFS
    will dispatch the sub-tree the Forward built. But root='shelved'
    contributes no alive seed to open_goals's CTE — the whole
    subtree is frozen until Strategist acts. Reject Noop-only batches
    in this state."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "shelved")
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "let BFS run"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "Inject" in err and "shelved" in err.lower()
    assert str(root) in err  # hint references actual root goal_id


def test_verify_decisions_rejects_emit_directive_alone_when_root_shelved(
    conn: sqlite3.Connection,
) -> None:
    """The #85 pump shape (EmitDirective-only batch on a shelved root)
    is now unrepresentable one gate EARLIER: the kind itself is retired
    (RS-B). The anti-idle property it used to leak stays guarded by the
    Noop-shape tests; this pins that the retired kind cannot re-enter
    the batch at all."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "shelved")
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "EmitDirective", "scope": "problem:p",
         "body": "Avoid X route.", "reason": "lock in learning"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "retired" in err and "## Conventions" in err


def test_verify_decisions_accepts_noop_when_root_shelved_but_inflight_forward(
    conn: sqlite3.Connection,
) -> None:
    """If a prior Strategist's Inject(Forward) is still in flight
    (batch_id non-NULL, outcome NULL), Noop is valid — the cascade-
    side `inject_batch_done` trigger will re-fire Strategist when
    the Forward terminates, so the framework IS making progress."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "shelved")
    # Seed an in-flight Forward Inject row on this problem
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', 'Inject', NULL, '## brief',"
        " NULL, '{\"pipeline\":\"Forward\"}', 'batch-x', NULL, ?, ?)",
        (db.now(), db.now()),
    )
    conn.commit()
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "wait for in-flight Forward"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""


def test_verify_decisions_rejects_noop_when_inflight_inject_parked_shelved(
    conn: sqlite3.Connection,
) -> None:
    """A NULL-outcome Inject whose produced goal got SHELVED is PARKED, not
    in flight — its outcome stays NULL forever now that `shelved` no longer
    settles (db.propagate_inject_outcome_from_goal). The old blanket "any
    NULL-outcome batch row" check read it as in-flight and ALLOWED a Noop
    here, while T4 (db.is_problem_stalled) saw the same problem as stalled and
    re-fired the Strategist → Noop → re-fire LIVELOCK (the P13 4284 spin).
    `has_live_inflight_inject` excludes the parked inject, so the guard
    rejects the Noop and forces a real action — agreeing with T4."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "shelved")
    # A prior Inject produced a lemma goal that then SHELVED (parked).
    lemma = db.insert_goal(
        conn, problem="p", slug="parked_lemma",
        lean_path="Problems/p/proofs/L_parked_lemma.lean", statement="T",
        origin="forward",
    )
    db.update_goal_status(conn, lemma, "shelved")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, produced_goal_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'Inject', NULL, '## b',"
        " NULL, '{\"pipeline\":\"Forward\"}', 'batch-x', ?, NULL, ?, ?)",
        (lemma, db.now(), db.now()),
    )
    conn.commit()
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "wait for the (parked) brick"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "Inject" in err and "shelved" in err.lower()


def test_verify_decisions_accepts_inject_root_when_root_shelved(
    conn: sqlite3.Connection,
) -> None:
    """The canonical unfreeze action: when root is shelved and no
    in-flight Forward, Inject(Backward, target=root) is exactly what
    the rule wants."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "shelved")
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Backward", "target_goal_id": root,
         "proof": "Theorem. homotopy lemma proved; re-engage BFS on root\nProof. as argued."},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""


def test_verify_decisions_accepts_noop_when_root_attempting(
    conn: sqlite3.Connection,
) -> None:
    """When root is dispatchable (open/attempting), Noop is fine —
    BFS will continue without Strategist intervention."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "attempting")
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "workers are progressing"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""


def test_verify_decisions_rejects_noop_alone_when_root_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """`pending_strategist_review` on root means the last Backward agent
    declined `shelve` — Strategist was invoked specifically to break
    that impasse. Noop is a logical contradiction in that state.

    residue_thm 2026-05-20 run 4: Backward on root declined shelve;
    cascade set root pending_review; T2 fired Strategist which emitted
    Noop #116 ('let s10404 run' — but s10404 was already dead from
    Backward cleanup). Daemon idle-exited.

    2026-07-11: the review-discharge rule (b6 wake pump) now catches
    this BEFORE the root-blocked gate — same rejection, message names
    the reviewed goal instead of the 'logical contradiction' framing."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "pending_strategist_review")
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "let the framework run"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "Inject" in err
    assert "pending_strategist_review" in err
    assert "review not discharged" in err and f"g{root}" in err


def test_verify_decisions_rejects_noop_alone_when_root_frozen(
    conn: sqlite3.Connection,
) -> None:
    """`frozen` (first_launch initial state) is the same shape as
    `shelved` for the rule: BFS cannot dispatch, only Strategist can
    unfreeze. Noop alone is lazy here too."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "frozen")
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "first launch; nothing to do?"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "Inject" in err and "frozen" in err.lower()
    assert str(root) in err


def test_verify_decisions_allows_two_request_user_amend_in_batch(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Multi-decision allows co-amending Defs.lean + the charter in one
    batch so the operator can review the coupled drafts side by side
    (e.g. new def + charter wording pointing at it). The per-item
    `problem_has_awaiting_human` gate naturally serialises across
    batches — once the batch commits, both rows are
    `outcome='awaiting_human'` and any subsequent Strategist amend
    is blocked until the operator resolves them."""
    _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "RequestUserAmend", "problem": "p", "file": "Defs.lean",
         "proposed_body": "-- new def body\n",
         "question": "OK?", "reason": "need vocab"},
        {"kind": "RequestUserAmend", "problem": "p", "file": "charter",
         "proposed_body": "## Hints\n- prefer new def\n",
         "question": "OK?", "reason": "point hints at new vocab"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""
    outcomes = strategist.commit_decisions(
        ds, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    assert len(outcomes) == 2
    # Both audit rows are awaiting_human, both `.proposed_<file>`
    # written.
    rows = list(conn.execute(
        "SELECT outcome FROM strategist_decisions"
        " WHERE decision_kind='RequestUserAmend' ORDER BY id"
    ))
    assert [r["outcome"] for r in rows] == ["awaiting_human",
                                            "awaiting_human"]
    assert (workspace / "Problems" / "p" / ".proposed_Defs.lean").exists()
    assert (workspace / "Problems" / "p" / ".proposed_charter").exists()


def test_verify_decisions_rejects_lone_confirmshelve(
    conn: sqlite3.Connection,
) -> None:
    """ConfirmShelve cannot be the only decision in a batch. Forces
    Strategist to articulate the next step (build the missing tool,
    redispatch a different goal, record the learning, etc.) — silent
    give-up is blocked at the framework level so the prompt doesn't
    have to police it."""
    root = _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "ConfirmShelve", "target_goal_id": root,
         "reason": "looks intractable"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "ConfirmShelve" in err and "alone" in err.lower()


def test_verify_decisions_rejects_confirmshelve_plus_only_noop(
    conn: sqlite3.Connection,
) -> None:
    """Noop is not a constructive sibling — `[ConfirmShelve, Noop]`
    is the same lazy pattern as a lone ConfirmShelve."""
    root = _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "ConfirmShelve", "target_goal_id": root, "reason": "x"},
        {"kind": "Noop", "reason": "nothing else to do"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "ConfirmShelve" in err and "alone" in err.lower()


def test_verify_decisions_rejects_multi_confirmshelve_without_constructive(
    conn: sqlite3.Connection,
) -> None:
    """Bulk give-up: two ConfirmShelves with no constructive sibling
    is still the lazy pattern. Same rule, different shape."""
    root = _insert_root(conn)
    sub = db.insert_goal(
        conn, problem="p", slug="sub",
        lean_path="Problems/p/proofs/L_sub.lean", statement="T",
        origin="backward",
    )
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "ConfirmShelve", "target_goal_id": root, "reason": "x"},
        {"kind": "ConfirmShelve", "target_goal_id": sub, "reason": "y"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "ConfirmShelve" in err and "alone" in err.lower()


def test_verify_decisions_accepts_confirmshelve_paired_with_inject(
    conn: sqlite3.Connection,
) -> None:
    """The canonical pairing: ConfirmShelve(pending) + Inject(Forward)
    to build the missing tool."""
    root = _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Forward",
         "proof": "Theorem. ## Need\nthe missing bridge lemma\nProof. as argued."},
        {"kind": "ConfirmShelve", "target_goal_id": root,
         "reason": "shelve while Forward builds the lemma"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""


def test_verify_decisions_allows_standalone_reconfirm_of_shelved_goal(
    conn: sqlite3.Connection,
) -> None:
    """ConfirmShelve 終態 (2026-07-06): a ConfirmShelve RE-CONFIRMING an
    already-shelved goal may stand alone. Pairing it with an Inject gives
    the new ConfirmShelve the batch's shared batch_id — a fresh
    reopen-promise — so the "still dead" verdict itself re-armed the loop
    it was answering. A standalone re-confirm acks the old promise (the
    reopen query's later-decision NOT EXISTS) and mints none (no Inject
    sibling = no promise). First-time shelves keep the pairing rule."""
    root = _insert_root(conn)          # root open → root-blocked gate idle
    assert root
    sub = db.insert_goal(
        conn, problem="p", slug="parked",
        lean_path="Problems/p/proofs/L_parked.lean", statement="T",
        origin="backward",
    )
    conn.execute("UPDATE goals SET status='shelved' WHERE id=?", (sub,))
    conn.commit()
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "ConfirmShelve", "target_goal_id": sub,
         "reason": "still dead: superseded by the reframed joint invariant"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""


def test_verify_decisions_standalone_reconfirm_still_blocked_when_stalled(
    conn: sqlite3.Connection,
) -> None:
    """The forcing backstop the exemption leans on: with the ROOT itself
    blocked (shelved) and no live in-flight Inject, a no-Inject batch —
    including a standalone re-confirm — is still hard-rejected by the
    root-blocked gate. The exemption can never idle a stalled problem."""
    root = _insert_root(conn)
    sub = db.insert_goal(
        conn, problem="p", slug="parked2",
        lean_path="Problems/p/proofs/L_parked2.lean", statement="T",
        origin="backward",
    )
    conn.execute("UPDATE goals SET status='shelved' WHERE id IN (?, ?)",
                 (root, sub))
    conn.commit()
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "ConfirmShelve", "target_goal_id": sub,
         "reason": "still dead"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "will progress without your action" in err


def test_verify_decisions_rejects_confirmshelve_paired_only_with_request_user_amend(
    conn: sqlite3.Connection,
) -> None:
    """RequestUserAmend is NOT a constructive sibling for ConfirmShelve.
    It's the user-escalation channel for Defs.lean / charter errors,
    not a way to dodge the 'articulate the next step' rule. If both
    apply, send as separate Strategist calls (the user-amend pauses
    dispatch anyway via the awaiting_human gate)."""
    root = _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "RequestUserAmend", "problem": "p", "file": "charter",
         "proposed_body": "## Hints\n- new hint\n",
         "question": "OK?", "reason": "hints look misleading"},
        {"kind": "ConfirmShelve", "target_goal_id": root,
         "reason": "give up while user reviews"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "ConfirmShelve" in err and "alone" in err.lower()


def test_fetch_paper_decision_is_retired_with_teaching(
    conn: sqlite3.Connection,
) -> None:
    """FetchPaper retired 2026-08-22 (owner ruling): paper fetching is
    the Strategist's own tool surface now. The kind stays recognized so
    the gate can TEACH the replacement instead of reading as a typo."""
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "FetchPaper", "query": "survey of the blocked route",
         "reason": "record learning before shelving"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "retired" in err
    assert "paper_fetch" in err and "paper_search" in err


def test_verify_decisions_rejects_confirmshelve_plus_inject_bb_same_target(
    conn: sqlite3.Connection,
) -> None:
    """Same-target safety: Inject(Backward, target=G) force-reopens G;
    a sibling ConfirmShelve(G) then shelves it, leaving a queued
    Backward dispatch on a shelved goal (undefined). Reject at verify
    time so the agent removes the ConfirmShelve (the Inject already
    keeps G alive) or aims the Inject elsewhere.

    Covers Backward; the Builder variant is symmetric.
    """
    root = _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Backward",
         "target_goal_id": root, "proof": "Theorem. try angle X\nProof. as argued."},
        {"kind": "ConfirmShelve", "target_goal_id": root,
         "reason": "give up"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "ConfirmShelve" in err and "Inject" in err
    assert "shelved goal" in err.lower() or "queued retry" in err.lower()


def test_verify_decisions_rejects_confirmshelve_ancestor_plus_inject_descendant(
    conn: sqlite3.Connection,
) -> None:
    """ConfirmShelve(ancestor) + Inject(Backward/Builder, target=descendant)
    is rejected. _set_goal_terminal_and_propagate cascades shelve to all
    descendants via _cascade_shelve_descendants AFTER the Inject's
    auto-reopen in the same batch, silently overriding it. The queued
    redispatch then moots on a goal that's been flipped back to shelved.

    Repro: BT 2026-05-29 batch [Inject(g3298 sphere_paradoxical),
    ConfirmShelve(g3296 main)] — Inject reopened g3298 at .475,
    ConfirmShelve cascade re-shelved it at .486, Builder dispatched at
    .494 and the goal_still_active check on entry returned False
    (status='shelved') → moot.
    """
    root = _insert_root(conn)
    # Build a 2-level chain: root → strategy → sub
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

    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Builder",
         "target_goal_id": sub,
         "proof": "Theorem. rescue this sub now that brick X landed\nProof. as argued."},
        {"kind": "ConfirmShelve", "target_goal_id": root,
         "reason": "current decomposition exhausted"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert "descendant" in err.lower()
    assert "_cascade_shelve_descendants" in err or "cascade" in err.lower()
    assert str(root) in err and str(sub) in err


def test_verify_decisions_allows_confirmshelve_with_inject_bb_different_target(
    conn: sqlite3.Connection,
) -> None:
    """The canonical pending_review multi-decision pattern: redispatch
    a DIFFERENT goal while shelving the pending one. Must NOT be
    blocked by the same-target safety check."""
    root = _insert_root(conn)
    other = db.insert_goal(
        conn, problem="p", slug="other",
        lean_path="Problems/p/proofs/L_other.lean", statement="T",
        origin="backward",
    )
    db.update_goal_status(conn, root, "pending_strategist_review")
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Backward",
         "target_goal_id": other, "proof": "Theorem. attack parent instead\nProof. as argued."},
        {"kind": "ConfirmShelve", "target_goal_id": root,
         "reason": "shelve pending; parent retry is the way"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""


def test_verify_decisions_indexes_per_item_failure(
    conn: sqlite3.Connection,
) -> None:
    """Per-item verify failure in a multi-decision batch surfaces the
    item index in the error so the agent can fix the right one."""
    _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "wait"},
        {"kind": "Inject", "pipeline": "Forward"},  # missing brief
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p")
    assert err != ""
    assert "#1" in err and "proof" in err.lower()


def test_commit_decisions_multi_forward_share_one_batch_id(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Two Inject(Forward) in one Strategist call share one batch_id
    so `inject_batch_done` fires once after both produced lemmas
    terminate (single Strategist wake-up, not two)."""
    _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Forward",
         "proof": "Theorem. ## Need\nlemma A\nProof. as argued."},
        {"kind": "Inject", "pipeline": "Forward",
         "proof": "Theorem. ## Need\nlemma B\nProof. as argued."},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""
    outcomes = strategist.commit_decisions(
        ds, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    assert len(outcomes) == 2
    assert outcomes[0].batch_id is not None
    assert outcomes[0].batch_id == outcomes[1].batch_id
    # Both decision rows persist with the same batch_id, and the audit
    # payload carries REAL per-step indices + the batch size (was
    # hardcoded step_index=0 for every row — Context labelled every
    # step "step 0" and the Strategist couldn't line outcomes up with
    # its briefs).
    rows = list(conn.execute(
        "SELECT batch_id, payload FROM strategist_decisions"
        " WHERE id IN (?, ?) ORDER BY id",
        (outcomes[0].decision_row_id, outcomes[1].decision_row_id),
    ))
    assert rows[0]["batch_id"] == rows[1]["batch_id"] == outcomes[0].batch_id
    payloads = [json.loads(r["payload"]) for r in rows]
    assert [p["step_index"] for p in payloads] == [0, 1]
    assert [p["batch_size"] for p in payloads] == [2, 2]


def test_commit_decisions_mixed_forward_and_backward_share_batch_id(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """In a mixed batch every Inject (Forward / Backward / Builder)
    shares one batch_id so a single `inject_batch_done` Strategist
    wake-up coalesces all completions — wake fires when the LAST
    decision (across kinds) reaches terminal. Each kind has its own
    completion signal: Forward via produced_goal_id, Backward via
    produced_strategy_id, Builder via produced_goal_id."""
    root = _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Forward",
         "proof": "Theorem. ## Need\nbridge lemma\nProof. as argued."},
        {"kind": "Inject", "pipeline": "Backward",
         "target_goal_id": root, "proof": "Theorem. try a different angle\nProof. as argued."},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""
    outcomes = strategist.commit_decisions(
        ds, conn, problem="p", tick=1, trigger_kind="pending_review",
        workspace=workspace,
    )
    assert outcomes[0].batch_id is not None
    assert outcomes[0].batch_id == outcomes[1].batch_id
    # And the persisted rows agree.
    fwd_row = conn.execute(
        "SELECT batch_id FROM strategist_decisions WHERE id=?",
        (outcomes[0].decision_row_id,),
    ).fetchone()
    bwd_row = conn.execute(
        "SELECT batch_id, produced_goal_id FROM strategist_decisions"
        " WHERE id=?",
        (outcomes[1].decision_row_id,),
    ).fetchone()
    assert fwd_row["batch_id"] == outcomes[0].batch_id
    assert bwd_row["batch_id"] == outcomes[0].batch_id
    # produced_goal_id still set on B/B so the goal-terminal path also
    # contributes to outcome filling (idempotent with the strategy path).
    assert bwd_row["produced_goal_id"] == root


def test_commit_decisions_inject_forward_plus_confirmshelve(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Canonical multi-decision use case during pending_review: inject
    a missing tool, shelve the pending goal in one transaction so the
    framework doesn't re-fire pending_review on the same goal."""
    root = _insert_root(conn)
    db.update_goal_status(conn, root, "pending_strategist_review")
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Forward",
         "proof": "Theorem. ## Need\nthe missing bridge lemma\nProof. as argued."},
        {"kind": "ConfirmShelve", "target_goal_id": root,
         "reason": "shelve pending; rely on injected lemma later"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""
    outcomes = strategist.commit_decisions(
        ds, conn, problem="p", tick=1, trigger_kind="pending_review",
        workspace=workspace,
    )
    assert len(outcomes) == 2
    # Forward enqueued.
    fq = conn.execute(
        "SELECT decision_id FROM queue WHERE kind='Formalizer'"
    ).fetchone()
    assert fq is not None
    assert fq["decision_id"] == outcomes[0].decision_row_id
    # Pending goal is now shelved (ConfirmShelve flipped it).
    assert db.get_goal(conn, root)["status"] == "shelved"


# ---------------------------------------------------------------------
# The acknowledgment law — which completed Inject batches a commit is
# allowed to swallow (2026-09-03).
#
# Since the per-round refresh (1c942b70 / ff9e9a6a) a Strategist learns
# mid-debate that a batch it did not wake for has finished, and may act
# on it in the batch it is about to land. The clock ratchet
# (`last_strategist_at`) could not tell those two apart: bumped at
# commit, it swallowed EVERY completed batch, acted on or not — so a
# batch whose whole report the author had seen as one delta LINE was
# marked as delivered and its outcomes never reached any wake.
# ---------------------------------------------------------------------

def _seed_done_batch(conn: sqlite3.Connection, *, batch_id: str,
                     group_id: int, produced_goal_id: "int | None" = None,
                     produced_strategy_id: "int | None" = None,
                     problem: str = "p") -> str:
    """One Inject batch that has fully terminated — every row's `outcome`
    filled, which is the shape `unacknowledged_inject_batches` looks
    for."""
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief, reason,"
        " payload, batch_id, produced_goal_id, produced_strategy_id,"
        " outcome, created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'Inject', ?, NULL, 'brief', NULL, '{}',"
        "         ?, ?, ?, 'success', ?, ?)",
        (problem, int(group_id), batch_id, produced_goal_id,
         produced_strategy_id, ts, ts))
    conn.commit()
    return batch_id


def _landed_row(conn: sqlite3.Connection, *, kind: str, group_id: int,
                target_id: "int | None", problem: str = "p") -> int:
    """A committed decision row of `kind` naming `target_id`."""
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief, reason,"
        " payload, outcome, created_at, updated_at)"
        " VALUES (?, 0, 'routine', ?, ?, ?, NULL, 'r', '{}', 'success',"
        "         ?, ?)",
        (problem, kind, int(group_id), target_id, ts, ts))
    conn.commit()
    return int(cur.lastrowid)


def test_a_landed_decision_acknowledges_the_batch_it_touches(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """THE scenario. Batch A produced g123 and finished mid-debate — the
    author saw it as a delta line, never as a report. This wake lands an
    Inject targeting g123: it ACTED on A, so A is acknowledged and never
    comes back. That Inject is batch B; when B finishes, the next wake's
    batch section carries B's outcome and only B's.

    The acknowledgment is keyed by batch_id, never by goal id: B is not
    acknowledged for containing g123's work, it is simply not finished
    yet, and A is not un-acknowledged by B landing on the same goal."""
    from Tooling.state import groups as _groups
    _insert_root(conn)
    top = _groups.ensure_top_group(conn, "p")
    g123 = db.insert_goal(
        conn, problem="p", slug="brick_a",
        lean_path="Problems/p/proofs/L_brick_a.lean", statement="A",
        origin="forward", depth=1)
    _seed_done_batch(conn, batch_id="A", group_id=top,
                     produced_goal_id=g123)
    assert db.unacknowledged_inject_batches(conn, "p", top) == ["A"]

    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Backward", "target_goal_id": g123,
         "proof": "Theorem. split the brick\nProof. as argued."},
    ]))
    assert strategist.verify_decisions(
        ds, conn, problem="p", group_id=top) == ""
    outcomes = strategist.commit_decisions(
        ds, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace, group_id=top, delivered_batches=[])
    b = outcomes[0].batch_id
    assert b is not None and b != "A"
    assert db.unacknowledged_inject_batches(conn, "p", top) == []

    # B terminates later — only B is owed a report.
    conn.execute(
        "UPDATE strategist_decisions SET outcome='return_to_nl',"
        " updated_at = ? WHERE batch_id = ?", (db.now(), b))
    conn.commit()
    assert db.unacknowledged_inject_batches(conn, "p", top) == [b]


def test_a_batch_that_terminated_on_the_commits_own_tick_is_still_owed(
    conn: sqlite3.Connection,
) -> None:
    """The ratchet compared `MAX(updated_at) > last_strategist_at`, and
    on Windows both stamps come from the same coarse clock: a batch whose
    last row settled inside the commit's own tick tied, lost the strict
    comparison, and its report reached no wake at all. Same granularity
    bug the decline window already carries `>=` for (`_recent_decline_
    lines`: "a decline landing the same clock tick as the wake's own
    commit must not vanish"); an exact-boundary repeat is harmless,
    a swallowed report is not."""
    from Tooling.state import groups as _groups
    _insert_root(conn)
    top = _groups.ensure_top_group(conn, "p")
    _seed_done_batch(conn, batch_id="TIE", group_id=top)
    tie = db.now()
    conn.execute("UPDATE strategist_decisions SET updated_at = ?"
                 " WHERE batch_id = 'TIE'", (tie,))
    conn.execute("UPDATE groups SET last_strategist_at = ? WHERE id = ?",
                 (tie, top))
    conn.commit()
    assert db.unacknowledged_inject_batches(conn, "p", top) == ["TIE"]


def test_a_batch_seen_only_in_the_delta_stays_unacknowledged(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Same setup, but nothing this wake lands touches g123. A delta LINE
    is not the report: the next wake still owes the author A's outcomes,
    so A survives the commit that would previously have swallowed it."""
    from Tooling.state import groups as _groups
    _insert_root(conn)
    top = _groups.ensure_top_group(conn, "p")
    g123 = db.insert_goal(
        conn, problem="p", slug="brick_b",
        lean_path="Problems/p/proofs/L_brick_b.lean", statement="A",
        origin="forward", depth=1)
    _seed_done_batch(conn, batch_id="A", group_id=top,
                     produced_goal_id=g123)

    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Forward",
         "proof": "Theorem. ## Need\nan unrelated lemma\nProof. as argued."},
    ]))
    assert strategist.verify_decisions(
        ds, conn, problem="p", group_id=top) == ""
    strategist.commit_decisions(
        ds, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace, group_id=top, delivered_batches=[])
    assert db.unacknowledged_inject_batches(conn, "p", top) == ["A"]


@pytest.mark.parametrize("kind", ["ConfirmShelve", "MarkDeliverable",
                                  "ReturnToParent", "Delegate", "Inject"])
def test_any_landed_kind_naming_a_goal_of_the_batch_acknowledges_it(
    conn: sqlite3.Connection, kind: str,
) -> None:
    """The law reads the COMMITTED ROWS' `target_id` / produced goal, not
    a per-kind allowlist: every decision kind that can name a goal
    acknowledges the batch that produced it, and a kind added tomorrow
    joins by construction."""
    from Tooling.state import groups as _groups
    from Tooling.pipeline.strategist import batch_ack
    _insert_root(conn)
    top = _groups.ensure_top_group(conn, "p")
    g = db.insert_goal(
        conn, problem="p", slug=f"brick_{kind.lower()}",
        lean_path=f"Problems/p/proofs/L_{kind.lower()}.lean",
        statement="A", origin="forward", depth=1)
    _seed_done_batch(conn, batch_id="A", group_id=top, produced_goal_id=g)
    rid = _landed_row(conn, kind=kind, group_id=top, target_id=g)
    acked, carried = batch_ack.settle(
        conn, problem="p", group_id=top, delivered=[],
        landed_row_ids=[rid])
    assert (acked, carried) == (["A"], [])
    # Acknowledged = not carried past the clock bump the commit does next.
    _groups.touch_strategist(conn, top, routine=False)
    assert db.unacknowledged_inject_batches(conn, "p", top) == []


def test_the_batch_goal_set_reaches_its_minted_descendants(
    conn: sqlite3.Connection,
) -> None:
    """"Its goals" means the batch's produced goals AND the sub-goals
    minted under them — a Strategist acting on a grandchild is acting on
    the batch. A CITED sibling is not descent: it has its own life and
    its own producing batch."""
    from Tooling.state import groups as _groups
    from Tooling.pipeline.strategist import batch_ack
    _insert_root(conn)
    top = _groups.ensure_top_group(conn, "p")
    parent = db.insert_goal(
        conn, problem="p", slug="anc", lean_path="Problems/p/proofs/anc.lean",
        statement="A", origin="forward", depth=1)
    kid = db.insert_goal(
        conn, problem="p", slug="kid", lean_path="Problems/p/proofs/kid.lean",
        statement="B", origin="backward", depth=2)
    outsider = db.insert_goal(
        conn, problem="p", slug="out", lean_path="Problems/p/proofs/out.lean",
        statement="C", origin="backward", depth=2)
    sid = db.insert_strategy(
        conn, goal_id=parent, lean_path="Problems/p/proofs/anc.lean",
        proposal_md="split", created_by="backward")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=kid, position=0)
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=outsider, position=1,
                    link_kind="cited")
    _seed_done_batch(conn, batch_id="A", group_id=top,
                     produced_goal_id=parent)
    assert batch_ack.batch_goal_ids(conn, "A") == {parent, kid}

    rid = _landed_row(conn, kind="ConfirmShelve", group_id=top,
                      target_id=kid)
    acked, _ = batch_ack.settle(conn, problem="p", group_id=top,
                                delivered=[], landed_row_ids=[rid])
    assert acked == ["A"]


def test_acknowledging_a_batch_leaves_the_pending_review_standing(
    conn: sqlite3.Connection,
) -> None:
    """The law touches batch reports and nothing else. A goal parked in
    `pending_strategist_review` by a `return_to_nl` decline is the T2
    trigger's persistent state — answered by a decision about THAT goal,
    never by a batch acknowledgment happening beside it. So after the
    acknowledgment the review row still stands and still classifies the
    next wake."""
    from Tooling.state import groups as _groups
    from Tooling.pipeline.strategist import batch_ack
    from Tooling.core.dispatcher.triggers import _derive_strategist_trigger
    _insert_root(conn)
    top = _groups.ensure_top_group(conn, "p")
    g123 = db.insert_goal(
        conn, problem="p", slug="brick_c",
        lean_path="Problems/p/proofs/L_brick_c.lean", statement="A",
        origin="forward", depth=1)
    reviewed = db.insert_goal(
        conn, problem="p", slug="returned",
        lean_path="Problems/p/proofs/L_returned.lean", statement="R",
        origin="forward", depth=1, status="pending_strategist_review")
    _seed_done_batch(conn, batch_id="A", group_id=top,
                     produced_goal_id=g123)
    rid = _landed_row(conn, kind="Inject", group_id=top, target_id=g123)

    acked, carried = batch_ack.settle(
        conn, problem="p", group_id=top, delivered=[],
        landed_row_ids=[rid])
    _groups.touch_strategist(conn, top, routine=False)
    assert (acked, carried) == (["A"], [])
    assert db.unacknowledged_inject_batches(conn, "p", top) == []
    assert (db.get_goal(conn, reviewed)["status"]
            == "pending_strategist_review")
    assert _derive_strategist_trigger(
        conn, "p", group_id=top) == ("pending_review", reviewed)


def test_run_strategist_noop_only_batch_maps_to_strategist_noop(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """A batch of N Noops still trips `strategist_noop` so cascade_one
    doesn't burn root.attempts. Audit rows are written so the
    decisions show up in failure_replay."""
    _insert_root(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Noop", "reason": "wait A"},
        {"kind": "Noop", "reason": "wait B"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""
    outcomes = strategist.commit_decisions(
        ds, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace,
    )
    assert len(outcomes) == 2
    rows = list(conn.execute(
        "SELECT decision_kind, reason FROM strategist_decisions"
        " WHERE problem='p' ORDER BY id"
    ))
    assert [r["decision_kind"] for r in rows] == ["Noop", "Noop"]
    assert [r["reason"] for r in rows] == ["wait A", "wait B"]


def test_strict_ancestor_ids_walks_the_chain(conn):
    """Ancestor-link guard (PutnamCmp a5 deadlock 2026-07-19): the id
    walk must reach grandparents through strategy_subgoals so linking
    an ancestor as a sub-goal can be refused before it closes a cycle."""
    from Tooling.pipeline.backward import _strict_ancestor_ids
    from Tooling.state import db as _db
    _insert_root(conn)
    g1 = _db.insert_goal(conn, problem="p", slug="anc_top",
                         lean_path="Problems/p/proofs/L_anc_top.lean",
                         statement="A", origin="backward", depth=1)
    g2 = _db.insert_goal(conn, problem="p", slug="anc_mid",
                         lean_path="Problems/p/proofs/L_anc_mid.lean",
                         statement="B", origin="backward", depth=2)
    g3 = _db.insert_goal(conn, problem="p", slug="anc_leaf",
                         lean_path="Problems/p/proofs/L_anc_leaf.lean",
                         statement="C", origin="backward", depth=3)
    s1 = _db.insert_strategy(conn, goal_id=g1, lean_path="x",
                             scratch_path="s1", created_by="t")
    _db.link_subgoal(conn, strategy_id=s1, subgoal_id=g2, position=0)
    s2 = _db.insert_strategy(conn, goal_id=g2, lean_path="x",
                             scratch_path="s2", created_by="t")
    _db.link_subgoal(conn, strategy_id=s2, subgoal_id=g3, position=0)

    anc = _strict_ancestor_ids(conn, g3)
    assert g1 in anc and g2 in anc      # parent AND grandparent
    assert g3 not in anc                # strict
    assert _strict_ancestor_ids(conn, g1) == set()  # top has none


# ---------------------------------------------------------------------
# Theorize (theory_wake_design.md 2) - the hand-off to the theory layer
# ---------------------------------------------------------------------

_THEORIZE = {
    "kind": "Theorize",
    "objective": "S: S implies MAIN, or a proof that no such S exists.",
    "situation": "The bridge g12 came back returned; PAST 3-4 died there.",
}


def _theorize(**over):
    return json.dumps({**_THEORIZE, **over})


def test_theorize_parses_with_both_fields_in_payload(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Neither field is the `brief` column: a Theorize carries TWO
    pieces of prose and the column holds one, so both ride the payload
    - which is also what puts them in front of the judge (the
    projection renders every payload field)."""
    d, err = strategist.parse_decision(_theorize())
    assert err == "" and d is not None
    assert d.brief is None
    assert d.payload["objective"].startswith("S:")
    assert d.payload["situation"].startswith("The bridge")


@pytest.mark.parametrize("missing", ["objective", "situation"])
def test_verify_theorize_requires_both_fields(
    workspace: Path, conn: sqlite3.Connection, missing: str,
) -> None:
    """A request with no objective is a request the Theorist cannot
    answer, and one with no situation makes it re-derive the record it
    was supposed to build on."""
    d, _ = strategist.parse_decision(_theorize(**{missing: "   "}))
    err = strategist.verify_decision(d, conn, problem="p")
    assert missing in err, err
    ok, _ = strategist.parse_decision(_theorize())
    assert strategist.verify_decision(ok, conn, problem="p") == ""


def test_verify_theorize_allows_only_one_in_flight_per_group(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """One wall at a time (design 2). The predicate is the DB's own
    signal - a Theorize row of this group whose outcome is still NULL -
    not a count of anything the wake said."""
    from Tooling.state import groups as _groups
    top = _groups.ensure_top_group(conn, "p")
    d, _ = strategist.parse_decision(_theorize())
    assert strategist.verify_decision(
        d, conn, problem="p", group_id=top) == ""
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace, group_id=top)
    err = strategist.verify_decision(
        d, conn, problem="p", group_id=top)
    assert "in flight" in err, err
    # a sibling group is not blocked by it
    kid = _groups.open_group(conn, problem="p", parent_group_id=top,
                             charter="the sub-charter")
    assert strategist.verify_decision(
        d, conn, problem="p", group_id=kid) == ""
    # and once it settles, the group may ask again
    conn.execute("UPDATE strategist_decisions SET outcome = 'success'"
                 " WHERE decision_kind = 'Theorize'")
    conn.commit()
    assert strategist.verify_decision(
        d, conn, problem="p", group_id=top) == ""


def test_theorize_is_a_batch_delta_and_an_action_on_a_blocked_root(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Handing the wall to the theory layer IS the state change the
    anti-idle gates ask for: the stall gate counts it as a delta, and
    the blocked-root gate counts it as an action."""
    from Tooling.state import transitions as _t
    d, _ = strategist.parse_decision(_theorize())
    assert _t.predicted_batch_delta(conn, [d]) >= 1
    assert "Theorize" in db.BATCH_DECISION_KINDS


def test_commit_theorize_files_an_open_step_and_dispatches_a_theorist(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The row is an OPEN batch step - outcome NULL until the document
    comes back - and its executor is a Theorist pipeline on this group,
    the way an Inject's is a Formalizer on this problem."""
    from Tooling.state import groups as _groups
    top = _groups.ensure_top_group(conn, "p")
    d, _ = strategist.parse_decision(_theorize())
    out = strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace, group_id=top)
    assert out.batch_id is not None
    row = conn.execute(
        "SELECT decision_kind, group_id, outcome, batch_id, payload,"
        " produced_kind FROM strategist_decisions WHERE id = ?",
        (out.decision_row_id,)).fetchone()
    assert row["decision_kind"] == "Theorize"
    assert row["outcome"] is None
    assert row["batch_id"] == out.batch_id
    assert int(row["group_id"]) == top
    assert row["produced_kind"] == "document"
    payload = json.loads(row["payload"])
    assert payload["objective"] == _THEORIZE["objective"]
    assert payload["situation"] == _THEORIZE["situation"]
    q = conn.execute(
        "SELECT kind, target_id, target_kind, decision_id FROM queue"
        " WHERE kind = 'Theorist'").fetchone()
    assert q is not None
    assert (q["target_id"], q["target_kind"]) == (str(top), "Group")
    assert q["decision_id"] == out.decision_row_id


def test_an_open_theorize_is_in_flight_for_the_idle_gates(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """A Theorize produces no goal, no strategy and no group, so the
    three artifact arms cannot see it - and without an arm of its own
    the group would read as idle while the Theorist works, and T4 would
    wake it to invent something beside the question it just asked."""
    from Tooling.state import groups as _groups
    top = _groups.ensure_top_group(conn, "p")
    assert not db.has_active_inflight_inject(conn, "p", group_id=top)
    d, _ = strategist.parse_decision(_theorize())
    strategist.commit_decision(
        d, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace, group_id=top)
    assert db.has_active_inflight_inject(conn, "p", group_id=top)
    assert db.has_live_inflight_inject(conn, "p", group_id=top)
    conn.execute("UPDATE strategist_decisions SET outcome = 'success'"
                 " WHERE decision_kind = 'Theorize'")
    conn.commit()
    assert not db.has_active_inflight_inject(conn, "p", group_id=top)


def test_a_theorize_the_owner_filed_does_not_freeze_the_group(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The `_NOT_HUMAN_OPENED` rule, one kind further: a person's
    request runs BESIDE the group's line, not instead of it, so the
    group still owes its own next move."""
    from Tooling.state import groups as _groups
    from Tooling.pipeline.strategist import commit as _commit
    top = _groups.ensure_top_group(conn, "p")
    d, _ = strategist.parse_decision(_theorize())
    _commit.commit_decisions(
        [d], conn, problem="p", tick=0, trigger_kind="human",
        workspace=workspace, group_id=top, actor=_commit.ACTOR_HUMAN)
    assert not db.has_active_inflight_inject(conn, "p", group_id=top)
    assert not db.has_live_inflight_inject(conn, "p", group_id=top)
