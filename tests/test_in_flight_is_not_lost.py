"""Work that is still running must not read as work that vanished.

The batch scoreboard lists batches that have TERMINATED, so a batch
with a spawn still in flight appeared nowhere at all — and a reader
cannot tell "not finished" from "gone". Both readers of that section
paid: the Strategist re-dispatched what was already running, and the
judge spent a round rebuilding chronology by hand. It was the largest
cluster in the 08-12/13 feedback.

BOTH SIDES BY CONSTRUCTION. `_section_inject_batch_outcomes` is the
same function the Strategist's Context and the Adversary's PROGRAMME
projection render (`pipeline/adversary.py` calls it directly), so the
line lands in both. That is checked here rather than assumed — fixing
one side of this pair was how it stayed open.
"""
from __future__ import annotations

import sqlite3

from Tooling.agent import phase2_context


def _seed(conn: sqlite3.Connection, *, batch: str, outcome) -> None:
    from Tooling.state import db
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', NULL, 'do it', NULL,"
        "         '{}', ?, ?, ?, ?)",
        (batch, outcome, ts, ts))
    conn.commit()


def test_a_running_batch_is_named_as_running(conn: sqlite3.Connection):
    conn.execute(
        "INSERT INTO problems (name, created_at,"
        " bootstrap_done) VALUES ('p', ?, 1)",
        (__import__("Tooling.state.db", fromlist=["db"]).now(),))
    conn.commit()
    _seed(conn, batch="live-batch-1", outcome=None)

    text = "\n".join(
        phase2_context._section_inject_batch_outcomes(conn, "p"))

    assert "live-bat" in text, text
    assert "running" in text.lower(), text
    assert "do not re-dispatch" in text.lower() or "not listed" in text, text


def test_a_finished_batch_is_not_called_running(conn: sqlite3.Connection):
    conn.execute(
        "INSERT INTO problems (name, created_at,"
        " bootstrap_done) VALUES ('p', ?, 1)",
        (__import__("Tooling.state.db", fromlist=["db"]).now(),))
    conn.commit()
    _seed(conn, batch="done-batch-1", outcome="success")

    text = "\n".join(
        phase2_context._section_inject_batch_outcomes(conn, "p"))
    assert "done-bat" not in text or "running" not in text.lower(), text


def test_only_your_groups_running_batches_are_rostered(
        conn: sqlite3.Connection):
    """2026-08-18 context diet: a mature run inlined ~60 problem-wide
    in-flight batch ids (~1.6KB of hex, most of it other groups') —
    the actionable fact is "don't re-dispatch MINE"; other groups'
    work is a count. A group-less caller keeps the full roster."""
    from Tooling.state import db
    from Tooling.state import groups as groups_store
    ts = db.now()
    conn.execute(
        "INSERT INTO problems (name, created_at,"
        " bootstrap_done) VALUES ('p', ?, 1)", (ts,))
    top = groups_store.ensure_top_group(conn, "p")
    kid = groups_store.open_group(conn, problem="p", parent_group_id=top,
                                  charter="theirs")
    for batch, grp in (("mine-batch-1", top), ("their-batch-1", kid)):
        conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, group_id, target_id, brief,"
            " reason, payload, batch_id, outcome, created_at, updated_at)"
            " VALUES ('p', 0, 'routine', 'Inject', ?, NULL, 'do it', NULL,"
            "         '{}', ?, NULL, ?, ?)", (grp, batch, ts, ts))
    conn.commit()
    text = "\n".join(phase2_context._section_inject_batch_outcomes(
        conn, "p", group_id=top))
    assert "mine-bat" in text, text
    assert "their-ba" not in text, text
    assert "+1 other groups'" in text, text
    # No group in hand → the old problem-wide roster stands.
    bare = "\n".join(phase2_context._section_inject_batch_outcomes(
        conn, "p"))
    assert "mine-bat" in bare and "their-ba" in bare, bare


def test_a_running_batchs_substance_rides_the_lazy_companion(
        conn: sqlite3.Connection, tmp_path):
    """A bare hash was unactionable: checking one proposed Inject for
    duplication against "don't re-dispatch mine" took a four-source
    inference (46+2 self-reports). Owner ruling 2026-08-22: the lazy
    surface carries the FULL briefs (no truncation), the inline line
    carries existence + the pointer."""
    conn.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done)"
        " VALUES ('p', '2026-01-01', 1)")
    _seed(conn, batch="cafe1234beef", outcome=None)
    out = phase2_context._section_inject_batch_outcomes(
        conn, "p", attempts_dir=tmp_path)
    text = "\n".join(out)
    assert "cafe1234" in text
    assert "In flight" in text and "BATCHES.md" in text
    companion = (tmp_path / "BATCHES.md").read_text(encoding="utf-8")
    assert "## In flight — batch `cafe1234`" in companion
    assert "do it" in companion, "the full brief, untruncated"
    assert "mint (a new brick from the brief)" in companion
