"""Tests for Tooling/strategist/demux.py (P7 C50)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.strategist.demux import apply_decisions


_NOW = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    conn = connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


def _insert_goal(
    conn: sqlite3.Connection,
    *,
    problem: str = "p",
    slug: str = "g",
    status: str = "open",
    commit_state: str = "live",
    blocked_pipelines: list[str] | None = None,
) -> int:
    blocked_json = json.dumps(blocked_pipelines) if blocked_pipelines else None
    cur = conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, commit_state, "
        "blocked_pipelines, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (problem, slug, f"Problems/{problem}/{slug}.lean",
         "root", "theorem", status, commit_state, blocked_json,
         _NOW.isoformat(), _NOW.isoformat()),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Inject path
# ---------------------------------------------------------------------------

class TestInject:
    def test_backward_inject_enqueues_with_high_priority(self, db):
        gid = _insert_goal(db, problem="p", slug="g")
        result = apply_decisions(
            db, "p",
            [{"kind": "Backward", "target": gid, "reason": "test"}],
        )
        assert len(result.enqueued) == 1
        assert result.enqueued[0]["kind"] == "Backward"
        assert result.enqueued[0]["target_id"] == gid

        rows = db.execute(
            "SELECT kind, target_id, priority FROM queue"
        ).fetchall()
        assert rows == [("Backward", str(gid), 10)]

    def test_payload_overrides_propagated(self, db):
        gid = _insert_goal(db, problem="p", slug="g")
        decisions = [{
            "kind": "Backward",
            "target": gid,
            "reason": "boost reasoning",
            "model": "opus",
            "budget": {"wall_clock_sec": 28800},
        }]
        result = apply_decisions(db, "p", decisions)
        payload = result.enqueued[0]["payload"]
        assert payload["model"] == "opus"
        assert payload["budget"] == {"wall_clock_sec": 28800}

        # Verify the row in queue.payload is JSON-encoded.
        row = db.execute("SELECT payload FROM queue").fetchone()
        assert json.loads(row[0]) == payload

    def test_no_overrides_writes_null_payload(self, db):
        gid = _insert_goal(db, problem="p", slug="g")
        apply_decisions(
            db, "p",
            [{"kind": "Refuter", "target": gid, "reason": "negate it"}],
        )
        row = db.execute("SELECT payload FROM queue").fetchone()
        assert row[0] is None

    def test_provider_filter_rejects_unknown(self, db):
        gid = _insert_goal(db, problem="p", slug="g")
        decisions = [{
            "kind": "Backward", "target": gid, "reason": "...",
            "provider": "gemini",
        }]
        result = apply_decisions(
            db, "p", decisions, allowed_providers=["claude"],
        )
        assert result.enqueued == []
        assert len(result.rejected) == 1
        assert "gemini" in result.rejected[0]["reason"]

    def test_provider_in_allowed_list_passes(self, db):
        gid = _insert_goal(db, problem="p", slug="g")
        decisions = [{
            "kind": "Backward", "target": gid, "reason": "...",
            "provider": "claude",
        }]
        result = apply_decisions(
            db, "p", decisions, allowed_providers=["claude", "gemini"],
        )
        assert len(result.enqueued) == 1


# ---------------------------------------------------------------------------
# Shelve path
# ---------------------------------------------------------------------------

class TestShelve:
    def test_shelve_updates_goal_status(self, db):
        gid = _insert_goal(db, problem="p", slug="g", status="open")
        result = apply_decisions(
            db, "p", [{"kind": "Shelve", "target": gid, "reason": "stuck"}],
        )
        assert result.shelved == [gid]
        assert result.enqueued == []
        row = db.execute(
            "SELECT status, status_changed_at FROM goals WHERE id = ?",
            (gid,),
        ).fetchone()
        assert row[0] == "shelved"
        assert row[1] is not None  # touched

    def test_shelve_does_not_enqueue(self, db):
        gid = _insert_goal(db, problem="p", slug="g")
        apply_decisions(
            db, "p", [{"kind": "Shelve", "target": gid, "reason": "stuck"}],
        )
        rows = db.execute("SELECT COUNT(*) FROM queue").fetchone()
        assert rows[0] == 0

    def test_shelve_cancels_running_pipelines(self, db):
        gid = _insert_goal(db, problem="p", slug="g")
        # Pre-seed a running Backward + a queued Builder for this Goal.
        db.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, "
            "started_at) VALUES "
            "('pipe-1', 'Backward', 'atomic', ?, 'Goal', 'running', ?)",
            (str(gid), "2026-04-29T12:00:00+00:00"),
        )
        db.execute(
            "INSERT INTO queue (kind, target_id, priority, created_at) "
            "VALUES ('Builder', ?, 0, ?)",
            (str(gid), "2026-04-29T12:00:00+00:00"),
        )
        db.commit()
        apply_decisions(
            db, "p", [{"kind": "Shelve", "target": gid, "reason": "..."}],
        )
        pipe = db.execute(
            "SELECT status, outcome FROM pipelines WHERE id = 'pipe-1'"
        ).fetchone()
        assert pipe == ("failed", "cancelled")
        q_count = db.execute(
            "SELECT COUNT(*) FROM queue WHERE target_id = ?", (str(gid),),
        ).fetchone()
        assert q_count[0] == 0


# ---------------------------------------------------------------------------
# Filter / reject paths
# ---------------------------------------------------------------------------

class TestRejection:
    def test_unknown_goal_rejected(self, db):
        result = apply_decisions(
            db, "p", [{"kind": "Backward", "target": 999, "reason": "..."}],
        )
        assert result.enqueued == []
        assert len(result.rejected) == 1
        assert "not found" in result.rejected[0]["reason"]

    def test_cross_problem_rejected(self, db):
        gid = _insert_goal(db, problem="other", slug="g")
        result = apply_decisions(
            db, "p", [{"kind": "Backward", "target": gid, "reason": "..."}],
        )
        assert result.enqueued == []
        assert "other" in result.rejected[0]["reason"]

    def test_pending_commit_state_rejected(self, db):
        gid = _insert_goal(db, problem="p", slug="g", commit_state="pending")
        result = apply_decisions(
            db, "p", [{"kind": "Backward", "target": gid, "reason": "..."}],
        )
        assert result.enqueued == []
        assert "commit_state" in result.rejected[0]["reason"]

    def test_blocked_pipelines_corrupt_json_rejects_decision(self, db):
        """R3 regression (audit_c49_c50_c51.md M4): _decode_blocked used to
        silently return [] on JSON parse failure → blocked_pipelines filter
        bypassed → silent failure red line. Now the decision is rejected
        with a corruption-tagged reason."""
        gid = _insert_goal(db, problem="p", slug="g")
        # Manually corrupt blocked_pipelines column.
        db.execute(
            "UPDATE goals SET blocked_pipelines = ? WHERE id = ?",
            ("{not json", gid),
        )
        db.commit()
        result = apply_decisions(
            db, "p", [{"kind": "Backward", "target": gid, "reason": "..."}],
        )
        assert result.enqueued == []
        assert len(result.rejected) == 1
        assert "JSON corrupt" in result.rejected[0]["reason"]

    def test_blocked_pipeline_rejected(self, db):
        gid = _insert_goal(
            db, problem="p", slug="g",
            blocked_pipelines=["Backward"],
        )
        result = apply_decisions(
            db, "p", [{"kind": "Backward", "target": gid, "reason": "..."}],
        )
        assert result.enqueued == []
        assert "blocked_pipelines" in result.rejected[0]["reason"]
        # But a different kind on the same Goal still passes.
        result2 = apply_decisions(
            db, "p", [{"kind": "Refuter", "target": gid, "reason": "..."}],
        )
        assert len(result2.enqueued) == 1

    def test_unknown_kind_rejected(self, db):
        gid = _insert_goal(db, problem="p", slug="g")
        result = apply_decisions(
            db, "p", [{"kind": "Bogus", "target": gid, "reason": "..."}],
        )
        assert result.enqueued == []
        assert "unknown decision kind" in result.rejected[0]["reason"]

    def test_non_int_target_rejected(self, db):
        result = apply_decisions(
            db, "p", [{"kind": "Backward", "target": "G_42", "reason": "..."}],
        )
        assert result.enqueued == []
        assert "integer Goal id" in result.rejected[0]["reason"]


# ---------------------------------------------------------------------------
# Mixed
# ---------------------------------------------------------------------------

class TestMixed:
    def test_partial_acceptance(self, db):
        g1 = _insert_goal(db, problem="p", slug="g1")
        g2 = _insert_goal(db, problem="p", slug="g2",
                          blocked_pipelines=["Backward"])
        result = apply_decisions(
            db, "p",
            [
                {"kind": "Backward", "target": g1, "reason": "..."},
                {"kind": "Backward", "target": g2, "reason": "..."},  # blocked
                {"kind": "Shelve",   "target": g2, "reason": "..."},
                {"kind": "Backward", "target": 999, "reason": "..."},  # unknown
            ],
        )
        assert len(result.enqueued) == 1
        assert result.enqueued[0]["target_id"] == g1
        assert result.shelved == [g2]
        assert len(result.rejected) == 2
