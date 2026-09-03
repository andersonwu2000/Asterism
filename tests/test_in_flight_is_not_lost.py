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

…AND WORK THAT IS PARKED MUST NOT READ AS WORK THAT IS RUNNING (SP7,
2026-09-03). `outcome IS NULL` was the whole definition of "in flight",
and a `shelved` goal deliberately leaves its step's outcome NULL
forever (P13 4284, 2026-06-15) — so both batches SP7 listed as running
were phantoms with zero live pipelines, and the Strategist re-parked
g10712 twice citing "exact batch e9cbf9d9 remains in flight".
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


# ---------------------------------------------------------------------
# Parked is not running (SP7 2026-09-03)
# ---------------------------------------------------------------------

def _problem(conn: sqlite3.Connection) -> None:
    from Tooling.state import db
    conn.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done)"
        " VALUES ('p', ?, 1)", (db.now(),))
    conn.commit()


def _goal(conn: sqlite3.Connection, slug: str, status: str) -> int:
    from Tooling.state import db
    return db.insert_goal(
        conn, problem="p", slug=slug, lean_path=f"proofs/L_{slug}.lean",
        statement="T", origin="forward", status=status)


def _seed_produced(conn: sqlite3.Connection, *, batch: str,
                   goal_id: int) -> None:
    """A step whose worker already registered its product — the shape
    `outcome IS NULL` cannot classify on its own."""
    from Tooling.state import db
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, produced_goal_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', NULL, 'do it', NULL,"
        "         '{}', ?, ?, NULL, ?, ?)", (batch, goal_id, ts, ts))
    conn.commit()


def _running_pipeline(conn: sqlite3.Connection, goal_id: int) -> None:
    from Tooling.state import db
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('pid-live', 'Backward', ?, 'Goal', 'running', NULL,"
        "         ?, NULL)", (str(goal_id), db.now()))
    conn.commit()


def test_a_parked_step_is_not_called_running(conn: sqlite3.Connection):
    """SP7: batch e9cbf9d9 → g10712, goal shelved, zero pipelines. It
    rendered as `Still running … do not re-dispatch them`, so the
    Strategist re-parked the goal citing its own phantom."""
    _problem(conn)
    g = _goal(conn, "parked_brick", "shelved")
    _seed_produced(conn, batch="parked-batch-1", goal_id=g)

    text = "\n".join(
        phase2_context._section_inject_batch_outcomes(conn, "p"))

    assert "still running" not in text.lower(), text
    assert "do not re-dispatch" not in text.lower(), text
    assert "parked" in text.lower(), text
    assert f"g{g}" in text and "shelved" in text, text


def test_a_live_worker_over_an_attempting_goal_stays_running(
        conn: sqlite3.Connection):
    """The other direction, so the fix cannot be "call everything
    parked": a produced goal with an unfinished `pipelines` row is a
    worker that really is computing, and re-dispatching it duplicates
    the spawn."""
    _problem(conn)
    g = _goal(conn, "live_brick", "attempting")
    _seed_produced(conn, batch="live-batch-2", goal_id=g)
    _running_pipeline(conn, g)

    text = "\n".join(
        phase2_context._section_inject_batch_outcomes(conn, "p"))

    assert "live-bat" in text, text
    assert "running" in text.lower(), text
    assert "do not re-dispatch" in text.lower(), text


def test_the_companion_files_parked_steps_apart_from_in_flight(
        conn: sqlite3.Connection, tmp_path):
    """`BATCHES.md`'s `## In flight` sections carry the full briefs of
    what is running; a parked step's brief in that section says the
    same false thing at greater length."""
    _problem(conn)
    live = _goal(conn, "live_brick", "attempting")
    dead = _goal(conn, "parked_brick", "shelved")
    _seed_produced(conn, batch="cafe1234beef", goal_id=live)
    _running_pipeline(conn, live)
    _seed_produced(conn, batch="dead5678beef", goal_id=dead)

    phase2_context._section_inject_batch_outcomes(
        conn, "p", attempts_dir=tmp_path)
    companion = (tmp_path / "BATCHES.md").read_text(encoding="utf-8")

    assert "## In flight — batch `cafe1234`" in companion, companion
    assert "## In flight — batch `dead5678`" not in companion, companion
    assert "Parked" in companion and "dead5678" in companion, companion


# ---------------------------------------------------------------------
# …AND WORK THE OWNER OPENED IS NOT THE PARENT'S WORK (owner ruling
# 2026-09-03)
# ---------------------------------------------------------------------

def _owner_delegate_step(conn: sqlite3.Connection, *, batch: str,
                         parent: int, kid: int) -> None:
    """What `state/commands.py` writes: a `Delegate` row filed under the
    parent group, produced group active, `actor='human'`."""
    from Tooling.state import db
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, brief, reason, payload,"
        " batch_id, produced_group_id, produced_kind, outcome, actor,"
        " created_at, updated_at)"
        " VALUES ('p', 0, 'human', 'Delegate', ?, 'settle it', NULL, '{}',"
        "         ?, ?, 'group', NULL, 'human', ?, ?)",
        (parent, batch, kid, ts, ts))
    conn.commit()


def test_an_owner_opened_group_is_not_the_parents_running_work(
        conn: sqlite3.Connection):
    """It runs — but not on the parent's line, so "do not re-dispatch"
    is the wrong instruction and the parent must not read it as a reason
    to wait. Its own line says what it is (union_closed group 691/693,
    2026-09-03)."""
    from Tooling.state import groups as groups_store
    _problem(conn)
    top = groups_store.ensure_top_group(conn, "p")
    kid = groups_store.open_group(conn, problem="p", parent_group_id=top,
                                  charter="owner's")
    _owner_delegate_step(conn, batch="owner123beef", parent=top, kid=kid)

    text = "\n".join(phase2_context._section_inject_batch_outcomes(
        conn, "p", group_id=top))

    assert "do not re-dispatch" not in text.lower(), text
    assert "still running" not in text.lower(), text
    assert "other groups" not in text.lower(), text
    assert f"Group {kid} was opened by the owner" in text, text
    assert "independently of your line" in text, text
    assert "Do not wait for it" in text, text


def test_the_companion_files_an_owner_opened_group_apart_from_in_flight(
        conn: sqlite3.Connection, tmp_path):
    """`## In flight` is the roster of the reader's OWN dispatched work;
    a group the owner opened belongs beside it, not in it."""
    from Tooling.state import groups as groups_store
    _problem(conn)
    top = groups_store.ensure_top_group(conn, "p")
    kid = groups_store.open_group(conn, problem="p", parent_group_id=top,
                                  charter="owner's")
    _owner_delegate_step(conn, batch="owner123beef", parent=top, kid=kid)

    phase2_context._section_inject_batch_outcomes(
        conn, "p", group_id=top, attempts_dir=tmp_path)
    companion = (tmp_path / "BATCHES.md").read_text(encoding="utf-8")

    assert "## In flight — batch `owner123`" not in companion, companion
    assert "## Opened by the owner — batch `owner123`" in companion, companion
