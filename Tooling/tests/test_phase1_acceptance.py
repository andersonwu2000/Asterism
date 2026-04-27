"""P1 Acceptance tests #0–#11.

Covers phase1_skeleton.md §Acceptance criteria in order.
Each class maps to one acceptance criterion.

Lake calls are mocked (LAKE_MOCK_PROVED/SORRY env vars or unittest.mock)
so the suite runs in CI without a Lean/lake installation.

Caveat for #0 and #6: real lake integration requires `lake env lean` in PATH
and Mathlib in the lake environment. Those scenarios are tested with mock
hooks here; for manual verification run the demo bash with real lake env.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.cli import cmd_db_recover, cmd_goal_add, cmd_goal_show, cmd_init, cmd_run
from Tooling.commit import CommitWriter
from Tooling.db.connect import connect, init_schema
from Tooling.lake import LakeResult
from Tooling.pipelines.builder import Builder, BuilderConfig, BuilderResult
from Tooling.scheduler import FatalError, Reactor, ReactorConfig


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent.parent  # D:/Asterism (or wherever)
_FIXTURES = Path(__file__).parent / "fixtures"
_NOW = "2026-01-01T00:00:00+00:00"


def _make_db(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    db_path = tmp_path / "asterism.db"
    conn = connect(db_path)
    init_schema(conn)
    return db_path, conn


def _insert_goal(
    conn: sqlite3.Connection,
    lean_path: str,
    slug: str = "testgoal",
    status: str = "open",
    commit_state: str = "live",
    prior_state_snapshot: str | None = None,
) -> int:
    conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, commit_state, "
        "prior_state_snapshot, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("ex", slug, lean_path, "root", "theorem", status,
         commit_state, prior_state_snapshot, _NOW, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_strategy(
    conn: sqlite3.Connection,
    goal_id: int,
    lean_path: str,
    status: str = "proposed",
    commit_state: str = "live",
    prior_state_snapshot: str | None = None,
) -> int:
    conn.execute(
        "INSERT INTO strategies "
        "(goal_id, lean_path, status, commit_state, prior_state_snapshot, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (goal_id, lean_path, status, commit_state, prior_state_snapshot, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _enqueue(conn: sqlite3.Connection, target_id: int | str, kind: str = "Builder") -> None:
    conn.execute(
        "INSERT INTO queue (kind, target_id, priority, created_at) VALUES (?,?,?,?)",
        (kind, str(target_id), 0, _NOW),
    )
    conn.commit()


def _make_rows(
    conn: sqlite3.Connection,
    strategy_lean: Path,
    goal_lean: Path,
    slug: str = "add_zero",
) -> tuple[int, int]:
    goal_id = _insert_goal(conn, str(goal_lean), slug=slug)
    strategy_id = _insert_strategy(conn, goal_id, str(strategy_lean))
    return goal_id, strategy_id


def _args(**kwargs):
    ns = MagicMock()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


# ─────────────────────────────────────────────────────────────
# AC #0: Demo bash subprocess (init → goal add → run → goal show)
# ─────────────────────────────────────────────────────────────


class TestAC0DemoSubprocess:
    """#0: Full demo flow via subprocess with LAKE_MOCK_PROVED=1.

    Runs `python -m Tooling.cli` subprocesses with CWD=tmp_path so each
    call exercises the real CLI entry-point, DB setup, CommitWriter, Reactor,
    and cascade rule end-to-end without needing a live Lean installation.
    """

    def _run(self, args: list[str], tmp_path: Path, extra_env: dict) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "PYTHONPATH": str(_REPO_ROOT),
            **extra_env,
        }
        return subprocess.run(
            [sys.executable, "-m", "Tooling.cli"] + args,
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_demo_init_to_goal_show_proved(self, tmp_path: Path) -> None:
        env = {"LAKE_MOCK_PROVED": "1"}

        # 1. init
        r = self._run(["init", "--problem", "example"], tmp_path, env)
        assert r.returncode == 0, f"init failed (rc={r.returncode}): {r.stderr}"
        assert (tmp_path / "Problems" / "example" / "META.md").exists()

        # 2. Write leaf strategy (by simp)
        strat_file = tmp_path / "strat.lean"
        strat_file.write_text(
            "import Mathlib\n"
            "theorem add_zero_simple (n : Nat) : n + 0 = n := by simp\n",
            encoding="utf-8",
        )

        # 3. goal add
        r = self._run([
            "goal", "add",
            "--problem", "example",
            "--slug", "add_zero_simple",
            "--kind", "theorem",
            "--leaf-strategy", str(strat_file),
        ], tmp_path, env)
        assert r.returncode == 0, f"goal add failed (rc={r.returncode}): {r.stderr}"

        # 4. run --once  (Reactor exits 0 on empty queue after proved)
        r = self._run(["run", "--once"], tmp_path, env)
        assert r.returncode == 0, f"run failed (rc={r.returncode}): {r.stderr}"

        # 5. goal show G_root
        r = self._run(["goal", "show", "G_root"], tmp_path, env)
        assert r.returncode == 0, f"goal show failed (rc={r.returncode}): {r.stderr}"
        assert "proved" in r.stdout, f"expected 'proved' in: {r.stdout}"
        assert "classical" in r.stdout, f"expected 'classical' in: {r.stdout}"


# ─────────────────────────────────────────────────────────────
# AC #1: SQL schema completeness
# ─────────────────────────────────────────────────────────────


class TestAC1SqlSchema:
    """#1: sqlite3 .schema lists all v3 §9.1 tables with required columns."""

    _REQUIRED_TABLES = {
        "goals", "strategies", "strategy_subgoals", "pipelines",
        "dead_attempts", "queue", "events", "schedulers",
        "continuous_tasks", "construction_attempts",
        "library_index", "search_cache", "strategist_decisions",
    }

    _SPOT_COLUMNS = {
        "goals": {
            "id", "problem", "slug", "lean_path", "origin", "kind", "status",
            "answer_data", "commit_state", "prior_state_snapshot",
            "created_at", "updated_at",
            # P2+ nullable columns present in schema
            "twin_of", "derived_from", "trust_set", "depth",
        },
        "strategies": {
            "id", "goal_id", "lean_path", "status",
            "commit_state", "prior_state_snapshot", "created_by",
        },
        "pipelines": {
            "id", "kind", "runtime", "target_id", "target_kind",
            "status", "outcome", "started_at", "finished_at",
        },
        "dead_attempts": {
            "id", "target_id", "target_kind", "pipeline_id",
            "pipeline_kind", "outcome", "reason_summary", "ts",
        },
        "queue": {"id", "kind", "target_id", "priority", "created_at"},
        "events": {"id", "kind", "payload", "ts"},
    }

    def test_all_tables_exist(self, tmp_path: Path) -> None:
        _, conn = _make_db(tmp_path)
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing = self._REQUIRED_TABLES - tables
        assert not missing, f"Missing tables: {missing}"

    def test_spot_columns_exist(self, tmp_path: Path) -> None:
        _, conn = _make_db(tmp_path)
        for table, expected_cols in self._SPOT_COLUMNS.items():
            info = conn.execute(f"PRAGMA table_info({table})").fetchall()
            actual_cols = {row[1] for row in info}
            missing = expected_cols - actual_cols
            assert not missing, f"{table}: missing columns {missing}"

    def test_nullable_p2_columns_accept_null(self, tmp_path: Path) -> None:
        """Columns unused in P1 must accept NULL (no NOT NULL constraint)."""
        _, conn = _make_db(tmp_path)
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("ex", "g", "path.lean", "root", "theorem", "open", "live", _NOW, _NOW),
        )
        conn.commit()
        # trust_set, depth, twin_of, derived_from should be NULL
        row = conn.execute(
            "SELECT trust_set, depth, twin_of, derived_from FROM goals"
        ).fetchone()
        assert all(v is None for v in row), f"Expected NULLs, got: {row}"


