"""The one road to a refutation (owner rulings 2026-08-30).

Before: `-- decline: disprove` certified the negation in the kernel and
flipped the goal to `disproved`, then THREW THE PROOF AWAY ("nothing
from the probe is ever committed") — so `ReturnToParent(refuted)`, which
demands "the PROVED node carrying the negation", had nothing gate-born
to point at, and the Strategist's only recourse was a hand-minted
`¬claim` brick with no kernel link to the claim (the fin10 lesson:
`Q ∩ D` vs `Q \\ S` — a refutation of a nearby statement is not a
refutation of the charter). And a disproved ROOT had no exit at all:
`Ingest` refused it.

Now: the certified negation lands as a proved brick `<slug>_disproof`;
`refuted` accepts only that gate-born brick; a disproved root closes the
problem as `refuted` through `Ingest`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, groups, transitions


PATCH = """import Mathlib

namespace Problems.Test.dp

-- decline: disprove
-- the claim is false: 1 ≠ 2
theorem s1 : ¬ (1 = 2) := by decide

end Problems.Test.dp
"""


def _conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at) VALUES ('Test.dp', 't')")
    c.commit()
    return c


def _goal(conn, slug, *, origin="backward", status="open", problem="Test.dp"):
    return db.insert_goal(conn, problem=problem, slug=slug,
                          lean_path=f"Problems/Test/dp/proofs/L_{slug}.lean",
                          statement="1 = 2", origin=origin, depth=1,
                          status=status)


# ─── 1. the certified negation lands as a proved brick ───────────────

def test_certified_negation_lands_as_a_proved_disproof_brick(tmp_path, monkeypatch):
    from Tooling.pipeline import _axiom, _disprove
    conn = _conn(tmp_path)
    (tmp_path / "Problems" / "Test" / "dp" / "proofs").mkdir(parents=True)
    attempts = tmp_path / "_a"
    attempts.mkdir()
    gid = _goal(conn, "one_eq_two")
    conn.commit()

    class _Ok:
        ok = True
        failure_reason = None
        detail = ""

    monkeypatch.setattr(_axiom, "axiom_gate", lambda *a, **k: _Ok())
    brick_id = _disprove.persist_disproof_brick(
        conn, workspace=tmp_path, attempts_dir=attempts, patch_text=PATCH,
        goal=db.get_goal(conn, gid), problem="Test.dp", claim_slug="s1",
        axiom_whitelist=[])
    brick = db.get_goal(conn, brick_id)
    assert brick["slug"] == "one_eq_two_disproof"
    assert brick["status"] == "proved" and brick["origin"] == "forward"
    text = (tmp_path / "Problems" / "Test" / "dp" / "proofs"
            / "L_one_eq_two_disproof.lean").read_text(encoding="utf-8")
    assert "theorem one_eq_two_disproof : ¬ (1 = 2)" in text
    assert "-- decline:" not in text, "the directive is not part of the brick"
    assert "absurd" not in text, "the probe bridge stays in the attempt dir"
    assert _disprove.disproof_brick_for(conn, gid) == brick_id
    # the pair is complete once the goal itself flips (the abort that
    # follows the landing does it in the pipeline)
    assert _disprove.refuted_goal_for(conn, brick_id) is None
    conn.execute("UPDATE goals SET status = 'disproved' WHERE id = ?", (gid,))
    assert _disprove.refuted_goal_for(conn, brick_id) == gid


# ─── 2. `refuted` accepts only the gate-born brick ───────────────────

def _S():
    from Tooling.pipeline import strategist as s
    return s


def _verify(conn, decision, problem, group_id):
    return _S().verify_decision(decision, conn, problem=problem,
                                group_id=group_id)


def test_refuted_accepts_only_the_gate_minted_disproof_brick(tmp_path):
    conn = _conn(tmp_path)
    p = "Test.dp"
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="claim A")
    conn.commit()
    S = _S()
    # a hand-minted proved brick is a brick, not a refutation
    hand = _goal(conn, "not_claim_a", origin="forward", status="proved")
    conn.commit()
    err = _verify(conn, S.Decision(kind="ReturnToParent", reason="r",
                                   target_id=hand,
                                   payload={"flavour": "refuted"}), p, sub)
    assert "disproof" in err and "gate" in err
    # the gate-born pair: <slug> disproved + <slug>_disproof proved
    claim = _goal(conn, "claim_a", status="disproved")
    brick = _goal(conn, "claim_a_disproof", origin="forward", status="proved")
    conn.commit()
    assert _verify(conn, S.Decision(kind="ReturnToParent", reason="r",
                                    target_id=brick,
                                    payload={"flavour": "refuted"}), p, sub) == ""


# ─── 3. a disproved root closes the problem as `refuted` ─────────────

def test_refuted_is_a_problem_terminal():
    assert "refuted" in transitions.PROBLEM_STATES
    assert ("active", "refuted") in transitions.PROBLEM_EDGES
    assert transitions.WAKE_LEGALITY["refuted"] == frozenset()


def test_fresh_schema_accepts_the_refuted_state(tmp_path):
    conn = _conn(tmp_path)
    conn.execute("UPDATE problems SET state = 'refuted' WHERE name = 'Test.dp'")
    assert conn.execute("SELECT state FROM problems").fetchone()[0] == "refuted"


def test_ingest_on_a_disproved_root_closes_the_problem_as_refuted(tmp_path):
    conn = _conn(tmp_path)
    p = "Test.dp"
    root = _goal(conn, "main", origin="root", status="disproved")
    brick = _goal(conn, "main_disproof", origin="forward", status="proved")
    proofs = tmp_path / "Problems" / "Test" / "dp" / "proofs"
    proofs.mkdir(parents=True)
    for g in (root, brick):  # the drift guard wants every row's file
        (tmp_path / db.get_goal(conn, g)["lean_path"]).write_text(
            "theorem x : True := trivial\n", encoding="utf-8")
    top = groups.ensure_top_group(conn, p)
    conn.commit()
    S = _S()
    err = S.verify_decisions([S.Decision(kind="Ingest")], conn, problem=p,
                             group_id=top, workspace=tmp_path)
    assert err == "", err
    S.commit_decisions([S.Decision(kind="Ingest")], conn, problem=p, tick=0,
                       trigger_kind="routine", workspace=tmp_path, group_id=top)
    row = conn.execute("SELECT state, ingested_at FROM problems WHERE name = ?",
                       (p,)).fetchone()
    assert row["state"] == "refuted"
    assert row["ingested_at"] is not None, "the terminal stamp the liveness reads"


# ─── 4. the Strategist is told the road ─────────────────────────────

def test_strategist_surfaces_name_the_disproof_road():
    root = Path(__file__).resolve().parents[1] / "Tooling" / "prompts" / "strategist"
    for name in ("inject_batch_done.md", "pending_review.md"):
        text = (root / name).read_text(encoding="utf-8")
        inject = text[text.index("- `Inject`"):text.index("- `ConfirmShelve`")]
        assert "_disproof" in inject and "disproved" in inject, name
        ingest = text[text.index("- `Ingest`"):]
        ingest = ingest[:ingest.index("\n")]
        assert "refuted" in ingest and "RequestUserAmend" not in ingest.split("only")[0], name
