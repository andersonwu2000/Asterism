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


def test_ingest_gate_blocks_on_db_file_drift(tmp_path: Path) -> None:
    """`proof_store.inventory` is the DB↔file oracle, and until
    2026-07-30 its only caller was the operator typing `asterism
    drift-check` — so nothing asked it across a 13-hour unattended run.
    Ingest is the moment it matters (this publishes the snapshot) and,
    unlike the per-spawn audit, a place where the question is answerable:
    the oracle only needs the tree to agree with the DB, not to know who
    wrote a file.

    Passing `workspace` is what arms it; the gate stays quiet without one
    so callers that have no tree to inspect are unaffected."""
    conn = _conn(tmp_path)
    gid = _mk_deliverable(conn, tmp_path)
    # The seed helper writes a `sorry` body under a `proved` row — which
    # the oracle rightly calls a silent fake proof. Make the baseline
    # honest first, or the test proves nothing about orphans.
    proved = tmp_path / str(_db.get_goal(conn, gid)["lean_path"])
    proved.write_text("theorem wanted : True := trivial\n", encoding="utf-8")
    assert verify_decision(Decision(kind="Ingest"), conn,
                           problem="Test.px", workspace=tmp_path) == ""

    # A proof file with no DB row — a placement that crashed before its
    # commit, or something that never went through the chokepoint.
    orphan = proved.parent / "L_ghost.lean"
    orphan.write_text("theorem ghost : True := trivial\n", encoding="utf-8")

    err = verify_decision(Decision(kind="Ingest"), conn,
                          problem="Test.px", workspace=tmp_path)
    assert "Ingest blocked" in err and "orphan" in err
    assert "drift-check" in err
    # Without a workspace there is nothing to inspect — unchanged.
    assert verify_decision(Decision(kind="Ingest"), conn,
                           problem="Test.px") == ""
    conn.close()


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
    # Target retired but no user round-trip yet → still blocked
    # (decision-pure 返回用戶 enforcement).
    conn.execute("UPDATE goals SET status='shelved' WHERE id=?", (target,))
    conn.commit()
    err = verify_decision(Decision(kind="Ingest"), conn, problem="Test.px")
    assert "handed back" in err
    # A RequestUserAmend resolved AFTER the disproof decision releases it.
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at) VALUES ('Test.px', 0, 'routine',"
        " 'RequestUserAmend', '{}', 'accepted', 'ts', 'ts')")
    conn.commit()
    assert verify_decision(Decision(kind="Ingest"), conn,
                           problem="Test.px") == ""
    # Both proved → consistency alarm, unconditionally blocked.
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (target,))
    conn.commit()
    err = verify_decision(Decision(kind="Ingest"), conn, problem="Test.px")
    assert "consistency alarm" in err
    conn.close()


def test_amend_accepts_root_lean_and_syncs_statement(
        tmp_path: Path) -> None:
    """Livelock fix (2026-07-08): a FALSE root claim is amendable —
    Root.lean joins the amend whitelist; accept syncs goals.statement
    and refreezes the root (old proof state is moot for the new claim)."""
    import json
    from Tooling.state import amend as _amend
    conn = _conn(tmp_path)
    pdir = tmp_path / "Problems" / "Test" / "px"
    pdir.mkdir(parents=True, exist_ok=True)
    old_root = ("import Mathlib\n\nnamespace Problems.Test.px\n\n"
                "theorem main : ∀ n : ℕ, n < 0 := by sorry\n\n"
                "end Problems.Test.px\n")
    (pdir / "Root.lean").write_text(old_root, encoding="utf-8")
    rid = _db.insert_goal(
        conn, problem="Test.px", slug="main",
        lean_path="Problems/Test/px/Root.lean",
        statement="∀ n : ℕ, n < 0", origin="root", depth=0,
        status="shelved")
    conn.execute("UPDATE goals SET attempts = 4 WHERE id = ?", (rid,))
    new_root = old_root.replace("n < 0", "0 ≤ n")
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at) VALUES ('Test.px', 0, 'routine',"
        " 'RequestUserAmend', ?, 'awaiting_human', 'ts', 'ts')",
        (json.dumps({"file": "Root.lean", "proposed_body": new_root}),))
    conn.commit()
    out = _amend.resolve_amend(conn, tmp_path, int(cur.lastrowid),
                               action="accept")
    assert out["file"] == "Root.lean"
    g = _db.get_goal(conn, rid)
    assert g["statement"] == "∀ n : ℕ, 0 ≤ n"
    assert g["status"] == "frozen" and g["attempts"] == 0
    assert "0 ≤ n" in (pdir / "Root.lean").read_text(encoding="utf-8")
    # Task #120 class sweep: the accepted amendment IS the sanctioned
    # user-file change — the baseline pin moves with it (source='repin'),
    # so root_integrity_gate accepts the amended file after the re-prove.
    pin = conn.execute(
        "SELECT body, source FROM user_file_history"
        " WHERE problem='Test.px' AND file='Root.lean'"
        " ORDER BY id DESC LIMIT 1").fetchone()
    assert pin is not None and pin["source"] == "repin"
    assert "0 ≤ n" in pin["body"]
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