# ─────────────────────────────────────────────────────────────
# AC #2: Commit recovery — INSERT / strategies
# ─────────────────────────────────────────────────────────────


class TestAC2RecoveryInsertStrategies:
    """#2: Pending INSERT strategies row (no file) → recover_scan → DELETE."""

    def test_pending_insert_strategies_deleted(self, tmp_path: Path) -> None:
        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(conn, "nonexistent/goal.lean")
        # Simulate interrupted INSERT: pending row, no snapshot, lean_path doesn't exist
        s_id = _insert_strategy(
            conn, goal_id, "nonexistent/strat.lean",
            commit_state="pending", prior_state_snapshot=None,
        )

        writer = CommitWriter(conn)
        recovered = writer.recover_scan()

        # Row should be deleted
        row = conn.execute(
            "SELECT id FROM strategies WHERE id=?", (s_id,)
        ).fetchone()
        assert row is None, "Pending INSERT strategies row should be deleted on recover"
        assert s_id in recovered["strategies"]


# ─────────────────────────────────────────────────────────────
# AC #3: Commit recovery — INSERT / goals (both tables)
# ─────────────────────────────────────────────────────────────


class TestAC3RecoveryInsertGoals:
    """#3: Pending INSERT goals + strategies rows → recover_scan → both DELETE."""

    def test_pending_insert_goals_deleted(self, tmp_path: Path) -> None:
        _, conn = _make_db(tmp_path)
        # Pending goal: no lean_path file, no snapshot
        g_id = _insert_goal(
            conn, "nonexistent/goal.lean",
            commit_state="pending", prior_state_snapshot=None,
        )
        # Pending strategy linked to that goal
        s_id = _insert_strategy(
            conn, g_id, "nonexistent/strat.lean",
            commit_state="pending", prior_state_snapshot=None,
        )

        writer = CommitWriter(conn)
        recovered = writer.recover_scan()

        goal_row = conn.execute("SELECT id FROM goals WHERE id=?", (g_id,)).fetchone()
        strat_row = conn.execute("SELECT id FROM strategies WHERE id=?", (s_id,)).fetchone()
        assert goal_row is None, "Pending INSERT goals row should be deleted"
        assert strat_row is None, "Pending INSERT strategies row should also be deleted"
        assert g_id in recovered["goals"]
        assert s_id in recovered["strategies"]


