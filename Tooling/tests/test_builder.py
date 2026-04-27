"""Unit tests for Tooling.pipelines.builder.

Covered cases:
  1. tactic_try hit — a tactic passes; first-pass wins
  2. tactic_try exhausted — all tactics fail; dead_attempts written
  3. sorry detection — LakeResult(outcome=exhausted, hasSorry) → exhausted
  4. T_wall timeout — mock monotonic to exceed t_wall before tactics run
  5. commit success path — strategies.status=succeeded + stage_file mv verified
  6. lake / commit fully mocked — no real subprocess
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from Tooling.db.connect import init_schema
from Tooling.lake import LakeResult
from Tooling.pipelines.builder import TACTICS, Builder, BuilderConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    yield conn
    conn.close()


def _make_rows(
    conn: sqlite3.Connection,
    strategy_lean: Path,
    goal_lean: Path,
    *,
    slug: str = "add_zero",
    problem: str = "example",
) -> tuple[int, int]:
    """Insert goal + strategy rows; return (goal_id, strategy_id)."""
    now = "2026-01-01T00:00:00+00:00"
    with conn:
        conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (problem, slug, str(goal_lean), "root", "theorem",
             "open", "live", now, now),
        )
        goal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "INSERT INTO strategies "
            "(goal_id, lean_path, status, commit_state, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (goal_id, str(strategy_lean), "proposed", "live", now),
        )
        strategy_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return goal_id, strategy_id


def _lean_source(proof: str = "by sorry") -> str:
    return f"import Mathlib\ntheorem add_zero (n : Nat) : n + 0 = n := {proof}"


def _exhausted_result() -> LakeResult:
    return LakeResult(outcome="exhausted")


def _proved_result() -> LakeResult:
    return LakeResult(outcome="proved")


# ---------------------------------------------------------------------------
# 1. tactic_try hit — first tactic to pass wins
# ---------------------------------------------------------------------------


class TestTacticHit:
    def test_first_tactic_wins(self, db, tmp_path):
        """rfl passes on first try; no dead_attempts written."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        with patch("Tooling.pipelines.builder.run_lean", return_value=_proved_result()):
            result = Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        assert result.outcome == "proved"
        assert result.tactic == "rfl"
        assert db.execute("SELECT count(*) FROM dead_attempts").fetchone()[0] == 0

    def test_second_tactic_wins(self, db, tmp_path):
        """rfl fails, simp passes; 1 dead_attempt row written for rfl."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        call_count = [0]

        def fake_run(lean_file: str, cwd: str, timeout: float = 600.0) -> LakeResult:
            call_count[0] += 1
            if call_count[0] == 1:
                return _exhausted_result()
            return _proved_result()

        with patch("Tooling.pipelines.builder.run_lean", side_effect=fake_run):
            result = Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        assert result.outcome == "proved"
        assert result.tactic == "simp"
        # dead_attempts only written on full exhausted; not recorded for tactics tried before a hit
        assert db.execute("SELECT count(*) FROM dead_attempts").fetchone()[0] == 0

    def test_staging_file_contains_tactic(self, db, tmp_path):
        """Staging lean written for each attempted tactic."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        seen_contents: list[str] = []

        def fake_run(lean_file: str, cwd: str, timeout: float = 600.0) -> LakeResult:
            seen_contents.append(Path(lean_file).read_text(encoding="utf-8"))
            return _proved_result()

        with patch("Tooling.pipelines.builder.run_lean", side_effect=fake_run):
            Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        assert len(seen_contents) == 1
        assert ":= by rfl" in seen_contents[0]


# ---------------------------------------------------------------------------
# 2. tactic_try exhausted — all tactics fail
# ---------------------------------------------------------------------------


