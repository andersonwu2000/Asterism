"""Unit tests for Tooling.pipelines.builder.

Covered cases:
  1. tactic_try hit — a tactic passes; first-pass wins
  2. tactic_try exhausted — all tactics fail; dead_attempts written
  3. sorry detection — LakeResult(outcome=exhausted, hasSorry) → exhausted
  4. T_wall timeout — mock monotonic to exceed t_wall before tactics run
  5. commit success path — strategies.status=succeeded + stage_file mv verified
  6. lake / commit fully mocked — no real subprocess
  7. failure_replay — reads real dead_attempts from DB (K_digest=5)
  8. tactic_llm dispatch — three outcomes: tactic_proof / needs_decomp / bad_goal
  9. self_verify — extracted stage: proved→True, non-proved→False
  10. silent-failure防線 — non-proved lake result never silently passes
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.agent.provider import AgentResponse
from Tooling.db.connect import init_schema
from Tooling.lake import LakeResult
from Tooling.pipelines.builder import K_DIGEST, TACTICS, Builder, BuilderConfig


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

    def test_twall_breaks_mid_loop(self, db, tmp_path):
        """T_wall triggered after N tactics tried (acceptance #8 真實情境):
        rfl + simp run (both exhausted), then T_wall trips before decide.
        dead_attempts has 2 rows; timed_out=True; lake called twice."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # monotonic call sequence:
        #   call 1 (_start)        : 0.0
        #   call 2 (rfl entry)     : 0.5  (< 2s, enter)
        #   call 3 (simp entry)    : 1.5  (< 2s, enter)
        #   call 4 (decide entry)  : 3.0  (>= 2s, break)
        mono_seq = iter([0.0, 0.5, 1.5, 3.0])

        with patch("Tooling.pipelines.builder.time") as mock_time:
            mock_time.monotonic.side_effect = lambda: next(mono_seq)
            with patch(
                "Tooling.pipelines.builder.run_lean",
                return_value=_exhausted_result(),
            ) as mock_lake:
                config = BuilderConfig(t_wall=2.0, base_dir=str(tmp_path))
                result = Builder(strategy_id, db, config).run()

        assert result.outcome == "exhausted"
        assert result.timed_out is True
        assert mock_lake.call_count == 2
        assert db.execute("SELECT count(*) FROM dead_attempts").fetchone()[0] == 2

    def test_twall_clamps_per_call_timeout(self, db, tmp_path):
        """run_lean receives min(lake_timeout, remaining T_wall) — fix #1."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # call 1 _start=0.0, call 2 rfl entry elapsed=1.5 → remaining=0.5
        mono_seq = iter([0.0, 1.5])
        captured: list[float] = []

        def fake_run(lean_file: str, cwd: str, timeout: float = 600.0) -> LakeResult:
            captured.append(timeout)
            return _proved_result()

        with patch("Tooling.pipelines.builder.time") as mock_time:
            mock_time.monotonic.side_effect = lambda: next(mono_seq)
            with patch("Tooling.pipelines.builder.run_lean", side_effect=fake_run):
                config = BuilderConfig(
                    t_wall=2.0, lake_timeout=600.0, base_dir=str(tmp_path)
                )
                Builder(strategy_id, db, config).run()

        # remaining = 2.0 - 1.5 = 0.5 < lake_timeout=600 → clamp to 0.5
        assert captured == [0.5]


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


# ---------------------------------------------------------------------------
# Helper: build a mock FallbackChain that returns a fixed AgentResponse
# ---------------------------------------------------------------------------


def _mock_chain(output: str, *, outcome: str = "success") -> MagicMock:
    response = AgentResponse(output=output, session_id="test-session")
    chain = MagicMock()
    chain.run.return_value = (response if outcome == "success" else None, outcome)
    return chain


def _json_block(obj: dict) -> str:
    import json
    return f"```json\n{json.dumps(obj)}\n```"


# ---------------------------------------------------------------------------
# 7. failure_replay — reads real dead_attempts from DB
# ---------------------------------------------------------------------------


class TestFailureReplay:
    def _insert_pipeline_row(self, db, pid: str, strategy_id: int) -> None:
        now = "2026-01-01T00:00:00+00:00"
        with db:
            db.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, started_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pid, "Builder", "atomic", str(strategy_id), "Strategy", "failed", now),
            )

    def test_reads_dead_attempts_for_strategy(self, db, tmp_path):
        """_failure_replay returns rows for this strategy sorted newest-first."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        self._insert_pipeline_row(db, "p-test", strategy_id)
        with db:
            for i in range(3):
                db.execute(
                    "INSERT INTO dead_attempts "
                    "(target_id, target_kind, pipeline_id, pipeline_kind, "
                    "outcome, reason_summary, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(strategy_id), "Strategy", "p-test", "Builder",
                        "exhausted", f"tactic t{i}: failed",
                        f"2026-01-01T{i:02d}:00:00+00:00",
                    ),
                )

        builder = Builder(strategy_id, db, BuilderConfig())
        rows = builder._failure_replay()

        assert len(rows) == 3
        # Newest first
        assert rows[0]["ts"] == "2026-01-01T02:00:00+00:00"
        assert rows[2]["ts"] == "2026-01-01T00:00:00+00:00"

    def test_respects_k_digest_limit(self, db, tmp_path):
        """_failure_replay returns at most k_digest rows."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        self._insert_pipeline_row(db, "p-test", strategy_id)
        # Insert K_DIGEST + 2 rows
        with db:
            for i in range(K_DIGEST + 2):
                db.execute(
                    "INSERT INTO dead_attempts "
                    "(target_id, target_kind, pipeline_id, pipeline_kind, "
                    "outcome, reason_summary, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(strategy_id), "Strategy", "p-test", "Builder",
                        "exhausted", f"reason {i}",
                        f"2026-01-01T{i:02d}:00:00+00:00",
                    ),
                )

        builder = Builder(strategy_id, db, BuilderConfig())
        rows = builder._failure_replay()

        assert len(rows) == K_DIGEST

    def test_ignores_other_strategy_attempts(self, db, tmp_path):
        """_failure_replay only returns rows for this strategy_id."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # Insert pipeline for strategy_id=999 (won't exist in goals/strategies, but
        # dead_attempts FK only checks pipelines.id, not target_id)
        self._insert_pipeline_row(db, "p-other", strategy_id)
        with db:
            db.execute(
                "INSERT INTO dead_attempts "
                "(target_id, target_kind, pipeline_id, pipeline_kind, "
                "outcome, reason_summary, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("999", "Strategy", "p-other", "Builder", "exhausted", "x", "2026-01-01T00:00:00+00:00"),
            )

        builder = Builder(strategy_id, db, BuilderConfig())
        rows = builder._failure_replay()

        assert rows == []

    def test_failure_replay_feeds_into_tactic_llm_prompt(self, db, tmp_path):
        """After tactic_try exhausted, failure_replay result (from DB) is passed to tactic_llm."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # Pre-insert a dead_attempt in DB (needs pipeline FK)
        self._insert_pipeline_row(db, "p-prev", strategy_id)
        with db:
            db.execute(
                "INSERT INTO dead_attempts "
                "(target_id, target_kind, pipeline_id, pipeline_kind, "
                "outcome, reason_summary, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(strategy_id), "Strategy", "p-prev", "Builder",
                    "exhausted", "tactic ring: failed", "2026-01-01T00:00:00+00:00",
                ),
            )

        captured_prompts: list[str] = []
        mock_chain = MagicMock()

        def fake_chain_run(**kwargs):
            captured_prompts.append(kwargs.get("prompt", ""))
            return None, "exhausted"

        mock_chain.run.side_effect = lambda **kwargs: (None, "exhausted")
        # Capture prompt from _build_prompt instead
        original_build = Builder._build_prompt

        def capturing_build(self_ref, goal, dead_attempts, lemmas):
            prompt = original_build(self_ref, goal, dead_attempts, lemmas)
            captured_prompts.append(prompt)
            return prompt

        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            with patch.object(Builder, "_build_prompt", capturing_build):
                mock_chain.run.return_value = (None, "exhausted")
                Builder(
                    strategy_id, db,
                    BuilderConfig(base_dir=str(tmp_path), max_retries=1),
                    chain=mock_chain,
                ).run()

        # dead_attempt from DB must appear in the prompt
        assert any("ring" in p for p in captured_prompts)


# ---------------------------------------------------------------------------
# 8. tactic_llm dispatch — three outcomes
# ---------------------------------------------------------------------------


class TestTacticLlmDispatch:
    def _setup(self, db, tmp_path, *, slug="add_zero"):
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        return _make_rows(db, strategy_lean, goal_lean, slug=slug)

    def test_tactic_proof_outcome_proved(self, db, tmp_path):
        """tactic_llm returns tactic_proof; self_verify passes → outcome=proved."""
        _, strategy_id = self._setup(db, tmp_path)

        call_count = [0]

        def fake_run(lean_file, cwd, timeout=600.0):
            call_count[0] += 1
            if call_count[0] <= len(TACTICS):
                return _exhausted_result()   # tactic_try all fail
            return _proved_result()           # self_verify passes

        chain = _mock_chain(_json_block({"tactic_proof": "exact rfl"}))
        with patch("Tooling.pipelines.builder.run_lean", side_effect=fake_run):
            result = Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path)),
                chain=chain,
            ).run()

        assert result.outcome == "proved"
        assert result.tactic == "exact rfl"

    def test_tactic_proof_pipeline_row_succeeded(self, db, tmp_path):
        """tactic_llm proved → pipelines row status=succeeded."""
        _, strategy_id = self._setup(db, tmp_path)

        call_count = [0]

        def fake_run(lean_file, cwd, timeout=600.0):
            call_count[0] += 1
            return _proved_result() if call_count[0] > len(TACTICS) else _exhausted_result()

        chain = _mock_chain(_json_block({"tactic_proof": "ring"}))
        with patch("Tooling.pipelines.builder.run_lean", side_effect=fake_run):
            Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path)),
                chain=chain,
            ).run()

        pipeline = db.execute("SELECT status, outcome FROM pipelines").fetchone()
        assert pipeline[0] == "succeeded"
        assert pipeline[1] == "proved"

    def test_needs_decomposition_outcome(self, db, tmp_path):
        """tactic_llm returns needs_decomposition → outcome=needs_decomp."""
        _, strategy_id = self._setup(db, tmp_path)

        chain = _mock_chain(_json_block({"needs_decomposition": True}))
        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            result = Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path)),
                chain=chain,
            ).run()

        assert result.outcome == "needs_decomp"

    def test_needs_decomp_pipeline_row_failed(self, db, tmp_path):
        """needs_decomp → pipelines row status=failed."""
        _, strategy_id = self._setup(db, tmp_path)

        chain = _mock_chain(_json_block({"needs_decomposition": True}))
        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path)),
                chain=chain,
            ).run()

        pipeline = db.execute("SELECT status, outcome FROM pipelines").fetchone()
        assert pipeline[0] == "failed"
        assert pipeline[1] == "needs_decomp"

    def test_bad_goal_outcome(self, db, tmp_path):
        """tactic_llm returns bad_goal → outcome=bad_goal."""
        _, strategy_id = self._setup(db, tmp_path)

        chain = _mock_chain(_json_block({"bad_goal": "statement is vacuously false"}))
        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            result = Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path)),
                chain=chain,
            ).run()

        assert result.outcome == "bad_goal"

    def test_bad_goal_writes_dead_attempts(self, db, tmp_path):
        """bad_goal → dead_attempts row with 'Builder reviewed bad' written for goal."""
        _, strategy_id = self._setup(db, tmp_path)

        chain = _mock_chain(_json_block({"bad_goal": "missing hypothesis H"}))
        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path)),
                chain=chain,
            ).run()

        rows = db.execute(
            "SELECT reason_summary FROM dead_attempts WHERE target_kind = 'Goal'"
        ).fetchall()
        assert any("Builder reviewed bad" in r[0] for r in rows)
        assert any("missing hypothesis H" in r[0] for r in rows)

    def test_bad_goal_writes_parent_dead_attempts(self, db, tmp_path):
        """bad_goal → dead_attempts also written for parent goal when findable."""
        now = "2026-01-01T00:00:00+00:00"
        # Use distinct lean_paths to avoid UNIQUE constraint
        parent_goal_lean = tmp_path / "parent_goal.lean"
        parent_goal_lean.write_text("placeholder", encoding="utf-8")
        sub_goal_lean = tmp_path / "sub_goal.lean"
        sub_goal_lean.write_text("placeholder", encoding="utf-8")
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        leaf_strategy_lean = tmp_path / "leaf_strat.lean"
        leaf_strategy_lean.write_text(_lean_source(), encoding="utf-8")

        with db:
            db.execute(
                "INSERT INTO goals "
                "(problem, slug, lean_path, origin, kind, status, commit_state, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("example", "parent_g", str(parent_goal_lean), "root", "theorem",
                 "open", "live", now, now),
            )
            parent_goal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            db.execute(
                "INSERT INTO strategies "
                "(goal_id, lean_path, status, commit_state, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (parent_goal_id, str(strategy_lean), "proposed", "live", now),
            )
            parent_strat_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            db.execute(
                "INSERT INTO goals "
                "(problem, slug, lean_path, origin, kind, status, commit_state, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("example", "sub_g", str(sub_goal_lean), "backward", "theorem",
                 "open", "live", now, now),
            )
            sub_goal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            db.execute(
                "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position) "
                "VALUES (?, ?, ?)",
                (parent_strat_id, sub_goal_id, 0),
            )

            db.execute(
                "INSERT INTO strategies "
                "(goal_id, lean_path, status, commit_state, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (sub_goal_id, str(leaf_strategy_lean), "proposed", "live", now),
            )
            leaf_strat_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        chain = _mock_chain(_json_block({"bad_goal": "bad"}))
        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            Builder(
                leaf_strat_id, db,
                BuilderConfig(base_dir=str(tmp_path)),
                chain=chain,
            ).run()

        goal_da = db.execute(
            "SELECT target_id, reason_summary FROM dead_attempts WHERE target_kind='Goal'"
        ).fetchall()
        target_ids = {r[0] for r in goal_da}
        assert str(sub_goal_id) in target_ids
        assert str(parent_goal_id) in target_ids

    def test_chain_exhausted_returns_exhausted(self, db, tmp_path):
        """chain.run returns exhausted (all providers failed) → outcome=exhausted."""
        _, strategy_id = self._setup(db, tmp_path)

        chain = _mock_chain("", outcome="exhausted")
        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            result = Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path), max_retries=1),
                chain=chain,
            ).run()

        assert result.outcome == "exhausted"


# ---------------------------------------------------------------------------
# 9. self_verify — extracted stage behavior
# ---------------------------------------------------------------------------


class TestSelfVerify:
    def test_proved_returns_true(self, db, tmp_path):
        """_self_verify returns True only when lake outcome is 'proved'."""
        builder = Builder(1, db, BuilderConfig(base_dir=str(tmp_path)))
        staging = tmp_path / "test.lean"
        staging.write_text("theorem t : True := trivial", encoding="utf-8")

        with patch(
            "Tooling.pipelines.builder.run_lean",
            return_value=LakeResult(outcome="proved"),
        ):
            assert builder._self_verify(staging, timeout=5.0) is True

    def test_exhausted_returns_false(self, db, tmp_path):
        """_self_verify returns False when lake outcome is 'exhausted' (error)."""
        builder = Builder(1, db, BuilderConfig(base_dir=str(tmp_path)))
        staging = tmp_path / "test.lean"
        staging.write_text("theorem t : True := by sorry", encoding="utf-8")

        with patch(
            "Tooling.pipelines.builder.run_lean",
            return_value=LakeResult(
                outcome="exhausted",
                messages=[{"kind": "error", "data": "type mismatch"}],
            ),
        ):
            assert builder._self_verify(staging, timeout=5.0) is False

    def test_hassorry_returns_false(self, db, tmp_path):
        """_self_verify returns False for hasSorry (proves nothing)."""
        builder = Builder(1, db, BuilderConfig(base_dir=str(tmp_path)))
        staging = tmp_path / "test.lean"
        staging.write_text("theorem t : True := by sorry", encoding="utf-8")

        with patch(
            "Tooling.pipelines.builder.run_lean",
            return_value=LakeResult(
                outcome="exhausted",
                messages=[{"kind": "hasSorry", "data": "uses sorry"}],
            ),
        ):
            assert builder._self_verify(staging, timeout=5.0) is False

    def test_timed_out_returns_false(self, db, tmp_path):
        """_self_verify returns False when lake times out."""
        builder = Builder(1, db, BuilderConfig(base_dir=str(tmp_path)))
        staging = tmp_path / "test.lean"
        staging.write_text("theorem t : True := by sorry", encoding="utf-8")

        with patch(
            "Tooling.pipelines.builder.run_lean",
            return_value=LakeResult(outcome="exhausted", timed_out=True),
        ):
            assert builder._self_verify(staging, timeout=5.0) is False

    def test_self_verify_triggers_retry_on_fail(self, db, tmp_path):
        """self_verify fail → retry tactic_llm (max_retries times) → exhausted."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # tactic_try all fail; self_verify always fails
        def fake_run(lean_file, cwd, timeout=600.0):
            return _exhausted_result()

        chain = _mock_chain(_json_block({"tactic_proof": "exact rfl"}))
        with patch("Tooling.pipelines.builder.run_lean", side_effect=fake_run):
            result = Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path), max_retries=2),
                chain=chain,
            ).run()

        # Must exhaust retries, not silently pass
        assert result.outcome == "exhausted"
        # chain.run must have been called max_retries times
        assert chain.run.call_count == 2


