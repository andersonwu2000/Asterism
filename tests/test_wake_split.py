"""The Strategist wake split is RETIRED (2026-08-11). This file is what
keeps it retired.

It ran from 2026-08-03: Turn A (admin, un-judged, fail-open) owned
registry operations, Turn M (math, adversary-judged) owned route and
verdicts, and the isolation was billed as a contract diet — each turn
sees only its own world.

Two things ended it.

The exit condition was split across the turns. `Ingest` was a math kind
and `MarkDeliverable` — its precondition — was an admin kind, so "mark
the last brick, then Ingest" could not happen in one wake. Turn A
running FIRST concealed that: the marks a wake saw were the previous
wake's, so the ordering was load-bearing for a defect the split had
introduced.

And it was offloading less than it cost: across the union_closed run's
43 batches, Turn A produced 18 MarkDeliverable + 4 Noop + 0
RequestUserAmend, at one spawn and one Context per wake. The isolation
argument did not survive its own prompt either — admin.md said "Mark
only top-level claims the Manifest asks for" and "Do not reason about
the mathematics", and which claims are the deliverable IS a
mathematical judgement.
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
    (pdir / "proofs").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, created_at,"
        " bootstrap_done) VALUES ('p', ?, 1)",
        (db.now(),))
    c.commit()
    return c


def _proved_forward(conn, slug="brick") -> int:
    g = db.insert_goal(
        conn, problem="p", slug=slug,
        lean_path=f"Problems/p/proofs/L_{slug}.lean", statement="T",
        origin="forward")
    db.update_goal_status(conn, g, "proved")
    conn.commit()
    return g


def test_the_wake_has_no_second_turn(conn: sqlite3.Connection) -> None:
    """No admin stage, no turn whitelists, no per-turn knob. Named here
    so a reintroduction has to argue with this file rather than land
    quietly beside it."""
    for gone in ("run_admin_turn", "ADMIN_TURN_KINDS", "MATH_TURN_KINDS",
                 "_turn_whitelist_error"):
        assert not hasattr(strategist, gone), gone
    from Tooling.agent import phase2_context
    assert not hasattr(phase2_context, "compile_admin_context")
    from Tooling.core import config
    assert "strategist.admin_timeout_sec" not in config.CONFIG_SPEC
    from Tooling.pipeline import PROMPT_DIR
    assert not (PROMPT_DIR / "strategist" / "admin.md").exists()


def test_one_turn_takes_both_registry_and_route_kinds(
    conn: sqlite3.Connection,
) -> None:
    """The split's whole content was that these two could not appear in
    the same batch. `Ingest`'s precondition and `Ingest` now can."""
    g = _proved_forward(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "MarkDeliverable", "target_goal_id": g, "reason": "r"},
        {"kind": "Inject", "pipeline": "Forward", "proof": "Theorem. ## Need\nx\nProof. as argued."},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""


def test_a_mark_only_batch_needs_no_programme_revision(
    conn: sqlite3.Connection,
) -> None:
    """Marking records that work already dispatched, already argued and
    already kernel-checked is the deliverable. Requiring a fresh
    revision to say so would be friction the un-judged admin turn never
    charged — so `MarkDeliverable` is package-exempt, while a mark that
    rides a route-moving batch is gated with it."""
    assert not strategist.package_gate_applies(
        [strategist.Decision(kind="MarkDeliverable", target_id="1")],
        "routine")


def test_the_wakes_clocks_advance_on_the_one_commit(
    conn: sqlite3.Connection, workspace: Path,
) -> None:
    """`touch_clocks=False` existed so an admin commit could not let a
    wake whose math half failed read as "strategist ran", starving the
    retry pressure. With one turn there is no half to fail separately,
    and the flag went with the split — the clocks advance here, once."""
    g = _proved_forward(conn)
    ds, _ = strategist.parse_decisions(json.dumps([
        {"kind": "MarkDeliverable", "target_goal_id": g,
         "reason": "top-level claim"},
    ]))
    assert strategist.verify_decisions(ds, conn, problem="p") == ""
    strategist.commit_decisions(
        ds, conn, problem="p", tick=1, trigger_kind="routine",
        workspace=workspace)
    row = conn.execute(
        "SELECT is_deliverable FROM goals WHERE id = ?", (g,)).fetchone()
    assert int(row["is_deliverable"]) == 1
    p = conn.execute(
        "SELECT last_strategist_at, last_routine_at FROM problems"
        " WHERE name='p'").fetchone()
    assert p["last_strategist_at"] is not None
    assert p["last_routine_at"] is not None
