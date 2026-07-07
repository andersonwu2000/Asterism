"""Feature D — AttemptDisproof: mechanical negation of a believed-false
user-requested claim. Belief is never trusted: both directions need the
kernel. Covers verify cases, the negation surgery, the commit mint
(goal+file+linkage), the Ingest gate extension, and the consistency
alarm."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.pipeline.strategist import (
    Decision, _commit_attempt_disproof, _negation_statement,
    verify_decision,
)
from Tooling.state import db as _db


def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES"
        " ('Test.px', 'Problems/Test/px/Manifest.md', 'ts')")
    conn.commit()
    return conn


def _seed_claim(conn, tmp_path: Path, slug: str = "all_small",
                body: str | None = None, kind: str = "theorem",
                status: str = "open") -> int:
    pdir = tmp_path / "Problems" / "Test" / "px" / "proofs"
    pdir.mkdir(parents=True, exist_ok=True)
    f = pdir / f"L_{slug}.lean"
    f.write_text(body or (
        "import Mathlib\n\n"
        "namespace Problems.Test.px\n\n"
        f"theorem {slug} (n : ℕ) : ∃ m, m < n := by sorry\n\n"
        "end Problems.Test.px\n"), encoding="utf-8")
    return _db.insert_goal(
        conn, problem="Test.px", slug=slug,
        lean_path=f.relative_to(tmp_path).as_posix(),
        statement="∃ m, m < n", origin="forward", depth=0,
        kind=kind, status=status)


# ---------------------------------------------------------------------
# negation surgery
# ---------------------------------------------------------------------

def test_negation_statement_mechanical() -> None:
    text = ("import Mathlib\n"
            "-- prose mentioning theorem fake_name here\n"
            "theorem all_small (n : ℕ) (h : 0 < n) : ∃ m, m < n "
            ":= by sorry\n")
    neg = _negation_statement(text)
    assert neg == "¬ (∀ (n : ℕ) (h : 0 < n), ∃ m, m < n)"


def test_negation_statement_bare_conclusion() -> None:
    text = "theorem flat : 1 + 1 = 3 := by sorry\n"
    assert _negation_statement(text) == "¬ (1 + 1 = 3)"


def test_negation_statement_unextractable_returns_none() -> None:
    assert _negation_statement("-- nothing here\n") is None


# ---------------------------------------------------------------------
# verify_decision
# ---------------------------------------------------------------------

def test_verify_attempt_disproof_cases(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    gid = _seed_claim(conn, tmp_path)

    assert "requires target" in verify_decision(
        Decision(kind="AttemptDisproof"), conn, problem="Test.px")
    assert "reason" in verify_decision(
        Decision(kind="AttemptDisproof", target_id=gid),
        conn, problem="Test.px")
    ok = Decision(kind="AttemptDisproof", target_id=gid,
                  reason="fails at n=0")
    assert verify_decision(ok, conn, problem="Test.px") == ""
    # Prop-only: data kinds rejected.
    did = _seed_claim(conn, tmp_path, slug="some_def", kind="inductive")
    assert "meaningless" in verify_decision(
        Decision(kind="AttemptDisproof", target_id=did, reason="r"),
        conn, problem="Test.px")
    # Proved target rejected (contradiction hunting).
    pid = _seed_claim(conn, tmp_path, slug="proved_one", status="proved")
    assert "already proved" in verify_decision(
        Decision(kind="AttemptDisproof", target_id=pid, reason="r"),
        conn, problem="Test.px")
    conn.close()


# ---------------------------------------------------------------------
# commit: mint + linkage; in-flight dedup; Ingest gate; alarm
# ---------------------------------------------------------------------

def test_commit_mints_negation_goal_and_linkage(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    gid = _seed_claim(conn, tmp_path)
    d = Decision(kind="AttemptDisproof", target_id=gid,
                 reason="fails at n=0")
    out = _commit_attempt_disproof(
        d, conn, problem="Test.px", tick=1, trigger_kind="routine",
        workspace=tmp_path)
    row = conn.execute(
        "SELECT * FROM strategist_decisions WHERE id = ?",
        (out.decision_row_id,)).fetchone()
    assert int(row["target_id"]) == gid
    ng = _db.get_goal(conn, int(row["produced_goal_id"]))
    assert ng["slug"] == "not_all_small"
    assert ng["statement"].startswith("¬ (∀")
    assert ng["status"] == "open" and ng["origin"] == "forward"
    f = tmp_path / str(ng["lean_path"])
    text = f.read_text(encoding="utf-8")
    assert "import Mathlib" in text
    assert f"theorem not_all_small : {ng['statement']} := by sorry" in text
    # Second AttemptDisproof on the same target while in flight → verify
    # rejects (outcome still NULL).
    assert "in flight" in verify_decision(
        Decision(kind="AttemptDisproof", target_id=gid, reason="r"),
        conn, problem="Test.px")
    conn.close()


def _mk_deliverable(conn, tmp_path: Path) -> int:
    gid = _seed_claim(conn, tmp_path, slug="wanted", status="proved")
    _db.mark_deliverable(conn, gid)
    return gid


def test_ingest_gate_blocks_on_proved_negation(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    # A proved+marked deliverable satisfies the base Ingest requirement.
    _mk_deliverable(conn, tmp_path)
    target = _seed_claim(conn, tmp_path, slug="false_claim")
    d = Decision(kind="AttemptDisproof", target_id=target,
                 reason="fails at n=0")
    out = _commit_attempt_disproof(
        d, conn, problem="Test.px", tick=1, trigger_kind="routine",
        workspace=tmp_path)
    neg_id = int(conn.execute(
        "SELECT produced_goal_id FROM strategist_decisions WHERE id=?",
        (out.decision_row_id,)).fetchone()[0])
    # Before the negation proves: Ingest passes the D gate.
    assert verify_decision(Decision(kind="Ingest"), conn,
                           problem="Test.px") == ""
    # Negation proves while the target is still pursued → blocked.
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (neg_id,))
    conn.commit()
    err = verify_decision(Decision(kind="Ingest"), conn, problem="Test.px")
    assert "negation of" in err and "RequestUserAmend" in err
    # Target retired (user amended / negation adopted) → released.
    conn.execute("UPDATE goals SET status='shelved' WHERE id=?", (target,))
    conn.commit()
    assert verify_decision(Decision(kind="Ingest"), conn,
                           problem="Test.px") == ""
    # Both proved → consistency alarm, unconditionally blocked.
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (target,))
    conn.commit()
    err = verify_decision(Decision(kind="Ingest"), conn, problem="Test.px")
    assert "consistency alarm" in err
    conn.close()


def test_disproof_guidance_section_gating(tmp_path: Path) -> None:
    from Tooling.agent.phase2_context import _section_disproof_guidance
    conn = _conn(tmp_path)
    assert _section_disproof_guidance(conn, "Test.px") == []
    target = _seed_claim(conn, tmp_path, slug="false_claim")
    d = Decision(kind="AttemptDisproof", target_id=target,
                 reason="fails at n=0")
    out = _commit_attempt_disproof(
        d, conn, problem="Test.px", tick=1, trigger_kind="routine",
        workspace=tmp_path)
    joined = "\n".join(_section_disproof_guidance(conn, "Test.px"))
    assert "Falsity triage" in joined and "AttemptDisproof" in joined
    assert "SETTLED FALSE" not in joined
    neg_id = int(conn.execute(
        "SELECT produced_goal_id FROM strategist_decisions WHERE id=?",
        (out.decision_row_id,)).fetchone()[0])
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (neg_id,))
    conn.commit()
    joined = "\n".join(_section_disproof_guidance(conn, "Test.px"))
    assert "SETTLED FALSE" in joined and "not_false_claim" in joined
    conn.close()