# ---------------------------------------------------------------------------
# 10. Silent-failure 防線 — non-proved results never silently pass
# ---------------------------------------------------------------------------


class TestSilentFailureGuard:
    def test_lake_non_proved_goes_to_dead_path(self, db, tmp_path):
        """self_verify outcome != 'proved' → retry loop → exhausted (never silent-PASS)."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # Every lake call returns exhausted (error) — self_verify never passes
        def always_exhausted(lean_file, cwd, timeout=600.0):
            return LakeResult(outcome="exhausted", messages=[{"kind": "error", "data": "bad"}])

        chain = _mock_chain(_json_block({"tactic_proof": "exact rfl"}))
        with patch("Tooling.pipelines.builder.run_lean", side_effect=always_exhausted):
            result = Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path), max_retries=2),
                chain=chain,
            ).run()

        assert result.outcome == "exhausted"
        assert result.tactic is None

    def test_agent_json_parse_failure_retries_not_passes(self, db, tmp_path):
        """Agent JSON parse failure → retry agent, not silent-PASS."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # Agent returns gibberish (no valid JSON keys)
        chain = _mock_chain("I am not valid JSON at all, sorry")
        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            result = Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path), max_retries=3),
                chain=chain,
            ).run()

        assert result.outcome == "exhausted"
        # Must have retried max_retries times, not returned after first parse fail
        assert chain.run.call_count == 3

    def test_agent_missing_keys_retries_not_passes(self, db, tmp_path):
        """Agent JSON with unknown keys (not tactic_proof/needs_decomp/bad_goal) → retry."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # JSON is valid but has wrong keys
        chain = _mock_chain(_json_block({"unknown_key": "some_value"}))
        with patch("Tooling.pipelines.builder.run_lean", return_value=_exhausted_result()):
            result = Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path), max_retries=2),
                chain=chain,
            ).run()

        assert result.outcome == "exhausted"
        assert chain.run.call_count == 2

    def test_tactic_try_non_proved_not_silently_committed(self, db, tmp_path):
        """tactic_try lake outcome != 'proved' must not trigger commit."""
        strategy_lean = tmp_path / "strat.lean"
        strategy_lean.write_text(_lean_source(), encoding="utf-8")
        goal_lean = tmp_path / "goal.lean"
        goal_lean.write_text("placeholder", encoding="utf-8")
        _, strategy_id = _make_rows(db, strategy_lean, goal_lean)

        # All tactics return hasSorry (outcome=exhausted) — not proved
        sorry_result = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        with patch("Tooling.pipelines.builder.run_lean", return_value=sorry_result):
            result = Builder(
                strategy_id, db,
                BuilderConfig(base_dir=str(tmp_path)),
            ).run()

        assert result.outcome == "exhausted"
        # strategies.status must NOT be 'succeeded'
        row = db.execute(
            "SELECT status FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()
        assert row[0] == "proposed"