# ─────────────────────────────────────────────────────────────
# AC #4: Commit recovery — UPDATE / strategies (restore old status)
# ─────────────────────────────────────────────────────────────


class TestAC4RecoveryUpdateStrategies:
    """#4: Pending UPDATE strategies row with snapshot → recover restores old status."""

    def test_update_recovery_restores_status(self, tmp_path: Path) -> None:
        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(conn, "nonexistent/goal.lean")

        # Insert as pending UPDATE (simulating COMMIT_FAULT=after_step1 on update)
        s_id = _insert_strategy(
            conn, goal_id, "nonexistent/strat.lean",
            status="proposed",
            commit_state="pending",
        )
        # Build snapshot from actual columns in strategies table (no session_id in P1 schema)
        snapshot = json.dumps({
            "id": s_id,
            "goal_id": goal_id,
            "lean_path": "nonexistent/strat.lean",
            "status": "proposed",
            "commit_state": "live",
            "prior_state_snapshot": None,
            "parent_subgoal_max_similarity": None,
            "created_by": None,
            "created_at": _NOW,
        })
        conn.execute(
            "UPDATE strategies SET prior_state_snapshot=? WHERE id=?",
            (snapshot, s_id),
        )
        conn.commit()

        writer = CommitWriter(conn)
        writer.recover_scan()

        row = conn.execute(
            "SELECT status, commit_state, prior_state_snapshot FROM strategies WHERE id=?",
            (s_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "proposed", f"Status should be restored to 'proposed', got {row[0]}"
        assert row[1] == "live", f"commit_state should be 'live' after recovery, got {row[1]}"
        assert row[2] is None, "prior_state_snapshot should be cleared after recovery"


# ─────────────────────────────────────────────────────────────
# AC #5: Commit recovery — lean_path exists (mv done, finalize not done)
# ─────────────────────────────────────────────────────────────


class TestAC5RecoveryMvAfterKill:
    """#5: COMMIT_FAULT=after_step2 → lean_path file exists, row pending
    → recover detects file presence → finalize → commit_state='live'."""

    def test_lean_path_exists_finalizes_row(self, tmp_path: Path) -> None:
        _, conn = _make_db(tmp_path)
        goal_id = _insert_goal(conn, str(tmp_path / "goal.lean"))

        # Create the lean file (simulating stage_file mv success)
        strat_lean = tmp_path / "strat.lean"
        strat_lean.write_text("theorem t : True := by trivial\n", encoding="utf-8")

        # Strategy row: pending, has snapshot (UPDATE path), lean_path exists
        old_snap = json.dumps({
            "id": 1, "goal_id": goal_id, "lean_path": str(strat_lean),
            "status": "proposed", "commit_state": "live",
            "prior_state_snapshot": None, "created_at": _NOW,
            "created_by": None, "parent_subgoal_max_similarity": None,
        })
        s_id = _insert_strategy(
            conn, goal_id, str(strat_lean),
            status="proposed",
            commit_state="pending",
            prior_state_snapshot=old_snap,
        )

        writer = CommitWriter(conn)
        recovered = writer.recover_scan()

        row = conn.execute(
            "SELECT commit_state, prior_state_snapshot FROM strategies WHERE id=?",
            (s_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "live", f"Expected commit_state=live after finalize, got {row[0]}"
        assert row[1] is None, "prior_state_snapshot should be cleared"
        assert s_id in recovered["strategies"]


# ─────────────────────────────────────────────────────────────
# AC #6: Lake integration — pass path (by simp → proved)
# ─────────────────────────────────────────────────────────────


class TestAC6LakeIntegrationPass:
    """#6: run --once on a by-simp leaf Strategy → status=proved.

    run_lean is mocked so the test runs without a real lake installation.
    The full Reactor → Builder → cascade path is exercised.
    """

    def test_full_reactor_run_proves_goal(self, tmp_path: Path) -> None:
        db_path, conn = _make_db(tmp_path)

        # Write leaf strategy file with `by simp` (demo theorem content)
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(
            "import Mathlib\n"
            "theorem add_zero_simple (n : Nat) : n + 0 = n := by simp\n",
            encoding="utf-8",
        )
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("-- goal placeholder\n", encoding="utf-8")

        goal_id, strategy_id = _make_rows(conn, strategy_lean, goal_lean)
        _enqueue(conn, strategy_id)
        conn.close()

        with patch("Tooling.pipelines.builder.run_lean", return_value=LakeResult(outcome="proved")):
            reactor = Reactor(str(db_path), ReactorConfig(base_dir=str(tmp_path)))
            with pytest.raises(SystemExit) as exc:
                reactor.run()
        assert exc.value.code == 0

        conn2 = connect(db_path)
        try:
            row = conn2.execute(
                "SELECT status, answer_data FROM goals WHERE id=?", (goal_id,)
            ).fetchone()
            assert row[0] == "proved", f"Expected proved, got {row[0]}"
            ad = json.loads(row[1])
            assert ad["type"] == "classical"
            assert "lean_path" in ad
        finally:
            conn2.close()


# ─────────────────────────────────────────────────────────────
# AC #7: Lake integration — sorry detection
# ─────────────────────────────────────────────────────────────


class TestAC7SorryDetection:
    """#7: Strategy containing sorry → outcome=exhausted, dead_attempts written.

    Uses spike003_sorry_nolib.lean as the source file content.
    run_lean is mocked to return hasSorry (spike-003 §D4 rule).
    """

    def test_sorry_strategy_exhausted_with_dead_attempts(self, tmp_path: Path) -> None:
        # Use the spike fixture as source content
        spike_content = (_FIXTURES / "spikes" / "spike003_sorry_nolib.lean").read_text(
            encoding="utf-8"
        )
        db_path, conn = _make_db(tmp_path)

        strategy_lean = tmp_path / "strat_sorry.lean"
        strategy_lean.write_text(spike_content, encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("-- goal\n", encoding="utf-8")

        goal_id, strategy_id = _make_rows(conn, strategy_lean, goal_lean)
        _enqueue(conn, strategy_id)
        conn.close()

        sorry_result = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "declaration uses `sorry`"}],
        )
        with patch("Tooling.pipelines.builder.run_lean", return_value=sorry_result):
            reactor = Reactor(str(db_path), ReactorConfig(base_dir=str(tmp_path)))
            with pytest.raises(SystemExit) as exc:
                reactor.run()
        assert exc.value.code == 0

        conn2 = connect(db_path)
        try:
            # Goal status unchanged (not proved)
            g_status = conn2.execute(
                "SELECT status FROM goals WHERE id=?", (goal_id,)
            ).fetchone()[0]
            assert g_status == "open", f"Goal should still be open, got {g_status}"

            # dead_attempts written with sorry reason
            reasons = [
                r[0]
                for r in conn2.execute(
                    "SELECT reason_summary FROM dead_attempts"
                ).fetchall()
            ]
            assert reasons, "dead_attempts should have rows after sorry exhaustion"
            assert any("hasSorry" in r for r in reasons), (
                f"Expected hasSorry in dead_attempts reasons: {reasons}"
            )
        finally:
            conn2.close()


# ─────────────────────────────────────────────────────────────
# AC #8: T_wall timeout → exhausted (no retry loop)
# ─────────────────────────────────────────────────────────────


class TestAC8TWallTimeout:
    """#8: T_wall=2s + simulated slow lake → outcome=exhausted, no retry.

    time.monotonic is patched to simulate T_wall breach mid-loop so the
    test completes instantly without real sleeping.
    """

    def test_twall_timeout_produces_exhausted(self, tmp_path: Path) -> None:
        _, conn = _make_db(tmp_path)

        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(
            "theorem foo (n : Nat) : n + 0 = n := by simp\n", encoding="utf-8"
        )
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("-- goal\n", encoding="utf-8")
        goal_id, strategy_id = _make_rows(conn, strategy_lean, goal_lean)

        # Monotonic sequence: start=0.0, then first tactic check = 3.0 (> T_wall=2s)
        mono_seq = iter([0.0, 3.0])

        with patch("Tooling.pipelines.builder.time") as mock_time:
            mock_time.monotonic.side_effect = lambda: next(mono_seq)
            with patch("Tooling.pipelines.builder.run_lean") as mock_lake:
                cfg = BuilderConfig(t_wall=2.0, base_dir=str(tmp_path))
                result = Builder(strategy_id, conn, cfg).run()

        assert result.outcome == "exhausted", f"Expected exhausted, got {result.outcome}"
        assert result.timed_out is True
        mock_lake.assert_not_called()  # no retry loop — exited before any tactic

        # No dead_attempts when T_wall fires before any tactic runs
        assert conn.execute("SELECT COUNT(*) FROM dead_attempts").fetchone()[0] == 0


# ─────────────────────────────────────────────────────────────
# AC #9: CLI chain — init → goal add → run → goal show
# ─────────────────────────────────────────────────────────────


class TestAC9CliChain:
    """#9: Full CLI one-liner in-process: init → goal add → run → goal show.

    run_lean mocked so no Lean required. Verifies CLI commands compose
    correctly via real CommitWriter + Reactor + cascade.
    """

    def test_cli_chain_proved(self, tmp_path: Path) -> None:
        db_path = tmp_path / "asterism.db"

        # 1. init
        cmd_init(_args(problem="example"), base_dir=tmp_path)
        assert (tmp_path / "Problems" / "example" / "META.md").exists()

        # 2. Write leaf strategy and goal add
        leaf = tmp_path / "leaf.lean"
        leaf.write_text(
            "import Mathlib\n"
            "theorem add_zero_simple (n : Nat) : n + 0 = n := by simp\n",
            encoding="utf-8",
        )
        cmd_goal_add(
            _args(problem="example", slug="add_zero_simple",
                  kind="theorem", leaf_strategy=str(leaf)),
            db_path=db_path, base_dir=tmp_path,
        )

        # 3. run --once (mock lake)
        with patch("Tooling.pipelines.builder.run_lean",
                   return_value=LakeResult(outcome="proved")):
            with pytest.raises(SystemExit) as exc:
                cmd_run(_args(once=True, daemon=False), db_path=db_path, base_dir=tmp_path)
        assert exc.value.code == 0

        # 4. goal show G_root
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_goal_show(_args(goal_id="G_root"), db_path=db_path)
        out = buf.getvalue()
        assert "proved" in out
        assert "classical" in out


# ─────────────────────────────────────────────────────────────
# AC #10: Idempotent — second run exits 0, no duplicate commit
# ─────────────────────────────────────────────────────────────


class TestAC10Idempotent:
    """#10: Second `run --once` on proved goal → empty queue → exit 0, no side effects."""

    def test_second_run_is_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "asterism.db"

        # Setup: init + goal add
        cmd_init(_args(problem="ex"), base_dir=tmp_path)
        leaf = tmp_path / "leaf.lean"
        leaf.write_text("theorem t : True := by trivial\n", encoding="utf-8")
        cmd_goal_add(
            _args(problem="ex", slug="t", kind="theorem", leaf_strategy=str(leaf)),
            db_path=db_path, base_dir=tmp_path,
        )

        # First run: proves the goal
        with patch("Tooling.pipelines.builder.run_lean",
                   return_value=LakeResult(outcome="proved")):
            with pytest.raises(SystemExit) as exc:
                cmd_run(_args(once=True, daemon=False), db_path=db_path, base_dir=tmp_path)
        assert exc.value.code == 0

        # Verify proved after first run
        conn = connect(db_path)
        try:
            status_before = conn.execute("SELECT status FROM goals").fetchone()[0]
            events_before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            queue_count = conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]
        finally:
            conn.close()

        assert status_before == "proved"
        assert queue_count == 0

        # Second run: queue is empty → reactor exits 0 immediately
        with patch("Tooling.pipelines.builder.run_lean") as mock_lake:
            with pytest.raises(SystemExit) as exc:
                cmd_run(_args(once=True, daemon=False), db_path=db_path, base_dir=tmp_path)
        assert exc.value.code == 0
        mock_lake.assert_not_called()  # no new Builder spawned

        conn = connect(db_path)
        try:
            status_after = conn.execute("SELECT status FROM goals").fetchone()[0]
            events_after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        finally:
            conn.close()

        assert status_after == "proved"  # goal unchanged
        assert events_after == events_before  # no new events emitted


# ─────────────────────────────────────────────────────────────
# AC #11: Cascade fatal halt (unique constraint → fatal event + exit 1)
# ─────────────────────────────────────────────────────────────


class TestAC11CascadeFatalHalt:
    """#11: Injected UNIQUE constraint in cascade → fatal event + exit(1) + DB preserved.

    Acceptance: phase1_skeleton.md §Scope §In line 28:
    'cascade SQL fail → emit fatal event + scheduler halt (exit non-zero)
     + 保留現場 + DB 現場保留'.
    """

    def test_cascade_sql_fail_emits_fatal_and_exits_1(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"

        # Pre-populate DB
        setup = connect(db_path)
        init_schema(setup)
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text("theorem t : True := by trivial\n", encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("-- goal\n", encoding="utf-8")
        g_id, s_id = _make_rows(setup, strategy_lean, goal_lean)
        _enqueue(setup, s_id)
        setup.close()

        reactor = Reactor(str(db_path), ReactorConfig(base_dir=str(tmp_path)))

        with patch("Tooling.scheduler.Builder") as MockBuilder:
            MockBuilder.return_value.run.return_value = BuilderResult(outcome="proved")
            reactor.startup()
            with patch.object(
                reactor, "_update_goal_proved",
                side_effect=sqlite3.IntegrityError("UNIQUE constraint failed"),
            ):
                with pytest.raises(SystemExit) as exc:
                    reactor._run_loop()

        assert exc.value.code == 1, f"Expected exit(1), got {exc.value.code}"

        # fatal event written to DB
        event = reactor.conn.execute(
            "SELECT kind, payload FROM events WHERE kind='fatal'"
        ).fetchone()
        assert event is not None, "fatal event must be written on cascade SQL failure"
        assert "UNIQUE constraint failed" in json.loads(event[1])["error"]

        # DB 現場保留: strategy + goal rows still present
        assert reactor.conn.execute(
            "SELECT id FROM strategies WHERE id=?", (s_id,)
        ).fetchone() is not None, "strategy row must be preserved on fatal halt"
        assert reactor.conn.execute(
            "SELECT id FROM goals WHERE id=?", (g_id,)
        ).fetchone() is not None, "goal row must be preserved on fatal halt"
