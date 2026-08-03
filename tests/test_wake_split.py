"""RS-C (research_mission_design.md §3.2) — the Strategist wake split.

Turn A (admin, un-judged, fail-open) owns registry operations; Turn M
(math, adversary-judged) owns route and verdicts. The isolation IS the
contract diet: each turn sees only its own world, and the wake's clocks
belong to M alone.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling import agent
from Tooling.pipeline import strategist
from Tooling.state import db, manifest


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n## Statement\nT\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at,"
        " bootstrap_done) VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),))
    c.commit()
    return c


@pytest.fixture
def mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="T")


def _proved_forward(conn, slug="brick") -> int:
    g = db.insert_goal(
        conn, problem="p", slug=slug,
        lean_path=f"Problems/p/proofs/L_{slug}.lean", statement="T",
        origin="forward")
    db.update_goal_status(conn, g, "proved")
    conn.commit()
    return g


# ------------------------------------------------------- turn whitelists

def test_admin_turn_rejects_math_kinds(conn: sqlite3.Connection) -> None:
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Forward", "brief": "## Need\nx"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p", turn="admin")
    assert "MATH turn" in err


def test_math_turn_rejects_admin_kinds(conn: sqlite3.Connection) -> None:
    g = _proved_forward(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "MarkDeliverable", "target_goal_id": g, "reason": "r"},
    ]))
    err = strategist.verify_decisions(ds, conn, problem="p", turn="math")
    assert "ADMIN turn" in err
    ds2, _ = strategist.parse_decisions(json.dumps([
        {"kind": "FetchPaper", "query": "q", "reason": "r"},
    ]))
    err2 = strategist.verify_decisions(ds2, conn, problem="p", turn="math")
    assert "ADMIN turn" in err2


def test_both_turns_accept_the_shared_kinds(conn: sqlite3.Connection,
                                            workspace: Path) -> None:
    """RequestUserAmend and Noop are deliberately dual-homed: an amend
    can be discovered mathematically (kernel-checked negation in hand)
    or clerically (the file is malformed)."""
    for turn in ("admin", "math"):
        ds, _ = strategist.parse_decisions(json.dumps([
            {"kind": "Noop", "reason": "r"},
        ]))
        assert strategist.verify_decisions(
            ds, conn, problem="p", turn=turn) == "", turn


def test_legacy_callers_see_no_whitelist(conn: sqlite3.Connection) -> None:
    """turn=None (pre-split callers and tests) keeps the old contract."""
    g = _proved_forward(conn, "legacy")
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "MarkDeliverable", "target_goal_id": g, "reason": "r"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""


# --------------------------------------------- admin skips the M gates

def test_admin_turn_skips_review_discharge(conn: sqlite3.Connection) -> None:
    """A pending review is the MATH turn's burden — the admin batch must
    not be bounced for failing to discharge it (it structurally cannot:
    none of its kinds target goals under review)."""
    g = db.insert_goal(conn, problem="p", slug="rev",
                       lean_path="Problems/p/proofs/L_rev.lean",
                       statement="T", origin="backward")
    db.update_goal_status(conn, g, "pending_strategist_review")
    conn.commit()
    marked = _proved_forward(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "MarkDeliverable", "target_goal_id": marked,
         "reason": "top-level claim"},
    ]))
    err_admin = strategist.verify_decisions(
        ds, conn, problem="p", trigger_kind="inject_batch_done",
        turn="admin")
    assert err_admin == ""
    # ... while the math turn on the same trigger still faces the gate.
    ds_m, _ = strategist.parse_decisions(json.dumps([
        {"kind": "Inject", "pipeline": "Forward", "brief": "## Need\nx"},
    ]))
    err_math = strategist.verify_decisions(
        ds_m, conn, problem="p", trigger_kind="inject_batch_done",
        turn="math")
    assert "review not discharged" in err_math


# ------------------------------------------------- run_admin_turn stage

def _run_admin(conn, workspace, mfst, payload, monkeypatch,
               trigger="routine"):
    def fake_spawn(**kw):
        (kw["attempts_dir"] / "admin.json").write_text(
            json.dumps(payload), encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    attempts = workspace / ".attempts" / "wake1"
    attempts.mkdir(parents=True, exist_ok=True)
    return strategist.run_admin_turn(
        conn, problem="p", trigger_kind=trigger, tick=1,
        workspace=workspace, mfst=mfst, attempts_dir=attempts)


def test_admin_stage_commits_marks_without_touching_clocks(
    conn: sqlite3.Connection, workspace: Path, mfst: manifest.Manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wake's clocks belong to the MATH turn: an admin commit that
    advanced them would let a wake whose math half failed read as
    'strategist ran', starving the retry pressure."""
    g = _proved_forward(conn)
    out = _run_admin(conn, workspace, mfst,
                     [{"kind": "MarkDeliverable", "target_goal_id": g,
                       "reason": "top-level claim"}], monkeypatch)
    assert out is None
    row = conn.execute(
        "SELECT is_deliverable FROM goals WHERE id = ?", (g,)).fetchone()
    assert int(row["is_deliverable"]) == 1
    p = conn.execute(
        "SELECT last_strategist_at, last_routine_at FROM problems"
        " WHERE name='p'").fetchone()
    assert p["last_strategist_at"] is None
    assert p["last_routine_at"] is None


def test_admin_stage_is_fail_open_on_garbage(
    conn: sqlite3.Connection, workspace: Path, mfst: manifest.Manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken admin turn never blocks the mathematics."""
    def fake_spawn(**kw):
        (kw["attempts_dir"] / "admin.json").write_text(
            "not json at all", encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    attempts = workspace / ".attempts" / "wake2"
    attempts.mkdir(parents=True, exist_ok=True)
    out = strategist.run_admin_turn(
        conn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, mfst=mfst, attempts_dir=attempts)
    assert out is None  # math turn proceeds


def test_admin_amend_freezes_the_wake(
    conn: sqlite3.Connection, workspace: Path, mfst: manifest.Manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An amend committed by the admin turn ends the wake: the math turn
    must not plan against a statement under repair."""
    out = _run_admin(conn, workspace, mfst,
                     [{"kind": "RequestUserAmend", "file": "Manifest.md",
                       "reason": "the Statement section is empty",
                       "question": "what should the Statement say?",
                       "proposed_body": "## Statement\n<fill in>"}],
                     monkeypatch)
    assert out == "frozen"
    assert db.problem_has_awaiting_human(conn, "p")
