"""AttemptDisproof is RETIRED (2026-08-04, user call).

One use all-time — its own acceptance test (Test.false_root, 07-08);
the real counterexample work always went through Forward mints (SLC's
orientability brick, origin='forward'). The bet-against-a-claim move is
expressed with the general machinery: Inject a mint of the precise
negation, `ReturnToParent(refuted)` naming the proved node, or
`RequestUserAmend` with the disproof. This file pins the retirement:
the kind parses (legacy rows keep their enum value) and the verifier
teaches the way out instead of committing anything.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.pipeline import strategist
from Tooling.state import db as _db


def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES"
        " ('Test.px', 'ts')")
    conn.commit()
    return conn


def test_attempt_disproof_is_retired(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ds, perr = strategist.parse_decisions(
        '[{"kind": "AttemptDisproof", "target_goal_id": 1,'
        ' "reason": "believed false"}]')
    assert not perr and ds, "kind must stay parseable (teaching path)"
    err = strategist.verify_decision(
        ds[0], conn, problem="Test.px", workspace=tmp_path)
    assert "retired" in err
    # The teaching message names the one road (2026-08-30): Inject the
    # node with the counterexample, the worker certifies the negation,
    # `<slug>_disproof` lands, then refuted / Ingest.
    assert "Inject" in err and "_disproof" in err and "ReturnToParent" in err


def test_attempt_disproof_gone_from_experiment_and_math_kinds() -> None:
    from Tooling.state import db
    assert "AttemptDisproof" not in db.BATCH_DECISION_KINDS
    # Parseable-but-rejected, exactly the EmitDirective pattern:
    assert "AttemptDisproof" in strategist.DECISION_KINDS
    # The turn whitelists retired with the wake split (2026-08-11);
    # what mattered here — the kind parses and is then rejected with a
    # teaching message rather than crashing — is above.


def test_prompts_carry_no_attempt_disproof() -> None:
    """The retired kind must not survive in any wake prompt or the
    judge's contract copy — a prompt offering a verb the verifier
    rejects is a round-trip trap."""
    root = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
    for rel in ("strategist/routine.md", "strategist/inject_batch_done.md",
                "adversary/_contract.md", "adversary/adversary.md"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "AttemptDisproof" not in text, rel