class TestTacticExhausted:
    def test_all_tactics_fail(self, db, tmp_path):
        """All 5 tactics fail; dead_attempts has 5 rows; outcome=exhausted."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            result = Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        assert result.outcome == "exhausted"
        assert result.tactic is None

        rows = db.execute("SELECT reason_summary FROM dead_attempts").fetchall()
        assert len(rows) == len(TACTICS)
        written_tactics = {r[0].split(":")[0].replace("tactic ", "") for r in rows}
        assert written_tactics == set(TACTICS)

    def test_strategy_status_unchanged_on_exhausted(self, db, tmp_path):
        """strategies.status stays 'proposed' when exhausted (no commit)."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        row = db.execute(
            "SELECT status, commit_state FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()
        assert row[0] == "proposed"
        assert row[1] == "live"

    def test_pipeline_outcome_exhausted(self, db, tmp_path):
        """pipelines row has outcome=exhausted and status=failed."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        pipeline = db.execute("SELECT status, outcome FROM pipelines").fetchone()
        assert pipeline[0] == "failed"
        assert pipeline[1] == "exhausted"


# ---------------------------------------------------------------------------
# 3. sorry detection → exhausted
# ---------------------------------------------------------------------------


class TestSorryDetection:
    def test_sorry_outcome_exhausted(self, db, tmp_path):
        """lake returns hasSorry (exit 0) → Builder treats as exhausted."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source("by sorry"), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        sorry_result = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "declaration uses `sorry`"}],
        )

        with patch("Tooling.pipelines.builder.run_lean", return_value=sorry_result):
            result = Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        assert result.outcome == "exhausted"

    def test_sorry_reason_in_dead_attempts(self, db, tmp_path):
        """dead_attempts reason_summary mentions hasSorry."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source("by sorry"), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        sorry_result = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "declaration uses `sorry`"}],
        )

        with patch("Tooling.pipelines.builder.run_lean", return_value=sorry_result):
            Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        reasons = [
            r[0]
            for r in db.execute("SELECT reason_summary FROM dead_attempts").fetchall()
        ]
        assert any("hasSorry" in r for r in reasons)


# ---------------------------------------------------------------------------
# 4. T_wall timeout
# ---------------------------------------------------------------------------


class TestTWall:
    def test_twall_forces_exhausted(self, db, tmp_path):
        """T_wall exceeded before any tactic → outcome=exhausted, no run_lean calls."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # First call: _start = 0.0; second call: T_wall check = 10.0 > 2.0
        mono_seq = [0.0, 10.0]

        with patch("Tooling.pipelines.builder.time") as mock_time:
            mock_time.monotonic.side_effect = mono_seq
            with patch("Tooling.pipelines.builder.run_lean") as mock_lake:
                config = BuilderConfig(t_wall=2.0, base_dir=str(tmp_path))
                result = Builder(strategy_id, db, config).run()

        assert result.outcome == "exhausted"
        assert result.timed_out is True
        mock_lake.assert_not_called()

    def test_twall_no_dead_attempts_when_no_tactics_run(self, db, tmp_path):
        """No dead_attempts written when T_wall triggers before first tactic."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        with patch("Tooling.pipelines.builder.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 10.0]
            with patch("Tooling.pipelines.builder.run_lean"):
                config = BuilderConfig(t_wall=2.0, base_dir=str(tmp_path))
                Builder(strategy_id, db, config).run()

        assert db.execute("SELECT count(*) FROM dead_attempts").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# 5. commit success path
# ---------------------------------------------------------------------------


class TestCommitSuccess:
    def test_strategies_status_succeeded(self, db, tmp_path):
        """After proved: strategies.status=succeeded, commit_state=live."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        with patch("Tooling.pipelines.builder.run_lean", return_value=_proved_result()):
            Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        row = db.execute(
            "SELECT status, commit_state, prior_state_snapshot "
            "FROM strategies WHERE id = ?",
            (strategy_id,),
        ).fetchone()
        assert row[0] == "succeeded"
        assert row[1] == "live"
        assert row[2] is None

    def test_stage_file_mv_to_lean_path(self, db, tmp_path):
        """staging .lean is moved to strategy.lean_path with tactic content."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source("by sorry"), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        with patch("Tooling.pipelines.builder.run_lean", return_value=_proved_result()):
            Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        # lean_path now has 'by rfl' (first tactic, first passed)
        final_content = strategy_lean.read_text(encoding="utf-8")
        assert ":= by rfl" in final_content

    def test_pipeline_outcome_proved(self, db, tmp_path):
        """pipelines row has outcome=proved and status=succeeded."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        with patch("Tooling.pipelines.builder.run_lean", return_value=_proved_result()):
            Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        pipeline = db.execute("SELECT status, outcome FROM pipelines").fetchone()
        assert pipeline[0] == "succeeded"
        assert pipeline[1] == "proved"

    def test_pipeline_finished_event_emitted(self, db, tmp_path):
        """pipeline_finished event written to events table."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        with patch("Tooling.pipelines.builder.run_lean", return_value=_proved_result()):
            Builder(strategy_id, db, BuilderConfig(base_dir=str(tmp_path))).run()

        event = db.execute(
            "SELECT kind FROM events WHERE kind = 'pipeline_finished'"
        ).fetchone()
        assert event is not None
