"""P6 C44 scheduler integration tests:
- _pop_queue skips Problems in self._paused_problems
- _handle_control_signal accepts (problem_pause, problem) tuple
- _poll_db_control_signals forwards problem_pause/resume payloads
- bypass_startup_check clears existing schedulers rows on register
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from Tooling.db.connect import init_schema
from Tooling.scheduler import FatalError, Reactor, ReactorConfig


_NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    yield conn
    conn.close()


def _make_reactor(
    db: sqlite3.Connection,
    tmp_path: Path,
    *,
    bypass: bool = False,
) -> Reactor:
    reactor = Reactor(
        str(tmp_path / "test.db"),
        ReactorConfig(base_dir=str(tmp_path), bypass_startup_check=bypass),
    )
    reactor.conn = db
    return reactor


def _seed_goal(conn: sqlite3.Connection, problem: str, slug: str) -> int:
    with conn:
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, "
            "commit_state, created_at, updated_at) "
            "VALUES (?, ?, ?, 'root', 'theorem', 'open', 'live', ?, ?)",
            (problem, slug, f"path/{slug}.lean", _NOW, _NOW),
        )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed_strategy(conn: sqlite3.Connection, goal_id: int) -> int:
    with conn:
        conn.execute(
            "INSERT INTO strategies "
            "(goal_id, lean_path, status, commit_state, created_at) "
            "VALUES (?, ?, 'proposed', 'live', ?)",
            (goal_id, f"path/strat_g{goal_id}.lean", _NOW),
        )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _enqueue(
    conn: sqlite3.Connection,
    kind: str,
    target_id: str,
    priority: int = 0,
) -> int:
    with conn:
        conn.execute(
            "INSERT INTO queue (kind, target_id, priority, created_at) "
            "VALUES (?, ?, ?, ?)",
            (kind, target_id, priority, _NOW),
        )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ---------------------------------------------------------------------------
# _pop_queue paused-Problem filter
# ---------------------------------------------------------------------------


class TestPopQueuePausedProblems:
    def test_skip_paused_backward(self, db, tmp_path):
        gid_paused = _seed_goal(db, "alpha", "g_paused")
        gid_active = _seed_goal(db, "beta", "g_active")
        _enqueue(db, "Backward", str(gid_paused))
        _enqueue(db, "Backward", str(gid_active))

        reactor = _make_reactor(db, tmp_path)
        reactor._paused_problems.add("alpha")

        task = reactor._pop_queue()
        assert task is not None
        assert task["target_id"] == str(gid_active)

    def test_skip_paused_builder(self, db, tmp_path):
        gid = _seed_goal(db, "alpha", "g")
        sid = _seed_strategy(db, gid)
        _enqueue(db, "Builder", str(sid))

        reactor = _make_reactor(db, tmp_path)
        reactor._paused_problems.add("alpha")

        task = reactor._pop_queue()
        assert task is None  # the only queued task belongs to paused alpha

    def test_unpaused_default_path(self, db, tmp_path):
        gid = _seed_goal(db, "alpha", "g")
        _enqueue(db, "Backward", str(gid))
        reactor = _make_reactor(db, tmp_path)
        # No paused — fast path
        task = reactor._pop_queue()
        assert task is not None
        assert task["target_id"] == str(gid)
        assert db.execute("SELECT COUNT(*) FROM queue").fetchone()[0] == 0

    def test_paused_task_stays_in_queue(self, db, tmp_path):
        gid = _seed_goal(db, "alpha", "g")
        _enqueue(db, "Backward", str(gid))
        reactor = _make_reactor(db, tmp_path)
        reactor._paused_problems.add("alpha")

        reactor._pop_queue()
        # Paused row stays — operator resumes later and it gets picked up
        assert db.execute("SELECT COUNT(*) FROM queue").fetchone()[0] == 1

    def test_resume_re_enables_pop(self, db, tmp_path):
        gid = _seed_goal(db, "alpha", "g")
        _enqueue(db, "Backward", str(gid))
        reactor = _make_reactor(db, tmp_path)
        reactor._paused_problems.add("alpha")
        assert reactor._pop_queue() is None
        reactor._paused_problems.discard("alpha")
        task = reactor._pop_queue()
        assert task is not None


# ---------------------------------------------------------------------------
# _handle_control_signal per-Problem branches
# ---------------------------------------------------------------------------


class TestHandleControlSignalPerProblem:
    def test_problem_pause_adds_to_set(self, db, tmp_path):
        reactor = _make_reactor(db, tmp_path)
        reactor._handle_control_signal(("problem_pause", "alpha"))
        assert "alpha" in reactor._paused_problems

    def test_problem_resume_removes_from_set(self, db, tmp_path):
        reactor = _make_reactor(db, tmp_path)
        reactor._paused_problems.add("alpha")
        reactor._handle_control_signal(("problem_resume", "alpha"))
        assert "alpha" not in reactor._paused_problems

    def test_problem_pause_emits_applied_event(self, db, tmp_path):
        reactor = _make_reactor(db, tmp_path)
        reactor._handle_control_signal(("problem_pause", "alpha"))
        rows = db.execute(
            "SELECT payload FROM events WHERE kind='control_signal' ORDER BY id"
        ).fetchall()
        # Should have one applied event
        applied = [
            json.loads(p) for (p,) in rows
            if p and json.loads(p).get("status") == "applied"
        ]
        assert any(
            ev.get("action") == "problem_pause" and ev.get("problem") == "alpha"
            for ev in applied
        )

    def test_unknown_tuple_action_diagnostic(self, db, tmp_path):
        reactor = _make_reactor(db, tmp_path)
        reactor._handle_control_signal(("bogus_action", "alpha"))
        rows = db.execute(
            "SELECT payload FROM events WHERE kind='control_signal'"
        ).fetchall()
        # Diagnostic event present
        any_unknown = any(
            "unknown_action" in p for (p,) in rows
        )
        assert any_unknown


# ---------------------------------------------------------------------------
# _poll_db_control_signals forwards per-Problem actions
# ---------------------------------------------------------------------------


class TestPollDbControlSignalsPerProblem:
    def test_problem_pause_forwarded_as_tuple(self, db, tmp_path):
        with db:
            db.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                (
                    "control_signal",
                    json.dumps({
                        "action": "problem_pause", "source": "cli",
                        "problem": "alpha",
                    }),
                    _NOW,
                ),
            )
        reactor = _make_reactor(db, tmp_path)
        reactor._poll_db_control_signals()
        # _event_queue should have one tuple (control_signal, ('problem_pause', 'alpha'))
        items = []
        while not reactor._event_queue.empty():
            items.append(reactor._event_queue.get_nowait())
        assert ("control_signal", ("problem_pause", "alpha")) in items

    def test_problem_resume_forwarded(self, db, tmp_path):
        with db:
            db.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                (
                    "control_signal",
                    json.dumps({
                        "action": "problem_resume", "source": "cli",
                        "problem": "alpha",
                    }),
                    _NOW,
                ),
            )
        reactor = _make_reactor(db, tmp_path)
        reactor._poll_db_control_signals()
        items = []
        while not reactor._event_queue.empty():
            items.append(reactor._event_queue.get_nowait())
        assert ("control_signal", ("problem_resume", "alpha")) in items

    def test_problem_pause_without_problem_field_skipped(self, db, tmp_path):
        with db:
            db.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                (
                    "control_signal",
                    json.dumps({"action": "problem_pause", "source": "cli"}),
                    _NOW,
                ),
            )
        reactor = _make_reactor(db, tmp_path)
        reactor._poll_db_control_signals()
        # Empty queue: no tuple forwarded for malformed payload
        assert reactor._event_queue.empty()

    def test_non_cli_source_filtered(self, db, tmp_path):
        # Daemon's own emit (no source='cli') should not loop back through poll.
        with db:
            db.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                (
                    "control_signal",
                    json.dumps({
                        "action": "problem_pause",
                        "problem": "alpha",
                        "status": "applied",
                    }),
                    _NOW,
                ),
            )
        reactor = _make_reactor(db, tmp_path)
        reactor._poll_db_control_signals()
        assert reactor._event_queue.empty()


# ---------------------------------------------------------------------------
# bypass_startup_check
# ---------------------------------------------------------------------------


class TestBypassStartupCheck:
    def test_bypass_clears_existing_rows(self, db, tmp_path):
        fresh = datetime.now(timezone.utc).isoformat()
        with db:
            db.execute(
                "INSERT INTO schedulers (host, pid, started_at, "
                "last_heartbeat) VALUES ('h', 99, ?, ?)",
                (fresh, fresh),
            )
        reactor = _make_reactor(db, tmp_path, bypass=True)
        # _register_scheduler should not raise + should DELETE old rows
        reactor._register_scheduler()
        rows = db.execute(
            "SELECT COUNT(*) FROM schedulers"
        ).fetchone()[0]
        # Exactly one row (the freshly registered one)
        assert rows == 1
        # And startup_bypass event recorded for audit trail
        events = db.execute(
            "SELECT payload FROM events WHERE kind='control_signal'"
        ).fetchall()
        assert any(
            "startup_bypass" in p for (p,) in events
        )

    def test_no_bypass_rejects_live(self, db, tmp_path):
        fresh = datetime.now(timezone.utc).isoformat()
        with db:
            db.execute(
                "INSERT INTO schedulers (host, pid, started_at, "
                "last_heartbeat) VALUES ('h', 99, ?, ?)",
                (fresh, fresh),
            )
        reactor = _make_reactor(db, tmp_path, bypass=False)
        with pytest.raises(FatalError):
            reactor._register_scheduler()

    def test_no_bypass_succeeds_when_empty(self, db, tmp_path):
        reactor = _make_reactor(db, tmp_path, bypass=False)
        reactor._register_scheduler()
        rows = db.execute(
            "SELECT COUNT(*) FROM schedulers"
        ).fetchone()[0]
        assert rows == 1
